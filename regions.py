# -*- coding: utf-8 -*-
"""The regions of a ROM, read out of the image itself.

A BIOS dump is not one solid block: inside it there is a map saying where each
piece starts and ends. Two formats cover almost the whole field:

  - the **Intel descriptor** (IFD), the first 4 KiB of every Intel-chipset
    flash: it says where the descriptor, BIOS, ME, GbE and EC live;
  - **FMAP**, the map coreboot (and everything derived from it) carries: a
    `__FMAP__` signature followed by the list of named areas.

⚠️ This reads the IMAGE, not the chip. The reason is practical: we already
have the image -- it is the one just read, or the one about to be written --
whereas asking the chip means another round of flashrom over the wires. And
there is a better reason: this way the chip's regions can be compared with the
new image's BEFORE writing, and a different map gets noticed.

Regions are what let you write only the piece that matters: on a board that
still boots, rewriting ME or the descriptor when the BIOS would do is risk for
nothing.
"""
from __future__ import unicode_literals

import struct

# ----------------------------------------------------------------- Intel IFD

FIRMA_IFD = 0x0FF0A55A
POSIZIONE_FIRMA = 0x10
SETTORE_IFD = 0x1000

# The names are flashrom's own, not invented: a layout written with these
# names still reads properly next to an --ifd.
NOMI_IFD = ("fd", "bios", "me", "gbe", "pd", "reg5", "bios2", "reg7",
            "ec", "reg9", "ie", "10gbe", "reg12", "reg13", "reg14", "reg15")

# ---------------------------------------------------------------------- FMAP

FIRMA_FMAP = b"__FMAP__"
TESTA_FMAP = struct.Struct("<8sBBQI32sH")     # firma, ver, base, dim, nome, n
AREA_FMAP = struct.Struct("<II32sH")          # inizio, dimensione, nome, flag
ALLINEAMENTO_FMAP = 64
MAX_AREE = 400


class Regione(object):
    """A named piece of ROM, from the first to the last byte inclusive."""

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
    """The names arrive as fixed-length fields, padded with trailing zeros."""
    if isinstance(nome, bytes):
        nome = nome.split(b"\x00")[0].decode("ascii", "replace")
    return "".join(c if (c.isalnum() or c in "-_") else "_"
                   for c in nome.strip()).strip("_") or "senza_nome"


def regioni_ifd(dati):
    """The Intel descriptor's regions, or [] when there is no descriptor."""
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
        # ⚠️ base > limit is not a read error: it is how the descriptor
        # says "this region does not exist on this board".
        if inizio > fine or fine >= len(dati):
            continue
        nome = NOMI_IFD[indice] if indice < len(NOMI_IFD) else "reg%d" % indice
        fuori.append(Regione(nome, inizio, fine, "ifd"))
    return fuori


def regioni_fmap(dati):
    """The areas an FMAP declares, or [] when there is no valid one."""
    posizione = -1
    while True:
        posizione = dati.find(FIRMA_FMAP, posizione + 1)
        if posizione == -1:
            return []
        # the spec wants it aligned: that way we do not chase copies of
        # the signature that happen to sit inside the data
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

# ⚠️ The addresses in the AMD structures are the ones the CPU sees
# (0xFF8E0000), not offsets in the file: they have to be brought back
# inside the image.
def _in_immagine(indirizzo, dimensione):
    if not indirizzo or indirizzo in (0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF):
        return None
    offset = indirizzo & (dimensione - 1) if dimensione else indirizzo
    return offset if offset < dimensione else None


# Only the types whose name is certain: the others keep their number,
# which is less convenient but is not a lie.
NOMI_PSP = {0x00: "amd_pubkey", 0x01: "psp_bootloader", 0x02: "psp_os",
            0x08: "smu", 0x12: "smu2", 0x24: "sec_gasket", 0x28: "mp2"}
NOMI_BHD = {0x60: "apcb", 0x61: "apob", 0x62: "bios", 0x63: "apcb_scorta",
            0x68: "bios_l2", 0x70: "bios_dir_l2"}


def _direttorio(dati, posizione, firme, passo, formato):
    """Reads an AMD directory.

    Returns (signature, entries, table_end, contents_end): the table and the
    pieces it points at are two different things and have to be kept apart, or
    a "directory" region would end up covering half the chip.
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
        # address; the BHD also carries the destination in memory at the
        # end, which is no use here and must not be mistaken for the
        # address in the file
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
    """The regions of an AMD ROM, from the EFS structure.

    AMD boards have neither an Intel descriptor nor an FMAP: they have this.
    It sits at a fixed offset, declares where the PSP and BIOS directories
    are, and from there you reach the real pieces -- including the one people
    usually want to rewrite, the BIOS image.
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
            # for the PSP the whole area is what matters: the pieces are
            # many and nobody rewrites them one at a time
            fuori.append(Regione(nome, posizione, ultimo, "amd"))
            continue
        # the BIOS directory's entries, on the other hand, are few and are
        # the ones that really matter: the UEFI image, the memory config
        fuori.append(Regione(nome, posizione, fine_tabella, "amd"))
        for tipo, inizio, quanti in voci:
            fuori.append(Regione(NOMI_BHD.get(tipo, "bios_0x%02X" % tipo),
                                 inizio, inizio + quanti - 1, "amd"))
    fuori.sort(key=lambda r: (r.inizio, r.fine))
    return fuori


def trova(dati):
    """The image's regions, from wherever they can be read.

    The IFD first, which sits at a fixed place and cannot be mistaken; then
    the FMAP. Returns (source, [Regione]); (None, []) when the image says
    nothing about itself, which is the common case on AMD boards.
    """
    trovate = regioni_ifd(dati)
    if trovate:
        # On Intel the two maps coexist: the FMAP describes the inside of
        # the BIOS region. The extra areas are added, without duplicates.
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
    """A flashrom layout file, with the regions' real names.

    ⚠️ Regions can nest (an FMAP inside an IFD's BIOS) and flashrom wants a
    flat list: all of them are written here, because it is the user who picks
    one with --image, and overlapping ones do no harm as long as only one is
    used.
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
