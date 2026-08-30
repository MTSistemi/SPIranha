# -*- coding: utf-8 -*-
"""Talks to the Pico in the serprog protocol, before handing it to flashrom.

Why bother, when flashrom does the work anyway: showing up as a serial port
means nothing, any wrong firmware would do that too. Here it is asked who it
is and what it can do, so a Pico with the wrong firmware is found out at once
and not halfway through a write.

⚠️ Only one process can hold the serial port open: this module opens, asks
and closes. Nothing here is touched while flashrom runs.

Commands used (serprog specification):
  0x00 NOP        -> ACK
  0x01 Q_IFACE    -> ACK + 2 bytes, version (must be 1)
  0x03 Q_PGMNAME  -> ACK + 16 bytes, programmer name
  0x05 Q_BUSTYPE  -> ACK + 1 byte, supported buses (0x08 = SPI)
  0x10 SYNCNOP    -> NAK (0x15) + ACK (0x06)   <- this is a CORRECT answer
"""
from __future__ import unicode_literals

import re

try:
    import serial
    from serial.tools import list_ports
    HAS_SERIAL = True
except ImportError:                                    # pyserial assente
    serial = None
    list_ports = None
    HAS_SERIAL = False

ACK = 0x06
NAK = 0x15

NOP = 0x00
Q_IFACE = 0x01
Q_PGMNAME = 0x03
Q_BUSTYPE = 0x05
O_SPIOP = 0x13
S_SPI_FREQ = 0x14
S_PIN_STATE = 0x15
SYNCNOP = 0x10

# The commands sent to the chip, not to the programmer.
CMD_JEDEC = 0x9F           # three bytes: vendor, type, capacity
CMD_SFDP = 0x5A            # parameter table, when the chip has one
SFDP_SIGNATURE = b"SFDP"

# The JEDEC vendor codes you actually meet on an SPI flash.
# ⚠️ Only the certain ones: a wrong name is worse than no name, because
# it sends you looking for another chip's datasheet.
VENDORS = {
    0x01: "Spansion/Cypress", 0x04: "Fujitsu", 0x0B: "XTX", 0x1C: "EON",
    0x1F: "Atmel/Adesto", 0x20: "Micron/ST", 0x37: "AMIC", 0x4A: "ESMT",
    0x5E: "Zbit", 0x62: "SANYO", 0x68: "Boya", 0x85: "Puya",
    0x8C: "Micron", 0x9D: "ISSI", 0xA1: "Fudan", 0xAD: "Hyundai",
    0xBF: "SST", 0xC2: "Macronix", 0xC8: "GigaDevice", 0xD5: "ISSI",
    0xEF: "Winbond",
}

BUS = ((0x01, "parallelo/parallel"), (0x02, "LPC"), (0x04, "FWH"), (0x08, "SPI"))

# A Pico running pico-serprog presents TinyUSB's identity.
VID_TINYUSB = 0xCAFE
PID_TINYUSB = 0x4001
VID_RASPBERRY = 0x2E8A


# The name the programmer reports carries the version too, because it is
# the only place it fits without inventing new commands:
# "pico-serprog1.1". A bare name is not "unknown", it is a board older
# than 1.1.
_RE_VERSIONE = re.compile(r"^(.*?)[\s_-]*v?(\d+(?:\.\d+)+)$")


def split_version(name):
    """'pico-serprog1.1' -> ('pico-serprog', '1.1'). Senza versione, None."""
    if not name:
        return name, None
    hit = _RE_VERSIONE.match(name.strip())
    if not hit:
        return name.strip(), None
    return hit.group(1).strip(), hit.group(2)


def _numeri(version):
    out = []
    for chunk in (version or "").split("."):
        try:
            out.append(int(chunk))
        except ValueError:
            out.append(0)
    return out


def is_older(quella, di_questa):
    """Is the board's version older than the one we carry here?

    ⚠️ No version at all = firmware older than 1.1, so yes, it is old. That is
    precisely the case we care about.
    """
    if not di_questa:
        return False
    if not quella:
        return True
    return _numeri(quella) < _numeri(di_questa)


class Diagnostics(object):
    """L'esito dell'interrogazione."""

    def __init__(self, name=None, version=None, bus=None, error=None):
        self.name = name
        self.version = version
        self.bus = bus
        self.error = error

    @property
    def ok(self):
        return self.error is None

    @property
    def firmware(self):
        """The version the board reports, or None when it reports none."""
        return split_version(self.name)[1]

    @property
    def bare_name(self):
        return split_version(self.name)[0]

    @property
    def speaks_spi(self):
        return self.bus is not None and bool(self.bus & 0x08)

    @property
    def readable_bus(self):
        if self.bus is None:
            return "?"
        names_of = [n for bits, n in BUS if self.bus & bits]
        return "0x%02X = %s" % (self.bus, ", ".join(names_of) or "-")


