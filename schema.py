# -*- coding: utf-8 -*-
"""Lo schema dei collegamenti, disegnato a codice e in scala.

Perche' disegnato e non un'immagine: resta nitido a qualunque dimensione, segue
il tema e sta dentro l'eseguibile senza file esterni.

LE FONTI, e sono d'accordo fra loro:
  mothenjoyer69/bc250-documentation  e  elektricM/amd-bc250-docs
pubblicano entrambe questa disposizione del J4004:

      [ GND SCLK MOSI UNK ]
      [ VCC  CS  MISO     ]
         ^  piedino 1, triangolo bianco in serigrafia

La seconda fonte la numera a colonne (1 VCC / 2 GND, 3 CS / 4 SCLK, 5 MISO /
6 MOSI, 7 n.d. / 8 UNK): rimessa in fila e' la stessa cosa, i dispari sono la
fila di sotto e i pari quella di sopra.
⚠️ UNK e' a massa tramite 10 kOhm: non si collega.

La piedinatura del Pico e' quella ufficiale RP2040: 1-20 scendendo a sinistra,
21-40 risalendo a destra, USB in alto.

I PERCORSI DEI CAVETTI sono calcolati per non incrociarsi mai: chi va alla fila
di sopra passa sopra la scheda, chi va a quella di sotto passa sotto.
"""
from __future__ import unicode_literals

import tkinter as tk

import tema as T

# ------------------------------------------------------- dati, non disegno

PICO_SX = [
    (1, "GP0"), (2, "GP1"), (3, "GND"), (4, "GP2"), (5, "GP3"),
    (6, "GP4"), (7, "GP5"), (8, "GND"), (9, "GP6"), (10, "GP7"),
    (11, "GP8"), (12, "GP9"), (13, "GND"), (14, "GP10"), (15, "GP11"),
    (16, "GP12"), (17, "GP13"), (18, "GND"), (19, "GP14"), (20, "GP15"),
]
PICO_DX = [   # dal basso verso l'alto, come sono numerati davvero
    (21, "GP16"), (22, "GP17"), (23, "GND"), (24, "GP18"), (25, "GP19"),
    (26, "GP20"), (27, "GP21"), (28, "GND"), (29, "GP22"), (30, "RUN"),
    (31, "GP26"), (32, "GP27"), (33, "AGND"), (34, "GP28"), (35, "ADC_VREF"),
    (36, "3V3 OUT"), (37, "3V3_EN"), (38, "GND"), (39, "VSYS"), (40, "VBUS"),
]

J4004 = [   # (colonna, fila, numero, nome)
    (0, "bassa", 1, "VCC"), (0, "alta", 2, "GND"),
    (1, "bassa", 3, "CS"), (1, "alta", 4, "SCLK"),
    (2, "bassa", 5, "MISO"), (2, "alta", 6, "MOSI"),
    (3, "bassa", 7, None), (3, "alta", 8, "UNK"),
]

COLLEGAMENTI = [   # (segnale, piedino Pico, nome Pico, piedino J4004)
    ("VCC", 36, "3V3 OUT", 1),
    ("GND", 3, "GND", 2),
    ("CS", 7, "GP5", 3),
    ("SCLK", 4, "GP2", 4),
    ("MISO", 6, "GP4", 5),
    ("MOSI", 5, "GP3", 6),
]

AVVISI = ("sch_av1", "sch_av2", "sch_av3", "sch_av4")

# --------------------------------------------------------------- geometria
# Tutto in coordinate «naturali»: al disegno vengono moltiplicate per k.
LARG, ALT = 1030, 566

# IL CONNETTORE STA A SINISTRA, e non e' un capriccio: i quattro segnali
# (SCLK, MOSI, MISO, CS) escono dai piedini 4-7, che sul Pico sono sul fianco
# SINISTRO. Mettendo il J4004 da quella parte i quattro cavi vanno dritti, e
# solo alimentazione e massa — che escono a destra — devono fare il giro.
# Col connettore a destra giravano in quattro, e il disegno diventava un
# groviglio di cornici.
PX0, PY0 = 430, 140           # scheda Pico
PLARG, PALT = 190, 358
PPASSO, PPRIMO = 16, 170
PADL, PADH = 11, 8

