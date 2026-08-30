# -*- coding: utf-8 -*-
"""The piece that calls flashrom.exe and reads what it says.

This does NOT talk to the chip: the code that erases and writes sectors stays
flashrom's, which is proven. This module builds the right command line, starts
the process and hands back every output line as it comes.

The caller passes an `on_line(text)` function: it is called from a worker
thread, so the interface must queue, not draw.
"""
from __future__ import unicode_literals

import os
import re
import subprocess
import threading

# On Windows, port names from COM10 up need the prefix.
_RE_COM = re.compile(r"^COM(\d+)$", re.IGNORECASE)
# vendor="Macronix" name="MX25L12835F/MX25L12873F"
_RE_NAME = re.compile(r'vendor="([^"]*)"\s+name="([^"]*)"')
# Found Macronix flash chip "MX25L12835F/MX25L12873F" (16384 kB, SPI) on serprog.
_RE_FOUND = re.compile(r'Found\s+(.+?)\s+flash chip\s+"([^"]+)"\s+\((\d+)\s*kB')
_RE_AMBIGUOUS = re.compile(r"Multiple flash chip definitions match", re.IGNORECASE)

# The write protection, the way flashrom tells it:
#   Protection range: start=0x00000000 length=0x00000000 (none)
#   Protection mode: disabled
_RE_WP_SPAN = re.compile(
    r"Protection range:\s*start=0x([0-9a-f]+)\s*length=0x([0-9a-f]+)\s*\(([^)]*)\)",
    re.IGNORECASE)
_RE_WP_MODE = re.compile(r"Protection mode:\s*(\S+)", re.IGNORECASE)
_RE_CANDIDATE = re.compile(r'^\s*"?([A-Za-z0-9][\w./\-]{3,})"?\s*$')

# What flashrom says while it works, which is what the block map needs.
# --progress stampa  [READ:  42%]  a fasi (READ, ERASE, WRITE).
_RE_PHASE = re.compile(r"\[(READ|ERASE|WRITE|VERIFY)\s*:\s*(\d+)%\]")
# -V prints a marker for every erased block and for the written range:
#   E(ae0000:aeffff)   W(ae0000:c228ff)
_RE_BLOCK = re.compile(r"([EW])\(([0-9a-f]+):([0-9a-f]+)\)")

# -V is always on when writing, to get the block markers; but its internal
# chatter must not end up in the log the user is watching. First the
# housekeeping lines are dropped, then only what says
# really is protected.
_INTERNAL = re.compile(
    r"read_flash:|erase_write:|write_flash:|verify_range:|probe_jedec|"
    r"Probing for|Emulating |Filling fake|Fixing total|Found persistent image|"
    r"^(Reading|Writing) [A-Za-z]:")
_INTERESTING = re.compile(
    r"Found .*flash chip|Using region|Reading flash|Reading old flash|"
    r"Updating flash chip|Erasing and writing|Verifying flash|Erase/write done|"
    r"VERIFIED|SUCCESS|Restoring|error|fail|warning",
    re.IGNORECASE)
_NOISE = re.compile(r"^\s*(\.+|\[?[A-Z]+:\s*\d+%\]?\.*)\s*$")

