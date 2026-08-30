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

IFD_SIGNATURE = 0x0FF0A55A
SIGNATURE_OFFSET = 0x10
IFD_SECTOR = 0x1000

# The names are flashrom's own, not invented: a layout written with these
# names still reads properly next to an --ifd.
IFD_NAMES = ("fd", "bios", "me", "gbe", "pd", "reg5", "bios2", "reg7",
            "ec", "reg9", "ie", "10gbe", "reg12", "reg13", "reg14", "reg15")

# ---------------------------------------------------------------------- FMAP

FMAP_SIGNATURE = b"__FMAP__"
FMAP_HEADER = struct.Struct("<8sBBQI32sH")     # firma, ver, base, dim, nome, n
FMAP_AREA = struct.Struct("<II32sH")          # inizio, dimensione, nome, flag
FMAP_ALIGNMENT = 64
MAX_AREAS = 400


class Region(object):
    """A named piece of ROM, from the first to the last byte inclusive."""

    def __init__(self, name, start, end, source=None):
        self.name = name
        self.start = start
        self.end = end
        self.source = source

    @property
    def size(self):
        return self.end - self.start + 1

    def __repr__(self):
        return "<%s 0x%06X-0x%06X>" % (self.name, self.start, self.end)


def _pulisci(name):
    """The names arrive as fixed-length fields, padded with trailing zeros."""
    if isinstance(name, bytes):
        name = name.split(b"\x00")[0].decode("ascii", "replace")
    return "".join(c if (c.isalnum() or c in "-_") else "_"
                   for c in name.strip()).strip("_") or "senza_nome"


def ifd_regions(data):
    """The Intel descriptor's regions, or [] when there is no descriptor."""
    if len(data) < IFD_SECTOR:
        return []
    if struct.unpack_from("<I", data, SIGNATURE_OFFSET)[0] != IFD_SIGNATURE:
        return []
    chip_map = struct.unpack_from("<I", data, 0x14)[0]
    base = (chip_map >> 16 & 0xFF) << 4          # FRBA
    count = (chip_map >> 24 & 0x07) + 1         # NR
    out = []
    for index in range(count):
        position = base + index * 4
        if position + 4 > len(data):
            break
        value_for = struct.unpack_from("<I", data, position)[0]
        start = (value_for & 0x7FFF) << 12
        end = (((value_for >> 16) & 0x7FFF) << 12) | 0xFFF
        # ⚠️ base > limit is not a read error: it is how the descriptor
        # says "this region does not exist on this board".
        if start > end or end >= len(data):
            continue
        name = IFD_NAMES[index] if index < len(IFD_NAMES) else "reg%d" % index
        out.append(Region(name, start, end, "ifd"))
    return out


def fmap_regions(data):
    """The areas an FMAP declares, or [] when there is no valid one."""
    position = -1
    while True:
        position = data.find(FMAP_SIGNATURE, position + 1)
        if position == -1:
            return []
        # the spec wants it aligned: that way we do not chase copies of
        # the signature that happen to sit inside the data
        if position % FMAP_ALIGNMENT:
            continue
        if position + FMAP_HEADER.size > len(data):
            continue
        _f, maggiore, _minore, _base, _dim, name, count = FMAP_HEADER.unpack_from(
            data, position)
        if maggiore != 1 or not 0 < count <= MAX_AREAS:
            continue
        fine_elenco = position + FMAP_HEADER.size + count * FMAP_AREA.size
        if fine_elenco > len(data):
            continue
        out = []
        buona = True
        for index in range(count):
            a = position + FMAP_HEADER.size + index * FMAP_AREA.size
            start, total_size, label_for, _flag = FMAP_AREA.unpack_from(data, a)
            if total_size == 0:
                continue          # segnaposto: dichiarata e vuota
            if start + total_size > len(data):
                buona = False     # non e' la FMAP di questa immagine
                break
            out.append(Region(_pulisci(label_for), start,
                                 start + total_size - 1, "fmap"))
        if buona and out:
            out.sort(key=lambda r: (r.start, r.end))
            return out


# ----------------------------------------------------------------- AMD (EFS)

# La struttura AMD sta in uno di questi punti fissi, e in nessun altro.
EFS_OFFSETS = (0xFA0000, 0xF20000, 0xE20000, 0xC20000, 0x820000, 0x20000)
EFS_SIGNATURE = 0x55AA55AA
PSP_SIGNATURES = (b"$PSP", b"$PL2")
BHD_SIGNATURES = (b"$BHD", b"$BL2")

# ⚠️ The addresses in the AMD structures are the ones the CPU sees
# (0xFF8E0000), not offsets in the file: they have to be brought back
# inside the image.
def _in_immagine(address, total_size):
    if not address or address in (0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF):
        return None
    offset = address & (total_size - 1) if total_size else address
    return offset if offset < total_size else None


# Only the types whose name is certain: the others keep their number,
# which is less convenient but is not a lie.
PSP_NAMES = {0x00: "amd_pubkey", 0x01: "psp_bootloader", 0x02: "psp_os",
            0x08: "smu", 0x12: "smu2", 0x24: "sec_gasket", 0x28: "mp2"}
BHD_NAMES = {0x60: "apcb", 0x61: "apob", 0x62: "bios", 0x63: "apcb_scorta",
            0x68: "bios_l2", 0x70: "bios_dir_l2"}


