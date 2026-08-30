# -*- coding: utf-8 -*-
"""Shared test helpers.

⚠️ The BC-250 BIOS images are NOT in this repository: they are the dump of
one specific board and weigh 16 MiB each. The tests that need them look for
them, and when they are missing they stop and say why instead of failing.

Point SPIRANHA_BIOS_BACKUP at a folder containing them to run the full
test.
"""
from __future__ import unicode_literals

import os
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)

# What the full test needs. The stock dump goes by more than one name:
# all of them are accepted, so nobody has to rename a folder that
# already works.
STOCK = ("bc250-stock.rom", "BC250-stock-P3.00-scheda-Mattia.rom")
ATTESO = ("bc250-risultato-atteso.rom",)
LAYOUT = ("bc250-layout.txt",)
NECESSARI = (STOCK, ATTESO, LAYOUT)


def _primo(cartella, nomi):
    for nome in nomi:
        percorso = os.path.join(cartella, nome)
        if os.path.isfile(percorso):
            return percorso
    return None


def trova_backup():
    """The folder holding the BC-250 images, or None."""
    candidate = [os.environ.get("SPIRANHA_BIOS_BACKUP")]
    candidate += [
        os.path.join(RADICE, "bios-backup"),
        os.path.join(os.path.dirname(RADICE), "bios-backup"),
        os.path.join(os.path.dirname(RADICE), "SkillFishOS", "bios-backup"),
    ]
    for cartella in candidate:
        if cartella and all(_primo(cartella, n) for n in NECESSARI):
            return cartella
    return None


def file_prova(cartella):
    """(stock, atteso, layout) dentro la cartella trovata."""
    return tuple(_primo(cartella, n) for n in NECESSARI)


def backup_o_salta():
    """Restituisce la cartella, oppure esce con un messaggio chiaro."""
    cartella = trova_backup()
    if cartella:
        return cartella
    print("SKIPPED: cannot find the BC-250 images.")
    print("These are needed, in one folder:")
    for gruppo in NECESSARI:
        print("   " + " oppure ".join(gruppo))
    print("Point SPIRANHA_BIOS_BACKUP at it,")
    print("or put them in a 'bios-backup' folder next to the project.")
    sys.exit(0)


def flashrom_o_salta():
    """flashrom.exe, or bail out: it is not in the repository (see
    flashrom/PROVENANCE.md for building it)."""
    percorso = os.path.join(RADICE, "flashrom", "flashrom.exe")
    if os.path.isfile(percorso):
        return percorso
    print("SKIPPED: cannot find flashrom/flashrom.exe.")
    print("Not in the repository: build it following flashrom/PROVENANCE.md,")
    print("with the 'dummy' programmer enabled (these tests drive it).")
    sys.exit(0)
