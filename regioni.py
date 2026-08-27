# -*- coding: utf-8 -*-
"""Le regioni di una ROM, lette dall'immagine stessa.

Un dump di BIOS non e' un blocco unico: dentro c'e' una mappa che dice dove
comincia e dove finisce ogni pezzo. Due formati coprono quasi tutto il parco
macchine:

  - il **descrittore Intel** (IFD), i primi 4 KiB di ogni flash di chipset
    Intel: dice dove stanno descrittore, BIOS, ME, GbE, EC;
  - **FMAP**, la mappa che coreboot (e chi ne deriva) si porta dentro: una
    firma `__FMAP__` seguita dall'elenco delle aree con nome.

⚠️ Si legge dall'IMMAGINE, non dal chip. Il motivo e' pratico: l'immagine ce
l'abbiamo gia' -- e' quella appena letta, o quella che si sta per scrivere --
mentre chiedere al chip vuol dire un altro giro di flashrom sui fili. E c'e' un
motivo migliore: cosi' si possono confrontare le regioni del chip con quelle
dell'immagine nuova PRIMA di scrivere, e accorgersi che non e' la stessa mappa.

Le regioni servono a scrivere solo il pezzo che interessa: su una scheda che si
accende ancora, riscrivere ME o il descrittore quando basta il BIOS e' rischio
gratuito.
"""
from __future__ import unicode_literals

import struct

# ----------------------------------------------------------------- Intel IFD

FIRMA_IFD = 0x0FF0A55A
POSIZIONE_FIRMA = 0x10
SETTORE_IFD = 0x1000

# I nomi sono quelli di flashrom, non di fantasia: un layout scritto con questi
# nomi resta leggibile accanto a un --ifd.
NOMI_IFD = ("fd", "bios", "me", "gbe", "pd", "reg5", "bios2", "reg7",
            "ec", "reg9", "ie", "10gbe", "reg12", "reg13", "reg14", "reg15")

# ---------------------------------------------------------------------- FMAP

FIRMA_FMAP = b"__FMAP__"
TESTA_FMAP = struct.Struct("<8sBBQI32sH")     # firma, ver, base, dim, nome, n
AREA_FMAP = struct.Struct("<II32sH")          # inizio, dimensione, nome, flag
ALLINEAMENTO_FMAP = 64
MAX_AREE = 400


class Regione(object):
    """Un pezzo di ROM con un nome, dal primo all'ultimo byte compresi."""

    def __init__(self, nome, inizio, fine, origine=None):
        self.nome = nome
        self.inizio = inizio
        self.fine = fine
        self.origine = origine

    @property
    def byte(self):
        return self.fine - self.inizio + 1

    def __repr__(self):
        return "<%s 0x%06X-0x%06X>" % (self.nome, self.inizio, self.fine)


def _pulisci(nome):
    """I nomi arrivano come campi a lunghezza fissa, pieni di zeri in coda."""
    if isinstance(nome, bytes):
        nome = nome.split(b"\x00")[0].decode("ascii", "replace")
    return "".join(c if (c.isalnum() or c in "-_") else "_"
                   for c in nome.strip()).strip("_") or "senza_nome"


def regioni_ifd(dati):
    """Le regioni del descrittore Intel, o [] se non c'e' un descrittore."""
    if len(dati) < SETTORE_IFD:
        return []
    if struct.unpack_from("<I", dati, POSIZIONE_FIRMA)[0] != FIRMA_IFD:
        return []
    mappa = struct.unpack_from("<I", dati, 0x14)[0]
    base = (mappa >> 16 & 0xFF) << 4          # FRBA
    quante = (mappa >> 24 & 0x07) + 1         # NR
    fuori = []
    for indice in range(quante):
        posizione = base + indice * 4
        if posizione + 4 > len(dati):
            break
        valore = struct.unpack_from("<I", dati, posizione)[0]
        inizio = (valore & 0x7FFF) << 12
        fine = (((valore >> 16) & 0x7FFF) << 12) | 0xFFF
        # ⚠️ base > limite non e' un errore di lettura: e' come il descrittore
        # dice "questa regione non esiste su questa scheda".
        if inizio > fine or fine >= len(dati):
            continue
        nome = NOMI_IFD[indice] if indice < len(NOMI_IFD) else "reg%d" % indice
        fuori.append(Regione(nome, inizio, fine, "ifd"))
    return fuori


