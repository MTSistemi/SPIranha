# -*- coding: utf-8 -*-
"""Lo schema dei collegamenti, disegnato a codice e in scala.

Perche' disegnato e non un'immagine: resta nitido a qualunque dimensione, segue
il tema e sta dentro l'eseguibile senza file esterni.

LE FONTI, e sono d'accordo fra loro:
  mothenjoyer69/bc250-documentation  e  elektricM/amd-bc250-docs
pubblicano entrambe questa disposizione del J4004:

      [ GND SCLK MOSI UNK ]
      [ VCC  CS  MISO     ]
         ^  piedino 1, triangolo bianco in serigrafia

La seconda fonte la numera a colonne (1 VCC / 2 GND, 3 CS / 4 SCLK, 5 MISO /
6 MOSI, 7 n.d. / 8 UNK): rimessa in fila e' la stessa cosa, i dispari sono la
fila di sotto e i pari quella di sopra.
⚠️ UNK e' a massa tramite 10 kOhm: non si collega.

La piedinatura del Pico e' quella ufficiale RP2040: 1-20 scendendo a sinistra,
21-40 risalendo a destra, USB in alto.

I PERCORSI DEI CAVETTI sono calcolati per non incrociarsi mai: chi va alla fila
di sopra passa sopra la scheda, chi va a quella di sotto passa sotto.
"""
from __future__ import unicode_literals

import tkinter as tk
from tkinter import ttk

import theme as T

# ------------------------------------------------------- dati, non disegno

PICO_LEFT = [
    (1, "GP0"), (2, "GP1"), (3, "GND"), (4, "GP2"), (5, "GP3"),
    (6, "GP4"), (7, "GP5"), (8, "GND"), (9, "GP6"), (10, "GP7"),
    (11, "GP8"), (12, "GP9"), (13, "GND"), (14, "GP10"), (15, "GP11"),
    (16, "GP12"), (17, "GP13"), (18, "GND"), (19, "GP14"), (20, "GP15"),
]
PICO_RIGHT = [   # dal basso verso l'alto, come sono numerati davvero
    (21, "GP16"), (22, "GP17"), (23, "GND"), (24, "GP18"), (25, "GP19"),
    (26, "GP20"), (27, "GP21"), (28, "GND"), (29, "GP22"), (30, "RUN"),
    (31, "GP26"), (32, "GP27"), (33, "AGND"), (34, "GP28"), (35, "ADC_VREF"),
    (36, "3V3 OUT"), (37, "3V3_EN"), (38, "GND"), (39, "VSYS"), (40, "VBUS"),
]

J4004 = [   # (colonna, fila, numero, nome)
    (0, "bassa", 1, "VCC"), (0, "alta", 2, "GND"),
    (1, "bassa", 3, "CS"), (1, "alta", 4, "SCLK"),
    (2, "bassa", 5, "MISO"), (2, "alta", 6, "MOSI"),
    (3, "bassa", 7, None), (3, "alta", 8, "UNK"),
]

CONNECTIONS = [   # (segnale, piedino Pico, nome Pico, piedino J4004)
    ("VCC", 36, "3V3 OUT", 1),
    ("GND", 3, "GND", 2),
    ("CS", 7, "GP5", 3),
    ("SCLK", 4, "GP2", 4),
    ("MISO", 6, "GP4", 5),
    ("MOSI", 5, "GP3", 6),
]

WARNINGS = ("sch_av1", "sch_av2", "sch_av3", "sch_av4")