# ⚠️ Il connettore e' disegnato con le piazzole piu' distanziate del vero: il
# passo reale e' 2,54 mm ed e' scritto nella nota. Distanziarle serve a far
# stare numero e nome DENTRO la piazzola, unico posto dove non finiscono sotto
# ai cavetti. Posizioni, verso e piedino 1 restano quelli veri.
CX = [170, 216, 262, 308]     # colonne del J4004
CY = {"alta": 292, "bassa": 356}
CPAD = 15

# GND si prende dal piedino 3, non dal 38: sta sul fianco sinistro accanto ai
# quattro segnali (3-4-5-6-7 contigui, un solo pettine da cinque) e cosi' UN
# SOLO cavo — il 3V3 — deve fare il giro della scheda.
VCC_GIU = 520                 # corsia sotto, per il solo VCC
VCC_X = 686                   # verticale a destra della scheda
GND_X = 140                   # verticale a sinistra, appena fuori dal guscio
LANE = (420, 440)             # rientri sotto a sinistra: MISO, CS
RIENTRO = (350, 368)          # verticali corrispondenti

TITOLO_Y, NOTA_Y = 62, 76
COL_X, COL_LARG = 730, 280


def y_pico(numero):
    if numero <= 20:
        return PPRIMO + (numero - 1) * PPASSO
    return PPRIMO + (40 - numero) * PPASSO


