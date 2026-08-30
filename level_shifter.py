# -*- coding: utf-8 -*-
"""Lo schema elettrico per i chip a 1,8 V.

Il problema, in due righe: l'RP2040 parla a 3,3 V e un chip a 1,8 V regge
1,95 V sui piedini. Collegarlo diretto e' come dargli il doppio della
tensione prevista. E non funzionerebbe nemmeno al contrario: un 1 logico a
1,8 V non arriva alla soglia d'ingresso dell'RP2040, che vuole almeno
0,7 x 3,3 = 2,31 V, quindi il MISO si leggerebbe a caso anche nel caso
fortunato in cui il chip sopravvive.

SERVONO DUE COSE, e vanno insieme:
  1. alimentare il chip a 1,8 V, che il Pico non ha: un regolatore dal 3V3;
  2. tradurre i livelli nei due versi.

QUALE TRADUTTORE. Qui e' disegnato quello a MOSFET (il montaggio classico di
Philips AN97055): quattro BSS138 e otto resistenze, roba da cassetto, e
funziona nei due versi da solo. Ha un limite vero e va detto: la salita del
segnale la fa la resistenza, non il transistor. Con 1 kOhm si tengono 4 MHz;
con i 10 kOhm dello schema classico -- che vengono dall'I2C a 100 kHz -- la
salita va sui 700 ns e gia' a 1 MHz le due letture non coincidono.

Se il chip e' grande e la pazienza poca, un integrato a direzione fissa
(TI SN74LVC8T245PWR) tiene i 12 MHz senza fare una piega: le direzioni
dell'SPI sono fisse -- SCLK, MOSI e CS vanno sempre verso il chip, MISO
sempre verso il Pico -- quindi la traduzione automatica non serve. Il
TXS0108E invece no: e' fatto per bus a collettore aperto (I2C) e sull'SPI
push-pull si comporta male.

⚠️ I MODELLI STANNO IN PEZZI, e ci stanno apposta. «Un MOSFET» e «un
regolatore» non bastano a comprare i pezzi giusti: sul MOSFET conta la
tensione di soglia e il 2N7002 -- stesso contenitore, stesso prezzo -- col
gate a 1,8 V non accende proprio.
"""
from __future__ import unicode_literals

import os
import tkinter.messagebox as messagebox
import tkinter.filedialog as filedialog

import wiring
import printing
import theme as T

# ------------------------------------------------------------------ dati

# I quattro segnali che passano dall'adattatore, e come sono orientati.
CHANNELS = (
    ("SCLK", "GP2", "6  CLK", "verso"),
    ("MOSI", "GP3", "5  DI", "verso"),
    ("MISO", "GP4", "2  DO", "da"),
    ("CS", "GP5", "1  /CS", "verso"),
)

# LA DISTINTA, con sigle vere.
#
# ⚠️ Sul MOSFET la specifica che conta non e' la corrente, e' la tensione di
# soglia: il gate sta a 1,8 V, quindi serve un Vgs(th) sotto 1,5 V. Il BSS138
# ce l'ha (0,5-1,5 V). Il 2N7002, che gli somiglia e costa uguale, arriva a
# 2,5 V e col gate a 1,8 V non accende: e' l'errore piu' facile da fare qui.
#
# ⚠️ E le resistenze sono da 1 kΩ, non i 10 kΩ dello schema classico: quelli
# vengono dall'I2C a 100 kHz. Qui la salita del segnale la fa la resistenza,
# e con 10 kΩ su una trentina di picofarad si va sui 700 ns -- piu' del mezzo
# periodo a 1 MHz. Con 1 kΩ si scende a ~70 ns e si tengono i 4 MHz.
# ⚠️ La colonna «cosa» e' bilingue anche per la virgola: 1,5 V in italiano e
# 1.5 V in inglese. Le sigle dei modelli invece non si traducono.
PARTS = (
    ("Q1-Q4", {"it": "N-MOSFET · Vgs(th) < 1,5 V · SOT-23",
               "en": "N-MOSFET · Vgs(th) < 1.5 V · SOT-23"},
     "onsemi BSS138LT1G · Diodes BSS138-7-F · Nexperia BSS138BK"),
    ("R1-R8", {"it": "1 kΩ · 1% · 0603", "en": "1 kΩ · 1% · 0603"},
     "Yageo RC0603FR-071KL"),
    ("U1", {"it": "LDO 1,8 V · > 100 mA · SOT-23",
            "en": "LDO 1.8 V · > 100 mA · SOT-23"},
     "Microchip MCP1700T-1802E/TT · Torex XC6206P182MR · Diodes AP2112K-1.8TRG1"),
    ("C1, C2", {"it": "1 µF · X7R · 16 V · 0603",
                "en": "1 µF · X7R · 16 V · 0603"},
     "Murata GRM188R71C105KA12D"),
)