# ---------------------------------------------------- il chip nudo (SOIC-8)
# Piedinatura standard delle flash SPI in SOIC-8, vista da sopra: 1-4 scendendo
# a sinistra, 5-8 risalendo a destra, tacca in alto.
#
# ⚠️ Qui NON si disegnano i cavetti, e non e' pigrizia: su un SOIC-8 i quattro
# segnali stanno su DUE lati opposti (CS e MISO da una parte, MOSI e SCLK
# dall'altra), quindi nella realta' i cavi si incrociano e basta. Un disegno
# che li mostrasse ordinati sarebbe piu' bello del vero e meno utile: qui
# contano i NUMERI dei piedini e il colore del segnale.
SOIC8 = [   # (lato, numero, nome, segnale o None)
    ("sx", 1, "/CS", "CS"),
    ("sx", 2, "DO", "MISO"),
    ("sx", 3, "/WP", None),
    ("sx", 4, "GND", "GND"),
    ("dx", 5, "DI", "MOSI"),
    ("dx", 6, "CLK", "SCLK"),
    ("dx", 7, "/HOLD", None),
    ("dx", 8, "VCC", "VCC"),
]

CLIP_CONNECTIONS = [   # (segnale, piedino Pico, nome Pico, piedino del chip)
    ("VCC", 36, "3V3 OUT", 8),
    ("GND", 3, "GND", 4),
    ("CS", 7, "GP5", 1),
    ("SCLK", 4, "GP2", 6),
    ("MISO", 6, "GP4", 2),
    ("MOSI", 5, "GP3", 5),
]

CLIP_WARNINGS = ("sch_pz_av1", "sch_pz_av2", "sch_pz_av3", "sch_pz_av4")

# geometria del chip: corpo stretto, piazzole che sporgono
CHIP_X0, CHIP_X1 = 206, 286          # corpo
CHIP_Y0 = 268
CHIP_PITCH = 40
PAD_CHIP = 26                     # quanto sporge la piazzola
CHIP_HALF_H = 13                     # mezza altezza della piazzola

# --------------------------------------------------------------- geometria
# Tutto in coordinate «naturali»: al disegno vengono moltiplicate per k.
WIDTH, HEIGHT = 1030, 566

# IL CONNETTORE STA A SINISTRA, e non e' un capriccio: i quattro segnali
# (SCLK, MOSI, MISO, CS) escono dai piedini 4-7, che sul Pico sono sul fianco
# SINISTRO. Mettendo il J4004 da quella parte i quattro cavi vanno dritti, e
# solo alimentazione e massa — che escono a destra — devono fare il giro.
# Col connettore a destra giravano in quattro, e il disegno diventava un
# groviglio di cornici.
PICO_X, PICO_Y = 430, 140           # scheda Pico
PICO_W, PICO_H = 190, 358
PIN_PITCH, FIRST_PIN_Y = 16, 170
PAD_LEN, PAD_H = 11, 8

# ⚠️ Il connettore e' disegnato con le piazzole piu' distanziate del vero: il
# passo reale e' 2,54 mm ed e' scritto nella nota. Distanziarle serve a far
# stare numero e nome DENTRO la piazzola, unico posto dove non finiscono sotto
# ai cavetti. Posizioni, verso e piedino 1 restano quelli veri.
HEADER_COLS = [170, 216, 262, 308]     # colonne del J4004
HEADER_ROWS = {"alta": 292, "bassa": 356}
PAD_HEADER = 15

# GND si prende dal piedino 3, non dal 38: sta sul fianco sinistro accanto ai
# quattro segnali (3-4-5-6-7 contigui, un solo pettine da cinque) e cosi' UN
# SOLO cavo — il 3V3 — deve fare il giro della scheda.
VCC_LANE_Y = 520                 # corsia sotto, per il solo VCC
VCC_X = 686                   # verticale a destra della scheda
GND_LANE_X = 140                   # verticale a sinistra, appena fuori dal guscio
LANES = (420, 440)             # rientri sotto a sinistra: MISO, CS
RETURN_X = (350, 368)          # verticali corrispondenti

TITLE_Y, NOTE_Y = 62, 76
COL_X, COL_WIDTH = 730, 280


def pico_pin_y(number):
    if number <= 20:
        return FIRST_PIN_Y + (number - 1) * PIN_PITCH
    return FIRST_PIN_Y + (40 - number) * PIN_PITCH


