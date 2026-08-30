# -*- coding: utf-8 -*-
"""Comparing two BIOS images, with the layout ready to go.

This is the job that was done by hand on 2026-08-22 to find the four areas
where the modified BIOS differed from the board's own: which ranges change,
aligned to 4 KB sectors, and what is inside them. Here it takes a second, and
at the bottom there is the button that writes the flashrom layout file.
"""
from __future__ import unicode_literals

import os
import tkinter as tk
from tkinter import filedialog, ttk

import analysis as A
import chipmap as M
import theme as T


class CompareWindow(tk.Toplevel):

    def __init__(self, parent, tm, L, folder=None):
        tk.Toplevel.__init__(self, parent, background=T.INK)
        self.theme = tm
        self.L = L
        self.folder = folder or ""
        self.result = None
        self.total_size = 0
        self.title(L("cmp_title"))
        self.geometry("980x620")
        self.minsize(680, 460)

        self.var_a = tk.StringVar()
        self.var_b = tk.StringVar()
        self.var_name = tk.StringVar(value="modificata")
        self._build_ui()
        self.bind("<Escape>", lambda _e: self.destroy())
        T.dark_title_bar(self)

    # ---------------------------------------------------------- costruzione
    def _build_ui(self):
        root = tk.Frame(self, background=T.INK)
        root.pack(fill="both", expand=True, padx=10, pady=10)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        header_area = tk.Frame(root, background=T.INK)
        header_area.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tk.Label(header_area, text=self.L("cmp_title"), background=T.INK,
                 foreground=T.FG, font=self.theme.f_title).pack(anchor="w")
        tk.Label(header_area, text=self.L("cmp_sub"), background=T.INK,
                 foreground=T.MUT, font=self.theme.f_sub).pack(anchor="w")

        choice, s = T.card(root, self.L("cmp_sec_files"), self.theme)
        choice.grid(row=1, column=0, sticky="ew")
        s.columnconfigure(1, weight=1)
        for line, (key, variable) in enumerate(((self.L("cmp_a"), self.var_a),
                                              (self.L("cmp_b"), self.var_b))):
            tk.Label(s, text=T.micro(key), background=T.PANEL,
                     foreground=T.MUT, font=self.theme.f_micro).grid(
                row=line, column=0, sticky="w", pady=(0 if not line else 6, 0))
            ttk.Entry(s, textvariable=variable, font=self.theme.f_text).grid(
                row=line, column=1, sticky="ew", padx=(6, 4),
                pady=(0 if not line else 6, 0))
            ttk.Button(s, text=self.L("browse"), width=3,
                       style="Secondario.TButton",
                       command=lambda v=variable: self._pick(v)).grid(
                row=line, column=2, pady=(0 if not line else 6, 0))

        actions = tk.Frame(s, background=T.PANEL)
        actions.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text=self.L("cmp_run"), style="Primary.TButton",
                   command=self.compare_images).pack(side="left")
        tk.Label(actions, text=T.micro(self.L("cmp_name")), background=T.PANEL,
                 foreground=T.MUT, font=self.theme.f_micro).pack(side="left",
                                                                padx=(16, 6))
        ttk.Entry(actions, textvariable=self.var_name, width=16,
                  font=self.theme.f_text).pack(side="left")
        self.b_layout = ttk.Button(actions, text=self.L("cmp_save_layout"),
                                   style="Secondario.TButton",
                                   command=self.save_layout)
        self.b_layout.pack(side="left", padx=8)
        self.b_layout.state(["disabled"])

        self.outcome_text = tk.Label(s, background=T.PANEL, foreground=T.MUT,
                                    font=self.theme.f_text, anchor="w")
        self.outcome_text.grid(row=3, column=0, columnspan=3, sticky="w",
                              pady=(8, 0))

        results_, r = T.card(root, self.L("cmp_sec_outcome"), self.theme)
        results_.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        r.columnconfigure(0, weight=1)
        r.rowconfigure(1, weight=1)

        self.chip_map = M.ChipMap(r, lines=6)
        self.chip_map.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        frame = tk.Frame(r, background=T.LOG_BG, highlightthickness=1,
                           highlightbackground=T.LINE)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.table = tk.Text(frame, wrap="none", font=self.theme.f_log,
                               background=T.LOG_BG, foreground="#C3D2DE",
                               relief="flat", bd=0, padx=8, pady=6,
                               state="disabled", height=10)
        self.table.grid(row=0, column=0, sticky="nsew")
        bar = ttk.Scrollbar(frame, orient="vertical",
                              command=self.table.yview)
        bar.grid(row=0, column=1, sticky="ns")
        self.table.configure(yscrollcommand=bar.set)
        self.table.tag_configure("intestazione", foreground=T.MUT)
        self.table.tag_configure("cosa", foreground=T.OK)

    def _pick(self, variable):
        path = filedialog.askopenfilename(
            parent=self, initialdir=os.path.dirname(variable.get()) or self.folder
            or None, filetypes=[("ROM", "*.rom *.bin *.fd"), ("*", "*.*")])
        if path:
            variable.set(path)

    # ------------------------------------------------------------ confronto
    def compare_images(self):
        a, b = self.var_a.get().strip(), self.var_b.get().strip()
        if not (a and b and os.path.isfile(a) and os.path.isfile(b)):
            return self._say(self.L("cmp_pick"), T.WARN)
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            data_a, data_b = A.read(a), A.read(b)
            if len(data_a) != len(data_b):
                return self._say(self.L("cmp_sizes",
                                          a=A.human_size(len(data_a)),
                                          b=A.human_size(len(data_b))), T.CRIT)
            self.total_size = len(data_a)
            self.result = A.compare_images(data_a, data_b)
            self.chip_map.set_size(total_size=self.total_size)
            self.chip_map.reset(M.VERIFIED)
            self.chip_map.mark_spans(self.result["allineati"], M.MISMATCH)
            self._fill(A.signatures(data_b))
        finally:
            self.configure(cursor="")

    def _say(self, text, colour=T.MUT):
        self.outcome_text.configure(text=text, foreground=colour)

    def _fill(self, signature_map):
        aligned = self.result["allineati"]
        exact = self.result["esatti"]
        if not aligned:
            self._say(self.L("cmp_identical"), T.OK)
            self.b_layout.state(["disabled"])
        else:
            key = "cmp_result_one" if len(aligned) == 1                 else "cmp_result"
            self._say(self.L(key, spans=len(aligned),
                               size=A.human_size(self.result["byte_diversi"])),
                        T.WARN)
            self.b_layout.state(["!disabled"])

        self.table.configure(state="normal")
        self.table.delete("1.0", "end")
        self.table.insert("end", "%-23s  %-23s  %10s  %s\n" % (
            self.L("cmp_col_span"), self.L("cmp_col_exact"),
            self.L("cmp_col_size"), self.L("cmp_col_what")), ("intestazione",))
        for index, (start, end) in enumerate(aligned):
            real_ones = exact[index] if index < len(exact) else (start, end)
            self.table.insert("end", "0x%06X-0x%06X  0x%06X-0x%06X  %10s  " % (
                start, end, real_ones[0], real_ones[1], A.human_size(end - start + 1)))
            self.table.insert(
                "end", (A.describe(start, end, signature_map,
                                   self.L.code) or "—") + "\n", ("cosa",))
        self.table.configure(state="disabled")

    # ---------------------------------------------------------------- layout
    def save_layout(self):
        if not self.result or not self.result["allineati"]:
            return
        path = filedialog.asksaveasfilename(
            parent=self, initialdir=self.folder or None,
            initialfile="layout-generato.txt", defaultextension=".txt")
        if not path:
            return
        text = A.make_layout(self.result["allineati"], self.total_size,
                                self.var_name.get().strip() or "modificata")
        with open(path, "wb") as f:
            f.write(text.encode("ascii"))
        self._say(self.L("cmp_saved", path=path), T.OK)


def open_window(parent, tm, L, folder=None):
    existing = getattr(parent, "_compare_window", None)
    if existing is not None and existing.winfo_exists():
        existing.deiconify()
        existing.lift()
        existing.focus_set()
        return existing
    window = CompareWindow(parent, tm, L, folder)
    parent._compare_window = window
    return window
