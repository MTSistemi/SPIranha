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
    SERIALE = True
except ImportError:                                    # pyserial assente
    serial = None
    list_ports = None
    SERIALE = False

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
FIRMA_SFDP = b"SFDP"

# The JEDEC vendor codes you actually meet on an SPI flash.
# ⚠️ Only the certain ones: a wrong name is worse than no name, because
# it sends you looking for another chip's datasheet.
COSTRUTTORI = {
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


def separa_versione(nome):
    """'pico-serprog1.1' -> ('pico-serprog', '1.1'). Senza versione, None."""
    if not nome:
        return nome, None
    trovato = _RE_VERSIONE.match(nome.strip())
    if not trovato:
        return nome.strip(), None
    return trovato.group(1).strip(), trovato.group(2)


def _numeri(versione):
    fuori = []
    for pezzo in (versione or "").split("."):
        try:
            fuori.append(int(pezzo))
        except ValueError:
            fuori.append(0)
    return fuori


def piu_vecchia(quella, di_questa):
    """Is the board's version older than the one we carry here?

    ⚠️ No version at all = firmware older than 1.1, so yes, it is old. That is
    precisely the case we care about.
    """
    if not di_questa:
        return False
    if not quella:
        return True
    return _numeri(quella) < _numeri(di_questa)


class Diagnostica(object):
    """L'esito dell'interrogazione."""

    def __init__(self, nome=None, versione=None, bus=None, errore=None):
        self.nome = nome
        self.versione = versione
        self.bus = bus
        self.errore = errore

    @property
    def ok(self):
        return self.errore is None

    @property
    def firmware(self):
        """The version the board reports, or None when it reports none."""
        return separa_versione(self.nome)[1]

    @property
    def nome_nudo(self):
        return separa_versione(self.nome)[0]

    @property
    def parla_spi(self):
        return self.bus is not None and bool(self.bus & 0x08)

    @property
    def bus_leggibile(self):
        if self.bus is None:
            return "?"
        nomi = [n for bit, n in BUS if self.bus & bit]
        return "0x%02X = %s" % (self.bus, ", ".join(nomi) or "-")


def elenca_porte():
    """[(device, description, probably_the_pico, serial)], sorted.

    ⚠️ The serial is the one the board exposes WHILE THE FIRMWARE RUNS (16
    digits): it is not the one it shows in BOOTSEL. See boards.py.
    """
    if not SERIALE:
        return []
    trovate = []
    for p in list_ports.comports():
        vid, pid = p.vid, p.pid
        sospetto = (vid == VID_TINYUSB and pid == PID_TINYUSB) or vid == VID_RASPBERRY
        descrizione = p.description or ""
        if vid is not None and pid is not None:
            descrizione = "%s (%04X:%04X)" % (descrizione, vid, pid)
        trovate.append((p.device, descrizione, sospetto,
                        (p.serial_number or "").upper() or None))
    # candidates first, then by name
    trovate.sort(key=lambda t: (not t[2], _chiave_com(t[0])))
    return trovate


def _chiave_com(nome):
    cifre = "".join(c for c in nome if c.isdigit())
    return (int(cifre) if cifre else 0, nome)


def _chiedi(s, comando, quanti):
    s.reset_input_buffer()
    s.write(bytearray([comando]))
    s.flush()
    r = s.read(1)
    if not r:
        return None, "nessuna risposta / no answer"
    if r[0] != ACK:
        return None, "0x%02X invece di ACK / instead of ACK" % r[0]
    return (s.read(quanti) if quanti else b""), None


def _chiedi_con_dato(s, comando, dato):
    """A command with one argument byte, answering ACK and nothing else."""
    s.reset_input_buffer()
    s.write(bytearray([comando, dato]))
    s.flush()
    r = s.read(1)
    if not r:
        return None, "nessuna risposta / no answer"
    if r[0] != ACK:
        return None, "0x%02X invece di ACK / instead of ACK" % r[0]
    return b"", None


def sincronizza(s):
    """SYNCNOP: la risposta giusta e' NAK seguito da ACK, non un errore."""
    s.reset_input_buffer()
    s.write(bytearray([SYNCNOP]))
    s.flush()
    r = s.read(2)
    if len(r) == 2 and r[0] == NAK and r[1] == ACK:
        return None
    if not r:
        return "nessuna risposta a SYNCNOP / no answer to SYNCNOP"
    byte = " ".join("0x%02X" % b for b in bytearray(r))
    return "SYNCNOP ha risposto / answered %s" % byte


def interroga(porta, baud=115200, timeout=2.0):
    """Opens the port, asks who it is, closes. Does not touch the chip."""
    if not SERIALE:
        return Diagnostica(errore="pyserial")
    try:
        s = serial.Serial(porta, baud, timeout=timeout)
    except Exception as e:                             # noqa: BLE001 - va mostrato
        return Diagnostica(errore="%s" % e)

    with s:
        s.dtr = True
        errore = sincronizza(s)
        if errore:
            # Not necessarily serious: some firmware wants a NOP first.
            _, errore_nop = _chiedi(s, NOP, 0)
            if errore_nop:
                return Diagnostica(errore=errore)

        dati, errore = _chiedi(s, Q_IFACE, 2)
        if errore:
            return Diagnostica(errore=errore)
        versione = dati[0] | (dati[1] << 8)

        dati, errore = _chiedi(s, Q_PGMNAME, 16)
        nome = None if errore else dati.rstrip(b"\x00").decode("ascii", "replace")

        dati, errore = _chiedi(s, Q_BUSTYPE, 1)
        bus = None if errore else dati[0]

    return Diagnostica(nome=nome or "?", versione=versione, bus=bus)


# ------------------------------------------------- parlare al chip, non al Pico

def _tre(numero):
    """An integer over three bytes, the way serprog wants them: least
    significant first."""
    return bytearray([numero & 0xFF, (numero >> 8) & 0xFF, (numero >> 16) & 0xFF])


def operazione_spi(s, da_inviare, quanti_leggere):
    """A raw SPI transaction through the programmer.

    ⚠️ The ACK arrives AFTER the written part and BEFORE the read bytes: that
    is how the protocol is built, not an implementation detail.
    """
    testa = bytearray([O_SPIOP]) + _tre(len(da_inviare)) + _tre(quanti_leggere)
    s.reset_input_buffer()
    s.write(bytes(testa) + bytes(da_inviare))
    s.flush()
    risposta = s.read(1)
    if not risposta:
        return None, "nessuna risposta / no answer"
    if risposta[0] != ACK:
        return None, "0x%02X invece di ACK / instead of ACK" % risposta[0]
    if not quanti_leggere:
        return b"", None
    letti = s.read(quanti_leggere)
    if len(letti) != quanti_leggere:
        return None, ("attesi %d byte, arrivati %d / expected %d bytes, got %d"
                      % (quanti_leggere, len(letti), quanti_leggere, len(letti)))
    return bytes(letti), None


class Identita(object):
    """What the chip says about itself when asked to its face."""

    def __init__(self, costruttore=None, tipo=None, capacita=None, byte=None,
                 sfdp=False, errore=None):
        self.costruttore = costruttore      # codice JEDEC del costruttore
        self.tipo = tipo
        self.capacita = capacita
        self.byte = byte                    # dimensione, se si riesce a dirla
        self.sfdp = sfdp                    # il chip ha una tabella SFDP?
        self.errore = errore

    @property
    def ok(self):
        return self.errore is None

    @property
    def risponde(self):
        """Is there a chip attached, and does it answer?

        ⚠️ All 0x00 or all 0xFF is not a chip: it is a loose wire or a CS that
        never moves. That is the distinction that actually matters -- an
        unknown chip and a bad wire are two different problems.
        """
        if not self.ok:
            return False
        tre = (self.costruttore, self.tipo, self.capacita)
        return tre not in ((0x00, 0x00, 0x00), (0xFF, 0xFF, 0xFF))

    @property
    def nome_costruttore(self):
        return COSTRUTTORI.get(self.costruttore)

    @property
    def jedec(self):
        if self.costruttore is None:
            return None
        return "%02X %02X %02X" % (self.costruttore, self.tipo, self.capacita)

    def descrizione(self):
        pezzi = []
        if self.nome_costruttore:
            pezzi.append(self.nome_costruttore)
        if self.jedec:
            pezzi.append("JEDEC %s" % self.jedec)
        if self.byte:
            pezzi.append("%d MiB" % (self.byte // (1024 * 1024))
                         if self.byte >= 1024 * 1024
                         else "%d KiB" % (self.byte // 1024))
        if self.sfdp:
            pezzi.append("SFDP")
        return " \u00b7 ".join(pezzi)


def _byte_da_capacita(capacita):
    """La dimensione dal terzo byte JEDEC: quasi sempre 2^capacita byte."""
    if capacita is None or not 0x10 <= capacita <= 0x1C:
        return None
    return 1 << capacita


def _byte_da_sfdp(s):
    """The size from the SFDP table, which is the most reliable source.

    Returns (bytes, table_present). ⚠️ A chip without SFDP is not broken: the
    older ones simply do not have one.
    """
    testa, errore = operazione_spi(s, bytearray([CMD_SFDP, 0, 0, 0, 0xFF]), 8)
    if errore or not testa or testa[:4] != FIRMA_SFDP:
        return None, False
    quante = testa[6] + 1                   # numero di intestazioni parametro
    for indice in range(min(quante, 8)):
        posizione = 8 + indice * 8
        voce, errore = operazione_spi(
            s, bytearray([CMD_SFDP, (posizione >> 16) & 0xFF,
                          (posizione >> 8) & 0xFF, posizione & 0xFF, 0xFF]), 8)
        if errore or not voce or voce[0] != 0x00:
            continue                        # non e' la tabella base JEDEC
        lunghezza = voce[3] * 4
        puntatore = voce[4] | (voce[5] << 8) | (voce[6] << 16)
        if lunghezza < 8:
            continue
        tabella, errore = operazione_spi(
            s, bytearray([CMD_SFDP, (puntatore >> 16) & 0xFF,
                          (puntatore >> 8) & 0xFF, puntatore & 0xFF, 0xFF]),
            min(lunghezza, 64))
        if errore or not tabella or len(tabella) < 8:
            continue
        densita = (tabella[4] | (tabella[5] << 8) | (tabella[6] << 16)
                   | (tabella[7] << 24))
        if densita & 0x80000000:
            # oltre i 2 Gbit la densita' e' un esponente, non un numero
            esponente = densita & 0x7FFFFFFF
            if esponente > 40:
                return None, True
            bit = 1 << esponente
        else:
            bit = densita + 1
        return bit // 8, True
    return None, True


def identifica_chip(porta, baud=115200, timeout=2.0):
    """Asks the chip for its JEDEC id and, when present, its SFDP table.

    This is for when flashrom does not recognise the chip: from here you can
    tell whether the chip answers (then it is merely unknown) or does not
    answer at all (then it is a wiring problem, not a model one).
    """
    if not SERIALE:
        return Identita(errore="pyserial")
    try:
        s = serial.Serial(porta, baud, timeout=timeout)
    except Exception as e:                             # noqa: BLE001
        return Identita(errore="%s" % e)
    with s:
        s.dtr = True
        errore = sincronizza(s)
        if errore:
            _, errore_nop = _chiedi(s, NOP, 0)
            if errore_nop:
                return Identita(errore=errore)
        # ⚠️ The pins have to be turned on FIRST, always. When flashrom
        # exits it sends S_PIN_STATE(0) and the programmer is left with SPI
        # off: an SPI operation in that state never returns and hangs the
        # board, USB included. It cost us a board that had to be unplugged.
        _, errore = _chiedi_con_dato(s, S_PIN_STATE, 1)
        if errore:
            return Identita(errore=errore)
        try:
            dati, errore = operazione_spi(s, bytearray([CMD_JEDEC]), 3)
            if errore:
                return Identita(errore=errore)
            identita = Identita(costruttore=dati[0], tipo=dati[1],
                                capacita=dati[2])
            if not identita.risponde:
                return identita
            byte, ha_sfdp = _byte_da_sfdp(s)
            identita.sfdp = ha_sfdp
            identita.byte = byte or _byte_da_capacita(identita.capacita)
        finally:
            # si rimette come si e' trovato: flashrom si aspetta di trovarlo
            # off, and it is flashrom that turns it back on when needed
            _chiedi_con_dato(s, S_PIN_STATE, 0)
    return identita
