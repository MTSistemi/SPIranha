# -*- coding: utf-8 -*-
"""The wiring diagram, drawn in code and to scale.

Why drawn and not an image: it stays sharp at any size, follows the theme
and lives inside the executable with no external files.

THE SOURCES, and they agree with each other:
  mothenjoyer69/bc250-documentation  and  elektricM/amd-bc250-docs
both publish this J4004 arrangement:

      [ GND SCLK MOSI UNK ]
      [ VCC  CS  MISO     ]
         ^  pin 1, white triangle in the silkscreen

The second source numbers it by columns (1 VCC / 2 GND, 3 CS / 4 SCLK,
5 MISO / 6 MOSI, 7 n/c / 8 UNK): laid back out in a row it is the same
thing, the odd numbers are the bottom row and the even ones the top.
⚠️ UNK is tied to ground through 10 kOhm: do not connect it.

The Pico pinout is the official RP2040 one: 1-20 going down the left,
21-40 coming back up the right, USB at the top.

THE WIRE ROUTES are worked out never to cross: whatever goes to the top row
passes above the board, whatever goes to the bottom row passes below.
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
PICO_RIGHT = [   # bottom to top, the way they are really numbered
    (21, "GP16"), (22, "GP17"), (23, "GND"), (24, "GP18"), (25, "GP19"),
    (26, "GP20"), (27, "GP21"), (28, "GND"), (29, "GP22"), (30, "RUN"),
    (31, "GP26"), (32, "GP27"), (33, "AGND"), (34, "GP28"), (35, "ADC_VREF"),
    (36, "3V3 OUT"), (37, "3V3_EN"), (38, "GND"), (39, "VSYS"), (40, "VBUS"),
]

J4004 = [   # (column, row, number, name)
    (0, "bassa", 1, "VCC"), (0, "alta", 2, "GND"),
    (1, "bassa", 3, "CS"), (1, "alta", 4, "SCLK"),
    (2, "bassa", 5, "MISO"), (2, "alta", 6, "MOSI"),
    (3, "bassa", 7, None), (3, "alta", 8, "UNK"),
]

CONNECTIONS = [   # (signal, Pico pin, Pico name, J4004 pin)
    ("VCC", 36, "3V3 OUT", 1),
    ("GND", 3, "GND", 2),
    ("CS", 7, "GP5", 3),
    ("SCLK", 4, "GP2", 4),
    ("MISO", 6, "GP4", 5),
    ("MOSI", 5, "GP3", 6),
]

WARNINGS = ("sch_warn1", "sch_warn2", "sch_warn3", "sch_warn4")

# ------------------------------------------------- the bare chip (SOIC-8)
# Standard SOIC-8 SPI flash pinout, seen from above: 1-4 going down
# down the left, 5-8 back up the right, notch at the top.
#
# ⚠️ The wires are NOT drawn here, and it is not laziness: on a SOIC-8 the
# signals sit on TWO opposite sides (CS and MISO on one, MOSI and SCLK on the
# other), so in reality the wires cross and that is that. A drawing that
# showed them tidy would be prettier than the truth and less useful: what
# counts here are the pin NUMBERS and the signal colour.
SOIC8 = [   # (side, number, name, signal or None)
    ("sx", 1, "/CS", "CS"),
    ("sx", 2, "DO", "MISO"),
    ("sx", 3, "/WP", None),
    ("sx", 4, "GND", "GND"),
    ("dx", 5, "DI", "MOSI"),
    ("dx", 6, "CLK", "SCLK"),
    ("dx", 7, "/HOLD", None),
    ("dx", 8, "VCC", "VCC"),
]

CLIP_CONNECTIONS = [   # (signal, Pico pin, Pico name, chip pin)
    ("VCC", 36, "3V3 OUT", 8),
    ("GND", 3, "GND", 4),
    ("CS", 7, "GP5", 1),
    ("SCLK", 4, "GP2", 6),
    ("MISO", 6, "GP4", 2),
    ("MOSI", 5, "GP3", 5),
]

CLIP_WARNINGS = ("sch_clip_warn1", "sch_clip_warn2", "sch_clip_warn3", "sch_clip_warn4")

# chip geometry: narrow body, pads sticking out
CHIP_X0, CHIP_X1 = 206, 286          # corpo
CHIP_Y0 = 268
CHIP_PITCH = 40
PAD_CHIP = 26                     # quanto sporge la piazzola
CHIP_HALF_H = 13                     # half the height of the pad

# --------------------------------------------------------------- geometria
# Everything in "natural" coordinates: multiplied by k when drawn.
WIDTH, HEIGHT = 1030, 566

# THE HEADER IS ON THE LEFT, and that is not a whim: the four signals
# (SCLK, MOSI, MISO, CS) come out of pins 4-7, which on the Pico are on the
# LEFT side. Putting J4004 over there makes the four wires run straight, and
# only power and ground -- which come out on the right -- have to go around.
# With the header on the right all four had to go around, and the drawing
# turned into a tangle of frames.
PICO_X, PICO_Y = 430, 140           # the Pico board
PICO_W, PICO_H = 190, 358
PIN_PITCH, FIRST_PIN_Y = 16, 170
PAD_LEN, PAD_H = 11, 8

# ⚠️ The header is drawn with its pads further apart than they really are:
# the real pitch is 2.54 mm and the note says so. Spreading them lets the
# number and the name fit INSIDE the pad, the one place they do not end up
# for the wires. Positions, orientation and pin 1 stay the real ones.
HEADER_COLS = [170, 216, 262, 308]     # colonne del J4004
HEADER_ROWS = {"alta": 292, "bassa": 356}
PAD_HEADER = 15

# GND comes off pin 3, not pin 38: it is on the left side next to the
# four signals (3-4-5-6-7 contiguous, a single five-way comb) so that only
# ONE wire -- the 3V3 -- has to go around the board.
VCC_LANE_Y = 520                 # the lane below, for VCC alone
VCC_X = 686                   # vertical to the right of the board
GND_LANE_X = 140                   # vertical on the left, just outside the shell
LANES = (420, 440)             # returns below on the left: MISO, CS
RETURN_X = (350, 368)          # verticali corrispondenti

TITLE_Y, NOTE_Y = 62, 76
COL_X, COL_WIDTH = 730, 280


def pico_pin_y(number):
    if number <= 20:
        return FIRST_PIN_Y + (number - 1) * PIN_PITCH
    return FIRST_PIN_Y + (40 - number) * PIN_PITCH


class Diagram(tk.Toplevel):
    """The wiring window: it redraws to scale when the size changes."""

    def __init__(self, parent, tm, L, clip=False):
        tk.Toplevel.__init__(self, parent, background=T.INK)
        self.theme = tm
        self.L = L
        # two diagrams: a known board's header, or the clip on the bare
        # chip, which is every other case
        self.clip = clip
        self.k = 1.0
        self._redraw_after = None
        self.title(L("sch_title_clip" if clip else "sch_title"))
        self.geometry("1060x630")
        self.minsize(660, 420)

        self.canvas = tk.Canvas(self, background=T.INK, highlightthickness=0, bd=0)
        # ⚠️ Below a certain size the drawing cannot shrink any further:
        # fonts have a legible minimum and the text grows against the
        # rest. Without a scrollbar the last notes simply disappeared.
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
        """The scrollbar appears only when it is actually needed."""
        if float(first) <= 0.0 and float(last) >= 1.0:
            self.bar.pack_forget()
        else:
            self.bar.pack(side="right", fill="y")
        self.bar.set(first, last)

    def _on_wheel(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    # ------------------------------------------------------------- scala
    def _maybe_redraw(self, _event_of=None):
        if self._redraw_after:
            self.after_cancel(self._redraw_after)
        self._redraw_after = self.after(70, self.draw)

    def _s(self, *values):
        """Coordinates to scale. Returns a number or a list, as it was given."""
        if len(values) == 1:
            return values[0] * self.k
        return [v * self.k for v in values]

    def _font(self, points, bold=False, mono=False):
        """A font to scale, never below what can be read."""
        family = self.theme.mono if mono else self.theme.ui
        size_text = max(6, int(round(points * self.k)))
        return (family, size_text, "bold") if bold else (family, size_text)

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

    def _frame_around(self, tag, x0, y0, x1, title, margin=13):
        """Draws the box AROUND what is already there, by measuring it.

        ⚠️ The content used to be written inside a box whose height was
        decided by hand, and with long sentences the text spilled past the
        border. Here what has been drawn is measured (bbox) and the box is
        fitted to it; then it is sent to the back, so the content stays on
        top.
        """
        bounds = self.canvas.bbox(tag)
        background = (bounds[3] / self.k) + margin if bounds else y0 + 46
        background_colour = self._rect(x0, y0, x1, background)
        self.canvas.tag_lower(background_colour)
        self._text(x0 + 11, y0 + 12, T.micro(title), T.MUT, self._font(7, True))
        a, b = self._s(x0 + 11, y0 + 23)
        self.canvas.create_line(a, b, self._s(x1 - 11), b, fill=T.LINE)
        return background

    def _wire(self, points, colour):
        """A wire: dark outline underneath to lift it off the ground, colour on top.

        ⚠️ SHARP corners, not splines: the approximated curve looks
        hand-drawn and does not even pass through the given points. The routes
        here are orthogonal and must stay that way, with only the round join.
        """
        plates = []
        for x, y in points:
            plates += [self._s(x), self._s(y)]
        for width, tint in ((max(3.2, 5.2 * self.k), "#060B10"),
                                 (max(1.8, 2.9 * self.k), colour)):
            self.canvas.create_line(*plates, fill=tint, width=width,
                                  capstyle="round", joinstyle="round")

    # ------------------------------------------------------------ disegno
    def draw(self):
        self._redraw_after = None
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
        """The scroll region is what the drawing actually occupies."""
        bounds = self.canvas.bbox("all")
        if bounds:
            self.canvas.configure(scrollregion=(0, 0, bounds[2],
                                              bounds[3] + self._s(12)))

    def _draw_title_bar(self, real_width):
        top = self._s(52)
        # the gradient puts itself at the bottom: a filled rectangle drawn
        # under it would cover it
        T.gradient(self.canvas, real_width, top)
        self.canvas.create_line(0, top, real_width, top, fill=T.LINE)
        self._text(20, 18, self.L("sch_title_clip" if self.clip
                                   else "sch_title"), T.FG, self._font(12, True))
        self._text(21, 37, self.L("sch_sub_clip" if self.clip
                                   else "sch_sub"), T.MUT, self._font(8))

    # -- the Pico ---------------------------------------------------------
    def _draw_pico(self):
        t = self.canvas
        x1, y1 = PICO_X + PICO_W, PICO_Y + PICO_H

        self._text(PICO_X, TITLE_Y, T.micro(self.L("sch_pico")), T.MUT,
                    self._font(7, True))
        # ⚠️ anchor "nw": with vertical centring the first line of a note
        # that wraps climbs ABOVE the given point, onto the heading.
        self._text(PICO_X, NOTE_Y - 4, self.L("sch_pico_note"), "#5E7488",
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
                    x_num, x_name, anchor = PICO_X + 6, PICO_X + 21, "w"
                else:
                    pad0, pad1 = x1, x1 + PAD_LEN
                    x_num, x_name, anchor = x1 - 6, x1 - 21, "e"

                if colour:      # a halo, so it catches the eye
                    self._rect(pad0 - 2.5, y - PAD_H / 2.0 - 2.5,
                               pad1 + 2.5, y + PAD_H / 2.0 + 2.5, "", colour)
                self._rect(pad0, y - PAD_H / 2.0, pad1, y + PAD_H / 2.0,
                           colour or "#C9A227", colour or "#8A6F1B")
                self._text(x_num, y, str(number),
                            "#8FA6B8" if not colour else "#E4EDF4",
                            self._font(6.5, bool(colour), mono=True), anchor=anchor)
                # for GND the pin name is already the signal: no repeating
                label = name
                if colour and signal != name:
                    label = "%s · %s" % (name, signal)
                self._text(x_name, y, label,
                            colour or "#7E9C8C", self._font(7, bool(colour)),
                            anchor=anchor)

    def _draw_pico_parts(self, x1, y1):
        """The parts you can see on the real board, to tell which way up it is.

        ⚠️ The USB connector alone was not enough: whoever looks at the
        drawing cannot tell whether they are seeing the board from above or
        below, and the pins are mirrored. The square chip in the middle, the
        BOOTSEL button under the USB and the debug pads at the bottom give the
        orientation you have in front of you holding the board.

        ⚠️ Everything sits in the free CENTRE STRIP. The pin names are
        written inside the board and, where the signal is appended
        ("GP2 · SCLK", "3V3 OUT · VCC"), they reach almost to the middle:
        the parts have to go where those names are short, or they land on top
        of them. That already happened once.
        """
        cx = (PICO_X + x1) / 2.0

        # the BOOTSEL button, just below the USB: rows 1-3 and 38-40, short names
        bx, by = cx, PICO_Y + 26
        self._rect(bx - 13, by - 8, bx + 13, by + 8, "#20262E", "#3A4652")
        self._rect(bx - 8, by - 4, bx + 8, by + 4, "#313943", "#4B5967")
        self._text(cx, by + 17, "BOOTSEL", "#7E9C8C", self._font(6, True),
                    anchor="center")

        # the chip: square, in the middle, where the names beside it are short
        side = 62
        qx0, qy0 = cx - side / 2.0, PICO_Y + 150
        self._rect(qx0, qy0, qx0 + side, qy0 + side, "#12171D", "#39434E")
        # the pin-1 dot, top left as on the real chip
        px, py = self._s(qx0 + 9, qy0 + 9)
        r = self._s(3)
        self.canvas.create_oval(px - r, py - r, px + r, py + r, fill="#8FA2B2",
                              outline="")
        self._text(cx, qy0 + side / 2.0, "RP2040", "#B9C7D3",
                    self._font(7, True), anchor="center")

        # the debug pads (SWD) along the bottom edge
        for index in range(3):
            sx = cx - 26 + index * 26
            self._rect(sx - 7, y1 - 16, sx + 7, y1 - 6, "#C9A227", "#8A6F1B")
        self._text(cx, y1 - 26, "SWD", "#5E8A72", self._font(6),
                    anchor="center")

    # -- the header -------------------------------------------------------
    def _draw_header_pins(self):
        x0, x1 = HEADER_COLS[0] - PAD_HEADER - 9, HEADER_COLS[3] + PAD_HEADER + 9
        y0, y1 = HEADER_ROWS["alta"] - PAD_HEADER - 9, HEADER_ROWS["bassa"] + PAD_HEADER + 9

        self._text(x0, TITLE_Y, T.micro(self.L("sch_conn")), T.MUT,
                    self._font(7, True))
        self._text(x0, NOTE_Y - 4, self.L("sch_conn_note"), "#5E7488",
                    self._font(7), anchor="nw", width=210)

        self._rect(x0, y0, x1, y1, "#171E26", "#2E3A46")
        self._rect(x0 + 3, y0 + 3, x1 - 3, y1 - 3, "", "#0D131A")

        # the pin-1 triangle, as in the silkscreen: next to VCC
        tx, ty = self._s(x0 - 8), self._s(HEADER_ROWS["bassa"])
        d = self._s(6)
        self.canvas.create_polygon(tx - d * 0.7, ty - d, tx - d * 0.7, ty + d,
                                 tx + d * 0.7, ty, fill="#E4EDF4", outline="")
        self._text(x0 - 20, HEADER_ROWS["bassa"], "1", "#E4EDF4",
                    self._font(7, True, mono=True), anchor="e")

        by_number = {c[3]: c[0] for c in CONNECTIONS}
        for column, row_, number, name in J4004:
            x, y = HEADER_COLS[column], HEADER_ROWS[row_]
            signal = by_number.get(number)
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
            # number and name INSIDE the pad: outside they would end up under the wires
            dark = bool(colour)
            self._text(x, y - 5, str(number),
                        "#0A1017" if dark else "#54657A",
                        self._font(6, mono=True), anchor="center")
            self._text(x, y + 6, name, "#0A1017" if dark else "#7C8B99",
                        self._font(6.5, True), anchor="center")

        # ⚠️ Moved right of the VCC riser (x = HEADER_COLS[0]): the red wire
        # runs under there and the text became unreadable.
        # ⚠️ Width capped at 200: any wider and it ran into the Pico board
        # (which starts at x=430), and the last words ended up under the
        # pins.
        self._text(HEADER_COLS[0] + 34, 456, self.L("sch_unk"), "#93A5B4",
                    self._font(7), anchor="nw", width=200)

    # -- the bare chip, taken with the clip -------------------------------
    def _draw_bare_chip(self):
        """The SOIC-8 seen from above, pins coloured by signal.

        ⚠️ No wires drawn: see the note next to SOIC8. Here the
        connection is read from the NUMBERS and the colours, which is also how
        it is actually done -- looking at the notch and counting pins.
        """
        y_end = CHIP_Y0 + 3 * CHIP_PITCH
        self._text(CHIP_X0 - PAD_CHIP, TITLE_Y, T.micro(self.L("sch_chip")), T.MUT,
                    self._font(7, True))
        self._text(CHIP_X0 - PAD_CHIP, NOTE_Y - 4, self.L("sch_chip_note"),
                    "#5E7488", self._font(7), anchor="nw", width=230)

        # corpo del contenitore
        self._rect(CHIP_X0, CHIP_Y0 - 30, CHIP_X1, y_end + 30, "#12171D", "#39434E")
        # the notch: this is how you tell which end pin 1 is at
        cx, cy = self._s((CHIP_X0 + CHIP_X1) / 2.0, CHIP_Y0 - 30)
        r = self._s(13)
        self.canvas.create_arc(cx - r, cy - r, cx + r, cy + r, start=180,
                             extent=180, style="chord", fill=T.INK,
                             outline="#39434E")
        # and the dot next to pin 1, which real chips nearly always have.
        # ⚠️ It sits ABOVE the first row, not beside it: alongside the pin it
        # landed on the signal name.
        px, py = self._s(CHIP_X0 + 13, CHIP_Y0 - 15)
        d = self._s(3.5)
        self.canvas.create_oval(px - d, py - d, px + d, py + d, fill="#8FA2B2",
                              outline="")

        for side, number, name, signal in SOIC8:
            row_ = (number - 1) if side == "sx" else (8 - number)
            y = CHIP_Y0 + row_ * CHIP_PITCH
            colour = T.WIRE.get(signal) if signal else None
            if side == "sx":
                x0, x1 = CHIP_X0 - PAD_CHIP, CHIP_X0
                x_num, anchor_num = CHIP_X0 - PAD_CHIP - 8, "e"
            else:
                x0, x1 = CHIP_X1, CHIP_X1 + PAD_CHIP
                x_num, anchor_num = CHIP_X1 + PAD_CHIP + 8, "w"
            self._rect(x0, y - CHIP_HALF_H, x1, y + CHIP_HALF_H,
                       colour or "#2A323B", colour or "#3A4652")
            self._text(x_num, y, str(number), "#8FA2B2",
                        self._font(7, True, mono=True), anchor=anchor_num)
            # the name goes INSIDE the body, on its own pin's side
            self._text(CHIP_X0 + 10 if side == "sx" else CHIP_X1 - 10, y, name,
                        colour or "#6E8296", self._font(7, True),
                        anchor="w" if side == "sx" else "e")

        # ⚠️ /WP and /HOLD held low = the chip takes the commands and writes
        # nothing. The same silent failure as the write protection.
        self._text(CHIP_X0 - PAD_CHIP, y_end + 58, self.L("sch_wp_note"), "#93A5B4",
                    self._font(7), anchor="nw", width=210)

    # -- i cavetti ---------------------------------------------------------
    def _draw_wires(self):
        sx = PICO_X - PAD_LEN
        dx = PICO_X + PICO_W + PAD_LEN
        miso_lane, cs_lane = LANES
        miso_x, cs_x = RETURN_X

        # the wires stop at the EDGE of the pad, not at its centre: inside
        # is where the number and the name sit
        top = HEADER_ROWS["alta"] - PAD_HEADER
        bottom = HEADER_ROWS["bassa"] + PAD_HEADER

        # the four signals: from the Pico's left side to the header, straight
        self._wire([(sx, pico_pin_y(4)), (HEADER_COLS[1], pico_pin_y(4)),
                    (HEADER_COLS[1], top)], T.WIRE["SCLK"])
        self._wire([(sx, pico_pin_y(5)), (HEADER_COLS[2], pico_pin_y(5)),
                    (HEADER_COLS[2], top)], T.WIRE["MOSI"])
        self._wire([(sx, pico_pin_y(6)), (miso_x, pico_pin_y(6)), (miso_x, miso_lane),
                    (HEADER_COLS[2], miso_lane), (HEADER_COLS[2], bottom)], T.WIRE["MISO"])
        self._wire([(sx, pico_pin_y(7)), (cs_x, pico_pin_y(7)), (cs_x, cs_lane),
                    (HEADER_COLS[1], cs_lane), (HEADER_COLS[1], bottom)], T.WIRE["CS"])

        # GND comes out on the left as well and returns alongside: its pad
        # sits in the top row, in the same column as VCC
        self._wire([(sx, pico_pin_y(3)), (GND_LANE_X, pico_pin_y(3)), (GND_LANE_X, HEADER_ROWS["alta"]),
                    (HEADER_COLS[0] - PAD_HEADER, HEADER_ROWS["alta"])], T.WIRE["GND"])
        # the 3V3 is the only one leaving on the right: it goes under, outside
        self._wire([(dx, pico_pin_y(36)), (VCC_X, pico_pin_y(36)), (VCC_X, VCC_LANE_Y),
                    (HEADER_COLS[0], VCC_LANE_Y), (HEADER_COLS[0], bottom)], T.WIRE["VCC"])

    # -- colonna di destra: tabella e avvisi -------------------------------
    def _draw_side_column(self):
        x = COL_X
        y = TITLE_Y - 12

        line = y + 38
        for label, dx in ((self.L("sch_col_signal"), 30),
                              (self.L("sch_col_pico"), 130),
                              (self.L("sch_col_chip" if self.clip
                                      else "sch_col_conn"), 215)):
            self._text(x + dx, line, T.micro(label), "#55697C",
                        self._font(6, True), tag="table")
        line += 15

        for signal, pin_pico, pico_name, pin_conn in (
                CLIP_CONNECTIONS if self.clip else CONNECTIONS):
            colour = T.WIRE[signal]
            a, b, c = self._s(x + 12, line, x + 23)
            self.canvas.create_line(a, b, c, b, fill=colour, tags="table",
                                  width=max(2.0, 3.0 * self.k), capstyle="round")
            self._text(x + 30, line, signal, colour, self._font(8, True),
                        tag="table")
            self._text(x + 130, line, "%2d  %s" % (pin_pico, pico_name), T.FG,
                        self._font(7, mono=True), tag="table")
            self._text(x + 215, line, "%d  %s" % (pin_conn, signal), T.FG,
                        self._font(7, mono=True), tag="table")
            line += 21

        a, b = self._s(x + 12, line - 8)
        self.canvas.create_line(a, b, self._s(x + COL_WIDTH - 12), b, fill=T.LINE,
                              tags="table")
        # ⚠️ anchor "nw", not "w": centred vertically, wrapping text extends
        # ABOVE the given point too, and it landed on the rule.
        self._text(x + 12, line - 1,
                    self.L("sch_clip_note" if self.clip else "sch_gnd_note"),
                    "#6E8296",
                    self._font(7), anchor="nw", width=COL_WIDTH - 24,
                    tag="table")

        # the box fits what is inside it, not the other way round
        background = self._frame_around("table", x, y, x + COL_WIDTH,
                               self.L("sch_table"))

        # --- avvisi
        y2 = background + 14
        line = y2 + 38
        for index, key in enumerate(CLIP_WARNINGS if self.clip
                                        else WARNINGS):
            colour = T.CRIT if index < 2 else T.WARN
            a, b = self._s(x + 15, line + 4)
            r = self._s(3)
            self.canvas.create_oval(a - r, b - r, a + r, b + r, fill=colour,
                                  outline="", tags="warnings")
            board_id = self._text(x + 26, line, self.L(key), "#B9C7D3",
                                         self._font(7), anchor="nw",
                                         width=COL_WIDTH - 42, tag="warnings")
            # every warning drops by what it REALLY takes up: in English and
            # Italian the line counts are not the same
            bounds = self.canvas.bbox(board_id)
            line += ((bounds[3] - bounds[1]) / self.k if bounds else 34) + 15

        self._frame_around("warnings", x, y2, x + COL_WIDTH, self.L("sch_warn_title"))

        # The pinout sources are no longer in the drawing: they stay in the
        # documentation and at the top of this file, where they serve whoever
        # wants to check.


def open_window(parent, tm, L, clip=False):
    """Opens the diagram, or brings an already-open one to the front.

    ⚠️ If the open one is of the other kind it has to be rebuilt, not raised:
    it would be another board's diagram.
    """
    existing = getattr(parent, "_wiring_window", None)
    if existing is not None and existing.winfo_exists():
        if getattr(existing, "clip", False) == clip:
            existing.deiconify()
            existing.lift()
            existing.focus_set()
            return existing
        existing.destroy()
    window = Diagram(parent, tm, L, clip=clip)
    parent._wiring_window = window
    return window