def list_serial_ports():
    """[(device, description, probably_the_pico, serial)], sorted.

    ⚠️ The serial is the one the board exposes WHILE THE FIRMWARE RUNS (16
    digits): it is not the one it shows in BOOTSEL. See boards.py.
    """
    if not HAS_SERIAL:
        return []
    found = []
    for p in list_ports.comports():
        vid, pid = p.vid, p.pid
        likely = (vid == VID_TINYUSB and pid == PID_TINYUSB) or vid == VID_RASPBERRY
        description = p.description or ""
        if vid is not None and pid is not None:
            description = "%s (%04X:%04X)" % (description, vid, pid)
        found.append((p.device, description, likely,
                        (p.serial_number or "").upper() or None))
    # candidates first, then by name
    found.sort(key=lambda t: (not t[2], _chiave_com(t[0])))
    return found


def _chiave_com(name):
    cifre = "".join(c for c in name if c.isdigit())
    return (int(cifre) if cifre else 0, name)


def _chiedi(s, command, how_many):
    s.reset_input_buffer()
    s.write(bytearray([command]))
    s.flush()
    r = s.read(1)
    if not r:
        return None, "nessuna risposta / no answer"
    if r[0] != ACK:
        return None, "0x%02X invece di ACK / instead of ACK" % r[0]
    return (s.read(how_many) if how_many else b""), None


def _chiedi_con_dato(s, command, datum):
    """A command with one argument byte, answering ACK and nothing else."""
    s.reset_input_buffer()
    s.write(bytearray([command, datum]))
    s.flush()
    r = s.read(1)
    if not r:
        return None, "nessuna risposta / no answer"
    if r[0] != ACK:
        return None, "0x%02X invece di ACK / instead of ACK" % r[0]
    return b"", None


def sync(s):
    """SYNCNOP: la risposta giusta e' NAK seguito da ACK, non un errore."""
    s.reset_input_buffer()
    s.write(bytearray([SYNCNOP]))
    s.flush()
    r = s.read(2)
    if len(r) == 2 and r[0] == NAK and r[1] == ACK:
        return None
    if not r:
        return "nessuna risposta a SYNCNOP / no answer to SYNCNOP"
    size = " ".join("0x%02X" % b for b in bytearray(r))
    return "SYNCNOP ha risposto / answered %s" % size


def query(port, baud=115200, timeout=2.0):
    """Opens the port, asks who it is, closes. Does not touch the chip."""
    if not HAS_SERIAL:
        return Diagnostics(error="pyserial")
    try:
        s = serial.Serial(port, baud, timeout=timeout)
    except Exception as e:                             # noqa: BLE001 - va mostrato
        return Diagnostics(error="%s" % e)

    with s:
        s.dtr = True
        error = sync(s)
        if error:
            # Not necessarily serious: some firmware wants a NOP first.
            _, errore_nop = _chiedi(s, NOP, 0)
            if errore_nop:
                return Diagnostics(error=error)

        data, error = _chiedi(s, Q_IFACE, 2)
        if error:
            return Diagnostics(error=error)
        version = data[0] | (data[1] << 8)

        data, error = _chiedi(s, Q_PGMNAME, 16)
        name = None if error else data.rstrip(b"\x00").decode("ascii", "replace")

        data, error = _chiedi(s, Q_BUSTYPE, 1)
        bus = None if error else data[0]

    return Diagnostics(name=name or "?", version=version, bus=bus)


# ------------------------------------------------- parlare al chip, non al Pico

def _tre(number):
    """An integer over three bytes, the way serprog wants them: least
    significant first."""
    return bytearray([number & 0xFF, (number >> 8) & 0xFF, (number >> 16) & 0xFF])


def spi_transfer(s, da_inviare, to_read):
    """A raw SPI transaction through the programmer.

    ⚠️ The ACK arrives AFTER the written part and BEFORE the read bytes: that
    is how the protocol is built, not an implementation detail.
    """
    header = bytearray([O_SPIOP]) + _tre(len(da_inviare)) + _tre(to_read)
    s.reset_input_buffer()
    s.write(bytes(header) + bytes(da_inviare))
    s.flush()
    risposta = s.read(1)
    if not risposta:
        return None, "nessuna risposta / no answer"
    if risposta[0] != ACK:
        return None, "0x%02X invece di ACK / instead of ACK" % risposta[0]
    if not to_read:
        return b"", None
    read_bytes = s.read(to_read)
    if len(read_bytes) != to_read:
        return None, ("attesi %d byte, arrivati %d / expected %d bytes, got %d"
                      % (to_read, len(read_bytes), to_read, len(read_bytes)))
    return bytes(read_bytes), None