def value_for(chunk, language="it"):
    """La colonna «cosa» del pezzo, nella lingua giusta."""
    text = chunk[1]
    if isinstance(text, dict):
        return text.get(language) or text.get("it") or ""
    return text

NOTES = ("ad_nota1", "ad_nota3", "ad_nota5", "ad_nota6")

# --------------------------------------------------------------- geometria
# Un canale solo, disegnato in grande: gli altri tre sono identici e
# disegnarli tutti e quattro non aggiunge un'informazione, aggiunge righe.
RAIL_HIGH_Y = 132              # barra dei 3,3 V
RAIL_LOW_Y = 300             # barra degli 1,8 V
CHANNEL_Y = 216                 # il segnale, in mezzo alle due barre
X_RAIL0, X_RAIL1 = 56, 620     # da dove a dove arrivano le due barre
X_PICO, X_CHIP = 112, 560      # dove comincia e finisce il filo del segnale
X_MOSFET = 336                    # il transistor, al centro
X_R_ALTA, X_R_BASSA = 232, 440  # le due resistenze di tiraggio
# ⚠️ La presa del regolatore sta PRIMA dell'inizio del segnale (x=112): messa
# in mezzo, il suo filo attraversava la linea del segnale e sembrava toccarla.
X_IN, X_OUT = 76, 500
LDO_X, LDO_Y = 216, 400        # il regolatore, sotto
# ⚠️ La colonna di destra ha tre riquadri e arriva a 720: misurato, non
# stimato. Se ALT_AD e' piu' corto dell'altezza vera, la scala si calcola su
# un disegno che non c'e' e l'ultima nota finisce fuori dalla finestra.
SHIFTER_HEIGHT = 720
# ⚠️ Nel PDF va SOLO il circuito: la colonna di destra diventa una
# tabella vera nella seconda pagina, che in stampa si legge meglio di
# un riquadro fotografato.
DRAWING_AREA = (10, 60, 700, 600)
LDO_L, LDO_A = 140, 44


