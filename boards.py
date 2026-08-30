# -*- coding: utf-8 -*-
"""Giving boards a name, and recognising them next time.

⚠️ THE AWKWARD PART: an RP2040 board has TWO different identifiers, and they
do not even resemble each other.
  - while the firmware runs it appears as a serial port, and its USB serial
    number is the flash unique id: 16 hex digits, e.g. 5303284738DE6E1C;
  - held in BOOTSEL it appears as a disk, and there the bootloader exposes a
    DIFFERENT one, 12 digits: e.g. E0C9125B0D9B.
Verified on the same board: neither can be derived from the other.

So a board here is a pair (running serial, BOOTSEL serial), and the two sides
are learned by themselves: when a board that was in BOOTSEL gets programmed
and a new port shows up right afterwards, that port IS that board. The same
in reverse, when it is sent back to BOOTSEL.
"""
from __future__ import unicode_literals


class Registry(object):
    """The known boards. Stored inside the configuration."""

    def __init__(self, listing=None):
        # each entry: {"name": str, "run": str|None, "boot": str|None}
        self.boards = [dict(v) for v in (listing or [])]
        # ⚠️ Up to 1.2.0 the name was stored under "nome". Reading it back is
        # not cosmetic: the name is the only thing that tells two identical
        # boards apart on the bench, and it was lost on upgrade.
        for entry in self.boards:
            if "nome" in entry:
                entry.setdefault("name", entry.pop("nome"))

    # ------------------------------------------------------------ lookup
    def _find(self, run=None, boot=None):
        for entry in self.boards:
            if run and entry.get("run") == run:
                return entry
            if boot and entry.get("boot") == boot:
                return entry
        return None

    def name(self, run=None, boot=None):
        entry = self._find(run, boot)
        return (entry or {}).get("name") or None

    def entry(self, run=None, boot=None):
        return self._find(run, boot)

    # ------------------------------------------------------------ changes
    def set_name(self, name, run=None, boot=None):
        """Name a board. An empty name forgets it."""
        if not (run or boot):
            return None
        entry = self._find(run, boot)
        if entry is None:
            if not name:
                return None
            entry = {"name": "", "run": None, "boot": None}
            self.boards.append(entry)
        entry["name"] = name.strip()
        if run:
            entry["run"] = run
        if boot:
            entry["boot"] = boot
        if not entry["name"]:
            self.boards.remove(entry)
            return None
        return entry

    def link(self, run, boot):
        """Records that these two identifiers are the same board.

        This is only known for certain after watching it move from one state
        to the other: that is the single moment the two sides touch.
        """
        if not (run and boot):
            return None
        by_run = self._find(run=run)
        by_boot = self._find(boot=boot)
        if by_run and by_boot and by_run is not by_boot:
            # two boards turn out to be one: merge them, keeping the name
            # that was already given (the first one there is)
            by_run["boot"] = boot
            if not by_run.get("name"):
                by_run["name"] = by_boot.get("name", "")
            self.boards.remove(by_boot)
            return by_run
        entry = by_run or by_boot
        if entry is None:
            entry = {"name": "", "run": None, "boot": None}
            self.boards.append(entry)
        entry["run"] = run
        entry["boot"] = boot
        return entry

    # ------------------------------------------------------------ saving
    def as_list(self):
        return [dict(v) for v in self.boards if v.get("run") or v.get("boot")]


def label_for(name, serial, count=6):
    """"name · 5303284738DE6E1C", or just the serial when it has no name."""
    if not serial:
        return name or ""
    if name:
        return "%s · %s" % (name, serial)
    return serial


def tail_of(serial, count=4):
    """The last digits of the serial: the ones we make you retype to confirm
    WHICH board is about to be erased."""
    return (serial or "")[-count:].upper()
