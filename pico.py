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

MAGIC0 = 0x0A324655
MAGIC1 = 0x9E5D5157
MAGIC_END = 0x0AB16F30
FAMILY_FLAG = 0x00002000
FAMILY_RP2040 = 0xE48BFF56

BLOCK = 512
PAYLOAD = 256
BASE_FLASH = 0x10000000

# how many times to retry a copy that cannot even get started
COPY_ATTEMPTS = 6
FLASH_PICO = 2 * 1024 * 1024        # the original Pico has 2 MiB

BOOTSEL_BAUD = 1200                 # opening at this rate = back to BOOTSEL
NO_WINDOW = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
VOLUME_LABEL = "RPI-RP2"
FIRMWARE_NAME = "pico_serprog.uf2"
INFO_FILE = "INFO_UF2.TXT"
DRIVE_REMOVABLE = 2


class Board(object):
    """An RP2040 board in BOOTSEL, seen as a disk."""

    def __init__(self, drive, model=None, board_id=None, byte_liberi=0,
                 serial=None):
        self.drive = drive                      # "E:\\"
        self.model = model or "RP2040"
        self.board_id = board_id or "?"
        self.byte_liberi = byte_liberi
        # ⚠️ This is NOT the serial number the same board shows while the
        # firmware runs: the bootloader exposes one of its own, shorter.
        # Verified on the same board: 12 digits here, 16 over there.
        self.serial = serial

    @property
    def letter(self):
        return self.drive[:2]

    def __repr__(self):
        return "<Scheda %s %s>" % (self.letter, self.model)


# ------------------------------------------------------------ finding

def _unita_rimovibili():
    if os.name != "nt":
        return []
    found = []
    maschera = ctypes.windll.kernel32.GetLogicalDrives()
    for index in range(26):
        if not (maschera >> index) & 1:
            continue
        drive = "%s:\\" % chr(ord("A") + index)
        try:
            if ctypes.windll.kernel32.GetDriveTypeW(drive) == DRIVE_REMOVABLE:
                found.append(drive)
        except Exception:                        # noqa: BLE001
            continue
    return found


def _leggi_informazioni(path):
    """INFO_UF2.TXT -> (model, board id). The file is two lines."""
    model = board_id = None
    try:
        with open(path, "rb") as f:
            text = f.read(512).decode("ascii", "replace")
    except OSError:
        return None, None
    for line in text.splitlines():
        if line.startswith("Model:"):
            model = line.split(":", 1)[1].strip()
        elif line.startswith("Board-ID:"):
            board_id = line.split(":", 1)[1].strip()
    return model, board_id


def is_rp2040(model, board_id):
    """Does this board declare itself an RP2040?

    ⚠️ The real Board-ID is "RPI-RP2", not "RP2...": RP2 is looked for INSIDE
    the string. The first version demanded that it start with RP2 and
    recognised no board at all -- only the hardware caught that.
    """
    return "RP2" in ("%s %s" % (board_id or "", model or "")).upper()


def boards_in_bootsel():
    """The RP2040 boards waiting for firmware, right now."""
    found = []
    for drive in _unita_rimovibili():
        informazioni = os.path.join(drive, INFO_FILE)
        if not os.path.isfile(informazioni):
            continue
        model, board_id = _leggi_informazioni(informazioni)
        # copying onto some random disk would do no harm, but no good
        # either
        if not is_rp2040(model, board_id):
            continue
        liberi = 0
        try:
            liberi = shutil.disk_usage(drive).free
        except OSError:
            pass
        found.append(Board(drive, model, board_id, liberi,
                              serial=serial_of_drive(drive)))
    return found


# the serial the bootloader exposes is inside the device path:
#   USBSTOR\DISK&VEN_RPI&PROD_RP2&REV_3\9&25F25AF4&0&E0C9125B0D9B&0
_RE_SERIALE = re.compile(r"&([0-9A-F]{8,20})&\d+$", re.IGNORECASE)
_CACHE_SERIALI = {}


def serial_of_drive(drive):
    """The serial number of the board in BOOTSEL, from its drive letter.

    ⚠️ It costs a PowerShell call, so the result is kept: the watcher looks at
    the drives every two seconds and cannot pay that each time. A drive letter
    does not change board under your feet without the board disappearing
    first, and in that case the entry is thrown away.
    """
    letter = (drive or "")[:1].upper()
    if not letter:
        return None
    if letter in _CACHE_SERIALI:
        return _CACHE_SERIALI[letter]
    serial = None
    if os.name == "nt":
        command = (
            "$ErrorActionPreference='SilentlyContinue';"
            "Get-CimInstance Win32_DiskDrive | ForEach-Object { $d=$_;"
            " Get-CimAssociatedInstance -InputObject $d"
            " -ResultClassName Win32_DiskPartition | ForEach-Object {"
            " Get-CimAssociatedInstance -InputObject $_"
            " -ResultClassName Win32_LogicalDisk } | ForEach-Object {"
            " \"$($_.DeviceID)|$($d.PNPDeviceID)\" } }")
        try:
            output = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True, timeout=20,
                creationflags=NO_WINDOW).stdout.decode("utf-8", "replace")
        except Exception:                            # noqa: BLE001
            output = ""
        for line in output.splitlines():
            if "|" not in line:
                continue
            disco, path = line.split("|", 1)
            if disco.strip().upper().startswith(letter + ":"):
                hit = _RE_SERIALE.search(path.strip())
                if hit:
                    serial = hit.group(1).upper()
                break
    _CACHE_SERIALI[letter] = serial
    return serial


def forget_serials():
    """To be called when a board goes away: the letter could come back on a
    different one."""
    _CACHE_SERIALI.clear()


# ------------------------------------------------------------ formato UF2

