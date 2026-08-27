# -*- coding: utf-8 -*-
"""Roba condivisa fra le prove.

⚠️ Le immagini di BIOS della BC-250 NON stanno in questo repository: sono il
dump di una scheda precisa e pesano 16 MiB l'una. Le prove che ne hanno bisogno
le cercano, e se non ci sono si fermano dicendo perche' invece di fallire.

Shared test helpers. The BC-250 BIOS images are NOT in this repository: point
SPIRANHA_BIOS_BACKUP at a folder containing them to run the full test.
"""
from __future__ import unicode_literals

import os
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)

# Quello che serve alla prova completa. Il dump originale puo' chiamarsi in
# piu' modi: si accettano tutti, cosi' non si e' costretti a rinominare una
# cartella che gia' funziona.
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
    """La cartella con le immagini della BC-250, o None."""
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
    print("SALTATA: non trovo le immagini della BC-250.")
    print("Servono, nella stessa cartella:")
    for gruppo in NECESSARI:
        print("   " + " oppure ".join(gruppo))
    print("Indicarla con la variabile d'ambiente SPIRANHA_BIOS_BACKUP,")
    print("oppure metterle in una cartella 'bios-backup' accanto al progetto.")
    sys.exit(0)


def flashrom_o_salta():
    """flashrom.exe, oppure esce: nel repository non c'e' (vedi
    flashrom/PROVENIENZA.md per compilarlo)."""
    percorso = os.path.join(RADICE, "flashrom", "flashrom.exe")
    if os.path.isfile(percorso):
        return percorso
    print("SALTATA: non trovo flashrom/flashrom.exe.")
    print("Non e' nel repository: si compila seguendo flashrom/PROVENIENZA.md,")
    print("con il programmatore 'dummy' attivo (serve a queste prove).")
    sys.exit(0)
