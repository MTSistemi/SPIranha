# -*- coding: utf-8 -*-
"""The chip map in little squares, defragmenter style.

A rectangle split into blocks: each stands for a slice of flash and takes its
colour from whatever is happening to it. It is not a decorative animation --
the colours come from what flashrom actually says while it works:

  · the ERASE ranges are exact: flashrom with -V prints an E(start:end)
    marker for every block it erases;
  · the WRITE range is exact (W(start:end) marker) and fills up with the
    percentage from --progress;
  · the READ fills up with the percentage, over the range being read.

So with the board on the desk you can see at a glance how far it has got,
and at the end whether it is green everywhere.
"""
from __future__ import unicode_literals

import tkinter as tk

import theme as T

# stati di un blocco
IGNOTO = 0        # non ancora toccato
FUORI = 1         # fuori dalla regione: non verra' toccato
LETTO = 2
CANCELLATO = 3
SCRITTO = 4
VERIFICATO = 5
DIVERSO = 6       # la verifica finale non torna
ATTIVO = 7        # ci sta lavorando adesso

COLORI = {
    IGNOTO: "#16202B",
    FUORI: "#0E151D",
    LETTO: "#2A5D80",
    CANCELLATO: T.WARN,
    SCRITTO: T.ACCENT,
    VERIFICATO: T.OK,
    DIVERSO: T.CRIT,
    ATTIVO: "#DCEBF7",
}

# ordine e chiavi per la legenda
LEGENDA = ((IGNOTO, "leg_ignoto"), (LETTO, "leg_letto"),
           (CANCELLATO, "leg_cancellato"), (SCRITTO, "leg_scritto"),
           (VERIFICATO, "leg_verificato"), (DIVERSO, "leg_diverso"))

LATO = 6          # lato del quadratino
PASSO = 7         # quadratino + fessura
RIGHE = 8


