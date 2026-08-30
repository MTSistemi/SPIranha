# -*- coding: utf-8 -*-
"""The chip map in little squares, defragmenter style.

A rectangle split into blocks: each stands for a slice of flash and takes its
colour from whatever is happening to it. It is not a decorative animation --
the colours come from what flashrom actually says while it works:

  · the ERASE ranges are exact: flashrom with -V prints an E(start:end)
    marker for every block it erases;
  · the WRITE range is exact (W(start:end) marker) and fills up with the
    percentage from --progress;
  · the READ fills up with the percentage, over the range being read.

So with the board on the desk you can see at a glance how far it has got,
and at the end whether it is green everywhere.
"""
from __future__ import unicode_literals

import tkinter as tk

import theme as T

# the states a block can be in
PENDING = 0        # not touched yet
OUTSIDE = 1         # outside the region: it will not be touched
READ = 2
ERASED_BLOCK = 3
WRITTEN = 4
VERIFIED = 5
MISMATCH = 6       # the final check does not add up
ACTIVE = 7        # being worked on right now

COLOURS = {
    PENDING: "#16202B",
    OUTSIDE: "#0E151D",
    READ: "#2A5D80",
    ERASED_BLOCK: T.WARN,
    WRITTEN: T.ACCENT,
    VERIFIED: T.OK,
    MISMATCH: T.CRIT,
    ACTIVE: "#DCEBF7",
}

# ordine e chiavi per la legenda
LEGEND_KEYS = ((PENDING, "leg_pending"), (READ, "leg_read"),
           (ERASED_BLOCK, "leg_erased"), (WRITTEN, "leg_written"),
           (VERIFIED, "leg_verified"), (MISMATCH, "leg_mismatch"))

SIDE = 6          # lato del quadratino
PITCH = 7         # quadratino + fessura
ROWS = 8


class ChipMap(tk.Canvas):

    def __init__(self, parent, total_size=16 * 1024 * 1024, lines=ROWS,
                 on_position=None):
        tk.Canvas.__init__(self, parent, background=T.LOG_BG,
                           highlightthickness=1, highlightbackground=T.LINE,
                           bd=0, height=lines * PITCH + 5)
        self.total_size = total_size
        self.lines = lines
        self.on_position = on_position
        self.columns = 0
        self.states = []
        self._id = []
        self.regions = []
        self._highlighted = None
        self.bind("<Configure>", lambda _e: self._rebuild())
        self.bind("<Motion>", self._under_the_mouse)
        self.bind("<Leave>", lambda _e: self.on_position and self.on_position(None))

    # ------------------------------------------------------------- griglia
    @property
    def blocks(self):
        return len(self.states)

    def _bytes_per_block(self):
        return max(1, self.total_size / float(max(self.blocks, 1)))

    def _rebuild(self):
        width = max(self.winfo_width(), 40)
        columns = max(16, int((width - 6) // PITCH))
        if columns == self.columns and self._id:
            return
        old_ones = list(self.states)
        self.columns = columns
        total = columns * self.lines
        self.delete("all")
        self._id = []
        # the old states are reprojected onto the new grid, so that
        # a resize mid-job does not wipe what is on screen
        fresh = []
        for index in range(total):
            if old_ones:
                fresh.append(old_ones[min(len(old_ones) - 1,
                                        index * len(old_ones) // total)])
            else:
                fresh.append(PENDING)
        self.states = fresh
        for index in range(total):
            column, line = index % columns, index // columns
            x = 3 + column * PITCH
            y = 3 + line * PITCH
            self._id.append(self.create_rectangle(
                x, y, x + SIDE, y + SIDE, fill=COLOURS[self.states[index]],
                outline=""))
        self._draw_regions()

    def _draw_regions(self):
        self.delete("region")
        if self._highlighted is None:
            return
        start, end = self._highlighted
        first, last = self._block_rect(start), self._block_rect(end)
        for index in (first, last):
            column, line = index % self.columns, index // self.columns
            x = 3 + column * PITCH
            y = 3 + line * PITCH
            self.create_rectangle(x - 1, y - 1, x + SIDE + 1, y + SIDE + 1,
                                  outline=T.MUT, width=1, tags="region")

    # ------------------------------------------------------------- accesso
    def _block_rect(self, position):
        if self.blocks == 0:
            return 0
        index = int(position * self.blocks // max(self.total_size, 1))
        return max(0, min(self.blocks - 1, index))

    def _under_the_mouse(self, event):
        if not self.on_position or not self.blocks:
            return
        column = int((event.x - 3) // PITCH)
        line = int((event.y - 3) // PITCH)
        if column < 0 or line < 0 or column >= self.columns or line >= self.lines:
            return self.on_position(None)
        index = line * self.columns + column
        if 0 <= index < self.blocks:
            self.on_position(int(index * self._bytes_per_block()))

    # ------------------------------------------------------------- comandi
    def set_size(self, total_size=None, regions=None):
        if total_size:
            self.total_size = total_size
        if regions is not None:
            self.regions = regions
        self._rebuild()

    def reset(self, state=PENDING):
        for index in range(self.blocks):
            self._paint(index, state)

    def highlight(self, span):
        """Marks the bounds of the region about to be worked on."""
        self._highlighted = span
        if span is None:
            self.reset(PENDING)
        else:
            start, end = span
            self.reset(OUTSIDE)
            self.mark(start, end, PENDING)
        self._draw_regions()

    def _paint(self, index, state):
        if not (0 <= index < self.blocks) or self.states[index] == state:
            return
        self.states[index] = state
        try:
            self.itemconfigure(self._id[index], fill=COLOURS[state])
        except (tk.TclError, IndexError):
            pass

    def mark(self, start, end, state):
        """Colora l'intervallo di byte [inizio, fine]."""
        if end < start:
            return
        for index in range(self._block_rect(start), self._block_rect(end) + 1):
            self._paint(index, state)

    def advance(self, start, end, percent, state, active_=True):
        """Fills the span up to the percentage given."""
        if end < start:
            return
        first, last = self._block_rect(start), self._block_rect(end)
        how_many = last - first + 1
        done_ = int(how_many * max(0, min(100, percent)) / 100.0)
        for spare in range(how_many):
            index = first + spare
            if spare < done_:
                self._paint(index, state)
            elif spare == done_ and active_ and percent < 100:
                self._paint(index, ACTIVE)

    def mark_spans(self, spans, state):
        for start, end in spans:
            self.mark(start, end, state)


class Legend(tk.Frame):
    """What the colours mean, in a single row."""

    def __init__(self, parent, theme, L, background=T.PANEL):
        tk.Frame.__init__(self, parent, background=background)
        self.theme = theme
        self.L = L
        self.entries = []
        for state, key in LEGEND_KEYS:
            cell = tk.Frame(self, background=background)
            cell.pack(side="left", padx=(0, 10))
            square = tk.Canvas(cell, width=SIDE, height=SIDE,
                                  highlightthickness=0, background=background)
            square.create_rectangle(0, 0, SIDE, SIDE, fill=COLOURS[state],
                                       outline="")
            square.pack(side="left", padx=(0, 4))
            label = tk.Label(cell, background=background, foreground=T.MUT,
                                 font=theme.f_tiny)
            label.pack(side="left")
            self.entries.append((label, key))
        self.translate()

    def translate(self):
        for label, key in self.entries:
            label.configure(text=self.L(key))