class Identity(object):
    """What the chip says about itself when asked to its face."""

    def __init__(self, vendor_id=None, kind=None, capacity=None, size=None,
                 sfdp=False, error=None):
        self.vendor_id = vendor_id      # codice JEDEC del costruttore
        self.kind = kind
        self.capacity = capacity
        self.size = size                    # dimensione, se si riesce a dirla
        self.sfdp = sfdp                    # il chip ha una tabella SFDP?
        self.error = error

    @property
    def ok(self):
        return self.error is None

    @property
    def answers(self):
        """Is there a chip attached, and does it answer?

        ⚠️ All 0x00 or all 0xFF is not a chip: it is a loose wire or a CS that
        never moves. That is the distinction that actually matters -- an
        unknown chip and a bad wire are two different problems.
        """
        if not self.ok:
            return False
        tre = (self.vendor_id, self.kind, self.capacity)
        return tre not in ((0x00, 0x00, 0x00), (0xFF, 0xFF, 0xFF))

    @property
    def vendor_name(self):
        return VENDORS.get(self.vendor_id)

    @property
    def jedec(self):
        if self.vendor_id is None:
            return None
        return "%02X %02X %02X" % (self.vendor_id, self.kind, self.capacity)

    def description(self):
        chunks = []
        if self.vendor_name:
            chunks.append(self.vendor_name)
        if self.jedec:
            chunks.append("JEDEC %s" % self.jedec)
        if self.size:
            chunks.append("%d MiB" % (self.size // (1024 * 1024))
                         if self.size >= 1024 * 1024
                         else "%d KiB" % (self.size // 1024))
        if self.sfdp:
            chunks.append("SFDP")
        return " \u00b7 ".join(chunks)


def _byte_da_capacita(capacity):
    """La dimensione dal terzo byte JEDEC: quasi sempre 2^capacita byte."""
    if capacity is None or not 0x10 <= capacity <= 0x1C:
        return None
    return 1 << capacity


def _byte_da_sfdp(s):
    """The size from the SFDP table, which is the most reliable source.

    Returns (bytes, table_present). ⚠️ A chip without SFDP is not broken: the
    older ones simply do not have one.
    """
    header, error = spi_transfer(s, bytearray([CMD_SFDP, 0, 0, 0, 0xFF]), 8)
    if error or not header or header[:4] != SFDP_SIGNATURE:
        return None, False
    count = header[6] + 1                   # numero di intestazioni parametro
    for index in range(min(count, 8)):
        position = 8 + index * 8
        entry, error = spi_transfer(
            s, bytearray([CMD_SFDP, (position >> 16) & 0xFF,
                          (position >> 8) & 0xFF, position & 0xFF, 0xFF]), 8)
        if error or not entry or entry[0] != 0x00:
            continue                        # non e' la tabella base JEDEC
        length = entry[3] * 4
        puntatore = entry[4] | (entry[5] << 8) | (entry[6] << 16)
        if length < 8:
            continue
        table, error = spi_transfer(
            s, bytearray([CMD_SFDP, (puntatore >> 16) & 0xFF,
                          (puntatore >> 8) & 0xFF, puntatore & 0xFF, 0xFF]),
            min(length, 64))
        if error or not table or len(table) < 8:
            continue
        densita = (table[4] | (table[5] << 8) | (table[6] << 16)
                   | (table[7] << 24))
        if densita & 0x80000000:
            # oltre i 2 Gbit la densita' e' un esponente, non un numero
            esponente = densita & 0x7FFFFFFF
            if esponente > 40:
                return None, True
            bits = 1 << esponente
        else:
            bits = densita + 1
        return bits // 8, True
    return None, True


def identify_chip(port, baud=115200, timeout=2.0):
    """Asks the chip for its JEDEC id and, when present, its SFDP table.

    This is for when flashrom does not recognise the chip: from here you can
    tell whether the chip answers (then it is merely unknown) or does not
    answer at all (then it is a wiring problem, not a model one).
    """
    if not HAS_SERIAL:
        return Identity(error="pyserial")
    try:
        s = serial.Serial(port, baud, timeout=timeout)
    except Exception as e:                             # noqa: BLE001
        return Identity(error="%s" % e)
    with s:
        s.dtr = True
        error = sync(s)
        if error:
            _, errore_nop = _chiedi(s, NOP, 0)
            if errore_nop:
                return Identity(error=error)
        # ⚠️ The pins have to be turned on FIRST, always. When flashrom
        # exits it sends S_PIN_STATE(0) and the programmer is left with SPI
        # off: an SPI operation in that state never returns and hangs the
        # board, USB included. It cost us a board that had to be unplugged.
        _, error = _chiedi_con_dato(s, S_PIN_STATE, 1)
        if error:
            return Identity(error=error)
        try:
            data, error = spi_transfer(s, bytearray([CMD_JEDEC]), 3)
            if error:
                return Identity(error=error)
            identity = Identity(vendor_id=data[0], kind=data[1],
                                capacity=data[2])
            if not identity.answers:
                return identity
            size, ha_sfdp = _byte_da_sfdp(s)
            identity.sfdp = ha_sfdp
            identity.size = size or _byte_da_capacita(identity.capacity)
        finally:
            # si rimette come si e' trovato: flashrom si aspetta di trovarlo
            # off, and it is flashrom that turns it back on when needed
            _chiedi_con_dato(s, S_PIN_STATE, 0)
    return identity
