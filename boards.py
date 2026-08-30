# -*- coding: utf-8 -*-
"""Dare un nome alle schede, e riconoscerle la volta dopo.

⚠️ IL PUNTO DELICATO: una scheda RP2040 ha DUE identificativi diversi, e non si
somigliano nemmeno.
  - mentre gira il firmware si presenta come porta seriale, e il suo numero di
    serie USB e' l'identificativo unico della flash: 16 cifre esadecimali,
    p.es. 5303284738DE6E1C;
  - tenuta in BOOTSEL si presenta come disco, e li' il bootloader ne espone uno
    DIVERSO, di 12 cifre: p.es. E0C9125B0D9B.
Verificato sulla stessa scheda: non c'e' modo di ricavare l'uno dall'altro.

Quindi una scheda qui e' una coppia (seriale in esecuzione, seriale in
BOOTSEL), e i due lati si imparano da soli: quando si programma una scheda che
era in BOOTSEL e subito dopo compare una porta nuova, quella porta E' quella
scheda. Idem al contrario, quando la si rimanda in BOOTSEL.
"""
from __future__ import unicode_literals


class Anagrafica(object):
    """Le schede conosciute. Si salva dentro la configurazione."""

    def __init__(self, elenco=None):
        # ogni voce: {"nome": str, "run": str|None, "boot": str|None}
        self.schede = [dict(v) for v in (elenco or [])]

    # ------------------------------------------------------------ ricerca
    def _trova(self, run=None, boot=None):
        for voce in self.schede:
            if run and voce.get("run") == run:
                return voce
            if boot and voce.get("boot") == boot:
                return voce
        return None

    def nome(self, run=None, boot=None):
        voce = self._trova(run, boot)
        return (voce or {}).get("nome") or None

    def voce(self, run=None, boot=None):
        return self._trova(run, boot)

    # ------------------------------------------------------------ modifica
    def imposta_nome(self, nome, run=None, boot=None):
        """Battezza una scheda. Un nome vuoto la dimentica."""
        if not (run or boot):
            return None
        voce = self._trova(run, boot)
        if voce is None:
            if not nome:
                return None
            voce = {"nome": "", "run": None, "boot": None}
            self.schede.append(voce)
        voce["nome"] = nome.strip()
        if run:
            voce["run"] = run
        if boot:
            voce["boot"] = boot
        if not voce["nome"]:
            self.schede.remove(voce)
            return None
        return voce

    def collega(self, run, boot):
        """Dice che questi due identificativi sono la stessa scheda.

        Lo si sa con certezza solo dopo averla vista passare da uno stato
        all'altro: e' l'unico momento in cui i due lati si toccano.
        """
        if not (run and boot):
            return None
        per_run = self._trova(run=run)
        per_boot = self._trova(boot=boot)
        if per_run and per_boot and per_run is not per_boot:
            # due schede si rivelano la stessa: si fondono, tenendo il nome
            # gia' dato (il primo che c'e')
            per_run["boot"] = boot
            if not per_run.get("nome"):
                per_run["nome"] = per_boot.get("nome", "")
            self.schede.remove(per_boot)
            return per_run
        voce = per_run or per_boot
        if voce is None:
            voce = {"nome": "", "run": None, "boot": None}
            self.schede.append(voce)
        voce["run"] = run
        voce["boot"] = boot
        return voce

    # ------------------------------------------------------------ salvataggio
    def come_elenco(self):
        return [dict(v) for v in self.schede if v.get("run") or v.get("boot")]


def etichetta(nome, seriale, quante=6):
    """«nome · 5303284738DE6E1C», oppure solo il seriale se non ha nome."""
    if not seriale:
        return nome or ""
    if nome:
        return "%s · %s" % (nome, seriale)
    return seriale


def coda(seriale, quante=4):
    """Le ultime cifre del seriale: quelle che si fanno ribattere per
    confermare CHE scheda si sta cancellando."""
    return (seriale or "")[-quante:].upper()
