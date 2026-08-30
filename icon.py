# -*- coding: utf-8 -*-
"""Builds SPIranha.ico from the artwork, without any imaging library.

    python icon.py

Reads `docs/img/icon-768.png` and writes `SPIranha.ico`.

⚠️ Why 768 and not any other size: it divides exactly by 16, 32, 48, 64,
128 and 256, so every size in the icon is a plain box average of the same
file. No resampling library, no interpolation choices, and the result does
not depend on which machine ran the build.

⚠️ The artwork the .ico is built from carries NO text. The labels
(MISO/MOSI/SCLK/CS) belong to `icon-hero.png`, which is meant to be looked
at large. Four lines of text inside 16 pixels are four grey smudges, and
what survives down there is the shape and the four wire colours.

⚠️ Pillow is not needed: PNG is read and the ICO written by hand (BMP
entries for the small sizes, a PNG entry for the 256), with zlib from the
standard library.
"""
from __future__ import unicode_literals

import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ARTWORK = os.path.join(HERE, "docs", "img", "icon-768.png")

SIZES = (16, 32, 48, 64, 128)
BIG_SIZE = 256


class Surface(object):
    """A bare RGBA canvas: a list of rows of (r, g, b, a)."""

    def __init__(self, side, rows=None):
        self.side = side
        self.px = rows if rows is not None else \
            [[(0, 0, 0, 0)] * side for _ in range(side)]

    def scaled(self, factor):
        """The mean of every factor×factor square: that is the resampling."""
        side = self.side // factor
        small = Surface(side)
        for y in range(side):
            row = small.px[y]
            for x in range(side):
                r = g = b = a = 0
                for dy in range(factor):
                    source = self.px[y * factor + dy]
                    for dx in range(factor):
                        pr, pg, pb, pa = source[x * factor + dx]
                        # ⚠️ the colours are weighted by alpha: averaging a
                        # transparent pixel's colour in would darken the edge
                        # with whatever happens to sit behind it.
                        r += pr * pa
                        g += pg * pa
                        b += pb * pa
                        a += pa
                n = factor * factor
                row[x] = (r // a, g // a, b // a, a // n) if a else (0, 0, 0, 0)
        return small


# ------------------------------------------------------------------- reading

def read_png(source):
    """An 8-bit RGB/RGBA PNG, as a Surface. A path, or the bytes themselves."""
    if isinstance(source, bytes):
        data, path = source, "<bytes>"
    else:
        path = source
        with open(path, "rb") as f:
            data = f.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("%s is not a PNG" % path)
    position = 8
    width = height = depth = kind = None
    body = bytearray()
    while position < len(data):
        (length,) = struct.unpack_from(">I", data, position)
        name = data[position + 4:position + 8]
        chunk = data[position + 8:position + 8 + length]
        position += 12 + length
        if name == b"IHDR":
            width, height, depth, kind = struct.unpack(">IIBB", chunk[:10])
        elif name == b"IDAT":
            body += chunk
        elif name == b"IEND":
            break
    if depth != 8 or kind not in (2, 6):
        raise ValueError("only 8-bit RGB or RGBA is read here, not %s/%s"
                         % (depth, kind))
    if width != height:
        raise ValueError("the artwork must be square, this is %dx%d"
                         % (width, height))

    step = 4 if kind == 6 else 3
    raw = zlib.decompress(bytes(body))
    stride = width * step
    rows = []
    previous = bytearray(stride)
    position = 0
    for _y in range(height):
        which = raw[position]
        line = bytearray(raw[position + 1:position + 1 + stride])
        position += 1 + stride
        _unfilter(which, line, previous, step)
        row = []
        for x in range(0, stride, step):
            if step == 4:
                row.append((line[x], line[x + 1], line[x + 2], line[x + 3]))
            else:
                row.append((line[x], line[x + 1], line[x + 2], 255))
        rows.append(row)
        previous = line
    return Surface(width, rows)


def _unfilter(which, line, previous, step):
    """The five PNG filters, undone in place. See RFC 2083, §6."""
    if which == 0:
        return
    for i in range(len(line)):
        left = line[i - step] if i >= step else 0
        up = previous[i]
        corner = previous[i - step] if i >= step else 0
        if which == 1:
            line[i] = (line[i] + left) & 0xFF
        elif which == 2:
            line[i] = (line[i] + up) & 0xFF
        elif which == 3:
            line[i] = (line[i] + (left + up) // 2) & 0xFF
        elif which == 4:
            p = left + up - corner
            pa, pb, pc = abs(p - left), abs(p - up), abs(p - corner)
            best = left if (pa <= pb and pa <= pc) else (up if pb <= pc else corner)
            line[i] = (line[i] + best) & 0xFF
        else:
            raise ValueError("unknown PNG filter %d" % which)


# ------------------------------------------------------------------ formats

def bmp_entry(canvas):
    """One ICO entry as a 32-bit BMP, rows from the bottom up."""
    side = canvas.side
    heading = struct.pack("<IiiHHIIiiII", 40, side, side * 2, 1, 32, 0,
                               side * side * 4, 0, 0, 0, 0)
    body = bytearray()
    for y in range(side - 1, -1, -1):
        for r, g, b, a in canvas.px[y]:
            body += bytes((b, g, r, a))
    line = ((side + 31) // 32) * 4
    return heading + bytes(body) + bytes(line * side)


def png_entry(canvas):
    """One ICO entry as a PNG: allowed from Vista onwards, and for the 256 it
    is the only sensible way."""
    side = canvas.side
    raw = bytearray()
    for y in range(side):
        raw.append(0)               # filter "none"
        for r, g, b, a in canvas.px[y]:
            raw += bytes((r, g, b, a))

    def chunk(name, data):
        block = name + data
        return struct.pack(">I", len(data)) + block + \
            struct.pack(">I", zlib.crc32(block) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", side, side, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def png_from_ico(path, side):
    """The icon at `side` pixels, as PNG bytes, taken out of an .ico.

    ⚠️ For the interface, not for the build: Tk reads PNG and nothing else
    useful, and its own subsample() decimates rather than averages, which on
    a painted image looks exactly as bad as it sounds. So the 256 entry --
    the one entry that is already a PNG -- is read and box-averaged here.
    """
    with open(path, "rb") as f:
        data = f.read()
    count = struct.unpack_from("<HHH", data, 0)[2]
    for i in range(count):
        entry = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        size, offset = entry[6], entry[7]
        body = data[offset:offset + size]
        if body[:8] != b"\x89PNG\r\n\x1a\n":
            continue
        big = read_png(body)
        if big.side % side:
            raise ValueError("%d does not divide %d exactly" % (side, big.side))
        return png_entry(big.scaled(big.side // side))
    raise ValueError("%s carries no PNG entry" % path)


def write(path=None, artwork=ARTWORK):
    path = path or os.path.join(HERE, "SPIranha.ico")
    big = read_png(artwork)
    images = []
    for side in SIZES:
        if big.side % side:
            raise ValueError("%d does not divide %d exactly" % (side, big.side))
        images.append((side, bmp_entry(big.scaled(big.side // side))))
    images.append((BIG_SIZE, png_entry(big.scaled(big.side // BIG_SIZE))))

    header = struct.pack("<HHH", 0, 1, len(images))
    spare = len(header) + 16 * len(images)
    entries, bodies = b"", b""
    for side, data in images:
        entries += struct.pack("<BBBBHHII", side & 0xFF, side & 0xFF, 0, 0, 1, 32,
                            len(data), spare)
        bodies += data
        spare += len(data)
    with open(path, "wb") as f:
        f.write(header + entries + bodies)
    return path


if __name__ == "__main__":
    written = write()
    print("written %s (%d bytes)" % (written, os.path.getsize(written)))