def regioni_fmap(dati):
    """Le aree dichiarate da una FMAP, o [] se non ce n'e' una valida."""
    posizione = -1
    while True:
        posizione = dati.find(FIRMA_FMAP, posizione + 1)
        if posizione == -1:
            return []
        # la specifica la vuole allineata: cosi' non si inseguono le copie
        # della firma che capitano dentro i dati
        if posizione % ALLINEAMENTO_FMAP:
            continue
        if posizione + TESTA_FMAP.size > len(dati):
            continue
        _f, maggiore, _minore, _base, _dim, nome, quante = TESTA_FMAP.unpack_from(
            dati, posizione)
        if maggiore != 1 or not 0 < quante <= MAX_AREE:
            continue
        fine_elenco = posizione + TESTA_FMAP.size + quante * AREA_FMAP.size
        if fine_elenco > len(dati):
            continue
        fuori = []
        buona = True
        for indice in range(quante):
            a = posizione + TESTA_FMAP.size + indice * AREA_FMAP.size
            inizio, dimensione, etichetta, _flag = AREA_FMAP.unpack_from(dati, a)
            if dimensione == 0:
                continue          # segnaposto: dichiarata e vuota
            if inizio + dimensione > len(dati):
                buona = False     # non e' la FMAP di questa immagine
                break
            fuori.append(Regione(_pulisci(etichetta), inizio,
                                 inizio + dimensione - 1, "fmap"))
        if buona and fuori:
            fuori.sort(key=lambda r: (r.inizio, r.fine))
            return fuori


# ----------------------------------------------------------------- AMD (EFS)

# La struttura AMD sta in uno di questi punti fissi, e in nessun altro.
POSIZIONI_EFS = (0xFA0000, 0xF20000, 0xE20000, 0xC20000, 0x820000, 0x20000)
FIRMA_EFS = 0x55AA55AA
FIRME_PSP = (b"$PSP", b"$PL2")
FIRME_BHD = (b"$BHD", b"$BL2")

# ⚠️ Gli indirizzi nelle strutture AMD sono quelli visti dalla CPU
# (0xFF8E0000), non offset nel file: vanno riportati dentro l'immagine.
def _in_immagine(indirizzo, dimensione):
    if not indirizzo or indirizzo in (0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF):
        return None
    offset = indirizzo & (dimensione - 1) if dimensione else indirizzo
    return offset if offset < dimensione else None


# Solo i tipi di cui il nome e' certo: gli altri restano il loro numero, che
# e' meno comodo ma non e' una bugia.
NOMI_PSP = {0x00: "amd_pubkey", 0x01: "psp_bootloader", 0x02: "psp_os",
            0x08: "smu", 0x12: "smu2", 0x24: "sec_gasket", 0x28: "mp2"}
NOMI_BHD = {0x60: "apcb", 0x61: "apob", 0x62: "bios", 0x63: "apcb_scorta",
            0x68: "bios_l2", 0x70: "bios_dir_l2"}


def _direttorio(dati, posizione, firme, passo, formato):
    """Legge un direttorio AMD.

    Restituisce (firma, voci, fine_tabella, fine_contenuti): la tabella e i
    pezzi a cui punta sono due cose diverse e vanno tenute separate, o una
    regione «direttorio» finirebbe per coprire mezzo chip.
    """
    if posizione is None or posizione + 16 > len(dati):
        return None, [], None, None
    firma = dati[posizione:posizione + 4]
    if firma not in firme:
        return None, [], None, None
    quante = struct.unpack_from("<I", dati, posizione + 8)[0]
    if not 0 < quante <= 256:
        return None, [], None, None
    fine_tabella = posizione + 16 + quante * passo
    if fine_tabella > len(dati):
        return None, [], None, None
    voci = []
    ultimo = fine_tabella - 1
    for indice in range(quante):
        pezzi = formato.unpack_from(dati, posizione + 16 + indice * passo)
        # tipo, poi (a distanza fissa in tutti e due i formati) dimensione e
        # indirizzo; il BHD ha in coda anche la destinazione in memoria, che
        # qui non serve e non va scambiata per l'indirizzo nel file
        tipo, dimensione, indirizzo = pezzi[0], pezzi[3], pezzi[4]
        inizio = _in_immagine(indirizzo, len(dati))
        if inizio is None or not dimensione or inizio + dimensione > len(dati):
            continue
        voci.append((tipo, inizio, dimensione))
        ultimo = max(ultimo, inizio + dimensione - 1)
    return (firma.decode("ascii", "replace"), voci, fine_tabella - 1, ultimo)


_VOCE_PSP = struct.Struct("<BBHIQ")        # tipo, sub, rsvd, dimensione, dove
_VOCE_BHD = struct.Struct("<BBHIQQ")       # tipo, regione, flag, dim, dove, dest


