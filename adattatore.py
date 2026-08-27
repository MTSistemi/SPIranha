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

import schema
import stampa
import tema as T

# ------------------------------------------------------------------ dati

# I quattro segnali che passano dall'adattatore, e come sono orientati.
CANALI = (
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
PEZZI = (
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


def valore(pezzo, lingua="it"):
    """La colonna «cosa» del pezzo, nella lingua giusta."""
    testo = pezzo[1]
    if isinstance(testo, dict):
        return testo.get(lingua) or testo.get("it") or ""
    return testo

NOTE = ("ad_nota1", "ad_nota3", "ad_nota5", "ad_nota6")

# --------------------------------------------------------------- geometria
# Un canale solo, disegnato in grande: gli altri tre sono identici e
# disegnarli tutti e quattro non aggiunge un'informazione, aggiunge righe.
RAIL_ALTO_Y = 132              # barra dei 3,3 V
RAIL_BASSO_Y = 300             # barra degli 1,8 V
CANALE_Y = 216                 # il segnale, in mezzo alle due barre
X_RAIL0, X_RAIL1 = 56, 620     # da dove a dove arrivano le due barre
X_PICO, X_CHIP = 112, 560      # dove comincia e finisce il filo del segnale
X_MOS = 336                    # il transistor, al centro
X_R_ALTA, X_R_BASSA = 232, 440  # le due resistenze di tiraggio
# ⚠️ La presa del regolatore sta PRIMA dell'inizio del segnale (x=112): messa
# in mezzo, il suo filo attraversava la linea del segnale e sembrava toccarla.
X_ENTRATA, X_USCITA = 76, 500
LDO_X, LDO_Y = 216, 400        # il regolatore, sotto
# ⚠️ La colonna di destra ha tre riquadri e arriva a 720: misurato, non
# stimato. Se ALT_AD e' piu' corto dell'altezza vera, la scala si calcola su
# un disegno che non c'e' e l'ultima nota finisce fuori dalla finestra.
ALT_AD = 720
# ⚠️ Nel PDF va SOLO il circuito: la colonna di destra diventa una
# tabella vera nella seconda pagina, che in stampa si legge meglio di
# un riquadro fotografato.
AREA_DISEGNO = (10, 60, 700, 600)
LDO_L, LDO_A = 140, 44


class Adattatore(schema.Schema):
    """La finestra dello schema elettrico: riusa i pennelli di Schema."""

    def __init__(self, padre, tm, L):
        schema.Schema.__init__(self, padre, tm, L, pinza=True)
        self.title(L("ad_titolo"))
        # ⚠️ 800 di altezza, non 700: il contenuto naturale arriva a 720 e
        # con la scala guidata dalla larghezza diventano ~755 pixel.
        # Misurato: a occhio l'ultima nota restava fuori.
        self.geometry("1080x800")

    # ------------------------------------------------------------ disegno
    def disegna(self):
        self._attesa = None
        larghezza = max(self.tela.winfo_width(), 300)
        altezza = max(self.tela.winfo_height(), 240)
        self.k = max(0.52, min(larghezza / float(schema.LARG),
                               altezza / float(ALT_AD), 1.7))
        self.tela.delete("all")
        self._testata_ad(larghezza)
        self._barre()
        self._canale()
        self._regolatore()
        self._colonna_ad()
        self._misura_disegno()

    def _testata_ad(self, larghezza_vera):
        alta = self._s(52)
        T.gradiente(self.tela, larghezza_vera, alta)
        self.tela.create_line(0, alta, larghezza_vera, alta, fill=T.LINE)
        self._testo(20, 18, self.L("ad_titolo"), T.FG, self._car(12, True))
        self._testo(21, 37, self.L("ad_sotto"), T.MUT, self._car(8))

        # il tasto per la stampa: una pillola disegnata, come il resto
        larghezza_pillola = 96
        x0 = (larghezza_vera / self.k) - larghezza_pillola - 16
        self._rett(x0, 14, x0 + larghezza_pillola, 38, "#1D2937", "#2A3846",
                   tag="pdf")
        self._testo(x0 + larghezza_pillola / 2.0, 26, self.L("ad_pdf"),
                    "#8FC2E3", self._car(7.5, True), ancora="center",
                    tag="pdf")
        self.tela.tag_bind("pdf", "<Button-1>", lambda _e: self.esporta_pdf())
        self.tela.tag_bind("pdf", "<Enter>",
                           lambda _e: self.tela.configure(cursor="hand2"))
        self.tela.tag_bind("pdf", "<Leave>",
                           lambda _e: self.tela.configure(cursor=""))

    # -- stampa ------------------------------------------------------------
    def esporta_pdf(self, percorso=None):
        """Il disegno e la distinta in un PDF stampabile."""
        if percorso is None:
            if stampa.trova_chrome() is None:
                messagebox.showwarning(self.L("ad_titolo"),
                                       self.L("ad_pdf_niente_chrome"),
                                       parent=self)
                return None
            percorso = filedialog.asksaveasfilename(
                parent=self, title=self.L("ad_pdf_dove"), defaultextension=".pdf",
                initialfile="adattatore-1v8.pdf",
                filetypes=[("PDF", "*.pdf")])
            if not percorso:
                return None
        # ⚠️ Il tasto non deve finire nel PDF: e' un comando, non un disegno.
        self.tela.delete("pdf")
        area = [self._s(v) for v in AREA_DISEGNO]
        disegno = stampa.svg_da_tela(self.tela, area)
        pagina = stampa.html_adattatore(
            disegno, self.L,
            [(p[0], valore(p, self.L.codice), p[2]) for p in PEZZI],
            CANALI, NOTE, self.L("ad_gia_pronti"),
            self.L("ad_titolo"), self.L("ad_sotto"))
        fatto, motivo = stampa.in_pdf(pagina, percorso)
        self.disegna()
        if not fatto:
            messagebox.showerror(self.L("ad_titolo"),
                                 self.L("ad_pdf_errore", motivo=motivo),
                                 parent=self)
            return None
        messagebox.showinfo(self.L("ad_titolo"),
                            self.L("ad_pdf_fatto",
                                   file=os.path.basename(percorso)),
                            parent=self)
        return percorso

    # -- le due alimentazioni ---------------------------------------------
    def _barre(self):
        # ⚠️ Le scritte vanno SOPRA la barra, non a sinistra: a sinistra
        # occupavano lo spazio da cui scende la presa del regolatore.
        for y, etichetta, colore, x_da in (
                (RAIL_ALTO_Y, self.L("ad_rail_alto"), T.FILO["VCC"], X_RAIL0),
                (RAIL_BASSO_Y, self.L("ad_rail_basso"), "#F0A93B",
                 X_ENTRATA + 24)):
            a, b, c = self._s(x_da, y, X_RAIL1)
            self.tela.create_line(a, b, c, b, fill=colore,
                                  width=max(1.6, 2.4 * self.k))
            self._testo(x_da + 4, y - 13, etichetta, colore,
                        self._car(8, True))

    # -- un canale: MOSFET e due resistenze -------------------------------
    def _canale(self):
        colore = T.FILO["MOSI"]

        # ⚠️ Il filo NON passa dietro al transistor: il transistor lo
        # interrompe, ed e' tutto il punto del montaggio.
        self._filo([(X_PICO, CANALE_Y), (X_MOS - 40, CANALE_Y)], colore)
        self._filo([(X_MOS + 40, CANALE_Y), (X_CHIP, CANALE_Y)], colore)

        self._testo(X_PICO, CANALE_Y - 14, self.L("ad_lato_pico"), "#B9C7D3",
                    self._car(7, True))
        self._testo(X_CHIP, CANALE_Y - 14, self.L("ad_lato_chip"), "#B9C7D3",
                    self._car(7, True), ancora="e")

        # le due resistenze di tiraggio, una per lato
        self._resistenza(X_R_ALTA, RAIL_ALTO_Y, CANALE_Y, "R5", "1k")
        self._resistenza(X_R_BASSA, RAIL_BASSO_Y, CANALE_Y, "R1", "1k")

        self._mosfet(X_MOS, CANALE_Y)

        # ⚠️ Il verso del transistor non e' simmetrico: il source guarda il
        # lato a 1,8 V. Montato al contrario il MOSFET conduce sempre e i due
        # lati restano attaccati, cioe' il chip prende 3,3 V lo stesso.
        self._testo(X_ENTRATA + 28, RAIL_BASSO_Y + 24, self.L("ad_verso"),
                    "#93A5B4", self._car(7), ancora="nw", larghezza=340)

    def _resistenza(self, x, y_rail, y_segnale, sigla, valore):
        """Resistenza verticale fra la barra e il filo del segnale."""
        meta = (y_rail + y_segnale) / 2.0
        alta, bassa = meta - 22, meta + 22
        self._filo([(x, y_rail), (x, alta)], "#5E7488")
        self._filo([(x, bassa), (x, y_segnale)], "#5E7488")
        self._rett(x - 11, alta, x + 11, bassa, "#141A21", "#7C8B99")
        self._testo(x + 18, meta - 7, sigla, "#93A5B4", self._car(7, True))
        self._testo(x + 18, meta + 6, valore, "#6E8296", self._car(7))
        # il pallino di giunzione: senza, un incrocio sembra un incrocio
        self._nodo(x, y_segnale)

    def _nodo(self, x, y):
        a, b = self._s(x, y)
        r = self._s(3.2)
        self.tela.create_oval(a - r, b - r, a + r, b + r, fill="#B9C7D3",
                              outline="")

    def _mosfet(self, x, y):
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
        largo = 32
        y_canale = y + 13           # le tre barrette del canale
        y_gate = y + 22             # la placca di gate, staccata sotto

        for x0, x1 in ((x - largo, x - 10), (x - 7, x + 7), (x + 10, x + largo)):
            a, b = self._s(x0, y_canale)
            self.tela.create_line(a, b, self._s(x1), b, fill="#B9C7D3",
                                  width=max(1.5, 2.2 * self.k))
        a, b = self._s(x - largo, y_gate)
        self.tela.create_line(a, b, self._s(x + largo), b, fill="#B9C7D3",
                              width=max(1.5, 2.2 * self.k))

        # drain a sinistra (lato 3,3 V), source a destra (lato 1,8 V)
        self._filo([(X_MOS - 40, y), (x - largo + 6, y),
                    (x - largo + 6, y_canale)], "#8FA2B2")
        self._filo([(x + largo - 6, y_canale), (x + largo - 6, y),
                    (X_MOS + 40, y)], "#8FA2B2")
        # il gate sta fisso a 1,8 V: e' quello che fa funzionare tutto
        self._filo([(x, y_gate), (x, RAIL_BASSO_Y)], "#F0A93B")
        self._nodo(x, RAIL_BASSO_Y)

        # ⚠️ le sigle sotto il filo, non sopra: sopra finivano sul cavetto
        self._testo(x - largo - 3, y + 4, "D", "#93A5B4",
                    self._car(6.5, True, mono=True), ancora="e")
        self._testo(x + largo + 3, y + 4, "S", "#93A5B4",
                    self._car(6.5, True, mono=True))
        self._testo(x + largo + 6, y_gate - 2, "G", "#93A5B4",
                    self._car(6.5, True, mono=True))
        self._testo(x, y - 30, "Q1 · BSS138", "#93A5B4",
                    self._car(7, True), ancora="center")

    # -- il regolatore da 3,3 a 1,8 ---------------------------------------
    def _regolatore(self):
        x0, y0 = LDO_X, LDO_Y
        x1, y1 = x0 + LDO_L, y0 + LDO_A
        self._rett(x0, y0, x1, y1, "#141A21", "#7C8B99")
        self._testo((x0 + x1) / 2.0, y0 + 15, "U1", "#E4EDF4",
                    self._car(8, True), ancora="center")
        self._testo((x0 + x1) / 2.0, y0 + 31, self.L("ad_ldo"), "#93A5B4",
                    self._car(6.5), ancora="center")

        meta = y0 + LDO_A / 2.0
        # ingresso dal 3,3 (preso a sinistra di tutto), uscita sugli 1,8
        self._filo([(X_ENTRATA, RAIL_ALTO_Y), (X_ENTRATA, meta), (x0, meta)],
                   T.FILO["VCC"])
        self._nodo(X_ENTRATA, RAIL_ALTO_Y)
        self._filo([(x1, meta), (X_USCITA, meta), (X_USCITA, RAIL_BASSO_Y)],
                   "#F0A93B")
        self._nodo(X_USCITA, RAIL_BASSO_Y)

        # i due condensatori, uno per lato: senza, il regolatore oscilla
        self._condensatore(X_ENTRATA + 60, meta, "C1")
        self._condensatore(X_USCITA - 44, meta, "C2")
        self._nodo(X_ENTRATA + 60, meta)
        self._nodo(X_USCITA - 44, meta)
        self._testo(X_ENTRATA + 28, y1 + 86, self.L("ad_ldo_nota"), "#93A5B4",
                    self._car(7), ancora="nw", larghezza=430)

    def _condensatore(self, x, y, sigla):
        """Appeso al filo: dal nodo scende, due piatti, poi massa."""
        self._filo([(x, y), (x, y + 26)], "#5E7488")
        for dy, largo in ((26, 15), (36, 15)):
            a, b = self._s(x - largo, y + dy)
            self.tela.create_line(a, b, self._s(x + largo), b, fill="#B9C7D3",
                                  width=max(1.4, 2.0 * self.k))
        self._filo([(x, y + 36), (x, y + 58)], "#5E7488")
        self._massa(x, y + 58)
        self._testo(x + 22, y + 31, sigla, "#93A5B4", self._car(7, True))

    def _massa(self, x, y):
        for indice, largo in enumerate((14, 9, 4)):
            a, b = self._s(x - largo, y + indice * 5)
            self.tela.create_line(a, b, self._s(x + largo), b, fill="#8FA2B2",
                                  width=max(1.2, 1.8 * self.k))

    # -- colonna di destra: pezzi e note ----------------------------------
    def _colonna_ad(self):
        x = schema.COL_X
        y = schema.TITOLO_Y - 12
        riga = y + 38

        for etichetta, dx in ((self.L("ad_col_segnale"), 26),
                              (self.L("sch_col_pico"), 110),
                              (self.L("sch_col_chip"), 190)):
            self._testo(x + dx, riga, T.micro(etichetta), "#55697C",
                        self._car(6, True), tag="tabella")
        riga += 15
        for segnale, pico, chip, verso in CANALI:
            colore = T.FILO[segnale]
            self._testo(x + 26, riga, segnale, colore, self._car(8, True),
                        tag="tabella")
            self._testo(x + 110, riga, pico, T.FG, self._car(7, mono=True),
                        tag="tabella")
            freccia = "→" if verso == "verso" else "←"
            self._testo(x + 170, riga, freccia, "#6E8296", self._car(7),
                        tag="tabella")
            self._testo(x + 190, riga, chip, T.FG, self._car(7, mono=True),
                        tag="tabella")
            riga += 20

        fondo = self._riquadra("tabella", x, y, x + schema.COL_LARG,
                               self.L("ad_tabella"))

        # --- la distinta: sigla e valore su una riga, i modelli sotto
        # ⚠️ I modelli servono: "un MOSFET" e "un regolatore" non bastano a
        # comprare i pezzi giusti, e sul MOSFET la scelta sbagliata (2N7002)
        # sembra identica e non funziona.
        y1 = fondo + 14
        riga = y1 + 38
        for pezzo in PEZZI:
            sigla, _v, modelli = pezzo
            self._testo(x + 15, riga, sigla, "#E4EDF4",
                        self._car(7.5, True, mono=True), tag="distinta")
            self._testo(x + 74, riga, valore(pezzo, self.L.codice),
                        "#B9C7D3", self._car(7),
                        ancora="nw", larghezza=schema.COL_LARG - 90,
                        tag="distinta")
            limiti = self.tela.bbox("distinta")
            riga = (limiti[3] / self.k) + 4 if limiti else riga + 14
            identificativo = self._testo(x + 74, riga, modelli, "#7C8B99",
                                         self._car(6.5), ancora="nw",
                                         larghezza=schema.COL_LARG - 90,
                                         tag="distinta")
            limiti = self.tela.bbox(identificativo)
            riga = (limiti[3] / self.k) + 11 if limiti else riga + 24

        identificativo = self._testo(x + 15, riga + 2, self.L("ad_gia_pronti"),
                                     "#8FC2E3", self._car(6.5), ancora="nw",
                                     larghezza=schema.COL_LARG - 30,
                                     tag="distinta")
        fondo = self._riquadra("distinta", x, y1, x + schema.COL_LARG,
                               self.L("ad_distinta"))

        y2 = fondo + 14
        riga = y2 + 38
        for indice, chiave in enumerate(NOTE):
            colore = T.CRIT if indice == 0 else T.WARN
            a, b = self._s(x + 15, riga + 4)
            r = self._s(3)
            self.tela.create_oval(a - r, b - r, a + r, b + r, fill=colore,
                                  outline="", tags="avvisi")
            identificativo = self._testo(x + 26, riga, self.L(chiave), "#B9C7D3",
                                         self._car(7), ancora="nw",
                                         larghezza=schema.COL_LARG - 42,
                                         tag="avvisi")
            limiti = self.tela.bbox(identificativo)
            riga += ((limiti[3] - limiti[1]) / self.k if limiti else 34) + 15
        self._riquadra("avvisi", x, y2, x + schema.COL_LARG,
                       self.L("ad_note_titolo"))


def apri(padre, tm, L):
    """Apre lo schema dell'adattatore, o riporta davanti quello aperto."""
    esistente = getattr(padre, "_finestra_adattatore", None)
    if esistente is not None and esistente.winfo_exists():
        esistente.deiconify()
        esistente.lift()
        esistente.focus_set()
        return esistente
    finestra = Adattatore(padre, tm, L)
    padre._finestra_adattatore = finestra
    return finestra
