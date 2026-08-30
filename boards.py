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


class Anagrafica(object):
    """The known boards. Stored inside the configuration."""

    def __init__(self, elenco=None):
        # each entry: {"nome": str, "run": str|None, "boot": str|None}
        self.schede = [dict(v) for v in (elenco or [])]

    # ------------------------------------------------------------ lookup
    def _trova(self, run=None, boot=None):
        for voce in self.schede:
            if run and voce.get("run") == run:
                return voce
            if boot and voce.get("boot") == boot:
                return voce
        return None

    def nome(self, run=None, boot=None):
        voce = self._trova(run, boot)
        return (voce or {}).get("nome") or None

    def voce(self, run=None, boot=None):
        return self._trova(run, boot)

    # ------------------------------------------------------------ changes
    def imposta_nome(self, nome, run=None, boot=None):
        """Name a board. An empty name forgets it."""
        if not (run or boot):
            return None
        voce = self._trova(run, boot)
        if voce is None:
            if not nome:
                return None
            voce = {"nome": "", "run": None, "boot": None}
            self.schede.append(voce)
        voce["nome"] = nome.strip()
        if run:
            voce["run"] = run
        if boot:
            voce["boot"] = boot
        if not voce["nome"]:
            self.schede.remove(voce)
            return None
        return voce

    def collega(self, run, boot):
        """Records that these two identifiers are the same board.

        This is only known for certain after watching it move from one state
        to the other: that is the single moment the two sides touch.
        """
        if not (run and boot):
            return None
        per_run = self._trova(run=run)
        per_boot = self._trova(boot=boot)
        if per_run and per_boot and per_run is not per_boot:
            # two boards turn out to be one: merge them, keeping the name
            # that was already given (the first one there is)
            per_run["boot"] = boot
            if not per_run.get("nome"):
                per_run["nome"] = per_boot.get("nome", "")
            self.schede.remove(per_boot)
            return per_run
        voce = per_run or per_boot
        if voce is None:
            voce = {"nome": "", "run": None, "boot": None}
            self.schede.append(voce)
        voce["run"] = run
        voce["boot"] = boot
        return voce

    # ------------------------------------------------------------ saving
    def come_elenco(self):
        return [dict(v) for v in self.schede if v.get("run") or v.get("boot")]


def etichetta(nome, seriale, quante=6):
    """"name · 5303284738DE6E1C", or just the serial when it has no name."""
    if not seriale:
        return nome or ""
    if nome:
        return "%s · %s" % (nome, seriale)
    return seriale


def coda(seriale, quante=4):
    """The last digits of the serial: the ones we make you retype to confirm
    WHICH board is about to be erased."""
    return (seriale or "")[-quante:].upper()
