# -*- coding: utf-8 -*-
"""The "instrument panel" dark theme, ported to tkinter.

It is not decoration: it is a visual language that was decided once and gets
reused. A monitoring console, not a generic dashboard: thin rules, spaced-out
uppercase micro-labels, fixed-pitch numbers and logs, and the strong colour
spent in ONE place only.
"""
from __future__ import unicode_literals

import os
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# ---------------------------------------------------------------- colori
INK = "#0B1119"        # fondo ardesia a dominante blu (non grigio neutro: voluto)
PANEL = "#141E29"      # superficie card
PANEL2 = "#1A2634"     # superficie sollevata
LINE = "#24323F"       # filetti e bordi
FG = "#E4EDF4"         # testo
MUT = "#8095A6"        # testo secondario
ACCENT = "#2F9BE0"     # accent (a blue lightened for the dark ground)
ACCENT2 = "#0070B0"    # blu Polo autentico

OK = "#35B87A"
WARN = "#E0A030"
CRIT = "#E5484D"

OK_BG, OK_BORDER = "#12241C", "#1E4D38"
WARN_BG, WARN_BORDER = "#241D10", "#4D3C1A"
CRIT_BG, CRIT_BORDER = "#251215", "#4F2225"

SIDEBAR = "#0E161F"          # sidebar / trogolo
ACTIVE = "#16273A"
HEADER_DA, HEADER_A = "#0F2C42", INK    # gradiente 103deg

LOG_BG = "#080D13"
LOG_TIME = "#546B7E"
LOG_OK = "#63C08E"

WINDOW_BORDER = "#1E2A36"

# wire colours in the diagram: still distinguishable on the dark ground
WIRE = {
    "VCC": "#E5484D",
    "GND": "#7E93A4",
    "SCLK": "#E0A030",
    "MOSI": "#2F9BE0",
    "MISO": "#35B87A",
    "CS": "#B18AE0",
}


