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

# quante volte riprovare una copia che non riesce nemmeno a cominciare
TENTATIVI_COPIA = 6
FLASH_PICO = 2 * 1024 * 1024        # il Pico originale ne ha 2 MiB

BAUD_BOOTSEL = 1200                 # aprire a questa velocita' = torna in BOOTSEL
SENZA_FINESTRA = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
ETICHETTA = "RPI-RP2"
NOME_FIRMWARE = "pico_serprog.uf2"
INFORMAZIONI = "INFO_UF2.TXT"
DRIVE_REMOVIBILE = 2


class Scheda(object):
    """Una scheda RP2040 in BOOTSEL, vista come disco."""

    def __init__(self, unita, modello=None, identificativo=None, byte_liberi=0,
                 seriale=None):
        self.unita = unita                      # "E:\\"
        self.modello = modello or "RP2040"
        self.identificativo = identificativo or "?"
        self.byte_liberi = byte_liberi
        # ⚠️ Questo NON e' il numero di serie che la stessa scheda mostra
        # quando gira il firmware: il bootloader ne espone uno suo, piu' corto.
        # Verificato sulla stessa scheda: 12 cifre qui, 16 di la'.
        self.seriale = seriale

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
        trovate.append(Scheda(unita, modello, identificativo, liberi,
                              seriale=seriale_di_unita(unita)))
    return trovate


# il seriale che il bootloader espone e' dentro il percorso del dispositivo:
#   USBSTOR\DISK&VEN_RPI&PROD_RP2&REV_3\9&25F25AF4&0&E0C9125B0D9B&0
_RE_SERIALE = re.compile(r"&([0-9A-F]{8,20})&\d+$", re.IGNORECASE)
_CACHE_SERIALI = {}


def seriale_di_unita(unita):
    """Il numero di serie della scheda in BOOTSEL, dalla lettera di unita'.

    ⚠️ Costa una chiamata a PowerShell, quindi il risultato si tiene da parte:
    la sorveglianza guarda le unita' ogni due secondi e non puo' pagarla ogni
    volta. Una lettera di unita' non cambia scheda sotto i piedi senza che la
    scheda sparisca prima, e in quel caso la voce viene ributtata via.
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
    """Da chiamare quando una scheda se ne va: la lettera potrebbe tornare
    addosso a un'altra."""
    _CACHE_SERIALI.clear()


# ------------------------------------------------------------ formato UF2

def versione_disponibile(cartella):
    """La versione dell'UF2 che spediamo, dal file VERSION accanto."""
    try:
        percorso = os.path.join(cartella, "VERSION")
        with io.open(percorso, encoding="utf-8") as f:
            versione = f.read().strip()
        return versione or None
    except Exception:                                  # noqa: BLE001
        return None


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


# ------------------------------------------------- rientro nel bootloader

def rientra_in_bootsel(porta):
    """Chiede al firmware di riavviarsi nel bootloader ROM.

    Si apre la porta a 1200 baud: e' la convenzione dell'Arduino Leonardo, e
    il nostro pico-serprog la implementa (vedi firmware/). Funziona SOLO con il
    firmware nostro dalla 1.2 in poi; con quello di prima non succede niente e
    il pulsante BOOTSEL resta l'unica strada.

    ⚠️ L'apertura della porta di solito FALLISCE, e va bene cosi': la scheda si
    riavvia e sparisce mentre il sistema sta ancora configurando la porta. E'
    il segno che ha funzionato, non un errore. Chi chiama deve verificare
    guardando se la scheda ricompare in BOOTSEL, non l'esito di questa.
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
    # ⚠️ Un errore a copia iniziata e un errore PRIMA di scrivere un byte
    # sembrano uguali (sono entrambi OSError) e non lo sono affatto: il primo
    # e' la scheda che riparte, il secondo e' una copia mai avvenuta. A
    # confonderli si dice "fatto" a un firmware che non e' stato scritto.
    # Succede sul serio: una scheda appena entrata in BOOTSEL risponde
    # "Permission denied" finche' Windows non ha finito di montare il disco.
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
                # il disco sparisce sotto i piedi appena il bootloader ha
                # ricevuto tutto: questo e' l'andamento normale
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
