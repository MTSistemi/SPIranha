# -*- coding: utf-8 -*-
"""What is inside a BIOS image, and what changes between two of them.

No chip is touched here: this reads, compares and counts. It serves three
things that used to be done by hand:

  1. the DRY RUN: work out how the flash will end up BEFORE writing it, and
     check that every changing byte falls inside the chosen region;
  2. the COMPARISON of two images, with the ranges aligned to sectors;
  3. the COHERENCE CHECK after writing: not only "the bytes match", but
     "there is still a sensible structure in there".

⚠️ The comparison works in 4 KB blocks because that is the granularity the
chip erases at: a range that is not sector-aligned cannot be written without
dragging along whatever sits around it.
"""
from __future__ import unicode_literals

import os

SETTORE = 4096
VUOTO = b"\xff"
ZERO = b"\x00"

# Signatures we can recognise in this flash, verified on the real dump
# di una BC-250 vera (BIOS P3.00): _FVH x7, NVAR x958, APCB a
# 0xAB1000, $PSP a 0x8E0000.
FIRME = (
    (b"_FVH", "fv", "volume UEFI", "UEFI firmware volume"),
    (b"NVAR", "nvar", "variabili UEFI", "UEFI variables"),
    (b"APCB", "apcb", "configurazione memoria (APCB)", "memory config (APCB)"),
    (b"$PSP", "psp", "direttorio PSP", "PSP directory"),
)


def leggi(percorso):
    with open(percorso, "rb") as f:
        return f.read()


# --------------------------------------------------------------- confronto