def dark_title_bar(window):
    """A dark title bar, like the rest of the window.

    From Windows 10 1809 onwards this is asked of the window manager (DWM).
    The attribute is 20 on recent builds and 19 on older ones; if neither
    works, we live with a light title bar.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        window.update_idletasks()
        handle = ctypes.windll.user32.GetParent(window.winfo_id())
        enabled = ctypes.c_int(1)
        for attribute in (20, 19):
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                handle, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled))
            if result == 0:
                return
    except Exception:                                  # noqa: BLE001
        pass


def micro(text):
    """Micro-label: UPPERCASE and letter-spaced.

    tkinter knows nothing about letter-spacing, so it is done by hand with
    thin spaces between the letters. Ugly to write, right to look at.
    """
    return " ".join(text.upper())


def _first_free(root, candidates, fallback):
    present = set(tkfont.families(root))
    for name in candidates:
        if name in present:
            return name
    return fallback


class Theme(object):
    """Holds the chosen fonts and applies the ttk styles."""

    def __init__(self, root):
        self.ui = _first_free(
            root, ["Segoe UI Variable Text", "Segoe UI"], "TkDefaultFont")
        self.mono = _first_free(
            root, ["Cascadia Code", "Cascadia Mono", "Consolas"], "Courier New")

        # Deliberately tight sizes: the window has to stay wide, not tall.
        self.f_title = (self.ui, 12, "bold")
        self.f_sub = (self.ui, 8)
        self.f_text = (self.ui, 8)
        self.f_micro = (self.ui, 7, "bold")
        self.f_tiny = (self.ui, 7)
        self.f_datum = (self.mono, 8)
        self.f_log = (self.mono, 8)
        self.f_button = (self.ui, 8)

        self._apply(root)

    # -------------------------------------------------------------- ttk
    def _apply(self, root):
        root.configure(background=INK)
        s = ttk.Style(root)
        # clam is the one ttk theme that really lets itself be recoloured: vista
        # and xpnative draw with Windows images and ignore background.
        s.theme_use("clam")

        s.configure(".", background=INK, foreground=FG, font=self.f_text,
                    borderwidth=0, focuscolor=ACCENT)
        s.configure("TFrame", background=INK)
        s.configure("Card.TFrame", background=PANEL)
        s.configure("Sollevato.TFrame", background=PANEL2)

        s.configure("TLabel", background=INK, foreground=FG, font=self.f_text)
        s.configure("Card.TLabel", background=PANEL, foreground=FG)
        s.configure("Micro.TLabel", background=PANEL, foreground=MUT,
                    font=self.f_micro)
        s.configure("MicroFondo.TLabel", background=INK, foreground=MUT,
                    font=self.f_micro)
        s.configure("Muto.TLabel", background=PANEL, foreground=MUT,
                    font=(self.ui, 8))
        s.configure("Titolo.TLabel", background=INK, foreground=FG,
                    font=self.f_title)
        s.configure("Sub.TLabel", background=INK, foreground=MUT,
                    font=self.f_sub)
        s.configure("Dato.TLabel", background=PANEL, foreground=FG,
                    font=self.f_datum)

        # --- pulsanti -------------------------------------------------
        self._button_style(s, "Primary.TButton", ACCENT2, "#FFFFFF", "#1B6E9F",
                      "#0A80C8", "#0C5F92")
        self._button_style(s, "Secondario.TButton", "#1D2937", FG, "#2A3846",
                      "#243244", "#18222E")
        self._button_style(s, "Ghost.TButton", PANEL, "#8FC2E3", "#2A4457",
                      "#17242F", "#111A23")
        self._button_style(s, "Pericolo.TButton", CRIT_BG, "#FF9C9F", CRIT_BORDER,
                      "#31171B", "#1E0F12")

        # --- campi ----------------------------------------------------
        for name in ("TEntry", "TCombobox"):
            s.configure(name, fieldbackground=SIDEBAR, background=SIDEBAR,
                        foreground=FG, bordercolor=LINE, lightcolor=LINE,
                        darkcolor=LINE, insertcolor=FG, arrowcolor=MUT,
                        selectbackground=ACCENT2, selectforeground="#FFFFFF",
                        padding=4)
            s.map(name,
                  bordercolor=[("focus", ACCENT)],
                  lightcolor=[("focus", ACCENT)],
                  darkcolor=[("focus", ACCENT)],
                  fieldbackground=[("disabled", "#101922")],
                  foreground=[("disabled", "#4A5C6B")],
                  arrowcolor=[("disabled", "#3A4A58")])
        # the combobox dropdown is a plain Tk Listbox: it is dressed separately
        root.option_add("*TCombobox*Listbox.background", PANEL2)
        root.option_add("*TCombobox*Listbox.foreground", FG)
        root.option_add("*TCombobox*Listbox.selectBackground", ACCENT2)
        root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
        root.option_add("*TCombobox*Listbox.font", self.f_text)

        # --- radio / spunte -------------------------------------------
        for name, background in (("TRadiobutton", PANEL), ("Fondo.TRadiobutton", INK)):
            s.configure(name, background=background, foreground=FG,
                        indicatorbackground=SIDEBAR, indicatorforeground=ACCENT,
                        bordercolor=LINE, font=self.f_text, padding=2)
            s.map(name, background=[("active", background)],
                  indicatorbackground=[("selected", ACCENT),
                                       ("active", PANEL2)])

        # --- barra di avanzamento -------------------------------------
        s.configure("Sottile.Horizontal.TProgressbar", troughcolor=SIDEBAR,
                    background=ACCENT, bordercolor=SIDEBAR, lightcolor=ACCENT,
                    darkcolor=ACCENT2, thickness=5)

        # --- scrollbar -------------------------------------------------
        s.configure("Vertical.TScrollbar", background=PANEL2, troughcolor=INK,
                    bordercolor=INK, arrowcolor=MUT, gripcount=0)
        s.map("Vertical.TScrollbar", background=[("active", "#28394A")])
        s.configure("Horizontal.TScrollbar", background=PANEL2, troughcolor=INK,
                    bordercolor=INK, arrowcolor=MUT, gripcount=0)

        s.configure("TSeparator", background=LINE)

    @staticmethod
    def _button_style(s, name, background, text, border, above, pressed):
        s.configure(name, background=background, foreground=text,
                    bordercolor=border, lightcolor=background, darkcolor=background,
                    focusthickness=1, focuscolor=border,
                    padding=(11, 6), relief="flat")
        s.map(name,
              background=[("pressed", pressed), ("active", above),
                          ("disabled", "#141C25")],
              foreground=[("disabled", "#43535F")],
              bordercolor=[("disabled", "#1B242E")],
              lightcolor=[("pressed", pressed), ("active", above)],
              darkcolor=[("pressed", pressed), ("active", above)])


# ------------------------------------------------------------- widget

def card(parent, title=None, theme=None):
    """Card: --panel ground, --line hairline, heading in a micro label.

    Returns (outer container, body). Things go into the body.
    """
    out = tk.Frame(parent, background=PANEL, highlightbackground=LINE,
                     highlightcolor=LINE, highlightthickness=1, bd=0)
    body = tk.Frame(out, background=PANEL)
    if title is not None:
        header_area = tk.Frame(out, background=PANEL)
        header_area.pack(fill="x", padx=12, pady=(9, 0))
        label = tk.Label(header_area, text=micro(title), background=PANEL,
                             foreground=MUT, font=theme.f_micro if theme else None,
                             anchor="w")
        label.pack(side="left")
        tk.Frame(out, background=LINE, height=1).pack(fill="x", padx=12,
                                                        pady=(7, 0))
        out.title_label = label
    body.pack(fill="both", expand=True, padx=12, pady=10)
    out.body = body
    return out, body


class Chip(tk.Frame):
    """A status pill: coloured dot plus text."""

    def __init__(self, parent, theme, background=PANEL):
        tk.Frame.__init__(self, parent, background=background)
        self.theme = theme
        self.background = background
        self.pill = tk.Frame(self, background=background, highlightthickness=1,
                                highlightbackground=background, bd=0)
        self.dot = tk.Canvas(self.pill, width=8, height=8, highlightthickness=0,
                               background=background, bd=0)
        self.dot.pack(side="left", padx=(8, 6), pady=4)
        self.text = tk.Label(self.pill, background=background, foreground=MUT,
                              font=theme.f_text, anchor="w", justify="left",
                              wraplength=820)
        self.text.pack(side="left", padx=(0, 10), pady=3)
        self.pill.pack(anchor="w")
        self._id = None
        self.hide()

    def hide(self):
        self.pill.pack_forget()

    def show(self, text, colour=MUT, background=None, border=None):
        background_colour = background or self.background
        self.pill.configure(background=background_colour,
                               highlightbackground=border or background_colour)
        self.dot.configure(background=background_colour)
        self.text.configure(background=background_colour, foreground=colour, text=text)
        self.dot.delete("all")
        self.dot.create_oval(1, 1, 7, 7, fill=colour, outline="")
        self.pill.pack(anchor="w")


class Checkbox(tk.Frame):
    """A hand-drawn checkbox: 14px, 3px corners, the tick traced.

    ttk.Checkbutton under clam shows a system square that clashes with
    everything else; this is the design system's box, drawn on a Canvas.
    """

    SIDE = 15

    def __init__(self, parent, theme, variable_, text="", command=None,
                 background=PANEL, colour=FG):
        tk.Frame.__init__(self, parent, background=background, cursor="hand2")
        self.variable = variable_
        self.command = command
        self.colour = colour
        self.canvas = tk.Canvas(self, width=self.SIDE + 2, height=self.SIDE + 2,
                              highlightthickness=0, background=background, bd=0)
        self.canvas.pack(side="left")
        self.label = tk.Label(self, text=text, background=background,
                                  foreground=colour, font=theme.f_text)
        self.label.pack(side="left", padx=(8, 0))
        for widget in (self, self.canvas, self.label):
            widget.bind("<Button-1>", self._flip)
        self.variable.trace_add("write", lambda *_: self.redraw())
        self.redraw()

    def configure(self, cnf=None, **kw):
        """Also accepts `testo=`, so the translator treats it like the others."""
        text = kw.pop("testo", None)
        if text is not None:
            self.label.configure(text=text)
        if cnf or kw:
            return tk.Frame.configure(self, cnf, **kw)
        return None

    config = configure

    def _flip(self, _event_of=None):
        if str(self.label.cget("state")) == "disabled":
            return
        self.variable.set(0 if self.variable.get() else 1)
        if self.command:
            self.command()

    def redraw(self):
        c = self.canvas
        c.delete("all")
        enabled = bool(self.variable.get())
        b, l = 1, self.SIDE
        c.create_rectangle(b, b, b + l, b + l,
                           fill=ACCENT if enabled else SIDEBAR,
                           outline=ACCENT if enabled else LINE, width=1)
        if enabled:
            # spunta tracciata a mano, non un carattere di font
            c.create_line(b + 3.5, b + 7.5, b + 6.2, b + 10.5, b + 11.5, b + 4.5,
                          fill="#08131C", width=2, capstyle="round",
                          joinstyle="round")


def gradient(canvas, width, height, da=HEADER_DA, a=HEADER_A, degrees=103):
    """The header gradient, drawn as stripes.

    tkinter has no gradients: N lines are drawn, interpolating the colour. At
    103 degrees the direction is nearly horizontal, with a slight tilt.
    """
    import math
    canvas.delete("gradiente")
    from_r, from_g, from_b = canvas.winfo_rgb(da)
    to_r, to_g, to_b = canvas.winfo_rgb(a)
    rad = math.radians(degrees - 90)
    spare = math.tan(rad) * height
    steps = max(int(width + abs(spare)), 2)
    for i in range(steps):
        t = i / float(steps - 1)
        colour = "#%02x%02x%02x" % (
            int((from_r + (to_r - from_r) * t)) >> 8,
            int((from_g + (to_g - from_g) * t)) >> 8,
            int((from_b + (to_b - from_b) * t)) >> 8)
        x = i - abs(spare) * 0.5
        canvas.create_line(x, 0, x + spare, height, fill=colour,
                         tags="gradiente")
    canvas.tag_lower("gradiente")
