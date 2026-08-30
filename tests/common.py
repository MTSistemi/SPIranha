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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# What the full test needs. The stock dump goes by more than one name:
# all of them are accepted, so nobody has to rename a folder that
# already works.
STOCK = ("bc250-stock.rom", "BC250-stock-P3.00-scheda-Mattia.rom")
EXPECTED = ("bc250-expected-result.rom", "bc250-risultato-atteso.rom")
LAYOUT = ("bc250-layout.txt",)
REQUIRED = (STOCK, EXPECTED, LAYOUT)


def _first_of(folder, names):
    for name in names:
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            return path
    return None


def find_backup():
    """The folder holding the BC-250 images, or None."""
    candidate = [os.environ.get("SPIRANHA_BIOS_BACKUP")]
    candidate += [
        os.path.join(ROOT, "bios-backup"),
        os.path.join(os.path.dirname(ROOT), "bios-backup"),
        os.path.join(os.path.dirname(ROOT), "SkillFishOS", "bios-backup"),
    ]
    for folder in candidate:
        if folder and all(_first_of(folder, n) for n in REQUIRED):
            return folder
    return None


def test_files(folder):
    """(stock, expected, layout) inside the folder that was found."""
    return tuple(_first_of(folder, n) for n in REQUIRED)


def backup_or_skip():
    """The folder, or a clean exit with a message that says why."""
    folder = find_backup()
    if folder:
        return folder
    print("SKIPPED: cannot find the BC-250 images.")
    print("These are needed, in one folder:")
    for group_ in REQUIRED:
        print("   " + " or ".join(group_))
    print("Point SPIRANHA_BIOS_BACKUP at it,")
    print("or put them in a 'bios-backup' folder next to the project.")
    sys.exit(0)


def flashrom_or_skip():
    """flashrom.exe, or bail out: it is not in the repository (see
    flashrom/PROVENANCE.md for building it)."""
    path = os.path.join(ROOT, "flashrom", "flashrom.exe")
    if os.path.isfile(path):
        return path
    print("SKIPPED: cannot find flashrom/flashrom.exe.")
    print("Not in the repository: build it following flashrom/PROVENANCE.md,")
    print("with the 'dummy' programmer enabled (these tests drive it).")
    sys.exit(0)
