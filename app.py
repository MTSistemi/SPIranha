# -*- coding: utf-8 -*-
"""L'interfaccia: la procedura in quattro passi, con i controlli obbligatori.

L'idea di fondo: quando serve questo programma la scheda e' gia' morta e si ha
fretta. Le cose che oggi bisogna ricordarsi a mente — leggere due volte e
confrontare, tenere la BC-250 staccata, rileggere prima di riattaccare — qui le
impone il programma, e il tasto di scrittura resta spento finche' non tornano.

Il codice che tocca il chip e' flashrom: qui si costruiscono i comandi e si
guardano gli esiti. La veste e' il tema «quadro strumenti» (vedi theme.py).
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

import level_shifter
import analysis as A
import boards
import compare
import flashrom as fr
import chipmap as M
import pico
import profiles
import regions as reg
import chip_search
import wiring
import voltage as V
import serprog
import theme as T
from i18n import LANGUAGES, LANGUAGE_NAMES, Language

APP_NAME = "SPIranha"
BAUD = 115200
BLOCK = 1024 * 1024


SPEEDS = ["", "8M", "4M", "2M", "1M", "500k"]
SPEED_LABELS = {
    "": "12 MHz (firmware)",
    "8M": "8 MHz", "4M": "4 MHz", "2M": "2 MHz",
    "1M": "1 MHz", "500k": "500 kHz",
}

# I modelli suggeriti li porta il profilo: qui resta solo la voce vuota, che
# vuol dire «fai riconoscere il chip a flashrom».
SUGGESTED_CHIPS = [""]

# Quanto si legge per qualificare il collegamento: abbastanza da accorgersi di
# un cavo incerto, poco abbastanza da poterlo rifare a ogni velocita'.
QUALIFY_BYTES = 256 * 1024

# I quattro stati di un messaggio, nei colori del tema.
GREEN = T.OK
RED = T.CRIT
AMBER = T.WARN
GREY = T.MUT
TINTS = {
    T.OK: (T.OK_BG, T.OK_BORDO),
    T.CRIT: (T.CRIT_BG, T.CRIT_BORDO),
    T.WARN: (T.WARN_BG, T.WARN_BORDO),
}


# ---------------------------------------------------------------- utilita'

def app_folder():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def config_folder():
    """Dove stanno le impostazioni.

    ⚠️ SPIRANHA_CONFIG esiste per le prove, e non e' un vezzo: le prove
    costruiscono la finestra vera, cambiano profilo e salvano -- cioe'
    riscrivevano le impostazioni di chi stava usando il programma. Chi le
    lanciava se lo ritrovava con un altro profilo e i percorsi delle prove.
    """
    forzata = os.environ.get("SPIRANHA_CONFIG")
    if forzata:
        return forzata
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME)


def default_folder():
    documenti = os.path.join(os.path.expanduser("~"), "Documents")
    for candidate in (
        os.path.join(documenti, "Claude", "SkillFishOS", "bios-backup"),
        os.path.join(documenti, "bios-backup"),
    ):
        if os.path.isdir(candidate):
            return candidate
    return documenti


def md5_of_file(path, stop_flag=None):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(BLOCK)
            if not chunk:
                break
            h.update(chunk)
            if stop_flag is not None and stop_flag.is_set():
                return None
    return h.hexdigest()


def timestamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _durata(seconds):
    """Un tempo che resta alla fine, detto corto."""
    seconds = int(max(0, seconds))
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm %02ds" % (seconds // 60, seconds % 60)
    return "%dh %02dm" % (seconds // 3600, (seconds % 3600) // 60)


def md5_of(data):
    return hashlib.md5(data).hexdigest()


# ---------------------------------------------------------------- finestra

class App(tk.Tk):

    def __init__(self):
        tk.Tk.__init__(self)
        self.settings = self._load_config()
        self.L = Language(self.settings.get("lingua", "it"))

        self.tail_of = queue.Queue()
        self.busy = False
        self.writing = False
        self.stop_flag = threading.Event()

        # stato della procedura: ogni requisito e' una condizione per scrivere
        self.chip = None                 # fr.Chip identificato
        self.protection = None           # fr.Protezione, letta col chip
        self.profile = profiles.by_key(self.settings.get("profilo"))
        self.board_firmware = None            # versione dichiarata dal programmatore
        self.chip_is_1v8 = None            # il chip vuole 1,8 V? None = non si sa
        self.known_chips = []              # l'elenco che flashrom dichiara
        self.firmware_asked = set()          # seriali a cui l'abbiamo gia' chiesta
        self.verified_read = None   # md5 dell'ultima lettura doppia riuscita
        self.log_lines = []
        self.regions = []                # (nome, inizio, fine) dal file di layout
        self.flashrom_version = ""
        self.read_path = None         # file dell'ultima lettura verificata
        self.dry = None                # esito della prova a secco
        self.secco_firma = None
        self.phase = None                 # fase in corso, per mappa e avanzamento
        self.phase_start = None
        self.written_span = None
        self.read_span = (0, 16 * 1024 * 1024 - 1)
        self.known_boards = boards.Registry(self.settings.get("schede"))
        self.bootsel_board = None       # RP2040 in attesa di firmware
        self.bootsel_watch = None

        self.flash = None
        path = self.settings.get("flashrom")
        if not (path and os.path.isfile(path)):
            # nell'eseguibile unico flashrom viaggia dentro: _MEIPASS e' la
            # cartella dove PyInstaller lo scompatta all'avvio
            path = fr.find_executable(
                app_folder(), extra=[getattr(sys, "_MEIPASS", None)])
        if path:
            self._imposta_flashrom(path, silenzioso=True)

        self._etichette = []             # (widget, chiave, attributo, trasforma)
        self._messaggi = []              # Messaggio da ridisegnare al cambio lingua

        self.theme = T.Theme(self)
        self._build_ui()
        self._retranslate()
        self.detect_ports()
        T.dark_title_bar(self)
        self.after(60, self._pump)
        self.after(400, self._watch_bootsel)
        # l'elenco dei modelli si riempie da solo poco dopo l'apertura: la
        # finestra deve comparire subito, non aspettare flashrom
        self.after(600, self._load_chip_list)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------ config
    def _load_config(self):
        try:
            with open(os.path.join(config_folder(), "config.json"), "rb") as f:
                return json.loads(f.read().decode("utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_config(self):
        self.settings.update({
            "lingua": self.L.code,
            "flashrom": self.flash.path if self.flash else None,
            "porta": self.var_port.get(),
            "spispeed": self.var_speed.get(),
            "cartella": self.var_folder.get(),
            "chip": self.var_chip.get(),
            "immagine": self.var_image.get(),
            "layout": self.var_layout.get(),
            "profilo": self.profile.key,
            "atteso": self.var_expected.get(),
            "dettagli": bool(self.var_verbose.get()),
            "schede": self.known_boards.as_list(),
        })
        try:
            os.makedirs(config_folder(), exist_ok=True)
            with open(os.path.join(config_folder(), "config.json"), "wb") as f:
                f.write(json.dumps(self.settings, indent=2).encode("utf-8"))
        except OSError:
            pass

    # ------------------------------------------------- costruzione grafica
    def _translated(self, widget, key, attribute="text", transform=None):
        """Registra un widget perche' si riscriva al cambio lingua."""
        self._etichette.append((widget, key, attribute, transform))
        return widget

    def _retranslate(self):
        self.title(self.L("titolo"))
        for widget, key, attribute, transform in self._etichette:
            text = self.L(key)
            if transform:
                text = transform(text)
            try:
                widget.configure(**{attribute: text})
            except tk.TclError:
                pass
        for message in self._messaggi:
            message.redraw()
        if hasattr(self, "lbl_reminder"):
            self._write_reminder()
        # ⚠️ Anche il selettore e la barra di stato: cambiando lingua da
        # codice restavano indietro, e si vedeva «Italiano» sopra una
        # finestra in inglese.
        if hasattr(self, "var_language"):
            self.var_language.set(LANGUAGE_NAMES.get(self.L.code, ""))
        if hasattr(self, "var_status"):
            self.var_status.set(self.L("occupato") if self.busy
                               else self.L("pronto"))
        if hasattr(self, "combo_profile"):
            self._fill_profiles()
        self.var_speed_label.set(SPEED_LABELS.get(self.var_speed.get(), ""))
        if hasattr(self, "legend"):
            self.legend.translate()
            self._map_at_rest()
        # ⚠️ Va chiamata anche all'avvio: _guarda_bootsel aggiorna solo quando
        # lo stato CAMBIA, e all'inizio "nessuna scheda" non e' un cambiamento.
        if hasattr(self, "msg_firmware"):
            self._update_firmware_row()
        self._draw_header()
        self._update_flashrom_banner()
        self._update_write_state()
        window = getattr(self, "_wiring_window", None)
        if window is not None and window.winfo_exists():
            window.title(self.L("sch_titolo"))
            window.draw()

    SOGLIA_DUE_COLONNE = 940      # sotto questa larghezza si impila tutto

    def _build_ui(self):
        self.geometry("1040x876")
        self.minsize(620, 540)

        self.root = tk.Frame(self, background=T.INK)
        self.root.pack(fill="both", expand=True)

        self._costruisci_testata(self.root)
        self._build_banner(self.root)
        self.boards = [
            self._make_connection_card(self.root),
            self._make_chip_card(self.root),
            self._make_read_card(self.root),
            self._make_write_card(self.root),
        ]
        self.scheda_mappa = self._make_map_card(self.root)
        self.scheda_registro = self._make_log_card(self.root)
        self._costruisci_barra(self.root)

        self._colonne = None
        self._riflusso(two=True)
        self._attesa_riflusso = None
        self.bind("<Configure>", self._forse_riflusso)

    # -- responsive: una o due colonne secondo lo spazio --------------------
    def _forse_riflusso(self, event):
        if event.widget is not self:
            return
        if self._attesa_riflusso:
            self.after_cancel(self._attesa_riflusso)
        self._attesa_riflusso = self.after(
            90, lambda: self._riflusso(two=self.winfo_width() >= self.SOGLIA_DUE_COLONNE))

    def _riflusso(self, two):
        self._attesa_riflusso = None
        if two == self._colonne:
            self._adatta_larghezze()
            return
        self._colonne = two
        r = self.root
        for card in self.boards:
            card.grid_forget()
        self.scheda_mappa.grid_forget()
        self.scheda_registro.grid_forget()
        self.bar.grid_forget()

        for index in (0, 1):
            r.columnconfigure(index, weight=1 if (two or index == 0) else 0,
                              uniform="colonne" if two else "")
        for index in range(3, 12):
            r.rowconfigure(index, weight=0)

        pad = dict(padx=8, pady=(8, 0))
        if two:
            self.boards[0].grid(row=3, column=0, sticky="new", **pad)
            self.boards[1].grid(row=4, column=0, sticky="new", **pad)
            self.boards[2].grid(row=5, column=0, sticky="new", **pad)
            self.boards[3].grid(row=3, column=1, rowspan=3, sticky="new", **pad)
            riga_mappa = 6
        else:
            for index, card in enumerate(self.boards):
                card.grid(row=3 + index, column=0, columnspan=2, sticky="new",
                            **pad)
            riga_mappa = 7
        self.scheda_mappa.grid(row=riga_mappa, column=0, columnspan=2,
                               sticky="ew", padx=8, pady=(8, 0))
        riga_registro = riga_mappa + 1
        self.scheda_registro.grid(row=riga_registro, column=0, columnspan=2,
                                  sticky="nsew", padx=8, pady=(8, 0))
        r.rowconfigure(riga_registro, weight=1)
        self.bar.grid(row=riga_registro + 1, column=0, columnspan=2, sticky="ew",
                        padx=10, pady=(6, 8))
        self._adatta_larghezze()

    def _adatta_larghezze(self):
        """Le scritte lunghe si adattano alla colonna invece di allargare tutto."""
        width = max(self.winfo_width(), 400)
        column = (width - 32) // (2 if self._colonne else 1)
        for message in self._messaggi:
            message.chip.text.configure(wraplength=max(column - 70, 180))
        for widget, avvolgi in getattr(self, "_wrappables", ()):
            widget.configure(wraplength=max(int(column * avvolgi), 150))

    # -- testata -----------------------------------------------------------
    def _costruisci_testata(self, parent):
        self.header_canvas = tk.Canvas(parent, height=54, background=T.HEADER_DA,
                                      highlightthickness=0, bd=0)
        self.header_canvas.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.header_canvas.bind("<Configure>", lambda _e: self._draw_header())

        frame = tk.Frame(self.header_canvas, background=T.INK)
        self.var_language = tk.StringVar(value=LANGUAGE_NAMES[self.L.code])
        choice = ttk.Combobox(frame, textvariable=self.var_language, width=9,
                              state="readonly", font=self.theme.f_text,
                              values=[LANGUAGE_NAMES[c] for c in LANGUAGES])
        choice.pack(side="left")
        choice.bind("<<ComboboxSelected>>", self._language_changed)

        # ⚠️ Il profilo sta accanto alla lingua e non dentro una scheda: dice
        # SU COSA si sta lavorando, e va visto prima di toccare qualunque cosa.
        self.var_profile = tk.StringVar()
        self.combo_profile = ttk.Combobox(frame, textvariable=self.var_profile,
                                          width=16, state="readonly",
                                          font=self.theme.f_text)
        self.combo_profile.pack(side="left", padx=(8, 0))
        self.combo_profile.bind("<<ComboboxSelected>>", self._profile_changed)
        self._fill_profiles()
        self.header_canvas.create_window(0, 0, window=frame, anchor="ne",
                                        tags="lingua")
        self.header_canvas.bind("<Configure>", lambda _e: self._draw_header())

        # promemoria: la regola che non cambia mai
        pro = tk.Frame(parent, background=T.WARN_BG, highlightthickness=1,
                       highlightbackground=T.WARN_BORDO, bd=0)
        pro.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 0))
        dot = tk.Canvas(pro, width=8, height=8, background=T.WARN_BG,
                          highlightthickness=0)
        dot.create_oval(0, 0, 8, 8, fill=T.WARN, outline="")
        dot.pack(side="left", padx=(9, 7), pady=6)
        label_for = tk.Label(pro, background=T.WARN_BG, foreground="#E8D6B4",
                             anchor="w", justify="left", wraplength=900,
                             font=self.theme.f_text)
        label_for.pack(side="left", pady=5, padx=(0, 10))
        self.lbl_reminder = label_for
        self._avvolgibili = [(label_for, 1.9)]
        self._write_reminder()

    def _draw_header(self):
        canvas = self.header_canvas
        width = max(canvas.winfo_width(), 320)
        canvas.delete("scritte")
        T.gradient(canvas, width, 54)
        canvas.create_text(18, 18, text=self.L("titolo"), fill=T.FG, anchor="w",
                         font=self.theme.f_titolo, tags="scritte")
        canvas.create_text(19, 38,
                         text=self.L("sottotitolo",
                                     board=self.profile.text(
                                         "name", self.L.code)),
                         fill=T.MUT,
                         anchor="w", font=self.theme.f_sotto, tags="scritte")
        canvas.create_line(0, 53, width, 53, fill=T.LINE, tags="scritte")
        canvas.coords("lingua", width - 12, 14)

    # -- banner flashrom ---------------------------------------------------
    def _build_banner(self, parent):
        self.banner = tk.Frame(parent, background=T.CRIT_BG, highlightthickness=1,
                               highlightbackground=T.CRIT_BORDO, bd=0)
        dot = tk.Canvas(self.banner, width=8, height=8, background=T.CRIT_BG,
                          highlightthickness=0)
        dot.create_oval(0, 0, 8, 8, fill=T.CRIT, outline="")
        dot.pack(side="left", padx=(9, 7), pady=6)
        self.banner_testo = tk.Label(self.banner, background=T.CRIT_BG,
                                     foreground="#F0C9CB", anchor="w",
                                     justify="left", wraplength=700,
                                     font=self.theme.f_text)
        self.banner_testo.pack(side="left", fill="x", expand=True, pady=5)
        self._translated(self.banner_testo, "flashrom_assente")
        self.banner_bottone = ttk.Button(self.banner, style="Pericolo.TButton",
                                         command=self.pick_flashrom)
        self.banner_bottone.pack(side="right", padx=7, pady=5)
        self._translated(self.banner_bottone, "flashrom_individua")
        self.banner.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8,
                         pady=(8, 0))

    def _card(self, parent, key):
        card, body = T.card(parent, self.L(key), self.theme)
        self._translated(card.etichetta_titolo, key, transform=T.micro)
        return card, body

    def _micro_label(self, parent, key):
        return self._translated(
            tk.Label(parent, background=T.PANEL, foreground=T.MUT,
                     font=self.theme.f_micro, anchor="w"),
            key, transform=T.micro)

    def _note(self, parent, key, avvolgi=0.9):
        label_for = tk.Label(parent, background=T.PANEL, foreground=T.MUT,
                             font=self.theme.f_minuto, anchor="w", justify="left",
                             wraplength=320)
        self._translated(label_for, key)
        self._avvolgibili.append((label_for, avvolgi))
        return label_for

    def _browse_button(self, parent, command):
        return self._translated(ttk.Button(parent, style="Secondario.TButton",
                                          width=3, command=command), "sfoglia")

    # -- 1. collegamento ---------------------------------------------------
    def _make_connection_card(self, parent):
        card, s = self._card(parent, "sez_collegamento")
        s.columnconfigure(1, weight=1)

        self._micro_label(s, "porta").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.var_port = tk.StringVar(value=self.settings.get("porta", ""))
        self.combo_port = ttk.Combobox(s, textvariable=self.var_port,
                                        font=self.theme.f_text)
        self.combo_port.grid(row=0, column=1, sticky="ew", padx=(6, 6), pady=(0, 4))

        buttons = tk.Frame(s, background=T.PANEL)
        buttons.grid(row=0, column=2, sticky="e", pady=(0, 4))
        self._translated(ttk.Button(buttons, style="Secondario.TButton",
                                   command=self.detect_ports),
                        "rileva").pack(side="left", padx=(0, 4))
        self.b_prova = self._translated(
            ttk.Button(buttons, style="Secondario.TButton",
                       command=self.query_pico), "prova")
        self.b_prova.pack(side="left", padx=(0, 4))
        self.b_schema = self._translated(
            ttk.Button(buttons, style="Ghost.TButton", command=self.open_wiring),
            "sch_apri")
        self.b_schema.pack(side="left")

        self._micro_label(s, "velocita").grid(row=1, column=0, sticky="w")
        cornice_v = tk.Frame(s, background=T.PANEL)
        cornice_v.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(6, 0))
        self.var_speed = tk.StringVar(value=self.settings.get("spispeed", ""))
        self.var_speed_label = tk.StringVar()
        combo_v = ttk.Combobox(cornice_v, width=15, state="readonly",
                               font=self.theme.f_text,
                               textvariable=self.var_speed_label,
                               values=[SPEED_LABELS[v] for v in SPEEDS])
        combo_v.pack(side="left")
        combo_v.bind("<<ComboboxSelected>>", self._speed_changed)
        self.b_qualify = self._translated(
            ttk.Button(cornice_v, style="Secondario.TButton",
                       command=self.qualify_link), "qualifica")
        self.b_qualify.pack(side="left", padx=(6, 0))
        self._note(cornice_v, "qualifica_nota", 0.5).pack(side="left", padx=8)

        # --- firmware del programmatore
        filetto = tk.Frame(s, background=T.LINE, height=1)
        filetto.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 8))

        self._micro_label(s, "firmware").grid(row=3, column=0, sticky="w")
        cornice_f = tk.Frame(s, background=T.PANEL)
        cornice_f.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(6, 0))
        self.b_firmware = self._translated(
            ttk.Button(cornice_f, style="Secondario.TButton",
                       command=self.install_firmware), "fw_installa")
        self.b_firmware.pack(side="left")
        self.b_reset = self._translated(
            ttk.Button(cornice_f, style="Ghost.TButton",
                       command=self.reset_board), "fw_azzera")
        self.b_reset.pack(side="left", padx=6)
        self.b_bootsel = self._translated(
            ttk.Button(cornice_f, style="Ghost.TButton",
                       command=self.back_to_bootsel), "fw_bootsel")
        self.b_bootsel.pack(side="left")
        # compare solo se c'e' davvero qualcosa da aggiornare
        self.b_update = self._translated(
            ttk.Button(cornice_f, style="Secondario.TButton",
                       command=self.update_firmware), "fw_aggiorna")

        self.lbl_name = self._micro_label(s, "nome_scheda")
        self.lbl_name.grid(row=4, column=0, sticky="w", pady=(7, 0))
        cornice_n = tk.Frame(s, background=T.PANEL)
        cornice_n.grid(row=4, column=1, columnspan=2, sticky="ew", padx=(6, 0),
                       pady=(7, 0))
        self.var_board_name = tk.StringVar()
        self.name_field = ttk.Entry(cornice_n, textvariable=self.var_board_name,
                                    width=26, font=self.theme.f_text)
        self.name_field.pack(side="left")
        self.name_field.bind("<Return>", lambda _e: self.name_board())
        self.name_field.bind("<FocusOut>", lambda _e: self.name_board())
        self._note(cornice_n, "nome_scheda_nota", 0.5).pack(side="left", padx=8)
        self.msg_firmware = Message(self, s)
        self.msg_firmware.widget.grid(row=5, column=0, columnspan=3, sticky="w",
                                      pady=(7, 0))

        self.msg_connection = Message(self, s)
        self.msg_connection.widget.grid(row=6, column=0, columnspan=3, sticky="w",
                                          pady=(7, 0))
        if not serprog.HAS_SERIAL:
            self.msg_connection.show("seriale_assente", AMBER)
        return card

    # -- 2. chip -----------------------------------------------------------
    def _make_chip_card(self, parent):
        card, s = self._card(parent, "sez_chip")
        s.columnconfigure(2, weight=1)

        self.b_identify = self._translated(
            ttk.Button(s, style="Secondario.TButton", command=self.identify_chip),
            "identifica")
        self.b_identify.grid(row=0, column=0, sticky="w")
        self._micro_label(s, "chip_forzato").grid(row=0, column=1, sticky="e", padx=(10, 6))
        self.var_chip = tk.StringVar(value=self.settings.get("chip", ""))
        cornice_m = tk.Frame(s, background=T.PANEL)
        cornice_m.grid(row=0, column=2, sticky="ew")
        cornice_m.columnconfigure(0, weight=1)
        self.combo_chip = ttk.Combobox(cornice_m, textvariable=self.var_chip,
                                       font=self.theme.f_text,
                                       values=SUGGESTED_CHIPS + self.profile.chip)
        self.combo_chip.grid(row=0, column=0, sticky="ew")
        self.b_search_chip = self._translated(
            ttk.Button(cornice_m, style="Ghost.TButton",
                       command=self.search_model), "cerca")
        self.b_search_chip.grid(row=0, column=1, padx=(6, 0))
        self.combo_chip.bind("<<ComboboxSelected>>", lambda _e: self._invalidate_chip())
        self.combo_chip.bind("<KeyRelease>", lambda _e: self._invalidate_chip())

        self.msg_chip = Message(self, s)
        self.msg_chip.widget.grid(row=1, column=0, columnspan=3, sticky="w",
                                  pady=(7, 0))

        # La protezione occupa spazio solo quando ha qualcosa da dire: niente
        # etichetta fissa, e il tasto compare solo se c'e' un blocco da togliere.
        cornice_p = tk.Frame(s, background=T.PANEL)
        cornice_p.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(7, 0))
        self.msg_protection = Message(self, cornice_p)
        self.msg_protection.widget.pack(side="left")
        self.b_shifter = self._translated(
            ttk.Button(cornice_p, style="Ghost.TButton",
                       command=self.open_level_shifter), "tens_schema")
        self.b_shifter.pack(side="right")
        self.b_unlock = self._translated(
            ttk.Button(cornice_p, style="Secondario.TButton",
                       command=self.unlock_chip), "prot_sblocca")
        return card

    # -- 3. lettura --------------------------------------------------------
    def _make_read_card(self, parent):
        card, s = self._card(parent, "sez_lettura")
        s.columnconfigure(1, weight=1)

        self._micro_label(s, "cartella").grid(row=0, column=0, sticky="w")
        self.var_folder = tk.StringVar(
            value=self.settings.get("cartella") or default_folder())
        ttk.Entry(s, textvariable=self.var_folder,
                  font=self.theme.f_text).grid(row=0, column=1, sticky="ew",
                                               padx=(6, 4))
        self._browse_button(s, self.pick_folder).grid(row=0, column=2)

        frame = tk.Frame(s, background=T.PANEL)
        frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.b_leggi = self._translated(
            ttk.Button(frame, style="Primario.TButton",
                       command=self.read_and_verify), "leggi")
        self.b_leggi.pack(side="left")
        self._translated(ttk.Button(frame, style="Ghost.TButton",
                                   command=self.open_compare),
                        "conf_apri").pack(side="left", padx=6)
        self._note(frame, "leggi_nota", 0.5).pack(side="left", padx=8)

        self.msg_read = Message(self, s)
        self.msg_read.widget.grid(row=2, column=0, columnspan=3, sticky="w",
                                     pady=(7, 0))
        return card

    # -- 4. scrittura ------------------------------------------------------
    def _make_write_card(self, parent):
        card, s = self._card(parent, "sez_scrittura")
        s.columnconfigure(1, weight=1)

        self._micro_label(s, "modo").grid(row=0, column=0, sticky="w")
        cornice_m = tk.Frame(s, background=T.PANEL)
        cornice_m.grid(row=0, column=1, columnspan=2, sticky="w", padx=(6, 0))
        self.var_mode = tk.StringVar(value="regione")
        for value_for, key in (("regione", "modo_regione"), ("intero", "modo_intero")):
            b = ttk.Radiobutton(cornice_m, value=value_for, variable=self.var_mode,
                                command=self._update_write_state)
            b.pack(side="left", padx=(0, 12))
            self._translated(b, key)

        self.var_image = tk.StringVar(value=self.settings.get("immagine", ""))
        self.var_layout = tk.StringVar(value=self.settings.get("layout", ""))
        self.var_expected = tk.StringVar(value=self.settings.get("atteso", ""))
        for r, (key, variable, command) in enumerate((
                ("immagine", self.var_image, self.pick_image),
                ("file_layout", self.var_layout, self.pick_layout),
                ("atteso", self.var_expected, self.pick_expected),
        ), start=1):
            self._micro_label(s, key).grid(row=r, column=0, sticky="w", pady=(6, 0))
            e = ttk.Entry(s, textvariable=variable, font=self.theme.f_text)
            e.grid(row=r, column=1, sticky="ew", padx=(6, 4), pady=(6, 0))
            e.bind("<KeyRelease>", lambda _e: self._update_write_state())
            self._browse_button(s, command).grid(row=r, column=2, pady=(6, 0))
        self._note(s, "atteso_nota", 0.7).grid(row=4, column=1, sticky="w",
                                               padx=(6, 0))

        self.lbl_region = self._micro_label(s, "regione")
        self.lbl_region.grid(row=5, column=0, sticky="w", pady=(6, 0))
        self.var_region = tk.StringVar()
        self.combo_region = ttk.Combobox(s, textvariable=self.var_region, width=18,
                                          state="readonly", font=self.theme.f_text)
        self.combo_region.grid(row=5, column=1, sticky="w", padx=(6, 0), pady=(6, 0))
        self.b_regions = self._translated(
            ttk.Button(s, style="Ghost.TButton", command=self.derive_regions),
            "reg_ricava")
        self.b_regions.grid(row=5, column=2, sticky="w", pady=(6, 0))
        self.combo_region.bind("<<ComboboxSelected>>",
                                lambda _e: self._update_write_state())

        filetto = tk.Frame(s, background=T.LINE, height=1)
        filetto.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(11, 9))

        self.var_mains_off = tk.IntVar(value=0)
        self.check_mains_off = T.Checkbox(
            s, self.theme, self.var_mains_off,
            command=self._update_write_state, colour="#F0C9CB")
        self.checks_box = tk.Frame(s, background=T.PANEL)
        self.checks_box.grid(row=7, column=0, columnspan=3, sticky="w")
        self.check_mains_off.pack(in_=self.checks_box, anchor="w")
        self._translated(self.check_mains_off, "spunta_alimentazione",
                        attribute="testo")

        # ⚠️ Compare solo se il chip e' davvero a 1,8 V. Una casella sempre
        # presente si spunta per abitudine e non protegge nessuno.
        self.var_shifter = tk.IntVar(value=0)
        self.check_shifter = T.Checkbox(
            self.checks_box, self.theme, self.var_shifter,
            command=self._update_write_state, colour="#F0C9CB")
        self._translated(self.check_shifter, "check_shifter",
                        attribute="testo")

        actions = tk.Frame(s, background=T.PANEL)
        actions.grid(row=8, column=0, columnspan=3, sticky="w", pady=(9, 0))
        self.b_dry_run = self._translated(
            ttk.Button(actions, style="Secondario.TButton",
                       command=self.dry_run), "prova_secco")
        self.b_dry_run.pack(side="left", padx=(0, 8))
        self.b_write = self._translated(
            ttk.Button(actions, style="Pericolo.TButton", command=self.write),
            "scrivi")
        self.b_write.pack(side="left")

        self.msg_write = Message(self, s)
        self.msg_write.widget.grid(row=9, column=0, columnspan=3, sticky="w",
                                       pady=(7, 0))
        if self.var_layout.get():
            self._reload_regions()
        return card

    # -- mappa del chip ----------------------------------------------------
    def _make_map_card(self, parent):
        card, s = self._card(parent, "sez_mappa")
        s.columnconfigure(0, weight=1)

        self.chip_map = M.ChipMap(s, lines=8, on_position=self._map_position)
        self.chip_map.grid(row=0, column=0, sticky="ew")

        footer = tk.Frame(s, background=T.PANEL)
        footer.grid(row=1, column=0, sticky="ew", pady=(7, 0))
        self.legend = M.Legend(footer, self.theme, self.L)
        self.legend.pack(side="left")
        self.var_map_note = tk.StringVar()
        tk.Label(footer, textvariable=self.var_map_note, background=T.PANEL,
                 foreground="#55697C", font=(self.theme.mono, 7)).pack(side="right")
        self.after(200, self._map_at_rest)
        return card

    def _map_position(self, position):
        if position is None:
            self._map_at_rest()
        else:
            self.var_map_note.set(self.L("mappa_posizione", position=position))

    def _map_at_rest(self):
        blocks = max(self.chip_map.blocks, 1)
        self.var_map_note.set(self.L(
            "mappa_riposo",
            total_size=A.human_size(self.chip_map.total_size),
            blocks=blocks,
            grain=A.human_size(int(self.chip_map.total_size / float(blocks)))))

    def _prepare_map(self, span=None):
        """Azzera la mappa e, se si lavora su una regione, la evidenzia."""
        if self.chip and self.chip.size:
            self.chip_map.set_size(total_size=self.chip.size)
        self.chip_map.highlight(span)
        self._map_at_rest()

    # -- registro ----------------------------------------------------------
    def _make_log_card(self, parent):
        card, s = self._card(parent, "sez_registro")
        s.columnconfigure(0, weight=1)
        s.rowconfigure(0, weight=1)

        frame = tk.Frame(s, background=T.LOG_BG, highlightthickness=1,
                           highlightbackground=T.LINE)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.text = tk.Text(frame, height=6, wrap="none", font=self.theme.f_log,
                             background=T.LOG_BG, foreground="#C3D2DE",
                             insertbackground=T.FG, state="disabled",
                             relief="flat", bd=0, padx=8, pady=6,
                             selectbackground=T.ACCENT2)
        self.text.grid(row=0, column=0, sticky="nsew")
        bar = ttk.Scrollbar(frame, orient="vertical", command=self.text.yview)
        bar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=bar.set)
        self.text.tag_configure("ora", foreground=T.LOG_ORA)
        self.text.tag_configure("io", foreground="#7FB2FF")
        self.text.tag_configure("male", foreground="#FF8686")
        self.text.tag_configure("bene", foreground=T.LOG_OK)
        self.text.tag_configure("attenzione", foreground=T.WARN)

        buttons = tk.Frame(s, background=T.PANEL)
        buttons.grid(row=1, column=0, columnspan=2, sticky="w", pady=(7, 0))
        self.b_abort = self._translated(
            ttk.Button(buttons, style="Secondario.TButton",
                       command=self.abort), "interrompi")
        self.b_abort.pack(side="left")
        self.b_abort.state(["disabled"])
        self._translated(ttk.Button(buttons, style="Ghost.TButton",
                                   command=self.clear_log),
                        "pulisci").pack(side="left", padx=4)
        self._translated(ttk.Button(buttons, style="Ghost.TButton",
                                   command=self.save_log),
                        "salva_registro").pack(side="left")
        self.var_verbose = tk.IntVar(value=1 if self.settings.get("dettagli") else 0)
        T.Checkbox(buttons, self.theme, self.var_verbose, text="-V").pack(
            side="left", padx=12)
        return card

    # -- barra di stato ----------------------------------------------------
    def _costruisci_barra(self, parent):
        self.bar = tk.Frame(parent, background=T.INK)
        self.bar.columnconfigure(1, weight=1)
        self.progress = ttk.Progressbar(
            self.bar, mode="indeterminate", length=130,
            style="Sottile.Horizontal.TProgressbar")
        self.progress.grid(row=0, column=0, sticky="w")
        self.progress.configure(mode="determinate", value=0)
        self.var_status = tk.StringVar(value=self.L("pronto"))
        tk.Label(self.bar, textvariable=self.var_status, background=T.INK,
                 foreground=T.MUT, font=self.theme.f_text).grid(
            row=0, column=1, sticky="w", padx=10)
        self.var_flashrom = tk.StringVar()
        tk.Label(self.bar, textvariable=self.var_flashrom, background=T.INK,
                 foreground="#4F657A", font=(self.theme.mono, 7)).grid(
            row=0, column=2, sticky="e")

    # ------------------------------------------------------------ lingua
    def _language_changed(self, _evento=None):
        scelto = self.var_language.get()
        for code, name in LANGUAGE_NAMES.items():
            if name == scelto:
                self.L.code = code
                break
        self._retranslate()

    def _speed_changed(self, _evento=None):
        label_for = self.var_speed_label.get()
        for value_for, text in SPEED_LABELS.items():
            if text == label_for:
                self.var_speed.set(value_for)
                break
        self._invalidate_read()

    def open_level_shifter(self):
        level_shifter.open_window(self, self.theme, self.L)

    def open_wiring(self):
        wiring.open_window(self, self.theme, self.L,
                    clip=self.profile.connection == profiles.CLIP)

    def open_compare(self):
        compare.open_window(self, self.theme, self.L, self.var_folder.get().strip())

    # -------------------------------------------------------- flashrom
    def _imposta_flashrom(self, path, silenzioso=False):
        candidato = fr.Flashrom(path)
        version = candidato.version()
        if version is None:
            if not silenzioso:
                messagebox.showerror(self.L("titolo"), self.L("flashrom_non_valido"))
            return False
        self.flash = candidato
        self.flashrom_version = version
        return True

    def pick_flashrom(self):
        path = filedialog.askopenfilename(
            title=self.L("flashrom_scegli"),
            filetypes=[("flashrom.exe", "flashrom.exe"), ("*", "*.*")])
        if path and self._imposta_flashrom(path):
            self._update_flashrom_banner()
            self._update_write_state()
            self._save_config()

    def _update_flashrom_banner(self):
        if self.flash:
            self.banner.grid_remove()
            chunks = self.flashrom_version.split()
            self.var_flashrom.set(self.L("flashrom_trovato",
                                         version=chunks[1] if len(chunks) > 1 else "",
                                         path=self.flash.path))
        else:
            self.banner.grid(row=2, column=0, columnspan=2, sticky="ew",
                             padx=8, pady=(8, 0))
            self.var_flashrom.set("")
        for bottone in (self.b_identify, self.b_leggi, self.b_qualify):
            bottone.state(["!disabled"] if self.flash and not self.busy
                          else ["disabled"])


    # ------------------------------------------------- firmware del Pico
    def _percorso_firmware(self):
        """pico_serprog.uf2: dentro l'eseguibile, accanto, in firmware\\."""
        for root in (getattr(sys, "_MEIPASS", None), app_folder()):
            if not root:
                continue
            for candidato in (os.path.join(root, "firmware", pico.FIRMWARE_NAME),
                              os.path.join(root, pico.FIRMWARE_NAME)):
                if os.path.isfile(candidato):
                    return candidato
        return None

    def _watch_bootsel(self):
        """Ogni due secondi: c'e' una scheda che aspetta il firmware?"""
        if not self.busy:
            try:
                boards = pico.boards_in_bootsel()
            except Exception:                          # noqa: BLE001
                boards = []
            newer = boards[0] if boards else None
            before = self.bootsel_board.drive if self.bootsel_board else None
            adesso = newer.drive if newer else None
            if adesso != before:
                if newer is None:
                    pico.forget_serials()
                self.bootsel_board = newer
                if newer:
                    self.log("   RP2040 in BOOTSEL su %s (%s)" % (
                        newer.letter, newer.board_id), "io")
                self._update_firmware_row()
            self._ask_version_once()
        self.bootsel_watch = self.after(2000, self._watch_bootsel)

    # ------------------------------------------------------- profilo
    def _write_reminder(self):
        """La regola fissa, piu' le avvertenze proprie di questa scheda."""
        lines = [self.L("promemoria")]
        lines += [self.L(key) for key in self.profile.avvisi]
        self.lbl_reminder.configure(text="  ".join(lines))

    def _load_chip_list(self, poi=None):
        """Chiede a flashrom l\u0027elenco dei chip, in un thread a parte.

        ⚠️ Sono seicento righe da spremere e costano mezzo secondo: farlo
        all\u0027avvio, nel thread della finestra, si vedrebbe.
        """
        if self.known_chips or not self.flash:
            if poi:
                poi()
            return

        def work():
            try:
                return self.flash.chip_list()
            except Exception:                          # noqa: BLE001
                return []

        def end(listing):
            self.known_chips = listing
            self._fill_models()
            if poi:
                poi()

        threading.Thread(
            target=lambda: self.tail_of.put(("chiamata", end, work())),
            daemon=True).start()

    def _fill_models(self):
        """La tendina: prima i modelli del profilo, poi tutti gli SPI noti."""
        values = list(SUGGESTED_CHIPS) + list(self.profile.chip)
        visti = set(v for v in values)
        for chip in self.known_chips:
            if chip.spi and chip.name not in visti:
                visti.add(chip.name)
                values.append(chip.name)
        self.combo_chip.configure(values=values)

    def search_model(self):
        """Apre la ricerca fra i modelli, caricando l\u0027elenco se serve."""
        def open_window():
            if not self.known_chips:
                self.msg_chip.show("cerca_vuoto", AMBER)
                return
            chip_search.open_window(self, self.theme, self.L, self.known_chips,
                         self._model_picked, self.var_chip.get().strip())

        self._load_chip_list(poi=open_window)

    def _model_picked(self, chip):
        self.var_chip.set(chip.name)
        self._invalidate_chip()
        self._check_voltage(chip.name)
        self.log("   %s" % self.L(
            "cerca_scelto", vendor=chip.vendor, chip=chip.name,
            size_text=A.human_size(chip.size) if chip.size else "?"), "io")

    def _fill_profiles(self):
        names_of = profiles.names_of(self.L.code)
        self.combo_profile.configure(values=[n for _c, n in names_of])
        self.var_profile.set(self.profile.text("name", self.L.code))

    def _profile_changed(self, _evento=None):
        scelto = self.var_profile.get()
        for key, name in profiles.names_of(self.L.code):
            if name == scelto:
                self.profile = profiles.by_key(key)
                break
        self._fill_models()
        self._invalidate_chip()
        self._write_reminder()
        self._draw_header()
        self._save_config()
        self.log("→ %s" % self.profile.text("name", self.L.code), "io")
        self.msg_chip.raw_text(
            self.profile.text("description", self.L.code), GREY)

    def _known_fingerprint(self, md5):
        """Come si chiama questa immagine, se il profilo la conosce."""
        entry = self.profile.md5.get(md5)
        if not entry:
            return None
        return entry.get(self.L.code) or entry.get("it")

    def _profile_deviations(self):
        """Dove la scheda vera si scosta da quello che il profilo prevede."""
        nomi_regioni = [n for n, _a, _b in getattr(self, "regioni", ())]
        return profiles.deviations(
            self.profile,
            found_chip=self.chip.name if self.chip else None,
            found_size=self.chip.size if self.chip else None,
            regions=nomi_regioni)

    def _update_firmware_row(self, con_messaggio=True):
        # il rientro in BOOTSEL si offre solo se c'e' un programmatore collegato
        port = self._programmer_port()
        if port is None:
            # niente programmatore, niente versione: quella di prima non vale
            self.board_firmware = None
        self.b_bootsel.state(["!disabled"] if port and not self.busy
                             else ["disabled"])

        # il campo del nome segue la scheda che si sta guardando
        run, boot, _translated = self._current_board()
        name = self.known_boards.name(run=run, boot=boot) or ""
        if not self.name_field.focus_get() is self.name_field:
            self.var_board_name.set(name)
        self.name_field.state(["!disabled"] if (run or boot) else ["disabled"])

        card = self.bootsel_board
        if card is None:
            shipped = self._shipped_version()
            vecchia = (port is not None and shipped
                       and serprog.is_older(self.board_firmware, shipped))
            if con_messaggio:
                if port is None or self.board_firmware is None:
                    self.msg_firmware.show("fw_nessuna", GREY)
                elif not vecchia:
                    self.msg_firmware.show("fw_versione_ok", GREEN,
                                             version=self.board_firmware or "?")
                elif self.board_firmware:
                    self.msg_firmware.show("fw_versione_vecchia", AMBER,
                                             version=self.board_firmware,
                                             newer=shipped)
                else:
                    self.msg_firmware.show("fw_versione_muta", AMBER,
                                             newer=shipped)
            if vecchia:
                self.b_update.pack(side="left", padx=(6, 0))
                self.b_update.state(["!disabled"] if not self.busy
                                      else ["disabled"])
            else:
                self.b_update.pack_forget()
            self.b_firmware.state(["disabled"])
            self.b_reset.state(["disabled"])
            return
        self.b_update.pack_forget()
        firmware = self._percorso_firmware()
        if not firmware:
            self.msg_firmware.show("fw_assente", AMBER)
        elif name:
            self.msg_firmware.show("fw_trovata_nome", GREEN, name=name,
                                     model=card.model,
                                     drive=card.letter,
                                     serial=card.serial or "?")
        else:
            self.msg_firmware.show("fw_trovata_anonima", GREEN,
                                     model=card.model,
                                     drive=card.letter,
                                     serial=card.serial or "?")
        enabled = ["!disabled"] if not self.busy else ["disabled"]
        self.b_reset.state(enabled)
        self.b_firmware.state(enabled if firmware else ["disabled"])

    def name_board(self):
        """Da' un nome alla scheda che si sta guardando. Vuoto = la dimentica."""
        run, boot, _e = self._current_board()
        if not (run or boot):
            return
        name = self.var_board_name.get().strip()
        before = self.known_boards.name(run=run, boot=boot) or ""
        if name == before:
            return
        self.known_boards.set_name(name, run=run, boot=boot)
        self._save_config()
        self.detect_ports()
        if name:
            self.msg_firmware.show("fw_battezzata", GREEN, name=name)
        else:
            self.msg_firmware.show("fw_dimenticata", GREY)

    def _program_board(self, uf2_path, chiave_avvio, chiave_fine, aspetta_porta):
        """Copia un .uf2 sulla scheda e racconta com'e' andata."""
        card = self.bootsel_board
        if card is None or not uf2_path:
            return

        # ⚠️ Le porte serprog gia' presenti si annotano PRIMA: dopo si aspetta
        # una porta NUOVA. Cercandone una qualunque, con un programmatore gia'
        # collegato si direbbe "fatto" anche a copia fallita.
        before = set(d for d, _n, likely, _s in serprog.list_serial_ports() if likely)

        def work():
            self._message_from_thread(self.msg_firmware, chiave_avvio, AMBER)
            done, reason = pico.install(uf2_path, card,
                                          on_line=self._line_from_thread)
            if not done:
                return ("errore", reason, None)
            if not aspetta_porta:
                return ("fatto", None, None)
            self._message_from_thread(self.msg_firmware, "fw_attendo", GREY)
            # la scheda riparte come porta seriale: le si da' tempo
            for _ in range(30):
                time.sleep(0.5)
                adesso = set(d for d, _n, likely, _s in serprog.list_serial_ports()
                             if likely)
                for device in sorted(adesso - before):
                    diagnostics = serprog.query(device, BAUD)
                    if diagnostics.ok and diagnostics.speaks_spi:
                        return ("pronto", device, diagnostics)
            return ("muto", None, None)

        def end(outcome):
            state, datum, diagnostics = outcome
            self.bootsel_board = None
            if state == "errore":
                self.msg_firmware.show("fw_errore", RED, reason=datum)
            elif state == "pronto":
                # ⚠️ Qui e' l'unico momento in cui i due identificativi della
                # stessa scheda si toccano: era in BOOTSEL, ora e' quella porta.
                if card.serial:
                    seriale_run = self._serial_of_port(datum)
                    if seriale_run:
                        self.known_boards.link(seriale_run, card.serial)
                        self._save_config()
                self.msg_firmware.show("fw_pronto", GREEN, port=datum)
                self.log("   %s, iface v%s, bus %s" % (
                    diagnostics.name, diagnostics.version,
                    diagnostics.readable_bus), "bene")
                self.detect_ports()
            elif state == "muto":
                self.msg_firmware.show("fw_non_riappare", AMBER)
            else:
                self.msg_firmware.show(chiave_fine, GREEN)
            # ⚠️ senza questo, il riepilogo cancellerebbe l'esito appena letto
            self._update_firmware_row(con_messaggio=False)

        self._start_job(work, end, "firmware")

    def _shipped_version(self):
        """La versione dell'UF2 che abbiamo qui dentro."""
        path = self._percorso_firmware()
        if not path:
            return None
        return pico.shipped_version(os.path.dirname(path))

    def _note_firmware(self, diagnostics, serial=None):
        """Registra cosa dichiara la scheda interrogata."""
        if diagnostics is None or not diagnostics.ok:
            return
        self.board_firmware = diagnostics.firmware or ""
        if serial:
            self.firmware_asked.add(serial)

    def _ask_version_once(self):
        """Una volta per scheda, non a ogni giro: apre e chiude la porta.

        ⚠️ Nessuno puo' dire da fuori che firmware c'e' su un RP2040: il
        seriale USB e' quello del chip e non cambia mai. Va chiesto alla
        scheda, e la scheda risponde solo dalla 1.1 in poi.
        """
        if self.busy:
            return
        port = self._programmer_port()
        if not port:
            return
        serial = self._serial_of_port(port)
        if serial and serial in self.firmware_asked:
            return
        diagnostics = serprog.query(port, BAUD)
        if diagnostics.ok:
            self._note_firmware(diagnostics, serial)
            self._update_firmware_row()

    def _programmer_port(self):
        """La porta di un programmatore collegato adesso, se c'e'."""
        for device, _descrizione, likely, _seriale in serprog.list_serial_ports():
            if likely:
                return device
        return None

    def _serial_of_port(self, port):
        for device, _d, _s, serial in serprog.list_serial_ports():
            if device == port:
                return serial
        return None

    def _current_board(self):
        """(chiave_run, chiave_boot, etichetta) di cio' che si sta guardando.

        In BOOTSEL comanda la scheda-disco; altrimenti il programmatore
        collegato. Sono due identificativi diversi della stessa cosa, vedi
        boards.py.
        """
        if self.bootsel_board is not None:
            boot = self.bootsel_board.serial
            return None, boot, boot
        port = self._programmer_port()
        if port:
            run = self._serial_of_port(port)
            return run, None, run
        return None, None, None

    def back_to_bootsel(self):
        """Rimette il programmatore in modalita' aggiornamento, da software."""
        port = self._programmer_port()
        if not port:
            return
        seriale_prima = self._serial_of_port(port)

        def work():
            self._message_from_thread(self.msg_firmware, "fw_bootsel_provo",
                                      AMBER, port=port)
            pico.back_to_bootsel(port)
            # ⚠️ L'esito non si legge dall'apertura della porta, che fallisce
            # apposta: si guarda se la scheda ricompare come disco.
            for _ in range(20):
                time.sleep(0.5)
                boards = pico.boards_in_bootsel()
                if boards:
                    return ("bootsel", boards[0], None)
            return ("niente", None, None)

        def end(outcome):
            state, card, _ = outcome
            if state == "bootsel":
                # stessa cosa al contrario: era quella porta, ora e' quel disco
                if seriale_prima and card.serial:
                    self.known_boards.link(seriale_prima, card.serial)
                    self._save_config()
                self.bootsel_board = card
                self.msg_firmware.show("fw_bootsel_ok", GREEN,
                                         drive=card.letter)
                self.detect_ports()
            else:
                self.msg_firmware.show("fw_bootsel_no", AMBER)
            self._update_firmware_row()

        self._start_job(work, end, "bootsel")

    def update_firmware(self):
        """Rientro in BOOTSEL, copia, e ricontrollo: tre passi, un tasto.

        ⚠️ Il rientro da software esiste solo dalla 1.1. Una scheda piu'
        vecchia non torna in BOOTSEL da sola e va premuto il pulsante, una
        volta: dopo quell\u0027aggiornamento non serve piu'.
        """
        port = self._programmer_port()
        path = self._percorso_firmware()
        if not (port and path):
            return
        seriale_prima = self._serial_of_port(port)
        # la porta della scheda che stiamo aggiornando sparisce e torna: non
        # va contata fra quelle "gia' presenti", o non la vedremmo tornare
        before = set(d for d, _n, likely, _s in serprog.list_serial_ports()
                    if likely)
        before.discard(port)

        def work():
            self._message_from_thread(self.msg_firmware, "fw_aggiorno", AMBER)
            pico.back_to_bootsel(port)
            card = None
            for _ in range(20):
                time.sleep(0.5)
                boards = pico.boards_in_bootsel()
                if boards:
                    card = boards[0]
                    break
            if card is None:
                return ("no_bootsel", None, None)
            self._message_from_thread(self.msg_firmware, "fw_installando",
                                      AMBER)
            done, reason = pico.install(path, card,
                                          on_line=self._line_from_thread)
            if not done:
                return ("errore", reason, card)
            self._message_from_thread(self.msg_firmware, "fw_attendo", GREY)
            for _ in range(30):
                time.sleep(0.5)
                adesso = set(d for d, _n, likely, _s in serprog.list_serial_ports()
                             if likely)
                for device in sorted(adesso - before):
                    diagnostics = serprog.query(device, BAUD)
                    if diagnostics.ok and diagnostics.speaks_spi:
                        return ("pronto", (device, diagnostics), card)
            return ("muto", None, card)

        def end(outcome):
            state, datum, card = outcome
            if card is not None and seriale_prima and card.serial:
                self.known_boards.link(seriale_prima, card.serial)
                self._save_config()
            self.bootsel_board = None
            if state == "no_bootsel":
                self.msg_firmware.show("fw_aggiorna_no_bootsel", AMBER)
            elif state == "errore":
                self.msg_firmware.show("fw_errore", RED, reason=datum)
            elif state == "muto":
                self.msg_firmware.show("fw_non_riappare", AMBER)
            else:
                device, diagnostics = datum
                self._note_firmware(diagnostics,
                                      self._serial_of_port(device))
                shipped = self._shipped_version()
                # ⚠️ Non basta che la copia sia riuscita: la versione la deve
                # dichiarare la scheda, dopo essere ripartita.
                if diagnostics.firmware == shipped:
                    self.msg_firmware.show("fw_aggiornato", GREEN,
                                             version=diagnostics.firmware,
                                             port=device)
                else:
                    self.msg_firmware.show("fw_aggiorna_dubbio", RED,
                                             version=diagnostics.firmware
                                             or diagnostics.name)
                self.detect_ports()
            self._update_firmware_row(con_messaggio=False)

        self._start_job(work, end, "aggiornamento firmware")

    def install_firmware(self):
        self._program_board(self._percorso_firmware(), "fw_installando",
                        "fw_pronto", aspetta_porta=True)

    def reset_board(self):
        """Riporta la scheda allo stato di fabbrica. Il .uf2 lo generiamo noi.

        ⚠️ DUE CONSENSI, e il secondo e' legato al SERIALE: con tre schede
        identiche sul tavolo, la domanda «sei sicuro?» non dice niente su QUALE
        stai cancellando. Ribattere le ultime quattro cifre obbliga a guardare
        quella giusta.
        """
        card = self.bootsel_board
        if card is None:
            return
        name = self.known_boards.name(boot=card.serial)
        who = "%s · %s" % (name, card.serial) if name else (
            card.serial or "%s su %s" % (card.model, card.letter))

        first = self.L("fw_azzera_uno", who=who, size=A.human_size(pico.FLASH_PICO))
        if not Confirm(self, self.L, first, self.theme,
                        word=self.L("parola_cancella")).confirmed:
            return

        if card.serial:
            second = self.L("fw_azzera_due", drive=card.letter,
                             serial=card.serial)
            word = boards.tail_of(card.serial)
        else:
            second = self.L("fw_azzera_due_senza", drive=card.letter)
            word = self.L("parola_cancella")
        if not Confirm(self, self.L, second, self.theme,
                        word=word).confirmed:
            return
        path = os.path.join(config_folder(), "azzera.uf2")
        try:
            os.makedirs(config_folder(), exist_ok=True)
            pico.make_eraser(path)
        except OSError as e:
            self.msg_firmware.show("fw_errore", RED, reason="%s" % e)
            return
        self._program_board(path, "fw_azzerando", "fw_azzerato",
                        aspetta_porta=False)

    # ------------------------------------------------------------ porte
    def detect_ports(self):
        ports = serprog.list_serial_ports()
        values = []
        for device, description, likely, serial in ports:
            # il nome dato alla scheda vale piu' della descrizione di Windows
            name = self.known_boards.name(run=serial) if serial else None
            if name:
                values.append("%s — %s · %s" % (device, name, serial))
            elif likely and serial:
                values.append("%s — %s · %s" % (device, description, serial))
            else:
                values.append("%s — %s" % (device, description))
        self.combo_port.configure(values=values)
        if ports:
            current = self._chosen_port()
            candidate = next((v for v, p in zip(values, ports) if p[2]), values[0])
            programmatori = [p[0] for p in ports if p[2]]
            # ⚠️ Non basta che la porta salvata esista ancora: se quella scelta
            # NON e' un programmatore e uno collegato c'e', si passa a quello.
            # Altrimenti, dopo che il Pico sparisce e torna, resta selezionata
            # una porta qualunque (Bluetooth, seriale di sistema).
            if (not current or current not in [p[0] for p in ports]
                    or (programmatori and current not in programmatori)):
                self.var_port.set(candidate)
            else:
                # ⚠️ La porta e' la stessa ma la SCRITTA puo' essere cambiata:
                # dopo aver battezzato una scheda restava esposta la vecchia
                # descrizione di Windows, e il nome dato sembrava perso.
                for value_for, port in zip(values, ports):
                    if port[0] == current and value_for != self.var_port.get():
                        self.var_port.set(value_for)
                        break
        elif serprog.HAS_SERIAL:
            self.msg_connection.show("nessuna_porta", AMBER)

    def _chosen_port(self):
        text = (self.var_port.get() or "").strip()
        return text.split("—")[0].strip() if "—" in text else text

    def query_pico(self):
        port = self._chosen_port()
        if not port:
            self.msg_connection.show("nessuna_porta", AMBER)
            return
        self.log("→ serprog: %s" % port, "io")
        diagnostics = serprog.query(port, BAUD)
        if not diagnostics.ok:
            self.msg_connection.show("pico_non_apre", RED,
                                         port=port, reason=diagnostics.error)
            return
        self.msg_connection.show(
            "pico_riconosciuto", GREEN if diagnostics.speaks_spi else AMBER,
            name=diagnostics.name, version=diagnostics.version,
            bus=diagnostics.readable_bus)
        self.log("   %s, iface v%s, bus %s" % (
            diagnostics.name, diagnostics.version, diagnostics.readable_bus))
        self._note_firmware(diagnostics, self._serial_of_port(port))
        self._update_firmware_row(con_messaggio=False)
        if not diagnostics.speaks_spi:
            self.msg_connection.show("pico_no_spi", RED)

    # ------------------------------------------------------------- chip
    def _invalidate_chip(self):
        self.chip = None
        self.chip_is_1v8 = None
        if hasattr(self, "check_shifter"):
            self.check_shifter.pack_forget()
        self.protection = None
        if hasattr(self, "msg_protection"):
            self._show_protection()
        self._invalidate_read()

    def _invalidate_read(self):
        self.verified_read = None
        self._update_write_state()

    def identify_chip(self):
        port = self._chosen_port()
        if not self.flash or not port:
            return

        def work():
            result, chip = self.flash.identify(
                port, BAUD, self.var_speed.get() or None,
                self.var_chip.get().strip() or None,
                bool(self.var_verbose.get()), self._line_from_thread)
            protection = None
            if result.ok and chip.name:
                # ⚠️ Si chiede SUBITO: e' il modo piu' comune in cui una
                # scrittura non passa, e scoprirlo dopo la cancellazione e'
                # tardi.
                _e, protection = self.flash.protection(
                    port, BAUD, self.var_speed.get() or None,
                    chip.name, bool(self.var_verbose.get()),
                    self._line_from_thread)
            identity = None
            if not (result.ok and chip.name) and not chip.candidates:
                # ⚠️ Solo qui: se flashrom ha riconosciuto il chip, chiederlo
                # una seconda volta non aggiunge niente e tocca i fili per
                # niente.
                identity = serprog.identify_chip(port, BAUD)
            return result, chip, protection, identity

        def end(outcome):
            result, chip, protection, identity = outcome
            if chip.candidates:
                self.combo_chip.configure(values=SUGGESTED_CHIPS + chip.candidates)
                self.msg_chip.show("chip_ambiguo", AMBER)
                return
            if not result.ok or not chip.name:
                self.msg_chip.show("chip_non_trovato", RED)
                self._report_identity(identity)
                return
            self.chip = chip
            self.protection = protection
            self.msg_chip.show("chip_trovato", GREEN, chip=chip.description)
            self._check_voltage(chip.name)
            # ⚠️ Uno scostamento dal profilo si dice e basta: non si blocca
            # niente. Chi ha la scheda davanti ne sa piu' di una tabella.
            for key, fields in self._profile_deviations():
                self.log("   %s" % self.L(key, **fields), "attenzione")
            self._show_protection()
            self._update_write_state()

        self._start_job(work, end, "identifica")

    def _check_voltage(self, name):
        """Dal modello si capisce a che tensione lavora il chip.

        ⚠️ Non c\u0027e\u0027 modo di misurarla da qui, ma il nome basta: nelle
        famiglie SPI NOR la versione a 1,8 V si distingue da una lettera. E
        sbagliare tensione non da\u0027 un errore: da\u0027 un chip morto.
        """
        volts, family = V.voltage_of(name)
        self.chip_is_1v8 = None if volts is None else (volts == V.LOW)
        if self.chip_is_1v8:
            self.log("!! %s" % self.L("tens_bassa", family=family),
                          "male")
            self.check_shifter.pack(anchor="w", pady=(5, 0))
        else:
            self.check_shifter.pack_forget()
            self.var_shifter.set(0)
            if volts is None:
                self.log("   %s" % self.L("tens_ignota"), "attenzione")
            else:
                self.log("   %s" % self.L("tens_alta", family=family))
        self._update_write_state()

    def _report_identity(self, identity):
        """Cosa ha risposto il chip quando gliel\u0027abbiamo chiesto noi.

        ⚠️ Serve a separare due guai che sembrano lo stesso: un chip che
        flashrom non conosce, e un chip che non c\u0027e\u0027. Nel primo caso si
        forza un modello simile e si va avanti; nel secondo si rifanno i
        collegamenti, e provare modelli a caso non porta da nessuna parte.
        """
        if identity is None:
            return
        if not identity.ok:
            self.log("   %s" % self.L("jedec_errore",
                                           reason=identity.error), "attenzione")
            return
        if not identity.answers:
            self.msg_chip.show("jedec_muto", RED)
            self.log("   %s (JEDEC %s)" % (self.L("jedec_muto"),
                                                identity.jedec), "male")
            return
        self.msg_chip.show("jedec_risponde", AMBER,
                             description=identity.description())
        self.log("   %s" % self.L("jedec_risponde",
                                       description=identity.description()),
                      "attenzione")

    def _show_protection(self):
        p = self.protection
        if p is None:
            self.msg_protection.clean()
            self.b_unlock.pack_forget()
            return
        if not p.supported:
            self.msg_protection.show("prot_ignota", GREY)
            self.b_unlock.pack_forget()
            return
        if not p.active:
            self.msg_protection.show("prot_libera", GREEN)
            self.b_unlock.pack_forget()
            return
        self.b_unlock.pack(side="right", padx=(10, 8))
        span = self._region_span()
        scontro = span and p.overlaps(span[0], span[1])
        if scontro:
            self.msg_protection.show("prot_scontro", RED,
                                       start=p.start, end=p.end)
        else:
            self.msg_protection.show("prot_attiva", AMBER, start=p.start,
                                       end=p.end, description=p.description,
                                       mode=p.mode)
        self.b_unlock.state(["!disabled"] if not self.busy else ["disabled"])

    def unlock_chip(self):
        """Toglie la protezione. Cambia lo stato del chip: si chiede prima."""
        port = self._chosen_port()
        if not (self.flash and port and self.chip):
            return
        text = self.L("prot_conferma", chip=self.chip.description)
        if not Confirm(self, self.L, text, self.theme,
                        word=self.L("parola_sblocca")).confirmed:
            return

        def work():
            common = dict(port=port, baud=BAUD,
                          spispeed=self.var_speed.get() or None,
                          chip=self._chip_for_flashrom(),
                          verbose=bool(self.var_verbose.get()),
                          on_line=self._line_from_thread)
            result = self.flash.unlock(**common)
            _e, after = self.flash.protection(**common)
            return result, after

        def end(outcome):
            result, after = outcome
            self.protection = after
            if after is not None and not after.active:
                self.log("   %s" % self.L("prot_sbloccato"), "bene")
            else:
                self.msg_protection.show("prot_non_tolta", RED,
                                           code=result.code)
                self.log("!! %s" % self.L("prot_non_tolta",
                                               code=result.code), "male")
                self._update_write_state()
                return
            self._show_protection()
            self._update_write_state()

        self._start_job(work, end, "sblocco")

    # ---------------------------------------------------------- lettura
    def read_and_verify(self):
        port = self._chosen_port()
        if not self.flash or not port:
            return
        folder = self.var_folder.get().strip()
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as e:
            self.msg_read.raw_text("%s" % e, RED)
            return

        stamp = timestamp()
        first = os.path.join(folder, "%s-letto-%s.rom"
                             % (self.profile.key, stamp))
        second = os.path.join(folder, "%s-verifica-%s.rom"
                               % (self.profile.key, stamp))

        self._prepare_map()
        self.read_span = (0, (self.chip.size if self.chip and self.chip.size
                                       else 16 * 1024 * 1024) - 1)

        def work():
            common = dict(port=port, baud=BAUD,
                          spispeed=self.var_speed.get() or None,
                          chip=self._chip_for_flashrom(),
                          verbose=bool(self.var_verbose.get()),
                          on_line=self._line_from_thread,
                          on_event=self._evento_da_thread)
            self._message_from_thread(self.msg_read, "lettura_1", GREY)
            result = self.flash.read(first, **common)
            if not result.ok:
                return ("errore", result, None, None)
            self._message_from_thread(self.msg_read, "lettura_2", GREY)
            result = self.flash.read(second, **common)
            if not result.ok:
                return ("errore", result, None, None)
            return ("ok", result, md5_of_file(first), md5_of_file(second))

        def end(outcome):
            state, result, a, b = outcome
            if state == "errore":
                self._flashrom_failed(self.msg_read, result)
                return
            if a != b:
                self.msg_read.show("lettura_diversa", RED, a=a[:8], b=b[:8])
                self.log("!! letture diverse: %s != %s" % (a, b), "male")
                return
            self.verified_read = a
            self.read_path = first
            self.dry = None          # cambiata la base, la prova va rifatta
            self.chip_map.mark(0, self.read_span[1], M.VERIFIED)
            try:
                os.remove(second)
            except OSError:
                pass
            self.msg_read.show("lettura_ok", GREEN, md5=a)
            self.log("   %s" % self.L("lettura_salvata", path=first), "bene")
            nota = self._known_fingerprint(a)
            self.log("   %s" % self.L(
                "riconosciuto_come",
                what=nota or self.L("md5_sconosciuto")))
            expected = os.path.join(folder, "%s-risultato-atteso.rom"
                                  % self.profile.key)
            if not self.var_expected.get() and os.path.isfile(expected):
                self.var_expected.set(expected)
            self._compare_with_previous(folder, first)
            self._update_write_state()

        self._start_job(work, end, "lettura")

    def _previous_reads(self, folder, escluso=None):
        """I backup gia' presenti in cartella, dal piu' recente."""
        prefisso = "%s-letto-" % self.profile.key
        found_items = []
        try:
            names_of = os.listdir(folder)
        except OSError:
            return []
        for name in names_of:
            if not (name.startswith(prefisso) and name.endswith(".rom")):
                continue
            path = os.path.join(folder, name)
            if escluso and os.path.abspath(path) == os.path.abspath(escluso):
                continue
            try:
                found_items.append((os.path.getmtime(path), path))
            except OSError:
                continue
        found_items.sort(reverse=True)
        return [p for _t, p in found_items]

    def _compare_with_previous(self, folder, appena_letto):
        """Confronta la lettura appena fatta con il backup precedente.

        ⚠️ Serve a rispondere a una domanda che viene sempre e a cui nessuno
        sa rispondere a memoria: «questo chip e\u0027 ancora come l\u0027ho
        lasciato?». Il confronto lo fa il programma, non l\u0027occhio su due
        md5 lunghi trentadue cifre.
        """
        precedenti = self._previous_reads(folder, escluso=appena_letto)
        if not precedenti:
            self.log("   %s" % self.L("conf_primo"))
            return
        before = precedenti[0]
        name = A.file_name(before)
        try:
            vecchia = A.read(before)
            newer = A.read(appena_letto)
        except OSError:
            return
        if len(vecchia) != len(newer):
            self.log("   %s" % self.L("conf_altra_misura", file=name),
                          "attenzione")
            return
        result = A.compare_images(vecchia, newer)
        spans = result["allineati"]
        if result["uguali"] or not spans:
            self.log("   %s" % self.L("conf_uguale", file=name), "bene")
            return
        start = min(a for a, _b in spans)
        end = max(b for _a, b in spans)
        how_many = len(result["blocchi"])
        self.log("   %s" % self.L("conf_diverso", file=name, how_many=how_many,
                                       start=start, end=end), "attenzione")
        for a, b in spans[:8]:
            self.log("      0x%06X-0x%06X  %s" % (
                a, b, A.human_size(b - a + 1)))

    def _flashrom_failed(self, message, result):
        """Quando flashrom si rifiuta: dirlo chiaro e lasciare il dettaglio nel
        registro, che c'e' gia' finito riga per riga."""
        if result.aborted:
            message.raw_text(self.L("interrotto"), AMBER)
            return
        if result.error:
            message.raw_text(result.error, RED)
            return
        message.show("lettura_fallita", RED, code=result.code)

    def _chip_for_flashrom(self):
        forzato = self.var_chip.get().strip()
        if forzato:
            return forzato
        return self.chip.name if self.chip and self.chip.name else None

    # ------------------------------------------------- qualifica del cavo
    def qualify_link(self):
        """Cerca la velocita' piu' alta che dia due letture identiche.

        Legge una regione piccola invece di tutto il chip: la stessa domanda,
        in pochi secondi invece che in minuti.
        """
        port = self._chosen_port()
        if not self.flash or not port:
            return
        folder = self.var_folder.get().strip()
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as e:
            self.msg_connection.raw_text("%s" % e, RED)
            return

        total_size = self.chip.size if self.chip and self.chip.size else 16 * 1024 * 1024
        prova_byte = min(QUALIFY_BYTES, total_size)
        layout = os.path.join(folder, "qualifica-layout.txt")
        with open(layout, "wb") as f:
            f.write(("%08x:%08x prova\n%08x:%08x resto\n" % (
                0, prova_byte - 1, prova_byte, total_size - 1)).encode("ascii"))
        first = os.path.join(folder, "qualifica-a.bin")
        second = os.path.join(folder, "qualifica-b.bin")
        self._prepare_map()
        self.read_span = (0, prova_byte - 1)

        def work():
            for speed in SPEEDS:
                label_for = SPEED_LABELS[speed]
                self._message_from_thread(self.msg_connection,
                                          "qualifica_prova", GREY,
                                          speed=label_for)
                common = dict(port=port, baud=BAUD,
                              spispeed=speed or None,
                              chip=self._chip_for_flashrom(),
                              verbose=bool(self.var_verbose.get()),
                              on_line=self._line_from_thread,
                              on_event=self._evento_da_thread)
                a = self.flash.read_region(layout, "prova", first, **common)
                if self.stop_flag.is_set():
                    return ("interrotto", None, None)
                b = self.flash.read_region(layout, "prova", second, **common)
                if not (a.ok and b.ok):
                    continue
                if md5_of_file(first) == md5_of_file(second):
                    return ("ok", speed, prova_byte)
            return ("no", None, None)

        def end(outcome):
            state, speed, how_many = outcome
            for path in (first, second, layout):
                try:
                    os.remove(path)
                except OSError:
                    pass
            if state == "ok":
                self.var_speed.set(speed)
                self.var_speed_label.set(SPEED_LABELS[speed])
                self._invalidate_read()
                self.msg_connection.show(
                    "qualifica_ok", GREEN, speed=SPEED_LABELS[speed],
                    size=A.human_size(how_many))
            elif state == "no":
                self.msg_connection.show("qualifica_nessuna", RED)

        self._start_job(work, end, "qualifica")

    # --------------------------------------------------------- prova a secco
    def _region_span(self):
        """(inizio, fine) della regione scelta, oppure None per il chip intero."""
        if self.var_mode.get() != "regione":
            return None
        name = self.var_region.get()
        for region, start, end in self.regions:
            if region == name:
                return (start, end)
        return None

    def dry_run(self):
        """Calcola come verra' la flash, senza toccarla."""
        if not (self.read_path and os.path.isfile(self.read_path)):
            self.msg_write.show("scrivi_bloccato", AMBER,
                                      what=self.L("req_lettura"))
            return
        image = self.var_image.get().strip()
        if not image or not os.path.isfile(image):
            self.msg_write.show("scrivi_bloccato", AMBER,
                                      what=self.L("req_immagine"))
            return
        region = self._region_span()
        if self.var_mode.get() == "regione" and region is None:
            self.msg_write.show("scrivi_bloccato", AMBER,
                                      what=self.L("req_layout"))
            return
        expected = self.var_expected.get().strip()

        def work():
            current = A.read(self.read_path)
            source_image = A.read(image)
            result = A.dry_run(current, source_image, region, md5=md5_of)
            expected_md5 = md5_of_file(expected) if expected and os.path.isfile(expected) else None
            return result, expected_md5, region

        def end(outcome):
            result, expected_md5, span = outcome
            if result.error:
                self.dry = None
                self.msg_write.raw_text(result.error, RED)
                self._update_write_state()
                return
            self.dry = result
            self.secco_firma = self._firma_secco()
            self._prepare_map(span)
            self.chip_map.mark_spans(result.changes, M.WRITTEN)
            self.chip_map.mark_spans(result.outside, M.MISMATCH)

            if result.nothing_to_do:
                self.msg_write.show("secco_nulla", AMBER)
            elif result.outside:
                self.msg_write.show(
                    "secco_fuori", AMBER, spans=len(result.outside),
                    size=A.human_size(result.bytes_changed), md5=result.md5[:12])
            else:
                self.msg_write.show(
                    "secco_ok_uno" if len(result.changes) == 1 else "secco_ok",
                    GREEN, size=A.human_size(result.bytes_changed),
                    spans=len(result.changes), md5=result.md5[:12])
            self.log("   md5 %s · %s · %d %s" % (
                result.md5, A.human_size(result.bytes_changed), len(result.changes),
                "intervalli"), "bene")
            for start, fine_ in result.changes[:12]:
                self.log("     0x%06X-0x%06X  %s" % (
                    start, fine_, A.human_size(fine_ - start + 1)))
            if expected_md5:
                if expected_md5 == result.md5:
                    self.log("   %s" % self.L("secco_atteso_uguale"), "bene")
                else:
                    self.msg_write.show("secco_atteso_diverso", RED,
                                              computed=result.md5[:8],
                                              expected=expected_md5[:8])
                    self.log("!! %s" % self.L(
                        "secco_atteso_diverso", computed=result.md5,
                        expected=expected_md5), "male")
                    self.dry = None
            self._update_write_state()

        self._start_job(work, end, "prova a secco")

    # --------------------------------------------------------- scrittura
    def _missing_requirements(self):
        missing = []
        if not self.flash:
            missing.append(self.L("req_flashrom"))
        if not self.chip:
            missing.append(self.L("req_chip"))
        if not self.verified_read:
            missing.append(self.L("req_lettura"))
        image = self.var_image.get().strip()
        if not image or not os.path.isfile(image):
            missing.append(self.L("req_immagine"))
        elif self.chip and self.chip.size:
            found_one = os.path.getsize(image)
            if found_one != self.chip.size:
                missing.append(self.L("req_dimensione", pending=self.chip.size,
                                      found_one=found_one))
        if self.var_mode.get() == "regione":
            layout = self.var_layout.get().strip()
            if not layout or not os.path.isfile(layout) or not self.var_region.get():
                missing.append(self.L("req_layout"))
        if not self.var_mains_off.get():
            missing.append(self.L("req_alimentazione"))
        if self.chip_is_1v8 and not self.var_shifter.get():
            missing.append(self.L("req_adattatore"))
        # ⚠️ Un chip protetto accetta i comandi e non cambia: la scrittura
        # sembrerebbe riuscita e non lo sarebbe.
        span = self._region_span() or (
            (0, self.chip.size - 1) if self.chip and self.chip.size else None)
        if (self.protection is not None and span
                and self.protection.overlaps(span[0], span[1])):
            missing.append(self.L("req_protezione"))
        # ⚠️ La prova a secco e' obbligatoria: e' l'unico controllo che guarda
        # il CONTENUTO invece dei nomi dei file, e produce l'immagine attesa
        # con cui si verifichera' il chip alla fine.
        if self.dry is None or self.secco_firma != self._firma_secco():
            missing.append(self.L("req_secco"))
        return missing

    def _firma_secco(self):
        """Da cosa dipende la prova a secco: se cambia, va rifatta."""
        image = self.var_image.get().strip()
        try:
            stamp = os.path.getmtime(image) if image else 0
        except OSError:
            stamp = 0
        return (self.verified_read, image, stamp, self.var_mode.get(),
                self.var_region.get(), self.var_layout.get().strip(),
                self.var_expected.get().strip())

    def _update_write_state(self):
        region = self.var_mode.get() == "regione"
        self.combo_region.configure(state="readonly" if region else "disabled")
        self.lbl_region.configure(foreground=T.MUT if region else "#455563")

        missing = self._missing_requirements()
        if self.busy or missing:
            self.b_write.state(["disabled"])
        else:
            self.b_write.state(["!disabled"])
        if missing:
            self.msg_write.show("scrivi_bloccato", GREY, what=", ".join(missing))
        else:
            self.msg_write.clean()

    def _reference_image(self):
        """Da quale file si guardano le regioni, e in quest\u0027ordine.

        ⚠️ Prima la lettura del chip: le regioni che contano sono quelle di
        cio\u0027 che c\u0027e\u0027 adesso sul chip, non quelle dell\u0027immagine nuova.
        Se non si e\u0027 ancora letto, si ripiega su cosa ci si aspetta.
        """
        for path in (getattr(self, "read_path", None),
                         self.var_expected.get().strip(),
                         self.var_image.get().strip()):
            if path and os.path.isfile(path):
                return path
        return None

    def derive_regions(self):
        """Legge la mappa che l\u0027immagine si porta dentro e ne fa un layout."""
        path = self._reference_image()
        if not path:
            self.msg_write.show("reg_senza_immagine", AMBER)
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:                           # noqa: BLE001
            self.msg_write.show("reg_non_scrivo", RED, reason="%s" % e)
            return
        source, found = reg.find_regions(data)
        self.log("→ %s" % A.file_name(path), "io")
        if not found:
            self.msg_write.show("reg_niente", AMBER)
            self.log("   %s" % self.L("reg_niente"))
            return
        root = os.path.splitext(path)[0] + "-regions.layout"
        try:
            with open(root, "wb") as f:
                f.write(reg.as_layout(found, len(data)).encode("ascii"))
        except OSError as e:                           # noqa: BLE001
            self.msg_write.show("reg_non_scrivo", RED, reason="%s" % e)
            return
        for region in found:
            self.log("   %08x:%08x %s" % (region.start, region.end,
                                               region.name))
        self.var_layout.set(root)
        self._reload_regions()
        self._save_config()
        self.msg_write.show("reg_trovate", GREEN, count=len(found),
                                  source=self.L("reg_origine_%s" % source),
                                  file=A.file_name(root))

    def _reload_regions(self):
        path = self.var_layout.get().strip()
        self.regions = []
        if path and os.path.isfile(path):
            try:
                self.regions = fr.read_layout(path)
            except OSError:
                self.regions = []
        names_of = [n for n, _, _ in self.regions]
        self.combo_region.configure(values=names_of)
        if self.var_region.get() not in names_of:
            self.var_region.set("uefi" if "uefi" in names_of else (names_of[0] if names_of else ""))
        self._update_write_state()

    def write(self):
        missing = self._missing_requirements()
        if missing:
            self.msg_write.show("scrivi_bloccato", RED, what=", ".join(missing))
            return

        image = self.var_image.get().strip()
        region = self.var_region.get() if self.var_mode.get() == "regione" else None
        if region:
            entry = next((r for r in self.regions if r[0] == region), None)
            text = self.L("conferma_testo_regione", region=region,
                           size=entry[2] - entry[1] + 1 if entry else 0,
                           start=entry[1] if entry else 0, end=entry[2] if entry else 0,
                           chip=self.chip.description, image=image)
        else:
            text = self.L("conferma_testo_intero", size=os.path.getsize(image),
                           chip=self.chip.description, image=image)

        if not Confirm(self, self.L, text, self.theme).confirmed:
            return

        port = self._chosen_port()
        folder = self.var_folder.get().strip()
        pending = self.dry.outcome          # calcolata dalla prova a secco
        md5_attesa = self.dry.md5
        span = self._region_span() or (0, len(pending) - 1)

        self._prepare_map(self._region_span())
        self.read_span = (0, len(pending) - 1)

        def work():
            common = dict(port=port, baud=BAUD,
                          spispeed=self.var_speed.get() or None,
                          chip=self._chip_for_flashrom(),
                          verbose=bool(self.var_verbose.get()),
                          on_line=self._line_from_thread,
                          on_event=self._evento_da_thread)
            self._message_from_thread(self.msg_write, "scrittura_avvio", AMBER)
            result = self.flash.write(image,
                                      layout=self.var_layout.get().strip() or None,
                                      region=region, **common)
            if not result.ok:
                return ("errore", result, None)

            # ⚠️ La verifica finale e' NOSTRA e indipendente da quella di
            # flashrom: si rilegge tutto il chip e lo si confronta byte per byte
            # con l'immagine che la prova a secco aveva calcolato.
            self._message_from_thread(self.msg_write, "verifica_finale", GREY)
            after = os.path.join(folder, "bc250-dopo-%s.rom" % timestamp())
            esito2 = self.flash.read(after, **common)
            if not esito2.ok:
                return ("errore", esito2, None)
            letto = A.read(after)
            if len(letto) != len(pending):
                return ("errore", esito2, None)
            different = A.merge_runs(A.differing_blocks(pending, letto), A.SECTOR,
                               limit=len(pending))
            byte_diversi = sum(f - i + 1 for i, f in
                               A.exact_spans(pending, letto, different))
            coherent = A.coherence(letto, span[0], span[1])
            return ("fatto", result, (after, different, byte_diversi, coherent,
                                     md5_of(letto)))

        def end(outcome):
            state, result, data = outcome
            if state == "errore":
                self.msg_write.show("scrittura_fallita", RED,
                                          code=result.code)
                self.log("!! %s" % self.L("scrittura_fallita",
                                               code=result.code), "male")
                return
            self.log("   %s" % self.L("scrittura_ok"), "bene")
            after, different, byte_diversi, coherent, md5_letto = data
            self.log("   %s" % self.L("lettura_salvata", path=after))

            if different:
                self.chip_map.mark_spans(different, M.MISMATCH)
                self.msg_write.show(
                    "verifica_diversa_uno" if len(different) == 1
                    else "verifica_diversa", RED, spans=len(different),
                    size=A.human_size(byte_diversi))
                self.log("!! %s (md5 letto %s, atteso %s)" % (
                    self.L("verifica_diversa", spans=len(different),
                           size=A.human_size(byte_diversi)),
                    md5_letto, md5_attesa), "male")
                for start, fine_ in different[:12]:
                    self.log("     0x%06X-0x%06X" % (start, fine_), "male")
                return

            self.chip_map.mark(0, len(pending) - 1, M.VERIFIED)
            self.msg_write.show("verifica_ok", GREEN,
                                      size=A.human_size(len(pending)))
            self.log("   %s md5 %s" % (
                self.L("verifica_ok", size=A.human_size(len(pending))),
                md5_letto), "bene")
            self._dillo_coerenza(coherent)

        self._start_job(work, end, "scrittura", scrittura=True)

    def _dillo_coerenza(self, coherent):
        """La regione scritta ha ancora una struttura sensata?"""
        if coherent["vuoto"]:
            self.log("!! %s" % self.L("coerenza_vuota"), "male")
            self.msg_write.show("coerenza_vuota", RED)
            return
        if coherent["azzerato"]:
            self.log("!! %s" % self.L("coerenza_zero"), "male")
            self.msg_write.show("coerenza_zero", RED)
            return
        chunks = []
        for sig, key, testo_it, testo_en in A.SIGNATURES:
            count = coherent["firme"].get(key, 0)
            if count:
                name = testo_it if self.L.code == "it" else testo_en
                chunks.append("%s ×%d" % (name, count))
        if chunks:
            self.log("   %s" % self.L("coerenza_ok", what=", ".join(chunks)),
                          "bene")
        else:
            self.log("   %s" % self.L("coerenza_nulla"))

    # ------------------------------------------------------------ file
    def pick_folder(self):
        choice = filedialog.askdirectory(initialdir=self.var_folder.get() or None)
        if choice:
            self.var_folder.set(choice)

    def _pick_file(self, variable, tipi):
        iniziale = os.path.dirname(variable.get()) or self.var_folder.get()
        choice = filedialog.askopenfilename(initialdir=iniziale or None, filetypes=tipi)
        if choice:
            variable.set(choice)
        return choice

    def pick_image(self):
        if self._pick_file(self.var_image, [("ROM", "*.rom *.bin *.fd"), ("*", "*.*")]):
            self._update_write_state()

    def pick_layout(self):
        if self._pick_file(self.var_layout, [("layout", "*.txt *.layout"), ("*", "*.*")]):
            self._reload_regions()

    def pick_expected(self):
        self._pick_file(self.var_expected, [("ROM", "*.rom *.bin"), ("*", "*.*")])

    # --------------------------------------------------------- registro
    def log(self, text, tag=None):
        stamp = datetime.now().strftime("%H:%M:%S")
        line = "%s  %s" % (stamp, text)
        self.log_lines.append(line)
        self.text.configure(state="normal")
        self.text.insert("end", stamp + "  ", ("ora",))
        self.text.insert("end", text + "\n", tag or ())
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear_log(self):
        self.log_lines = []
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def save_log(self):
        path = filedialog.asksaveasfilename(
            initialdir=self.var_folder.get() or None,
            initialfile="SPIranha-%s.log" % timestamp(),
            defaultextension=".log")
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(("\n".join(self.log_lines) + "\n").encode("utf-8"))
        except OSError as e:
            messagebox.showerror(self.L("titolo"), "%s" % e)

    def _autosave_log(self, operazione):
        folder = self.var_folder.get().strip()
        if not folder or not os.path.isdir(folder):
            return
        try:
            with open(os.path.join(folder, "SPIranha.log"), "ab") as f:
                intestazione = "\n===== %s — %s =====\n" % (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), operazione)
                f.write(intestazione.encode("utf-8"))
                f.write(("\n".join(self.log_lines) + "\n").encode("utf-8"))
        except OSError:
            pass

    # ------------------------------------------------------------ lavoro
    def _line_from_thread(self, text):
        self.tail_of.put(("riga", text))

    def _evento_da_thread(self, kind, *data):
        self.tail_of.put(("evento", kind, data))

    # -- quello che flashrom racconta mentre lavora ------------------------
    def _apply_event(self, kind, data):
        if kind == "cancella":
            self.chip_map.mark(data[0], data[1], M.ERASED_BLOCK)
            return
        if kind == "scrive":
            self.written_span = (data[0], data[1])
            return
        if kind != "fase":
            return

        name, percent = data
        if name != self.phase:
            self.phase = name
            self.phase_start = datetime.now()
        self.progress.configure(mode="determinate", maximum=100,
                                   value=percent)
        self.var_status.set(self._testo_avanzamento(name, percent))

        if name == "READ" or name == "VERIFY":
            start, end = self.read_span
            state = M.VERIFIED if self.writing else M.READ
            self.chip_map.advance(start, end, percent, state)
        elif name == "WRITE":
            start, end = self.written_span or self.read_span
            self.chip_map.advance(start, end, percent, M.WRITTEN)

    def _testo_avanzamento(self, name, percent):
        phase = self.L("fase_%s" % name)
        trascorso = (datetime.now() - self.phase_start).total_seconds() \
            if self.phase_start else 0
        if percent >= 3 and trascorso > 2:
            left = trascorso * (100 - percent) / float(percent)
            return self.L("avanzamento_resta", phase=phase, percent=percent,
                          left=_durata(left))
        return self.L("avanzamento", phase=phase, percent=percent)

    def _message_from_thread(self, message, key, colour, **fields):
        self.tail_of.put(("messaggio", message, key, colour, fields))

    def _start_job(self, work, on_finish, name, scrittura=False):
        if self.busy:
            messagebox.showinfo(self.L("titolo"), self.L("in_corso"))
            return
        self.busy = True
        self.writing = scrittura
        self.stop_flag.clear()
        self.phase = None
        self.phase_start = None
        self.written_span = None
        self._set_busy(True)
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.var_status.set(self.L("occupato"))
        self.log("→ %s" % name, "io")

        def background_colour():
            try:
                outcome = work()
                self.tail_of.put(("fine", on_finish, outcome, name, None))
            except Exception:                              # noqa: BLE001
                self.tail_of.put(("fine", None, None, name, traceback.format_exc()))

        threading.Thread(target=background_colour, daemon=True).start()

    def _set_busy(self, busy):
        for bottone in (self.b_identify, self.b_leggi, self.b_prova,
                        self.b_qualify, self.b_dry_run, self.b_bootsel,
                        self.b_search_chip,
                        self.b_regions,
                        self.b_update):
            bottone.state(["disabled"] if busy else ["!disabled"])
        self.b_abort.state(["!disabled"] if busy else ["disabled"])
        if busy:
            self.b_write.state(["disabled"])
            self.b_unlock.state(["disabled"])
        elif hasattr(self, "msg_protection"):
            self._show_protection()
        if not busy and not self.flash:
            for bottone in (self.b_identify, self.b_leggi, self.b_qualify):
                bottone.state(["disabled"])

    def abort(self):
        if self.writing:
            messagebox.showwarning(self.L("titolo"), self.L("interruzione_vietata"))
            return
        self.stop_flag.set()
        if self.flash:
            self.flash.abort()
        self.log("!! %s" % self.L("interrotto"), "male")

    def _pump(self):
        try:
            while True:
                entry = self.tail_of.get_nowait()
                if entry[0] == "riga":
                    self.log("   " + entry[1])
                elif entry[0] == "evento":
                    self._apply_event(entry[1], entry[2])
                elif entry[0] == "messaggio":
                    _, message, key, colour, fields = entry
                    message.show(key, colour, **fields)
                elif entry[0] == "chiamata":
                    # un lavoro di sfondo che non e' un'operazione sul chip:
                    # non tocca lo stato «occupato», si limita a rientrare
                    # nel thread della finestra
                    entry[1](entry[2])
                elif entry[0] == "fine":
                    _, on_finish, outcome, name, error = entry
                    self.busy = False
                    self.writing = False
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=0)
                    self.var_status.set(self.L("pronto"))
                    self._set_busy(False)
                    if error:
                        self.log(error, "male")
                    elif on_finish:
                        on_finish(outcome)
                    self._autosave_log(name)
                    self._update_write_state()
                    self._update_firmware_row()
                    self._save_config()
        except queue.Empty:
            pass
        self.after(60, self._pump)

    def _on_close(self):
        if self.busy and not messagebox.askyesno(
                self.L("titolo"), self.L("chiudere_mentre_lavora")):
            return
        self._save_config()
        self.destroy()


