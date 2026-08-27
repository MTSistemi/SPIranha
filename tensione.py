# -*- coding: utf-8 -*-
"""A quanti volt lavora un chip, dedotto dal suo nome.

⚠️ PERCHE' CONTA. Le uscite dell'RP2040 sono a 3,3 V. Un chip da 1,8 V
attaccato ai fili come se fosse da 3,3 prende il doppio della tensione
prevista sui piedini: a volte muore subito, a volte legge storto e muore
dopo. E nell'altro verso non funziona comunque, perche' un 1 logico a 1,8 V
non arriva alla soglia dell'RP2040 (0,7 x 3,3 = 2,31 V): il MISO si legge a
caso.

Non c'e' modo di misurare la tensione da qui: si deduce dal nome del modello,
che per fortuna nelle famiglie SPI NOR e' regolare -- i costruttori mettono
una lettera fissa a distinguere le due versioni dello stesso chip.

⚠️ Solo le famiglie di cui la regola e' certa. Un chip che qui risulta
sconosciuto NON e' un chip a 3,3 V: e' un chip di cui non sappiamo dirlo, e
va guardata la scheda tecnica. Dire «3,3» per prudenza sarebbe il contrario
della prudenza.
"""
from __future__ import unicode_literals

import re

BASSA = 1.8
ALTA = 3.3

# (espressione, volt, come si chiama la famiglia)
REGOLE = (
    # Macronix: la U e' la serie a 1,8, la L quella a 3
    (r"MX25U", BASSA, "Macronix MX25U"),
    (r"MX25L", ALTA, "Macronix MX25L"),
    # MX25R lavora da 1,65 a 3,6 V: a 3,3 sta bene
    (r"MX25R", ALTA, "Macronix MX25R"),
    # Winbond: in coda W = 1,8 V, V = 3,3 V, con o senza la lettera di
    # generazione in mezzo (W25Q128.W, W25Q128.JW.DTR, W25Q32FW)
    (r"W25Q\d+[._]?[A-Z]?W", BASSA, "Winbond W25Q..W"),
    (r"W25Q\d+[._]?[A-Z]?V", ALTA, "Winbond W25Q..V"),
    (r"W25X\d+", ALTA, "Winbond W25X"),
    # GigaDevice: LQ/LB/LE/LF a 1,8; Q a 3
    (r"GD25L[QBEF]", BASSA, "GigaDevice GD25L"),
    (r"GD25Q", ALTA, "GigaDevice GD25Q"),
    # ISSI: WP a 1,8; LP a 3
    (r"IS25WP", BASSA, "ISSI IS25WP"),
    (r"IS25LP", ALTA, "ISSI IS25LP"),
    # Micron: MT25QU a 1,8; MT25QL a 3
    (r"MT25QU", BASSA, "Micron MT25QU"),
    (r"MT25QL", ALTA, "Micron MT25QL"),
    # ⚠️ Nei nomi che usa flashrom la cifra dopo i due punti E' la tensione:
    # N25Q128..1E = 1,8 V, N25Q128..3E = 3 V. Viene dalla sigla Micron.
    (r"N25Q\w*\.\.1", BASSA, "Micron N25Q 1,8 V"),
    (r"N25Q\w*\.\.3", ALTA, "Micron N25Q 3 V"),
    (r"N25Q\d+A13", BASSA, "Micron N25Q 1,8 V"),
    (r"N25Q\d+A11", ALTA, "Micron N25Q 3 V"),
    # XTX
    (r"XM25QU", BASSA, "XTX XM25QU"),
    (r"XM25QH", ALTA, "XTX XM25QH"),
    # Spansion/Cypress e SST: le serie diffuse sono a 3 V
    (r"S25FL", ALTA, "Spansion S25FL"),
    (r"SST25VF", ALTA, "SST SST25VF"),
    # EON/ESMT
    (r"EN25S", BASSA, "EON EN25S"),
    (r"EN25[QFP]", ALTA, "EON EN25Q/F/P"),
)

_COMPILATE = tuple((re.compile(e, re.IGNORECASE), v, n) for e, v, n in REGOLE)


def tensione(nome):
    """(volt, famiglia) dal nome del chip. (None, None) se non e' certo.

    Il nome e' quello che stampa flashrom, che a volte ne mette due separati
    da barra: basta che uno dei due sia riconosciuto, e se i due non vanno
    d'accordo si dice che non si sa.
    """
    if not nome:
        return None, None
    trovate = []
    for pezzo in re.split(r"[/,]", nome):
        pezzo = pezzo.strip()
        if not pezzo:
            continue
        for espressione, volt, famiglia in _COMPILATE:
            if espressione.search(pezzo):
                trovate.append((volt, famiglia))
                break
    if not trovate:
        return None, None
    volt = set(v for v, _f in trovate)
    if len(volt) > 1:
        # due nomi che dicono cose diverse: meglio ammettere di non saperlo
        return None, None
    return trovate[0]


def a_bassa_tensione(nome):
    """Questo chip vuole 1,8 V? None = non si sa, e va guardato a mano."""
    volt, _famiglia = tensione(nome)
    if volt is None:
        return None
    return volt == BASSA
