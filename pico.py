# -*- coding: utf-8 -*-
"""The RP2040 as the programmer: spotting it, programming it, resetting it.

An RP2040 board plugged in with BOOTSEL held down shows up as a removable
disk called RPI-RP2, with INFO_UF2.TXT inside. Copy a .uf2 file onto it and
the board programs itself and restarts. No external tool is needed: the ROM
bootloader does all of it.

In here:
  - boards in BOOTSEL are found by looking at the removable drives;
  - the firmware is installed by copying the .uf2 across;
  - a .uf2 is generated that RESETS THE BOARD TO FACTORY.

⚠️ ABOUT "RESET TO FACTORY". Nobody's flash_nuke needs downloading:
before writing a sector, the bootloader ERASES it. So a .uf2 that writes 0xFF
across the whole flash leaves it erased, which is the factory state -- with no
valid second stage the board returns to BOOTSEL by itself. We generate that
file ourselves, byte by byte, so no stranger's binary is involved.

UF2 format (512-byte blocks, 256 of payload):
    0  magic 0x0A324655 "UF2\\n"
    4  magic 0x9E5D5157
    8  flags               0x2000 = a family id is present
   12  target address
   16  payload bytes (256)
   20  block number
   24  total blocks
   28  family id (RP2040 = 0xE48BFF56)
   32  data (476 bytes, first 256 used)
  508  final magic 0x0AB16F30
"""
from __future__ import unicode_literals

import ctypes
import io
import os
import re
import shutil
import struct
import subprocess
import time

MAGIA0 = 0x0A324655
MAGIA1 = 0x9E5D5157
MAGIA_FINE = 0x0AB16F30
BANDIERA_FAMIGLIA = 0x00002000
FAMIGLIA_RP2040 = 0xE48BFF56

BLOCCO = 512
CARICO = 256
BASE_FLASH = 0x10000000

# how many times to retry a copy that cannot even get started
TENTATIVI_COPIA = 6
FLASH_PICO = 2 * 1024 * 1024        # the original Pico has 2 MiB

BAUD_BOOTSEL = 1200                 # opening at this rate = back to BOOTSEL
SENZA_FINESTRA = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
ETICHETTA = "RPI-RP2"
NOME_FIRMWARE = "pico_serprog.uf2"
INFORMAZIONI = "INFO_UF2.TXT"
DRIVE_REMOVIBILE = 2


class Scheda(object):
    """An RP2040 board in BOOTSEL, seen as a disk."""

    def __init__(self, unita, modello=None, identificativo=None, byte_liberi=0,
                 seriale=None):
        self.unita = unita                      # "E:\\"
        self.modello = modello or "RP2040"
        self.identificativo = identificativo or "?"
        self.byte_liberi = byte_liberi
        # ⚠️ This is NOT the serial number the same board shows while the
        # firmware runs: the bootloader exposes one of its own, shorter.
        # Verified on the same board: 12 digits here, 16 over there.
        self.seriale = seriale

    @property
    def lettera(self):
        return self.unita[:2]

    def __repr__(self):
        return "<Scheda %s %s>" % (self.lettera, self.modello)


# ------------------------------------------------------------ finding

def _unita_rimovibili():
    if os.name != "nt":
        return []
    trovate = []
    maschera = ctypes.windll.kernel32.GetLogicalDrives()
    for indice in range(26):
        if not (maschera >> indice) & 1:
            continue
        unita = "%s:\\" % chr(ord("A") + indice)
        try:
            if ctypes.windll.kernel32.GetDriveTypeW(unita) == DRIVE_REMOVIBILE:
                trovate.append(unita)
        except Exception:                        # noqa: BLE001
            continue
    return trovate


def _leggi_informazioni(percorso):
    """INFO_UF2.TXT -> (model, board id). The file is two lines."""
    modello = identificativo = None
    try:
        with open(percorso, "rb") as f:
            testo = f.read(512).decode("ascii", "replace")
    except OSError:
        return None, None
    for riga in testo.splitlines():
        if riga.startswith("Model:"):
            modello = riga.split(":", 1)[1].strip()
        elif riga.startswith("Board-ID:"):
            identificativo = riga.split(":", 1)[1].strip()
    return modello, identificativo


def e_rp2040(modello, identificativo):
    """Does this board declare itself an RP2040?

    ⚠️ The real Board-ID is "RPI-RP2", not "RP2...": RP2 is looked for INSIDE
    the string. The first version demanded that it start with RP2 and
    recognised no board at all -- only the hardware caught that.
    """
    return "RP2" in ("%s %s" % (identificativo or "", modello or "")).upper()


