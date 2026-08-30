# -*- coding: utf-8 -*-
"""Il tema «quadro strumenti» di Polo Informatico, portato su tkinter.

Non e' una decorazione: e' un linguaggio visivo deciso e riusato. Console di
monitoraggio, non dashboard generica: filetti sottili, micro-etichette maiuscole
spaziate, numeri e registri a spaziatura fissa, e il colore forte speso in UN
punto solo.

The "instrument panel" dark theme, ported to tkinter.
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
ACCENT = "#2F9BE0"     # accento (blu Polo schiarito per il fondo scuro)
ACCENT2 = "#0070B0"    # blu Polo autentico

OK = "#35B87A"
WARN = "#E0A030"
CRIT = "#E5484D"

OK_BG, OK_BORDO = "#12241C", "#1E4D38"
WARN_BG, WARN_BORDO = "#241D10", "#4D3C1A"
CRIT_BG, CRIT_BORDO = "#251215", "#4F2225"

BARRA = "#0E161F"          # sidebar / trogolo
ATTIVO = "#16273A"
HEADER_DA, HEADER_A = "#0F2C42", INK    # gradiente 103deg

LOG_BG = "#080D13"
LOG_ORA = "#546B7E"
LOG_OK = "#63C08E"

BORDO_FINESTRA = "#1E2A36"

# colori dei fili nello schema: distinguibili anche sul fondo scuro
FILO = {
    "VCC": "#E5484D",
    "GND": "#7E93A4",
    "SCLK": "#E0A030",
    "MOSI": "#2F9BE0",
    "MISO": "#35B87A",
    "CS": "#B18AE0",
}


def titolo_scuro(finestra):
    """Barra del titolo scura, come il resto della finestra.

    Da Windows 10 1809 in poi si chiede al gestore delle finestre (DWM).
    L'attributo e' 20 sulle versioni recenti e 19 su quelle prima; se non
    funziona nulla, si resta con la barra chiara e pazienza.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        finestra.update_idletasks()
        handle = ctypes.windll.user32.GetParent(finestra.winfo_id())
        acceso = ctypes.c_int(1)
        for attributo in (20, 19):
            esito = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                handle, attributo, ctypes.byref(acceso), ctypes.sizeof(acceso))
            if esito == 0:
                return
    except Exception:                                  # noqa: BLE001
        pass


def micro(testo):
    """Micro-etichetta: MAIUSCOLA e spaziata.

    tkinter non conosce il letter-spacing, quindi lo si fa a mano con spazi
    sottili fra le lettere. Brutto da scrivere, giusto da vedere.
    """
    return " ".join(testo.upper())


def _prima_disponibile(radice, candidati, ripiego):
    presenti = set(tkfont.families(radice))
    for nome in candidati:
        if nome in presenti:
            return nome
    return ripiego


