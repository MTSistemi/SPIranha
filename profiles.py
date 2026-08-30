# -*- coding: utf-8 -*-
"""Board profiles: what changes from one machine to the next, in one place.

The program was born on a BC-250, but there is nothing board-specific about
the programmer itself: the same four wires read any SPI flash. What changes
from board to board is the surroundings, and the surroundings are exactly
what trips people up -- where to attach, which chip to expect, which
fingerprints are already known, and the warnings that apply to that machine
and not to another.

⚠️ A profile is NOT a filter: if the chip found is not the expected one, the
program says so and carries on. A profile is what we expect, not what we
impose. Whoever has the board in front of them can see better than a table
written months ago.

Adding one is data only: name, chip, voltage, header, known fingerprints,
warnings. The wiring drawing comes in two shapes -- the BC-250 header and the
clip on the chip -- and a profile says which of the two to use.
"""
from __future__ import unicode_literals

# the two kinds of connection the drawing knows how to show
CONNETTORE = "connettore"       # a header on the board (BC-250: J4004)
PINZA = "pinza"                 # the clip straight onto the SOIC-8 chip


class Profilo(object):
    """What we know about a board in advance."""

    def __init__(self, chiave, nome, chip=(), byte=None, tensione=3.3,
                 collegamento=PINZA, connettore=None, md5=None, avvisi=(),
                 descrizione=None, regioni=()):
        self.chiave = chiave
        self.nome = nome                    # {"it":…, "en":…} or a string
        self.chip = list(chip)              # expected models, first is the one
        self.byte = byte                    # expected flash size
        self.tensione = tensione            # chip volts: 3.3 or 1.8
        self.collegamento = collegamento
        self.connettore = connettore        # what it is called, if any
        self.md5 = dict(md5 or {})          # fingerprint -> {"it":…, "en":…}
        self.avvisi = tuple(avvisi)         # the board's own warnings
        self.descrizione = descrizione
        self.regioni = tuple(regioni)       # regions we expect to find

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
    """The profile with that key, or the default one."""
    return PER_CHIAVE.get(chiave) or PER_CHIAVE[PREDEFINITO]


def chiavi():
    return [p.chiave for p in PROFILI]


def nomi(lingua="it"):
    return [(p.chiave, p.testo("nome", lingua)) for p in PROFILI]


def scostamenti(profilo, chip_trovato=None, byte_trovati=None, regioni=()):
    """Where the real board does not match what the profile expects.

    Returns a list of (message_key, fields). Empty = everything as expected.
    ⚠️ These are warnings, not prohibitions: a chip other than the expected
    one may perfectly well be a later revision of the same board.
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
