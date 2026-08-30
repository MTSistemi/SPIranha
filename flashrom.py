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

NO_WINDOW = 0
if os.name == "nt":
    NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def port_for_flashrom(device):
    """COM6 resta COM6; COM10 diventa \\\\.\\COM10, altrimenti Windows non lo apre."""
    m = _RE_COM.match(device or "")
    if m and int(m.group(1)) >= 10:
        return r"\\.\COM" + m.group(1)
    return device


class Result(object):
    def __init__(self, code, lines, aborted=False, error=None):
        self.code = code
        self.lines = lines
        self.aborted = aborted
        self.error = error

    @property
    def ok(self):
        return self.error is None and not self.aborted and self.code == 0

    @property
    def text(self):
        return "\n".join(self.lines)


class Protection(object):
    """Lo stato del blocco in scrittura di un chip SPI.

    ⚠️ Perche' conta: e' il modo piu' comune in cui una scrittura di BIOS
    fallisce o, peggio, sembra riuscita e non ha scritto niente. Il chip
    accetta i comandi e non cambia. Meglio saperlo prima.
    """

    def __init__(self, start=None, length=None, description=None,
                 mode=None, supported=True, reason=None):
        self.start = start
        self.length = length
        self.description = description
        self.mode = mode
        self.supported = supported      # il chip sa rispondere?
        self.reason = reason

    @property
    def active(self):
        """C'e' davvero un pezzo di chip protetto?"""
        return bool(self.length) and (self.mode or "").lower() != "disabled"

    @property
    def end(self):
        if self.start is None or not self.length:
            return None
        return self.start + self.length - 1

    def overlaps(self, start, end):
        """L'intervallo protetto si sovrappone a quello che vogliamo scrivere?"""
        if not self.active:
            return False
        return not (end < self.start or start > self.end)


class Chip(object):
    def __init__(self, name=None, vendor=None, kb=None, candidates=None):
        self.name = name
        self.vendor = vendor
        self.kb = kb
        self.candidates = candidates or []

    @property
    def size(self):
        return self.kb * 1024 if self.kb else None

    @property
    def description(self):
        chunks = [p for p in (self.vendor, self.name) if p]
        text = " ".join(chunks) if chunks else "?"
        if self.kb:
            text += " (%d KiB)" % self.kb
        return text