def shipped_version(folder):
    """The version of the UF2 we ship, from the VERSION file next to it."""
    try:
        path = os.path.join(folder, "VERSION")
        with io.open(path, encoding="utf-8") as f:
            version = f.read().strip()
        return version or None
    except Exception:                                  # noqa: BLE001
        return None


def uf2_block(address, data, number, total, family=FAMILY_RP2040):
    """One 512-byte block, the way the bootloader wants it."""
    if len(data) > PAYLOAD:
        raise ValueError("carico utile troppo grande: %d" % len(data))
    header = struct.pack("<IIIIIIII", MAGIC0, MAGIC1, FAMILY_FLAG,
                        address, PAYLOAD, number, total, family)
    body = data + b"\x00" * (476 - len(data))
    return header + body + struct.pack("<I", MAGIC_END)


def read_uf2(path):
    """Checks a .uf2 and reports what is in it.

    Returns (blocks, first_address, last_address, families). Raises ValueError
    when the file is not a valid UF2: this is the check made BEFORE copying it
    onto a board.
    """
    with open(path, "rb") as f:
        data = f.read()
    if not data or len(data) % BLOCK:
        raise ValueError("non e' un UF2: la lunghezza non e' multipla di 512")
    blocks = len(data) // BLOCK
    indirizzi = []
    families = set()
    for index in range(blocks):
        chunk = data[index * BLOCK:(index + 1) * BLOCK]
        m0, m1, _bandiere, address, how_many, number, total, family = \
            struct.unpack("<IIIIIIII", chunk[:32])
        end = struct.unpack("<I", chunk[-4:])[0]
        if m0 != MAGIC0 or m1 != MAGIC1 or end != MAGIC_END:
            raise ValueError("blocco %d: le magie non tornano" % index)
        if total != blocks:
            raise ValueError("blocco %d: dice %d blocchi, il file ne ha %d"
                             % (index, total, blocks))
        if number != index:
            raise ValueError("blocco %d: si dichiara il numero %d" % (index, number))
        if how_many > PAYLOAD:
            raise ValueError("blocco %d: carico utile %d" % (index, how_many))
        indirizzi.append(address)
        families.add(family)
    return blocks, min(indirizzi), max(indirizzi) + PAYLOAD - 1, families


def make_eraser(path, size=FLASH_PICO):
    """Writes a .uf2 that returns the board to its factory state.

    It writes 0xFF across the whole flash: since the bootloader erases each
    sector before writing it, the result is an erased flash. With no valid
    second stage, the board comes back up in BOOTSEL.
    """
    if size % PAYLOAD:
        raise ValueError("la dimensione dev'essere multipla di %d" % PAYLOAD)
    total = size // PAYLOAD
    empty = b"\xff" * PAYLOAD
    with open(path, "wb") as f:
        for number in range(total):
            f.write(uf2_block(BASE_FLASH + number * PAYLOAD, empty,
                               number, total))
    return path


# ------------------------------------------------- rientro nel bootloader

def back_to_bootsel(port):
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
        connection = serial.Serial(port, BOOTSEL_BAUD, timeout=1)
        try:
            connection.close()
        except Exception:                            # noqa: BLE001
            pass
    except Exception:                                # noqa: BLE001
        pass          # atteso: la scheda se n'e' andata
    return True, None


# ------------------------------------------------------------ installazione

def install(uf2_path, card, on_line=None):
    """Copies the firmware onto the board. Returns (done, reason).

    ⚠️ There is no verification by reading back: as soon as the bootloader is
    done the board detaches and restarts, so the copy "fails" at the end and
    that is NORMAL. The real check is that it comes back as a serial port.
    """
    def dillo(text):
        if on_line:
            on_line(text)

    if not os.path.isfile(uf2_path):
        return False, "non trovo %s" % uf2_path
    try:
        blocks, first, last, families = read_uf2(uf2_path)
    except ValueError as e:
        return False, "%s" % e
    if FAMILY_RP2040 not in families:
        return False, "questo .uf2 non e' per RP2040"
    dillo("%s: %d blocchi, 0x%08X-0x%08X" % (
        os.path.basename(uf2_path), blocks, first, last))

    needed = blocks * BLOCK
    if card.byte_liberi and needed > card.byte_liberi:
        return False, "non ci sta: servono %d byte, liberi %d" % (
            needed, card.byte_liberi)

    destination = os.path.join(card.drive, os.path.basename(uf2_path))
    # ⚠️ An error once the copy has started and an error BEFORE a single
    # byte is written look the same (both are OSError) and are nothing
    # alike: the first is the board restarting, the second is a copy that
    # never happened. Confusing them means saying "done" about firmware
    # that was never written. It happens for real: a board fresh into
    # BOOTSEL answers "Permission denied" until Windows has finished
    # mounting the drive.
    for attempt in range(COPY_ATTEMPTS):
        written_bytes = 0
        try:
            with open(uf2_path, "rb") as source_image:
                with open(destination, "wb") as output:
                    while True:
                        chunk = source_image.read(64 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        written_bytes += len(chunk)
                    try:
                        output.flush()
                        os.fsync(output.fileno())
                    except OSError:
                        pass      # la scheda si e' gia' staccata: va bene cosi'
        except OSError as e:
            if written_bytes:
                # the disk vanishes under our feet as soon as the
                # bootloader has it all: this is the normal course
                dillo("la scheda si e' staccata durante la copia "
                      "(e' normale): %s" % e)
                return True, None
            if attempt + 1 < COPY_ATTEMPTS:
                dillo("il disco non accetta ancora la copia, riprovo: %s" % e)
                time.sleep(0.7)
                continue
            return False, "la copia non e' mai partita: %s" % e
        return True, None
    return False, "la copia non e' mai partita"