def schede_in_bootsel():
    """The RP2040 boards waiting for firmware, right now."""
    trovate = []
    for unita in _unita_rimovibili():
        informazioni = os.path.join(unita, INFORMAZIONI)
        if not os.path.isfile(informazioni):
            continue
        modello, identificativo = _leggi_informazioni(informazioni)
        # copying onto some random disk would do no harm, but no good
        # either
        if not e_rp2040(modello, identificativo):
            continue
        liberi = 0
        try:
            liberi = shutil.disk_usage(unita).free
        except OSError:
            pass
        trovate.append(Scheda(unita, modello, identificativo, liberi,
                              seriale=seriale_di_unita(unita)))
    return trovate


# the serial the bootloader exposes is inside the device path:
#   USBSTOR\DISK&VEN_RPI&PROD_RP2&REV_3\9&25F25AF4&0&E0C9125B0D9B&0
_RE_SERIALE = re.compile(r"&([0-9A-F]{8,20})&\d+$", re.IGNORECASE)
_CACHE_SERIALI = {}


def seriale_di_unita(unita):
    """The serial number of the board in BOOTSEL, from its drive letter.

    ⚠️ It costs a PowerShell call, so the result is kept: the watcher looks at
    the drives every two seconds and cannot pay that each time. A drive letter
    does not change board under your feet without the board disappearing
    first, and in that case the entry is thrown away.
    """
    lettera = (unita or "")[:1].upper()
    if not lettera:
        return None
    if lettera in _CACHE_SERIALI:
        return _CACHE_SERIALI[lettera]
    seriale = None
    if os.name == "nt":
        comando = (
            "$ErrorActionPreference='SilentlyContinue';"
            "Get-CimInstance Win32_DiskDrive | ForEach-Object { $d=$_;"
            " Get-CimAssociatedInstance -InputObject $d"
            " -ResultClassName Win32_DiskPartition | ForEach-Object {"
            " Get-CimAssociatedInstance -InputObject $_"
            " -ResultClassName Win32_LogicalDisk } | ForEach-Object {"
            " \"$($_.DeviceID)|$($d.PNPDeviceID)\" } }")
        try:
            uscita = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
                capture_output=True, timeout=20,
                creationflags=SENZA_FINESTRA).stdout.decode("utf-8", "replace")
        except Exception:                            # noqa: BLE001
            uscita = ""
        for riga in uscita.splitlines():
            if "|" not in riga:
                continue
            disco, percorso = riga.split("|", 1)
            if disco.strip().upper().startswith(lettera + ":"):
                trovato = _RE_SERIALE.search(percorso.strip())
                if trovato:
                    seriale = trovato.group(1).upper()
                break
    _CACHE_SERIALI[lettera] = seriale
    return seriale


def dimentica_seriali():
    """To be called when a board goes away: the letter could come back on a
    different one."""
    _CACHE_SERIALI.clear()


# ------------------------------------------------------------ formato UF2

def versione_disponibile(cartella):
    """The version of the UF2 we ship, from the VERSION file next to it."""
    try:
        percorso = os.path.join(cartella, "VERSION")
        with io.open(percorso, encoding="utf-8") as f:
            versione = f.read().strip()
        return versione or None
    except Exception:                                  # noqa: BLE001
        return None


def blocco_uf2(indirizzo, dati, numero, totale, famiglia=FAMIGLIA_RP2040):
    """One 512-byte block, the way the bootloader wants it."""
    if len(dati) > CARICO:
        raise ValueError("carico utile troppo grande: %d" % len(dati))
    testa = struct.pack("<IIIIIIII", MAGIA0, MAGIA1, BANDIERA_FAMIGLIA,
                        indirizzo, CARICO, numero, totale, famiglia)
    corpo = dati + b"\x00" * (476 - len(dati))
    return testa + corpo + struct.pack("<I", MAGIA_FINE)


def leggi_uf2(percorso):
    """Checks a .uf2 and reports what is in it.

    Returns (blocks, first_address, last_address, families). Raises ValueError
    when the file is not a valid UF2: this is the check made BEFORE copying it
    onto a board.
    """
    with open(percorso, "rb") as f:
        dati = f.read()
    if not dati or len(dati) % BLOCCO:
        raise ValueError("non e' un UF2: la lunghezza non e' multipla di 512")
    blocchi = len(dati) // BLOCCO
    indirizzi = []
    famiglie = set()
    for indice in range(blocchi):
        pezzo = dati[indice * BLOCCO:(indice + 1) * BLOCCO]
        m0, m1, _bandiere, indirizzo, quanti, numero, totale, famiglia = \
            struct.unpack("<IIIIIIII", pezzo[:32])
        fine = struct.unpack("<I", pezzo[-4:])[0]
        if m0 != MAGIA0 or m1 != MAGIA1 or fine != MAGIA_FINE:
            raise ValueError("blocco %d: le magie non tornano" % indice)
        if totale != blocchi:
            raise ValueError("blocco %d: dice %d blocchi, il file ne ha %d"
                             % (indice, totale, blocchi))
        if numero != indice:
            raise ValueError("blocco %d: si dichiara il numero %d" % (indice, numero))
        if quanti > CARICO:
            raise ValueError("blocco %d: carico utile %d" % (indice, quanti))
        indirizzi.append(indirizzo)
        famiglie.add(famiglia)
    return blocchi, min(indirizzi), max(indirizzi) + CARICO - 1, famiglie