class LevelShifter(wiring.Diagram):
    """La finestra dello schema elettrico: riusa i pennelli di Schema."""

    def __init__(self, parent, tm, L):
        wiring.Diagram.__init__(self, parent, tm, L, clip=True)
        self.title(L("ad_titolo"))
        # ⚠️ 800 di altezza, non 700: il contenuto naturale arriva a 720 e
        # con la scala guidata dalla larghezza diventano ~755 pixel.
        # Misurato: a occhio l'ultima nota restava fuori.
        self.geometry("1080x800")

    # ------------------------------------------------------------ disegno
    def draw(self):
        self._attesa = None
        width = max(self.canvas.winfo_width(), 300)
        height = max(self.canvas.winfo_height(), 240)
        self.k = max(0.52, min(width / float(wiring.WIDTH),
                               height / float(SHIFTER_HEIGHT), 1.7))
        self.canvas.delete("all")
        self._draw_shifter_title(width)
        self._draw_rails()
        self._draw_channel()
        self._draw_regulator()
        self._draw_shifter_column()
        self._measure_drawing()

    def _draw_shifter_title(self, real_width):
        top = self._s(52)
        T.gradient(self.canvas, real_width, top)
        self.canvas.create_line(0, top, real_width, top, fill=T.LINE)
        self._text(20, 18, self.L("ad_titolo"), T.FG, self._font(12, True))
        self._text(21, 37, self.L("ad_sotto"), T.MUT, self._font(8))

        # il tasto per la stampa: una pillola disegnata, come il resto
        larghezza_pillola = 96
        x0 = (real_width / self.k) - larghezza_pillola - 16
        self._rect(x0, 14, x0 + larghezza_pillola, 38, "#1D2937", "#2A3846",
                   tag="pdf")
        self._text(x0 + larghezza_pillola / 2.0, 26, self.L("ad_pdf"),
                    "#8FC2E3", self._font(7.5, True), anchor="center",
                    tag="pdf")
        self.canvas.tag_bind("pdf", "<Button-1>", lambda _e: self.export_pdf())
        self.canvas.tag_bind("pdf", "<Enter>",
                           lambda _e: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind("pdf", "<Leave>",
                           lambda _e: self.canvas.configure(cursor=""))

    # -- stampa ------------------------------------------------------------
    def export_pdf(self, path=None):
        """Il disegno e la distinta in un PDF stampabile."""
        if path is None:
            if printing.find_chrome() is None:
                messagebox.showwarning(self.L("ad_titolo"),
                                       self.L("ad_pdf_niente_chrome"),
                                       parent=self)
                return None
            path = filedialog.asksaveasfilename(
                parent=self, title=self.L("ad_pdf_dove"), defaultextension=".pdf",
                initialfile="adattatore-1v8.pdf",
                filetypes=[("PDF", "*.pdf")])
            if not path:
                return None
        # ⚠️ Il tasto non deve finire nel PDF: e' un comando, non un disegno.
        self.canvas.delete("pdf")
        area = [self._s(v) for v in DRAWING_AREA]
        drawing = printing.svg_from_canvas(self.canvas, area)
        page = printing.level_shifter_html(
            drawing, self.L,
            [(p[0], value_for(p, self.L.code), p[2]) for p in PARTS],
            CHANNELS, NOTES, self.L("ad_gia_pronti"),
            self.L("ad_titolo"), self.L("ad_sotto"))
        done, reason = printing.to_pdf(page, path)
        self.draw()
        if not done:
            messagebox.showerror(self.L("ad_titolo"),
                                 self.L("ad_pdf_errore", reason=reason),
                                 parent=self)
            return None
        messagebox.showinfo(self.L("ad_titolo"),
                            self.L("ad_pdf_fatto",
                                   file=os.path.basename(path)),
                            parent=self)
        return path

    # -- le due alimentazioni ---------------------------------------------
    def _draw_rails(self):
        # ⚠️ Le scritte vanno SOPRA la barra, non a sinistra: a sinistra
        # occupavano lo spazio da cui scende la presa del regolatore.
        for y, label_for, colour, x_da in (
                (RAIL_HIGH_Y, self.L("ad_rail_alto"), T.WIRE["VCC"], X_RAIL0),
                (RAIL_LOW_Y, self.L("ad_rail_basso"), "#F0A93B",
                 X_IN + 24)):
            a, b, c = self._s(x_da, y, X_RAIL1)
            self.canvas.create_line(a, b, c, b, fill=colour,
                                  width=max(1.6, 2.4 * self.k))
            self._text(x_da + 4, y - 13, label_for, colour,
                        self._font(8, True))

    # -- un canale: MOSFET e due resistenze -------------------------------
    def _draw_channel(self):
        colour = T.WIRE["MOSI"]

        # ⚠️ Il filo NON passa dietro al transistor: il transistor lo
        # interrompe, ed e' tutto il punto del montaggio.
        self._wire([(X_PICO, CHANNEL_Y), (X_MOSFET - 40, CHANNEL_Y)], colour)
        self._wire([(X_MOSFET + 40, CHANNEL_Y), (X_CHIP, CHANNEL_Y)], colour)

        self._text(X_PICO, CHANNEL_Y - 14, self.L("ad_lato_pico"), "#B9C7D3",
                    self._font(7, True))
        self._text(X_CHIP, CHANNEL_Y - 14, self.L("ad_lato_chip"), "#B9C7D3",
                    self._font(7, True), anchor="e")

        # le due resistenze di tiraggio, una per lato
        self._draw_resistor(X_R_ALTA, RAIL_HIGH_Y, CHANNEL_Y, "R5", "1k")
        self._draw_resistor(X_R_BASSA, RAIL_LOW_Y, CHANNEL_Y, "R1", "1k")

        self._draw_mosfet(X_MOSFET, CHANNEL_Y)

        # ⚠️ Il verso del transistor non e' simmetrico: il source guarda il
        # lato a 1,8 V. Montato al contrario il MOSFET conduce sempre e i due
        # lati restano attaccati, cioe' il chip prende 3,3 V lo stesso.
        self._text(X_IN + 28, RAIL_LOW_Y + 24, self.L("ad_verso"),
                    "#93A5B4", self._font(7), anchor="nw", width=340)

    def _draw_resistor(self, x, y_rail, y_segnale, ref, value_for):
        """Resistenza verticale fra la barra e il filo del segnale."""
        middle = (y_rail + y_segnale) / 2.0
        top, bottom = middle - 22, middle + 22
        self._wire([(x, y_rail), (x, top)], "#5E7488")
        self._wire([(x, bottom), (x, y_segnale)], "#5E7488")
        self._rect(x - 11, top, x + 11, bottom, "#141A21", "#7C8B99")
        self._text(x + 18, middle - 7, ref, "#93A5B4", self._font(7, True))
        self._text(x + 18, middle + 6, value_for, "#6E8296", self._font(7))
        # il pallino di giunzione: senza, un incrocio sembra un incrocio
        self._draw_junction(x, y_segnale)

    def _draw_junction(self, x, y):
        a, b = self._s(x, y)
        r = self._s(3.2)
        self.canvas.create_oval(a - r, b - r, a + r, b + r, fill="#B9C7D3",
                              outline="")

    def _draw_mosfet(self, x, y):
        """Un N-MOSFET fra i due lati: drain a 3,3 V, source a 1,8 V.

        ⚠️ Il drain sta dalla parte del Pico e il source da quella del chip,
        e non sono intercambiabili: e' il diodo interno fra source e drain,
        piu' il gate fisso a 1,8 V, a far funzionare la traduzione nei due
        versi. Al contrario il transistor resta acceso e i due lati sono
        semplicemente collegati.
        """
        # ⚠️ Simbolo coricato: la corrente passa da sinistra a destra come il
        # segnale, cosi' il filo resta dritto e si vede che il transistor sta
        # IN MEZZO. Col simbolo in piedi i collegamenti facevano un giro che
        # sembrava un rettangolo, non un transistor.
        wide = 32
        y_canale = y + 13           # le tre barrette del canale
        y_gate = y + 22             # la placca di gate, staccata sotto

        for x0, x1 in ((x - wide, x - 10), (x - 7, x + 7), (x + 10, x + wide)):
            a, b = self._s(x0, y_canale)
            self.canvas.create_line(a, b, self._s(x1), b, fill="#B9C7D3",
                                  width=max(1.5, 2.2 * self.k))
        a, b = self._s(x - wide, y_gate)
        self.canvas.create_line(a, b, self._s(x + wide), b, fill="#B9C7D3",
                              width=max(1.5, 2.2 * self.k))

        # drain a sinistra (lato 3,3 V), source a destra (lato 1,8 V)
        self._wire([(X_MOSFET - 40, y), (x - wide + 6, y),
                    (x - wide + 6, y_canale)], "#8FA2B2")
        self._wire([(x + wide - 6, y_canale), (x + wide - 6, y),
                    (X_MOSFET + 40, y)], "#8FA2B2")
        # il gate sta fisso a 1,8 V: e' quello che fa funzionare tutto
        self._wire([(x, y_gate), (x, RAIL_LOW_Y)], "#F0A93B")
        self._draw_junction(x, RAIL_LOW_Y)

        # ⚠️ le sigle sotto il filo, non sopra: sopra finivano sul cavetto
        self._text(x - wide - 3, y + 4, "D", "#93A5B4",
                    self._font(6.5, True, mono=True), anchor="e")
        self._text(x + wide + 3, y + 4, "S", "#93A5B4",
                    self._font(6.5, True, mono=True))
        self._text(x + wide + 6, y_gate - 2, "G", "#93A5B4",
                    self._font(6.5, True, mono=True))
        self._text(x, y - 30, "Q1 · BSS138", "#93A5B4",
                    self._font(7, True), anchor="center")

    # -- il regolatore da 3,3 a 1,8 ---------------------------------------
    def _draw_regulator(self):
        x0, y0 = LDO_X, LDO_Y
        x1, y1 = x0 + LDO_L, y0 + LDO_A
        self._rect(x0, y0, x1, y1, "#141A21", "#7C8B99")
        self._text((x0 + x1) / 2.0, y0 + 15, "U1", "#E4EDF4",
                    self._font(8, True), anchor="center")
        self._text((x0 + x1) / 2.0, y0 + 31, self.L("ad_ldo"), "#93A5B4",
                    self._font(6.5), anchor="center")

        middle = y0 + LDO_A / 2.0
        # ingresso dal 3,3 (preso a sinistra di tutto), uscita sugli 1,8
        self._wire([(X_IN, RAIL_HIGH_Y), (X_IN, middle), (x0, middle)],
                   T.WIRE["VCC"])
        self._draw_junction(X_IN, RAIL_HIGH_Y)
        self._wire([(x1, middle), (X_OUT, middle), (X_OUT, RAIL_LOW_Y)],
                   "#F0A93B")
        self._draw_junction(X_OUT, RAIL_LOW_Y)

        # i due condensatori, uno per lato: senza, il regolatore oscilla
        self._draw_capacitor(X_IN + 60, middle, "C1")
        self._draw_capacitor(X_OUT - 44, middle, "C2")
        self._draw_junction(X_IN + 60, middle)
        self._draw_junction(X_OUT - 44, middle)
        self._text(X_IN + 28, y1 + 86, self.L("ad_ldo_nota"), "#93A5B4",
                    self._font(7), anchor="nw", width=430)

    def _draw_capacitor(self, x, y, ref):
        """Appeso al filo: dal nodo scende, due piatti, poi massa."""
        self._wire([(x, y), (x, y + 26)], "#5E7488")
        for dy, wide in ((26, 15), (36, 15)):
            a, b = self._s(x - wide, y + dy)
            self.canvas.create_line(a, b, self._s(x + wide), b, fill="#B9C7D3",
                                  width=max(1.4, 2.0 * self.k))
        self._wire([(x, y + 36), (x, y + 58)], "#5E7488")
        self._draw_ground(x, y + 58)
        self._text(x + 22, y + 31, ref, "#93A5B4", self._font(7, True))

    def _draw_ground(self, x, y):
        for index, wide in enumerate((14, 9, 4)):
            a, b = self._s(x - wide, y + index * 5)
            self.canvas.create_line(a, b, self._s(x + wide), b, fill="#8FA2B2",
                                  width=max(1.2, 1.8 * self.k))

    # -- colonna di destra: pezzi e note ----------------------------------
    def _draw_shifter_column(self):
        x = wiring.COL_X
        y = wiring.TITLE_Y - 12
        line = y + 38

        for label_for, dx in ((self.L("ad_col_segnale"), 26),
                              (self.L("sch_col_pico"), 110),
                              (self.L("sch_col_chip"), 190)):
            self._text(x + dx, line, T.micro(label_for), "#55697C",
                        self._font(6, True), tag="tabella")
        line += 15
        for signal, pico, chip, direction in CHANNELS:
            colour = T.WIRE[signal]
            self._text(x + 26, line, signal, colour, self._font(8, True),
                        tag="tabella")
            self._text(x + 110, line, pico, T.FG, self._font(7, mono=True),
                        tag="tabella")
            freccia = "→" if direction == "verso" else "←"
            self._text(x + 170, line, freccia, "#6E8296", self._font(7),
                        tag="tabella")
            self._text(x + 190, line, chip, T.FG, self._font(7, mono=True),
                        tag="tabella")
            line += 20

        background = self._frame_around("tabella", x, y, x + wiring.COL_WIDTH,
                               self.L("ad_tabella"))

        # --- la distinta: sigla e valore su una riga, i modelli sotto
        # ⚠️ I modelli servono: "un MOSFET" e "un regolatore" non bastano a
        # comprare i pezzi giusti, e sul MOSFET la scelta sbagliata (2N7002)
        # sembra identica e non funziona.
        y1 = background + 14
        line = y1 + 38
        for chunk in PARTS:
            ref, _v, modelli = chunk
            self._text(x + 15, line, ref, "#E4EDF4",
                        self._font(7.5, True, mono=True), tag="distinta")
            self._text(x + 74, line, value_for(chunk, self.L.code),
                        "#B9C7D3", self._font(7),
                        anchor="nw", width=wiring.COL_WIDTH - 90,
                        tag="distinta")
            bounds = self.canvas.bbox("distinta")
            line = (bounds[3] / self.k) + 4 if bounds else line + 14
            board_id = self._text(x + 74, line, modelli, "#7C8B99",
                                         self._font(6.5), anchor="nw",
                                         width=wiring.COL_WIDTH - 90,
                                         tag="distinta")
            bounds = self.canvas.bbox(board_id)
            line = (bounds[3] / self.k) + 11 if bounds else line + 24

        board_id = self._text(x + 15, line + 2, self.L("ad_gia_pronti"),
                                     "#8FC2E3", self._font(6.5), anchor="nw",
                                     width=wiring.COL_WIDTH - 30,
                                     tag="distinta")
        background = self._frame_around("distinta", x, y1, x + wiring.COL_WIDTH,
                               self.L("ad_distinta"))

        y2 = background + 14
        line = y2 + 38
        for index, key in enumerate(NOTES):
            colour = T.CRIT if index == 0 else T.WARN
            a, b = self._s(x + 15, line + 4)
            r = self._s(3)
            self.canvas.create_oval(a - r, b - r, a + r, b + r, fill=colour,
                                  outline="", tags="avvisi")
            board_id = self._text(x + 26, line, self.L(key), "#B9C7D3",
                                         self._font(7), anchor="nw",
                                         width=wiring.COL_WIDTH - 42,
                                         tag="avvisi")
            bounds = self.canvas.bbox(board_id)
            line += ((bounds[3] - bounds[1]) / self.k if bounds else 34) + 15
        self._frame_around("avvisi", x, y2, x + wiring.COL_WIDTH,
                       self.L("ad_note_titolo"))


def open_window(parent, tm, L):
    """Apre lo schema dell'adattatore, o riporta davanti quello aperto."""
    existing = getattr(parent, "_shifter_window", None)
    if existing is not None and existing.winfo_exists():
        existing.deiconify()
        existing.lift()
        existing.focus_set()
        return existing
    window = LevelShifter(parent, tm, L)
    parent._finestra_adattatore = window
    return window