NO_WINDOW = 0
if os.name == "nt":
    NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def port_for_flashrom(device):
    """COM6 stays COM6; COM10 becomes \\\\.\\COM10, or Windows will not open it."""
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
    """The write-lock state of an SPI chip.

    ⚠️ Why it matters: this is the most common way a BIOS write fails or,
    worse, appears to succeed while writing nothing. The chip takes the
    commands and does not change. Better to know beforehand.
    """

    def __init__(self, start=None, length=None, description=None,
                 mode=None, supported=True, reason=None):
        self.start = start
        self.length = length
        self.description = description
        self.mode = mode
        self.supported = supported      # can the chip answer at all?
        self.reason = reason

    @property
    def active(self):
        """Is a piece of the chip really locked?"""
        return bool(self.length) and (self.mode or "").lower() != "disabled"

    @property
    def end(self):
        if self.start is None or not self.length:
            return None
        return self.start + self.length - 1

    def overlaps(self, start, end):
        """Does the protected range overlap the one we want to write?"""
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
    def __init__(self, path, programmer=None):
        self.path = path
        # Normally serprog. It can be forced (say "dummy:...") to exercise
        # the whole chain without anything attached to anything.
        self.programmer = programmer
        self._process = None
        self._block_rect = threading.Lock()

    # -- building the command line --------------------------------------
    def _programmer(self, port, baud=115200, spispeed=None):
        if self.programmer:
            return self.programmer
        value = "serprog:dev=%s:%d" % (port_for_flashrom(port), baud)
        if spispeed:
            value += ",spispeed=%s" % spispeed
        return value

    def arguments(self, port, baud=115200, spispeed=None, chip=None,
                  verbose=False, progress=True):
        args = [self.path, "-p", self._programmer(port, baud, spispeed)]
        if chip:
            args += ["-c", chip]
        if verbose:
            args += ["-V"]
        if progress:
            args += ["--progress"]
        return args

    @staticmethod
    def _events(buffer, on_event):
        """Pulls the complete events out of the buffer, returns (rest, how_many)."""
        found_items = []
        for m in _RE_PHASE.finditer(buffer):
            found_items.append((m.start(), m.end(),
                            ("phase", m.group(1), int(m.group(2)))))
        for m in _RE_BLOCK.finditer(buffer):
            kind = "erase" if m.group(1) == "E" else "write"
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

    # -- running ---------------------------------------------------------
    def run(self, args, on_line=None, on_event=None, whole_log=True):
        """Runs flashrom and returns the Result. Blocking: call it from a thread.

        `on_event(kind, *data)` receives progress as it comes out:
          ("phase", name, percent)   from --progress
          ("erase", start, end)  from -V, one erased block
          ("write", start, end)    from -V, the written range
        `tutto_il_registro=False` keeps -V's noise out of the log.
        """
        lines = []

        def emit(text):
            if not text or _NOISE.match(text):
                return
            # percentages and markers are events, not text to read
            clean_ = _RE_BLOCK.sub("", _RE_PHASE.sub("", text)).strip(" .")
            if not clean_:
                return
            if not whole_log:
                if _INTERNAL.search(clean_) or not _INTERESTING.search(clean_):
                    return
            lines.append(clean_)
            if on_line:
                on_line(clean_)

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
            self._process = process

        # flashrom writes progress with \r: read byte by byte and split
        # on both terminators, or the bar never shows up at all.
        # ⚠️ The E(...)/W(...) markers and the percentages do NOT end with a
        # newline: they come out in the middle of other lines. Hence a
        # separate buffer to look for events in, independent of the log.
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
                        buffer, consumed = self._events(buffer, on_event)
                        if not consumed:
                            buffer = buffer[-64:]
                if chunk in (b"\n", b"\r"):
                    if leftover:
                        text = leftover.decode("utf-8", "replace").rstrip()
                        if on_event:
                            buffer, _ = self._events(buffer, on_event)
                        emit(text)
                        leftover = bytearray()
                else:
                    leftover += chunk
            if on_event:
                self._events(buffer, on_event)
            if leftover:
                emit(leftover.decode("utf-8", "replace").rstrip())
        finally:
            process.stdout.close()
            code = process.wait()
            with self._block_rect:
                aborted = getattr(self, "_aborted", False)
                self._aborted = False
                self._process = None

        return Result(code, lines, aborted=aborted)

    def abort(self):
        with self._block_rect:
            process = self._process
            if process is None:
                return False
            self._aborted = True
        try:
            process.terminate()
        except OSError:
            return False
        return True

    @property
    def running(self):
        with self._block_rect:
            return self._process is not None

    # -- operazioni -------------------------------------------------------
    def version(self):
        """The first line of `flashrom --version`, or None if it is not flashrom."""
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
        """Every chip this flashrom knows, read from flashrom itself.

        ⚠️ There is no hand-written table anywhere: by asking the
        executable, the list is always the one belonging to the version
        actually in use. A list of ours would go stale in silence.
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
        """Asks the chip how its write lock stands."""
        args = self.arguments(port, baud, spispeed, chip, verbose,
                              progress=False) + ["--wp-status"]
        result = self.run(args, on_line)
        return result, parse_protection(result.lines, result.ok)

    def unlock(self, port, baud=115200, spispeed=None, chip=None,
                verbose=False, on_line=None):
        """Removes the lock: --wp-disable and a zeroed range.

        ⚠️ This changes the STATE OF THE CHIP, not a program setting. It has
        to be asked for, not done quietly.
        """
        args = self.arguments(port, baud, spispeed, chip, verbose,
                              progress=False) + ["--wp-range=0,0", "--wp-disable"]
        return self.run(args, on_line)

    def read(self, destination, port, baud=115200, spispeed=None, chip=None,
              verbose=False, on_line=None, on_event=None):
        args = self.arguments(port, baud, spispeed, chip, verbose) + \
            ["-r", destination]
        return self.run(args, on_line, on_event, whole_log=verbose)

    def read_region(self, layout, region, destination, port, baud=115200,
                      spispeed=None, chip=None, verbose=False, on_line=None,
                      on_event=None):
        """Reads ONLY one region of the layout: for the quick checks."""
        args = self.arguments(port, baud, spispeed, chip, verbose) + \
            ["-l", layout, "-i", "%s:%s" % (region, destination), "-r"]
        return self.run(args, on_line, on_event, whole_log=verbose)

    def write(self, image, port, baud=115200, spispeed=None, chip=None,
               layout=None, region=None, verbose=False, on_line=None,
               on_event=None):
        # ⚠️ -V is always forced on a write: it is the only way to get the
        # E(...)/W(...) markers, that is the map's real blocks. The log
        # still stays clean unless the user asked for the detail.
        args = self.arguments(port, baud, spispeed, chip,
                              verbose=verbose or on_event is not None)
        if layout and region:
            args += ["-l", layout, "-i", region]
        args += ["-w", image]
        return self.run(args, on_line, on_event, whole_log=verbose)


def parse_chip(lines):
    """Pulls out of flashrom's chatter which chip it found."""
    chip = Chip()
    ambiguous = False
    for line in lines:
        m = _RE_FOUND.search(line)
        if m:
            chip.vendor, chip.name, chip.kb = m.group(1), m.group(2), int(m.group(3))
            continue
        m = _RE_NAME.search(line)
        if m:
            chip.vendor, chip.name = m.group(1), m.group(2)
            continue
        if _RE_AMBIGUOUS.search(line):
            ambiguous = True
            continue
        if ambiguous:
            m = _RE_CANDIDATE.match(line)
            if m and "flashrom" not in line.lower():
                chip.candidates.append(m.group(1))
    if ambiguous:
        chip.name = None
    return chip


