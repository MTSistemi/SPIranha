# Programmer firmware

SPIranha can turn a blank RP2040 board into a working SPI programmer: plug the
board in while holding **BOOTSEL**, and the program offers to install the
firmware. It can also **reset a board to factory state**.

## What goes in this folder

| file | |
|---|---|
| `pico_serprog.uf2` | the firmware that makes an RP2040 a serprog programmer |

⚠️ **It is not in this repository.** Like `flashrom.exe`, it is GPL software and
has to be built — see below. Without it the "Make it a programmer" button stays
off and says so.

The **reset to factory** function needs nothing: SPIranha generates that `.uf2`
itself (see `pico.py`), so there is no third-party binary involved.

## Building pico-serprog

Source: [`pico-serprog`](https://codeberg.org/libreboot/pico-serprog) by
libreboot, GPL.

The build used for the reference binary:

| | |
|---|---|
| source | `https://codeberg.org/libreboot/pico-serprog.git` |
| commit | `3ea7926`, 2025-02-12 |
| pico-sdk | `98a542c`, 2026-07-03 |
| toolchain | GCC ARM 15.3.1 |
| result | `pico_serprog.uf2`, 45,056 bytes |
| sha256 | `d199bf99658b358af1a53239cdab91c3ed6537117d3307bd79415dddb7635b10` |

⚠️ **One change to the source is needed with GCC 15 or newer.** In `main.c`,
`enable_spi(baud)` is called while the function is declared as
`static void enable_spi()` — which in C23 means *no parameters* — so the build
fails with *"too many arguments to function 'enable_spi'"*.

It is not a behavioural bug: `baud` is a global that the function already reads
by itself, and older compilers silently discarded the argument. The fix is to
drop the argument:

```diff
-	enable_spi(baud);
+	enable_spi();
```

⚠️ **If you redistribute the resulting `.uf2`, GPL applies**: you must make the
corresponding source available, including this change. Worth reporting
upstream, too.

## Pin assignment

The stock firmware uses `spi0`:

| signal | GPIO | Pico pin |
|---|---|---|
| SCLK | GP2 | 4 |
| MOSI | GP3 | 5 |
| MISO | GP4 | 6 |
| CS | GP5 | 7 |

It starts at 12 MHz. SPIranha's **Qualify** button finds the fastest speed that
actually gives repeatable reads on your wiring.

## How the install works

An RP2040 held in BOOTSEL appears as a removable drive labelled `RPI-RP2`
containing `INFO_UF2.TXT`. Copying a `.uf2` onto it programs the board, which
then reboots on its own. The bootloader is in ROM: nothing can be bricked this
way, and a board with an empty flash always comes back in BOOTSEL.

SPIranha validates the `.uf2` before copying — magic numbers, block numbering,
payload size and the RP2040 family ID — so a wrong or truncated file is caught
before it reaches the board. After the copy it waits for the serial port to
appear and asks the firmware who it is, so "installed" means "answering", not
just "copied".

⚠️ The copy usually reports an error at the very end: the drive disappears the
moment the bootloader has what it needs. That is expected and is not treated as
a failure.

## How the reset works

The `.uf2` SPIranha generates writes `0xFF` over the whole flash. The bootloader
erases each sector before writing it, so the result is an erased flash — the
factory state. With no valid second-stage bootloader the board comes back in
BOOTSEL by itself and shows up as `RPI-RP2` again.

⚠️ It erases **2 MiB**, the size of a genuine Raspberry Pi Pico. A clone with a
larger flash keeps whatever is beyond that; it still boots to BOOTSEL, which is
what matters.
