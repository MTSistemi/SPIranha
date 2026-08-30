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

LOW = 1.8
HIGH = 3.3

# (pattern, volts, what the family is called)
RULES = (
    # Macronix: U is the 1.8 V series, L the 3 V one
    (r"MX25U", LOW, "Macronix MX25U"),
    (r"MX25L", HIGH, "Macronix MX25L"),
    # MX25R runs from 1.65 to 3.6 V: 3.3 suits it fine
    (r"MX25R", HIGH, "Macronix MX25R"),
    # Winbond: trailing W = 1.8 V, V = 3.3 V, with or without the generation
    # letter in between (W25Q128.W, W25Q128.JW.DTR, W25Q32FW)
    (r"W25Q\d+[._]?[A-Z]?W", LOW, "Winbond W25Q..W"),
    (r"W25Q\d+[._]?[A-Z]?V", HIGH, "Winbond W25Q..V"),
    (r"W25X\d+", HIGH, "Winbond W25X"),
    # GigaDevice: LQ/LB/LE/LF at 1.8; Q at 3
    (r"GD25L[QBEF]", LOW, "GigaDevice GD25L"),
    (r"GD25Q", HIGH, "GigaDevice GD25Q"),
    # ISSI: WP at 1.8; LP at 3
    (r"IS25WP", LOW, "ISSI IS25WP"),
    (r"IS25LP", HIGH, "ISSI IS25LP"),
    # Micron: MT25QU at 1.8; MT25QL at 3
    (r"MT25QU", LOW, "Micron MT25QU"),
    (r"MT25QL", HIGH, "Micron MT25QL"),
    # ⚠️ In the names flashrom uses, the digit after the dots IS the voltage:
    # N25Q128..1E = 1.8 V, N25Q128..3E = 3 V. It comes from Micron's own part
    # numbering.
    (r"N25Q\w*\.\.1", LOW, "Micron N25Q 1.8 V"),
    (r"N25Q\w*\.\.3", HIGH, "Micron N25Q 3 V"),
    (r"N25Q\d+A13", LOW, "Micron N25Q 1.8 V"),
    (r"N25Q\d+A11", HIGH, "Micron N25Q 3 V"),
    # XTX
    (r"XM25QU", LOW, "XTX XM25QU"),
    (r"XM25QH", HIGH, "XTX XM25QH"),
    # Spansion/Cypress and SST: the common series are 3 V
    (r"S25FL", HIGH, "Spansion S25FL"),
    (r"SST25VF", HIGH, "SST SST25VF"),
    # EON/ESMT
    (r"EN25S", LOW, "EON EN25S"),
    (r"EN25[QFP]", HIGH, "EON EN25Q/F/P"),
)

_COMPILED = tuple((re.compile(e, re.IGNORECASE), v, n) for e, v, n in RULES)


def voltage_of(name):
    """(volts, family) from the chip name. (None, None) when not certain.

    The name is the one flashrom prints, which sometimes carries two of them
    separated by a slash: one recognised half is enough, and if the two
    disagree the answer is that we do not know.
    """
    if not name:
        return None, None
    found = []
    for chunk in re.split(r"[/,]", name):
        chunk = chunk.strip()
        if not chunk:
            continue
        for expression, volts, family in _COMPILED:
            if expression.search(chunk):
                found.append((volts, family))
                break
    if not found:
        return None, None
    volts = set(v for v, _f in found)
    if len(volts) > 1:
        # two names saying different things: better to admit we do not know
        return None, None
    return found[0]


def is_low_voltage(name):
    """Does this chip want 1.8 V? None = unknown, go and read the datasheet."""
    volts, _family = voltage_of(name)
    if volts is None:
        return None
    return volts == LOW
