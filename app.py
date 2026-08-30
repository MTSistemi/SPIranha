# -*- coding: utf-8 -*-
"""The interface: the four-step procedure, with the checks that cannot be
skipped.

The idea behind it: by the time this program is needed the board is already
dead and you are in a hurry. The things you are supposed to remember -- read
twice and compare, keep the board unplugged, re-read before plugging it back
in -- are imposed here by the program, and the write button stays off until
they are all true.

The code that touches the chip is flashrom's: here the commands are built and
the results are watched. The look is the "instrument panel" theme (see
theme.py).
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

# The suggested models come from the profile: only the empty entry stays
# empty, which means "let flashrom work the chip out".
SUGGESTED_CHIPS = [""]

# How much is read to qualify the link: enough to notice
# a shaky cable, little enough to redo it at every speed.
QUALIFY_BYTES = 256 * 1024

# The four states a message can be in, in the theme's colours.
GREEN = T.OK
RED = T.CRIT
AMBER = T.WARN
GREY = T.MUT
TINTS = {
    T.OK: (T.OK_BG, T.OK_BORDER),
    T.CRIT: (T.CRIT_BG, T.CRIT_BORDER),
    T.WARN: (T.WARN_BG, T.WARN_BORDER),
}


# ---------------------------------------------------------------- utilita'

def app_folder():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def config_folder():
    """Where the settings live.

    ⚠️ SPIRANHA_CONFIG exists for the tests, and it is not a nicety:
    the tests build the real window, change profile and save -- that is, they
    were rewriting the settings of whoever was using the program. Anyone who
    ran them found it with a different profile and the tests' paths in it.
    """
    override = os.environ.get("SPIRANHA_CONFIG")
    if override:
        return override
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_NAME)


def default_folder():
    documents = os.path.join(os.path.expanduser("~"), "Documents")
    for candidate in (
        os.path.join(documents, "Claude", "SkillFishOS", "bios-backup"),
        os.path.join(documents, "bios-backup"),
    ):
        if os.path.isdir(candidate):
            return candidate
    return documents


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


def _short_time(seconds):
    """A time left to go, said short."""
    seconds = int(max(0, seconds))
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm %02ds" % (seconds // 60, seconds % 60)
    return "%dh %02dm" % (seconds // 3600, (seconds % 3600) // 60)


def md5_of(data):
    return hashlib.md5(data).hexdigest()


# ------------------------------------------------------------------ window

class App(tk.Tk):

    def __init__(self):
        tk.Tk.__init__(self)
        self.settings = self._load_config()
        self.L = Language(self.settings.get("language", "it"))

        self.tail_of = queue.Queue()
        self.busy = False
        self.writing = False
        self.stop_flag = threading.Event()

        # state of the procedure: every requirement gates the write
        self.chip = None                 # the fr.Chip that was identified
        self.protection = None           # fr.Protection, read along with the chip
        self.profile = profiles.by_key(self.settings.get("profile"))
        self.board_firmware = None            # the version the programmer reports
        self.chip_is_1v8 = None            # does the chip want 1.8 V? None = unknown
        self.known_chips = []              # the list flashrom declares
        self.firmware_asked = set()          # serials we have already asked
        self.verified_read = None   # md5 of the last good double read
        self.log_lines = []
        self.regions = []                # (name, start, end) from the layout file
        self.flashrom_version = ""
        self.read_path = None         # file of the last verified read
        self.dry = None                # the outcome of the dry run
        self.dry_stamp = None
        self.phase = None                 # fase in corso, per mappa e avanzamento
        self.phase_start = None
        self.written_span = None
        self.read_span = (0, 16 * 1024 * 1024 - 1)
        self.known_boards = boards.Registry(self.settings.get("boards"))
        self.bootsel_board = None       # RP2040 in attesa di firmware
        self.bootsel_watch = None

        self.flash = None
        path = self.settings.get("flashrom")
        if not (path and os.path.isfile(path)):
            # in the one-file executable flashrom travels inside: _MEIPASS is
            # the folder PyInstaller unpacks it into at startup
            path = fr.find_executable(
                app_folder(), extra=[getattr(sys, "_MEIPASS", None)])
        if path:
            self._set_flashrom(path, quiet=True)

        self._labels = []             # (widget, chiave, attributo, trasforma)
        self._messages = []              # Messages to redraw when the language changes

        self.theme = T.Theme(self)
        self._set_window_icon()
        self._build_ui()
        self._retranslate()
        self.detect_ports()
        T.dark_title_bar(self)
        self.after(60, self._pump)
        self.after(400, self._watch_bootsel)
        # the model list fills itself shortly after opening: the window has
        # to appear at once, not wait for flashrom
        self.after(600, self._load_chip_list)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------ config
    # ⚠️ The settings used to be saved under Italian names. A file written by
    # an older version has to keep working: the old names are read once and
    # rewritten under the new ones on the first save.
    OLD_KEYS = {
        "lingua": "language",
        "porta": "port",
        "cartella": "folder",
        "immagine": "image",
        "profilo": "profile",
        "atteso": "expected",
        "dettagli": "verbose",
        "schede": "boards",
    }

    def _load_config(self):
        try:
            with open(os.path.join(config_folder(), "config.json"), "rb") as f:
                settings = json.loads(f.read().decode("utf-8"))
        except (OSError, ValueError):
            return {}
        for old, new in self.OLD_KEYS.items():
            if old in settings:
                settings.setdefault(new, settings.pop(old))
        if settings.get("profile") == "generico":
            settings["profile"] = "generic"
        return settings

    def _save_config(self):
        self.settings.update({
            "language": self.L.code,
            "flashrom": self.flash.path if self.flash else None,
            "port": self.var_port.get(),
            "spispeed": self.var_speed.get(),
            "folder": self.var_folder.get(),
            "chip": self.var_chip.get(),
            "image": self.var_image.get(),
            "layout": self.var_layout.get(),
            "profile": self.profile.key,
            "expected": self.var_expected.get(),
            "verbose": bool(self.var_verbose.get()),
            "boards": self.known_boards.as_list(),
        })
        try:
            os.makedirs(config_folder(), exist_ok=True)
            with open(os.path.join(config_folder(), "config.json"), "wb") as f:
                f.write(json.dumps(self.settings, indent=2).encode("utf-8"))
        except OSError:
            pass

    # ------------------------------------------------- costruzione grafica
    def _translated(self, widget, key, attribute="text", transform=None):
        """Registers a widget so it rewrites itself when the language changes."""
        self._labels.append((widget, key, attribute, transform))
        return widget

    def _retranslate(self):
        self.title(self.L("title"))
        for widget, key, attribute, transform in self._labels:
            text = self.L(key)
            if transform:
                text = transform(text)
            try:
                widget.configure(**{attribute: text})
            except tk.TclError:
                pass
        for message in self._messages:
            message.redraw()
        if hasattr(self, "lbl_reminder"):
            self._write_reminder()
        # ⚠️ The selector and the status bar too: changing language from
        # code left them behind, showing "Italiano" above an
        # English window.
        if hasattr(self, "var_language"):
            self.var_language.set(LANGUAGE_NAMES.get(self.L.code, ""))
        if hasattr(self, "var_status"):
            self.var_status.set(self.L("busy") if self.busy
                               else self.L("ready"))
        if hasattr(self, "combo_profile"):
            self._fill_profiles()
        self.var_speed_label.set(SPEED_LABELS.get(self.var_speed.get(), ""))
        if hasattr(self, "legend"):
            self.legend.translate()
            self._map_at_rest()
        # ⚠️ Must be called at startup too: _watch_bootsel only updates when
        # the state CHANGES, and at the start "no board" is not a change.
        if hasattr(self, "msg_firmware"):
            self._update_firmware_row()
        self._draw_header()
        self._update_flashrom_banner()
        self._update_write_state()
        window = getattr(self, "_wiring_window", None)
        if window is not None and window.winfo_exists():
            window.title(self.L("sch_title"))
            window.draw()

    TWO_COLUMN_WIDTH = 940      # below this width everything stacks

    def _build_ui(self):
        self.geometry("1040x876")
        self.minsize(620, 540)

        self.root = tk.Frame(self, background=T.INK)
        self.root.pack(fill="both", expand=True)

        self._build_header(self.root)
        self._build_banner(self.root)
        self.boards = [
            self._make_connection_card(self.root),
            self._make_chip_card(self.root),
            self._make_read_card(self.root),
            self._make_write_card(self.root),
        ]
        self.map_card = self._make_map_card(self.root)
        self.log_card = self._make_log_card(self.root)
        self._build_bar(self.root)

        self._columns = None
        self._reflow(two=True)
        self._reflow_after = None
        self.bind("<Configure>", self._maybe_reflow)

    # -- responsive: one or two columns depending on the room --------------
    def _maybe_reflow(self, event):
        if event.widget is not self:
            return
        if self._reflow_after:
            self.after_cancel(self._reflow_after)
        self._reflow_after = self.after(
            90, lambda: self._reflow(two=self.winfo_width() >= self.TWO_COLUMN_WIDTH))

    def _reflow(self, two):
        self._reflow_after = None
        if two == self._columns:
            self._fit_widths()
            return
        self._columns = two
        r = self.root
        for card in self.boards:
            card.grid_forget()
        self.map_card.grid_forget()
        self.log_card.grid_forget()
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
            map_row = 6
        else:
            for index, card in enumerate(self.boards):
                card.grid(row=3 + index, column=0, columnspan=2, sticky="new",
                            **pad)
            map_row = 7
        self.map_card.grid(row=map_row, column=0, columnspan=2,
                               sticky="ew", padx=8, pady=(8, 0))
        log_row = map_row + 1
        self.log_card.grid(row=log_row, column=0, columnspan=2,
                                  sticky="nsew", padx=8, pady=(8, 0))
        r.rowconfigure(log_row, weight=1)
        self.bar.grid(row=log_row + 1, column=0, columnspan=2, sticky="ew",
                        padx=10, pady=(6, 8))
        self._fit_widths()

    def _fit_widths(self):
        """Long text wraps to the column instead of widening everything."""
        width = max(self.winfo_width(), 400)
        column = (width - 32) // (2 if self._columns else 1)
        for message in self._messages:
            message.chip.text.configure(wraplength=max(column - 70, 180))
        for widget, wrap_at in getattr(self, "_wrappables", ()):
            widget.configure(wraplength=max(int(column * wrap_at), 150))

    # -- testata -----------------------------------------------------------
    def _build_header(self, parent):
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

        # ⚠️ The profile sits next to the language, not inside a card: it says
        # WHAT is being worked on, and it has to be seen before touching anything.
        self.var_profile = tk.StringVar()
        self.combo_profile = ttk.Combobox(frame, textvariable=self.var_profile,
                                          width=16, state="readonly",
                                          font=self.theme.f_text)
        self.combo_profile.pack(side="left", padx=(8, 0))
        self.combo_profile.bind("<<ComboboxSelected>>", self._profile_changed)
        self._fill_profiles()
        self.header_canvas.create_window(0, 0, window=frame, anchor="ne",
                                        tags="language")
        self.header_canvas.bind("<Configure>", lambda _e: self._draw_header())

        # the reminder: the rule that never changes
        pro = tk.Frame(parent, background=T.WARN_BG, highlightthickness=1,
                       highlightbackground=T.WARN_BORDER, bd=0)
        pro.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 0))
        dot = tk.Canvas(pro, width=8, height=8, background=T.WARN_BG,
                          highlightthickness=0)
        dot.create_oval(0, 0, 8, 8, fill=T.WARN, outline="")
        dot.pack(side="left", padx=(9, 7), pady=6)
        label = tk.Label(pro, background=T.WARN_BG, foreground="#E8D6B4",
                             anchor="w", justify="left", wraplength=900,
                             font=self.theme.f_text)
        label.pack(side="left", pady=5, padx=(0, 10))
        self.lbl_reminder = label
        self._wrappables = [(label, 1.9)]
        self._write_reminder()

    def _draw_header(self):
        canvas = self.header_canvas
        width = max(canvas.winfo_width(), 320)
        canvas.delete("scritte")
        T.gradient(canvas, width, 54)
        canvas.create_text(18, 18, text=self.L("title"), fill=T.FG, anchor="w",
                         font=self.theme.f_title, tags="scritte")
        canvas.create_text(19, 38,
                         text=self.L("subtitle",
                                     board=self.profile.text(
                                         "name", self.L.code)),
                         fill=T.MUT,
                         anchor="w", font=self.theme.f_sub, tags="scritte")
        canvas.create_line(0, 53, width, 53, fill=T.LINE, tags="scritte")
        canvas.coords("language", width - 12, 14)

    # -- banner flashrom ---------------------------------------------------
    def _build_banner(self, parent):
        self.banner = tk.Frame(parent, background=T.CRIT_BG, highlightthickness=1,
                               highlightbackground=T.CRIT_BORDER, bd=0)
        dot = tk.Canvas(self.banner, width=8, height=8, background=T.CRIT_BG,
                          highlightthickness=0)
        dot.create_oval(0, 0, 8, 8, fill=T.CRIT, outline="")
        dot.pack(side="left", padx=(9, 7), pady=6)
        self.banner_testo = tk.Label(self.banner, background=T.CRIT_BG,
                                     foreground="#F0C9CB", anchor="w",
                                     justify="left", wraplength=700,
                                     font=self.theme.f_text)
        self.banner_testo.pack(side="left", fill="x", expand=True, pady=5)
        self._translated(self.banner_testo, "flashrom_missing")
        self.banner_bottone = ttk.Button(self.banner, style="Pericolo.TButton",
                                         command=self.pick_flashrom)
        self.banner_bottone.pack(side="right", padx=7, pady=5)
        self._translated(self.banner_bottone, "flashrom_locate")
        self.banner.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8,
                         pady=(8, 0))

    def _card(self, parent, key):
        card, body = T.card(parent, self.L(key), self.theme)
        self._translated(card.title_label, key, transform=T.micro)
        return card, body

    def _micro_label(self, parent, key):
        return self._translated(
            tk.Label(parent, background=T.PANEL, foreground=T.MUT,
                     font=self.theme.f_micro, anchor="w"),
            key, transform=T.micro)

    def _note(self, parent, key, wrap_at=0.9):
        label = tk.Label(parent, background=T.PANEL, foreground=T.MUT,
                             font=self.theme.f_tiny, anchor="w", justify="left",
                             wraplength=320)
        self._translated(label, key)
        self._wrappables.append((label, wrap_at))
        return label

    def _browse_button(self, parent, command):
        return self._translated(ttk.Button(parent, style="Secondario.TButton",
                                          width=3, command=command), "browse")

    # -- 1. collegamento ---------------------------------------------------
    def _make_connection_card(self, parent):
        card, s = self._card(parent, "sec_connection")
        s.columnconfigure(1, weight=1)

        self._micro_label(s, "port").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.var_port = tk.StringVar(value=self.settings.get("port", ""))
        self.combo_port = ttk.Combobox(s, textvariable=self.var_port,
                                        font=self.theme.f_text)
        self.combo_port.grid(row=0, column=1, sticky="ew", padx=(6, 6), pady=(0, 4))

        buttons = tk.Frame(s, background=T.PANEL)
        buttons.grid(row=0, column=2, sticky="e", pady=(0, 4))
        self._translated(ttk.Button(buttons, style="Secondario.TButton",
                                   command=self.detect_ports),
                        "detect").pack(side="left", padx=(0, 4))
        self.b_query = self._translated(
            ttk.Button(buttons, style="Secondario.TButton",
                       command=self.query_pico), "query")
        self.b_query.pack(side="left", padx=(0, 4))
        self.b_wiring = self._translated(
            ttk.Button(buttons, style="Ghost.TButton", command=self.open_wiring),
            "sch_open")
        self.b_wiring.pack(side="left")

        self._micro_label(s, "speed").grid(row=1, column=0, sticky="w")
        frame_speed = tk.Frame(s, background=T.PANEL)
        frame_speed.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(6, 0))
        self.var_speed = tk.StringVar(value=self.settings.get("spispeed", ""))
        self.var_speed_label = tk.StringVar()
        combo_v = ttk.Combobox(frame_speed, width=15, state="readonly",
                               font=self.theme.f_text,
                               textvariable=self.var_speed_label,
                               values=[SPEED_LABELS[v] for v in SPEEDS])
        combo_v.pack(side="left")
        combo_v.bind("<<ComboboxSelected>>", self._speed_changed)
        self.b_qualify = self._translated(
            ttk.Button(frame_speed, style="Secondario.TButton",
                       command=self.qualify_link), "qualify")
        self.b_qualify.pack(side="left", padx=(6, 0))
        self._note(frame_speed, "qualify_note", 0.5).pack(side="left", padx=8)

        # --- firmware del programmatore
        hairline = tk.Frame(s, background=T.LINE, height=1)
        hairline.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 8))

        self._micro_label(s, "firmware").grid(row=3, column=0, sticky="w")
        frame_fw = tk.Frame(s, background=T.PANEL)
        frame_fw.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(6, 0))
        self.b_firmware = self._translated(
            ttk.Button(frame_fw, style="Secondario.TButton",
                       command=self.install_firmware), "fw_install")
        self.b_firmware.pack(side="left")
        self.b_reset = self._translated(
            ttk.Button(frame_fw, style="Ghost.TButton",
                       command=self.reset_board), "fw_erase")
        self.b_reset.pack(side="left", padx=6)
        self.b_bootsel = self._translated(
            ttk.Button(frame_fw, style="Ghost.TButton",
                       command=self.back_to_bootsel), "fw_bootsel")
        self.b_bootsel.pack(side="left")
        # shown only when there is really something to update
        self.b_update = self._translated(
            ttk.Button(frame_fw, style="Secondario.TButton",
                       command=self.update_firmware), "fw_update")

        self.lbl_name = self._micro_label(s, "board_name")
        self.lbl_name.grid(row=4, column=0, sticky="w", pady=(7, 0))
        frame_name = tk.Frame(s, background=T.PANEL)
        frame_name.grid(row=4, column=1, columnspan=2, sticky="ew", padx=(6, 0),
                       pady=(7, 0))
        self.var_board_name = tk.StringVar()
        self.name_field = ttk.Entry(frame_name, textvariable=self.var_board_name,
                                    width=26, font=self.theme.f_text)
        self.name_field.pack(side="left")
        self.name_field.bind("<Return>", lambda _e: self.name_board())
        self.name_field.bind("<FocusOut>", lambda _e: self.name_board())
        self._note(frame_name, "board_name_note", 0.5).pack(side="left", padx=8)
        self.msg_firmware = Message(self, s)
        self.msg_firmware.widget.grid(row=5, column=0, columnspan=3, sticky="w",
                                      pady=(7, 0))

        self.msg_connection = Message(self, s)
        self.msg_connection.widget.grid(row=6, column=0, columnspan=3, sticky="w",
                                          pady=(7, 0))
        if not serprog.HAS_SERIAL:
            self.msg_connection.show("pyserial_missing", AMBER)
        return card

    # -- 2. chip -----------------------------------------------------------
    def _make_chip_card(self, parent):
        card, s = self._card(parent, "sec_chip")
        s.columnconfigure(2, weight=1)

        self.b_identify = self._translated(
            ttk.Button(s, style="Secondario.TButton", command=self.identify_chip),
            "identify")
        self.b_identify.grid(row=0, column=0, sticky="w")
        self._micro_label(s, "chip_forced").grid(row=0, column=1, sticky="e", padx=(10, 6))
        self.var_chip = tk.StringVar(value=self.settings.get("chip", ""))
        frame_mode = tk.Frame(s, background=T.PANEL)
        frame_mode.grid(row=0, column=2, sticky="ew")
        frame_mode.columnconfigure(0, weight=1)
        self.combo_chip = ttk.Combobox(frame_mode, textvariable=self.var_chip,
                                       font=self.theme.f_text,
                                       values=SUGGESTED_CHIPS + self.profile.chip)
        self.combo_chip.grid(row=0, column=0, sticky="ew")
        self.b_search_chip = self._translated(
            ttk.Button(frame_mode, style="Ghost.TButton",
                       command=self.search_model), "search")
        self.b_search_chip.grid(row=0, column=1, padx=(6, 0))
        self.combo_chip.bind("<<ComboboxSelected>>", lambda _e: self._invalidate_chip())
        self.combo_chip.bind("<KeyRelease>", lambda _e: self._invalidate_chip())

        self.msg_chip = Message(self, s)
        self.msg_chip.widget.grid(row=1, column=0, columnspan=3, sticky="w",
                                  pady=(7, 0))

        # Protection takes up room only when it has something to say: no
        # fixed label, and the button appears only if there is a lock to lift.
        frame_prot = tk.Frame(s, background=T.PANEL)
        frame_prot.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(7, 0))
        self.msg_protection = Message(self, frame_prot)
        self.msg_protection.widget.pack(side="left")
        self.b_shifter = self._translated(
            ttk.Button(frame_prot, style="Ghost.TButton",
                       command=self.open_level_shifter), "volt_schematic")
        self.b_shifter.pack(side="right")
        self.b_unlock = self._translated(
            ttk.Button(frame_prot, style="Secondario.TButton",
                       command=self.unlock_chip), "prot_unlock")
        return card

    # -- 3. reading -------------------------------------------------------
    def _make_read_card(self, parent):
        card, s = self._card(parent, "sec_read")
        s.columnconfigure(1, weight=1)

        self._micro_label(s, "folder").grid(row=0, column=0, sticky="w")
        self.var_folder = tk.StringVar(
            value=self.settings.get("folder") or default_folder())
        ttk.Entry(s, textvariable=self.var_folder,
                  font=self.theme.f_text).grid(row=0, column=1, sticky="ew",
                                               padx=(6, 4))
        self._browse_button(s, self.pick_folder).grid(row=0, column=2)

        frame = tk.Frame(s, background=T.PANEL)
        frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.b_read = self._translated(
            ttk.Button(frame, style="Primary.TButton",
                       command=self.read_and_verify), "read")
        self.b_read.pack(side="left")
        self._translated(ttk.Button(frame, style="Ghost.TButton",
                                   command=self.open_compare),
                        "cmp_open").pack(side="left", padx=6)
        self._note(frame, "read_note", 0.5).pack(side="left", padx=8)

        self.msg_read = Message(self, s)
        self.msg_read.widget.grid(row=2, column=0, columnspan=3, sticky="w",
                                     pady=(7, 0))
        return card

    # -- 4. writing -------------------------------------------------------
    def _make_write_card(self, parent):
        card, s = self._card(parent, "sec_write")
        s.columnconfigure(1, weight=1)

        self._micro_label(s, "mode").grid(row=0, column=0, sticky="w")
        frame_mode = tk.Frame(s, background=T.PANEL)
        frame_mode.grid(row=0, column=1, columnspan=2, sticky="w", padx=(6, 0))
        self.var_mode = tk.StringVar(value="region")
        for value, key in (("region", "mode_region"), ("whole", "mode_whole")):
            b = ttk.Radiobutton(frame_mode, value=value, variable=self.var_mode,
                                command=self._update_write_state)
            b.pack(side="left", padx=(0, 12))
            self._translated(b, key)

        self.var_image = tk.StringVar(value=self.settings.get("image", ""))
        self.var_layout = tk.StringVar(value=self.settings.get("layout", ""))
        self.var_expected = tk.StringVar(value=self.settings.get("expected", ""))
        for r, (key, variable, command) in enumerate((
                ("image", self.var_image, self.pick_image),
                ("layout_file", self.var_layout, self.pick_layout),
                ("expected", self.var_expected, self.pick_expected),
        ), start=1):
            self._micro_label(s, key).grid(row=r, column=0, sticky="w", pady=(6, 0))
            e = ttk.Entry(s, textvariable=variable, font=self.theme.f_text)
            e.grid(row=r, column=1, sticky="ew", padx=(6, 4), pady=(6, 0))
            e.bind("<KeyRelease>", lambda _e: self._update_write_state())
            self._browse_button(s, command).grid(row=r, column=2, pady=(6, 0))
        self._note(s, "expected_note", 0.7).grid(row=4, column=1, sticky="w",
                                               padx=(6, 0))

        self.lbl_region = self._micro_label(s, "region")
        self.lbl_region.grid(row=5, column=0, sticky="w", pady=(6, 0))
        self.var_region = tk.StringVar()
        self.combo_region = ttk.Combobox(s, textvariable=self.var_region, width=18,
                                          state="readonly", font=self.theme.f_text)
        self.combo_region.grid(row=5, column=1, sticky="w", padx=(6, 0), pady=(6, 0))
        self.b_regions = self._translated(
            ttk.Button(s, style="Ghost.TButton", command=self.derive_regions),
            "reg_derive")
        self.b_regions.grid(row=5, column=2, sticky="w", pady=(6, 0))
        self.combo_region.bind("<<ComboboxSelected>>",
                                lambda _e: self._update_write_state())

        hairline = tk.Frame(s, background=T.LINE, height=1)
        hairline.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(11, 9))

        self.var_mains_off = tk.IntVar(value=0)
        self.check_mains_off = T.Checkbox(
            s, self.theme, self.var_mains_off,
            command=self._update_write_state, colour="#F0C9CB")
        self.checks_box = tk.Frame(s, background=T.PANEL)
        self.checks_box.grid(row=7, column=0, columnspan=3, sticky="w")
        self.check_mains_off.pack(in_=self.checks_box, anchor="w")
        self._translated(self.check_mains_off, "tick_mains",
                        attribute="testo")

        # ⚠️ Shown only when the chip really is 1.8 V. A box that is always
        # there gets ticked out of habit and protects nobody.
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
                       command=self.dry_run), "dry_run")
        self.b_dry_run.pack(side="left", padx=(0, 8))
        self.b_write = self._translated(
            ttk.Button(actions, style="Pericolo.TButton", command=self.write),
            "write")
        self.b_write.pack(side="left")

        self.msg_write = Message(self, s)
        self.msg_write.widget.grid(row=9, column=0, columnspan=3, sticky="w",
                                       pady=(7, 0))
        if self.var_layout.get():
            self._reload_regions()
        return card

    # -- mappa del chip ----------------------------------------------------
    def _make_map_card(self, parent):
        card, s = self._card(parent, "sec_map")
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
            self.var_map_note.set(self.L("map_position", position=position))

    def _map_at_rest(self):
        blocks = max(self.chip_map.blocks, 1)
        self.var_map_note.set(self.L(
            "map_idle",
            total_size=A.human_size(self.chip_map.total_size),
            blocks=blocks,
            grain=A.human_size(int(self.chip_map.total_size / float(blocks)))))

    def _prepare_map(self, span=None):
        """Resets the map and, when working on a region, highlights it."""
        if self.chip and self.chip.size:
            self.chip_map.set_size(total_size=self.chip.size)
        self.chip_map.highlight(span)
        self._map_at_rest()

    # -- registro ----------------------------------------------------------
    def _make_log_card(self, parent):
        card, s = self._card(parent, "sec_log")
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
        self.text.tag_configure("time", foreground=T.LOG_TIME)
        self.text.tag_configure("io", foreground="#7FB2FF")
        self.text.tag_configure("bad", foreground="#FF8686")
        self.text.tag_configure("good", foreground=T.LOG_OK)
        self.text.tag_configure("warn", foreground=T.WARN)

        buttons = tk.Frame(s, background=T.PANEL)
        buttons.grid(row=1, column=0, columnspan=2, sticky="w", pady=(7, 0))
        self.b_abort = self._translated(
            ttk.Button(buttons, style="Secondario.TButton",
                       command=self.abort), "abort")
        self.b_abort.pack(side="left")
        self.b_abort.state(["disabled"])
        self._translated(ttk.Button(buttons, style="Ghost.TButton",
                                   command=self.clear_log),
                        "clear").pack(side="left", padx=4)
        self._translated(ttk.Button(buttons, style="Ghost.TButton",
                                   command=self.save_log),
                        "save_log").pack(side="left")
        self.var_verbose = tk.IntVar(value=1 if self.settings.get("verbose") else 0)
        T.Checkbox(buttons, self.theme, self.var_verbose, text="-V").pack(
            side="left", padx=12)
        return card

    # -- status bar -------------------------------------------------------
    def _build_bar(self, parent):
        self.bar = tk.Frame(parent, background=T.INK)
        self.bar.columnconfigure(1, weight=1)
        self.progress = ttk.Progressbar(
            self.bar, mode="indeterminate", length=130,
            style="Sottile.Horizontal.TProgressbar")
        self.progress.grid(row=0, column=0, sticky="w")
        self.progress.configure(mode="determinate", value=0)
        self.var_status = tk.StringVar(value=self.L("ready"))
        tk.Label(self.bar, textvariable=self.var_status, background=T.INK,
                 foreground=T.MUT, font=self.theme.f_text).grid(
            row=0, column=1, sticky="w", padx=10)
        self.var_flashrom = tk.StringVar()
        tk.Label(self.bar, textvariable=self.var_flashrom, background=T.INK,
                 foreground="#4F657A", font=(self.theme.mono, 7)).grid(
            row=0, column=2, sticky="e")

    # ------------------------------------------------------------ lingua
    def _language_changed(self, _event_of=None):
        chosen = self.var_language.get()
        for code, name in LANGUAGE_NAMES.items():
            if name == chosen:
                self.L.code = code
                break
        self._retranslate()

    def _speed_changed(self, _event_of=None):
        label = self.var_speed_label.get()
        for value, text in SPEED_LABELS.items():
            if text == label:
                self.var_speed.set(value)
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
    def _set_flashrom(self, path, quiet=False):
        candidate_ = fr.Flashrom(path)
        version = candidate_.version()
        if version is None:
            if not quiet:
                messagebox.showerror(self.L("title"), self.L("flashrom_invalid"))
            return False
        self.flash = candidate_
        self.flashrom_version = version
        return True

    def pick_flashrom(self):
        path = filedialog.askopenfilename(
            title=self.L("flashrom_pick"),
            filetypes=[("flashrom.exe", "flashrom.exe"), ("*", "*.*")])
        if path and self._set_flashrom(path):
            self._update_flashrom_banner()
            self._update_write_state()
            self._save_config()

    def _update_flashrom_banner(self):
        if self.flash:
            self.banner.grid_remove()
            chunks = self.flashrom_version.split()
            self.var_flashrom.set(self.L("flashrom_found",
                                         version=chunks[1] if len(chunks) > 1 else "",
                                         path=self.flash.path))
        else:
            self.banner.grid(row=2, column=0, columnspan=2, sticky="ew",
                             padx=8, pady=(8, 0))
            self.var_flashrom.set("")
        for button in (self.b_identify, self.b_read, self.b_qualify):
            button.state(["!disabled"] if self.flash and not self.busy
                          else ["disabled"])


    def _set_window_icon(self):
        """The window's own icon.

        ⚠️ Not the same thing as the executable's icon, and this is worth
        saying because it was wrong: PyInstaller's --icon only sets the
        resource on the .exe, which is what Explorer shows. The window keeps
        Tk's blue feather until it is told otherwise, and that is what people
        actually look at while the program runs.
        """
        for root in (getattr(sys, "_MEIPASS", None), app_folder()):
            if not root:
                continue
            path = os.path.join(root, "SPIranha.ico")
            if os.path.isfile(path):
                try:
                    self.iconbitmap(path)
                except tk.TclError:
                    pass          # a window without its icon still works
                return

    # ------------------------------------------------- firmware del Pico
    def _firmware_path(self):
        """pico_serprog.uf2: inside the executable, next to it, in firmware\\."""
        for root in (getattr(sys, "_MEIPASS", None), app_folder()):
            if not root:
                continue
            for candidate_ in (os.path.join(root, "firmware", pico.FIRMWARE_NAME),
                              os.path.join(root, pico.FIRMWARE_NAME)):
                if os.path.isfile(candidate_):
                    return candidate_
        return None

    def _watch_bootsel(self):
        """Every two seconds: is there a board waiting for firmware?"""
        if not self.busy:
            try:
                boards = pico.boards_in_bootsel()
            except Exception:                          # noqa: BLE001
                boards = []
            newer = boards[0] if boards else None
            before = self.bootsel_board.drive if self.bootsel_board else None
            now_ = newer.drive if newer else None
            if now_ != before:
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
        """The standing rule, plus this board's own warnings."""
        lines = [self.L("reminder")]
        lines += [self.L(key) for key in self.profile.warnings]
        self.lbl_reminder.configure(text="  ".join(lines))

    def _load_chip_list(self, then_=None):
        """Asks flashrom for the chip list, on a thread of its own.

        ⚠️ It is six hundred lines to squeeze and costs half a second:
        doing it at startup, on the window's thread, would show.
        """
        if self.known_chips or not self.flash:
            if then_:
                then_()
            return

        def work():
            try:
                return self.flash.chip_list()
            except Exception:                          # noqa: BLE001
                return []

        def end(listing):
            self.known_chips = listing
            self._fill_models()
            if then_:
                then_()

        threading.Thread(
            target=lambda: self.tail_of.put(("chiamata", end, work())),
            daemon=True).start()

    def _fill_models(self):
        """The dropdown: the profile's models first, then every known SPI chip."""
        values = list(SUGGESTED_CHIPS) + list(self.profile.chip)
        seen = set(v for v in values)
        for chip in self.known_chips:
            if chip.spi and chip.name not in seen:
                seen.add(chip.name)
                values.append(chip.name)
        self.combo_chip.configure(values=values)

    def search_model(self):
        """Opens the model search, loading the list first if need be."""
        def open_window():
            if not self.known_chips:
                self.msg_chip.show("search_empty", AMBER)
                return
            chip_search.open_window(self, self.theme, self.L, self.known_chips,
                         self._model_picked, self.var_chip.get().strip())

        self._load_chip_list(then_=open_window)

    def _model_picked(self, chip):
        self.var_chip.set(chip.name)
        self._invalidate_chip()
        self._check_voltage(chip.name)
        self.log("   %s" % self.L(
            "search_picked", vendor=chip.vendor, chip=chip.name,
            size_text=A.human_size(chip.size) if chip.size else "?"), "io")

    def _fill_profiles(self):
        names = profiles.names_of(self.L.code)
        self.combo_profile.configure(values=[n for _c, n in names])
        self.var_profile.set(self.profile.text("name", self.L.code))

    def _profile_changed(self, _event_of=None):
        chosen = self.var_profile.get()
        for key, name in profiles.names_of(self.L.code):
            if name == chosen:
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
        """What this image is called, if the profile knows it."""
        entry = self.profile.md5.get(md5)
        if not entry:
            return None
        return entry.get(self.L.code) or entry.get("it")

    def _profile_deviations(self):
        """Where the real board departs from what the profile expects."""
        region_names = [n for n, _a, _b in getattr(self, "regions", ())]
        return profiles.deviations(
            self.profile,
            found_chip=self.chip.name if self.chip else None,
            found_size=self.chip.size if self.chip else None,
            regions=region_names)

    def _update_firmware_row(self, with_message=True):
        # going back to BOOTSEL is offered only with a programmer attached
        port = self._programmer_port()
        if port is None:
            # no programmer, no version: the previous one no longer holds
            self.board_firmware = None
        self.b_bootsel.state(["!disabled"] if port and not self.busy
                             else ["disabled"])

        # the name field follows the board being looked at
        run, boot, _translated = self._current_board()
        name = self.known_boards.name(run=run, boot=boot) or ""
        if not self.name_field.focus_get() is self.name_field:
            self.var_board_name.set(name)
        self.name_field.state(["!disabled"] if (run or boot) else ["disabled"])

        card = self.bootsel_board
        if card is None:
            shipped = self._shipped_version()
            older = (port is not None and shipped
                       and serprog.is_older(self.board_firmware, shipped))
            if with_message:
                if port is None or self.board_firmware is None:
                    self.msg_firmware.show("fw_none", GREY)
                elif not older:
                    self.msg_firmware.show("fw_version_ok", GREEN,
                                             version=self.board_firmware or "?")
                elif self.board_firmware:
                    self.msg_firmware.show("fw_version_old", AMBER,
                                             version=self.board_firmware,
                                             newer=shipped)
                else:
                    self.msg_firmware.show("fw_version_silent", AMBER,
                                             newer=shipped)
            if older:
                self.b_update.pack(side="left", padx=(6, 0))
                self.b_update.state(["!disabled"] if not self.busy
                                      else ["disabled"])
            else:
                self.b_update.pack_forget()
            self.b_firmware.state(["disabled"])
            self.b_reset.state(["disabled"])
            return
        self.b_update.pack_forget()
        firmware = self._firmware_path()
        if not firmware:
            self.msg_firmware.show("fw_absent", AMBER)
        elif name:
            self.msg_firmware.show("fw_found_named", GREEN, name=name,
                                     model=card.model,
                                     drive=card.letter,
                                     serial=card.serial or "?")
        else:
            self.msg_firmware.show("fw_found_anon", GREEN,
                                     model=card.model,
                                     drive=card.letter,
                                     serial=card.serial or "?")
        enabled = ["!disabled"] if not self.busy else ["disabled"]
        self.b_reset.state(enabled)
        self.b_firmware.state(enabled if firmware else ["disabled"])

    def name_board(self):
        """Names the board being looked at. Empty = forget it."""
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
            self.msg_firmware.show("fw_named", GREEN, name=name)
        else:
            self.msg_firmware.show("fw_forgotten", GREY)

    def _program_board(self, uf2_path, start_key, end_key, wait_for_port):
        """Copies a .uf2 onto the board and reports how it went."""
        card = self.bootsel_board
        if card is None or not uf2_path:
            return

        # ⚠️ The serprog ports already present are noted FIRST: afterwards we
        # wait for a NEW port. Looking for any port at all, with a programmer
        # already plugged in, it would say "done" even on a failed copy.
        before = set(d for d, _n, likely, _s in serprog.list_serial_ports() if likely)

        def work():
            self._message_from_thread(self.msg_firmware, start_key, AMBER)
            done, reason = pico.install(uf2_path, card,
                                          on_line=self._line_from_thread)
            if not done:
                return ("error", reason, None)
            if not wait_for_port:
                return ("done", None, None)
            self._message_from_thread(self.msg_firmware, "fw_waiting", GREY)
            # the board comes back as a serial port: give it time
            for _ in range(30):
                time.sleep(0.5)
                now_ = set(d for d, _n, likely, _s in serprog.list_serial_ports()
                             if likely)
                for device in sorted(now_ - before):
                    diagnostics = serprog.query(device, BAUD)
                    if diagnostics.ok and diagnostics.speaks_spi:
                        return ("ready", device, diagnostics)
            return ("silent", None, None)

        def end(outcome):
            state, datum, diagnostics = outcome
            self.bootsel_board = None
            if state == "error":
                self.msg_firmware.show("fw_error", RED, reason=datum)
            elif state == "ready":
                # ⚠️ This is the one moment when the two identifiers of the
                # same board touch: it was in BOOTSEL, now it is that port.
                if card.serial:
                    run_serial = self._serial_of_port(datum)
                    if run_serial:
                        self.known_boards.link(run_serial, card.serial)
                        self._save_config()
                self.msg_firmware.show("fw_ready", GREEN, port=datum)
                self.log("   %s, iface v%s, bus %s" % (
                    diagnostics.name, diagnostics.version,
                    diagnostics.readable_bus), "good")
                self.detect_ports()
            elif state == "silent":
                self.msg_firmware.show("fw_no_return", AMBER)
            else:
                self.msg_firmware.show(end_key, GREEN)
            # ⚠️ without this the summary would wipe the result just read
            self._update_firmware_row(with_message=False)

        self._start_job(work, end, "firmware")

    def _shipped_version(self):
        """The version of the UF2 we carry in here."""
        path = self._firmware_path()
        if not path:
            return None
        return pico.shipped_version(os.path.dirname(path))

    def _note_firmware(self, diagnostics, serial=None):
        """Records what the board that was queried declares."""
        if diagnostics is None or not diagnostics.ok:
            return
        self.board_firmware = diagnostics.firmware or ""
        if serial:
            self.firmware_asked.add(serial)

    def _ask_version_once(self):
        """Once per board, not every round: it opens and closes the port.

        ⚠️ Nobody can tell from outside which firmware an RP2040 holds:
        the USB serial is the chip's own and never changes. It has to be asked
        of the board, and the board only answers from 1.1 onwards.
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
        for device, _description_of, likely, _serial_of in serprog.list_serial_ports():
            if likely:
                return device
        return None

    def _serial_of_port(self, port):
        for device, _d, _s, serial in serprog.list_serial_ports():
            if device == port:
                return serial
        return None

    def _current_board(self):
        """(run key, boot key, label) of whatever is being looked at.

        In BOOTSEL the disk-board wins; otherwise the attached programmer.
        They are two different identifiers for the same thing, see boards.py.
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
        """Puts the programmer back in update mode, from software."""
        port = self._programmer_port()
        if not port:
            return
        serial_before = self._serial_of_port(port)

        def work():
            self._message_from_thread(self.msg_firmware, "fw_bootsel_trying",
                                      AMBER, port=port)
            pico.back_to_bootsel(port)
            # ⚠️ The outcome is not read from opening the port, which fails
            # on purpose: we watch for the board to reappear as a disk.
            for _ in range(20):
                time.sleep(0.5)
                boards = pico.boards_in_bootsel()
                if boards:
                    return ("bootsel", boards[0], None)
            return ("nothing", None, None)

        def end(outcome):
            state, card, _ = outcome
            if state == "bootsel":
                # the same thing backwards: it was that port, now it is that disk
                if serial_before and card.serial:
                    self.known_boards.link(serial_before, card.serial)
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
        """Back to BOOTSEL, copy, and check again: three steps, one button.

        ⚠️ Going back from software only exists from 1.1. An older board
        will not return to BOOTSEL by itself and the button has to be pressed,
        once: after that update it is never needed again.
        """
        port = self._programmer_port()
        path = self._firmware_path()
        if not (port and path):
            return
        serial_before = self._serial_of_port(port)
        # the port of the board being updated disappears and comes back: it
        # must not count among the "already present" ones, or we would never
        # see it return
        before = set(d for d, _n, likely, _s in serprog.list_serial_ports()
                    if likely)
        before.discard(port)

        def work():
            self._message_from_thread(self.msg_firmware, "fw_updating", AMBER)
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
            self._message_from_thread(self.msg_firmware, "fw_installing",
                                      AMBER)
            done, reason = pico.install(path, card,
                                          on_line=self._line_from_thread)
            if not done:
                return ("error", reason, card)
            self._message_from_thread(self.msg_firmware, "fw_waiting", GREY)
            for _ in range(30):
                time.sleep(0.5)
                now_ = set(d for d, _n, likely, _s in serprog.list_serial_ports()
                             if likely)
                for device in sorted(now_ - before):
                    diagnostics = serprog.query(device, BAUD)
                    if diagnostics.ok and diagnostics.speaks_spi:
                        return ("ready", (device, diagnostics), card)
            return ("silent", None, card)

        def end(outcome):
            state, datum, card = outcome
            if card is not None and serial_before and card.serial:
                self.known_boards.link(serial_before, card.serial)
                self._save_config()
            self.bootsel_board = None
            if state == "no_bootsel":
                self.msg_firmware.show("fw_update_no_bootsel", AMBER)
            elif state == "error":
                self.msg_firmware.show("fw_error", RED, reason=datum)
            elif state == "silent":
                self.msg_firmware.show("fw_no_return", AMBER)
            else:
                device, diagnostics = datum
                self._note_firmware(diagnostics,
                                      self._serial_of_port(device))
                shipped = self._shipped_version()
                # ⚠️ A successful copy is not enough: the version has to be
                # declared by the board, after it has restarted.
                if diagnostics.firmware == shipped:
                    self.msg_firmware.show("fw_updated", GREEN,
                                             version=diagnostics.firmware,
                                             port=device)
                else:
                    self.msg_firmware.show("fw_update_doubt", RED,
                                             version=diagnostics.firmware
                                             or diagnostics.name)
                self.detect_ports()
            self._update_firmware_row(with_message=False)

        self._start_job(work, end, "firmware update")

    def install_firmware(self):
        self._program_board(self._firmware_path(), "fw_installing",
                        "fw_ready", wait_for_port=True)

    def reset_board(self):
        """Returns the board to its factory state. We generate the .uf2 ourselves.

        ⚠️ TWO CONSENTS, and the second is tied to the SERIAL: with
        three identical boards on the desk, "are you sure?" says nothing about
        WHICH one is being erased. Retyping the last four digits forces a look
        at the right one.
        """
        card = self.bootsel_board
        if card is None:
            return
        name = self.known_boards.name(boot=card.serial)
        who = "%s · %s" % (name, card.serial) if name else (
            card.serial or "%s su %s" % (card.model, card.letter))

        first = self.L("fw_erase_one", who=who, size=A.human_size(pico.FLASH_PICO))
        if not Confirm(self, self.L, first, self.theme,
                        word=self.L("word_erase")).confirmed:
            return

        if card.serial:
            second = self.L("fw_erase_two", drive=card.letter,
                             serial=card.serial)
            word = boards.tail_of(card.serial)
        else:
            second = self.L("fw_erase_two_noserial", drive=card.letter)
            word = self.L("word_erase")
        if not Confirm(self, self.L, second, self.theme,
                        word=word).confirmed:
            return
        path = os.path.join(config_folder(), "azzera.uf2")
        try:
            os.makedirs(config_folder(), exist_ok=True)
            pico.make_eraser(path)
        except OSError as e:
            self.msg_firmware.show("fw_error", RED, reason="%s" % e)
            return
        self._program_board(path, "fw_erasing", "fw_erased",
                        wait_for_port=False)

    # ------------------------------------------------------------ porte
    def detect_ports(self):
        ports = serprog.list_serial_ports()
        values = []
        for device, description, likely, serial in ports:
            # the name given to the board beats Windows' description
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
            programmers = [p[0] for p in ports if p[2]]
            # ⚠️ It is not enough that the saved port still exists: if the
            # chosen one is NOT a programmer and an attached one exists, we
            # switch to it. Otherwise, after the Pico disappears and comes
            # back, what stays selected is
            # any old port (Bluetooth, a system serial line).
            if (not current or current not in [p[0] for p in ports]
                    or (programmers and current not in programmers)):
                self.var_port.set(candidate)
            else:
                # ⚠️ The port is the same but its LABEL may have changed:
                # after naming a board, Windows' old description stayed on
                # show and the name just given looked lost.
                for value, port in zip(values, ports):
                    if port[0] == current and value != self.var_port.get():
                        self.var_port.set(value)
                        break
        elif serprog.HAS_SERIAL:
            self.msg_connection.show("no_port", AMBER)

    def _chosen_port(self):
        text = (self.var_port.get() or "").strip()
        return text.split("—")[0].strip() if "—" in text else text

    def query_pico(self):
        port = self._chosen_port()
        if not port:
            self.msg_connection.show("no_port", AMBER)
            return
        self.log("→ serprog: %s" % port, "io")
        diagnostics = serprog.query(port, BAUD)
        if not diagnostics.ok:
            self.msg_connection.show("pico_wont_open", RED,
                                         port=port, reason=diagnostics.error)
            return
        self.msg_connection.show(
            "pico_known", GREEN if diagnostics.speaks_spi else AMBER,
            name=diagnostics.name, version=diagnostics.version,
            bus=diagnostics.readable_bus)
        self.log("   %s, iface v%s, bus %s" % (
            diagnostics.name, diagnostics.version, diagnostics.readable_bus))
        self._note_firmware(diagnostics, self._serial_of_port(port))
        self._update_firmware_row(with_message=False)
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
                # ⚠️ Asked STRAIGHT AWAY: it is the most common way a write
                # fails to go through, and finding out after the erase is
                # tardi.
                _e, protection = self.flash.protection(
                    port, BAUD, self.var_speed.get() or None,
                    chip.name, bool(self.var_verbose.get()),
                    self._line_from_thread)
            identity = None
            if not (result.ok and chip.name) and not chip.candidates:
                # ⚠️ Only here: if flashrom recognised the chip, asking a
                # second time adds nothing and touches the wires for
                # niente.
                identity = serprog.identify_chip(port, BAUD)
            return result, chip, protection, identity

        def end(outcome):
            result, chip, protection, identity = outcome
            if chip.candidates:
                self.combo_chip.configure(values=SUGGESTED_CHIPS + chip.candidates)
                self.msg_chip.show("chip_ambiguous", AMBER)
                return
            if not result.ok or not chip.name:
                self.msg_chip.show("chip_not_found", RED)
                self._report_identity(identity)
                return
            self.chip = chip
            self.protection = protection
            self.msg_chip.show("chip_found", GREEN, chip=chip.description)
            self._check_voltage(chip.name)
            # ⚠️ A departure from the profile is said and nothing more: it
            # blocks nothing. Whoever has the board knows more than a table.
            for key, fields in self._profile_deviations():
                self.log("   %s" % self.L(key, **fields), "warn")
            self._show_protection()
            self._update_write_state()

        self._start_job(work, end, "identify")

    def _check_voltage(self, name):
        """The model tells you what voltage the chip runs at.

        ⚠️ There is no way to measure it from here, but the name is
        enough: in the SPI NOR families the 1.8 V version differs by one
        letter. And getting the voltage wrong does not give an error: it gives
        a dead chip.
        """
        volts, family = V.voltage_of(name)
        self.chip_is_1v8 = None if volts is None else (volts == V.LOW)
        if self.chip_is_1v8:
            self.log("!! %s" % self.L("volt_low", family=family),
                          "bad")
            self.check_shifter.pack(anchor="w", pady=(5, 0))
        else:
            self.check_shifter.pack_forget()
            self.var_shifter.set(0)
            if volts is None:
                self.log("   %s" % self.L("volt_unknown"), "warn")
            else:
                self.log("   %s" % self.L("volt_high", family=family))
        self._update_write_state()

    def _report_identity(self, identity):
        """What the chip answered when we asked it ourselves.

        ⚠️ This separates two troubles that look alike: a chip flashrom
        does not know, and a chip that is not there. In the first case you
        force a similar model and carry on; in the second you redo the wiring,
        and trying models at random leads nowhere.
        """
        if identity is None:
            return
        if not identity.ok:
            self.log("   %s" % self.L("jedec_error",
                                           reason=identity.error), "warn")
            return
        if not identity.answers:
            self.msg_chip.show("jedec_silent", RED)
            self.log("   %s (JEDEC %s)" % (self.L("jedec_silent"),
                                                identity.jedec), "bad")
            return
        self.msg_chip.show("jedec_answers", AMBER,
                             description=identity.description())
        self.log("   %s" % self.L("jedec_answers",
                                       description=identity.description()),
                      "warn")

    def _show_protection(self):
        p = self.protection
        if p is None:
            self.msg_protection.clean()
            self.b_unlock.pack_forget()
            return
        if not p.supported:
            self.msg_protection.show("prot_unknown", GREY)
            self.b_unlock.pack_forget()
            return
        if not p.active:
            self.msg_protection.show("prot_free", GREEN)
            self.b_unlock.pack_forget()
            return
        self.b_unlock.pack(side="right", padx=(10, 8))
        span = self._region_span()
        clash = span and p.overlaps(span[0], span[1])
        if clash:
            self.msg_protection.show("prot_clash", RED,
                                       start=p.start, end=p.end)
        else:
            self.msg_protection.show("prot_active", AMBER, start=p.start,
                                       end=p.end, description=p.description,
                                       mode=p.mode)
        self.b_unlock.state(["!disabled"] if not self.busy else ["disabled"])

    def unlock_chip(self):
        """Removes the protection. It changes the chip's state: ask first."""
        port = self._chosen_port()
        if not (self.flash and port and self.chip):
            return
        text = self.L("prot_confirm", chip=self.chip.description)
        if not Confirm(self, self.L, text, self.theme,
                        word=self.L("word_unlock")).confirmed:
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
                self.log("   %s" % self.L("prot_unlocked"), "good")
            else:
                self.msg_protection.show("prot_not_removed", RED,
                                           code=result.code)
                self.log("!! %s" % self.L("prot_not_removed",
                                               code=result.code), "bad")
                self._update_write_state()
                return
            self._show_protection()
            self._update_write_state()

        self._start_job(work, end, "unlock")

    # ------------------------------------------------------------- reading
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
        first = os.path.join(folder, "%s-read-%s.rom"
                             % (self.profile.key, stamp))
        second = os.path.join(folder, "%s-verify-%s.rom"
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
                          on_event=self._event_from_thread)
            self._message_from_thread(self.msg_read, "read_1", GREY)
            result = self.flash.read(first, **common)
            if not result.ok:
                return ("error", result, None, None)
            self._message_from_thread(self.msg_read, "read_2", GREY)
            result = self.flash.read(second, **common)
            if not result.ok:
                return ("error", result, None, None)
            return ("ok", result, md5_of_file(first), md5_of_file(second))

        def end(outcome):
            state, result, a, b = outcome
            if state == "error":
                self._flashrom_failed(self.msg_read, result)
                return
            if a != b:
                self.msg_read.show("read_differs", RED, a=a[:8], b=b[:8])
                self.log("!! reads disagree: %s != %s" % (a, b), "bad")
                return
            self.verified_read = a
            self.read_path = first
            self.dry = None          # the base changed, so the dry run has to be done again
            self.chip_map.mark(0, self.read_span[1], M.VERIFIED)
            try:
                os.remove(second)
            except OSError:
                pass
            self.msg_read.show("read_ok", GREEN, md5=a)
            self.log("   %s" % self.L("read_saved", path=first), "good")
            note = self._known_fingerprint(a)
            self.log("   %s" % self.L(
                "known_as",
                what=note or self.L("md5_unknown")))
            expected = os.path.join(folder, "%s-risultato-atteso.rom"
                                  % self.profile.key)
            if not self.var_expected.get() and os.path.isfile(expected):
                self.var_expected.set(expected)
            self._compare_with_previous(folder, first)
            self._update_write_state()

        self._start_job(work, end, "read")

    def _previous_reads(self, folder, excluded=None):
        """The backups already in the folder, newest first.

        ⚠️ The old Italian prefix is still accepted: whoever has been using
        the program has folders full of files named that way, and the
        comparison with the previous backup has to keep seeing them.
        """
        prefixes = ("%s-read-" % self.profile.key, "%s-letto-" % self.profile.key)
        found_items = []
        try:
            names = os.listdir(folder)
        except OSError:
            return []
        for name in names:
            if not (name.startswith(prefixes) and name.endswith(".rom")):
                continue
            path = os.path.join(folder, name)
            if excluded and os.path.abspath(path) == os.path.abspath(excluded):
                continue
            try:
                found_items.append((os.path.getmtime(path), path))
            except OSError:
                continue
        found_items.sort(reverse=True)
        return [p for _t, p in found_items]

    def _compare_with_previous(self, folder, just_read):
        """Compares the read just taken with the previous backup.

        ⚠️ It answers a question that always comes up and that nobody
        can answer from memory: "is this chip still how I left it?". The
        program does the comparing, not an eye on two thirty-two-digit md5s.
        """
        previous = self._previous_reads(folder, excluded=just_read)
        if not previous:
            self.log("   %s" % self.L("cmp_first"))
            return
        before = previous[0]
        name = A.file_name(before)
        try:
            older = A.read(before)
            newer = A.read(just_read)
        except OSError:
            return
        if len(older) != len(newer):
            self.log("   %s" % self.L("cmp_other_size", file=name),
                          "warn")
            return
        result = A.compare_images(older, newer)
        spans = result["aligned"]
        if result["identical"] or not spans:
            self.log("   %s" % self.L("cmp_same", file=name), "good")
            return
        start = min(a for a, _b in spans)
        end = max(b for _a, b in spans)
        how_many = len(result["blocks"])
        self.log("   %s" % self.L("cmp_differs", file=name, how_many=how_many,
                                       start=start, end=end), "warn")
        for a, b in spans[:8]:
            self.log("      0x%06X-0x%06X  %s" % (
                a, b, A.human_size(b - a + 1)))

    def _flashrom_failed(self, message, result):
        """When flashrom refuses: say it plainly and leave the detail in the log,
        where it has already landed line by line."""
        if result.aborted:
            message.raw_text(self.L("aborted"), AMBER)
            return
        if result.error:
            message.raw_text(result.error, RED)
            return
        message.show("read_failed", RED, code=result.code)

    def _chip_for_flashrom(self):
        forced = self.var_chip.get().strip()
        if forced:
            return forced
        return self.chip.name if self.chip and self.chip.name else None

    # ---------------------------------------------- qualifying the link
    def qualify_link(self):
        """Looks for the highest speed that gives two identical reads.

        It reads a small region instead of the whole chip: the same question,
        in seconds rather than minutes.
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
        test_bytes = min(QUALIFY_BYTES, total_size)
        layout = os.path.join(folder, "qualify-layout.txt")
        with open(layout, "wb") as f:
            f.write(("%08x:%08x test\n%08x:%08x rest\n" % (
                0, test_bytes - 1, test_bytes, total_size - 1)).encode("ascii"))
        first = os.path.join(folder, "qualify-a.bin")
        second = os.path.join(folder, "qualify-b.bin")
        self._prepare_map()
        self.read_span = (0, test_bytes - 1)

        def work():
            for speed in SPEEDS:
                label = SPEED_LABELS[speed]
                self._message_from_thread(self.msg_connection,
                                          "qualify_trying", GREY,
                                          speed=label)
                common = dict(port=port, baud=BAUD,
                              spispeed=speed or None,
                              chip=self._chip_for_flashrom(),
                              verbose=bool(self.var_verbose.get()),
                              on_line=self._line_from_thread,
                              on_event=self._event_from_thread)
                a = self.flash.read_region(layout, "test", first, **common)
                if self.stop_flag.is_set():
                    return ("aborted", None, None)
                b = self.flash.read_region(layout, "test", second, **common)
                if not (a.ok and b.ok):
                    continue
                if md5_of_file(first) == md5_of_file(second):
                    return ("ok", speed, test_bytes)
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
                    "qualify_ok", GREEN, speed=SPEED_LABELS[speed],
                    size=A.human_size(how_many))
            elif state == "no":
                self.msg_connection.show("qualify_none", RED)

        self._start_job(work, end, "qualify")

    # ------------------------------------------------------------- dry run
    def _region_span(self):
        """(start, end) of the chosen region, or None for the whole chip."""
        if self.var_mode.get() != "region":
            return None
        name = self.var_region.get()
        for region, start, end in self.regions:
            if region == name:
                return (start, end)
        return None

    def dry_run(self):
        """Works out how the flash will end up, without touching it."""
        if not (self.read_path and os.path.isfile(self.read_path)):
            self.msg_write.show("write_blocked", AMBER,
                                      what=self.L("req_read"))
            return
        image = self.var_image.get().strip()
        if not image or not os.path.isfile(image):
            self.msg_write.show("write_blocked", AMBER,
                                      what=self.L("req_image"))
            return
        region = self._region_span()
        if self.var_mode.get() == "region" and region is None:
            self.msg_write.show("write_blocked", AMBER,
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
            self.dry_stamp = self._dry_signature()
            self._prepare_map(span)
            self.chip_map.mark_spans(result.changes, M.WRITTEN)
            self.chip_map.mark_spans(result.outside, M.MISMATCH)

            if result.nothing_to_do:
                self.msg_write.show("dry_nothing", AMBER)
            elif result.outside:
                self.msg_write.show(
                    "dry_outside", AMBER, spans=len(result.outside),
                    size=A.human_size(result.bytes_changed), md5=result.md5[:12])
            else:
                self.msg_write.show(
                    "dry_ok_one" if len(result.changes) == 1 else "dry_ok",
                    GREEN, size=A.human_size(result.bytes_changed),
                    spans=len(result.changes), md5=result.md5[:12])
            self.log("   md5 %s · %s · %d %s" % (
                result.md5, A.human_size(result.bytes_changed), len(result.changes),
                "intervalli"), "good")
            for start, end_ in result.changes[:12]:
                self.log("     0x%06X-0x%06X  %s" % (
                    start, end_, A.human_size(end_ - start + 1)))
            if expected_md5:
                if expected_md5 == result.md5:
                    self.log("   %s" % self.L("dry_expected_same"), "good")
                else:
                    self.msg_write.show("dry_expected_differs", RED,
                                              computed=result.md5[:8],
                                              expected=expected_md5[:8])
                    self.log("!! %s" % self.L(
                        "dry_expected_differs", computed=result.md5,
                        expected=expected_md5), "bad")
                    self.dry = None
            self._update_write_state()

        self._start_job(work, end, "dry run")

    # ------------------------------------------------------------- writing
    def _missing_requirements(self):
        missing = []
        if not self.flash:
            missing.append(self.L("req_flashrom"))
        if not self.chip:
            missing.append(self.L("req_chip"))
        if not self.verified_read:
            missing.append(self.L("req_read"))
        image = self.var_image.get().strip()
        if not image or not os.path.isfile(image):
            missing.append(self.L("req_image"))
        elif self.chip and self.chip.size:
            found_one = os.path.getsize(image)
            if found_one != self.chip.size:
                missing.append(self.L("req_size", pending=self.chip.size,
                                      found_one=found_one))
        if self.var_mode.get() == "region":
            layout = self.var_layout.get().strip()
            if not layout or not os.path.isfile(layout) or not self.var_region.get():
                missing.append(self.L("req_layout"))
        if not self.var_mains_off.get():
            missing.append(self.L("req_mains"))
        if self.chip_is_1v8 and not self.var_shifter.get():
            missing.append(self.L("req_shifter"))
        # ⚠️ A protected chip takes the commands and does not change: the write
        # would look successful and would not be.
        span = self._region_span() or (
            (0, self.chip.size - 1) if self.chip and self.chip.size else None)
        if (self.protection is not None and span
                and self.protection.overlaps(span[0], span[1])):
            missing.append(self.L("req_protection"))
        # ⚠️ The dry run is compulsory: it is the only check that looks at
        # the CONTENT rather than the file names, producing the expected image
        # the chip will be verified against at the end.
        if self.dry is None or self.dry_stamp != self._dry_signature():
            missing.append(self.L("req_dry_run"))
        return missing

    def _dry_signature(self):
        """What the dry run depends on: if it changes, it has to be redone."""
        image = self.var_image.get().strip()
        try:
            stamp = os.path.getmtime(image) if image else 0
        except OSError:
            stamp = 0
        return (self.verified_read, image, stamp, self.var_mode.get(),
                self.var_region.get(), self.var_layout.get().strip(),
                self.var_expected.get().strip())

    def _update_write_state(self):
        region = self.var_mode.get() == "region"
        self.combo_region.configure(state="readonly" if region else "disabled")
        self.lbl_region.configure(foreground=T.MUT if region else "#455563")

        missing = self._missing_requirements()
        if self.busy or missing:
            self.b_write.state(["disabled"])
        else:
            self.b_write.state(["!disabled"])
        if missing:
            self.msg_write.show("write_blocked", GREY, what=", ".join(missing))
        else:
            self.msg_write.clean()

    def _reference_image(self):
        """Which file the regions are read from, and in this order.

        ⚠️ The chip's own read first: the regions that matter are those
        of what is on the chip now, not those of the new image. If nothing has
        been read yet, fall back on what is expected.
        """
        for path in (getattr(self, "read_path", None),
                         self.var_expected.get().strip(),
                         self.var_image.get().strip()):
            if path and os.path.isfile(path):
                return path
        return None

    def derive_regions(self):
        """Reads the map the image carries and turns it into a layout."""
        path = self._reference_image()
        if not path:
            self.msg_write.show("reg_no_image", AMBER)
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:                           # noqa: BLE001
            self.msg_write.show("reg_not_written", RED, reason="%s" % e)
            return
        source, found = reg.find_regions(data)
        self.log("→ %s" % A.file_name(path), "io")
        if not found:
            self.msg_write.show("reg_none", AMBER)
            self.log("   %s" % self.L("reg_none"))
            return
        root = os.path.splitext(path)[0] + "-regions.layout"
        try:
            with open(root, "wb") as f:
                f.write(reg.as_layout(found, len(data)).encode("ascii"))
        except OSError as e:                           # noqa: BLE001
            self.msg_write.show("reg_not_written", RED, reason="%s" % e)
            return
        for region in found:
            self.log("   %08x:%08x %s" % (region.start, region.end,
                                               region.name))
        self.var_layout.set(root)
        self._reload_regions()
        self._save_config()
        self.msg_write.show("reg_found", GREEN, count=len(found),
                                  source=self.L("reg_from_%s" % source),
                                  file=A.file_name(root))

    def _reload_regions(self):
        path = self.var_layout.get().strip()
        self.regions = []
        if path and os.path.isfile(path):
            try:
                self.regions = fr.read_layout(path)
            except OSError:
                self.regions = []
        names = [n for n, _, _ in self.regions]
        self.combo_region.configure(values=names)
        if self.var_region.get() not in names:
            self.var_region.set("uefi" if "uefi" in names else (names[0] if names else ""))
        self._update_write_state()

    def write(self):
        missing = self._missing_requirements()
        if missing:
            self.msg_write.show("write_blocked", RED, what=", ".join(missing))
            return

        image = self.var_image.get().strip()
        region = self.var_region.get() if self.var_mode.get() == "region" else None
        if region:
            entry = next((r for r in self.regions if r[0] == region), None)
            text = self.L("confirm_text_region", region=region,
                           size=entry[2] - entry[1] + 1 if entry else 0,
                           start=entry[1] if entry else 0, end=entry[2] if entry else 0,
                           chip=self.chip.description, image=image)
        else:
            text = self.L("confirm_text_whole", size=os.path.getsize(image),
                           chip=self.chip.description, image=image)

        if not Confirm(self, self.L, text, self.theme).confirmed:
            return

        port = self._chosen_port()
        folder = self.var_folder.get().strip()
        pending = self.dry.outcome          # worked out by the dry run
        md5_wanted = self.dry.md5
        span = self._region_span() or (0, len(pending) - 1)

        self._prepare_map(self._region_span())
        self.read_span = (0, len(pending) - 1)

        def work():
            common = dict(port=port, baud=BAUD,
                          spispeed=self.var_speed.get() or None,
                          chip=self._chip_for_flashrom(),
                          verbose=bool(self.var_verbose.get()),
                          on_line=self._line_from_thread,
                          on_event=self._event_from_thread)
            self._message_from_thread(self.msg_write, "write_start", AMBER)
            result = self.flash.write(image,
                                      layout=self.var_layout.get().strip() or None,
                                      region=region, **common)
            if not result.ok:
                return ("error", result, None)

            # ⚠️ The final check is OURS and independent of the one
            # flashrom: the whole chip is re-read and compared byte for byte
            # against the image the dry run had worked out.
            self._message_from_thread(self.msg_write, "verify_final", GREY)
            after = os.path.join(folder,
                                 "%s-after-%s.rom"
                                 % (self.profile.key, timestamp()))
            outcome2 = self.flash.read(after, **common)
            if not outcome2.ok:
                return ("error", outcome2, None)
            read_back = A.read(after)
            if len(read_back) != len(pending):
                return ("error", outcome2, None)
            different = A.merge_runs(A.differing_blocks(pending, read_back), A.SECTOR,
                               limit=len(pending))
            byte_diversi = sum(f - i + 1 for i, f in
                               A.exact_spans(pending, read_back, different))
            coherent = A.coherence(read_back, span[0], span[1])
            return ("done", result, (after, different, byte_diversi, coherent,
                                     md5_of(read_back)))

        def end(outcome):
            state, result, data = outcome
            if state == "error":
                self.msg_write.show("write_failed", RED,
                                          code=result.code)
                self.log("!! %s" % self.L("write_failed",
                                               code=result.code), "bad")
                return
            self.log("   %s" % self.L("write_ok"), "good")
            after, different, byte_diversi, coherent, md5_read = data
            self.log("   %s" % self.L("read_saved", path=after))

            if different:
                self.chip_map.mark_spans(different, M.MISMATCH)
                self.msg_write.show(
                    "verify_differs_one" if len(different) == 1
                    else "verify_differs", RED, spans=len(different),
                    size=A.human_size(byte_diversi))
                self.log("!! %s (md5 letto %s, atteso %s)" % (
                    self.L("verify_differs", spans=len(different),
                           size=A.human_size(byte_diversi)),
                    md5_read, md5_wanted), "bad")
                for start, end_ in different[:12]:
                    self.log("     0x%06X-0x%06X" % (start, end_), "bad")
                return

            self.chip_map.mark(0, len(pending) - 1, M.VERIFIED)
            self.msg_write.show("verify_ok", GREEN,
                                      size=A.human_size(len(pending)))
            self.log("   %s md5 %s" % (
                self.L("verify_ok", size=A.human_size(len(pending))),
                md5_read), "good")
            self._say_coherence(coherent)

        self._start_job(work, end, "write", writing=True)

    def _say_coherence(self, coherent):
        """Does the written region still have a sensible structure?"""
        if coherent["vuoto"]:
            self.log("!! %s" % self.L("coherence_empty"), "bad")
            self.msg_write.show("coherence_empty", RED)
            return
        if coherent["azzerato"]:
            self.log("!! %s" % self.L("coherence_zero"), "bad")
            self.msg_write.show("coherence_zero", RED)
            return
        chunks = []
        for sig, key, text_it, text_en in A.SIGNATURES:
            count = coherent["firme"].get(key, 0)
            if count:
                name = text_it if self.L.code == "it" else text_en
                chunks.append("%s ×%d" % (name, count))
        if chunks:
            self.log("   %s" % self.L("coherence_ok", what=", ".join(chunks)),
                          "good")
        else:
            self.log("   %s" % self.L("coherence_none"))

    # ------------------------------------------------------------ file
    def pick_folder(self):
        choice = filedialog.askdirectory(initialdir=self.var_folder.get() or None)
        if choice:
            self.var_folder.set(choice)

    def _pick_file(self, variable, kinds):
        initial = os.path.dirname(variable.get()) or self.var_folder.get()
        choice = filedialog.askopenfilename(initialdir=initial or None, filetypes=kinds)
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
        self.text.insert("end", stamp + "  ", ("time",))
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
            messagebox.showerror(self.L("title"), "%s" % e)

    def _autosave_log(self, operation):
        folder = self.var_folder.get().strip()
        if not folder or not os.path.isdir(folder):
            return
        try:
            with open(os.path.join(folder, "SPIranha.log"), "ab") as f:
                heading = "\n===== %s — %s =====\n" % (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), operation)
                f.write(heading.encode("utf-8"))
                f.write(("\n".join(self.log_lines) + "\n").encode("utf-8"))
        except OSError:
            pass

    # -------------------------------------------------------------- work
    def _line_from_thread(self, text):
        self.tail_of.put(("line", text))

    def _event_from_thread(self, kind, *data):
        self.tail_of.put(("event", kind, data))

    # -- what flashrom reports while it works ------------------------------
    def _apply_event(self, kind, data):
        if kind == "erase":
            self.chip_map.mark(data[0], data[1], M.ERASED_BLOCK)
            return
        if kind == "write":
            self.written_span = (data[0], data[1])
            return
        if kind != "phase":
            return

        name, percent = data
        if name != self.phase:
            self.phase = name
            self.phase_start = datetime.now()
        self.progress.configure(mode="determinate", maximum=100,
                                   value=percent)
        self.var_status.set(self._progress_text(name, percent))

        if name == "READ" or name == "VERIFY":
            start, end = self.read_span
            state = M.VERIFIED if self.writing else M.READ
            self.chip_map.advance(start, end, percent, state)
        elif name == "WRITE":
            start, end = self.written_span or self.read_span
            self.chip_map.advance(start, end, percent, M.WRITTEN)

    def _progress_text(self, name, percent):
        phase = self.L("phase_%s" % name)
        elapsed = (datetime.now() - self.phase_start).total_seconds() \
            if self.phase_start else 0
        if percent >= 3 and elapsed > 2:
            left = elapsed * (100 - percent) / float(percent)
            return self.L("progress_left", phase=phase, percent=percent,
                          left=_short_time(left))
        return self.L("progress", phase=phase, percent=percent)

    def _message_from_thread(self, message, key, colour, **fields):
        self.tail_of.put(("message", message, key, colour, fields))

    def _start_job(self, work, on_finish, name, writing=False):
        if self.busy:
            messagebox.showinfo(self.L("title"), self.L("running"))
            return
        self.busy = True
        self.writing = writing
        self.stop_flag.clear()
        self.phase = None
        self.phase_start = None
        self.written_span = None
        self._set_busy(True)
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.var_status.set(self.L("busy"))
        self.log("→ %s" % name, "io")

        def background_colour():
            try:
                outcome = work()
                self.tail_of.put(("fine", on_finish, outcome, name, None))
            except Exception:                              # noqa: BLE001
                self.tail_of.put(("fine", None, None, name, traceback.format_exc()))

        threading.Thread(target=background_colour, daemon=True).start()

    def _set_busy(self, busy):
        for button in (self.b_identify, self.b_read, self.b_query,
                        self.b_qualify, self.b_dry_run, self.b_bootsel,
                        self.b_search_chip,
                        self.b_regions,
                        self.b_update):
            button.state(["disabled"] if busy else ["!disabled"])
        self.b_abort.state(["!disabled"] if busy else ["disabled"])
        if busy:
            self.b_write.state(["disabled"])
            self.b_unlock.state(["disabled"])
        elif hasattr(self, "msg_protection"):
            self._show_protection()
        if not busy and not self.flash:
            for button in (self.b_identify, self.b_read, self.b_qualify):
                button.state(["disabled"])

    def abort(self):
        if self.writing:
            messagebox.showwarning(self.L("title"), self.L("abort_denied"))
            return
        self.stop_flag.set()
        if self.flash:
            self.flash.abort()
        self.log("!! %s" % self.L("aborted"), "bad")

    def _pump(self):
        try:
            while True:
                entry = self.tail_of.get_nowait()
                if entry[0] == "line":
                    self.log("   " + entry[1])
                elif entry[0] == "evento":
                    self._apply_event(entry[1], entry[2])
                elif entry[0] == "message":
                    _, message, key, colour, fields = entry
                    message.show(key, colour, **fields)
                elif entry[0] == "chiamata":
                    # background work that is not a chip operation: it does
                    # not touch the "busy" state, it only comes back into
                    # the window's thread
                    entry[1](entry[2])
                elif entry[0] == "fine":
                    _, on_finish, outcome, name, error = entry
                    self.busy = False
                    self.writing = False
                    self.progress.stop()
                    self.progress.configure(mode="determinate", value=0)
                    self.var_status.set(self.L("ready"))
                    self._set_busy(False)
                    if error:
                        self.log(error, "bad")
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
                self.L("title"), self.L("close_while_busy")):
            return
        self._save_config()
        self.destroy()


class Message(object):
    """One line of outcome, as a status pill, that can redraw itself when the
    language changes."""

    def __init__(self, app, parent):
        self.app = app
        self.chip = T.Chip(parent, app.theme)
        self.widget = self.chip
        self._key_of = None
        self._fields = {}
        self._colour_of = GREY
        app._messages.append(self)

    def show(self, key, colour=GREY, **fields):
        self._key_of, self._fields, self._colour_of = key, fields, colour
        self.redraw()

    def raw_text(self, text, colour=GREY):
        self._key_of = None
        background, border = TINTS.get(colour, (T.PANEL, T.PANEL))
        self.chip.show(text, colour, background, border)

    def clean(self):
        self._key_of = None
        self.chip.hide()

    def redraw(self):
        if self._key_of is None:
            return
        background, border = TINTS.get(self._colour_of, (T.PANEL, T.PANEL))
        self.chip.show(self.app.L(self._key_of, **self._fields), self._colour_of,
                         background, border)


class Confirm(tk.Toplevel):
    """A "yes" is not enough: the word has to be typed by hand."""

    def __init__(self, parent, L, text, tm=None, word=None):
        tk.Toplevel.__init__(self, parent, background=T.INK)
        self.confirmed = False
        self.L = L
        self.title(L("confirm_title"))
        self.resizable(False, False)
        self.transient(parent)
        tm = tm or getattr(parent, "theme", None)

        frame = tk.Frame(self, background=T.INK, padx=18, pady=16)
        frame.pack(fill="both", expand=True)

        warning = tk.Frame(frame, background=T.CRIT_BG, highlightthickness=1,
                          highlightbackground=T.CRIT_BORDER)
        warning.pack(fill="x")
        tk.Label(warning, text=text, justify="left", anchor="w", wraplength=520,
                 background=T.CRIT_BG, foreground="#F0C9CB",
                 font=tm.f_text if tm else None).pack(anchor="w", padx=12, pady=10)

        self.word = word or L("word_confirm")
        tk.Label(frame, text=L("confirm_type", word=self.word),
                 background=T.INK, foreground=T.FG,
                 font=tm.f_text if tm else None).pack(anchor="w", pady=(14, 5))
        self.variable = tk.StringVar()
        field = ttk.Entry(frame, textvariable=self.variable, width=26,
                          font=tm.f_datum if tm else None)
        field.pack(anchor="w")
        self.variable.trace_add("write", lambda *_: self._check())

        buttons = tk.Frame(frame, background=T.INK)
        buttons.pack(anchor="e", pady=(16, 0))
        ttk.Button(buttons, text=L("cancel"), style="Secondario.TButton",
                   command=self.destroy).pack(side="right")
        self.ok = ttk.Button(buttons, text=L("proceed"), style="Pericolo.TButton",
                             command=self._proceed)
        self.ok.pack(side="right", padx=8)
        self.ok.state(["disabled"])

        T.dark_title_bar(self)
        field.focus_set()
        self.grab_set()
        parent.wait_window(self)

    def _check(self):
        same = self.variable.get().strip().upper() == self.word.upper()
        self.ok.state(["!disabled"] if same else ["disabled"])

    def _proceed(self):
        self.confirmed = True
        self.destroy()


def main():
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
