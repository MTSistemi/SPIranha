# -*- coding: utf-8 -*-
"""Finding a chip model among the ones flashrom knows.

There are nearly five hundred SPI chips and a dropdown is no place to pick
from: here there is a search box that filters as you type, and a table that
also shows what you need in order to decide -- the size, the working voltage,
and whether flashrom has actually read and written that model or only got as
far as recognising it.

⚠️ SPI only. The other buses cannot be reached over serprog, so a parallel
chip in this list would only be a way to waste time.

⚠️ The list comes from `flashrom -L`, that is from the executable in use:
there is no table of ours to keep up to date, and when flashrom changes
version the list changes with it.
"""
from __future__ import unicode_literals

import tkinter as tk
from tkinter import ttk

import theme as T
import voltage as V


class ChipSearch(tk.Toplevel):
    """The search window. Whoever opens it passes what to do with the pick."""

    def __init__(self, parent, tm, L, chip, on_pick, iniziale=""):
        tk.Toplevel.__init__(self, parent, background=T.INK)
        self.theme = tm
        self.L = L
        self.on_pick = on_pick
        self.tutti = [c for c in chip if c.spi]
        self.shown = []
        self.title(L("cerca_titolo"))
        self.geometry("760x520")
        self.minsize(520, 360)
        self.transient(parent)
        T.dark_title_bar(self)

        self._style()
        frame = tk.Frame(self, background=T.INK)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        header = tk.Frame(frame, background=T.INK)
        header.grid(row=0, column=0, sticky="ew")
        tk.Label(header, text=L("cerca_titolo"), background=T.INK,
                 foreground=T.FG, font=tm.f_titolo).pack(side="left")
        self.var_count = tk.StringVar()
        tk.Label(header, textvariable=self.var_count, background=T.INK,
                 foreground=T.MUT, font=tm.f_text).pack(side="right")

        line = tk.Frame(frame, background=T.INK)
        line.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        line.columnconfigure(1, weight=1)
        tk.Label(line, text=T.micro(L("cerca_campo")), background=T.INK,
                 foreground=T.MUT, font=tm.f_micro).grid(row=0, column=0,
                                                         sticky="w")
        self.var_filter = tk.StringVar(value=iniziale)
        self.field = ttk.Entry(line, textvariable=self.var_filter,
                               font=tm.f_text)
        self.field.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.var_filter.trace_add("write", lambda *_a: self._filter())

        table = tk.Frame(frame, background=T.INK)
        table.grid(row=2, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        columns = ("produttore", "modello", "misura", "volt", "prove")
        self.tree = ttk.Treeview(table, columns=columns, show="headings",
                                  style="Cerca.Treeview", selectmode="browse")
        for key, width, anchor in (("produttore", 120, "w"),
                                          ("modello", 290, "w"),
                                          ("misura", 80, "e"),
                                          ("volt", 70, "e"),
                                          ("prove", 70, "center")):
            # ⚠️ the heading lines up like its column: centred over a wide
            # column it looked like it belonged to the one next to it
            self.tree.heading(key, text=T.micro(L("cerca_col_" + key)),
                               anchor=anchor)
            self.tree.column(key, width=width, anchor=anchor,
                              stretch=(key == "modello"))
        self.tree.grid(row=0, column=0, sticky="nsew")
        bar = ttk.Scrollbar(table, orient="vertical",
                              command=self.tree.yview)
        bar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=bar.set)
        # ⚠️ i chip a 1,8 V si vedono a colpo d'occhio: e' l'errore che costa
        # un chip, non un messaggio
        self.tree.tag_configure("bassa", foreground="#F0A93B")
        self.tree.tag_configure("ignota", foreground=T.MUT)

        self.tree.bind("<Double-Button-1>", lambda _e: self.pick())
        self.tree.bind("<Return>", lambda _e: self.pick())
        self.field.bind("<Return>", lambda _e: self._pick_first())
        self.field.bind("<Down>", lambda _e: self._focus_first())
        self.bind("<Escape>", lambda _e: self.destroy())

        footer = tk.Frame(frame, background=T.INK)
        footer.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        tk.Label(footer, text=L("cerca_nota"), background=T.INK,
                 foreground="#6E8296", font=tm.f_micro,
                 wraplength=430, justify="left").pack(side="left")
        ttk.Button(footer, text=L("cerca_annulla"), style="Ghost.TButton",
                   command=self.destroy).pack(side="right")
        self.b_pick = ttk.Button(footer, text=L("cerca_scegli"),
                                   style="Primario.TButton", command=self.pick)
        self.b_pick.pack(side="right", padx=(0, 8))

        self._filter()
        self.field.focus_set()

    # --------------------------------------------------------------- stile
    def _style(self):
        s = ttk.Style(self)
        s.configure("Cerca.Treeview", background=T.PANEL, fieldbackground=T.PANEL,
                    foreground=T.FG, bordercolor=T.LINE, borderwidth=0,
                    rowheight=max(20, self.theme.f_text[1] * 2),
                    font=self.theme.f_text)
        s.configure("Cerca.Treeview.Heading", background=T.SIDEBAR,
                    foreground=T.MUT, relief="flat", font=self.theme.f_micro)
        s.map("Cerca.Treeview.Heading", background=[("active", T.PANEL2)])
        s.map("Cerca.Treeview", background=[("selected", T.ACCENT2)],
              foreground=[("selected", "#FFFFFF")])

    # ------------------------------------------------------------- filtro
    def _filter(self):
        # every word must appear: "win 128" finds the 128 Mbit Winbonds
        parole = [p for p in self.var_filter.get().lower().split() if p]
        self.tree.delete(*self.tree.get_children())
        self.shown = []
        for chip in self.tutti:
            text = ("%s %s" % (chip.vendor, chip.name)).lower()
            if all(p in text for p in parole):
                self.shown.append(chip)
        for index, chip in enumerate(self.shown[:600]):
            volts, _famiglia = V.voltage_of(chip.name)
            label_for = ("bassa" if volts == V.LOW
                         else ("" if volts else "ignota"))
            self.tree.insert(
                "", "end", iid=str(index),
                values=(chip.vendor, chip.name, _misura(chip.kb),
                        _volt(volts, self.L.code), chip.tested or "—"),
                tags=(label_for,) if label_for else ())
        self.var_count.set(self.L("cerca_conteggio",
                                      how_many=len(self.shown),
                                      total=len(self.tutti)))

    def _focus_first(self):
        figli = self.tree.get_children()
        if figli:
            self.tree.selection_set(figli[0])
            self.tree.focus(figli[0])
            self.tree.focus_set()

    def _pick_first(self):
        if not self.tree.selection():
            self._focus_first()
        self.pick()

    # ------------------------------------------------------------- scelta
    def pick(self):
        selezione = self.tree.selection()
        if not selezione:
            return
        index = int(selezione[0])
        if index >= len(self.shown):
            return
        chip = self.shown[index]
        self.on_pick(chip)
        self.destroy()


def _volt(volts, language="it"):
    """1,8 V in italiano, 1.8 V in inglese: il separatore decimale cambia."""
    if volts is None:
        return "?"
    text = "%.1f V" % volts
    return text.replace(".", ",") if language == "it" else text


def _misura(kb):
    if not kb:
        return "?"
    if kb >= 1024:
        return "%g MiB" % (kb / 1024.0)
    return "%d KiB" % kb


def open_window(parent, tm, L, chip, on_pick, iniziale=""):
    """Opens the search, or brings the open one back to the front."""
    existing = getattr(parent, "_search_window", None)
    if existing is not None and existing.winfo_exists():
        existing.deiconify()
        existing.lift()
        existing.focus_set()
        return existing
    window = ChipSearch(parent, tm, L, chip, on_pick, iniziale)
    parent._finestra_ricerca = window
    return window