def genera_cancellazione(percorso, byte=FLASH_PICO):
    """Writes a .uf2 that returns the board to its factory state.

    It writes 0xFF across the whole flash: since the bootloader erases each
    sector before writing it, the result is an erased flash. With no valid
    second stage, the board comes back up in BOOTSEL.
    """
    if byte % CARICO:
        raise ValueError("la dimensione dev'essere multipla di %d" % CARICO)
    totale = byte // CARICO
    vuoto = b"\xff" * CARICO
    with open(percorso, "wb") as f:
        for numero in range(totale):
            f.write(blocco_uf2(BASE_FLASH + numero * CARICO, vuoto,
                               numero, totale))
    return percorso


# ------------------------------------------------- rientro nel bootloader

def rientra_in_bootsel(porta):
    """Asks the firmware to restart into the ROM bootloader.

    The port is opened at 1200 baud: that is the Arduino Leonardo convention,
    and our pico-serprog implements it (see firmware/). It works ONLY with our
    firmware from 1.2 onwards; with anything older nothing happens and the
    BOOTSEL button stays the only way.

    ⚠️ Opening the port usually FAILS, and that is fine: the board reboots and
    vanishes while the system is still configuring the port. It is the sign it
    worked, not an error. The caller has to check by watching for the board to
    reappear in BOOTSEL, not by this function's result.
    """
    try:
        import serial
    except ImportError:
        return False, "pyserial non e' installato"
    try:
        collegamento = serial.Serial(porta, BAUD_BOOTSEL, timeout=1)
        try:
            collegamento.close()
        except Exception:                            # noqa: BLE001
            pass
    except Exception:                                # noqa: BLE001
        pass          # atteso: la scheda se n'e' andata
    return True, None


# ------------------------------------------------------------ installazione

def installa(percorso_uf2, scheda, su_riga=None):
    """Copies the firmware onto the board. Returns (done, reason).

    ⚠️ There is no verification by reading back: as soon as the bootloader is
    done the board detaches and restarts, so the copy "fails" at the end and
    that is NORMAL. The real check is that it comes back as a serial port.
    """
    def dillo(testo):
        if su_riga:
            su_riga(testo)

    if not os.path.isfile(percorso_uf2):
        return False, "non trovo %s" % percorso_uf2
    try:
        blocchi, primo, ultimo, famiglie = leggi_uf2(percorso_uf2)
    except ValueError as e:
        return False, "%s" % e
    if FAMIGLIA_RP2040 not in famiglie:
        return False, "questo .uf2 non e' per RP2040"
    dillo("%s: %d blocchi, 0x%08X-0x%08X" % (
        os.path.basename(percorso_uf2), blocchi, primo, ultimo))

    servono = blocchi * BLOCCO
    if scheda.byte_liberi and servono > scheda.byte_liberi:
        return False, "non ci sta: servono %d byte, liberi %d" % (
            servono, scheda.byte_liberi)

    destinazione = os.path.join(scheda.unita, os.path.basename(percorso_uf2))
    # ⚠️ An error once the copy has started and an error BEFORE a single
    # byte is written look the same (both are OSError) and are nothing
    # alike: the first is the board restarting, the second is a copy that
    # never happened. Confusing them means saying "done" about firmware
    # that was never written. It happens for real: a board fresh into
    # BOOTSEL answers "Permission denied" until Windows has finished
    # mounting the drive.
    for tentativo in range(TENTATIVI_COPIA):
        scritti = 0
        try:
            with open(percorso_uf2, "rb") as sorgente:
                with open(destinazione, "wb") as uscita:
                    while True:
                        pezzo = sorgente.read(64 * 1024)
                        if not pezzo:
                            break
                        uscita.write(pezzo)
                        scritti += len(pezzo)
                    try:
                        uscita.flush()
                        os.fsync(uscita.fileno())
                    except OSError:
                        pass      # la scheda si e' gia' staccata: va bene cosi'
        except OSError as e:
            if scritti:
                # the disk vanishes under our feet as soon as the
                # bootloader has it all: this is the normal course
                dillo("la scheda si e' staccata durante la copia "
                      "(e' normale): %s" % e)
                return True, None
            if tentativo + 1 < TENTATIVI_COPIA:
                dillo("il disco non accetta ancora la copia, riprovo: %s" % e)
                time.sleep(0.7)
                continue
            return False, "la copia non e' mai partita: %s" % e
        return True, None
    return False, "la copia non e' mai partita"
