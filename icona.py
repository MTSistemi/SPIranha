# -*- coding: utf-8 -*-
"""Genera l'icona del programma, senza dipendere da librerie grafiche.

    python icona.py

Scrive `programmatore.ico`. Il disegno segue il tema: fondo ardesia, un chip
blu accento con i piedini ambra ai lati. Si ridisegna a ogni misura invece di
scalare una sola immagine, cosi' a 16 px resta leggibile.

⚠️ Non serve Pillow: il formato ICO e' scritto a mano (voci BMP per le misure
piccole, una voce PNG per i 256, compressa con zlib che sta nella libreria
standard).
"""
from __future__ import unicode_literals

import struct
import zlib

INK = (0x0B, 0x11, 0x19)
BORDO = (0x24, 0x32, 0x3F)
ACCENTO = (0x2F, 0x9B, 0xE0)
ACCENTO2 = (0x00, 0x70, 0xB0)
PIEDINO = (0xC9, 0xA2, 0x27)
SCURO = (0x08, 0x13, 0x1C)

MISURE = (16, 32, 48, 64)
SUPER = 4          # sovracampionamento, per bordi non seghettati


class Tela(object):
    """Una tela RGBA elementare: riempimenti, rettangoli e angoli tondi."""

    def __init__(self, lato):
        self.lato = lato
        self.px = [[(0, 0, 0, 0)] * lato for _ in range(lato)]

    def rettangolo(self, x0, y0, x1, y1, colore, raggio=0):
        r, g, b = colore
        for y in range(max(0, int(y0)), min(self.lato, int(y1) + 1)):
            for x in range(max(0, int(x0)), min(self.lato, int(x1) + 1)):
                if raggio:
                    # fuori dagli archi degli angoli non si disegna
                    for cx, cy in ((x0 + raggio, y0 + raggio), (x1 - raggio, y0 + raggio),
                                   (x0 + raggio, y1 - raggio), (x1 - raggio, y1 - raggio)):
                        dentro_x = (x < x0 + raggio) if cx < (x0 + x1) / 2 \
                            else (x > x1 - raggio)
                        dentro_y = (y < y0 + raggio) if cy < (y0 + y1) / 2 \
                            else (y > y1 - raggio)
                        if dentro_x and dentro_y:
                            if (x - cx) ** 2 + (y - cy) ** 2 > raggio ** 2:
                                break
                    else:
                        self.px[y][x] = (r, g, b, 255)
                    continue
                self.px[y][x] = (r, g, b, 255)

    def riduci(self, fattore):
        """Media di ogni quadrato fattore×fattore: e' l'antialiasing."""
        lato = self.lato // fattore
        piccola = Tela(lato)
        for y in range(lato):
            for x in range(lato):
                r = g = b = a = 0
                for dy in range(fattore):
                    for dx in range(fattore):
                        pr, pg, pb, pa = self.px[y * fattore + dy][x * fattore + dx]
                        r += pr * pa
                        g += pg * pa
                        b += pb * pa
                        a += pa
                n = fattore * fattore
                if a:
                    piccola.px[y][x] = (r // a, g // a, b // a, a // n)
                else:
                    piccola.px[y][x] = (0, 0, 0, 0)
        return piccola


def disegna(lato):
    """Il marchio, ridisegnato alla misura richiesta."""
    grande = Tela(lato * SUPER)
    L = lato * SUPER
    u = L / 64.0                       # unita': il disegno e' pensato su 64

    grande.rettangolo(0, 0, L - 1, L - 1, INK, raggio=int(10 * u))
    grande.rettangolo(int(1 * u), int(1 * u), L - 1 - int(1 * u), L - 1 - int(1 * u),
                      BORDO, raggio=int(9 * u))
    grande.rettangolo(int(2 * u), int(2 * u), L - 1 - int(2 * u), L - 1 - int(2 * u),
                      INK, raggio=int(8 * u))

    # i piedini, tre per lato
    for indice in range(3):
        y = int((21 + indice * 11) * u)
        alto = max(1, int(4 * u))
        grande.rettangolo(int(7 * u), y, int(20 * u), y + alto, PIEDINO)
        grande.rettangolo(L - 1 - int(20 * u), y, L - 1 - int(7 * u), y + alto, PIEDINO)

    # il corpo del chip
    grande.rettangolo(int(18 * u), int(16 * u), L - 1 - int(18 * u),
                      L - 1 - int(16 * u), ACCENTO2, raggio=int(3 * u))
    grande.rettangolo(int(20 * u), int(18 * u), L - 1 - int(20 * u),
                      L - 1 - int(18 * u), ACCENTO, raggio=int(2 * u))
    # la tacca del piedino 1
    grande.rettangolo(int(24 * u), int(22 * u), int(30 * u), int(28 * u), SCURO,
                      raggio=int(3 * u))
    return grande.riduci(SUPER)


# ------------------------------------------------------------------ formati

def voce_bmp(tela):
    """Una voce ICO in formato BMP a 32 bit, righe dal basso."""
    lato = tela.lato
    intestazione = struct.pack("<IiiHHIIiiII", 40, lato, lato * 2, 1, 32, 0,
                               lato * lato * 4, 0, 0, 0, 0)
    corpo = bytearray()
    for y in range(lato - 1, -1, -1):
        for x in range(lato):
            r, g, b, a = tela.px[y][x]
            corpo += bytes((b, g, r, a))
    maschera = bytearray()
    riga = ((lato + 31) // 32) * 4
    maschera += bytes(riga * lato)
    return intestazione + bytes(corpo) + bytes(maschera)


def voce_png(tela):
    """Una voce ICO in formato PNG: da Vista in poi si puo', e per i 256 e'
    l'unico modo sensato."""
    lato = tela.lato
    grezzo = bytearray()
    for y in range(lato):
        grezzo.append(0)               # filtro «nessuno»
        for x in range(lato):
            r, g, b, a = tela.px[y][x]
            grezzo += bytes((r, g, b, a))

    def pezzo(nome, dati):
        blocco = nome + dati
        return struct.pack(">I", len(dati)) + blocco + \
            struct.pack(">I", zlib.crc32(blocco) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + pezzo(b"IHDR", struct.pack(">IIBBBBB", lato, lato, 8, 6, 0, 0, 0))
            + pezzo(b"IDAT", zlib.compress(bytes(grezzo), 9))
            + pezzo(b"IEND", b""))


def scrivi(percorso="programmatore.ico"):
    immagini = []
    for lato in MISURE:
        immagini.append((lato, voce_bmp(disegna(lato))))
    immagini.append((256, voce_png(disegna(256))))

    testa = struct.pack("<HHH", 0, 1, len(immagini))
    scarto = len(testa) + 16 * len(immagini)
    voci, corpi = b"", b""
    for lato, dati in immagini:
        voci += struct.pack("<BBBBHHII", lato & 0xFF, lato & 0xFF, 0, 0, 1, 32,
                            len(dati), scarto)
        corpi += dati
        scarto += len(dati)
    with open(percorso, "wb") as f:
        f.write(testa + voci + corpi)
    return percorso


if __name__ == "__main__":
    import os
    percorso = scrivi(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "programmatore.ico"))
    print("scritta %s (%d byte)" % (percorso, os.path.getsize(percorso)))