def blocchi_diversi(a, b, grana=SETTORE):
    """Indices of the `grana`-byte blocks where the two images differ.

    Whole slices are compared rather than byte by byte: over 16 MiB that is
    the difference between an instant and half a minute.
    """
    if len(a) != len(b):
        raise ValueError("immagini di dimensione diversa: %d e %d" % (len(a), len(b)))
    diversi = []
    for indice in range(0, (len(a) + grana - 1) // grana):
        inizio = indice * grana
        if a[inizio:inizio + grana] != b[inizio:inizio + grana]:
            diversi.append(indice)
    return diversi


def unisci(indici, grana=SETTORE, limite=None):
    """Blocchi contigui -> intervalli (inizio, fine_inclusa)."""
    intervalli = []
    for indice in indici:
        inizio, fine = indice * grana, (indice + 1) * grana - 1
        if limite is not None:
            fine = min(fine, limite - 1)
        if intervalli and intervalli[-1][1] + 1 == inizio:
            intervalli[-1] = (intervalli[-1][0], fine)
        else:
            intervalli.append((inizio, fine))
    return intervalli


def intervalli_esatti(a, b, intervalli):
    """Inside the differing blocks, the true bounds, byte by byte."""
    esatti = []
    for inizio, fine in intervalli:
        primo = ultimo = None
        for posizione in range(inizio, fine + 1):
            if a[posizione] != b[posizione]:
                if primo is None:
                    primo = posizione
                ultimo = posizione
        if primo is not None:
            esatti.append((primo, ultimo))
    return esatti


def confronta(a, b, grana=SETTORE):
    """Il confronto completo: blocchi, intervalli allineati, confini veri."""
    indici = blocchi_diversi(a, b, grana)
    allineati = unisci(indici, grana, limite=len(a))
    esatti = intervalli_esatti(a, b, allineati)
    return {
        "blocchi": indici,
        "grana": grana,
        "allineati": allineati,
        "esatti": esatti,
        "byte_diversi": sum(f - i + 1 for i, f in esatti),
        "uguali": not indici,
    }


# ---------------------------------------------------------------- struttura

def firme(dati, massimo=4000):
    """Where the known structures sit. Only the first `massimo` per signature:
    NVAR alone shows up nearly a thousand times and listing them all helps
    nobody."""
    trovate = {}
    for firma, chiave, _it, _en in FIRME:
        posizioni = []
        posizione = dati.find(firma)
        while posizione != -1 and len(posizioni) < massimo:
            posizioni.append(posizione)
            posizione = dati.find(firma, posizione + 1)
        if posizioni:
            trovate[chiave] = posizioni
    return trovate


def descrivi(inizio, fine, mappa_firme, lingua="it"):
    """What sits in this range, in words."""
    dentro = []
    for firma, chiave, testo_it, testo_en in FIRME:
        posizioni = mappa_firme.get(chiave, ())
        quante = sum(1 for p in posizioni if inizio <= p <= fine)
        if quante:
            nome = testo_it if lingua == "it" else testo_en
            dentro.append("%s%s" % (nome, " ×%d" % quante if quante > 1 else ""))
    return ", ".join(dentro)


def coerenza(dati, inizio, fine, mappa_firme=None):
    """Does the written region still have a sensible structure?

    This is not a formal validation of the firmware -- nobody can do that
    from outside -- but it catches the two states a failed write leaves the
    chip in: all 0xFF (erased and never rewritten) or all 0x00.
    """
    pezzo = dati[inizio:fine + 1]
    esiti = {
        "vuoto": pezzo == VUOTO * len(pezzo),
        "azzerato": pezzo == ZERO * len(pezzo),
        "byte": len(pezzo),
    }
    mappa_firme = mappa_firme if mappa_firme is not None else firme(dati)
    esiti["firme"] = {chiave: sum(1 for p in posizioni if inizio <= p <= fine)
                      for chiave, posizioni in mappa_firme.items()}
    esiti["ok"] = not esiti["vuoto"] and not esiti["azzerato"]
    return esiti


# ------------------------------------------------------------- prova a secco

class ProvaASecco(object):
    """The result of working out how the flash will look after the write."""

    def __init__(self):
        self.risultato = None        # bytes: l'immagine attesa
        self.md5 = None
        self.cambia = []             # intervalli (allineati) che cambiano
        self.cambia_esatti = []
        self.fuori = []              # ⚠️ intervalli che cadono FUORI dalla regione
        self.byte_cambiati = 0
        self.nulla_da_fare = False
        self.errore = None


def prova_a_secco(attuale, sorgente, regione=None, md5=None):
    """Works out the image the write will produce, without writing anything.

    `attuale`  = what is on the chip right now (the verified read)
    `sorgente` = the image to be written
    `regione`  = (start, end) when writing a single region, None for all

    The check that matters is `fuori`: if the source image differs from the
    current one ALSO outside the chosen region, those differences will NOT be
    written. That is not an error in itself -- it is the whole reason for
    writing by region -- but it has to be said, because someone who believes
    they are transferring the whole BIOS while only part of it goes across
    needs to know.
    """
    esito = ProvaASecco()
    if len(attuale) != len(sorgente):
        esito.errore = "dimensioni diverse: %d e %d" % (len(attuale), len(sorgente))
        return esito

    if regione is None:
        risultato = bytes(sorgente)
    else:
        inizio, fine = regione
        risultato = bytes(attuale[:inizio]) + bytes(sorgente[inizio:fine + 1]) \
            + bytes(attuale[fine + 1:])

    esito.risultato = risultato
    if md5 is not None:
        esito.md5 = md5(risultato)

    indici = blocchi_diversi(attuale, risultato)
    esito.cambia = unisci(indici, SETTORE, limite=len(attuale))
    esito.cambia_esatti = intervalli_esatti(attuale, risultato, esito.cambia)
    esito.byte_cambiati = sum(f - i + 1 for i, f in esito.cambia_esatti)
    esito.nulla_da_fare = not indici

    # what would be left out: differences between current and source outside
    # the region, which the write would not carry over
    if regione is not None:
        inizio, fine = regione
        tutti = unisci(blocchi_diversi(attuale, sorgente), SETTORE,
                       limite=len(attuale))
        esito.fuori = [(a, b) for a, b in tutti if b < inizio or a > fine]
    return esito


# --------------------------------------------------------- layout generato

def genera_layout(intervalli, dimensione, nome="modificata"):
    """A flashrom layout file that isolates the given ranges.

    It covers the whole flash: flashrom accepts partial layouts too, but a
    complete one makes it obvious what is NOT being written.
    ⚠️ No comments in the file: flashrom's parser rejects them.
    """
    righe = []
    posizione = 0
    contatore = 0
    for inizio, fine in sorted(intervalli):
        if inizio > posizione:
            righe.append((posizione, inizio - 1, "salta%d" % contatore))
            contatore += 1
        etichetta = nome if len(intervalli) == 1 else "%s%d" % (nome, contatore)
        righe.append((inizio, fine, etichetta))
        contatore += 1
        posizione = fine + 1
    if posizione < dimensione:
        righe.append((posizione, dimensione - 1, "salta%d" % contatore))
    return "".join("%08x:%08x %s\n" % (a, b, n) for a, b, n in righe)


def allineato(inizio, fine, grana=SETTORE):
    return inizio % grana == 0 and (fine + 1) % grana == 0


# ------------------------------------------------------------------ comodo

def leggibile(byte):
    """Dimensione a misura d'uomo."""
    for unita, soglia in (("MiB", 1024 * 1024), ("KiB", 1024)):
        if byte >= soglia:
            valore = byte / float(soglia)
            return ("%.0f %s" if valore >= 100 else "%.1f %s") % (valore, unita)
    return "%d B" % byte


def nome_file(percorso):
    return os.path.basename(percorso) if percorso else ""
