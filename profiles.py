# -*- coding: utf-8 -*-
"""Board profiles: what changes from one machine to the next, in one place.

The program was born on a BC-250, but there is nothing board-specific about
the programmer itself: the same four wires read any SPI flash. What changes
from board to board is the surroundings, and the surroundings are exactly
what trips people up -- where to attach, which chip to expect, which
fingerprints are already known, and the warnings that apply to that machine
and not to another.

⚠️ A profile is NOT a filter: if the chip found is not the expected one, the
program says so and carries on. A profile is what we expect, not what we
impose. Whoever has the board in front of them can see better than a table
written months ago.

Adding one is data only: name, chip, voltage, header, known fingerprints,
warnings. The wiring drawing comes in two shapes -- the BC-250 header and the
clip on the chip -- and a profile says which of the two to use.
"""
from __future__ import unicode_literals

# the two kinds of connection the drawing knows how to show
HEADER = "connettore"       # a header on the board (BC-250: J4004)
CLIP = "pinza"                 # the clip straight onto the SOIC-8 chip


class Profile(object):
    """What we know about a board in advance."""

    def __init__(self, key, name, chip=(), size=None, voltage_of=3.3,
                 connection=CLIP, connettore=None, md5=None, avvisi=(),
                 description=None, regions=()):
        self.key = key
        self.name = name                    # {"it":…, "en":…} or a string
        self.chip = list(chip)              # expected models, first is the one
        self.size = size                    # expected flash size
        self.voltage_of = voltage_of            # chip volts: 3.3 or 1.8
        self.connection = connection
        self.connettore = connettore        # what it is called, if any
        self.md5 = dict(md5 or {})          # fingerprint -> {"it":…, "en":…}
        self.avvisi = tuple(avvisi)         # the board's own warnings
        self.description = description
        self.regions = tuple(regions)       # regions we expect to find

    def text(self, field, language="it"):
        value_for = getattr(self, field, None)
        if isinstance(value_for, dict):
            return value_for.get(language) or value_for.get("it") or ""
        return value_for or ""

    @property
    def generic(self):
        return self.key == "generico"


PROFILES = [
    Profile(
        "bc250",
        {"it": "AMD BC-250", "en": "AMD BC-250"},
        chip=["MX25L12835F/MX25L12873F", "MX25L12805D", "W25Q128.V"],
        size=16 * 1024 * 1024,
        voltage_of=3.3,
        connection=HEADER,
        connettore="J4004",
        md5={
            "3487f648a69a781d2609a8d4e6f4808e": {
                "it": "BIOS originale P3.00",
                "en": "stock BIOS P3.00",
            },
            "f7632f2ff61a7a5e65fff74d09942aeb": {
                "it": "risultato atteso dopo la modifica",
                "en": "expected result after the modification",
            },
        },
        avvisi=("prof_bc250_sio",),
        description={
            "it": "Connettore J4004 a 8 piedini accanto al chip BIOS. "
                  "Sulla scheda ci sono DUE flash: quella grande da 16 MiB "
                  "è il BIOS, quella da 512 KiB è il SuperIO.",
            "en": "Eight-pin J4004 header next to the BIOS chip. The board "
                  "carries TWO flash chips: the 16 MiB one is the BIOS, the "
                  "512 KiB one is the SuperIO.",
        },
        regions=("bios", "apcb", "psp"),
    ),
    Profile(
        "generico",
        {"it": "Scheda generica", "en": "Generic board"},
        chip=[],
        size=None,
        voltage_of=3.3,
        connection=CLIP,
        avvisi=("prof_gen_pinza",),
        description={
            "it": "Qualunque flash SPI in contenitore SOIC-8, presa con una "
                  "pinza. È il caso più comune fuori da una scheda "
                  "conosciuta.",
            "en": "Any SPI flash in a SOIC-8 package, taken with a clip. This "
                  "is the common case outside a known board.",
        },
    ),
]

BY_KEY = dict((p.key, p) for p in PROFILES)
DEFAULT_KEY = "bc250"


def by_key(key):
    """The profile with that key, or the default one."""
    return BY_KEY.get(key) or BY_KEY[DEFAULT_KEY]


def keys_of():
    return [p.key for p in PROFILES]


def names_of(language="it"):
    return [(p.key, p.text("name", language)) for p in PROFILES]


def deviations(profile, found_chip=None, found_size=None, regions=()):
    """Where the real board does not match what the profile expects.

    Returns a list of (message_key, fields). Empty = everything as expected.
    ⚠️ These are warnings, not prohibitions: a chip other than the expected
    one may perfectly well be a later revision of the same board.
    """
    out = []
    if profile.size and found_size and found_size != profile.size:
        out.append(("prof_dim_diversa",
                      {"atteso": profile.size, "trovato": found_size}))
    if profile.chip and found_chip:
        expected = [c.lower() for c in profile.chip]
        name = found_chip.lower()
        if not any(name in c or c in name for c in expected):
            out.append(("prof_chip_diverso",
                          {"atteso": profile.chip[0], "trovato": found_chip}))
    if profile.regions and regions:
        found = set(regions)
        mancanti = [n for n in profile.regions if n not in found]
        if mancanti:
            out.append(("prof_regioni_mancanti",
                          {"quali": ", ".join(mancanti)}))
    return out