def parse_protection(lines, outcome_ok=True):
    """Pulls the lock state out of what flashrom said."""
    text = "\n".join(lines)
    span = _RE_WP_SPAN.search(text)
    mode = _RE_WP_MODE.search(text)
    if not span and not mode:
        # a chip that cannot answer, or a programmer that cannot ask
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
        supported=outcome_ok)


class KnownChip(object):
    """One line of flashrom's listing."""

    def __init__(self, vendor, name, kb=None, kind=None, tested=None):
        self.vendor = vendor
        self.name = name
        self.kb = kb
        self.kind = kind
        self.tested = tested or ""      # P/R/E/W: what was really tested

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
        """Does flashrom claim it both read AND wrote this one?"""
        return "R" in self.tested and "W" in self.tested

    def __repr__(self):
        return "<%s %s %s>" % (self.vendor, self.name, self.kind)


# The listing's lines are fixed columns, but long names wrap
# e la continuazione ha la colonna del produttore VUOTA:
#     Winbond      W25Q32BW/     PREW    4096  SPI
#                  W25Q32CW/
#                  W25Q32DW
# ⚠️ Stitching them back is not a nicety: the name flashrom accepts is
# the WHOLE one, "W25Q32BW/W25Q32CW/W25Q32DW". Taking only the first
# would pick a model that flashrom then refuses.
_LIST_START = "Supported flash chips"
_VENDOR_WIDTH = 29


def parse_chip_list(lines):
    """The lines of `flashrom -L` become KnownChip objects."""
    out = []
    inside = False
    for line in lines:
        text = line.rstrip()
        if not inside:
            if text.startswith(_LIST_START):
                inside = True
            continue
        if not text.strip():
            continue
        if text.startswith(("Vendor", "(P =")) or text.lstrip().startswith("OK "):
            continue
        vendor = text[:_VENDOR_WIDTH].strip()
        rest = text[_VENDOR_WIDTH:]
        if not vendor:
            # continuation of the name above
            if out and rest.strip():
                out[-1].name += rest.strip()
            continue
        fields = re.split(r"\s{2,}", rest.strip())
        fields = [c for c in fields if c]
        if len(fields) < 2:
            # a line without a size or a type is not a chip line
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
    """Looks for flashrom.exe: inside the executable, beside it, in a
    subfolder, on the PATH.

    `extra` are folders to look at first: in the one-file executable this is
    given the temporary folder where PyInstaller unpacks what it carries, so
    the portable program brings its own flashrom along.
    """
    names = ["flashrom.exe", "flashrom"] if os.name == "nt" else ["flashrom"]
    roots = list(extra or []) + [app_folder]
    candidates = []
    for root in roots:
        if not root:
            continue
        for name in names:
            candidates.append(os.path.join(root, name))
            candidates.append(os.path.join(root, "flashrom", name))
    for path in candidates:
        if os.path.isfile(path):
            return path
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        for name in names:
            path = os.path.join(folder.strip('"'), name)
            if os.path.isfile(path):
                return path
    return None


def read_layout(path):
    """[(name, start, end)] from a flashrom layout file.

    ⚠️ flashrom's own parser accepts no comments: we tolerate them here only
    so that good lines do not disappear, but the file we hand it stays
    flashrom's.
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