class Diagram(tk.Toplevel):
    """La finestra dello schema: si ridisegna in scala quando cambia misura."""

    def __init__(self, parent, tm, L, clip=False):
        tk.Toplevel.__init__(self, parent, background=T.INK)
        self.theme = tm
        self.L = L
        # due schemi: il connettore di una scheda conosciuta, oppure la pinza
        # sul chip nudo, che e' il caso di tutte le altre
        self.clip = clip
        self.k = 1.0
        self._attesa = None
        self.title(L("sch_titolo_pinza" if clip else "sch_titolo"))
        self.geometry("1060x630")
        self.minsize(660, 420)

        self.canvas = tk.Canvas(self, background=T.INK, highlightthickness=0, bd=0)
        # ⚠️ Sotto una certa misura il disegno non puo' rimpicciolirsi ancora:
        # i caratteri hanno un minimo leggibile e il testo cresce rispetto al
        # resto. Senza barra, le ultime note sparivano e basta.
        self.bar = ttk.Scrollbar(self, orient="vertical",
                                   command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._maybe_scrollbar)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", self._maybe_redraw)
        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Escape>", lambda _e: self.destroy())
        T.dark_title_bar(self)

    # --------------------------------------------------------- scorrimento
    def _maybe_scrollbar(self, first, last):
        """La barra compare solo se serve davvero."""
        if float(first) <= 0.0 and float(last) >= 1.0:
            self.bar.pack_forget()
        else:
            self.bar.pack(side="right", fill="y")
        self.bar.set(first, last)

    def _on_wheel(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    # ------------------------------------------------------------- scala
    def _maybe_redraw(self, _evento=None):
        if self._attesa:
            self.after_cancel(self._attesa)
        self._attesa = self.after(70, self.draw)

    def _s(self, *values):
        """Coordinate in scala. Restituisce un numero o una lista, come arriva."""
        if len(values) == 1:
            return values[0] * self.k
        return [v * self.k for v in values]

    def _font(self, points, grassetto=False, mono=False):
        """Un carattere in scala, mai sotto il leggibile."""
        family = self.theme.mono if mono else self.theme.ui
        size_text = max(6, int(round(points * self.k)))
        return (family, size_text, "bold") if grassetto else (family, size_text)

    # ------------------------------------------------------------ pennelli
    def _text(self, x, y, text, colour=T.FG, font=None, anchor="w",
               width=None, tag=None):
        return self.canvas.create_text(
            self._s(x), self._s(y), text=text, fill=colour, anchor=anchor,
            font=font or self._font(8),
            width=self._s(width) if width else None,
            tags=tag or ())

    def _rect(self, x0, y0, x1, y1, background=T.PANEL, border=T.LINE, thickness=1,
              dash=None, tag=None):
        a, b, c, d = self._s(x0, y0, x1, y1)
        return self.canvas.create_rectangle(a, b, c, d, fill=background, outline=border,
                                          width=thickness, dash=dash,
                                          tags=tag or ())

    def _frame_around(self, tag, x0, y0, x1, title, margine=13):
        """Disegna il riquadro ATTORNO a quello che c'e' gia', misurandolo.

        ⚠️ Prima si scriveva il contenuto dentro un riquadro di altezza decisa
        a mano, e con le frasi lunghe il testo usciva dal bordo. Qui si misura
        cio' che e' stato disegnato (bbox) e il riquadro gli si adatta; poi lo
        si manda sotto, cosi' il contenuto resta sopra.
        """
        bounds = self.canvas.bbox(tag)
        background = (bounds[3] / self.k) + margine if bounds else y0 + 46
        background_colour = self._rect(x0, y0, x1, background)
        self.canvas.tag_lower(background_colour)
        self._text(x0 + 11, y0 + 12, T.micro(title), T.MUT, self._font(7, True))
        a, b = self._s(x0 + 11, y0 + 23)
        self.canvas.create_line(a, b, self._s(x1 - 11), b, fill=T.LINE)
        return background

    def _wire(self, points, colour):
        """Cavetto: contorno scuro sotto per staccarlo dal fondo, colore sopra.

        ⚠️ Angoli VIVI, non spline: la curva approssimata sembra tracciata a
        mano e non passa nemmeno per i punti dati. Qui i percorsi sono
        ortogonali e devono restare tali, con il solo raccordo tondo del giunto.
        """
        piatti = []
        for x, y in points:
            piatti += [self._s(x), self._s(y)]
        for width, tinta in ((max(3.2, 5.2 * self.k), "#060B10"),
                                 (max(1.8, 2.9 * self.k), colour)):
            self.canvas.create_line(*piatti, fill=tinta, width=width,
                                  capstyle="round", joinstyle="round")

    # ------------------------------------------------------------ disegno
    def draw(self):
        self._attesa = None
        width = max(self.canvas.winfo_width(), 300)
        height = max(self.canvas.winfo_height(), 240)
        self.k = max(0.52, min(width / float(WIDTH), height / float(HEIGHT), 1.7))
        self.canvas.delete("all")
        self._draw_title_bar(width)
        self._draw_pico()
        if self.clip:
            self._draw_bare_chip()
        else:
            self._draw_header_pins()
            self._draw_wires()
        self._draw_side_column()
        self._measure_drawing()

    def _measure_drawing(self):
        """La regione di scorrimento e' quella che il disegno occupa davvero."""
        bounds = self.canvas.bbox("all")
        if bounds:
            self.canvas.configure(scrollregion=(0, 0, bounds[2],
                                              bounds[3] + self._s(12)))

    def _draw_title_bar(self, real_width):
        top = self._s(52)
        # il gradiente si mette da solo sul fondo: se ci disegnassimo sotto un
        # rettangolo pieno lo coprirebbe
        T.gradient(self.canvas, real_width, top)
        self.canvas.create_line(0, top, real_width, top, fill=T.LINE)
        self._text(20, 18, self.L("sch_titolo_pinza" if self.clip
                                   else "sch_titolo"), T.FG, self._font(12, True))
        self._text(21, 37, self.L("sch_sotto_pinza" if self.clip
                                   else "sch_sotto"), T.MUT, self._font(8))

    # -- il Pico ----------------------------------------------------------
    def _draw_pico(self):
        t = self.canvas
        x1, y1 = PICO_X + PICO_W, PICO_Y + PICO_H

        self._text(PICO_X, TITLE_Y, T.micro(self.L("sch_pico")), T.MUT,
                    self._font(7, True))
        # ⚠️ ancora "nw": col centraggio verticale la prima riga di una nota
        # che va a capo sale SOPRA il punto dato, cioe' addosso al titolo.
        self._text(PICO_X, NOTE_Y - 4, self.L("sch_pico_nota"), "#5E7488",
                    self._font(7), anchor="nw", width=230)

        # circuito stampato
        self._rect(PICO_X, PICO_Y, x1, y1, "#0E3428", "#1C5943")
        # connettore USB, in cima
        self._rect(PICO_X + 63, PICO_Y - 9, x1 - 63, PICO_Y + 13, "#8C93A0", "#B9C1CC")
        self._rect(PICO_X + 71, PICO_Y - 4, x1 - 71, PICO_Y + 8, "#4E5561", "#4E5561")
        self._text((PICO_X + x1) / 2.0, PICO_Y - 19, "USB", T.MUT, self._font(7, True),
                    anchor="center")
        self._draw_pico_parts(x1, y1)

        used = {c[1]: c[0] for c in CONNECTIONS}

        for listing, side in ((PICO_LEFT, "sx"), (PICO_RIGHT, "dx")):
            for number, name in listing:
                y = pico_pin_y(number)
                signal = used.get(number)
                colour = T.WIRE[signal] if signal else None

                if side == "sx":
                    pad0, pad1 = PICO_X - PAD_LEN, PICO_X
                    x_num, x_nome, anchor = PICO_X + 6, PICO_X + 21, "w"
                else:
                    pad0, pad1 = x1, x1 + PAD_LEN
                    x_num, x_nome, anchor = x1 - 6, x1 - 21, "e"

                if colour:      # alone, perche' salti all'occhio
                    self._rect(pad0 - 2.5, y - PAD_H / 2.0 - 2.5,
                               pad1 + 2.5, y + PAD_H / 2.0 + 2.5, "", colour)
                self._rect(pad0, y - PAD_H / 2.0, pad1, y + PAD_H / 2.0,
                           colour or "#C9A227", colour or "#8A6F1B")
                self._text(x_num, y, str(number),
                            "#8FA6B8" if not colour else "#E4EDF4",
                            self._font(6.5, bool(colour), mono=True), anchor=anchor)
                # per GND il nome del piedino e' gia' il segnale: non si ripete
                label_for = name
                if colour and signal != name:
                    label_for = "%s · %s" % (name, signal)
                self._text(x_nome, y, label_for,
                            colour or "#7E9C8C", self._font(7, bool(colour)),
                            anchor=anchor)

    def _draw_pico_parts(self, x1, y1):
        """I pezzi che si vedono sulla scheda vera, per capire il verso.

        ⚠️ Il connettore USB da solo non bastava: chi guarda il disegno non
        sa se sta vedendo la scheda da sopra o da sotto, e i piedini sono
        specchiati. Il chip quadrato in mezzo, il pulsante BOOTSEL sotto
        l'USB e i contatti di servizio in fondo danno il verso che si ha
        davanti tenendo la scheda in mano.

        ⚠️ Tutto sta nella STRISCIA CENTRALE libera. I nomi dei piedini sono
        scritti dentro la scheda e, dove c'e' anche il segnale ("GP2 · SCLK",
        "3V3 OUT · VCC"), arrivano quasi a meta': i pezzi vanno messi dove
        quei nomi sono corti, o ci finiscono sopra. E' gia' successo.
        """
        cx = (PICO_X + x1) / 2.0

        # il pulsante BOOTSEL, subito sotto l'USB: righe 1-3 e 38-40, nomi corti
        bx, by = cx, PICO_Y + 26
        self._rect(bx - 13, by - 8, bx + 13, by + 8, "#20262E", "#3A4652")
        self._rect(bx - 8, by - 4, bx + 8, by + 4, "#313943", "#4B5967")
        self._text(cx, by + 17, "BOOTSEL", "#7E9C8C", self._font(6, True),
                    anchor="center")

        # il chip: quadrato, in mezzo, dove i nomi accanto sono corti
        side = 62
        qx0, qy0 = cx - side / 2.0, PICO_Y + 150
        self._rect(qx0, qy0, qx0 + side, qy0 + side, "#12171D", "#39434E")
        # il puntino del piedino 1, in alto a sinistra come sul chip vero
        px, py = self._s(qx0 + 9, qy0 + 9)
        r = self._s(3)
        self.canvas.create_oval(px - r, py - r, px + r, py + r, fill="#8FA2B2",
                              outline="")
        self._text(cx, qy0 + side / 2.0, "RP2040", "#B9C7D3",
                    self._font(7, True), anchor="center")

        # i contatti di servizio (SWD) sul bordo di sotto
        for index in range(3):
            sx = cx - 26 + index * 26
            self._rect(sx - 7, y1 - 16, sx + 7, y1 - 6, "#C9A227", "#8A6F1B")
        self._text(cx, y1 - 26, "SWD", "#5E8A72", self._font(6),
                    anchor="center")

    # -- il connettore -----------------------------------------------------
    def _draw_header_pins(self):
        x0, x1 = HEADER_COLS[0] - PAD_HEADER - 9, HEADER_COLS[3] + PAD_HEADER + 9
        y0, y1 = HEADER_ROWS["alta"] - PAD_HEADER - 9, HEADER_ROWS["bassa"] + PAD_HEADER + 9

        self._text(x0, TITLE_Y, T.micro(self.L("sch_conn")), T.MUT,
                    self._font(7, True))
        self._text(x0, NOTE_Y - 4, self.L("sch_conn_nota"), "#5E7488",
                    self._font(7), anchor="nw", width=210)

        self._rect(x0, y0, x1, y1, "#171E26", "#2E3A46")
        self._rect(x0 + 3, y0 + 3, x1 - 3, y1 - 3, "", "#0D131A")

        # triangolo del piedino 1, come sulla serigrafia: accanto a VCC
        tx, ty = self._s(x0 - 8), self._s(HEADER_ROWS["bassa"])
        d = self._s(6)
        self.canvas.create_polygon(tx - d * 0.7, ty - d, tx - d * 0.7, ty + d,
                                 tx + d * 0.7, ty, fill="#E4EDF4", outline="")
        self._text(x0 - 20, HEADER_ROWS["bassa"], "1", "#E4EDF4",
                    self._font(7, True, mono=True), anchor="e")

        per_numero = {c[3]: c[0] for c in CONNECTIONS}
        for column, fila, number, name in J4004:
            x, y = HEADER_COLS[column], HEADER_ROWS[fila]
            signal = per_numero.get(number)
            colour = T.WIRE[signal] if signal else None
            if name is None:
                self._rect(x - PAD_HEADER, y - PAD_HEADER, x + PAD_HEADER, y + PAD_HEADER, "", "#39434E",
                           dash=(2, 3))
                self._text(x, y - 5, str(number), "#4B5967",
                            self._font(6, mono=True), anchor="center")
                self._text(x, y + 6, self.L("sch_nc"), "#4B5967", self._font(6),
                            anchor="center")
                continue
            self._rect(x - PAD_HEADER, y - PAD_HEADER, x + PAD_HEADER, y + PAD_HEADER,
                       colour or "#20262E", colour or "#3A4652")
            # numero e nome DENTRO la piazzola: fuori finirebbero sotto ai cavi
            scuro = bool(colour)
            self._text(x, y - 5, str(number),
                        "#0A1017" if scuro else "#54657A",
                        self._font(6, mono=True), anchor="center")
            self._text(x, y + 6, name, "#0A1017" if scuro else "#7C8B99",
                        self._font(6.5, True), anchor="center")

        # ⚠️ Spostata a destra del risalitore del VCC (x = CX[0]): li' sotto ci
        # passa il cavo rosso e la scritta diventava illeggibile.
        # ⚠️ Larghezza fermata a 200: piu' larga arrivava a sbattere contro la
        # scheda Pico (che comincia a x=430) e le ultime parole finivano sotto
        # ai piedini.
        self._text(HEADER_COLS[0] + 34, 456, self.L("sch_unk"), "#93A5B4",
                    self._font(7), anchor="nw", width=200)

    # -- il chip nudo, preso con la pinza ----------------------------------
    def _draw_bare_chip(self):
        """Il SOIC-8 visto da sopra, con i piedini colorati per segnale.

        ⚠️ Niente cavetti disegnati: vedi la nota accanto a SOIC8. Qui il
        collegamento si legge dai NUMERI e dai colori, che e' anche il modo in
        cui lo si fa davvero -- guardando la tacca e contando i piedini.
        """
        y_fine = CHIP_Y0 + 3 * CHIP_PITCH
        self._text(CHIP_X0 - PAD_CHIP, TITLE_Y, T.micro(self.L("sch_chip")), T.MUT,
                    self._font(7, True))
        self._text(CHIP_X0 - PAD_CHIP, NOTE_Y - 4, self.L("sch_chip_nota"),
                    "#5E7488", self._font(7), anchor="nw", width=230)

        # corpo del contenitore
        self._rect(CHIP_X0, CHIP_Y0 - 30, CHIP_X1, y_fine + 30, "#12171D", "#39434E")
        # la tacca: e' cosi' che si riconosce da che parte sta il piedino 1
        cx, cy = self._s((CHIP_X0 + CHIP_X1) / 2.0, CHIP_Y0 - 30)
        r = self._s(13)
        self.canvas.create_arc(cx - r, cy - r, cx + r, cy + r, start=180,
                             extent=180, style="chord", fill=T.INK,
                             outline="#39434E")
        # e il punto accanto al piedino 1, che sui chip veri c'e' quasi sempre.
        # ⚠️ Sta SOPRA la prima riga, non accanto: al fianco del piedino finiva
        # addosso al nome del segnale.
        px, py = self._s(CHIP_X0 + 13, CHIP_Y0 - 15)
        d = self._s(3.5)
        self.canvas.create_oval(px - d, py - d, px + d, py + d, fill="#8FA2B2",
                              outline="")

        for side, number, name, signal in SOIC8:
            fila = (number - 1) if side == "sx" else (8 - number)
            y = CHIP_Y0 + fila * CHIP_PITCH
            colour = T.WIRE.get(signal) if signal else None
            if side == "sx":
                x0, x1 = CHIP_X0 - PAD_CHIP, CHIP_X0
                x_num, ancora_num = CHIP_X0 - PAD_CHIP - 8, "e"
            else:
                x0, x1 = CHIP_X1, CHIP_X1 + PAD_CHIP
                x_num, ancora_num = CHIP_X1 + PAD_CHIP + 8, "w"
            self._rect(x0, y - CHIP_HALF_H, x1, y + CHIP_HALF_H,
                       colour or "#2A323B", colour or "#3A4652")
            self._text(x_num, y, str(number), "#8FA2B2",
                        self._font(7, True, mono=True), anchor=ancora_num)
            # il nome sta DENTRO il corpo, dalla parte del suo piedino
            self._text(CHIP_X0 + 10 if side == "sx" else CHIP_X1 - 10, y, name,
                        colour or "#6E8296", self._font(7, True),
                        anchor="w" if side == "sx" else "e")

        # ⚠️ /WP e /HOLD bassi = il chip accetta i comandi e non scrive niente.
        # E' lo stesso modo silenzioso di fallire della protezione in scrittura.
        self._text(CHIP_X0 - PAD_CHIP, y_fine + 58, self.L("sch_wp_nota"), "#93A5B4",
                    self._font(7), anchor="nw", width=210)

    # -- i cavetti ---------------------------------------------------------
    def _draw_wires(self):
        sx = PICO_X - PAD_LEN
        dx = PICO_X + PICO_W + PAD_LEN
        miso_lane, cs_lane = LANES
        miso_x, cs_x = RETURN_X

        # i cavi si fermano sul BORDO della piazzola, non al centro: dentro ci
        # stanno numero e nome
        top = HEADER_ROWS["alta"] - PAD_HEADER
        bottom = HEADER_ROWS["bassa"] + PAD_HEADER

        # i quattro segnali: dal fianco sinistro del Pico al connettore, dritti
        self._wire([(sx, pico_pin_y(4)), (HEADER_COLS[1], pico_pin_y(4)),
                    (HEADER_COLS[1], top)], T.WIRE["SCLK"])
        self._wire([(sx, pico_pin_y(5)), (HEADER_COLS[2], pico_pin_y(5)),
                    (HEADER_COLS[2], top)], T.WIRE["MOSI"])
        self._wire([(sx, pico_pin_y(6)), (miso_x, pico_pin_y(6)), (miso_x, miso_lane),
                    (HEADER_COLS[2], miso_lane), (HEADER_COLS[2], bottom)], T.WIRE["MISO"])
        self._wire([(sx, pico_pin_y(7)), (cs_x, pico_pin_y(7)), (cs_x, cs_lane),
                    (HEADER_COLS[1], cs_lane), (HEADER_COLS[1], bottom)], T.WIRE["CS"])

        # GND esce anche lui a sinistra e rientra di fianco: la sua piazzola
        # sta nella fila di sopra, sulla stessa colonna di VCC
        self._wire([(sx, pico_pin_y(3)), (GND_LANE_X, pico_pin_y(3)), (GND_LANE_X, HEADER_ROWS["alta"]),
                    (HEADER_COLS[0] - PAD_HEADER, HEADER_ROWS["alta"])], T.WIRE["GND"])
        # il 3V3 e' l'unico che esce a destra: gira sotto, fuori dal bordo
        self._wire([(dx, pico_pin_y(36)), (VCC_X, pico_pin_y(36)), (VCC_X, VCC_LANE_Y),
                    (HEADER_COLS[0], VCC_LANE_Y), (HEADER_COLS[0], bottom)], T.WIRE["VCC"])

    # -- colonna di destra: tabella e avvisi -------------------------------
    def _draw_side_column(self):
        x = COL_X
        y = TITLE_Y - 12

        line = y + 38
        for label_for, dx in ((self.L("sch_col_segnale"), 30),
                              (self.L("sch_col_pico"), 130),
                              (self.L("sch_col_chip" if self.clip
                                      else "sch_col_conn"), 215)):
            self._text(x + dx, line, T.micro(label_for), "#55697C",
                        self._font(6, True), tag="tabella")
        line += 15

        for signal, pin_pico, nome_pico, pin_conn in (
                CLIP_CONNECTIONS if self.clip else CONNECTIONS):
            colour = T.WIRE[signal]
            a, b, c = self._s(x + 12, line, x + 23)
            self.canvas.create_line(a, b, c, b, fill=colour, tags="tabella",
                                  width=max(2.0, 3.0 * self.k), capstyle="round")
            self._text(x + 30, line, signal, colour, self._font(8, True),
                        tag="tabella")
            self._text(x + 130, line, "%2d  %s" % (pin_pico, nome_pico), T.FG,
                        self._font(7, mono=True), tag="tabella")
            self._text(x + 215, line, "%d  %s" % (pin_conn, signal), T.FG,
                        self._font(7, mono=True), tag="tabella")
            line += 21

        a, b = self._s(x + 12, line - 8)
        self.canvas.create_line(a, b, self._s(x + COL_WIDTH - 12), b, fill=T.LINE,
                              tags="tabella")
        # ⚠️ ancora "nw", non "w": con l'ancoraggio al centro un testo che va a
        # capo si estende anche SOPRA il punto dato, e finiva addosso al filetto.
        self._text(x + 12, line - 1,
                    self.L("sch_pz_nota" if self.clip else "sch_gnd_nota"),
                    "#6E8296",
                    self._font(7), anchor="nw", width=COL_WIDTH - 24,
                    tag="tabella")

        # il riquadro si adatta a quello che c'e' dentro, non viceversa
        background = self._frame_around("tabella", x, y, x + COL_WIDTH,
                               self.L("sch_tabella"))

        # --- avvisi
        y2 = background + 14
        line = y2 + 38
        for index, key in enumerate(CLIP_WARNINGS if self.clip
                                        else WARNINGS):
            colour = T.CRIT if index < 2 else T.WARN
            a, b = self._s(x + 15, line + 4)
            r = self._s(3)
            self.canvas.create_oval(a - r, b - r, a + r, b + r, fill=colour,
                                  outline="", tags="avvisi")
            board_id = self._text(x + 26, line, self.L(key), "#B9C7D3",
                                         self._font(7), anchor="nw",
                                         width=COL_WIDTH - 42, tag="avvisi")
            # ogni avviso scende di quanto occupa DAVVERO: in inglese e in
            # italiano le righe non sono le stesse
            bounds = self.canvas.bbox(board_id)
            line += ((bounds[3] - bounds[1]) / self.k if bounds else 34) + 15

        self._frame_around("avvisi", x, y2, x + COL_WIDTH, self.L("sch_av_titolo"))

        # Le fonti della piedinatura non stanno piu' nel disegno: restano nella
        # documentazione e in testa a questo file, dove servono a chi verifica.


def open_window(parent, tm, L, clip=False):
    """Apre lo schema, o riporta davanti quello gia' aperto.

    ⚠️ Se quello aperto e' dell'altro tipo va rifatto, non riportato davanti:
    sarebbe lo schema di un'altra scheda.
    """
    existing = getattr(parent, "_wiring_window", None)
    if existing is not None and existing.winfo_exists():
        if getattr(existing, "pinza", False) == clip:
            existing.deiconify()
            existing.lift()
            existing.focus_set()
            return existing
        existing.destroy()
    window = Diagram(parent, tm, L, clip=clip)
    parent._finestra_schema = window
    return window
