# -*- coding: utf-8 -*-
"""What voltage a chip runs at, worked out from its name.

⚠️ WHY IT MATTERS. The RP2040 drives its pins at 3.3 V. A 1.8 V chip wired
up as if it were a 3.3 V one gets nearly twice the voltage it is rated for:
sometimes it dies straight away, sometimes it reads wrong and dies later.
And it does not work in the other direction either, because a logic one at
1.8 V never reaches the RP2040's input threshold (0.7 x 3.3 = 2.31 V): MISO
reads at random.

There is no way to measure the voltage from here, so it is read off the
model name, which in the SPI NOR families is mercifully regular -- the
vendors use a fixed letter to tell the two versions of the same chip apart.

⚠️ Only the families whose rule is certain. A chip that comes back unknown
here is NOT a 3.3 V chip: it is a chip we cannot tell about, and its
datasheet has to be read. Saying "3.3" to be safe would be the opposite of
safe.
"""
from __future__ import unicode_literals

import re

BASSA = 1.8
ALTA = 3.3

# (pattern, volts, what the family is called)
REGOLE = (
    # Macronix: U is the 1.8 V series, L the 3 V one
    (r"MX25U", BASSA, "Macronix MX25U"),
    (r"MX25L", ALTA, "Macronix MX25L"),
    # MX25R runs from 1.65 to 3.6 V: 3.3 suits it fine
    (r"MX25R", ALTA, "Macronix MX25R"),
    # Winbond: trailing W = 1.8 V, V = 3.3 V, with or without the generation
    # letter in between (W25Q128.W, W25Q128.JW.DTR, W25Q32FW)
    (r"W25Q\d+[._]?[A-Z]?W", BASSA, "Winbond W25Q..W"),
    (r"W25Q\d+[._]?[A-Z]?V", ALTA, "Winbond W25Q..V"),
    (r"W25X\d+", ALTA, "Winbond W25X"),
    # GigaDevice: LQ/LB/LE/LF at 1.8; Q at 3
    (r"GD25L[QBEF]", BASSA, "GigaDevice GD25L"),
    (r"GD25Q", ALTA, "GigaDevice GD25Q"),
    # ISSI: WP at 1.8; LP at 3
    (r"IS25WP", BASSA, "ISSI IS25WP"),
    (r"IS25LP", ALTA, "ISSI IS25LP"),
    # Micron: MT25QU at 1.8; MT25QL at 3
    (r"MT25QU", BASSA, "Micron MT25QU"),
    (r"MT25QL", ALTA, "Micron MT25QL"),
    # ⚠️ In the names flashrom uses, the digit after the dots IS the voltage:
    # N25Q128..1E = 1.8 V, N25Q128..3E = 3 V. It comes from Micron's own part
    # numbering.
    (r"N25Q\w*\.\.1", BASSA, "Micron N25Q 1.8 V"),
    (r"N25Q\w*\.\.3", ALTA, "Micron N25Q 3 V"),
    (r"N25Q\d+A13", BASSA, "Micron N25Q 1.8 V"),
    (r"N25Q\d+A11", ALTA, "Micron N25Q 3 V"),
    # XTX
    (r"XM25QU", BASSA, "XTX XM25QU"),
    (r"XM25QH", ALTA, "XTX XM25QH"),
    # Spansion/Cypress and SST: the common series are 3 V
    (r"S25FL", ALTA, "Spansion S25FL"),
    (r"SST25VF", ALTA, "SST SST25VF"),
    # EON/ESMT
    (r"EN25S", BASSA, "EON EN25S"),
    (r"EN25[QFP]", ALTA, "EON EN25Q/F/P"),
)

_COMPILATE = tuple((re.compile(e, re.IGNORECASE), v, n) for e, v, n in REGOLE)


def tensione(nome):
    """(volts, family) from the chip name. (None, None) when not certain.

    The name is the one flashrom prints, which sometimes carries two of them
    separated by a slash: one recognised half is enough, and if the two
    disagree the answer is that we do not know.
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
        # two names saying different things: better to admit we do not know
        return None, None
    return trovate[0]


def a_bassa_tensione(nome):
    """Does this chip want 1.8 V? None = unknown, go and read the datasheet."""
    volt, _famiglia = tensione(nome)
    if volt is None:
        return None
    return volt == BASSA
