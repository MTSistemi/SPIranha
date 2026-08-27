# -*- coding: utf-8 -*-
"""L'interfaccia: la procedura in quattro passi, con i controlli obbligatori.

L'idea di fondo: quando serve questo programma la scheda e' gia' morta e si ha
fretta. Le cose che oggi bisogna ricordarsi a mente — leggere due volte e
confrontare, tenere la BC-250 staccata, rileggere prima di riattaccare — qui le
impone il programma, e il tasto di scrittura resta spento finche' non tornano.

Il codice che tocca il chip e' flashrom: qui si costruiscono i comandi e si
guardano gli esiti. La veste e' il tema «quadro strumenti» (vedi tema.py).
"""
from __future__ import unicode_literals

import hashlib
import json
import os
import queue
import sys
import threading
import time
import traceback
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import analisi as A
import anagrafica
import confronto
import flashrom as fr
import mappa as M
import pico
import schema
import serprog
import tema as T
from i18n import LINGUE, NOMI_LINGUA, Lingua

APPNOME = "SPIranha"
BAUD = 115200
BLOCCO = 1024 * 1024

# Le impronte che conosciamo di questa scheda (vedi bios-backup/LEGGIMI.md).
MD5_NOTI = {
    "3487f648a69a781d2609a8d4e6f4808e": "md5_stock",
    "f7632f2ff61a7a5e65fff74d09942aeb": "md5_atteso",
}

VELOCITA = ["", "8M", "4M", "2M", "1M", "500k"]
VELOCITA_ETICHETTE = {
    "": "12 MHz (firmware)",
    "8M": "8 MHz", "4M": "4 MHz", "2M": "2 MHz",
    "1M": "1 MHz", "500k": "500 kHz",
}

CHIP_SUGGERITI = ["", "MX25L12835F/MX25L12873F", "MX25L12805D", "W25Q128.V"]

# Quanto si legge per qualificare il collegamento: abbastanza da accorgersi di
# un cavo incerto, poco abbastanza da poterlo rifare a ogni velocita'.
PROVA_QUALIFICA = 256 * 1024

# I quattro stati di un messaggio, nei colori del tema.
VERDE = T.OK
ROSSO = T.CRIT
AMBRA = T.WARN
GRIGIO = T.MUT
FONDI = {
    T.OK: (T.OK_BG, T.OK_BORDO),
    T.CRIT: (T.CRIT_BG, T.CRIT_BORDO),
    T.WARN: (T.WARN_BG, T.WARN_BORDO),
}


# ---------------------------------------------------------------- utilita'

def cartella_app():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def cartella_config():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APPNOME)


def cartella_predefinita():
    documenti = os.path.join(os.path.expanduser("~"), "Documents")
    for candidata in (
        os.path.join(documenti, "Claude", "SkillFishOS", "bios-backup"),
        os.path.join(documenti, "bios-backup"),
    ):
        if os.path.isdir(candidata):
            return candidata
    return documenti


def md5_file(percorso, fermati=None):
    h = hashlib.md5()
    with open(percorso, "rb") as f:
        while True:
            pezzo = f.read(BLOCCO)
            if not pezzo:
                break
            h.update(pezzo)
            if fermati is not None and fermati.is_set():
                return None
    return h.hexdigest()


