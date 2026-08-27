# -*- coding: utf-8 -*-
"""Parla col Pico nel protocollo serprog, prima di passarlo a flashrom.

A che serve, visto che poi tocca a flashrom: presentarsi come porta seriale non
vuol dire niente, qualunque firmware sbagliato lo farebbe. Qui gli si chiede chi
e' e cosa sa fare, cosi' se il Pico ha il firmware sbagliato lo si scopre subito
e non in mezzo a una scrittura.

⚠️ La porta seriale la puo' tenere aperta un processo solo: questo modulo apre,
chiede e chiude. Mentre gira flashrom qui non si tocca niente.

Comandi usati (specifica serprog):
  0x00 NOP        -> ACK
  0x01 Q_IFACE    -> ACK + 2 byte, versione (deve essere 1)
  0x03 Q_PGMNAME  -> ACK + 16 byte, nome del programmatore
  0x05 Q_BUSTYPE  -> ACK + 1 byte, bus supportati (0x08 = SPI)
  0x10 SYNCNOP    -> NAK (0x15) + ACK (0x06)   <- e' una risposta CORRETTA
"""
from __future__ import unicode_literals

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
SYNCNOP = 0x10

BUS = ((0x01, "parallelo/parallel"), (0x02, "LPC"), (0x04, "FWH"), (0x08, "SPI"))

# Il Pico con pico-serprog si presenta con l'identita' di TinyUSB.
VID_TINYUSB = 0xCAFE
PID_TINYUSB = 0x4001
VID_RASPBERRY = 0x2E8A


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
    def parla_spi(self):
        return self.bus is not None and bool(self.bus & 0x08)

    @property
    def bus_leggibile(self):
        if self.bus is None:
            return "?"
        nomi = [n for bit, n in BUS if self.bus & bit]
        return "0x%02X = %s" % (self.bus, ", ".join(nomi) or "-")


def elenca_porte():
    """[(dispositivo, descrizione, e_probabilmente_il_pico, seriale)] ordinate.

    ⚠️ Il seriale e' quello che la scheda espone MENTRE GIRA il firmware (16
    cifre): non e' lo stesso che mostra in BOOTSEL. Vedi anagrafica.py.
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
    # prima i candidati, poi in ordine di nome
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
    """Apre la porta, chiede chi e', chiude. Non tocca il chip."""
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
            # Non e' detto sia grave: qualche firmware vuole prima un NOP.
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