def _direttorio(data, position, signatures, pitch, formato):
    """Reads an AMD directory.

    Returns (signature, entries, table_end, contents_end): the table and the
    pieces it points at are two different things and have to be kept apart, or
    a "directory" region would end up covering half the chip.
    """
    if position is None or position + 16 > len(data):
        return None, [], None, None
    sig = data[position:position + 4]
    if sig not in signatures:
        return None, [], None, None
    count = struct.unpack_from("<I", data, position + 8)[0]
    if not 0 < count <= 256:
        return None, [], None, None
    fine_tabella = position + 16 + count * pitch
    if fine_tabella > len(data):
        return None, [], None, None
    entries = []
    last = fine_tabella - 1
    for index in range(count):
        chunks = formato.unpack_from(data, position + 16 + index * pitch)
        # tipo, poi (a distanza fissa in tutti e due i formati) dimensione e
        # address; the BHD also carries the destination in memory at the
        # end, which is no use here and must not be mistaken for the
        # address in the file
        kind, total_size, address = chunks[0], chunks[3], chunks[4]
        start = _in_immagine(address, len(data))
        if start is None or not total_size or start + total_size > len(data):
            continue
        entries.append((kind, start, total_size))
        last = max(last, start + total_size - 1)
    return (sig.decode("ascii", "replace"), entries, fine_tabella - 1, last)


_VOCE_PSP = struct.Struct("<BBHIQ")        # tipo, sub, rsvd, dimensione, dove
_VOCE_BHD = struct.Struct("<BBHIQQ")       # tipo, regione, flag, dim, dove, dest


def amd_regions(data):
    """The regions of an AMD ROM, from the EFS structure.

    AMD boards have neither an Intel descriptor nor an FMAP: they have this.
    It sits at a fixed offset, declares where the PSP and BIOS directories
    are, and from there you reach the real pieces -- including the one people
    usually want to rewrite, the BIOS image.
    """
    total_size = len(data)
    posizione_efs = None
    for candidate in EFS_OFFSETS:
        if candidate + 0x24 > total_size:
            continue
        if struct.unpack_from("<I", data, candidate)[0] == EFS_SIGNATURE:
            posizione_efs = candidate
            break
    if posizione_efs is None:
        return []

    out = [Region("efs", posizione_efs, posizione_efs + IFD_SECTOR - 1, "amd")]
    fields = struct.unpack_from("<9I", data, posizione_efs)
    # +0x10 psp vecchio, +0x14 psp nuovo, +0x18/0x1C/0x20 direttori BIOS
    visti = set()
    for index, signatures, pitch, formato, name in (
            (4, PSP_SIGNATURES, 16, _VOCE_PSP, "psp"),
            (5, PSP_SIGNATURES, 16, _VOCE_PSP, "psp"),
            (6, BHD_SIGNATURES, 24, _VOCE_BHD, "bios_dir"),
            (7, BHD_SIGNATURES, 24, _VOCE_BHD, "bios_dir"),
            (8, BHD_SIGNATURES, 24, _VOCE_BHD, "bios_dir")):
        position = _in_immagine(fields[index], total_size)
        sig, entries, fine_tabella, last = _direttorio(
            data, position, signatures, pitch, formato)
        if sig is None or position in visti:
            continue
        visti.add(position)
        if pitch == 16:
            # for the PSP the whole area is what matters: the pieces are
            # many and nobody rewrites them one at a time
            out.append(Region(name, position, last, "amd"))
            continue
        # the BIOS directory's entries, on the other hand, are few and are
        # the ones that really matter: the UEFI image, the memory config
        out.append(Region(name, position, fine_tabella, "amd"))
        for kind, start, how_many in entries:
            out.append(Region(BHD_NAMES.get(kind, "bios_0x%02X" % kind),
                                 start, start + how_many - 1, "amd"))
    out.sort(key=lambda r: (r.start, r.end))
    return out


def find_regions(data):
    """The image's regions, from wherever they can be read.

    The IFD first, which sits at a fixed place and cannot be mistaken; then
    the FMAP. Returns (source, [Regione]); (None, []) when the image says
    nothing about itself, which is the common case on AMD boards.
    """
    found = ifd_regions(data)
    if found:
        # On Intel the two maps coexist: the FMAP describes the inside of
        # the BIOS region. The extra areas are added, without duplicates.
        gia = set((r.start, r.end) for r in found)
        for region in fmap_regions(data):
            if (region.start, region.end) not in gia:
                found.append(region)
        found.sort(key=lambda r: (r.start, r.end))
        return "ifd", found
    found = fmap_regions(data)
    if found:
        return "fmap", found
    found = amd_regions(data)
    if found:
        return "amd", found
    return None, []


def as_layout(regions, total_size):
    """A flashrom layout file, with the regions' real names.

    ⚠️ Regions can nest (an FMAP inside an IFD's BIOS) and flashrom wants a
    flat list: all of them are written here, because it is the user who picks
    one with --image, and overlapping ones do no harm as long as only one is
    used.
    """
    lines = []
    used = {}
    for region in sorted(regions, key=lambda r: (r.start, r.end)):
        name = region.name
        if name in used:
            used[name] += 1
            name = "%s_%d" % (name, used[name])
        else:
            used[name] = 0
        lines.append("%08x:%08x %s" % (region.start, region.end, name))
    return "\n".join(lines) + ("\n" if lines else "")
