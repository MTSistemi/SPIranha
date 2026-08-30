# -*- coding: utf-8 -*-
"""Generates the program icon, without depending on any imaging library.

    python icon.py

Writes `SPIranha.ico`. The drawing follows the theme: slate background, an
accent-blue chip with amber pins along its sides. It is redrawn at every size
rather than scaling one image, so it stays legible at 16 px.

⚠️ Pillow is not needed: the ICO format is written by hand (BMP entries for
the small sizes, one PNG entry for the 256, compressed with zlib from the
standard library).
"""
from __future__ import unicode_literals

import struct
import zlib

INK = (0x0B, 0x11, 0x19)
BORDER = (0x24, 0x32, 0x3F)
ACCENT_COLOUR = (0x2F, 0x9B, 0xE0)
ACCENT_COLOUR2 = (0x00, 0x70, 0xB0)
PIN_COLOUR = (0xC9, 0xA2, 0x27)
DARK = (0x08, 0x13, 0x1C)

SIZES = (16, 32, 48, 64)
BIG_SIZE = 4          # sovracampionamento, per bordi non seghettati


class Surface(object):
    """Una tela RGBA elementare: riempimenti, rettangoli e angoli tondi."""

    def __init__(self, side):
        self.side = side
        self.px = [[(0, 0, 0, 0)] * side for _ in range(side)]

    def rect(self, x0, y0, x1, y1, colour, radius=0):
        r, g, b = colour
        for y in range(max(0, int(y0)), min(self.side, int(y1) + 1)):
            for x in range(max(0, int(x0)), min(self.side, int(x1) + 1)):
                if radius:
                    # nothing is drawn outside the corner arcs
                    for cx, cy in ((x0 + radius, y0 + radius), (x1 - radius, y0 + radius),
                                   (x0 + radius, y1 - radius), (x1 - radius, y1 - radius)):
                        dentro_x = (x < x0 + radius) if cx < (x0 + x1) / 2 \
                            else (x > x1 - radius)
                        dentro_y = (y < y0 + radius) if cy < (y0 + y1) / 2 \
                            else (y > y1 - radius)
                        if dentro_x and dentro_y:
                            if (x - cx) ** 2 + (y - cy) ** 2 > radius ** 2:
                                break
                    else:
                        self.px[y][x] = (r, g, b, 255)
                    continue
                self.px[y][x] = (r, g, b, 255)

    def scaled(self, factor):
        """Media di ogni quadrato fattore×fattore: e' l'antialiasing."""
        side = self.side // factor
        piccola = Surface(side)
        for y in range(side):
            for x in range(side):
                r = g = b = a = 0
                for dy in range(factor):
                    for dx in range(factor):
                        pr, pg, pb, pa = self.px[y * factor + dy][x * factor + dx]
                        r += pr * pa
                        g += pg * pa
                        b += pb * pa
                        a += pa
                n = factor * factor
                if a:
                    piccola.px[y][x] = (r // a, g // a, b // a, a // n)
                else:
                    piccola.px[y][x] = (0, 0, 0, 0)
        return piccola


def draw(side):
    """Il marchio, ridisegnato alla misura richiesta."""
    big = Surface(side * BIG_SIZE)
    L = side * BIG_SIZE
    u = L / 64.0                       # unita': il disegno e' pensato su 64

    big.rect(0, 0, L - 1, L - 1, INK, radius=int(10 * u))
    big.rect(int(1 * u), int(1 * u), L - 1 - int(1 * u), L - 1 - int(1 * u),
                      BORDER, radius=int(9 * u))
    big.rect(int(2 * u), int(2 * u), L - 1 - int(2 * u), L - 1 - int(2 * u),
                      INK, radius=int(8 * u))

    # i piedini, tre per lato
    for index in range(3):
        y = int((21 + index * 11) * u)
        alto = max(1, int(4 * u))
        big.rect(int(7 * u), y, int(20 * u), y + alto, PIN_COLOUR)
        big.rect(L - 1 - int(20 * u), y, L - 1 - int(7 * u), y + alto, PIN_COLOUR)

    # the chip body
    big.rect(int(18 * u), int(16 * u), L - 1 - int(18 * u),
                      L - 1 - int(16 * u), ACCENT_COLOUR2, radius=int(3 * u))
    big.rect(int(20 * u), int(18 * u), L - 1 - int(20 * u),
                      L - 1 - int(18 * u), ACCENT_COLOUR, radius=int(2 * u))
    # la tacca del piedino 1
    big.rect(int(24 * u), int(22 * u), int(30 * u), int(28 * u), DARK,
                      radius=int(3 * u))
    return big.scaled(BIG_SIZE)


# ------------------------------------------------------------------ formati

def bmp_entry(canvas):
    """One ICO entry as a 32-bit BMP, rows from the bottom up."""
    side = canvas.side
    intestazione = struct.pack("<IiiHHIIiiII", 40, side, side * 2, 1, 32, 0,
                               side * side * 4, 0, 0, 0, 0)
    body = bytearray()
    for y in range(side - 1, -1, -1):
        for x in range(side):
            r, g, b, a = canvas.px[y][x]
            body += bytes((b, g, r, a))
    maschera = bytearray()
    line = ((side + 31) // 32) * 4
    maschera += bytes(line * side)
    return intestazione + bytes(body) + bytes(maschera)


def png_entry(canvas):
    """One ICO entry as a PNG: allowed from Vista onwards, and for the 256 it
    is the only sensible way."""
    side = canvas.side
    grezzo = bytearray()
    for y in range(side):
        grezzo.append(0)               # filtro «nessuno»
        for x in range(side):
            r, g, b, a = canvas.px[y][x]
            grezzo += bytes((r, g, b, a))

    def chunk(name, data):
        blocco = name + data
        return struct.pack(">I", len(data)) + blocco + \
            struct.pack(">I", zlib.crc32(blocco) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", side, side, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(grezzo), 9))
            + chunk(b"IEND", b""))


def write(path="SPIranha.ico"):
    images = []
    for side in SIZES:
        images.append((side, bmp_entry(draw(side))))
    images.append((256, png_entry(draw(256))))

    header = struct.pack("<HHH", 0, 1, len(images))
    spare = len(header) + 16 * len(images)
    entries, corpi = b"", b""
    for side, data in images:
        entries += struct.pack("<BBBBHHII", side & 0xFF, side & 0xFF, 0, 0, 1, 32,
                            len(data), spare)
        corpi += data
        spare += len(data)
    with open(path, "wb") as f:
        f.write(header + entries + corpi)
    return path


if __name__ == "__main__":
    import os
    path = write(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "SPIranha.ico"))
    print("scritta %s (%d byte)" % (path, os.path.getsize(path)))
