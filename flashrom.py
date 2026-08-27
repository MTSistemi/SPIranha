# -*- coding: utf-8 -*-
"""Il pezzo che chiama flashrom.exe e legge quello che dice.

Qui NON si parla col chip: il codice che cancella e scrive settori resta quello
di flashrom, che e' collaudato. Questo modulo costruisce la riga di comando
giusta, lancia il processo e riporta indietro ogni riga di uscita mentre esce.

Il modulo che chiama passa una funzione `su_riga(testo)`: viene chiamata da un
thread di lavoro, quindi l'interfaccia deve accodare, non disegnare.
"""
from __future__ import unicode_literals

import os
import re
import subprocess
import threading

# Su Windows i nomi di porta dal COM10 in su vogliono il prefisso.
_RE_COM = re.compile(r"^COM(\d+)$", re.IGNORECASE)
# vendor="Macronix" name="MX25L12835F/MX25L12873F"
_RE_NOME = re.compile(r'vendor="([^"]*)"\s+name="([^"]*)"')
# Found Macronix flash chip "MX25L12835F/MX25L12873F" (16384 kB, SPI) on serprog.
_RE_TROVATO = re.compile(r'Found\s+(.+?)\s+flash chip\s+"([^"]+)"\s+\((\d+)\s*kB')
_RE_AMBIGUO = re.compile(r"Multiple flash chip definitions match", re.IGNORECASE)

# La protezione in scrittura, come la racconta flashrom:
#   Protection range: start=0x00000000 length=0x00000000 (none)
#   Protection mode: disabled
_RE_WP_INTERVALLO = re.compile(
    r"Protection range:\s*start=0x([0-9a-f]+)\s*length=0x([0-9a-f]+)\s*\(([^)]*)\)",
    re.IGNORECASE)
_RE_WP_MODO = re.compile(r"Protection mode:\s*(\S+)", re.IGNORECASE)
_RE_CANDIDATO = re.compile(r'^\s*"?([A-Za-z0-9][\w./\-]{3,})"?\s*$')

# Quello che flashrom dice mentre lavora, e che serve per la mappa a blocchi.
# --progress stampa  [READ:  42%]  a fasi (READ, ERASE, WRITE).
_RE_FASE = re.compile(r"\[(READ|ERASE|WRITE|VERIFY)\s*:\s*(\d+)%\]")
# -V stampa un marcatore per ogni blocco cancellato e per l'intervallo scritto:
#   E(ae0000:aeffff)   W(ae0000:c228ff)
_RE_BLOCCO = re.compile(r"([EW])\(([0-9a-f]+):([0-9a-f]+)\)")

# -V si accende sempre in scrittura, per avere i marcatori dei blocchi; ma il
# suo chiacchiericcio interno non deve finire nel registro di chi guarda.
# Prima si buttano le righe di servizio, poi si tiene solo cio' che dice
# davvero qualcosa.
_INTERNE = re.compile(
    r"read_flash:|erase_write:|write_flash:|verify_range:|probe_jedec|"
    r"Probing for|Emulating |Filling fake|Fixing total|Found persistent image|"
    r"^(Reading|Writing) [A-Za-z]:")
_INTERESSANTI = re.compile(
    r"Found .*flash chip|Using region|Reading flash|Reading old flash|"
    r"Updating flash chip|Erasing and writing|Verifying flash|Erase/write done|"
    r"VERIFIED|SUCCESS|Restoring|error|fail|warning",
    re.IGNORECASE)
_RUMORE = re.compile(r"^\s*(\.+|\[?[A-Z]+:\s*\d+%\]?\.*)\s*$")

SENZA_FINESTRA = 0
if os.name == "nt":
    SENZA_FINESTRA = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def porta_per_flashrom(dispositivo):
    """COM6 resta COM6; COM10 diventa \\\\.\\COM10, altrimenti Windows non lo apre."""
    m = _RE_COM.match(dispositivo or "")
    if m and int(m.group(1)) >= 10:
        return r"\\.\COM" + m.group(1)
    return dispositivo


class Esito(object):
    def __init__(self, codice, righe, interrotto=False, errore=None):
        self.codice = codice
        self.righe = righe
        self.interrotto = interrotto
        self.errore = errore

    @property
    def ok(self):
        return self.errore is None and not self.interrotto and self.codice == 0

    @property
    def testo(self):
        return "\n".join(self.righe)