def marca_ora():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _durata(secondi):
    """Un tempo che resta alla fine, detto corto."""
    secondi = int(max(0, secondi))
    if secondi < 60:
        return "%ds" % secondi
    if secondi < 3600:
        return "%dm %02ds" % (secondi // 60, secondi % 60)
    return "%dh %02dm" % (secondi // 3600, (secondi % 3600) // 60)


def md5_dati(dati):
    return hashlib.md5(dati).hexdigest()


# ---------------------------------------------------------------- finestra

class App(tk.Tk):

    def __init__(self):
        tk.Tk.__init__(self)
        self.conf = self._carica_config()
        self.L = Lingua(self.conf.get("lingua", "it"))

        self.coda = queue.Queue()
        self.occupato = False
        self.operazione_scrittura = False
        self.fermati = threading.Event()

        # stato della procedura: ogni requisito e' una condizione per scrivere
        self.chip = None                 # fr.Chip identificato
        self.protezione = None           # fr.Protezione, letta col chip
        self.fw_scheda = None            # versione dichiarata dal programmatore
        self.fw_chiesto = set()          # seriali a cui l'abbiamo gia' chiesta
        self.lettura_verificata = None   # md5 dell'ultima lettura doppia riuscita
        self.righe_registro = []
        self.regioni = []                # (nome, inizio, fine) dal file di layout
        self.versione_flashrom = ""
        self.lettura_file = None         # file dell'ultima lettura verificata
        self.secco = None                # esito della prova a secco
        self.secco_firma = None
        self.fase = None                 # fase in corso, per mappa e avanzamento
        self.inizio_fase = None
        self.intervallo_scritto = None
        self.intervallo_lettura = (0, 16 * 1024 * 1024 - 1)
        self.schede_note = anagrafica.Anagrafica(self.conf.get("schede"))
        self.scheda_bootsel = None       # RP2040 in attesa di firmware
        self.attesa_bootsel = None

        self.flash = None
        percorso = self.conf.get("flashrom")
        if not (percorso and os.path.isfile(percorso)):
            # nell'eseguibile unico flashrom viaggia dentro: _MEIPASS e' la
            # cartella dove PyInstaller lo scompatta all'avvio
            percorso = fr.trova_eseguibile(
                cartella_app(), extra=[getattr(sys, "_MEIPASS", None)])
        if percorso:
            self._imposta_flashrom(percorso, silenzioso=True)

        self._etichette = []             # (widget, chiave, attributo, trasforma)
        self._messaggi = []              # Messaggio da ridisegnare al cambio lingua

        self.tema = T.Tema(self)
        self._costruisci()
        self._traduci()
        self.rileva_porte()
        T.titolo_scuro(self)
        self.after(60, self._pompa)
        self.after(400, self._guarda_bootsel)
        self.protocol("WM_DELETE_WINDOW", self._chiudi)

    # ------------------------------------------------------------ config
    def _carica_config(self):
        try:
            with open(os.path.join(cartella_config(), "config.json"), "rb") as f:
                return json.loads(f.read().decode("utf-8"))
        except (OSError, ValueError):
            return {}

    def _salva_config(self):
        self.conf.update({
            "lingua": self.L.codice,
            "flashrom": self.flash.percorso if self.flash else None,
            "porta": self.var_porta.get(),
            "spispeed": self.var_velocita.get(),
            "cartella": self.var_cartella.get(),
            "chip": self.var_chip.get(),
            "immagine": self.var_immagine.get(),
            "layout": self.var_layout.get(),
            "atteso": self.var_atteso.get(),
            "dettagli": bool(self.var_dettagli.get()),
            "schede": self.schede_note.come_elenco(),
        })
        try:
            os.makedirs(cartella_config(), exist_ok=True)
            with open(os.path.join(cartella_config(), "config.json"), "wb") as f:
                f.write(json.dumps(self.conf, indent=2).encode("utf-8"))
        except OSError:
            pass

    # ------------------------------------------------- costruzione grafica
    def _etichetta(self, widget, chiave, attributo="text", trasforma=None):
        """Registra un widget perche' si riscriva al cambio lingua."""
        self._etichette.append((widget, chiave, attributo, trasforma))
        return widget

    def _traduci(self):
        self.title(self.L("titolo"))
        for widget, chiave, attributo, trasforma in self._etichette:
            testo = self.L(chiave)
            if trasforma:
                testo = trasforma(testo)
            try:
                widget.configure(**{attributo: testo})
            except tk.TclError:
                pass
        for messaggio in self._messaggi:
            messaggio.ridisegna()
        self.var_velocita_etichetta.set(VELOCITA_ETICHETTE.get(self.var_velocita.get(), ""))
        if hasattr(self, "legenda"):
            self.legenda.traduci()
            self._riposo_mappa()
        # ⚠️ Va chiamata anche all'avvio: _guarda_bootsel aggiorna solo quando
        # lo stato CAMBIA, e all'inizio "nessuna scheda" non e' un cambiamento.
        if hasattr(self, "msg_firmware"):
            self._aggiorna_firmware()
        self._disegna_testata()
        self._aggiorna_stato_flashrom()
        self._aggiorna_scrittura()
        finestra = getattr(self, "_finestra_schema", None)
        if finestra is not None and finestra.winfo_exists():
            finestra.title(self.L("sch_titolo"))
            finestra.disegna()

    SOGLIA_DUE_COLONNE = 940      # sotto questa larghezza si impila tutto

    def _costruisci(self):
        self.geometry("1040x876")
        self.minsize(620, 540)

        self.radice = tk.Frame(self, background=T.INK)
        self.radice.pack(fill="both", expand=True)

        self._costruisci_testata(self.radice)
        self._costruisci_banner(self.radice)
        self.schede = [
            self._crea_collegamento(self.radice),
            self._crea_chip(self.radice),
            self._crea_lettura(self.radice),
            self._crea_scrittura(self.radice),
        ]
        self.scheda_mappa = self._crea_mappa(self.radice)
        self.scheda_registro = self._crea_registro(self.radice)
        self._costruisci_barra(self.radice)

        self._colonne = None
        self._riflusso(due=True)
        self._attesa_riflusso = None
        self.bind("<Configure>", self._forse_riflusso)

    # -- responsive: una o due colonne secondo lo spazio --------------------
    def _forse_riflusso(self, evento):
        if evento.widget is not self:
            return
        if self._attesa_riflusso:
            self.after_cancel(self._attesa_riflusso)
        self._attesa_riflusso = self.after(
            90, lambda: self._riflusso(due=self.winfo_width() >= self.SOGLIA_DUE_COLONNE))

    def _riflusso(self, due):
        self._attesa_riflusso = None
        if due == self._colonne:
            self._adatta_larghezze()
            return
        self._colonne = due
        r = self.radice
        for scheda in self.schede:
            scheda.grid_forget()
        self.scheda_mappa.grid_forget()
        self.scheda_registro.grid_forget()
        self.barra.grid_forget()

        for indice in (0, 1):
            r.columnconfigure(indice, weight=1 if (due or indice == 0) else 0,
                              uniform="colonne" if due else "")
        for indice in range(3, 12):
            r.rowconfigure(indice, weight=0)

        pad = dict(padx=8, pady=(8, 0))
        if due:
            self.schede[0].grid(row=3, column=0, sticky="new", **pad)
            self.schede[1].grid(row=4, column=0, sticky="new", **pad)
            self.schede[2].grid(row=5, column=0, sticky="new", **pad)
            self.schede[3].grid(row=3, column=1, rowspan=3, sticky="new", **pad)
            riga_mappa = 6
        else:
            for indice, scheda in enumerate(self.schede):
                scheda.grid(row=3 + indice, column=0, columnspan=2, sticky="new",
                            **pad)
            riga_mappa = 7
        self.scheda_mappa.grid(row=riga_mappa, column=0, columnspan=2,
                               sticky="ew", padx=8, pady=(8, 0))
        riga_registro = riga_mappa + 1
        self.scheda_registro.grid(row=riga_registro, column=0, columnspan=2,
                                  sticky="nsew", padx=8, pady=(8, 0))
        r.rowconfigure(riga_registro, weight=1)
        self.barra.grid(row=riga_registro + 1, column=0, columnspan=2, sticky="ew",
                        padx=10, pady=(6, 8))
        self._adatta_larghezze()

    def _adatta_larghezze(self):
        """Le scritte lunghe si adattano alla colonna invece di allargare tutto."""
        larghezza = max(self.winfo_width(), 400)
        colonna = (larghezza - 32) // (2 if self._colonne else 1)
        for messaggio in self._messaggi:
            messaggio.chip.testo.configure(wraplength=max(colonna - 70, 180))
        for widget, avvolgi in getattr(self, "_avvolgibili", ()):
            widget.configure(wraplength=max(int(colonna * avvolgi), 150))

    # -- testata -----------------------------------------------------------
    def _costruisci_testata(self, padre):
        self.tela_testata = tk.Canvas(padre, height=54, background=T.HEADER_DA,
                                      highlightthickness=0, bd=0)
        self.tela_testata.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.tela_testata.bind("<Configure>", lambda _e: self._disegna_testata())

        cornice = tk.Frame(self.tela_testata, background=T.INK)
        self.var_lingua = tk.StringVar(value=NOMI_LINGUA[self.L.codice])
        scelta = ttk.Combobox(cornice, textvariable=self.var_lingua, width=9,
                              state="readonly", font=self.tema.f_testo,
                              values=[NOMI_LINGUA[c] for c in LINGUE])
        scelta.pack(side="left")
        scelta.bind("<<ComboboxSelected>>", self._cambia_lingua)
        self.tela_testata.create_window(0, 0, window=cornice, anchor="ne",
                                        tags="lingua")
        self.tela_testata.bind("<Configure>", lambda _e: self._disegna_testata())

        # promemoria: la regola che non cambia mai
        pro = tk.Frame(padre, background=T.WARN_BG, highlightthickness=1,
                       highlightbackground=T.WARN_BORDO, bd=0)
        pro.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 0))
        punto = tk.Canvas(pro, width=8, height=8, background=T.WARN_BG,
                          highlightthickness=0)
        punto.create_oval(0, 0, 8, 8, fill=T.WARN, outline="")
        punto.pack(side="left", padx=(9, 7), pady=6)
        etichetta = tk.Label(pro, background=T.WARN_BG, foreground="#E8D6B4",
                             anchor="w", justify="left", wraplength=900,
                             font=self.tema.f_testo)
        etichetta.pack(side="left", pady=5, padx=(0, 10))
        self._etichetta(etichetta, "promemoria")
        self._avvolgibili = [(etichetta, 1.9)]

    def _disegna_testata(self):
        tela = self.tela_testata
        larghezza = max(tela.winfo_width(), 320)
        tela.delete("scritte")
        T.gradiente(tela, larghezza, 54)
        tela.create_text(18, 18, text=self.L("titolo"), fill=T.FG, anchor="w",
                         font=self.tema.f_titolo, tags="scritte")
        tela.create_text(19, 38, text=self.L("sottotitolo"), fill=T.MUT,
                         anchor="w", font=self.tema.f_sotto, tags="scritte")
        tela.create_line(0, 53, larghezza, 53, fill=T.LINE, tags="scritte")
        tela.coords("lingua", larghezza - 12, 14)

    # -- banner flashrom ---------------------------------------------------
    def _costruisci_banner(self, padre):
        self.banner = tk.Frame(padre, background=T.CRIT_BG, highlightthickness=1,
                               highlightbackground=T.CRIT_BORDO, bd=0)
        punto = tk.Canvas(self.banner, width=8, height=8, background=T.CRIT_BG,
                          highlightthickness=0)
        punto.create_oval(0, 0, 8, 8, fill=T.CRIT, outline="")
        punto.pack(side="left", padx=(9, 7), pady=6)
        self.banner_testo = tk.Label(self.banner, background=T.CRIT_BG,
                                     foreground="#F0C9CB", anchor="w",
                                     justify="left", wraplength=700,
                                     font=self.tema.f_testo)
        self.banner_testo.pack(side="left", fill="x", expand=True, pady=5)
        self._etichetta(self.banner_testo, "flashrom_assente")
        self.banner_bottone = ttk.Button(self.banner, style="Pericolo.TButton",
                                         command=self.scegli_flashrom)
        self.banner_bottone.pack(side="right", padx=7, pady=5)
        self._etichetta(self.banner_bottone, "flashrom_individua")
        self.banner.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8,
                         pady=(8, 0))

    def _scheda(self, padre, chiave):
        scheda, corpo = T.scheda(padre, self.L(chiave), self.tema)
        self._etichetta(scheda.etichetta_titolo, chiave, trasforma=T.micro)
        return scheda, corpo

    def _micro(self, padre, chiave):
        return self._etichetta(
            tk.Label(padre, background=T.PANEL, foreground=T.MUT,
                     font=self.tema.f_micro, anchor="w"),
            chiave, trasforma=T.micro)

    def _nota(self, padre, chiave, avvolgi=0.9):
        etichetta = tk.Label(padre, background=T.PANEL, foreground=T.MUT,
                             font=self.tema.f_minuto, anchor="w", justify="left",
                             wraplength=320)
        self._etichetta(etichetta, chiave)
        self._avvolgibili.append((etichetta, avvolgi))
        return etichetta

    def _sfoglia(self, padre, comando):
        return self._etichetta(ttk.Button(padre, style="Secondario.TButton",
                                          width=3, command=comando), "sfoglia")

    # -- 1. collegamento ---------------------------------------------------
    def _crea_collegamento(self, padre):
        scheda, s = self._scheda(padre, "sez_collegamento")
        s.columnconfigure(1, weight=1)

        self._micro(s, "porta").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.var_porta = tk.StringVar(value=self.conf.get("porta", ""))
        self.combo_porta = ttk.Combobox(s, textvariable=self.var_porta,
                                        font=self.tema.f_testo)
        self.combo_porta.grid(row=0, column=1, sticky="ew", padx=(6, 6), pady=(0, 4))

        bottoni = tk.Frame(s, background=T.PANEL)
        bottoni.grid(row=0, column=2, sticky="e", pady=(0, 4))
        self._etichetta(ttk.Button(bottoni, style="Secondario.TButton",
                                   command=self.rileva_porte),
                        "rileva").pack(side="left", padx=(0, 4))
        self.b_prova = self._etichetta(
            ttk.Button(bottoni, style="Secondario.TButton",
                       command=self.interroga_pico), "prova")
        self.b_prova.pack(side="left", padx=(0, 4))
        self.b_schema = self._etichetta(
            ttk.Button(bottoni, style="Ghost.TButton", command=self.apri_schema),
            "sch_apri")
        self.b_schema.pack(side="left")

        self._micro(s, "velocita").grid(row=1, column=0, sticky="w")
        cornice_v = tk.Frame(s, background=T.PANEL)
        cornice_v.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(6, 0))
        self.var_velocita = tk.StringVar(value=self.conf.get("spispeed", ""))
        self.var_velocita_etichetta = tk.StringVar()
        combo_v = ttk.Combobox(cornice_v, width=15, state="readonly",
                               font=self.tema.f_testo,
                               textvariable=self.var_velocita_etichetta,
                               values=[VELOCITA_ETICHETTE[v] for v in VELOCITA])
        combo_v.pack(side="left")
        combo_v.bind("<<ComboboxSelected>>", self._cambia_velocita)
        self.b_qualifica = self._etichetta(
            ttk.Button(cornice_v, style="Secondario.TButton",
                       command=self.qualifica_collegamento), "qualifica")
        self.b_qualifica.pack(side="left", padx=(6, 0))
        self._nota(cornice_v, "qualifica_nota", 0.5).pack(side="left", padx=8)

        # --- firmware del programmatore
        filetto = tk.Frame(s, background=T.LINE, height=1)
        filetto.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 8))

        self._micro(s, "firmware").grid(row=3, column=0, sticky="w")
        cornice_f = tk.Frame(s, background=T.PANEL)
        cornice_f.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(6, 0))
        self.b_firmware = self._etichetta(
            ttk.Button(cornice_f, style="Secondario.TButton",
                       command=self.installa_firmware), "fw_installa")
        self.b_firmware.pack(side="left")
        self.b_azzera = self._etichetta(
            ttk.Button(cornice_f, style="Ghost.TButton",
                       command=self.azzera_scheda), "fw_azzera")
        self.b_azzera.pack(side="left", padx=6)
        self.b_bootsel = self._etichetta(
            ttk.Button(cornice_f, style="Ghost.TButton",
                       command=self.rientra_in_bootsel), "fw_bootsel")
        self.b_bootsel.pack(side="left")
        # compare solo se c'e' davvero qualcosa da aggiornare
        self.b_aggiorna = self._etichetta(
            ttk.Button(cornice_f, style="Secondario.TButton",
                       command=self.aggiorna_firmware), "fw_aggiorna")

        self.et_nome = self._micro(s, "nome_scheda")
        self.et_nome.grid(row=4, column=0, sticky="w", pady=(7, 0))
        cornice_n = tk.Frame(s, background=T.PANEL)
        cornice_n.grid(row=4, column=1, columnspan=2, sticky="ew", padx=(6, 0),
                       pady=(7, 0))
        self.var_nome_scheda = tk.StringVar()
        self.campo_nome = ttk.Entry(cornice_n, textvariable=self.var_nome_scheda,
                                    width=26, font=self.tema.f_testo)
        self.campo_nome.pack(side="left")
        self.campo_nome.bind("<Return>", lambda _e: self.battezza_scheda())
        self.campo_nome.bind("<FocusOut>", lambda _e: self.battezza_scheda())
        self._nota(cornice_n, "nome_scheda_nota", 0.5).pack(side="left", padx=8)
        self.msg_firmware = Messaggio(self, s)
        self.msg_firmware.widget.grid(row=5, column=0, columnspan=3, sticky="w",
                                      pady=(7, 0))

        self.msg_collegamento = Messaggio(self, s)
        self.msg_collegamento.widget.grid(row=6, column=0, columnspan=3, sticky="w",
                                          pady=(7, 0))
        if not serprog.SERIALE:
            self.msg_collegamento.mostra("seriale_assente", AMBRA)
        return scheda

    # -- 2. chip -----------------------------------------------------------
    def _crea_chip(self, padre):
        scheda, s = self._scheda(padre, "sez_chip")
        s.columnconfigure(2, weight=1)

        self.b_identifica = self._etichetta(
            ttk.Button(s, style="Secondario.TButton", command=self.identifica_chip),
            "identifica")
        self.b_identifica.grid(row=0, column=0, sticky="w")
        self._micro(s, "chip_forzato").grid(row=0, column=1, sticky="e", padx=(10, 6))
        self.var_chip = tk.StringVar(value=self.conf.get("chip", ""))
        self.combo_chip = ttk.Combobox(s, textvariable=self.var_chip,
                                       font=self.tema.f_testo,
                                       values=CHIP_SUGGERITI)
        self.combo_chip.grid(row=0, column=2, sticky="ew")
        self.combo_chip.bind("<<ComboboxSelected>>", lambda _e: self._invalida_chip())
        self.combo_chip.bind("<KeyRelease>", lambda _e: self._invalida_chip())

        self.msg_chip = Messaggio(self, s)
        self.msg_chip.widget.grid(row=1, column=0, columnspan=3, sticky="w",
                                  pady=(7, 0))

        # La protezione occupa spazio solo quando ha qualcosa da dire: niente
        # etichetta fissa, e il tasto compare solo se c'e' un blocco da togliere.
        cornice_p = tk.Frame(s, background=T.PANEL)
        cornice_p.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(7, 0))
        self.msg_protezione = Messaggio(self, cornice_p)
        self.msg_protezione.widget.pack(side="left")
        self.b_sblocca = self._etichetta(
            ttk.Button(cornice_p, style="Secondario.TButton",
                       command=self.sblocca_chip), "prot_sblocca")
        return scheda

    # -- 3. lettura --------------------------------------------------------
    def _crea_lettura(self, padre):
        scheda, s = self._scheda(padre, "sez_lettura")
        s.columnconfigure(1, weight=1)

        self._micro(s, "cartella").grid(row=0, column=0, sticky="w")
        self.var_cartella = tk.StringVar(
            value=self.conf.get("cartella") or cartella_predefinita())
        ttk.Entry(s, textvariable=self.var_cartella,
                  font=self.tema.f_testo).grid(row=0, column=1, sticky="ew",
                                               padx=(6, 4))
        self._sfoglia(s, self.scegli_cartella).grid(row=0, column=2)

        cornice = tk.Frame(s, background=T.PANEL)
        cornice.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.b_leggi = self._etichetta(
            ttk.Button(cornice, style="Primario.TButton",
                       command=self.leggi_e_verifica), "leggi")
        self.b_leggi.pack(side="left")
        self._etichetta(ttk.Button(cornice, style="Ghost.TButton",
                                   command=self.apri_confronto),
                        "conf_apri").pack(side="left", padx=6)
        self._nota(cornice, "leggi_nota", 0.5).pack(side="left", padx=8)

        self.msg_lettura = Messaggio(self, s)
        self.msg_lettura.widget.grid(row=2, column=0, columnspan=3, sticky="w",
                                     pady=(7, 0))
        return scheda

    # -- 4. scrittura ------------------------------------------------------
    def _crea_scrittura(self, padre):
        scheda, s = self._scheda(padre, "sez_scrittura")
        s.columnconfigure(1, weight=1)

        self._micro(s, "modo").grid(row=0, column=0, sticky="w")
        cornice_m = tk.Frame(s, background=T.PANEL)
        cornice_m.grid(row=0, column=1, columnspan=2, sticky="w", padx=(6, 0))
        self.var_modo = tk.StringVar(value="regione")
        for valore, chiave in (("regione", "modo_regione"), ("intero", "modo_intero")):
            b = ttk.Radiobutton(cornice_m, value=valore, variable=self.var_modo,
                                command=self._aggiorna_scrittura)
            b.pack(side="left", padx=(0, 12))
            self._etichetta(b, chiave)

        self.var_immagine = tk.StringVar(value=self.conf.get("immagine", ""))
        self.var_layout = tk.StringVar(value=self.conf.get("layout", ""))
        self.var_atteso = tk.StringVar(value=self.conf.get("atteso", ""))
        for r, (chiave, var, comando) in enumerate((
                ("immagine", self.var_immagine, self.scegli_immagine),
                ("file_layout", self.var_layout, self.scegli_layout),
                ("atteso", self.var_atteso, self.scegli_atteso),
        ), start=1):
            self._micro(s, chiave).grid(row=r, column=0, sticky="w", pady=(6, 0))
            e = ttk.Entry(s, textvariable=var, font=self.tema.f_testo)
            e.grid(row=r, column=1, sticky="ew", padx=(6, 4), pady=(6, 0))
            e.bind("<KeyRelease>", lambda _e: self._aggiorna_scrittura())
            self._sfoglia(s, comando).grid(row=r, column=2, pady=(6, 0))
        self._nota(s, "atteso_nota", 0.7).grid(row=4, column=1, sticky="w",
                                               padx=(6, 0))

        self.et_regione = self._micro(s, "regione")
        self.et_regione.grid(row=5, column=0, sticky="w", pady=(6, 0))
        self.var_regione = tk.StringVar()
        self.combo_regione = ttk.Combobox(s, textvariable=self.var_regione, width=18,
                                          state="readonly", font=self.tema.f_testo)
        self.combo_regione.grid(row=5, column=1, sticky="w", padx=(6, 0), pady=(6, 0))
        self.combo_regione.bind("<<ComboboxSelected>>",
                                lambda _e: self._aggiorna_scrittura())

        filetto = tk.Frame(s, background=T.LINE, height=1)
        filetto.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(11, 9))

        self.var_alimentazione = tk.IntVar(value=0)
        self.spunta_alimentazione = T.Spunta(
            s, self.tema, self.var_alimentazione,
            comando=self._aggiorna_scrittura, colore="#F0C9CB")
        self.spunta_alimentazione.grid(row=7, column=0, columnspan=3, sticky="w")
        self._etichetta(self.spunta_alimentazione, "spunta_alimentazione",
                        attributo="testo")

        azioni = tk.Frame(s, background=T.PANEL)
        azioni.grid(row=8, column=0, columnspan=3, sticky="w", pady=(9, 0))
        self.b_secco = self._etichetta(
            ttk.Button(azioni, style="Secondario.TButton",
                       command=self.prova_a_secco), "prova_secco")
        self.b_secco.pack(side="left", padx=(0, 8))
        self.b_scrivi = self._etichetta(
            ttk.Button(azioni, style="Pericolo.TButton", command=self.scrivi),
            "scrivi")
        self.b_scrivi.pack(side="left")

        self.msg_scrittura = Messaggio(self, s)
        self.msg_scrittura.widget.grid(row=9, column=0, columnspan=3, sticky="w",
                                       pady=(7, 0))
        if self.var_layout.get():
            self._ricarica_regioni()
        return scheda

    # -- mappa del chip ----------------------------------------------------
    def _crea_mappa(self, padre):
        scheda, s = self._scheda(padre, "sez_mappa")
        s.columnconfigure(0, weight=1)

        self.mappa = M.Mappa(s, righe=8, su_posizione=self._posizione_mappa)
        self.mappa.grid(row=0, column=0, sticky="ew")

        piede = tk.Frame(s, background=T.PANEL)
        piede.grid(row=1, column=0, sticky="ew", pady=(7, 0))
        self.legenda = M.Legenda(piede, self.tema, self.L)
        self.legenda.pack(side="left")
        self.var_mappa = tk.StringVar()
        tk.Label(piede, textvariable=self.var_mappa, background=T.PANEL,
                 foreground="#55697C", font=(self.tema.mono, 7)).pack(side="right")
        self.after(200, self._riposo_mappa)
        return scheda

    def _posizione_mappa(self, posizione):
        if posizione is None:
            self._riposo_mappa()
        else:
            self.var_mappa.set(self.L("mappa_posizione", posizione=posizione))

    def _riposo_mappa(self):
        blocchi = max(self.mappa.blocchi, 1)
        self.var_mappa.set(self.L(
            "mappa_riposo",
            dimensione=A.leggibile(self.mappa.dimensione),
            blocchi=blocchi,
            grana=A.leggibile(int(self.mappa.dimensione / float(blocchi)))))

    def _prepara_mappa(self, intervallo=None):
        """Azzera la mappa e, se si lavora su una regione, la evidenzia."""
        if self.chip and self.chip.byte:
            self.mappa.imposta(dimensione=self.chip.byte)
        self.mappa.evidenzia(intervallo)
        self._riposo_mappa()

    # -- registro ----------------------------------------------------------
    def _crea_registro(self, padre):
        scheda, s = self._scheda(padre, "sez_registro")
        s.columnconfigure(0, weight=1)
        s.rowconfigure(0, weight=1)

        cornice = tk.Frame(s, background=T.LOG_BG, highlightthickness=1,
                           highlightbackground=T.LINE)
        cornice.grid(row=0, column=0, sticky="nsew")
        cornice.columnconfigure(0, weight=1)
        cornice.rowconfigure(0, weight=1)

        self.testo = tk.Text(cornice, height=6, wrap="none", font=self.tema.f_log,
                             background=T.LOG_BG, foreground="#C3D2DE",
                             insertbackground=T.FG, state="disabled",
                             relief="flat", bd=0, padx=8, pady=6,
                             selectbackground=T.ACCENT2)
        self.testo.grid(row=0, column=0, sticky="nsew")
        barra = ttk.Scrollbar(cornice, orient="vertical", command=self.testo.yview)
        barra.grid(row=0, column=1, sticky="ns")
        self.testo.configure(yscrollcommand=barra.set)
        self.testo.tag_configure("ora", foreground=T.LOG_ORA)
        self.testo.tag_configure("io", foreground="#7FB2FF")
        self.testo.tag_configure("male", foreground="#FF8686")
        self.testo.tag_configure("bene", foreground=T.LOG_OK)

        bottoni = tk.Frame(s, background=T.PANEL)
        bottoni.grid(row=1, column=0, columnspan=2, sticky="w", pady=(7, 0))
        self.b_interrompi = self._etichetta(
            ttk.Button(bottoni, style="Secondario.TButton",
                       command=self.interrompi), "interrompi")
        self.b_interrompi.pack(side="left")
        self.b_interrompi.state(["disabled"])
        self._etichetta(ttk.Button(bottoni, style="Ghost.TButton",
                                   command=self.pulisci_registro),
                        "pulisci").pack(side="left", padx=4)
        self._etichetta(ttk.Button(bottoni, style="Ghost.TButton",
                                   command=self.salva_registro),
                        "salva_registro").pack(side="left")
        self.var_dettagli = tk.IntVar(value=1 if self.conf.get("dettagli") else 0)
        T.Spunta(bottoni, self.tema, self.var_dettagli, testo="-V").pack(
            side="left", padx=12)
        return scheda

    # -- barra di stato ----------------------------------------------------
    def _costruisci_barra(self, padre):
        self.barra = tk.Frame(padre, background=T.INK)
        self.barra.columnconfigure(1, weight=1)
        self.avanzamento = ttk.Progressbar(
            self.barra, mode="indeterminate", length=130,
            style="Sottile.Horizontal.TProgressbar")
        self.avanzamento.grid(row=0, column=0, sticky="w")
        self.avanzamento.configure(mode="determinate", value=0)
        self.var_stato = tk.StringVar(value=self.L("pronto"))
        tk.Label(self.barra, textvariable=self.var_stato, background=T.INK,
                 foreground=T.MUT, font=self.tema.f_testo).grid(
            row=0, column=1, sticky="w", padx=10)
        self.var_flashrom = tk.StringVar()
        tk.Label(self.barra, textvariable=self.var_flashrom, background=T.INK,
                 foreground="#4F657A", font=(self.tema.mono, 7)).grid(
            row=0, column=2, sticky="e")

    # ------------------------------------------------------------ lingua
    def _cambia_lingua(self, _evento=None):
        scelto = self.var_lingua.get()
        for codice, nome in NOMI_LINGUA.items():
            if nome == scelto:
                self.L.codice = codice
                break
        self._traduci()
        self.var_stato.set(self.L("occupato") if self.occupato else self.L("pronto"))

    def _cambia_velocita(self, _evento=None):
        etichetta = self.var_velocita_etichetta.get()
        for valore, testo in VELOCITA_ETICHETTE.items():
            if testo == etichetta:
                self.var_velocita.set(valore)
                break
        self._invalida_lettura()

    def apri_schema(self):
        schema.apri(self, self.tema, self.L)

    def apri_confronto(self):
        confronto.apri(self, self.tema, self.L, self.var_cartella.get().strip())

    # -------------------------------------------------------- flashrom
    def _imposta_flashrom(self, percorso, silenzioso=False):
        candidato = fr.Flashrom(percorso)
        versione = candidato.versione()
        if versione is None:
            if not silenzioso:
                messagebox.showerror(self.L("titolo"), self.L("flashrom_non_valido"))
            return False
        self.flash = candidato
        self.versione_flashrom = versione
        return True

    def scegli_flashrom(self):
        percorso = filedialog.askopenfilename(
            title=self.L("flashrom_scegli"),
            filetypes=[("flashrom.exe", "flashrom.exe"), ("*", "*.*")])
        if percorso and self._imposta_flashrom(percorso):
            self._aggiorna_stato_flashrom()
            self._aggiorna_scrittura()
            self._salva_config()

    def _aggiorna_stato_flashrom(self):
        if self.flash:
            self.banner.grid_remove()
            pezzi = self.versione_flashrom.split()
            self.var_flashrom.set(self.L("flashrom_trovato",
                                         versione=pezzi[1] if len(pezzi) > 1 else "",
                                         percorso=self.flash.percorso))
        else:
            self.banner.grid(row=2, column=0, columnspan=2, sticky="ew",
                             padx=8, pady=(8, 0))
            self.var_flashrom.set("")
        for bottone in (self.b_identifica, self.b_leggi, self.b_qualifica):
            bottone.state(["!disabled"] if self.flash and not self.occupato
                          else ["disabled"])


    # ------------------------------------------------- firmware del Pico
    def _percorso_firmware(self):
        """pico_serprog.uf2: dentro l'eseguibile, accanto, in firmware\\."""
        for radice in (getattr(sys, "_MEIPASS", None), cartella_app()):
            if not radice:
                continue
            for candidato in (os.path.join(radice, "firmware", pico.NOME_FIRMWARE),
                              os.path.join(radice, pico.NOME_FIRMWARE)):
                if os.path.isfile(candidato):
                    return candidato
        return None

    def _guarda_bootsel(self):
        """Ogni due secondi: c'e' una scheda che aspetta il firmware?"""
        if not self.occupato:
            try:
                schede = pico.schede_in_bootsel()
            except Exception:                          # noqa: BLE001
                schede = []
            nuova = schede[0] if schede else None
            prima = self.scheda_bootsel.unita if self.scheda_bootsel else None
            adesso = nuova.unita if nuova else None
            if adesso != prima:
                if nuova is None:
                    pico.dimentica_seriali()
                self.scheda_bootsel = nuova
                if nuova:
                    self.registro("   RP2040 in BOOTSEL su %s (%s)" % (
                        nuova.lettera, nuova.identificativo), "io")
                self._aggiorna_firmware()
            self._chiedi_versione_se_serve()
        self.attesa_bootsel = self.after(2000, self._guarda_bootsel)

    def _aggiorna_firmware(self, con_messaggio=True):
        # il rientro in BOOTSEL si offre solo se c'e' un programmatore collegato
        porta = self._porta_programmatore()
        if porta is None:
            # niente programmatore, niente versione: quella di prima non vale
            self.fw_scheda = None
        self.b_bootsel.state(["!disabled"] if porta and not self.occupato
                             else ["disabled"])

        # il campo del nome segue la scheda che si sta guardando
        run, boot, _etichetta = self._scheda_corrente()
        nome = self.schede_note.nome(run=run, boot=boot) or ""
        if not self.campo_nome.focus_get() is self.campo_nome:
            self.var_nome_scheda.set(nome)
        self.campo_nome.state(["!disabled"] if (run or boot) else ["disabled"])

        scheda = self.scheda_bootsel
        if scheda is None:
            spedita = self._versione_spedita()
            vecchia = (porta is not None and spedita
                       and serprog.piu_vecchia(self.fw_scheda, spedita))
            if con_messaggio:
                if porta is None or self.fw_scheda is None:
                    self.msg_firmware.mostra("fw_nessuna", GRIGIO)
                elif not vecchia:
                    self.msg_firmware.mostra("fw_versione_ok", VERDE,
                                             versione=self.fw_scheda or "?")
                elif self.fw_scheda:
                    self.msg_firmware.mostra("fw_versione_vecchia", AMBRA,
                                             versione=self.fw_scheda,
                                             nuova=spedita)
                else:
                    self.msg_firmware.mostra("fw_versione_muta", AMBRA,
                                             nuova=spedita)
            if vecchia:
                self.b_aggiorna.pack(side="left", padx=(6, 0))
                self.b_aggiorna.state(["!disabled"] if not self.occupato
                                      else ["disabled"])
            else:
                self.b_aggiorna.pack_forget()
            self.b_firmware.state(["disabled"])
            self.b_azzera.state(["disabled"])
            return
        self.b_aggiorna.pack_forget()
        firmware = self._percorso_firmware()
        if not firmware:
            self.msg_firmware.mostra("fw_assente", AMBRA)
        elif nome:
            self.msg_firmware.mostra("fw_trovata_nome", VERDE, nome=nome,
                                     modello=scheda.modello,
                                     unita=scheda.lettera,
                                     seriale=scheda.seriale or "?")
        else:
            self.msg_firmware.mostra("fw_trovata_anonima", VERDE,
                                     modello=scheda.modello,
                                     unita=scheda.lettera,
                                     seriale=scheda.seriale or "?")
        acceso = ["!disabled"] if not self.occupato else ["disabled"]
        self.b_azzera.state(acceso)
        self.b_firmware.state(acceso if firmware else ["disabled"])

    def battezza_scheda(self):
        """Da' un nome alla scheda che si sta guardando. Vuoto = la dimentica."""
        run, boot, _e = self._scheda_corrente()
        if not (run or boot):
            return
        nome = self.var_nome_scheda.get().strip()
        prima = self.schede_note.nome(run=run, boot=boot) or ""
        if nome == prima:
            return
        self.schede_note.imposta_nome(nome, run=run, boot=boot)
        self._salva_config()
        self.rileva_porte()
        if nome:
            self.msg_firmware.mostra("fw_battezzata", VERDE, nome=nome)
        else:
            self.msg_firmware.mostra("fw_dimenticata", GRIGIO)

    def _programma(self, percorso_uf2, chiave_avvio, chiave_fine, aspetta_porta):
        """Copia un .uf2 sulla scheda e racconta com'e' andata."""
        scheda = self.scheda_bootsel
        if scheda is None or not percorso_uf2:
            return

        # ⚠️ Le porte serprog gia' presenti si annotano PRIMA: dopo si aspetta
        # una porta NUOVA. Cercandone una qualunque, con un programmatore gia'
        # collegato si direbbe "fatto" anche a copia fallita.
        prima = set(d for d, _n, sospetto, _s in serprog.elenca_porte() if sospetto)

        def lavoro():
            self._messaggio_da_thread(self.msg_firmware, chiave_avvio, AMBRA)
            fatto, motivo = pico.installa(percorso_uf2, scheda,
                                          su_riga=self._riga_da_thread)
            if not fatto:
                return ("errore", motivo, None)
            if not aspetta_porta:
                return ("fatto", None, None)
            self._messaggio_da_thread(self.msg_firmware, "fw_attendo", GRIGIO)
            # la scheda riparte come porta seriale: le si da' tempo
            for _ in range(30):
                time.sleep(0.5)
                adesso = set(d for d, _n, sospetto, _s in serprog.elenca_porte()
                             if sospetto)
                for dispositivo in sorted(adesso - prima):
                    diagnostica = serprog.interroga(dispositivo, BAUD)
                    if diagnostica.ok and diagnostica.parla_spi:
                        return ("pronto", dispositivo, diagnostica)
            return ("muto", None, None)

        def fine(risultato):
            stato, dato, diagnostica = risultato
            self.scheda_bootsel = None
            if stato == "errore":
                self.msg_firmware.mostra("fw_errore", ROSSO, motivo=dato)
            elif stato == "pronto":
                # ⚠️ Qui e' l'unico momento in cui i due identificativi della
                # stessa scheda si toccano: era in BOOTSEL, ora e' quella porta.
                if scheda.seriale:
                    seriale_run = self._seriale_di_porta(dato)
                    if seriale_run:
                        self.schede_note.collega(seriale_run, scheda.seriale)
                        self._salva_config()
                self.msg_firmware.mostra("fw_pronto", VERDE, porta=dato)
                self.registro("   %s, iface v%s, bus %s" % (
                    diagnostica.nome, diagnostica.versione,
                    diagnostica.bus_leggibile), "bene")
                self.rileva_porte()
            elif stato == "muto":
                self.msg_firmware.mostra("fw_non_riappare", AMBRA)
            else:
                self.msg_firmware.mostra(chiave_fine, VERDE)
            # ⚠️ senza questo, il riepilogo cancellerebbe l'esito appena letto
            self._aggiorna_firmware(con_messaggio=False)

        self._avvia(lavoro, fine, "firmware")

    def _versione_spedita(self):
        """La versione dell'UF2 che abbiamo qui dentro."""
        percorso = self._percorso_firmware()
        if not percorso:
            return None
        return pico.versione_disponibile(os.path.dirname(percorso))

    def _annota_firmware(self, diagnostica, seriale=None):
        """Registra cosa dichiara la scheda interrogata."""
        if diagnostica is None or not diagnostica.ok:
            return
        self.fw_scheda = diagnostica.firmware or ""
        if seriale:
            self.fw_chiesto.add(seriale)

    def _chiedi_versione_se_serve(self):
        """Una volta per scheda, non a ogni giro: apre e chiude la porta.

        ⚠️ Nessuno puo' dire da fuori che firmware c'e' su un RP2040: il
        seriale USB e' quello del chip e non cambia mai. Va chiesto alla
        scheda, e la scheda risponde solo dalla 1.1 in poi.
        """
        if self.occupato:
            return
        porta = self._porta_programmatore()
        if not porta:
            return
        seriale = self._seriale_di_porta(porta)
        if seriale and seriale in self.fw_chiesto:
            return
        diagnostica = serprog.interroga(porta, BAUD)
        if diagnostica.ok:
            self._annota_firmware(diagnostica, seriale)
            self._aggiorna_firmware()

    def _porta_programmatore(self):
        """La porta di un programmatore collegato adesso, se c'e'."""
        for dispositivo, _descrizione, sospetto, _seriale in serprog.elenca_porte():
            if sospetto:
                return dispositivo
        return None

    def _seriale_di_porta(self, porta):
        for dispositivo, _d, _s, seriale in serprog.elenca_porte():
            if dispositivo == porta:
                return seriale
        return None

    def _scheda_corrente(self):
        """(chiave_run, chiave_boot, etichetta) di cio' che si sta guardando.

        In BOOTSEL comanda la scheda-disco; altrimenti il programmatore
        collegato. Sono due identificativi diversi della stessa cosa, vedi
        anagrafica.py.
        """
        if self.scheda_bootsel is not None:
            boot = self.scheda_bootsel.seriale
            return None, boot, boot
        porta = self._porta_programmatore()
        if porta:
            run = self._seriale_di_porta(porta)
            return run, None, run
        return None, None, None

    def rientra_in_bootsel(self):
        """Rimette il programmatore in modalita' aggiornamento, da software."""
        porta = self._porta_programmatore()
        if not porta:
            return
        seriale_prima = self._seriale_di_porta(porta)

        def lavoro():
            self._messaggio_da_thread(self.msg_firmware, "fw_bootsel_provo",
                                      AMBRA, porta=porta)
            pico.rientra_in_bootsel(porta)
            # ⚠️ L'esito non si legge dall'apertura della porta, che fallisce
            # apposta: si guarda se la scheda ricompare come disco.
            for _ in range(20):
                time.sleep(0.5)
                schede = pico.schede_in_bootsel()
                if schede:
                    return ("bootsel", schede[0], None)
            return ("niente", None, None)

        def fine(risultato):
            stato, scheda, _ = risultato
            if stato == "bootsel":
                # stessa cosa al contrario: era quella porta, ora e' quel disco
                if seriale_prima and scheda.seriale:
                    self.schede_note.collega(seriale_prima, scheda.seriale)
                    self._salva_config()
                self.scheda_bootsel = scheda
                self.msg_firmware.mostra("fw_bootsel_ok", VERDE,
                                         unita=scheda.lettera)
                self.rileva_porte()
            else:
                self.msg_firmware.mostra("fw_bootsel_no", AMBRA)
            self._aggiorna_firmware()

        self._avvia(lavoro, fine, "bootsel")

    def aggiorna_firmware(self):
        """Rientro in BOOTSEL, copia, e ricontrollo: tre passi, un tasto.

        ⚠️ Il rientro da software esiste solo dalla 1.1. Una scheda piu'
        vecchia non torna in BOOTSEL da sola e va premuto il pulsante, una
        volta: dopo quell\u0027aggiornamento non serve piu'.
        """
        porta = self._porta_programmatore()
        percorso = self._percorso_firmware()
        if not (porta and percorso):
            return
        seriale_prima = self._seriale_di_porta(porta)
        # la porta della scheda che stiamo aggiornando sparisce e torna: non
        # va contata fra quelle "gia' presenti", o non la vedremmo tornare
        prima = set(d for d, _n, sospetto, _s in serprog.elenca_porte()
                    if sospetto)
        prima.discard(porta)

        def lavoro():
            self._messaggio_da_thread(self.msg_firmware, "fw_aggiorno", AMBRA)
            pico.rientra_in_bootsel(porta)
            scheda = None
            for _ in range(20):
                time.sleep(0.5)
                schede = pico.schede_in_bootsel()
                if schede:
                    scheda = schede[0]
                    break
            if scheda is None:
                return ("no_bootsel", None, None)
            self._messaggio_da_thread(self.msg_firmware, "fw_installando",
                                      AMBRA)
            fatto, motivo = pico.installa(percorso, scheda,
                                          su_riga=self._riga_da_thread)
            if not fatto:
                return ("errore", motivo, scheda)
            self._messaggio_da_thread(self.msg_firmware, "fw_attendo", GRIGIO)
            for _ in range(30):
                time.sleep(0.5)
                adesso = set(d for d, _n, sospetto, _s in serprog.elenca_porte()
                             if sospetto)
                for dispositivo in sorted(adesso - prima):
                    diagnostica = serprog.interroga(dispositivo, BAUD)
                    if diagnostica.ok and diagnostica.parla_spi:
                        return ("pronto", (dispositivo, diagnostica), scheda)
            return ("muto", None, scheda)

        def fine(risultato):
            stato, dato, scheda = risultato
            if scheda is not None and seriale_prima and scheda.seriale:
                self.schede_note.collega(seriale_prima, scheda.seriale)
                self._salva_config()
            self.scheda_bootsel = None
            if stato == "no_bootsel":
                self.msg_firmware.mostra("fw_aggiorna_no_bootsel", AMBRA)
            elif stato == "errore":
                self.msg_firmware.mostra("fw_errore", ROSSO, motivo=dato)
            elif stato == "muto":
                self.msg_firmware.mostra("fw_non_riappare", AMBRA)
            else:
                dispositivo, diagnostica = dato
                self._annota_firmware(diagnostica,
                                      self._seriale_di_porta(dispositivo))
                spedita = self._versione_spedita()
                # ⚠️ Non basta che la copia sia riuscita: la versione la deve
                # dichiarare la scheda, dopo essere ripartita.
                if diagnostica.firmware == spedita:
                    self.msg_firmware.mostra("fw_aggiornato", VERDE,
                                             versione=diagnostica.firmware,
                                             porta=dispositivo)
                else:
                    self.msg_firmware.mostra("fw_aggiorna_dubbio", ROSSO,
                                             versione=diagnostica.firmware
                                             or diagnostica.nome)
                self.rileva_porte()
            self._aggiorna_firmware(con_messaggio=False)

        self._avvia(lavoro, fine, "aggiornamento firmware")

    def installa_firmware(self):
        self._programma(self._percorso_firmware(), "fw_installando",
                        "fw_pronto", aspetta_porta=True)

    def azzera_scheda(self):
        """Riporta la scheda allo stato di fabbrica. Il .uf2 lo generiamo noi.

        ⚠️ DUE CONSENSI, e il secondo e' legato al SERIALE: con tre schede
        identiche sul tavolo, la domanda «sei sicuro?» non dice niente su QUALE
        stai cancellando. Ribattere le ultime quattro cifre obbliga a guardare
        quella giusta.
        """
        scheda = self.scheda_bootsel
        if scheda is None:
            return
        nome = self.schede_note.nome(boot=scheda.seriale)
        chi = "%s · %s" % (nome, scheda.seriale) if nome else (
            scheda.seriale or "%s su %s" % (scheda.modello, scheda.lettera))

        primo = self.L("fw_azzera_uno", chi=chi, byte=A.leggibile(pico.FLASH_PICO))
        if not Conferma(self, self.L, primo, self.tema,
                        parola=self.L("parola_cancella")).confermato:
            return

        if scheda.seriale:
            secondo = self.L("fw_azzera_due", unita=scheda.lettera,
                             seriale=scheda.seriale)
            parola = anagrafica.coda(scheda.seriale)
        else:
            secondo = self.L("fw_azzera_due_senza", unita=scheda.lettera)
            parola = self.L("parola_cancella")
        if not Conferma(self, self.L, secondo, self.tema,
                        parola=parola).confermato:
            return
        percorso = os.path.join(cartella_config(), "azzera.uf2")
        try:
            os.makedirs(cartella_config(), exist_ok=True)
            pico.genera_cancellazione(percorso)
        except OSError as e:
            self.msg_firmware.mostra("fw_errore", ROSSO, motivo="%s" % e)
            return
        self._programma(percorso, "fw_azzerando", "fw_azzerato",
                        aspetta_porta=False)

    # ------------------------------------------------------------ porte
    def rileva_porte(self):
        porte = serprog.elenca_porte()
        valori = []
        for dispositivo, descrizione, sospetto, seriale in porte:
            # il nome dato alla scheda vale piu' della descrizione di Windows
            nome = self.schede_note.nome(run=seriale) if seriale else None
            if nome:
                valori.append("%s — %s · %s" % (dispositivo, nome, seriale))
            elif sospetto and seriale:
                valori.append("%s — %s · %s" % (dispositivo, descrizione, seriale))
            else:
                valori.append("%s — %s" % (dispositivo, descrizione))
        self.combo_porta.configure(values=valori)
        if porte:
            attuale = self._porta_scelta()
            candidata = next((v for v, p in zip(valori, porte) if p[2]), valori[0])
            programmatori = [p[0] for p in porte if p[2]]
            # ⚠️ Non basta che la porta salvata esista ancora: se quella scelta
            # NON e' un programmatore e uno collegato c'e', si passa a quello.
            # Altrimenti, dopo che il Pico sparisce e torna, resta selezionata
            # una porta qualunque (Bluetooth, seriale di sistema).
            if (not attuale or attuale not in [p[0] for p in porte]
                    or (programmatori and attuale not in programmatori)):
                self.var_porta.set(candidata)
        elif serprog.SERIALE:
            self.msg_collegamento.mostra("nessuna_porta", AMBRA)

    def _porta_scelta(self):
        testo = (self.var_porta.get() or "").strip()
        return testo.split("—")[0].strip() if "—" in testo else testo

    def interroga_pico(self):
        porta = self._porta_scelta()
        if not porta:
            self.msg_collegamento.mostra("nessuna_porta", AMBRA)
            return
        self.registro("→ serprog: %s" % porta, "io")
        diagnostica = serprog.interroga(porta, BAUD)
        if not diagnostica.ok:
            self.msg_collegamento.mostra("pico_non_apre", ROSSO,
                                         porta=porta, motivo=diagnostica.errore)
            return
        self.msg_collegamento.mostra(
            "pico_riconosciuto", VERDE if diagnostica.parla_spi else AMBRA,
            nome=diagnostica.nome, versione=diagnostica.versione,
            bus=diagnostica.bus_leggibile)
        self.registro("   %s, iface v%s, bus %s" % (
            diagnostica.nome, diagnostica.versione, diagnostica.bus_leggibile))
        self._annota_firmware(diagnostica, self._seriale_di_porta(porta))
        self._aggiorna_firmware(con_messaggio=False)
        if not diagnostica.parla_spi:
            self.msg_collegamento.mostra("pico_no_spi", ROSSO)

    # ------------------------------------------------------------- chip
    def _invalida_chip(self):
        self.chip = None
        self.protezione = None
        if hasattr(self, "msg_protezione"):
            self._mostra_protezione()
        self._invalida_lettura()

    def _invalida_lettura(self):
        self.lettura_verificata = None
        self._aggiorna_scrittura()

    def identifica_chip(self):
        porta = self._porta_scelta()
        if not self.flash or not porta:
            return

        def lavoro():
            esito, chip = self.flash.identifica(
                porta, BAUD, self.var_velocita.get() or None,
                self.var_chip.get().strip() or None,
                bool(self.var_dettagli.get()), self._riga_da_thread)
            protezione = None
            if esito.ok and chip.nome:
                # ⚠️ Si chiede SUBITO: e' il modo piu' comune in cui una
                # scrittura non passa, e scoprirlo dopo la cancellazione e'
                # tardi.
                _e, protezione = self.flash.protezione(
                    porta, BAUD, self.var_velocita.get() or None,
                    chip.nome, bool(self.var_dettagli.get()),
                    self._riga_da_thread)
            return esito, chip, protezione

        def fine(risultato):
            esito, chip, protezione = risultato
            if chip.candidati:
                self.combo_chip.configure(values=CHIP_SUGGERITI + chip.candidati)
                self.msg_chip.mostra("chip_ambiguo", AMBRA)
                return
            if not esito.ok or not chip.nome:
                self.msg_chip.mostra("chip_non_trovato", ROSSO)
                return
            self.chip = chip
            self.protezione = protezione
            self.msg_chip.mostra("chip_trovato", VERDE, chip=chip.descrizione)
            self._mostra_protezione()
            self._aggiorna_scrittura()

        self._avvia(lavoro, fine, "identifica")

    def _mostra_protezione(self):
        p = self.protezione
        if p is None:
            self.msg_protezione.pulisci()
            self.b_sblocca.pack_forget()
            return
        if not p.sostenuta:
            self.msg_protezione.mostra("prot_ignota", GRIGIO)
            self.b_sblocca.pack_forget()
            return
        if not p.attiva:
            self.msg_protezione.mostra("prot_libera", VERDE)
            self.b_sblocca.pack_forget()
            return
        self.b_sblocca.pack(side="right", padx=(10, 0))
        intervallo = self._intervallo_regione()
        scontro = intervallo and p.tocca(intervallo[0], intervallo[1])
        if scontro:
            self.msg_protezione.mostra("prot_scontro", ROSSO,
                                       inizio=p.inizio, fine=p.fine)
        else:
            self.msg_protezione.mostra("prot_attiva", AMBRA, inizio=p.inizio,
                                       fine=p.fine, descrizione=p.descrizione,
                                       modo=p.modo)
        self.b_sblocca.state(["!disabled"] if not self.occupato else ["disabled"])

    def sblocca_chip(self):
        """Toglie la protezione. Cambia lo stato del chip: si chiede prima."""
        porta = self._porta_scelta()
        if not (self.flash and porta and self.chip):
            return
        testo = self.L("prot_conferma", chip=self.chip.descrizione)
        if not Conferma(self, self.L, testo, self.tema,
                        parola=self.L("parola_sblocca")).confermato:
            return

        def lavoro():
            comuni = dict(porta=porta, baud=BAUD,
                          spispeed=self.var_velocita.get() or None,
                          chip=self._chip_per_flashrom(),
                          dettagli=bool(self.var_dettagli.get()),
                          su_riga=self._riga_da_thread)
            esito = self.flash.sblocca(**comuni)
            _e, dopo = self.flash.protezione(**comuni)
            return esito, dopo

        def fine(risultato):
            esito, dopo = risultato
            self.protezione = dopo
            if dopo is not None and not dopo.attiva:
                self.registro("   %s" % self.L("prot_sbloccato"), "bene")
            else:
                self.msg_protezione.mostra("prot_non_tolta", ROSSO,
                                           codice=esito.codice)
                self.registro("!! %s" % self.L("prot_non_tolta",
                                               codice=esito.codice), "male")
                self._aggiorna_scrittura()
                return
            self._mostra_protezione()
            self._aggiorna_scrittura()

        self._avvia(lavoro, fine, "sblocco")

    # ---------------------------------------------------------- lettura
    def leggi_e_verifica(self):
        porta = self._porta_scelta()
        if not self.flash or not porta:
            return
        cartella = self.var_cartella.get().strip()
        try:
            os.makedirs(cartella, exist_ok=True)
        except OSError as e:
            self.msg_lettura.testo_grezzo("%s" % e, ROSSO)
            return

        marca = marca_ora()
        primo = os.path.join(cartella, "bc250-letto-%s.rom" % marca)
        secondo = os.path.join(cartella, "bc250-verifica-%s.rom" % marca)

        self._prepara_mappa()
        self.intervallo_lettura = (0, (self.chip.byte if self.chip and self.chip.byte
                                       else 16 * 1024 * 1024) - 1)

        def lavoro():
            comuni = dict(porta=porta, baud=BAUD,
                          spispeed=self.var_velocita.get() or None,
                          chip=self._chip_per_flashrom(),
                          dettagli=bool(self.var_dettagli.get()),
                          su_riga=self._riga_da_thread,
                          su_evento=self._evento_da_thread)
            self._messaggio_da_thread(self.msg_lettura, "lettura_1", GRIGIO)
            esito = self.flash.leggi(primo, **comuni)
            if not esito.ok:
                return ("errore", esito, None, None)
            self._messaggio_da_thread(self.msg_lettura, "lettura_2", GRIGIO)
            esito = self.flash.leggi(secondo, **comuni)
            if not esito.ok:
                return ("errore", esito, None, None)
            return ("ok", esito, md5_file(primo), md5_file(secondo))

        def fine(risultato):
            stato, esito, a, b = risultato
            if stato == "errore":
                self._esito_flashrom(self.msg_lettura, esito)
                return
            if a != b:
                self.msg_lettura.mostra("lettura_diversa", ROSSO, a=a[:8], b=b[:8])
                self.registro("!! letture diverse: %s != %s" % (a, b), "male")
                return
            self.lettura_verificata = a
            self.lettura_file = primo
            self.secco = None          # cambiata la base, la prova va rifatta
            self.mappa.segna(0, self.intervallo_lettura[1], M.VERIFICATO)
            try:
                os.remove(secondo)
            except OSError:
                pass
            self.msg_lettura.mostra("lettura_ok", VERDE, md5=a)
            self.registro("   %s" % self.L("lettura_salvata", percorso=primo), "bene")
            chiave = MD5_NOTI.get(a)
            self.registro("   %s" % self.L(
                "riconosciuto_come",
                cosa=self.L(chiave) if chiave else self.L("md5_sconosciuto")))
            if not self.var_atteso.get() and os.path.isfile(
                    os.path.join(cartella, "bc250-risultato-atteso.rom")):
                self.var_atteso.set(os.path.join(cartella, "bc250-risultato-atteso.rom"))
            self._aggiorna_scrittura()

        self._avvia(lavoro, fine, "lettura")

    def _esito_flashrom(self, messaggio, esito):
        """Quando flashrom si rifiuta: dirlo chiaro e lasciare il dettaglio nel
        registro, che c'e' gia' finito riga per riga."""
        if esito.interrotto:
            messaggio.testo_grezzo(self.L("interrotto"), AMBRA)
            return
        if esito.errore:
            messaggio.testo_grezzo(esito.errore, ROSSO)
            return
        messaggio.mostra("lettura_fallita", ROSSO, codice=esito.codice)

    def _chip_per_flashrom(self):
        forzato = self.var_chip.get().strip()
        if forzato:
            return forzato
        return self.chip.nome if self.chip and self.chip.nome else None

    # ------------------------------------------------- qualifica del cavo
    def qualifica_collegamento(self):
        """Cerca la velocita' piu' alta che dia due letture identiche.

        Legge una regione piccola invece di tutto il chip: la stessa domanda,
        in pochi secondi invece che in minuti.
        """
        porta = self._porta_scelta()
        if not self.flash or not porta:
            return
        cartella = self.var_cartella.get().strip()
        try:
            os.makedirs(cartella, exist_ok=True)
        except OSError as e:
            self.msg_collegamento.testo_grezzo("%s" % e, ROSSO)
            return

        dimensione = self.chip.byte if self.chip and self.chip.byte else 16 * 1024 * 1024
        prova_byte = min(PROVA_QUALIFICA, dimensione)
        layout = os.path.join(cartella, "qualifica-layout.txt")
        with open(layout, "wb") as f:
            f.write(("%08x:%08x prova\n%08x:%08x resto\n" % (
                0, prova_byte - 1, prova_byte, dimensione - 1)).encode("ascii"))
        primo = os.path.join(cartella, "qualifica-a.bin")
        secondo = os.path.join(cartella, "qualifica-b.bin")
        self._prepara_mappa()
        self.intervallo_lettura = (0, prova_byte - 1)

        def lavoro():
            for velocita in VELOCITA:
                etichetta = VELOCITA_ETICHETTE[velocita]
                self._messaggio_da_thread(self.msg_collegamento,
                                          "qualifica_prova", GRIGIO,
                                          velocita=etichetta)
                comuni = dict(porta=porta, baud=BAUD,
                              spispeed=velocita or None,
                              chip=self._chip_per_flashrom(),
                              dettagli=bool(self.var_dettagli.get()),
                              su_riga=self._riga_da_thread,
                              su_evento=self._evento_da_thread)
                a = self.flash.leggi_regione(layout, "prova", primo, **comuni)
                if self.fermati.is_set():
                    return ("interrotto", None, None)
                b = self.flash.leggi_regione(layout, "prova", secondo, **comuni)
                if not (a.ok and b.ok):
                    continue
                if md5_file(primo) == md5_file(secondo):
                    return ("ok", velocita, prova_byte)
            return ("no", None, None)

        def fine(risultato):
            stato, velocita, quanti = risultato
            for percorso in (primo, secondo, layout):
                try:
                    os.remove(percorso)
                except OSError:
                    pass
            if stato == "ok":
                self.var_velocita.set(velocita)
                self.var_velocita_etichetta.set(VELOCITA_ETICHETTE[velocita])
                self._invalida_lettura()
                self.msg_collegamento.mostra(
                    "qualifica_ok", VERDE, velocita=VELOCITA_ETICHETTE[velocita],
                    byte=A.leggibile(quanti))
            elif stato == "no":
                self.msg_collegamento.mostra("qualifica_nessuna", ROSSO)

        self._avvia(lavoro, fine, "qualifica")

    # --------------------------------------------------------- prova a secco
    def _intervallo_regione(self):
        """(inizio, fine) della regione scelta, oppure None per il chip intero."""
        if self.var_modo.get() != "regione":
            return None
        nome = self.var_regione.get()
        for regione, inizio, fine in self.regioni:
            if regione == nome:
                return (inizio, fine)
        return None

    def prova_a_secco(self):
        """Calcola come verra' la flash, senza toccarla."""
        if not (self.lettura_file and os.path.isfile(self.lettura_file)):
            self.msg_scrittura.mostra("scrivi_bloccato", AMBRA,
                                      cosa=self.L("req_lettura"))
            return
        immagine = self.var_immagine.get().strip()
        if not immagine or not os.path.isfile(immagine):
            self.msg_scrittura.mostra("scrivi_bloccato", AMBRA,
                                      cosa=self.L("req_immagine"))
            return
        regione = self._intervallo_regione()
        if self.var_modo.get() == "regione" and regione is None:
            self.msg_scrittura.mostra("scrivi_bloccato", AMBRA,
                                      cosa=self.L("req_layout"))
            return
        atteso = self.var_atteso.get().strip()

        def lavoro():
            attuale = A.leggi(self.lettura_file)
            sorgente = A.leggi(immagine)
            esito = A.prova_a_secco(attuale, sorgente, regione, md5=md5_dati)
            md5_atteso = md5_file(atteso) if atteso and os.path.isfile(atteso) else None
            return esito, md5_atteso, regione

        def fine(risultato):
            esito, md5_atteso, intervallo = risultato
            if esito.errore:
                self.secco = None
                self.msg_scrittura.testo_grezzo(esito.errore, ROSSO)
                self._aggiorna_scrittura()
                return
            self.secco = esito
            self.secco_firma = self._firma_secco()
            self._prepara_mappa(intervallo)
            self.mappa.segna_intervalli(esito.cambia, M.SCRITTO)
            self.mappa.segna_intervalli(esito.fuori, M.DIVERSO)

            if esito.nulla_da_fare:
                self.msg_scrittura.mostra("secco_nulla", AMBRA)
            elif esito.fuori:
                self.msg_scrittura.mostra(
                    "secco_fuori", AMBRA, intervalli=len(esito.fuori),
                    byte=A.leggibile(esito.byte_cambiati), md5=esito.md5[:12])
            else:
                self.msg_scrittura.mostra(
                    "secco_ok_uno" if len(esito.cambia) == 1 else "secco_ok",
                    VERDE, byte=A.leggibile(esito.byte_cambiati),
                    intervalli=len(esito.cambia), md5=esito.md5[:12])
            self.registro("   md5 %s · %s · %d %s" % (
                esito.md5, A.leggibile(esito.byte_cambiati), len(esito.cambia),
                "intervalli"), "bene")
            for inizio, fine_ in esito.cambia[:12]:
                self.registro("     0x%06X-0x%06X  %s" % (
                    inizio, fine_, A.leggibile(fine_ - inizio + 1)))
            if md5_atteso:
                if md5_atteso == esito.md5:
                    self.registro("   %s" % self.L("secco_atteso_uguale"), "bene")
                else:
                    self.msg_scrittura.mostra("secco_atteso_diverso", ROSSO,
                                              calcolato=esito.md5[:8],
                                              atteso=md5_atteso[:8])
                    self.registro("!! %s" % self.L(
                        "secco_atteso_diverso", calcolato=esito.md5,
                        atteso=md5_atteso), "male")
                    self.secco = None
            self._aggiorna_scrittura()

        self._avvia(lavoro, fine, "prova a secco")

    # --------------------------------------------------------- scrittura
    def _requisiti_mancanti(self):
        mancano = []
        if not self.flash:
            mancano.append(self.L("req_flashrom"))
        if not self.chip:
            mancano.append(self.L("req_chip"))
        if not self.lettura_verificata:
            mancano.append(self.L("req_lettura"))
        immagine = self.var_immagine.get().strip()
        if not immagine or not os.path.isfile(immagine):
            mancano.append(self.L("req_immagine"))
        elif self.chip and self.chip.byte:
            trovata = os.path.getsize(immagine)
            if trovata != self.chip.byte:
                mancano.append(self.L("req_dimensione", attesa=self.chip.byte,
                                      trovata=trovata))
        if self.var_modo.get() == "regione":
            layout = self.var_layout.get().strip()
            if not layout or not os.path.isfile(layout) or not self.var_regione.get():
                mancano.append(self.L("req_layout"))
        if not self.var_alimentazione.get():
            mancano.append(self.L("req_alimentazione"))
        # ⚠️ Un chip protetto accetta i comandi e non cambia: la scrittura
        # sembrerebbe riuscita e non lo sarebbe.
        intervallo = self._intervallo_regione() or (
            (0, self.chip.byte - 1) if self.chip and self.chip.byte else None)
        if (self.protezione is not None and intervallo
                and self.protezione.tocca(intervallo[0], intervallo[1])):
            mancano.append(self.L("req_protezione"))
        # ⚠️ La prova a secco e' obbligatoria: e' l'unico controllo che guarda
        # il CONTENUTO invece dei nomi dei file, e produce l'immagine attesa
        # con cui si verifichera' il chip alla fine.
        if self.secco is None or self.secco_firma != self._firma_secco():
            mancano.append(self.L("req_secco"))
        return mancano

    def _firma_secco(self):
        """Da cosa dipende la prova a secco: se cambia, va rifatta."""
        immagine = self.var_immagine.get().strip()
        try:
            marca = os.path.getmtime(immagine) if immagine else 0
        except OSError:
            marca = 0
        return (self.lettura_verificata, immagine, marca, self.var_modo.get(),
                self.var_regione.get(), self.var_layout.get().strip(),
                self.var_atteso.get().strip())

    def _aggiorna_scrittura(self):
        regione = self.var_modo.get() == "regione"
        self.combo_regione.configure(state="readonly" if regione else "disabled")
        self.et_regione.configure(foreground=T.MUT if regione else "#455563")

        mancano = self._requisiti_mancanti()
        if self.occupato or mancano:
            self.b_scrivi.state(["disabled"])
        else:
            self.b_scrivi.state(["!disabled"])
        if mancano:
            self.msg_scrittura.mostra("scrivi_bloccato", GRIGIO, cosa=", ".join(mancano))
        else:
            self.msg_scrittura.pulisci()

    def _ricarica_regioni(self):
        percorso = self.var_layout.get().strip()
        self.regioni = []
        if percorso and os.path.isfile(percorso):
            try:
                self.regioni = fr.leggi_layout(percorso)
            except OSError:
                self.regioni = []
        nomi = [n for n, _, _ in self.regioni]
        self.combo_regione.configure(values=nomi)
        if self.var_regione.get() not in nomi:
            self.var_regione.set("uefi" if "uefi" in nomi else (nomi[0] if nomi else ""))
        self._aggiorna_scrittura()

    def scrivi(self):
        mancano = self._requisiti_mancanti()
        if mancano:
            self.msg_scrittura.mostra("scrivi_bloccato", ROSSO, cosa=", ".join(mancano))
            return

        immagine = self.var_immagine.get().strip()
        regione = self.var_regione.get() if self.var_modo.get() == "regione" else None
        if regione:
            voce = next((r for r in self.regioni if r[0] == regione), None)
            testo = self.L("conferma_testo_regione", regione=regione,
                           byte=voce[2] - voce[1] + 1 if voce else 0,
                           inizio=voce[1] if voce else 0, fine=voce[2] if voce else 0,
                           chip=self.chip.descrizione, immagine=immagine)
        else:
            testo = self.L("conferma_testo_intero", byte=os.path.getsize(immagine),
                           chip=self.chip.descrizione, immagine=immagine)

        if not Conferma(self, self.L, testo, self.tema).confermato:
            return

        porta = self._porta_scelta()
        cartella = self.var_cartella.get().strip()
        attesa = self.secco.risultato          # calcolata dalla prova a secco
        md5_attesa = self.secco.md5
        intervallo = self._intervallo_regione() or (0, len(attesa) - 1)

        self._prepara_mappa(self._intervallo_regione())
        self.intervallo_lettura = (0, len(attesa) - 1)

        def lavoro():
            comuni = dict(porta=porta, baud=BAUD,
                          spispeed=self.var_velocita.get() or None,
                          chip=self._chip_per_flashrom(),
                          dettagli=bool(self.var_dettagli.get()),
                          su_riga=self._riga_da_thread,
                          su_evento=self._evento_da_thread)
            self._messaggio_da_thread(self.msg_scrittura, "scrittura_avvio", AMBRA)
            esito = self.flash.scrivi(immagine,
                                      layout=self.var_layout.get().strip() or None,
                                      regione=regione, **comuni)
            if not esito.ok:
                return ("errore", esito, None)

            # ⚠️ La verifica finale e' NOSTRA e indipendente da quella di
            # flashrom: si rilegge tutto il chip e lo si confronta byte per byte
            # con l'immagine che la prova a secco aveva calcolato.
            self._messaggio_da_thread(self.msg_scrittura, "verifica_finale", GRIGIO)
            dopo = os.path.join(cartella, "bc250-dopo-%s.rom" % marca_ora())
            esito2 = self.flash.leggi(dopo, **comuni)
            if not esito2.ok:
                return ("errore", esito2, None)
            letto = A.leggi(dopo)
            if len(letto) != len(attesa):
                return ("errore", esito2, None)
            diversi = A.unisci(A.blocchi_diversi(attesa, letto), A.SETTORE,
                               limite=len(attesa))
            byte_diversi = sum(f - i + 1 for i, f in
                               A.intervalli_esatti(attesa, letto, diversi))
            coerente = A.coerenza(letto, intervallo[0], intervallo[1])
            return ("fatto", esito, (dopo, diversi, byte_diversi, coerente,
                                     md5_dati(letto)))

        def fine(risultato):
            stato, esito, dati = risultato
            if stato == "errore":
                self.msg_scrittura.mostra("scrittura_fallita", ROSSO,
                                          codice=esito.codice)
                self.registro("!! %s" % self.L("scrittura_fallita",
                                               codice=esito.codice), "male")
                return
            self.registro("   %s" % self.L("scrittura_ok"), "bene")
            dopo, diversi, byte_diversi, coerente, md5_letto = dati
            self.registro("   %s" % self.L("lettura_salvata", percorso=dopo))

            if diversi:
                self.mappa.segna_intervalli(diversi, M.DIVERSO)
                self.msg_scrittura.mostra(
                    "verifica_diversa_uno" if len(diversi) == 1
                    else "verifica_diversa", ROSSO, intervalli=len(diversi),
                    byte=A.leggibile(byte_diversi))
                self.registro("!! %s (md5 letto %s, atteso %s)" % (
                    self.L("verifica_diversa", intervalli=len(diversi),
                           byte=A.leggibile(byte_diversi)),
                    md5_letto, md5_attesa), "male")
                for inizio, fine_ in diversi[:12]:
                    self.registro("     0x%06X-0x%06X" % (inizio, fine_), "male")
                return

            self.mappa.segna(0, len(attesa) - 1, M.VERIFICATO)
            self.msg_scrittura.mostra("verifica_ok", VERDE,
                                      byte=A.leggibile(len(attesa)))
            self.registro("   %s md5 %s" % (
                self.L("verifica_ok", byte=A.leggibile(len(attesa))),
                md5_letto), "bene")
            self._dillo_coerenza(coerente)

        self._avvia(lavoro, fine, "scrittura", scrittura=True)

    def _dillo_coerenza(self, coerente):
        """La regione scritta ha ancora una struttura sensata?"""
        if coerente["vuoto"]:
            self.registro("!! %s" % self.L("coerenza_vuota"), "male")
            self.msg_scrittura.mostra("coerenza_vuota", ROSSO)
            return
        if coerente["azzerato"]:
            self.registro("!! %s" % self.L("coerenza_zero"), "male")
            self.msg_scrittura.mostra("coerenza_zero", ROSSO)
            return
        pezzi = []
        for firma, chiave, testo_it, testo_en in A.FIRME:
            quante = coerente["firme"].get(chiave, 0)
            if quante:
                nome = testo_it if self.L.codice == "it" else testo_en
                pezzi.append("%s ×%d" % (nome, quante))
        if pezzi:
            self.registro("   %s" % self.L("coerenza_ok", cosa=", ".join(pezzi)),
                          "bene")
        else:
            self.registro("   %s" % self.L("coerenza_nulla"))

    # ------------------------------------------------------------ file
    def scegli_cartella(self):
        scelta = filedialog.askdirectory(initialdir=self.var_cartella.get() or None)
        if scelta:
            self.var_cartella.set(scelta)

    def _scegli_file(self, var, tipi):
        iniziale = os.path.dirname(var.get()) or self.var_cartella.get()
        scelta = filedialog.askopenfilename(initialdir=iniziale or None, filetypes=tipi)
        if scelta:
            var.set(scelta)
        return scelta

    def scegli_immagine(self):
        if self._scegli_file(self.var_immagine, [("ROM", "*.rom *.bin *.fd"), ("*", "*.*")]):
            self._aggiorna_scrittura()

    def scegli_layout(self):
        if self._scegli_file(self.var_layout, [("layout", "*.txt *.layout"), ("*", "*.*")]):
            self._ricarica_regioni()

    def scegli_atteso(self):
        self._scegli_file(self.var_atteso, [("ROM", "*.rom *.bin"), ("*", "*.*")])

    # --------------------------------------------------------- registro
    def registro(self, testo, tag=None):
        marca = datetime.now().strftime("%H:%M:%S")
        riga = "%s  %s" % (marca, testo)
        self.righe_registro.append(riga)
        self.testo.configure(state="normal")
        self.testo.insert("end", marca + "  ", ("ora",))
        self.testo.insert("end", testo + "\n", tag or ())
        self.testo.see("end")
        self.testo.configure(state="disabled")

    def pulisci_registro(self):
        self.righe_registro = []
        self.testo.configure(state="normal")
        self.testo.delete("1.0", "end")
        self.testo.configure(state="disabled")

    def salva_registro(self):
        percorso = filedialog.asksaveasfilename(
            initialdir=self.var_cartella.get() or None,
            initialfile="programmatore-bios-%s.log" % marca_ora(),
            defaultextension=".log")
        if not percorso:
            return
        try:
            with open(percorso, "wb") as f:
                f.write(("\n".join(self.righe_registro) + "\n").encode("utf-8"))
        except OSError as e:
            messagebox.showerror(self.L("titolo"), "%s" % e)

    def _salva_registro_automatico(self, operazione):
        cartella = self.var_cartella.get().strip()
        if not cartella or not os.path.isdir(cartella):
            return
        try:
            with open(os.path.join(cartella, "programmatore-bios.log"), "ab") as f:
                intestazione = "\n===== %s — %s =====\n" % (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), operazione)
                f.write(intestazione.encode("utf-8"))
                f.write(("\n".join(self.righe_registro) + "\n").encode("utf-8"))
        except OSError:
            pass

    # ------------------------------------------------------------ lavoro
    def _riga_da_thread(self, testo):
        self.coda.put(("riga", testo))

    def _evento_da_thread(self, tipo, *dati):
        self.coda.put(("evento", tipo, dati))

    # -- quello che flashrom racconta mentre lavora ------------------------
    def _applica_evento(self, tipo, dati):
        if tipo == "cancella":
            self.mappa.segna(dati[0], dati[1], M.CANCELLATO)
            return
        if tipo == "scrive":
            self.intervallo_scritto = (dati[0], dati[1])
            return
        if tipo != "fase":
            return

        nome, percento = dati
        if nome != self.fase:
            self.fase = nome
            self.inizio_fase = datetime.now()
        self.avanzamento.configure(mode="determinate", maximum=100,
                                   value=percento)
        self.var_stato.set(self._testo_avanzamento(nome, percento))

        if nome == "READ" or nome == "VERIFY":
            inizio, fine = self.intervallo_lettura
            stato = M.VERIFICATO if self.operazione_scrittura else M.LETTO
            self.mappa.avanza(inizio, fine, percento, stato)
        elif nome == "WRITE":
            inizio, fine = self.intervallo_scritto or self.intervallo_lettura
            self.mappa.avanza(inizio, fine, percento, M.SCRITTO)

    def _testo_avanzamento(self, nome, percento):
        fase = self.L("fase_%s" % nome)
        trascorso = (datetime.now() - self.inizio_fase).total_seconds() \
            if self.inizio_fase else 0
        if percento >= 3 and trascorso > 2:
            resta = trascorso * (100 - percento) / float(percento)
            return self.L("avanzamento_resta", fase=fase, percento=percento,
                          resta=_durata(resta))
        return self.L("avanzamento", fase=fase, percento=percento)

    def _messaggio_da_thread(self, messaggio, chiave, colore, **campi):
        self.coda.put(("messaggio", messaggio, chiave, colore, campi))

    def _avvia(self, lavoro, al_termine, nome, scrittura=False):
        if self.occupato:
            messagebox.showinfo(self.L("titolo"), self.L("in_corso"))
            return
        self.occupato = True
        self.operazione_scrittura = scrittura
        self.fermati.clear()
        self.fase = None
        self.inizio_fase = None
        self.intervallo_scritto = None
        self._blocca(True)
        self.avanzamento.configure(mode="indeterminate")
        self.avanzamento.start(12)
        self.var_stato.set(self.L("occupato"))
        self.registro("→ %s" % nome, "io")

        def sfondo():
            try:
                risultato = lavoro()
                self.coda.put(("fine", al_termine, risultato, nome, None))
            except Exception:                              # noqa: BLE001
                self.coda.put(("fine", None, None, nome, traceback.format_exc()))

        threading.Thread(target=sfondo, daemon=True).start()

    def _blocca(self, occupato):
        for bottone in (self.b_identifica, self.b_leggi, self.b_prova,
                        self.b_qualifica, self.b_secco, self.b_bootsel,
                        self.b_aggiorna):
            bottone.state(["disabled"] if occupato else ["!disabled"])
        self.b_interrompi.state(["!disabled"] if occupato else ["disabled"])
        if occupato:
            self.b_scrivi.state(["disabled"])
            self.b_sblocca.state(["disabled"])
        elif hasattr(self, "msg_protezione"):
            self._mostra_protezione()
        if not occupato and not self.flash:
            for bottone in (self.b_identifica, self.b_leggi, self.b_qualifica):
                bottone.state(["disabled"])

    def interrompi(self):
        if self.operazione_scrittura:
            messagebox.showwarning(self.L("titolo"), self.L("interruzione_vietata"))
            return
        self.fermati.set()
        if self.flash:
            self.flash.interrompi()
        self.registro("!! %s" % self.L("interrotto"), "male")

    def _pompa(self):
        try:
            while True:
                voce = self.coda.get_nowait()
                if voce[0] == "riga":
                    self.registro("   " + voce[1])
                elif voce[0] == "evento":
                    self._applica_evento(voce[1], voce[2])
                elif voce[0] == "messaggio":
                    _, messaggio, chiave, colore, campi = voce
                    messaggio.mostra(chiave, colore, **campi)
                elif voce[0] == "fine":
                    _, al_termine, risultato, nome, errore = voce
                    self.occupato = False
                    self.operazione_scrittura = False
                    self.avanzamento.stop()
                    self.avanzamento.configure(mode="determinate", value=0)
                    self.var_stato.set(self.L("pronto"))
                    self._blocca(False)
                    if errore:
                        self.registro(errore, "male")
                    elif al_termine:
                        al_termine(risultato)
                    self._salva_registro_automatico(nome)
                    self._aggiorna_scrittura()
                    self._aggiorna_firmware()
                    self._salva_config()
        except queue.Empty:
            pass
        self.after(60, self._pompa)

    def _chiudi(self):
        if self.occupato and not messagebox.askyesno(
                self.L("titolo"), self.L("chiudere_mentre_lavora")):
            return
        self._salva_config()
        self.destroy()