def regioni_amd(dati):
    """Le regioni di una ROM AMD, dalla struttura EFS.

    Le schede AMD non hanno ne' descrittore Intel ne' FMAP: hanno questa. Sta
    in un punto fisso, dichiara dove sono il direttorio PSP e quello del BIOS,
    e da li' si arriva ai pezzi veri -- compreso quello che di solito si vuole
    riscrivere, l'immagine BIOS.
    """
    dimensione = len(dati)
    posizione_efs = None
    for candidata in POSIZIONI_EFS:
        if candidata + 0x24 > dimensione:
            continue
        if struct.unpack_from("<I", dati, candidata)[0] == FIRMA_EFS:
            posizione_efs = candidata
            break
    if posizione_efs is None:
        return []

    fuori = [Regione("efs", posizione_efs, posizione_efs + SETTORE_IFD - 1, "amd")]
    campi = struct.unpack_from("<9I", dati, posizione_efs)
    # +0x10 psp vecchio, +0x14 psp nuovo, +0x18/0x1C/0x20 direttori BIOS
    visti = set()
    for indice, firme, passo, formato, nome in (
            (4, FIRME_PSP, 16, _VOCE_PSP, "psp"),
            (5, FIRME_PSP, 16, _VOCE_PSP, "psp"),
            (6, FIRME_BHD, 24, _VOCE_BHD, "bios_dir"),
            (7, FIRME_BHD, 24, _VOCE_BHD, "bios_dir"),
            (8, FIRME_BHD, 24, _VOCE_BHD, "bios_dir")):
        posizione = _in_immagine(campi[indice], dimensione)
        firma, voci, fine_tabella, ultimo = _direttorio(
            dati, posizione, firme, passo, formato)
        if firma is None or posizione in visti:
            continue
        visti.add(posizione)
        if passo == 16:
            # del PSP interessa l'area intera: i pezzi sono tanti e nessuno
            # li riscrive uno per uno
            fuori.append(Regione(nome, posizione, ultimo, "amd"))
            continue
        # le voci del direttorio BIOS invece sono poche e sono quelle che
        # contano davvero: l'immagine UEFI, la configurazione della memoria
        fuori.append(Regione(nome, posizione, fine_tabella, "amd"))
        for tipo, inizio, quanti in voci:
            fuori.append(Regione(NOMI_BHD.get(tipo, "bios_0x%02X" % tipo),
                                 inizio, inizio + quanti - 1, "amd"))
    fuori.sort(key=lambda r: (r.inizio, r.fine))
    return fuori


def trova(dati):
    """Le regioni dell'immagine, da dove si riesce a leggerle.

    Prima l'IFD, che sta in un posto fisso e non si puo' confondere; poi la
    FMAP. Restituisce (origine, [Regione]); ([], None) se l'immagine non dice
    niente di se stessa, che e' il caso piu' comune sulle schede AMD.
    """
    trovate = regioni_ifd(dati)
    if trovate:
        # Su Intel le due mappe convivono: la FMAP descrive l'interno della
        # regione BIOS. Le aree in piu' si aggiungono, senza doppioni.
        gia = set((r.inizio, r.fine) for r in trovate)
        for regione in regioni_fmap(dati):
            if (regione.inizio, regione.fine) not in gia:
                trovate.append(regione)
        trovate.sort(key=lambda r: (r.inizio, r.fine))
        return "ifd", trovate
    trovate = regioni_fmap(dati)
    if trovate:
        return "fmap", trovate
    trovate = regioni_amd(dati)
    if trovate:
        return "amd", trovate
    return None, []


def come_layout(regioni, dimensione):
    """Un file di layout per flashrom, con i nomi veri delle regioni.

    ⚠️ Le regioni possono annidarsi (una FMAP dentro il BIOS di un IFD) e
    flashrom vuole un elenco piatto: qui si scrivono tutte, perche' e'
    l'utente a sceglierne una con --image, e sovrapposte non danno fastidio
    finche' se ne usa una sola.
    """
    righe = []
    usati = {}
    for regione in sorted(regioni, key=lambda r: (r.inizio, r.fine)):
        nome = regione.nome
        if nome in usati:
            usati[nome] += 1
            nome = "%s_%d" % (nome, usati[nome])
        else:
            usati[nome] = 0
        righe.append("%08x:%08x %s" % (regione.inizio, regione.fine, nome))
    return "\n".join(righe) + ("\n" if righe else "")
