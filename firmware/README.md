# Programmer firmware

SPIranha turns a blank RP2040 board into a working SPI programmer: plug the
board in while holding **BOOTSEL** and the program offers to install the
firmware. It can also **reset a board to factory state**.

## What is here

| | |
|---|---|
| `pico_serprog.uf2` | the firmware, built from the source next to it |
| `pico-serprog/` | the complete source it was built from, all patches applied |
| `VERSION` | the version of the binary here, which the board reports back |
| `0001-enable_spi-gcc15.patch` | build fix for GCC 15 and newer |
| `0002-bootsel-1200-baud.patch` | reboot into BOOTSEL on a 1200-baud open |
| `0003-report-version.patch` | say which firmware version this is |

The firmware is **GPLv3** and it ships here **with its corresponding source**,
which is what the licence asks for. It is a separate program that runs on the
microcontroller; it is not linked into SPIranha, and its licence is its own —
not the GPL-2.0 of this repository.

> `pico-serprog` — Copyright © 2021 Mate Kukri, © 2023, 2024 Riku Viitanen,
> based on work by Thomas Roth. Upstream:
> <https://codeberg.org/libreboot/pico-serprog>

The **reset to factory** function needs no firmware at all: SPIranha generates
that `.uf2` itself (see `pico.py`), so there is no third-party binary involved.

## The binary

| | |
|---|---|
| file | `pico_serprog.uf2`, 44,544 bytes — 87 UF2 blocks |
| version | **1.1** |
| sha256 | `05a24665a85e7116ee25b90ed53e0cbcda76d57b0aee810f4c383d6a666bbdc4` |
| covers | `0x10000000`–`0x100056FF` |
| family | `0xE48BFF56` (RP2040) |

Tested on real hardware: copied onto a factory-fresh Pico, the board rebooted
and answered the serprog protocol one second later — `pico-serprog`,
interface 1, bus `0x08 = SPI`. Then reset to factory, reprogrammed, and sent
back to BOOTSEL over the wire, all without touching the button.

## Which version a board is running

Nothing on an RP2040 says which firmware it holds. The flash carries no version,
the USB serial number is the chip's unique id — the same before and after any
update — and the descriptors do not change between builds. Asking the board is
the only way, so `0003-report-version.patch` makes it answer.

The serprog name is a fixed 16-byte field and the host reads all sixteen, so the
version travels inside it, with no new command and no compatibility cost:

| firmware | reports |
|---|---|
| 1.1 and later | `pico-serprog1.1` |
| 1.0 and earlier | `pico-serprog` |

A bare name is therefore not "unknown": it is a board older than 1.1, which is
the distinction that matters — those boards cannot be sent back to BOOTSEL over
the wire, so updating them still needs the button, once.

## Rebuilding it

| | |
|---|---|
| upstream | <https://codeberg.org/libreboot/pico-serprog> |
| commit | `3ea792664ed29ca1ff3e2e78d1d16099684781bd`, 2025-02-12 |
| pico-sdk | 2.1.1 |
| toolchain | GCC ARM 14.2.1 (Arm GNU Toolchain 14.2.Rel1) |

```bash
cmake -S pico-serprog -B build -G Ninja \
      -DPICO_SDK_PATH=/path/to/pico-sdk -DPICO_BOARD=pico
cmake --build build
```

⚠️ On Windows, clone the SDK into a **short path** (`C:\pico\sdk`) and enable
`core.longpaths`: the TinyUSB submodule has paths deep enough to break a
checkout otherwise, and the failure looks like an unrelated git error.

⚠️ **The patch is needed with GCC 15 or newer.** `enable_spi` is declared as
`static void enable_spi()` — which in C23 means *no parameters* — but is called
once as `enable_spi(baud)`, so the build fails with *"too many arguments to
function 'enable_spi'"*.

It is not a behavioural change: `baud` is a global that the function already
reads by itself, and older compilers silently discarded the argument. The
source in `pico-serprog/` already has the fix; the diff is in
`0001-enable_spi-gcc15.patch`. Worth reporting upstream.

## Pin assignment

The firmware uses `spi0`:

| signal | GPIO | Pico pin |
|---|---|---|
| SCLK | GP2 | 4 |
| MOSI | GP3 | 5 |
| MISO | GP4 | 6 |
| CS | GP5 | 7 |

It starts at 12 MHz. SPIranha's **Qualify** button then finds the fastest speed
that actually gives repeatable reads on your wiring.

## How the install works

An RP2040 held in BOOTSEL appears as a removable drive labelled `RPI-RP2`
containing `INFO_UF2.TXT`. Copying a `.uf2` onto it programs the board, which
reboots on its own. The bootloader is in ROM: nothing can be bricked this way,
and a board with an empty flash always comes back in BOOTSEL.

SPIranha validates the `.uf2` before copying — magic numbers, block numbering,
payload size and the RP2040 family ID — so a wrong or truncated file is caught
before it reaches the board. Afterwards it waits for a **new** serial port to
appear and asks the firmware who it is: "installed" means "answering", not just
"copied".

⚠️ The copy usually reports an error at the very end: the drive disappears the
moment the bootloader has what it needs. That is expected and is not treated as
a failure.

⚠️ The board announces itself as `Board-ID: RPI-RP2` — note the `RPI-` prefix.
An early version of the detection looked for an id *starting* with `RP2` and
therefore recognised nothing. Only real hardware caught it; there is now a test
for exactly that string.

## Getting back into BOOTSEL, without the button

Upstream `pico-serprog` implements the serprog protocol and nothing else: no
`reset_usb_boot`, no 1200-baud touch, no vendor command. With it, the only way
back into the bootloader is physical — unplug, hold **BOOTSEL**, plug back in.

`0002-bootsel-1200-baud.patch` adds it. When the host sets the line coding to
**1200 baud**, the firmware calls `reset_usb_boot()` and the board comes back
as the `RPI-RP2` drive. It is the Arduino Leonardo convention, and the one
`pico_stdio_usb` uses.

It cannot fire by accident: serprog hosts open the port at their configured
rate — 115200 in SPIranha, whatever `-p serprog:dev=...:baud` says in flashrom.
Nothing legitimate asks for 1200.

⚠️ Opening the port at 1200 baud normally **raises an error on the host**: the
board reboots and the port disappears while the operating system is still
configuring it. That is the sign it worked. Never read the outcome from the
serial open — check whether the board came back as a drive.

⚠️ This only works with firmware built from the source here. A board carrying
an older build ignores 1200 baud, and the button is still the only way.

## Telling boards apart

A board reports **two different serial numbers**, and they do not match:

| state | where it comes from | example |
|---|---|---|
| running the firmware | flash unique id, over USB CDC | `5303284738DE6E1C` |
| in BOOTSEL | the bootloader's own id, on the mass-storage device | `E0C9125B0D9B` |

Verified on one physical board. There is no way to compute one from the other,
so SPIranha stores both and links them the first time it watches a board move
between the two states — during an install, or a send-to-BOOTSEL. From then on
the name you gave it shows up either way.

## How the reset works

The `.uf2` SPIranha generates writes `0xFF` over the whole flash. The bootloader
erases each sector before writing it, so the result is an erased flash — the
factory state. With no valid second-stage bootloader the board comes back in
BOOTSEL by itself and shows up as `RPI-RP2` again.

⚠️ It erases **2 MiB**, the size of a genuine Raspberry Pi Pico. A clone with a
larger flash keeps whatever lies beyond that; it still returns to BOOTSEL,
which is what matters.