class Schema(tk.Toplevel):
    """La finestra dello schema: si ridisegna in scala quando cambia misura."""

    def __init__(self, padre, tm, L):
        tk.Toplevel.__init__(self, padre, background=T.INK)
        self.tema = tm
        self.L = L
        self.k = 1.0
        self._attesa = None
        self.title(L("sch_titolo"))
        self.geometry("1060x630")
        self.minsize(660, 420)

        self.tela = tk.Canvas(self, background=T.INK, highlightthickness=0, bd=0)
        self.tela.pack(fill="both", expand=True)
        self.tela.bind("<Configure>", self._forse_ridisegna)
        self.bind("<Escape>", lambda _e: self.destroy())
        T.titolo_scuro(self)

    # ------------------------------------------------------------- scala
    def _forse_ridisegna(self, _evento=None):
        if self._attesa:
            self.after_cancel(self._attesa)
        self._attesa = self.after(70, self.disegna)

    def _s(self, *valori):
        """Coordinate in scala. Restituisce un numero o una lista, come arriva."""
        if len(valori) == 1:
            return valori[0] * self.k
        return [v * self.k for v in valori]

    def _car(self, punti, grassetto=False, mono=False):
        """Un carattere in scala, mai sotto il leggibile."""
        famiglia = self.tema.mono if mono else self.tema.ui
        misura = max(6, int(round(punti * self.k)))
        return (famiglia, misura, "bold") if grassetto else (famiglia, misura)

    # ------------------------------------------------------------ pennelli
    def _testo(self, x, y, testo, colore=T.FG, carattere=None, ancora="w",
               larghezza=None, tag=None):
        return self.tela.create_text(
            self._s(x), self._s(y), text=testo, fill=colore, anchor=ancora,
            font=carattere or self._car(8),
            width=self._s(larghezza) if larghezza else None,
            tags=tag or ())

    def _rett(self, x0, y0, x1, y1, fondo=T.PANEL, bordo=T.LINE, spessore=1,
              tratteggio=None, tag=None):
        a, b, c, d = self._s(x0, y0, x1, y1)
        return self.tela.create_rectangle(a, b, c, d, fill=fondo, outline=bordo,
                                          width=spessore, dash=tratteggio,
                                          tags=tag or ())

    def _riquadra(self, tag, x0, y0, x1, titolo, margine=13):
        """Disegna il riquadro ATTORNO a quello che c'e' gia', misurandolo.

        ⚠️ Prima si scriveva il contenuto dentro un riquadro di altezza decisa
        a mano, e con le frasi lunghe il testo usciva dal bordo. Qui si misura
        cio' che e' stato disegnato (bbox) e il riquadro gli si adatta; poi lo
        si manda sotto, cosi' il contenuto resta sopra.
        """
        limiti = self.tela.bbox(tag)
        fondo = (limiti[3] / self.k) + margine if limiti else y0 + 46
        sfondo = self._rett(x0, y0, x1, fondo)
        self.tela.tag_lower(sfondo)
        self._testo(x0 + 11, y0 + 12, T.micro(titolo), T.MUT, self._car(7, True))
        a, b = self._s(x0 + 11, y0 + 23)
        self.tela.create_line(a, b, self._s(x1 - 11), b, fill=T.LINE)
        return fondo

    def _filo(self, punti, colore):
        """Cavetto: contorno scuro sotto per staccarlo dal fondo, colore sopra.

        ⚠️ Angoli VIVI, non spline: la curva approssimata sembra tracciata a
        mano e non passa nemmeno per i punti dati. Qui i percorsi sono
        ortogonali e devono restare tali, con il solo raccordo tondo del giunto.
        """
        piatti = []
        for x, y in punti:
            piatti += [self._s(x), self._s(y)]
        for larghezza, tinta in ((max(3.2, 5.2 * self.k), "#060B10"),
                                 (max(1.8, 2.9 * self.k), colore)):
            self.tela.create_line(*piatti, fill=tinta, width=larghezza,
                                  capstyle="round", joinstyle="round")

    # ------------------------------------------------------------ disegno
    def disegna(self):
        self._attesa = None
        larghezza = max(self.tela.winfo_width(), 300)
        altezza = max(self.tela.winfo_height(), 240)
        self.k = max(0.52, min(larghezza / float(LARG), altezza / float(ALT), 1.7))
        self.tela.delete("all")
        self.tela.configure(scrollregion=(0, 0, self._s(LARG), self._s(ALT)))
        self._testata(larghezza)
        self._scheda_pico()
        self._connettore()
        self._fili()
        self._colonna_destra()

    def _testata(self, larghezza_vera):
        alta = self._s(52)
        # il gradiente si mette da solo sul fondo: se ci disegnassimo sotto un
        # rettangolo pieno lo coprirebbe
        T.gradiente(self.tela, larghezza_vera, alta)
        self.tela.create_line(0, alta, larghezza_vera, alta, fill=T.LINE)
        self._testo(20, 18, self.L("sch_titolo"), T.FG, self._car(12, True))
        self._testo(21, 37, self.L("sch_sotto"), T.MUT, self._car(8))

    # -- il Pico ----------------------------------------------------------
    def _scheda_pico(self):
        t = self.tela
        x1, y1 = PX0 + PLARG, PY0 + PALT

        self._testo(PX0, TITOLO_Y, T.micro(self.L("sch_pico")), T.MUT,
                    self._car(7, True))
        self._testo(PX0, NOTA_Y, self.L("sch_pico_nota"), "#5E7488", self._car(7),
                    larghezza=230)

        # circuito stampato
        self._rett(PX0, PY0, x1, y1, "#0E3428", "#1C5943")
        # connettore USB, l'unico riferimento di verso che conta
        self._rett(PX0 + 63, PY0 - 9, x1 - 63, PY0 + 13, "#8C93A0", "#B9C1CC")
        self._rett(PX0 + 71, PY0 - 4, x1 - 71, PY0 + 8, "#4E5561", "#4E5561")
        self._testo((PX0 + x1) / 2.0, PY0 - 19, "USB", T.MUT, self._car(7, True),
                    ancora="center")

        usati = {c[1]: c[0] for c in COLLEGAMENTI}

        for elenco, lato in ((PICO_SX, "sx"), (PICO_DX, "dx")):
            for numero, nome in elenco:
                y = y_pico(numero)
                segnale = usati.get(numero)
                colore = T.FILO[segnale] if segnale else None

                if lato == "sx":
                    pad0, pad1 = PX0 - PADL, PX0
                    x_num, x_nome, ancora = PX0 + 6, PX0 + 21, "w"
                else:
                    pad0, pad1 = x1, x1 + PADL
                    x_num, x_nome, ancora = x1 - 6, x1 - 21, "e"

                if colore:      # alone, perche' salti all'occhio
                    self._rett(pad0 - 2.5, y - PADH / 2.0 - 2.5,
                               pad1 + 2.5, y + PADH / 2.0 + 2.5, "", colore)
                self._rett(pad0, y - PADH / 2.0, pad1, y + PADH / 2.0,
                           colore or "#C9A227", colore or "#8A6F1B")
                self._testo(x_num, y, str(numero),
                            "#8FA6B8" if not colore else "#E4EDF4",
                            self._car(6.5, bool(colore), mono=True), ancora=ancora)
                # per GND il nome del piedino e' gia' il segnale: non si ripete
                etichetta = nome
                if colore and segnale != nome:
                    etichetta = "%s · %s" % (nome, segnale)
                self._testo(x_nome, y, etichetta,
                            colore or "#7E9C8C", self._car(7, bool(colore)),
                            ancora=ancora)

    # -- il connettore -----------------------------------------------------
    def _connettore(self):
        x0, x1 = CX[0] - CPAD - 9, CX[3] + CPAD + 9
        y0, y1 = CY["alta"] - CPAD - 9, CY["bassa"] + CPAD + 9

        self._testo(x0, TITOLO_Y, T.micro(self.L("sch_conn")), T.MUT,
                    self._car(7, True))
        self._testo(x0, NOTA_Y, self.L("sch_conn_nota"), "#5E7488", self._car(7),
                    larghezza=210)

        self._rett(x0, y0, x1, y1, "#171E26", "#2E3A46")
        self._rett(x0 + 3, y0 + 3, x1 - 3, y1 - 3, "", "#0D131A")

        # triangolo del piedino 1, come sulla serigrafia: accanto a VCC
        tx, ty = self._s(x0 - 8), self._s(CY["bassa"])
        d = self._s(6)
        self.tela.create_polygon(tx - d * 0.7, ty - d, tx - d * 0.7, ty + d,
                                 tx + d * 0.7, ty, fill="#E4EDF4", outline="")
        self._testo(x0 - 20, CY["bassa"], "1", "#E4EDF4",
                    self._car(7, True, mono=True), ancora="e")

        per_numero = {c[3]: c[0] for c in COLLEGAMENTI}
        for colonna, fila, numero, nome in J4004:
            x, y = CX[colonna], CY[fila]
            segnale = per_numero.get(numero)
            colore = T.FILO[segnale] if segnale else None
            if nome is None:
                self._rett(x - CPAD, y - CPAD, x + CPAD, y + CPAD, "", "#39434E",
                           tratteggio=(2, 3))
                self._testo(x, y - 5, str(numero), "#4B5967",
                            self._car(6, mono=True), ancora="center")
                self._testo(x, y + 6, self.L("sch_nc"), "#4B5967", self._car(6),
                            ancora="center")
                continue
            self._rett(x - CPAD, y - CPAD, x + CPAD, y + CPAD,
                       colore or "#20262E", colore or "#3A4652")
            # numero e nome DENTRO la piazzola: fuori finirebbero sotto ai cavi
            scuro = bool(colore)
            self._testo(x, y - 5, str(numero),
                        "#0A1017" if scuro else "#54657A",
                        self._car(6, mono=True), ancora="center")
            self._testo(x, y + 6, nome, "#0A1017" if scuro else "#7C8B99",
                        self._car(6.5, True), ancora="center")

        # ⚠️ Spostata a destra del risalitore del VCC (x = CX[0]): li' sotto ci
        # passa il cavo rosso e la scritta diventava illeggibile.
        # ⚠️ Larghezza fermata a 200: piu' larga arrivava a sbattere contro la
        # scheda Pico (che comincia a x=430) e le ultime parole finivano sotto
        # ai piedini.
        self._testo(CX[0] + 34, 456, self.L("sch_unk"), "#93A5B4",
                    self._car(7), ancora="nw", larghezza=200)

    # -- i cavetti ---------------------------------------------------------
    def _fili(self):
        sx = PX0 - PADL
        dx = PX0 + PLARG + PADL
        miso_lane, cs_lane = LANE
        miso_x, cs_x = RIENTRO

        # i cavi si fermano sul BORDO della piazzola, non al centro: dentro ci
        # stanno numero e nome
        alta = CY["alta"] - CPAD
        bassa = CY["bassa"] + CPAD

        # i quattro segnali: dal fianco sinistro del Pico al connettore, dritti
        self._filo([(sx, y_pico(4)), (CX[1], y_pico(4)),
                    (CX[1], alta)], T.FILO["SCLK"])
        self._filo([(sx, y_pico(5)), (CX[2], y_pico(5)),
                    (CX[2], alta)], T.FILO["MOSI"])
        self._filo([(sx, y_pico(6)), (miso_x, y_pico(6)), (miso_x, miso_lane),
                    (CX[2], miso_lane), (CX[2], bassa)], T.FILO["MISO"])
        self._filo([(sx, y_pico(7)), (cs_x, y_pico(7)), (cs_x, cs_lane),
                    (CX[1], cs_lane), (CX[1], bassa)], T.FILO["CS"])

        # GND esce anche lui a sinistra e rientra di fianco: la sua piazzola
        # sta nella fila di sopra, sulla stessa colonna di VCC
        self._filo([(sx, y_pico(3)), (GND_X, y_pico(3)), (GND_X, CY["alta"]),
                    (CX[0] - CPAD, CY["alta"])], T.FILO["GND"])
        # il 3V3 e' l'unico che esce a destra: gira sotto, fuori dal bordo
        self._filo([(dx, y_pico(36)), (VCC_X, y_pico(36)), (VCC_X, VCC_GIU),
                    (CX[0], VCC_GIU), (CX[0], bassa)], T.FILO["VCC"])

    # -- colonna di destra: tabella e avvisi -------------------------------
    def _colonna_destra(self):
        x = COL_X
        y = TITOLO_Y - 12

        riga = y + 38
        for etichetta, dx in ((self.L("sch_col_segnale"), 30),
                              (self.L("sch_col_pico"), 130),
                              (self.L("sch_col_conn"), 215)):
            self._testo(x + dx, riga, T.micro(etichetta), "#55697C",
                        self._car(6, True), tag="tabella")
        riga += 15

        for segnale, pin_pico, nome_pico, pin_conn in COLLEGAMENTI:
            colore = T.FILO[segnale]
            a, b, c = self._s(x + 12, riga, x + 23)
            self.tela.create_line(a, b, c, b, fill=colore, tags="tabella",
                                  width=max(2.0, 3.0 * self.k), capstyle="round")
            self._testo(x + 30, riga, segnale, colore, self._car(8, True),
                        tag="tabella")
            self._testo(x + 130, riga, "%2d  %s" % (pin_pico, nome_pico), T.FG,
                        self._car(7, mono=True), tag="tabella")
            self._testo(x + 215, riga, "%d  %s" % (pin_conn, segnale), T.FG,
                        self._car(7, mono=True), tag="tabella")
            riga += 21

        a, b = self._s(x + 12, riga - 8)
        self.tela.create_line(a, b, self._s(x + COL_LARG - 12), b, fill=T.LINE,
                              tags="tabella")
        # ⚠️ ancora "nw", non "w": con l'ancoraggio al centro un testo che va a
        # capo si estende anche SOPRA il punto dato, e finiva addosso al filetto.
        self._testo(x + 12, riga - 1, self.L("sch_gnd_nota"), "#6E8296",
                    self._car(7), ancora="nw", larghezza=COL_LARG - 24,
                    tag="tabella")

        # il riquadro si adatta a quello che c'e' dentro, non viceversa
        fondo = self._riquadra("tabella", x, y, x + COL_LARG,
                               self.L("sch_tabella"))

        # --- avvisi
        y2 = fondo + 14
        riga = y2 + 38
        for indice, chiave in enumerate(AVVISI):
            colore = T.CRIT if indice < 2 else T.WARN
            a, b = self._s(x + 15, riga + 4)
            r = self._s(3)
            self.tela.create_oval(a - r, b - r, a + r, b + r, fill=colore,
                                  outline="", tags="avvisi")
            identificativo = self._testo(x + 26, riga, self.L(chiave), "#B9C7D3",
                                         self._car(7), ancora="nw",
                                         larghezza=COL_LARG - 42, tag="avvisi")
            # ogni avviso scende di quanto occupa DAVVERO: in inglese e in
            # italiano le righe non sono le stesse
            limiti = self.tela.bbox(identificativo)
            riga += ((limiti[3] - limiti[1]) / self.k if limiti else 34) + 15

        self._riquadra("avvisi", x, y2, x + COL_LARG, self.L("sch_av_titolo"))

        # Le fonti della piedinatura non stanno piu' nel disegno: restano nella
        # documentazione e in testa a questo file, dove servono a chi verifica.


def apri(padre, tm, L):
    """Apre lo schema, o riporta davanti quello gia' aperto."""
    esistente = getattr(padre, "_finestra_schema", None)
    if esistente is not None and esistente.winfo_exists():
        esistente.deiconify()
        esistente.lift()
        esistente.focus_set()
        return esistente
    finestra = Schema(padre, tm, L)
    padre._finestra_schema = finestra
    return finestra