class Messaggio(object):
    """Una riga di esito, come pillola di stato, che sa ridisegnarsi al cambio
    lingua."""

    def __init__(self, app, padre):
        self.app = app
        self.chip = T.Chip(padre, app.tema)
        self.widget = self.chip
        self._chiave = None
        self._campi = {}
        self._colore = GRIGIO
        app._messaggi.append(self)

    def mostra(self, chiave, colore=GRIGIO, **campi):
        self._chiave, self._campi, self._colore = chiave, campi, colore
        self.ridisegna()

    def testo_grezzo(self, testo, colore=GRIGIO):
        self._chiave = None
        fondo, bordo = FONDI.get(colore, (T.PANEL, T.PANEL))
        self.chip.mostra(testo, colore, fondo, bordo)

    def pulisci(self):
        self._chiave = None
        self.chip.spegni()

    def ridisegna(self):
        if self._chiave is None:
            return
        fondo, bordo = FONDI.get(self._colore, (T.PANEL, T.PANEL))
        self.chip.mostra(self.app.L(self._chiave, **self._campi), self._colore,
                         fondo, bordo)


class Conferma(tk.Toplevel):
    """Non basta un «sì»: la parola va scritta a mano."""

    def __init__(self, padre, L, testo, tm=None, parola=None):
        tk.Toplevel.__init__(self, padre, background=T.INK)
        self.confermato = False
        self.L = L
        self.title(L("conferma_titolo"))
        self.resizable(False, False)
        self.transient(padre)
        tm = tm or getattr(padre, "tema", None)

        cornice = tk.Frame(self, background=T.INK, padx=18, pady=16)
        cornice.pack(fill="both", expand=True)

        avviso = tk.Frame(cornice, background=T.CRIT_BG, highlightthickness=1,
                          highlightbackground=T.CRIT_BORDO)
        avviso.pack(fill="x")
        tk.Label(avviso, text=testo, justify="left", anchor="w", wraplength=520,
                 background=T.CRIT_BG, foreground="#F0C9CB",
                 font=tm.f_testo if tm else None).pack(anchor="w", padx=12, pady=10)

        self.parola = parola or L("parola_conferma")
        tk.Label(cornice, text=L("conferma_digita", parola=self.parola),
                 background=T.INK, foreground=T.FG,
                 font=tm.f_testo if tm else None).pack(anchor="w", pady=(14, 5))
        self.var = tk.StringVar()
        campo = ttk.Entry(cornice, textvariable=self.var, width=26,
                          font=tm.f_dato if tm else None)
        campo.pack(anchor="w")
        self.var.trace_add("write", lambda *_: self._controlla())

        bottoni = tk.Frame(cornice, background=T.INK)
        bottoni.pack(anchor="e", pady=(16, 0))
        ttk.Button(bottoni, text=L("annulla"), style="Secondario.TButton",
                   command=self.destroy).pack(side="right")
        self.ok = ttk.Button(bottoni, text=L("procedi"), style="Pericolo.TButton",
                             command=self._procedi)
        self.ok.pack(side="right", padx=8)
        self.ok.state(["disabled"])

        T.titolo_scuro(self)
        campo.focus_set()
        self.grab_set()
        padre.wait_window(self)

    def _controlla(self):
        uguale = self.var.get().strip().upper() == self.parola.upper()
        self.ok.state(["!disabled"] if uguale else ["disabled"])

    def _procedi(self):
        self.confermato = True
        self.destroy()


def main():
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