class Message(object):
    """Una riga di esito, come pillola di stato, che sa ridisegnarsi al cambio
    lingua."""

    def __init__(self, app, parent):
        self.app = app
        self.chip = T.Chip(parent, app.theme)
        self.widget = self.chip
        self._chiave = None
        self._campi = {}
        self._colore = GREY
        app._messaggi.append(self)

    def show(self, key, colour=GREY, **fields):
        self._chiave, self._campi, self._colore = key, fields, colour
        self.redraw()

    def raw_text(self, text, colour=GREY):
        self._chiave = None
        background, border = TINTS.get(colour, (T.PANEL, T.PANEL))
        self.chip.show(text, colour, background, border)

    def clean(self):
        self._chiave = None
        self.chip.hide()

    def redraw(self):
        if self._chiave is None:
            return
        background, border = TINTS.get(self._colore, (T.PANEL, T.PANEL))
        self.chip.show(self.app.L(self._chiave, **self._campi), self._colore,
                         background, border)


class Confirm(tk.Toplevel):
    """Non basta un «sì»: la parola va scritta a mano."""

    def __init__(self, parent, L, text, tm=None, word=None):
        tk.Toplevel.__init__(self, parent, background=T.INK)
        self.confirmed = False
        self.L = L
        self.title(L("conferma_titolo"))
        self.resizable(False, False)
        self.transient(parent)
        tm = tm or getattr(parent, "tema", None)

        frame = tk.Frame(self, background=T.INK, padx=18, pady=16)
        frame.pack(fill="both", expand=True)

        avviso = tk.Frame(frame, background=T.CRIT_BG, highlightthickness=1,
                          highlightbackground=T.CRIT_BORDO)
        avviso.pack(fill="x")
        tk.Label(avviso, text=text, justify="left", anchor="w", wraplength=520,
                 background=T.CRIT_BG, foreground="#F0C9CB",
                 font=tm.f_text if tm else None).pack(anchor="w", padx=12, pady=10)

        self.word = word or L("parola_conferma")
        tk.Label(frame, text=L("conferma_digita", word=self.word),
                 background=T.INK, foreground=T.FG,
                 font=tm.f_text if tm else None).pack(anchor="w", pady=(14, 5))
        self.variable = tk.StringVar()
        field = ttk.Entry(frame, textvariable=self.variable, width=26,
                          font=tm.f_dato if tm else None)
        field.pack(anchor="w")
        self.variable.trace_add("write", lambda *_: self._controlla())

        buttons = tk.Frame(frame, background=T.INK)
        buttons.pack(anchor="e", pady=(16, 0))
        ttk.Button(buttons, text=L("annulla"), style="Secondario.TButton",
                   command=self.destroy).pack(side="right")
        self.ok = ttk.Button(buttons, text=L("procedi"), style="Pericolo.TButton",
                             command=self._procedi)
        self.ok.pack(side="right", padx=8)
        self.ok.state(["disabled"])

        T.dark_title_bar(self)
        field.focus_set()
        self.grab_set()
        parent.wait_window(self)

    def _controlla(self):
        uguale = self.variable.get().strip().upper() == self.word.upper()
        self.ok.state(["!disabled"] if uguale else ["disabled"])

    def _procedi(self):
        self.confirmed = True
        self.destroy()


def main():
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
