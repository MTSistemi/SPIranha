# -*- coding: utf-8 -*-
"""L'RP2040 come programmatore: riconoscerlo, programmarlo, riportarlo a nuovo.

Una scheda RP2040 tenuta premuto BOOTSEL mentre la si attacca si presenta come
un disco rimovibile chiamato RPI-RP2, con dentro INFO_UF2.TXT. Ci si copia
sopra un file .uf2 e la scheda si programma da sola e riparte. Non serve nessun
strumento esterno: e' il bootloader in ROM che fa tutto.

Qui dentro:
  - si trovano le schede in BOOTSEL guardando le unita' rimovibili;
  - si installa il firmware copiandoci il .uf2;
  - si genera un .uf2 che RIPORTA LA SCHEDA A NUOVO.

⚠️ SUL «TORNARE A NUOVO». Non serve scaricare il flash_nuke di nessuno: il
bootloader, prima di scrivere un settore, lo CANCELLA. Un .uf2 che scrive 0xFF
su tutta la flash quindi la lascia cancellata, che e' lo stato di fabbrica —
senza seconda fase di avvio valida la scheda torna in BOOTSEL da sola. Il file
lo generiamo noi, byte per byte, e cosi' non c'e' nessun binario di ignoti in
mezzo.

Formato UF2 (blocchi da 512 byte, 256 di carico utile):
    0  magia 0x0A324655 "UF2\\n"
    4  magia 0x9E5D5157
    8  bandiere            0x2000 = c'e' l'identificativo di famiglia
   12  indirizzo di destinazione
   16  byte di carico utile (256)
   20  numero del blocco
   24  quanti blocchi in tutto
   28  identificativo di famiglia (RP2040 = 0xE48BFF56)
   32  dati (476 byte, i primi 256 usati)
  508  magia finale 0x0AB16F30
"""
from __future__ import unicode_literals

import ctypes
import os
import shutil
import struct

MAGIA0 = 0x0A324655
MAGIA1 = 0x9E5D5157
MAGIA_FINE = 0x0AB16F30
BANDIERA_FAMIGLIA = 0x00002000
FAMIGLIA_RP2040 = 0xE48BFF56

BLOCCO = 512
CARICO = 256
BASE_FLASH = 0x10000000
FLASH_PICO = 2 * 1024 * 1024        # il Pico originale ne ha 2 MiB

ETICHETTA = "RPI-RP2"
NOME_FIRMWARE = "pico_serprog.uf2"
INFORMAZIONI = "INFO_UF2.TXT"
DRIVE_REMOVIBILE = 2


class Scheda(object):
    """Una scheda RP2040 in BOOTSEL, vista come disco."""

    def __init__(self, unita, modello=None, identificativo=None, byte_liberi=0):
        self.unita = unita                      # "E:\\"
        self.modello = modello or "RP2040"
        self.identificativo = identificativo or "?"
        self.byte_liberi = byte_liberi

    @property
    def lettera(self):
        return self.unita[:2]

    def __repr__(self):
        return "<Scheda %s %s>" % (self.lettera, self.modello)


# ------------------------------------------------------------ ricerca

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
    """INFO_UF2.TXT -> (modello, identificativo). Il file e' due righe."""
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
    """Questa scheda si dichiara un RP2040?

    ⚠️ Il Board-ID vero e' "RPI-RP2", non "RP2...": si cerca RP2 DENTRO la
    stringa. La prima versione pretendeva che cominciasse per RP2 e non
    riconosceva nessuna scheda — se ne e' accorto solo l'hardware.
    """
    return "RP2" in ("%s %s" % (identificativo or "", modello or "")).upper()


def schede_in_bootsel():
    """Le schede RP2040 in attesa di firmware, adesso."""
    trovate = []
    for unita in _unita_rimovibili():
        informazioni = os.path.join(unita, INFORMAZIONI)
        if not os.path.isfile(informazioni):
            continue
        modello, identificativo = _leggi_informazioni(informazioni)
        # su un disco qualunque una copia sbagliata non farebbe danni, ma
        # nemmeno bene
        if not e_rp2040(modello, identificativo):
            continue
        liberi = 0
        try:
            liberi = shutil.disk_usage(unita).free
        except OSError:
            pass
        trovate.append(Scheda(unita, modello, identificativo, liberi))
    return trovate


# ------------------------------------------------------------ formato UF2

def blocco_uf2(indirizzo, dati, numero, totale, famiglia=FAMIGLIA_RP2040):
    """Un blocco da 512 byte, come lo vuole il bootloader."""
    if len(dati) > CARICO:
        raise ValueError("carico utile troppo grande: %d" % len(dati))
    testa = struct.pack("<IIIIIIII", MAGIA0, MAGIA1, BANDIERA_FAMIGLIA,
                        indirizzo, CARICO, numero, totale, famiglia)
    corpo = dati + b"\x00" * (476 - len(dati))
    return testa + corpo + struct.pack("<I", MAGIA_FINE)


def leggi_uf2(percorso):
    """Controlla un .uf2 e ne racconta il contenuto.

    Restituisce (blocchi, primo_indirizzo, ultimo_indirizzo, famiglie).
    Solleva ValueError se il file non e' un UF2 valido: e' il controllo che si
    fa PRIMA di copiarlo su una scheda.
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
    """Scrive un .uf2 che riporta la scheda allo stato di fabbrica.

    Scrive 0xFF su tutta la flash: siccome il bootloader cancella il settore
    prima di scriverlo, il risultato e' una flash cancellata. Senza seconda
    fase di avvio valida, alla riaccensione la scheda torna in BOOTSEL.
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


# ------------------------------------------------------------ installazione

def installa(percorso_uf2, scheda, su_riga=None):
    """Copia il firmware sulla scheda. Restituisce (fatto, motivo).

    ⚠️ Non si verifica rileggendo: appena il bootloader ha finito, la scheda si
    stacca e riparte, quindi la copia «fallisce» in coda ed e' NORMALE. La
    verifica vera e' che dopo ricompaia come porta seriale.
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
    try:
        with open(percorso_uf2, "rb") as sorgente:
            with open(destinazione, "wb") as uscita:
                shutil.copyfileobj(sorgente, uscita, 64 * 1024)
                try:
                    uscita.flush()
                    os.fsync(uscita.fileno())
                except OSError:
                    pass          # la scheda si e' gia' staccata: va bene cosi'
    except OSError as e:
        # ⚠️ Errori in chiusura sono attesi: il disco sparisce sotto i piedi
        # nel momento in cui il bootloader ha finito di ricevere.
        dillo("la scheda si e' staccata durante la copia (e' normale): %s" % e)
        return True, None
    return True, None