class Protezione(object):
    """Lo stato del blocco in scrittura di un chip SPI.

    ⚠️ Perche' conta: e' il modo piu' comune in cui una scrittura di BIOS
    fallisce o, peggio, sembra riuscita e non ha scritto niente. Il chip
    accetta i comandi e non cambia. Meglio saperlo prima.
    """

    def __init__(self, inizio=None, lunghezza=None, descrizione=None,
                 modo=None, sostenuta=True, motivo=None):
        self.inizio = inizio
        self.lunghezza = lunghezza
        self.descrizione = descrizione
        self.modo = modo
        self.sostenuta = sostenuta      # il chip sa rispondere?
        self.motivo = motivo

    @property
    def attiva(self):
        """C'e' davvero un pezzo di chip protetto?"""
        return bool(self.lunghezza) and (self.modo or "").lower() != "disabled"

    @property
    def fine(self):
        if self.inizio is None or not self.lunghezza:
            return None
        return self.inizio + self.lunghezza - 1

    def tocca(self, inizio, fine):
        """L'intervallo protetto si sovrappone a quello che vogliamo scrivere?"""
        if not self.attiva:
            return False
        return not (fine < self.inizio or inizio > self.fine)


class Chip(object):
    def __init__(self, nome=None, produttore=None, kb=None, candidati=None):
        self.nome = nome
        self.produttore = produttore
        self.kb = kb
        self.candidati = candidati or []

    @property
    def byte(self):
        return self.kb * 1024 if self.kb else None

    @property
    def descrizione(self):
        pezzi = [p for p in (self.produttore, self.nome) if p]
        testo = " ".join(pezzi) if pezzi else "?"
        if self.kb:
            testo += " (%d KiB)" % self.kb
        return testo