class Tema(object):
    """Tiene i caratteri scelti e applica gli stili ttk."""

    def __init__(self, radice):
        self.ui = _prima_disponibile(
            radice, ["Segoe UI Variable Text", "Segoe UI"], "TkDefaultFont")
        self.mono = _prima_disponibile(
            radice, ["Cascadia Code", "Cascadia Mono", "Consolas"], "Courier New")

        # Misure strette apposta: la finestra deve stare larga, non alta.
        self.f_titolo = (self.ui, 12, "bold")
        self.f_sotto = (self.ui, 8)
        self.f_testo = (self.ui, 8)
        self.f_micro = (self.ui, 7, "bold")
        self.f_minuto = (self.ui, 7)
        self.f_dato = (self.mono, 8)
        self.f_log = (self.mono, 8)
        self.f_bottone = (self.ui, 8)

        self._applica(radice)

    # -------------------------------------------------------------- ttk
    def _applica(self, radice):
        radice.configure(background=INK)
        s = ttk.Style(radice)
        # clam e' l'unico tema ttk che si lascia ricolorare davvero: vista e
        # xpnative disegnano con le immagini di Windows e ignorano background.
        s.theme_use("clam")

        s.configure(".", background=INK, foreground=FG, font=self.f_testo,
                    borderwidth=0, focuscolor=ACCENT)
        s.configure("TFrame", background=INK)
        s.configure("Scheda.TFrame", background=PANEL)
        s.configure("Sollevato.TFrame", background=PANEL2)

        s.configure("TLabel", background=INK, foreground=FG, font=self.f_testo)
        s.configure("Scheda.TLabel", background=PANEL, foreground=FG)
        s.configure("Micro.TLabel", background=PANEL, foreground=MUT,
                    font=self.f_micro)
        s.configure("MicroFondo.TLabel", background=INK, foreground=MUT,
                    font=self.f_micro)
        s.configure("Muto.TLabel", background=PANEL, foreground=MUT,
                    font=(self.ui, 8))
        s.configure("Titolo.TLabel", background=INK, foreground=FG,
                    font=self.f_titolo)
        s.configure("Sotto.TLabel", background=INK, foreground=MUT,
                    font=self.f_sotto)
        s.configure("Dato.TLabel", background=PANEL, foreground=FG,
                    font=self.f_dato)

        # --- pulsanti -------------------------------------------------
        self._bottone(s, "Primario.TButton", ACCENT2, "#FFFFFF", "#1B6E9F",
                      "#0A80C8", "#0C5F92")
        self._bottone(s, "Secondario.TButton", "#1D2937", FG, "#2A3846",
                      "#243244", "#18222E")
        self._bottone(s, "Ghost.TButton", PANEL, "#8FC2E3", "#2A4457",
                      "#17242F", "#111A23")
        self._bottone(s, "Pericolo.TButton", CRIT_BG, "#FF9C9F", CRIT_BORDO,
                      "#31171B", "#1E0F12")

        # --- campi ----------------------------------------------------
        for nome in ("TEntry", "TCombobox"):
            s.configure(nome, fieldbackground=BARRA, background=BARRA,
                        foreground=FG, bordercolor=LINE, lightcolor=LINE,
                        darkcolor=LINE, insertcolor=FG, arrowcolor=MUT,
                        selectbackground=ACCENT2, selectforeground="#FFFFFF",
                        padding=4)
            s.map(nome,
                  bordercolor=[("focus", ACCENT)],
                  lightcolor=[("focus", ACCENT)],
                  darkcolor=[("focus", ACCENT)],
                  fieldbackground=[("disabled", "#101922")],
                  foreground=[("disabled", "#4A5C6B")],
                  arrowcolor=[("disabled", "#3A4A58")])
        # la tendina della combobox e' un Listbox Tk classico, si veste a parte
        radice.option_add("*TCombobox*Listbox.background", PANEL2)
        radice.option_add("*TCombobox*Listbox.foreground", FG)
        radice.option_add("*TCombobox*Listbox.selectBackground", ACCENT2)
        radice.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
        radice.option_add("*TCombobox*Listbox.font", self.f_testo)

        # --- radio / spunte -------------------------------------------
        for nome, fondo in (("TRadiobutton", PANEL), ("Fondo.TRadiobutton", INK)):
            s.configure(nome, background=fondo, foreground=FG,
                        indicatorbackground=BARRA, indicatorforeground=ACCENT,
                        bordercolor=LINE, font=self.f_testo, padding=2)
            s.map(nome, background=[("active", fondo)],
                  indicatorbackground=[("selected", ACCENT),
                                       ("active", PANEL2)])

        # --- barra di avanzamento -------------------------------------
        s.configure("Sottile.Horizontal.TProgressbar", troughcolor=BARRA,
                    background=ACCENT, bordercolor=BARRA, lightcolor=ACCENT,
                    darkcolor=ACCENT2, thickness=5)

        # --- scrollbar -------------------------------------------------
        s.configure("Vertical.TScrollbar", background=PANEL2, troughcolor=INK,
                    bordercolor=INK, arrowcolor=MUT, gripcount=0)
        s.map("Vertical.TScrollbar", background=[("active", "#28394A")])
        s.configure("Horizontal.TScrollbar", background=PANEL2, troughcolor=INK,
                    bordercolor=INK, arrowcolor=MUT, gripcount=0)

        s.configure("TSeparator", background=LINE)

    @staticmethod
    def _bottone(s, nome, fondo, testo, bordo, sopra, premuto):
        s.configure(nome, background=fondo, foreground=testo,
                    bordercolor=bordo, lightcolor=fondo, darkcolor=fondo,
                    focusthickness=1, focuscolor=bordo,
                    padding=(11, 6), relief="flat")
        s.map(nome,
              background=[("pressed", premuto), ("active", sopra),
                          ("disabled", "#141C25")],
              foreground=[("disabled", "#43535F")],
              bordercolor=[("disabled", "#1B242E")],
              lightcolor=[("pressed", premuto), ("active", sopra)],
              darkcolor=[("pressed", premuto), ("active", sopra)])


# ------------------------------------------------------------- widget

def scheda(padre, titolo=None, tema=None):
    """Card: fondo --panel, filetto --line, intestazione in micro-etichetta.

    Restituisce (contenitore_esterno, corpo). Si mette la roba nel corpo.
    """
    fuori = tk.Frame(padre, background=PANEL, highlightbackground=LINE,
                     highlightcolor=LINE, highlightthickness=1, bd=0)
    corpo = tk.Frame(fuori, background=PANEL)
    if titolo is not None:
        testata = tk.Frame(fuori, background=PANEL)
        testata.pack(fill="x", padx=12, pady=(9, 0))
        etichetta = tk.Label(testata, text=micro(titolo), background=PANEL,
                             foreground=MUT, font=tema.f_micro if tema else None,
                             anchor="w")
        etichetta.pack(side="left")
        tk.Frame(fuori, background=LINE, height=1).pack(fill="x", padx=12,
                                                        pady=(7, 0))
        fuori.etichetta_titolo = etichetta
    corpo.pack(fill="both", expand=True, padx=12, pady=10)
    fuori.corpo = corpo
    return fuori, corpo


