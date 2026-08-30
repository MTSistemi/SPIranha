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


class Confronto(tk.Toplevel):

    def __init__(self, padre, tm, L, cartella=None):
        tk.Toplevel.__init__(self, padre, background=T.INK)
        self.tema = tm
        self.L = L
        self.cartella = cartella or ""
        self.esito = None
        self.dimensione = 0
        self.title(L("conf_titolo"))
        self.geometry("980x620")
        self.minsize(680, 460)

        self.var_a = tk.StringVar()
        self.var_b = tk.StringVar()
        self.var_nome = tk.StringVar(value="modificata")
        self._costruisci()
        self.bind("<Escape>", lambda _e: self.destroy())
        T.titolo_scuro(self)

    # ---------------------------------------------------------- costruzione
    def _costruisci(self):
        radice = tk.Frame(self, background=T.INK)
        radice.pack(fill="both", expand=True, padx=10, pady=10)
        radice.columnconfigure(0, weight=1)
        radice.rowconfigure(2, weight=1)

        testata = tk.Frame(radice, background=T.INK)
        testata.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tk.Label(testata, text=self.L("conf_titolo"), background=T.INK,
                 foreground=T.FG, font=self.tema.f_titolo).pack(anchor="w")
        tk.Label(testata, text=self.L("conf_sotto"), background=T.INK,
                 foreground=T.MUT, font=self.tema.f_sotto).pack(anchor="w")

        scelta, s = T.scheda(radice, self.L("conf_sez_file"), self.tema)
        scelta.grid(row=1, column=0, sticky="ew")
        s.columnconfigure(1, weight=1)
        for riga, (chiave, var) in enumerate(((self.L("conf_a"), self.var_a),
                                              (self.L("conf_b"), self.var_b))):
            tk.Label(s, text=T.micro(chiave), background=T.PANEL,
                     foreground=T.MUT, font=self.tema.f_micro).grid(
                row=riga, column=0, sticky="w", pady=(0 if not riga else 6, 0))
            ttk.Entry(s, textvariable=var, font=self.tema.f_testo).grid(
                row=riga, column=1, sticky="ew", padx=(6, 4),
                pady=(0 if not riga else 6, 0))
            ttk.Button(s, text=self.L("sfoglia"), width=3,
                       style="Secondario.TButton",
                       command=lambda v=var: self._scegli(v)).grid(
                row=riga, column=2, pady=(0 if not riga else 6, 0))

        azioni = tk.Frame(s, background=T.PANEL)
        azioni.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Button(azioni, text=self.L("conf_esegui"), style="Primario.TButton",
                   command=self.confronta).pack(side="left")
        tk.Label(azioni, text=T.micro(self.L("conf_nome")), background=T.PANEL,
                 foreground=T.MUT, font=self.tema.f_micro).pack(side="left",
                                                                padx=(16, 6))
        ttk.Entry(azioni, textvariable=self.var_nome, width=16,
                  font=self.tema.f_testo).pack(side="left")
        self.b_layout = ttk.Button(azioni, text=self.L("conf_salva_layout"),
                                   style="Secondario.TButton",
                                   command=self.salva_layout)
        self.b_layout.pack(side="left", padx=8)
        self.b_layout.state(["disabled"])

        self.esito_testo = tk.Label(s, background=T.PANEL, foreground=T.MUT,
                                    font=self.tema.f_testo, anchor="w")
        self.esito_testo.grid(row=3, column=0, columnspan=3, sticky="w",
                              pady=(8, 0))

        risultati, r = T.scheda(radice, self.L("conf_sez_esito"), self.tema)
        risultati.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        r.columnconfigure(0, weight=1)
        r.rowconfigure(1, weight=1)

        self.mappa = M.Mappa(r, righe=6)
        self.mappa.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        cornice = tk.Frame(r, background=T.LOG_BG, highlightthickness=1,
                           highlightbackground=T.LINE)
        cornice.grid(row=1, column=0, sticky="nsew")
        cornice.columnconfigure(0, weight=1)
        cornice.rowconfigure(0, weight=1)
        self.tabella = tk.Text(cornice, wrap="none", font=self.tema.f_log,
                               background=T.LOG_BG, foreground="#C3D2DE",
                               relief="flat", bd=0, padx=8, pady=6,
                               state="disabled", height=10)
        self.tabella.grid(row=0, column=0, sticky="nsew")
        barra = ttk.Scrollbar(cornice, orient="vertical",
                              command=self.tabella.yview)
        barra.grid(row=0, column=1, sticky="ns")
        self.tabella.configure(yscrollcommand=barra.set)
        self.tabella.tag_configure("intestazione", foreground=T.MUT)
        self.tabella.tag_configure("cosa", foreground=T.OK)

    def _scegli(self, var):
        percorso = filedialog.askopenfilename(
            parent=self, initialdir=os.path.dirname(var.get()) or self.cartella
            or None, filetypes=[("ROM", "*.rom *.bin *.fd"), ("*", "*.*")])
        if percorso:
            var.set(percorso)

    # ------------------------------------------------------------ confronto
    def confronta(self):
        a, b = self.var_a.get().strip(), self.var_b.get().strip()
        if not (a and b and os.path.isfile(a) and os.path.isfile(b)):
            return self._dillo(self.L("conf_scegli"), T.WARN)
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            dati_a, dati_b = A.leggi(a), A.leggi(b)
            if len(dati_a) != len(dati_b):
                return self._dillo(self.L("conf_dimensioni",
                                          a=A.leggibile(len(dati_a)),
                                          b=A.leggibile(len(dati_b))), T.CRIT)
            self.dimensione = len(dati_a)
            self.esito = A.confronta(dati_a, dati_b)
            self.mappa.imposta(dimensione=self.dimensione)
            self.mappa.azzera(M.VERIFICATO)
            self.mappa.segna_intervalli(self.esito["allineati"], M.DIVERSO)
            self._riempi(A.firme(dati_b))
        finally:
            self.configure(cursor="")

    def _dillo(self, testo, colore=T.MUT):
        self.esito_testo.configure(text=testo, foreground=colore)

    def _riempi(self, mappa_firme):
        allineati = self.esito["allineati"]
        esatti = self.esito["esatti"]
        if not allineati:
            self._dillo(self.L("conf_uguali"), T.OK)
            self.b_layout.state(["disabled"])
        else:
            chiave = "conf_risultato_uno" if len(allineati) == 1                 else "conf_risultato"
            self._dillo(self.L(chiave, intervalli=len(allineati),
                               byte=A.leggibile(self.esito["byte_diversi"])),
                        T.WARN)
            self.b_layout.state(["!disabled"])

        self.tabella.configure(state="normal")
        self.tabella.delete("1.0", "end")
        self.tabella.insert("end", "%-23s  %-23s  %10s  %s\n" % (
            self.L("conf_col_intervallo"), self.L("conf_col_esatto"),
            self.L("conf_col_dim"), self.L("conf_col_cosa")), ("intestazione",))
        for indice, (inizio, fine) in enumerate(allineati):
            veri = esatti[indice] if indice < len(esatti) else (inizio, fine)
            self.tabella.insert("end", "0x%06X-0x%06X  0x%06X-0x%06X  %10s  " % (
                inizio, fine, veri[0], veri[1], A.leggibile(fine - inizio + 1)))
            self.tabella.insert(
                "end", (A.descrivi(inizio, fine, mappa_firme,
                                   self.L.codice) or "—") + "\n", ("cosa",))
        self.tabella.configure(state="disabled")

    # ---------------------------------------------------------------- layout
    def salva_layout(self):
        if not self.esito or not self.esito["allineati"]:
            return
        percorso = filedialog.asksaveasfilename(
            parent=self, initialdir=self.cartella or None,
            initialfile="layout-generato.txt", defaultextension=".txt")
        if not percorso:
            return
        testo = A.genera_layout(self.esito["allineati"], self.dimensione,
                                self.var_nome.get().strip() or "modificata")
        with open(percorso, "wb") as f:
            f.write(testo.encode("ascii"))
        self._dillo(self.L("conf_salvato", percorso=percorso), T.OK)


def apri(padre, tm, L, cartella=None):
    esistente = getattr(padre, "_finestra_confronto", None)
    if esistente is not None and esistente.winfo_exists():
        esistente.deiconify()
        esistente.lift()
        esistente.focus_set()
        return esistente
    finestra = Confronto(padre, tm, L, cartella)
    padre._finestra_confronto = finestra
    return finestra
