# -*- coding: utf-8 -*-
"""Profili di scheda: cosa cambia da una macchina all'altra, in un posto solo.

Il programma nasce su una BC-250, ma il programmatore non ha niente di
specifico: gli stessi quattro fili leggono qualunque flash SPI. Quello che
cambia da una scheda all'altra e' contorno, ed e' proprio il contorno che fa
sbagliare -- dove attaccarsi, che chip aspettarsi, quali impronte sono gia'
note, e le avvertenze che valgono su quella macchina e non su un'altra.

⚠️ Un profilo NON e' un filtro: se il chip trovato non e' quello atteso, il
programma lo dice e va avanti lo stesso. Il profilo e' quello che ci
aspettiamo, non quello che imponiamo. Chi ha davanti la scheda vede meglio di
una tabella scritta mesi prima.

Aggiungerne uno e' solo dati: nome, chip, tensione, connettore, impronte note,
avvertenze. Il disegno dei cavi ha due forme -- il connettore della BC-250 e la
pinza sul chip -- e un profilo dice quale delle due usare.
"""
from __future__ import unicode_literals

# le due forme di collegamento che il disegno sa fare
CONNETTORE = "connettore"       # un pettine sulla scheda (BC-250: J4004)
PINZA = "pinza"                 # la pinza direttamente sul chip SOIC-8


class Profilo(object):
    """Cosa sappiamo in anticipo di una scheda."""

    def __init__(self, chiave, nome, chip=(), byte=None, tensione=3.3,
                 collegamento=PINZA, connettore=None, md5=None, avvisi=(),
                 descrizione=None, regioni=()):
        self.chiave = chiave
        self.nome = nome                    # {"it":…, "en":…} o stringa
        self.chip = list(chip)              # modelli attesi, il primo e' quello
        self.byte = byte                    # dimensione attesa della flash
        self.tensione = tensione            # volt del chip: 3.3 o 1.8
        self.collegamento = collegamento
        self.connettore = connettore        # come si chiama, se c'e'
        self.md5 = dict(md5 or {})          # impronta -> {"it":…, "en":…}
        self.avvisi = tuple(avvisi)         # avvertenze proprie della scheda
        self.descrizione = descrizione
        self.regioni = tuple(regioni)       # regioni che ci aspettiamo di trovare

    def testo(self, campo, lingua="it"):
        valore = getattr(self, campo, None)
        if isinstance(valore, dict):
            return valore.get(lingua) or valore.get("it") or ""
        return valore or ""

    @property
    def generico(self):
        return self.chiave == "generico"


PROFILI = [
    Profilo(
        "bc250",
        {"it": "AMD BC-250", "en": "AMD BC-250"},
        chip=["MX25L12835F/MX25L12873F", "MX25L12805D", "W25Q128.V"],
        byte=16 * 1024 * 1024,
        tensione=3.3,
        collegamento=CONNETTORE,
        connettore="J4004",
        md5={
            "3487f648a69a781d2609a8d4e6f4808e": {
                "it": "BIOS originale P3.00",
                "en": "stock BIOS P3.00",
            },
            "f7632f2ff61a7a5e65fff74d09942aeb": {
                "it": "risultato atteso dopo la modifica",
                "en": "expected result after the modification",
            },
        },
        avvisi=("prof_bc250_sio",),
        descrizione={
            "it": "Connettore J4004 a 8 piedini accanto al chip BIOS. "
                  "Sulla scheda ci sono DUE flash: quella grande da 16 MiB "
                  "è il BIOS, quella da 512 KiB è il SuperIO.",
            "en": "Eight-pin J4004 header next to the BIOS chip. The board "
                  "carries TWO flash chips: the 16 MiB one is the BIOS, the "
                  "512 KiB one is the SuperIO.",
        },
        regioni=("bios", "apcb", "psp"),
    ),
    Profilo(
        "generico",
        {"it": "Scheda generica", "en": "Generic board"},
        chip=[],
        byte=None,
        tensione=3.3,
        collegamento=PINZA,
        avvisi=("prof_gen_pinza",),
        descrizione={
            "it": "Qualunque flash SPI in contenitore SOIC-8, presa con una "
                  "pinza. È il caso più comune fuori da una scheda "
                  "conosciuta.",
            "en": "Any SPI flash in a SOIC-8 package, taken with a clip. This "
                  "is the common case outside a known board.",
        },
    ),
]

PER_CHIAVE = dict((p.chiave, p) for p in PROFILI)
PREDEFINITO = "bc250"


def prendi(chiave):
    """Il profilo con quella chiave, o quello predefinito."""
    return PER_CHIAVE.get(chiave) or PER_CHIAVE[PREDEFINITO]


def chiavi():
    return [p.chiave for p in PROFILI]


def nomi(lingua="it"):
    return [(p.chiave, p.testo("nome", lingua)) for p in PROFILI]


def scostamenti(profilo, chip_trovato=None, byte_trovati=None, regioni=()):
    """Dove la scheda vera non coincide con quello che il profilo si aspetta.

    Restituisce una lista di (chiave_messaggio, campi). Vuota = tutto come
    previsto. ⚠️ Sono avvisi, non divieti: un chip diverso da quello atteso
    puo' benissimo essere una revisione successiva della stessa scheda.
    """
    fuori = []
    if profilo.byte and byte_trovati and byte_trovati != profilo.byte:
        fuori.append(("prof_dim_diversa",
                      {"atteso": profilo.byte, "trovato": byte_trovati}))
    if profilo.chip and chip_trovato:
        atteso = [c.lower() for c in profilo.chip]
        nome = chip_trovato.lower()
        if not any(nome in c or c in nome for c in atteso):
            fuori.append(("prof_chip_diverso",
                          {"atteso": profilo.chip[0], "trovato": chip_trovato}))
    if profilo.regioni and regioni:
        trovate = set(regioni)
        mancanti = [n for n in profilo.regioni if n not in trovate]
        if mancanti:
            fuori.append(("prof_regioni_mancanti",
                          {"quali": ", ".join(mancanti)}))
    return fuori
