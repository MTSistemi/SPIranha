# -*- coding: utf-8 -*-
"""Cosa c'e' dentro un'immagine di BIOS, e cosa cambia fra due.

Qui non si tocca nessun chip: si legge, si confronta, si conta. Serve a tre
cose che prima si facevano a mano:

  1. la PROVA A SECCO: calcolare come verra' la flash PRIMA di scriverla, e
     controllare che i byte che cambiano stiano tutti dentro la regione scelta;
  2. il CONFRONTO fra due immagini, con gli intervalli allineati ai settori;
  3. la VERIFICA DI COERENZA dopo la scrittura: non solo «i byte tornano», ma
     «li' dentro c'e' ancora una struttura sensata».

⚠️ Il confronto lavora a blocchi di 4 KB perche' e' la grana con cui il chip si
cancella: un intervallo che non e' allineato al settore non si puo' scrivere
senza portarsi dietro cio' che gli sta intorno.
"""
from __future__ import unicode_literals

import os

SETTORE = 4096
VUOTO = b"\xff"
ZERO = b"\x00"

# Firme che sappiamo riconoscere in questa flash, verificate sul dump vero
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
    """Indici dei blocchi da `grana` byte in cui le due immagini differiscono.

    Si confrontano fette intere invece che byte per byte: su 16 MiB e' la
    differenza fra un istante e mezzo minuto.
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
    """Dentro i blocchi che differiscono, i confini veri byte per byte."""
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
    """Dove stanno le strutture note. Solo le prime `massimo` per firma:
    NVAR da solo compare quasi mille volte e non serve elencarle tutte."""
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
    """Che cosa sta in questo intervallo, a parole."""
    dentro = []
    for firma, chiave, testo_it, testo_en in FIRME:
        posizioni = mappa_firme.get(chiave, ())
        quante = sum(1 for p in posizioni if inizio <= p <= fine)
        if quante:
            nome = testo_it if lingua == "it" else testo_en
            dentro.append("%s%s" % (nome, " ×%d" % quante if quante > 1 else ""))
    return ", ".join(dentro)


def coerenza(dati, inizio, fine, mappa_firme=None):
    """La regione scritta ha ancora una struttura sensata?

    Non e' una validazione formale del firmware — quella non la sa fare
    nessuno da fuori — ma intercetta i due modi in cui una scrittura fallita
    lascia il chip: tutto 0xFF (cancellato e mai riscritto) o tutto 0x00.
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
    """L'esito del calcolo di come verra' la flash dopo la scrittura."""

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
    """Calcola l'immagine che risultera' dalla scrittura, senza scrivere.

    `attuale`  = quello che c'e' adesso sul chip (la lettura verificata)
    `sorgente` = l'immagine da scrivere
    `regione`  = (inizio, fine) se si scrive una regione sola, None se tutto

    Il controllo che conta e' `fuori`: se l'immagine sorgente differisce
    dall'attuale ANCHE fuori dalla regione scelta, quelle differenze NON
    verranno scritte. Non e' un errore di per se' — e' anzi il motivo per cui
    si scrive per regioni — ma va detto, perche' se uno crede di star
    trasferendo tutto il BIOS e invece ne passa un pezzo, deve saperlo.
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

    # cosa resterebbe fuori: differenze fra attuale e sorgente al di fuori
    # della regione, che la scrittura non porterebbe
    if regione is not None:
        inizio, fine = regione
        tutti = unisci(blocchi_diversi(attuale, sorgente), SETTORE,
                       limite=len(attuale))
        esito.fuori = [(a, b) for a, b in tutti if b < inizio or a > fine]
    return esito


# --------------------------------------------------------- layout generato

def genera_layout(intervalli, dimensione, nome="modificata"):
    """Un file di layout per flashrom che isola gli intervalli dati.

    Copre tutta la flash: flashrom accetta anche layout parziali, ma averli
    completi rende evidente cosa NON si sta scrivendo.
    ⚠️ Niente commenti nel file: il parser di flashrom li rifiuta.
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