class Mappa(tk.Canvas):

    def __init__(self, padre, dimensione=16 * 1024 * 1024, righe=RIGHE,
                 su_posizione=None):
        tk.Canvas.__init__(self, padre, background=T.LOG_BG,
                           highlightthickness=1, highlightbackground=T.LINE,
                           bd=0, height=righe * PASSO + 5)
        self.dimensione = dimensione
        self.righe = righe
        self.su_posizione = su_posizione
        self.colonne = 0
        self.stati = []
        self._id = []
        self.regioni = []
        self._evidenziata = None
        self.bind("<Configure>", lambda _e: self._ricostruisci())
        self.bind("<Motion>", self._sotto_il_mouse)
        self.bind("<Leave>", lambda _e: self.su_posizione and self.su_posizione(None))

    # ------------------------------------------------------------- griglia
    @property
    def blocchi(self):
        return len(self.stati)

    def _byte_per_blocco(self):
        return max(1, self.dimensione / float(max(self.blocchi, 1)))

    def _ricostruisci(self):
        larghezza = max(self.winfo_width(), 40)
        colonne = max(16, int((larghezza - 6) // PASSO))
        if colonne == self.colonne and self._id:
            return
        vecchi = list(self.stati)
        self.colonne = colonne
        totale = colonne * self.righe
        self.delete("all")
        self._id = []
        # gli stati vecchi si riproiettano sulla griglia nuova, cosi' un
        # a resize mid-job does not wipe what is on screen
        nuovi = []
        for indice in range(totale):
            if vecchi:
                nuovi.append(vecchi[min(len(vecchi) - 1,
                                        indice * len(vecchi) // totale)])
            else:
                nuovi.append(IGNOTO)
        self.stati = nuovi
        for indice in range(totale):
            colonna, riga = indice % colonne, indice // colonne
            x = 3 + colonna * PASSO
            y = 3 + riga * PASSO
            self._id.append(self.create_rectangle(
                x, y, x + LATO, y + LATO, fill=COLORI[self.stati[indice]],
                outline=""))
        self._disegna_regioni()

    def _disegna_regioni(self):
        self.delete("regione")
        if self._evidenziata is None:
            return
        inizio, fine = self._evidenziata
        primo, ultimo = self._blocco(inizio), self._blocco(fine)
        for indice in (primo, ultimo):
            colonna, riga = indice % self.colonne, indice // self.colonne
            x = 3 + colonna * PASSO
            y = 3 + riga * PASSO
            self.create_rectangle(x - 1, y - 1, x + LATO + 1, y + LATO + 1,
                                  outline=T.MUT, width=1, tags="regione")

    # ------------------------------------------------------------- accesso
    def _blocco(self, posizione):
        if self.blocchi == 0:
            return 0
        indice = int(posizione * self.blocchi // max(self.dimensione, 1))
        return max(0, min(self.blocchi - 1, indice))

    def _sotto_il_mouse(self, evento):
        if not self.su_posizione or not self.blocchi:
            return
        colonna = int((evento.x - 3) // PASSO)
        riga = int((evento.y - 3) // PASSO)
        if colonna < 0 or riga < 0 or colonna >= self.colonne or riga >= self.righe:
            return self.su_posizione(None)
        indice = riga * self.colonne + colonna
        if 0 <= indice < self.blocchi:
            self.su_posizione(int(indice * self._byte_per_blocco()))

    # ------------------------------------------------------------- comandi
    def imposta(self, dimensione=None, regioni=None):
        if dimensione:
            self.dimensione = dimensione
        if regioni is not None:
            self.regioni = regioni
        self._ricostruisci()

    def azzera(self, stato=IGNOTO):
        for indice in range(self.blocchi):
            self._colora(indice, stato)

    def evidenzia(self, intervallo):
        """Marks the bounds of the region about to be worked on."""
        self._evidenziata = intervallo
        if intervallo is None:
            self.azzera(IGNOTO)
        else:
            inizio, fine = intervallo
            self.azzera(FUORI)
            self.segna(inizio, fine, IGNOTO)
        self._disegna_regioni()

    def _colora(self, indice, stato):
        if not (0 <= indice < self.blocchi) or self.stati[indice] == stato:
            return
        self.stati[indice] = stato
        try:
            self.itemconfigure(self._id[indice], fill=COLORI[stato])
        except (tk.TclError, IndexError):
            pass

    def segna(self, inizio, fine, stato):
        """Colora l'intervallo di byte [inizio, fine]."""
        if fine < inizio:
            return
        for indice in range(self._blocco(inizio), self._blocco(fine) + 1):
            self._colora(indice, stato)

    def avanza(self, inizio, fine, percento, stato, attivo=True):
        """Riempie l'intervallo fino alla percentuale indicata."""
        if fine < inizio:
            return
        primo, ultimo = self._blocco(inizio), self._blocco(fine)
        quanti = ultimo - primo + 1
        fatti = int(quanti * max(0, min(100, percento)) / 100.0)
        for scarto in range(quanti):
            indice = primo + scarto
            if scarto < fatti:
                self._colora(indice, stato)
            elif scarto == fatti and attivo and percento < 100:
                self._colora(indice, ATTIVO)

    def segna_intervalli(self, intervalli, stato):
        for inizio, fine in intervalli:
            self.segna(inizio, fine, stato)


class Legenda(tk.Frame):
    """What the colours mean, in a single row."""

    def __init__(self, padre, tema, L, fondo=T.PANEL):
        tk.Frame.__init__(self, padre, background=fondo)
        self.tema = tema
        self.L = L
        self.voci = []
        for stato, chiave in LEGENDA:
            cella = tk.Frame(self, background=fondo)
            cella.pack(side="left", padx=(0, 10))
            quadretto = tk.Canvas(cella, width=LATO, height=LATO,
                                  highlightthickness=0, background=fondo)
            quadretto.create_rectangle(0, 0, LATO, LATO, fill=COLORI[stato],
                                       outline="")
            quadretto.pack(side="left", padx=(0, 4))
            etichetta = tk.Label(cella, background=fondo, foreground=T.MUT,
                                 font=tema.f_minuto)
            etichetta.pack(side="left")
            self.voci.append((etichetta, chiave))
        self.traduci()

    def traduci(self):
        for etichetta, chiave in self.voci:
            etichetta.configure(text=self.L(chiave))
