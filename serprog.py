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

# I comandi che si mandano al chip, non al programmatore.
CMD_JEDEC = 0x9F           # tre byte: costruttore, tipo, capacita\u0027
CMD_SFDP = 0x5A            # tabella dei parametri, se il chip ce l\u0027ha
FIRMA_SFDP = b"SFDP"

# I codici JEDEC dei costruttori che si incontrano davvero su una flash SPI.
# ⚠️ Solo quelli sicuri: un nome sbagliato e\u0027 peggio di nessun nome, perche\u0027
# porta a cercare la scheda tecnica di un altro chip.
COSTRUTTORI = {
    0x01: "Spansion/Cypress", 0x04: "Fujitsu", 0x0B: "XTX", 0x1C: "EON",
    0x1F: "Atmel/Adesto", 0x20: "Micron/ST", 0x37: "AMIC", 0x4A: "ESMT",
    0x5E: "Zbit", 0x62: "SANYO", 0x68: "Boya", 0x85: "Puya",
    0x8C: "Micron", 0x9D: "ISSI", 0xA1: "Fudan", 0xAD: "Hyundai",
    0xBF: "SST", 0xC2: "Macronix", 0xC8: "GigaDevice", 0xD5: "ISSI",
    0xEF: "Winbond",
}

BUS = ((0x01, "parallelo/parallel"), (0x02, "LPC"), (0x04, "FWH"), (0x08, "SPI"))

# Il Pico con pico-serprog si presenta con l'identita' di TinyUSB.
VID_TINYUSB = 0xCAFE
PID_TINYUSB = 0x4001
VID_RASPBERRY = 0x2E8A


# Il nome che il programmatore dichiara porta anche la versione, perche' e'
# l'unico posto dove ci sta senza inventare comandi nuovi: "pico-serprog1.1".
# Un nome nudo non e' "sconosciuto", e' una scheda anteriore alla 1.1.
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
    """La versione della scheda e' anteriore a quella che abbiamo qui?

    ⚠️ Nessuna versione = firmware anteriore alla 1.1, quindi si', e'
    vecchio. E' proprio il caso che interessa.
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
        """La versione che la scheda dichiara, o None se non ne dichiara."""
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
    """[(dispositivo, descrizione, e_probabilmente_il_pico, seriale)] ordinate.

    ⚠️ Il seriale e' quello che la scheda espone MENTRE GIRA il firmware (16
    cifre): non e' lo stesso che mostra in BOOTSEL. Vedi boards.py.
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


def _chiedi_con_dato(s, comando, dato):
    """Un comando con un byte di argomento, che risponde solo ACK."""
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


# ------------------------------------------------- parlare al chip, non al Pico

def _tre(numero):
    """Un intero su tre byte, come li vuole serprog: il meno pesante prima."""
    return bytearray([numero & 0xFF, (numero >> 8) & 0xFF, (numero >> 16) & 0xFF])


def operazione_spi(s, da_inviare, quanti_leggere):
    """Una transazione SPI grezza attraverso il programmatore.

    ⚠️ L'ACK arriva DOPO la parte scritta e PRIMA dei byte letti: e' come e'
    fatto il protocollo, non un dettaglio implementativo.
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
    """Quello che il chip dice di se' quando glielo si chiede in faccia."""

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
        """C'e' un chip attaccato che risponde?

        ⚠️ Tutto 0x00 o tutto 0xFF non e' un chip: e' un filo staccato o un
        CS che non si muove. E' la distinzione che serve davvero -- chip
        sconosciuto o cavo storto sono due problemi diversi.
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
    """La dimensione dalla tabella SFDP, che e' la fonte piu' attendibile.

    Restituisce (byte, c_e_la_tabella). ⚠️ Un chip senza SFDP non e' rotto:
    i piu' vecchi non ce l'hanno proprio.
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
    """Chiede al chip il suo codice JEDEC e, se c'e', la tabella SFDP.

    Serve quando flashrom non riconosce il chip: da qui si capisce se il chip
    risponde (e allora e' solo sconosciuto) oppure se non risponde affatto (e
    allora e' un problema di collegamenti, non di modello).
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
        # ⚠️ I piedini vanno accesi PRIMA, sempre. flashrom, quando finisce,
        # manda S_PIN_STATE(0) e il programmatore resta con l'SPI spento: una
        # operazione SPI in quello stato non torna piu' indietro e blocca la
        # scheda, USB compreso. Costata una scheda da staccare e riattaccare.
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
            # spento, ed e' lui a riaccenderlo quando gli serve
            _chiedi_con_dato(s, S_PIN_STATE, 0)
    return identita