class Chip(tk.Frame):
    """Pillola di stato: puntino colorato + testo."""

    def __init__(self, padre, tema, fondo=PANEL):
        tk.Frame.__init__(self, padre, background=fondo)
        self.tema = tema
        self.fondo = fondo
        self.pillola = tk.Frame(self, background=fondo, highlightthickness=1,
                                highlightbackground=fondo, bd=0)
        self.punto = tk.Canvas(self.pillola, width=8, height=8, highlightthickness=0,
                               background=fondo, bd=0)
        self.punto.pack(side="left", padx=(8, 6), pady=4)
        self.testo = tk.Label(self.pillola, background=fondo, foreground=MUT,
                              font=tema.f_testo, anchor="w", justify="left",
                              wraplength=820)
        self.testo.pack(side="left", padx=(0, 10), pady=3)
        self.pillola.pack(anchor="w")
        self._id = None
        self.spegni()

    def spegni(self):
        self.pillola.pack_forget()

    def mostra(self, testo, colore=MUT, fondo=None, bordo=None):
        sfondo = fondo or self.fondo
        self.pillola.configure(background=sfondo,
                               highlightbackground=bordo or sfondo)
        self.punto.configure(background=sfondo)
        self.testo.configure(background=sfondo, foreground=colore, text=testo)
        self.punto.delete("all")
        self.punto.create_oval(1, 1, 7, 7, fill=colore, outline="")
        self.pillola.pack(anchor="w")


class Spunta(tk.Frame):
    """Casella disegnata a mano: 14px, angoli 3, spunta tracciata.

    Le ttk.Checkbutton su clam mostrano un quadratino di sistema che stona con
    il resto; questa e' la casella del design system, disegnata su Canvas.
    """

    LATO = 15

    def __init__(self, padre, tema, variabile, testo="", comando=None,
                 fondo=PANEL, colore=FG):
        tk.Frame.__init__(self, padre, background=fondo, cursor="hand2")
        self.var = variabile
        self.comando = comando
        self.colore = colore
        self.tela = tk.Canvas(self, width=self.LATO + 2, height=self.LATO + 2,
                              highlightthickness=0, background=fondo, bd=0)
        self.tela.pack(side="left")
        self.etichetta = tk.Label(self, text=testo, background=fondo,
                                  foreground=colore, font=tema.f_testo)
        self.etichetta.pack(side="left", padx=(8, 0))
        for widget in (self, self.tela, self.etichetta):
            widget.bind("<Button-1>", self._inverti)
        self.var.trace_add("write", lambda *_: self.ridisegna())
        self.ridisegna()

    def configure(self, cnf=None, **kw):
        """Accetta anche `testo=`, cosi' il traduttore la tratta come le altre."""
        testo = kw.pop("testo", None)
        if testo is not None:
            self.etichetta.configure(text=testo)
        if cnf or kw:
            return tk.Frame.configure(self, cnf, **kw)
        return None

    config = configure

    def _inverti(self, _evento=None):
        if str(self.etichetta.cget("state")) == "disabled":
            return
        self.var.set(0 if self.var.get() else 1)
        if self.comando:
            self.comando()

    def ridisegna(self):
        c = self.tela
        c.delete("all")
        acceso = bool(self.var.get())
        b, l = 1, self.LATO
        c.create_rectangle(b, b, b + l, b + l,
                           fill=ACCENT if acceso else BARRA,
                           outline=ACCENT if acceso else LINE, width=1)
        if acceso:
            # spunta tracciata a mano, non un carattere di font
            c.create_line(b + 3.5, b + 7.5, b + 6.2, b + 10.5, b + 11.5, b + 4.5,
                          fill="#08131C", width=2, capstyle="round",
                          joinstyle="round")


def gradiente(tela, larghezza, altezza, da=HEADER_DA, a=HEADER_A, gradi=103):
    """Il gradiente della testata, disegnato a strisce.

    tkinter non ha gradienti: si tracciano N linee interpolando il colore. A
    103 gradi la direzione e' quasi orizzontale, con una leggera inclinazione.
    """
    import math
    tela.delete("gradiente")
    da_r, da_g, da_b = tela.winfo_rgb(da)
    a_r, a_g, a_b = tela.winfo_rgb(a)
    radianti = math.radians(gradi - 90)
    scarto = math.tan(radianti) * altezza
    passi = max(int(larghezza + abs(scarto)), 2)
    for i in range(passi):
        t = i / float(passi - 1)
        colore = "#%02x%02x%02x" % (
            int((da_r + (a_r - da_r) * t)) >> 8,
            int((da_g + (a_g - da_g) * t)) >> 8,
            int((da_b + (a_b - da_b) * t)) >> 8)
        x = i - abs(scarto) * 0.5
        tela.create_line(x, 0, x + scarto, altezza, fill=colore,
                         tags="gradiente")
    tela.tag_lower("gradiente")
