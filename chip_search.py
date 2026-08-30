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


class Ricerca(tk.Toplevel):
    """The search window. Whoever opens it passes what to do with the pick."""

    def __init__(self, padre, tm, L, chip, al_scegliere, iniziale=""):
        tk.Toplevel.__init__(self, padre, background=T.INK)
        self.tema = tm
        self.L = L
        self.al_scegliere = al_scegliere
        self.tutti = [c for c in chip if c.spi]
        self.mostrati = []
        self.title(L("cerca_titolo"))
        self.geometry("760x520")
        self.minsize(520, 360)
        self.transient(padre)
        T.titolo_scuro(self)

        self._stile()
        cornice = tk.Frame(self, background=T.INK)
        cornice.pack(fill="both", expand=True, padx=12, pady=12)
        cornice.columnconfigure(0, weight=1)
        cornice.rowconfigure(2, weight=1)

        testa = tk.Frame(cornice, background=T.INK)
        testa.grid(row=0, column=0, sticky="ew")
        tk.Label(testa, text=L("cerca_titolo"), background=T.INK,
                 foreground=T.FG, font=tm.f_titolo).pack(side="left")
        self.var_conteggio = tk.StringVar()
        tk.Label(testa, textvariable=self.var_conteggio, background=T.INK,
                 foreground=T.MUT, font=tm.f_testo).pack(side="right")

        riga = tk.Frame(cornice, background=T.INK)
        riga.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        riga.columnconfigure(1, weight=1)
        tk.Label(riga, text=T.micro(L("cerca_campo")), background=T.INK,
                 foreground=T.MUT, font=tm.f_micro).grid(row=0, column=0,
                                                         sticky="w")
        self.var_cerca = tk.StringVar(value=iniziale)
        self.campo = ttk.Entry(riga, textvariable=self.var_cerca,
                               font=tm.f_testo)
        self.campo.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.var_cerca.trace_add("write", lambda *_a: self._filtra())

        tabella = tk.Frame(cornice, background=T.INK)
        tabella.grid(row=2, column=0, sticky="nsew")
        tabella.columnconfigure(0, weight=1)
        tabella.rowconfigure(0, weight=1)
        colonne = ("produttore", "modello", "misura", "volt", "prove")
        self.lista = ttk.Treeview(tabella, columns=colonne, show="headings",
                                  style="Cerca.Treeview", selectmode="browse")
        for chiave, larghezza, ancora in (("produttore", 120, "w"),
                                          ("modello", 290, "w"),
                                          ("misura", 80, "e"),
                                          ("volt", 70, "e"),
                                          ("prove", 70, "center")):
            # ⚠️ the heading lines up like its column: centred over a wide
            # column it looked like it belonged to the one next to it
            self.lista.heading(chiave, text=T.micro(L("cerca_col_" + chiave)),
                               anchor=ancora)
            self.lista.column(chiave, width=larghezza, anchor=ancora,
                              stretch=(chiave == "modello"))
        self.lista.grid(row=0, column=0, sticky="nsew")
        barra = ttk.Scrollbar(tabella, orient="vertical",
                              command=self.lista.yview)
        barra.grid(row=0, column=1, sticky="ns")
        self.lista.configure(yscrollcommand=barra.set)
        # ⚠️ i chip a 1,8 V si vedono a colpo d'occhio: e' l'errore che costa
        # un chip, non un messaggio
        self.lista.tag_configure("bassa", foreground="#F0A93B")
        self.lista.tag_configure("ignota", foreground=T.MUT)

        self.lista.bind("<Double-Button-1>", lambda _e: self.scegli())
        self.lista.bind("<Return>", lambda _e: self.scegli())
        self.campo.bind("<Return>", lambda _e: self._primo_e_scegli())
        self.campo.bind("<Down>", lambda _e: self._al_primo())
        self.bind("<Escape>", lambda _e: self.destroy())

        piede = tk.Frame(cornice, background=T.INK)
        piede.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        tk.Label(piede, text=L("cerca_nota"), background=T.INK,
                 foreground="#6E8296", font=tm.f_micro,
                 wraplength=430, justify="left").pack(side="left")
        ttk.Button(piede, text=L("cerca_annulla"), style="Ghost.TButton",
                   command=self.destroy).pack(side="right")
        self.b_scegli = ttk.Button(piede, text=L("cerca_scegli"),
                                   style="Primario.TButton", command=self.scegli)
        self.b_scegli.pack(side="right", padx=(0, 8))

        self._filtra()
        self.campo.focus_set()

    # --------------------------------------------------------------- stile
    def _stile(self):
        s = ttk.Style(self)
        s.configure("Cerca.Treeview", background=T.PANEL, fieldbackground=T.PANEL,
                    foreground=T.FG, bordercolor=T.LINE, borderwidth=0,
                    rowheight=max(20, self.tema.f_testo[1] * 2),
                    font=self.tema.f_testo)
        s.configure("Cerca.Treeview.Heading", background=T.BARRA,
                    foreground=T.MUT, relief="flat", font=self.tema.f_micro)
        s.map("Cerca.Treeview.Heading", background=[("active", T.PANEL2)])
        s.map("Cerca.Treeview", background=[("selected", T.ACCENT2)],
              foreground=[("selected", "#FFFFFF")])

    # ------------------------------------------------------------- filtro
    def _filtra(self):
        # every word must appear: "win 128" finds the 128 Mbit Winbonds
        parole = [p for p in self.var_cerca.get().lower().split() if p]
        self.lista.delete(*self.lista.get_children())
        self.mostrati = []
        for chip in self.tutti:
            testo = ("%s %s" % (chip.produttore, chip.nome)).lower()
            if all(p in testo for p in parole):
                self.mostrati.append(chip)
        for indice, chip in enumerate(self.mostrati[:600]):
            volt, _famiglia = V.tensione(chip.nome)
            etichetta = ("bassa" if volt == V.BASSA
                         else ("" if volt else "ignota"))
            self.lista.insert(
                "", "end", iid=str(indice),
                values=(chip.produttore, chip.nome, _misura(chip.kb),
                        _volt(volt, self.L.codice), chip.prove or "—"),
                tags=(etichetta,) if etichetta else ())
        self.var_conteggio.set(self.L("cerca_conteggio",
                                      quanti=len(self.mostrati),
                                      totale=len(self.tutti)))

    def _al_primo(self):
        figli = self.lista.get_children()
        if figli:
            self.lista.selection_set(figli[0])
            self.lista.focus(figli[0])
            self.lista.focus_set()

    def _primo_e_scegli(self):
        if not self.lista.selection():
            self._al_primo()
        self.scegli()

    # ------------------------------------------------------------- scelta
    def scegli(self):
        selezione = self.lista.selection()
        if not selezione:
            return
        indice = int(selezione[0])
        if indice >= len(self.mostrati):
            return
        chip = self.mostrati[indice]
        self.al_scegliere(chip)
        self.destroy()


def _volt(volt, lingua="it"):
    """1,8 V in italiano, 1.8 V in inglese: il separatore decimale cambia."""
    if volt is None:
        return "?"
    testo = "%.1f V" % volt
    return testo.replace(".", ",") if lingua == "it" else testo


def _misura(kb):
    if not kb:
        return "?"
    if kb >= 1024:
        return "%g MiB" % (kb / 1024.0)
    return "%d KiB" % kb


def apri(padre, tm, L, chip, al_scegliere, iniziale=""):
    """Opens the search, or brings the open one back to the front."""
    esistente = getattr(padre, "_finestra_ricerca", None)
    if esistente is not None and esistente.winfo_exists():
        esistente.deiconify()
        esistente.lift()
        esistente.focus_set()
        return esistente
    finestra = Ricerca(padre, tm, L, chip, al_scegliere, iniziale)
    padre._finestra_ricerca = finestra
    return finestra
