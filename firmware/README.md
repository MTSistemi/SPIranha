# Programmer firmware

SPIranha turns a blank RP2040 board into a working SPI programmer: plug the
board in while holding **BOOTSEL** and the program offers to install the
firmware. It can also **reset a board to factory state**.

## What is here

| | |
|---|---|
| `pico_serprog.uf2` | the firmware, built from the source next to it |
| `pico-serprog/` | the complete source it was built from, patch applied |
| `0001-enable_spi-gcc15.patch` | the one change we made, on its own |

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
| file | `pico_serprog.uf2`, 45,056 bytes — 88 UF2 blocks |
| sha256 | `d199bf99658b358af1a53239cdab91c3ed6537117d3307bd79415dddb7635b10` |
| covers | `0x10000000`–`0x100057FF` |
| family | `0xE48BFF56` (RP2040) |

Tested on real hardware: copied onto a factory-fresh Pico, the board rebooted
and answered the serprog protocol one second later — `pico-serprog`,
interface 1, bus `0x08 = SPI`.

## Rebuilding it

| | |
|---|---|
| upstream | <https://codeberg.org/libreboot/pico-serprog> |
| commit | `3ea792664ed29ca1ff3e2e78d1d16099684781bd`, 2025-02-12 |
| pico-sdk | `98a542c` |
| toolchain | GCC ARM 15.3.1 |

```bash
cd pico-serprog
mkdir build && cd build
cmake .. -DPICO_SDK_PATH=/path/to/pico-sdk
make
```

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

## How the reset works

The `.uf2` SPIranha generates writes `0xFF` over the whole flash. The bootloader
erases each sector before writing it, so the result is an erased flash — the
factory state. With no valid second-stage bootloader the board comes back in
BOOTSEL by itself and shows up as `RPI-RP2` again.

⚠️ It erases **2 MiB**, the size of a genuine Raspberry Pi Pico. A clone with a
larger flash keeps whatever lies beyond that; it still returns to BOOTSEL,
which is what matters.