class Flashrom(object):
    def __init__(self, percorso, programmatore=None):
        self.percorso = percorso
        # Normalmente serprog. Si puo' forzare (per esempio "dummy:...") per
        # provare tutta la catena senza attaccare niente a niente.
        self.programmatore = programmatore
        self._processo = None
        self._blocco = threading.Lock()

    # -- costruzione della riga di comando ------------------------------
    def _programmatore(self, porta, baud=115200, spispeed=None):
        if self.programmatore:
            return self.programmatore
        valore = "serprog:dev=%s:%d" % (porta_per_flashrom(porta), baud)
        if spispeed:
            valore += ",spispeed=%s" % spispeed
        return valore

    def argomenti(self, porta, baud=115200, spispeed=None, chip=None,
                  dettagli=False, avanzamento=True):
        args = [self.percorso, "-p", self._programmatore(porta, baud, spispeed)]
        if chip:
            args += ["-c", chip]
        if dettagli:
            args += ["-V"]
        if avanzamento:
            args += ["--progress"]
        return args

    @staticmethod
    def _eventi(tampone, su_evento):
        """Estrae dal tampone gli eventi completi e restituisce (resto, quanti)."""
        trovati = []
        for m in _RE_FASE.finditer(tampone):
            trovati.append((m.start(), m.end(),
                            ("fase", m.group(1), int(m.group(2)))))
        for m in _RE_BLOCCO.finditer(tampone):
            tipo = "cancella" if m.group(1) == "E" else "scrive"
            trovati.append((m.start(), m.end(),
                            (tipo, int(m.group(2), 16), int(m.group(3), 16))))
        if not trovati:
            return tampone, 0
        trovati.sort()
        for _inizio, _fine, evento in trovati:
            su_evento(*evento)
        return tampone[trovati[-1][1]:], len(trovati)

    @staticmethod
    def riga_leggibile(args):
        pezzi = []
        for a in args:
            pezzi.append('"%s"' % a if " " in a else a)
        return " ".join(pezzi)

    # -- esecuzione ------------------------------------------------------
    def esegui(self, args, su_riga=None, su_evento=None, tutto_il_registro=True):
        """Lancia flashrom e restituisce l'Esito. Bloccante: chiamare da un thread.

        `su_evento(tipo, *dati)` riceve l'avanzamento man mano che esce:
          ("fase", nome, percento)   da --progress
          ("cancella", inizio, fine) da -V, un blocco cancellato
          ("scrive", inizio, fine)   da -V, l'intervallo scritto
        `tutto_il_registro=False` tiene fuori dal registro il rumore di -V.
        """
        righe = []

        def emetti(testo):
            if not testo or _RUMORE.match(testo):
                return
            # percentuali e marcatori sono eventi, non testo da leggere
            pulito = _RE_BLOCCO.sub("", _RE_FASE.sub("", testo)).strip(" .")
            if not pulito:
                return
            if not tutto_il_registro:
                if _INTERNE.search(pulito) or not _INTERESSANTI.search(pulito):
                    return
            righe.append(pulito)
            if su_riga:
                su_riga(pulito)

        try:
            processo = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=SENZA_FINESTRA,
                bufsize=0,
            )
        except OSError as e:
            return Esito(None, righe, errore="%s" % e)

        with self._blocco:
            self._processo = processo

        # flashrom scrive l'avanzamento con \r: si legge a byte e si spezza su
        # entrambi i terminatori, altrimenti la barra non compare mai.
        # ⚠️ I marcatori E(...)/W(...) e le percentuali NON vanno a capo: escono
        # in mezzo alle altre righe. Per questo si tiene un tampone a parte su
        # cui si cercano gli eventi, indipendente dalle righe del registro.
        avanzo = bytearray()
        tampone = ""
        try:
            while True:
                pezzo = processo.stdout.read(1)
                if not pezzo:
                    break
                carattere = pezzo.decode("utf-8", "replace")
                if su_evento:
                    tampone += carattere
                    if len(tampone) > 512:
                        tampone, consumato = self._eventi(tampone, su_evento)
                        if not consumato:
                            tampone = tampone[-64:]
                if pezzo in (b"\n", b"\r"):
                    if avanzo:
                        testo = avanzo.decode("utf-8", "replace").rstrip()
                        if su_evento:
                            tampone, _ = self._eventi(tampone, su_evento)
                        emetti(testo)
                        avanzo = bytearray()
                else:
                    avanzo += pezzo
            if su_evento:
                self._eventi(tampone, su_evento)
            if avanzo:
                emetti(avanzo.decode("utf-8", "replace").rstrip())
        finally:
            processo.stdout.close()
            codice = processo.wait()
            with self._blocco:
                interrotto = getattr(self, "_interrotto", False)
                self._interrotto = False
                self._processo = None

        return Esito(codice, righe, interrotto=interrotto)

    def interrompi(self):
        with self._blocco:
            processo = self._processo
            if processo is None:
                return False
            self._interrotto = True
        try:
            processo.terminate()
        except OSError:
            return False
        return True

    @property
    def in_esecuzione(self):
        with self._blocco:
            return self._processo is not None

    # -- operazioni -------------------------------------------------------
    def versione(self):
        """La prima riga di `flashrom --version`, o None se non e' flashrom."""
        try:
            uscita = subprocess.check_output(
                [self.percorso, "--version"],
                stderr=subprocess.STDOUT,
                creationflags=SENZA_FINESTRA,
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        prima = uscita.decode("utf-8", "replace").splitlines()
        if not prima:
            return None
        if "flashrom" not in prima[0].lower():
            return None
        return prima[0].strip()

    def identifica(self, porta, baud=115200, spispeed=None, chip=None,
                   dettagli=False, su_riga=None, su_evento=None):
        args = self.argomenti(porta, baud, spispeed, chip, dettagli,
                              avanzamento=False) + ["--flash-name"]
        esito = self.esegui(args, su_riga, su_evento)
        return esito, leggi_chip(esito.righe)

    def protezione(self, porta, baud=115200, spispeed=None, chip=None,
                   dettagli=False, su_riga=None):
        """Chiede al chip com'e' messo il blocco in scrittura."""
        args = self.argomenti(porta, baud, spispeed, chip, dettagli,
                              avanzamento=False) + ["--wp-status"]
        esito = self.esegui(args, su_riga)
        return esito, leggi_protezione(esito.righe, esito.ok)

    def sblocca(self, porta, baud=115200, spispeed=None, chip=None,
                dettagli=False, su_riga=None):
        """Toglie il blocco: --wp-disable e intervallo azzerato.

        ⚠️ Cambia lo STATO DEL CHIP, non un'impostazione del programma. Va
        chiesto, non fatto di nascosto.
        """
        args = self.argomenti(porta, baud, spispeed, chip, dettagli,
                              avanzamento=False) + ["--wp-range=0,0", "--wp-disable"]
        return self.esegui(args, su_riga)

    def leggi(self, destinazione, porta, baud=115200, spispeed=None, chip=None,
              dettagli=False, su_riga=None, su_evento=None):
        args = self.argomenti(porta, baud, spispeed, chip, dettagli) + \
            ["-r", destinazione]
        return self.esegui(args, su_riga, su_evento, tutto_il_registro=dettagli)

    def leggi_regione(self, layout, regione, destinazione, porta, baud=115200,
                      spispeed=None, chip=None, dettagli=False, su_riga=None,
                      su_evento=None):
        """Legge SOLO una regione del layout: serve alle prove rapide."""
        args = self.argomenti(porta, baud, spispeed, chip, dettagli) + \
            ["-l", layout, "-i", "%s:%s" % (regione, destinazione), "-r"]
        return self.esegui(args, su_riga, su_evento, tutto_il_registro=dettagli)

    def scrivi(self, immagine, porta, baud=115200, spispeed=None, chip=None,
               layout=None, regione=None, dettagli=False, su_riga=None,
               su_evento=None):
        # ⚠️ -V si forza sempre in scrittura: e' l'unico modo per avere i
        # marcatori E(...)/W(...), cioe' i blocchi veri della mappa. Il registro
        # pero' resta pulito se l'utente non ha chiesto i dettagli.
        args = self.argomenti(porta, baud, spispeed, chip,
                              dettagli=dettagli or su_evento is not None)
        if layout and regione:
            args += ["-l", layout, "-i", regione]
        args += ["-w", immagine]
        return self.esegui(args, su_riga, su_evento, tutto_il_registro=dettagli)


def leggi_chip(righe):
    """Estrae dal chiacchiericcio di flashrom quale chip ha trovato."""
    chip = Chip()
    ambiguo = False
    for riga in righe:
        m = _RE_TROVATO.search(riga)
        if m:
            chip.produttore, chip.nome, chip.kb = m.group(1), m.group(2), int(m.group(3))
            continue
        m = _RE_NOME.search(riga)
        if m:
            chip.produttore, chip.nome = m.group(1), m.group(2)
            continue
        if _RE_AMBIGUO.search(riga):
            ambiguo = True
            continue
        if ambiguo:
            m = _RE_CANDIDATO.match(riga)
            if m and "flashrom" not in riga.lower():
                chip.candidati.append(m.group(1))
    if ambiguo:
        chip.nome = None
    return chip


def leggi_protezione(righe, esito_ok=True):
    """Estrae lo stato del blocco da cio' che flashrom ha detto."""
    testo = "\n".join(righe)
    intervallo = _RE_WP_INTERVALLO.search(testo)
    modo = _RE_WP_MODO.search(testo)
    if not intervallo and not modo:
        # chip che non sa rispondere, o programmatore che non ce la fa
        motivo = None
        for riga in righe:
            if "wp" in riga.lower() and ("not support" in riga.lower()
                                         or "failed" in riga.lower()
                                         or "error" in riga.lower()):
                motivo = riga.strip()
                break
        return Protezione(sostenuta=False, motivo=motivo)
    return Protezione(
        inizio=int(intervallo.group(1), 16) if intervallo else None,
        lunghezza=int(intervallo.group(2), 16) if intervallo else None,
        descrizione=intervallo.group(3).strip() if intervallo else None,
        modo=modo.group(1).strip() if modo else None,
        sostenuta=esito_ok)


def trova_eseguibile(cartella_app, extra=None):
    """Cerca flashrom.exe: dentro l'eseguibile, accanto, in una sottocartella,
    nel PATH.

    `extra` sono cartelle da guardare per prime: nell'eseguibile unico ci si
    passa la cartella temporanea dove PyInstaller scompatta cio' che ha dentro,
    cosi' il programma portatile si porta dietro il suo flashrom.
    """
    nomi = ["flashrom.exe", "flashrom"] if os.name == "nt" else ["flashrom"]
    radici = list(extra or []) + [cartella_app]
    candidati = []
    for radice in radici:
        if not radice:
            continue
        for nome in nomi:
            candidati.append(os.path.join(radice, nome))
            candidati.append(os.path.join(radice, "flashrom", nome))
    for percorso in candidati:
        if os.path.isfile(percorso):
            return percorso
    for cartella in os.environ.get("PATH", "").split(os.pathsep):
        for nome in nomi:
            percorso = os.path.join(cartella.strip('"'), nome)
            if os.path.isfile(percorso):
                return percorso
    return None


def leggi_layout(percorso):
    """[(nome, inizio, fine)] dal file di layout di flashrom.

    ⚠️ Il parser di flashrom non accetta commenti: qui li tolleriamo solo per
    non far sparire righe buone, ma il file che gli passiamo resta il suo.
    """
    regioni = []
    with open(percorso, "rb") as f:
        for riga in f.read().decode("utf-8", "replace").splitlines():
            riga = riga.strip()
            if not riga or riga.startswith("#"):
                continue
            try:
                intervallo, nome = riga.split(None, 1)
                inizio, fine = intervallo.split(":")
                regioni.append((nome.strip(), int(inizio, 16), int(fine, 16)))
            except ValueError:
                continue
    return regioni