class Flashrom(object):
    def __init__(self, path, programmatore=None):
        self.path = path
        # Normalmente serprog. Si puo' forzare (per esempio "dummy:...") per
        # provare tutta la catena senza attaccare niente a niente.
        self.programmatore = programmatore
        self._processo = None
        self._block_rect = threading.Lock()

    # -- costruzione della riga di comando ------------------------------
    def _programmatore(self, port, baud=115200, spispeed=None):
        if self.programmatore:
            return self.programmatore
        value_for = "serprog:dev=%s:%d" % (port_for_flashrom(port), baud)
        if spispeed:
            value_for += ",spispeed=%s" % spispeed
        return value_for

    def arguments(self, port, baud=115200, spispeed=None, chip=None,
                  verbose=False, progress=True):
        args = [self.path, "-p", self._programmatore(port, baud, spispeed)]
        if chip:
            args += ["-c", chip]
        if verbose:
            args += ["-V"]
        if progress:
            args += ["--progress"]
        return args

    @staticmethod
    def _eventi(buffer, on_event):
        """Estrae dal tampone gli eventi completi e restituisce (resto, quanti)."""
        found_items = []
        for m in _RE_FASE.finditer(buffer):
            found_items.append((m.start(), m.end(),
                            ("fase", m.group(1), int(m.group(2)))))
        for m in _RE_BLOCCO.finditer(buffer):
            kind = "cancella" if m.group(1) == "E" else "scrive"
            found_items.append((m.start(), m.end(),
                            (kind, int(m.group(2), 16), int(m.group(3), 16))))
        if not found_items:
            return buffer, 0
        found_items.sort()
        for _inizio, _fine, event in found_items:
            on_event(*event)
        return buffer[found_items[-1][1]:], len(found_items)

    @staticmethod
    def readable_line(args):
        chunks = []
        for a in args:
            chunks.append('"%s"' % a if " " in a else a)
        return " ".join(chunks)

    # -- esecuzione ------------------------------------------------------
    def run(self, args, on_line=None, on_event=None, tutto_il_registro=True):
        """Lancia flashrom e restituisce l'Esito. Bloccante: chiamare da un thread.

        `su_evento(tipo, *dati)` riceve l'avanzamento man mano che esce:
          ("fase", nome, percento)   da --progress
          ("cancella", inizio, fine) da -V, un blocco cancellato
          ("scrive", inizio, fine)   da -V, l'intervallo scritto
        `tutto_il_registro=False` tiene fuori dal registro il rumore di -V.
        """
        lines = []

        def emetti(text):
            if not text or _RUMORE.match(text):
                return
            # percentuali e marcatori sono eventi, non testo da leggere
            pulito = _RE_BLOCCO.sub("", _RE_FASE.sub("", text)).strip(" .")
            if not pulito:
                return
            if not tutto_il_registro:
                if _INTERNE.search(pulito) or not _INTERESSANTI.search(pulito):
                    return
            lines.append(pulito)
            if on_line:
                on_line(pulito)

        try:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
                bufsize=0,
            )
        except OSError as e:
            return Result(None, lines, error="%s" % e)

        with self._block_rect:
            self._processo = process

        # flashrom scrive l'avanzamento con \r: si legge a byte e si spezza su
        # entrambi i terminatori, altrimenti la barra non compare mai.
        # ⚠️ I marcatori E(...)/W(...) e le percentuali NON vanno a capo: escono
        # in mezzo alle altre righe. Per questo si tiene un tampone a parte su
        # cui si cercano gli eventi, indipendente dalle righe del registro.
        leftover = bytearray()
        buffer = ""
        try:
            while True:
                chunk = process.stdout.read(1)
                if not chunk:
                    break
                font = chunk.decode("utf-8", "replace")
                if on_event:
                    buffer += font
                    if len(buffer) > 512:
                        buffer, consumato = self._eventi(buffer, on_event)
                        if not consumato:
                            buffer = buffer[-64:]
                if chunk in (b"\n", b"\r"):
                    if leftover:
                        text = leftover.decode("utf-8", "replace").rstrip()
                        if on_event:
                            buffer, _ = self._eventi(buffer, on_event)
                        emetti(text)
                        leftover = bytearray()
                else:
                    leftover += chunk
            if on_event:
                self._eventi(buffer, on_event)
            if leftover:
                emetti(leftover.decode("utf-8", "replace").rstrip())
        finally:
            process.stdout.close()
            code = process.wait()
            with self._block_rect:
                aborted = getattr(self, "_interrotto", False)
                self._interrotto = False
                self._processo = None

        return Result(code, lines, aborted=aborted)

    def abort(self):
        with self._block_rect:
            process = self._processo
            if process is None:
                return False
            self._interrotto = True
        try:
            process.terminate()
        except OSError:
            return False
        return True

    @property
    def running(self):
        with self._block_rect:
            return self._processo is not None

    # -- operazioni -------------------------------------------------------
    def version(self):
        """La prima riga di `flashrom --version`, o None se non e' flashrom."""
        try:
            output = subprocess.check_output(
                [self.path, "--version"],
                stderr=subprocess.STDOUT,
                creationflags=NO_WINDOW,
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        before = output.decode("utf-8", "replace").splitlines()
        if not before:
            return None
        if "flashrom" not in before[0].lower():
            return None
        return before[0].strip()

    def chip_list(self):
        """Tutti i chip che questo flashrom conosce, letti da lui.

        ⚠️ Non c\u0027e\u0027 una tabella scritta a mano da nessuna parte: chiedendolo
        all\u0027eseguibile, l\u0027elenco e\u0027 sempre quello della versione che si sta
        usando davvero. Una lista nostra invecchierebbe in silenzio.
        """
        try:
            output = subprocess.check_output(
                [self.path, "-L"],
                stderr=subprocess.STDOUT,
                creationflags=NO_WINDOW,
            )
        except (OSError, subprocess.CalledProcessError):
            return []
        return parse_chip_list(output.decode("utf-8", "replace").splitlines())

    def identify(self, port, baud=115200, spispeed=None, chip=None,
                   verbose=False, on_line=None, on_event=None):
        args = self.arguments(port, baud, spispeed, chip, verbose,
                              progress=False) + ["--flash-name"]
        result = self.run(args, on_line, on_event)
        return result, parse_chip(result.lines)

    def protection(self, port, baud=115200, spispeed=None, chip=None,
                   verbose=False, on_line=None):
        """Chiede al chip com'e' messo il blocco in scrittura."""
        args = self.arguments(port, baud, spispeed, chip, verbose,
                              progress=False) + ["--wp-status"]
        result = self.run(args, on_line)
        return result, parse_protection(result.lines, result.ok)

    def unlock(self, port, baud=115200, spispeed=None, chip=None,
                verbose=False, on_line=None):
        """Toglie il blocco: --wp-disable e intervallo azzerato.

        ⚠️ Cambia lo STATO DEL CHIP, non un'impostazione del programma. Va
        chiesto, non fatto di nascosto.
        """
        args = self.arguments(port, baud, spispeed, chip, verbose,
                              progress=False) + ["--wp-range=0,0", "--wp-disable"]
        return self.run(args, on_line)

    def read(self, destination, port, baud=115200, spispeed=None, chip=None,
              verbose=False, on_line=None, on_event=None):
        args = self.arguments(port, baud, spispeed, chip, verbose) + \
            ["-r", destination]
        return self.run(args, on_line, on_event, tutto_il_registro=verbose)

    def read_region(self, layout, region, destination, port, baud=115200,
                      spispeed=None, chip=None, verbose=False, on_line=None,
                      on_event=None):
        """Legge SOLO una regione del layout: serve alle prove rapide."""
        args = self.arguments(port, baud, spispeed, chip, verbose) + \
            ["-l", layout, "-i", "%s:%s" % (region, destination), "-r"]
        return self.run(args, on_line, on_event, tutto_il_registro=verbose)

    def write(self, image, port, baud=115200, spispeed=None, chip=None,
               layout=None, region=None, verbose=False, on_line=None,
               on_event=None):
        # ⚠️ -V si forza sempre in scrittura: e' l'unico modo per avere i
        # marcatori E(...)/W(...), cioe' i blocchi veri della mappa. Il registro
        # pero' resta pulito se l'utente non ha chiesto i dettagli.
        args = self.arguments(port, baud, spispeed, chip,
                              verbose=verbose or on_event is not None)
        if layout and region:
            args += ["-l", layout, "-i", region]
        args += ["-w", image]
        return self.run(args, on_line, on_event, tutto_il_registro=verbose)


def parse_chip(lines):
    """Estrae dal chiacchiericcio di flashrom quale chip ha trovato."""
    chip = Chip()
    ambiguo = False
    for line in lines:
        m = _RE_TROVATO.search(line)
        if m:
            chip.vendor, chip.name, chip.kb = m.group(1), m.group(2), int(m.group(3))
            continue
        m = _RE_NOME.search(line)
        if m:
            chip.vendor, chip.name = m.group(1), m.group(2)
            continue
        if _RE_AMBIGUO.search(line):
            ambiguo = True
            continue
        if ambiguo:
            m = _RE_CANDIDATO.match(line)
            if m and "flashrom" not in line.lower():
                chip.candidates.append(m.group(1))
    if ambiguo:
        chip.name = None
    return chip


def parse_protection(lines, esito_ok=True):
    """Estrae lo stato del blocco da cio' che flashrom ha detto."""
    text = "\n".join(lines)
    span = _RE_WP_INTERVALLO.search(text)
    mode = _RE_WP_MODO.search(text)
    if not span and not mode:
        # chip che non sa rispondere, o programmatore che non ce la fa
        reason = None
        for line in lines:
            if "wp" in line.lower() and ("not support" in line.lower()
                                         or "failed" in line.lower()
                                         or "error" in line.lower()):
                reason = line.strip()
                break
        return Protection(supported=False, reason=reason)
    return Protection(
        start=int(span.group(1), 16) if span else None,
        length=int(span.group(2), 16) if span else None,
        description=span.group(3).strip() if span else None,
        mode=mode.group(1).strip() if mode else None,
        supported=esito_ok)


class KnownChip(object):
    """Una riga dell\u0027elenco di flashrom."""

    def __init__(self, vendor, name, kb=None, kind=None, tested=None):
        self.vendor = vendor
        self.name = name
        self.kb = kb
        self.kind = kind
        self.tested = tested or ""      # P/R/E/W: cosa e\u0027 stato provato davvero

    @property
    def size(self):
        return self.kb * 1024 if self.kb else None

    @property
    def spi(self):
        return (self.kind or "").upper() == "SPI"

    @property
    def full_name(self):
        return "%s %s" % (self.vendor, self.name)

    @property
    def well_tested(self):
        """flashrom dice di averci letto E scritto sopra?"""
        return "R" in self.tested and "W" in self.tested

    def __repr__(self):
        return "<%s %s %s>" % (self.vendor, self.name, self.kind)


# Le righe dell'elenco sono a colonne fisse, ma i nomi lunghi vanno a capo
# e la continuazione ha la colonna del produttore VUOTA:
#     Winbond      W25Q32BW/     PREW    4096  SPI
#                  W25Q32CW/
#                  W25Q32DW
# ⚠️ Ricucirle non e' un vezzo: il nome che flashrom accetta e' quello
# INTERO, "W25Q32BW/W25Q32CW/W25Q32DW". Prendendo solo la prima riga si
# sceglierebbe un modello che poi flashrom rifiuta.
_INIZIO_ELENCO = "Supported flash chips"
_LARGHEZZA_PRODUTTORE = 29


def parse_chip_list(lines):
    """Le righe di `flashrom -L` diventano ChipNoto."""
    out = []
    inside = False
    for line in lines:
        text = line.rstrip()
        if not inside:
            if text.startswith(_INIZIO_ELENCO):
                inside = True
            continue
        if not text.strip():
            continue
        if text.startswith(("Vendor", "(P =")) or text.lstrip().startswith("OK "):
            continue
        vendor = text[:_LARGHEZZA_PRODUTTORE].strip()
        resto = text[_LARGHEZZA_PRODUTTORE:]
        if not vendor:
            # continuazione del nome di sopra
            if out and resto.strip():
                out[-1].name += resto.strip()
            continue
        fields = re.split(r"\s{2,}", resto.strip())
        fields = [c for c in fields if c]
        if len(fields) < 2:
            # una riga senza dimensione ne' tipo non e' una riga di chip
            continue
        name = fields[0]
        kind = fields[-1]
        kb = None
        try:
            kb = int(fields[-2])
        except (ValueError, IndexError):
            kb = None
        tested = "".join(fields[1:-2])
        out.append(KnownChip(vendor, name, kb, kind, tested))
    return out


def find_executable(app_folder, extra=None):
    """Cerca flashrom.exe: dentro l'eseguibile, accanto, in una sottocartella,
    nel PATH.

    `extra` sono cartelle da guardare per prime: nell'eseguibile unico ci si
    passa la cartella temporanea dove PyInstaller scompatta cio' che ha dentro,
    cosi' il programma portatile si porta dietro il suo flashrom.
    """
    names_of = ["flashrom.exe", "flashrom"] if os.name == "nt" else ["flashrom"]
    radici = list(extra or []) + [app_folder]
    candidates = []
    for root in radici:
        if not root:
            continue
        for name in names_of:
            candidates.append(os.path.join(root, name))
            candidates.append(os.path.join(root, "flashrom", name))
    for path in candidates:
        if os.path.isfile(path):
            return path
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        for name in names_of:
            path = os.path.join(folder.strip('"'), name)
            if os.path.isfile(path):
                return path
    return None


def read_layout(path):
    """[(nome, inizio, fine)] dal file di layout di flashrom.

    ⚠️ Il parser di flashrom non accetta commenti: qui li tolleriamo solo per
    non far sparire righe buone, ma il file che gli passiamo resta il suo.
    """
    regions = []
    with open(path, "rb") as f:
        for line in f.read().decode("utf-8", "replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                span, name = line.split(None, 1)
                start, end = span.split(":")
                regions.append((name.strip(), int(start, 16), int(end, 16)))
            except ValueError:
                continue
    return regions
