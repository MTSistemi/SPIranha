# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/1.1.0/), and
the project uses [semantic versioning](https://semver.org/).

## [1.1.0] — 2026-08-27

First public release.

### Added
- **Guarded write path.** The write button stays off until flashrom is found,
  the chip is identified and its size matches the image, two consecutive reads
  agree, a dry run has been done, and the "board unplugged" box is ticked.
  Confirmation requires typing the word.
- **Dry run**, mandatory. Computes the resulting image in memory before
  anything is erased: expected md5, how many bytes change and where, and
  whether the source also differs outside the selected region.
- **Live chip map**, driven by flashrom's own `E(start:end)` and
  `W(start:end)` markers and per-stage progress, not by estimates.
- **Independent final verification.** Re-reads the whole chip after writing and
  compares it byte for byte with the dry-run image, then checks the written
  region is coherent (not all `0xFF`, not all `0x00`, known structures present).
- **Link qualification.** Finds the fastest SPI speed that gives two identical
  reads of 256 KB and sets it.
- **Image comparison** with 4 KB sector alignment, structure recognition
  (`_FVH`, `NVAR`, `APCB`, `$PSP`) and flashrom layout generation.
- **Wiring diagram** drawn in code, showing both the RP2040 and the target
  header, with the pin-1 marker.
- **Programmer firmware installation.** A board held in BOOTSEL is detected
  within seconds; SPIranha validates the `.uf2`, copies it, then waits for the
  serial port and queries the firmware before declaring the programmer ready.
- **Reset to factory** for an RP2040 board, using a `.uf2` SPIranha generates
  itself rather than a downloaded binary.
- The `pico-serprog` firmware ships with the project, together with the source
  it was built from and the two patches applied to it: the build fix for
  GCC 15, and a **1200-baud reboot into BOOTSEL** so a running programmer can
  be put back into update mode without touching the button.
- **Send to BOOTSEL**, which uses it.
- **1.8 V chips are recognised from the model name** and block the write
  until a level shifter is confirmed — wiring one straight to the RP2040 puts
  nearly twice its rated voltage on the pins, and reads MISO at random anyway.
  A model that cannot be placed is reported as unknown, never as 3.3 V.
- **A schematic for the 1.8 V adapter**: BSS138 per signal with its pull-ups,
  a 1.8 V regulator, and the two things the drawing cannot say — drop the speed
  to 1 MHz with MOSFETs, or use a 74LVC8T245 and keep 12 MHz.
- **The chip is asked directly when flashrom does not recognise it**: JEDEC
  id, and SFDP density when the chip has the table. An unknown chip and an
  absent chip stop looking the same.
- **Firmware 1.2.** An SPI operation can no longer hang the board. With the
  peripheral disabled it never returned, which stopped the USB task and made
  the board vanish from the host until unplugged — and flashrom leaves the
  peripheral disabled when it exits, so the next program to ask an ordinary
  question would hang it. Found by being that program.
- **Every read is compared with the previous backup** taken in the same
  folder: unchanged, or which sectors moved and where.
- **Board profiles.** Expected chips and size, chip voltage, known md5s,
  expected regions, board-specific warnings and the wiring diagram to open all
  come from a profile now. BC-250 is the first; **Generic board** covers a clip
  on a bare SOIC-8 and has its own pinout diagram. A profile is what we expect,
  not what we impose: a mismatch is reported and the work goes on.
- **Regions read out of the image.** Intel descriptor, FMAP and the AMD
  firmware structure are parsed straight from the dump, turned into a flashrom
  layout, and the region list fills itself. On the BC-250 — which has neither a
  descriptor nor an FMAP — the AMD structure yields the memory configuration
  and the 2 MiB BIOS image, and the full test has flashrom read that region
  back from the emulated chip and compares the bytes.
- **Firmware version.** The programmer now reports its version in the
  serprog name (`pico-serprog1.1`), SPIranha compares it with the firmware it
  carries, and offers a one-button update that goes back to BOOTSEL, copies,
  and then asks the board again — a copy going through is not proof the board
  is running the new code.
- **A copy that never started is no longer reported as done.** Any `OSError`
  used to count as the normal end-of-copy detach; a board fresh into BOOTSEL
  answers `Permission denied` until Windows finishes mounting it, so the
  firmware was never written and the program said it was. Now the copy is
  retried while nothing has been written, and reported as failed if it never
  starts.
- **Write protection.** The chip's lock is read together with its
  identification, shown with its range and mode, and blocks the write when it
  covers the target region — a protected chip accepts an erase and a write
  without changing, so this is the difference between a failure and a silent
  one. Clearing it takes a typed confirmation.
- **Board names.** Each programmer can be given a name that follows it
  everywhere. A board shows a different serial while running than it does in
  BOOTSEL, so SPIranha links the two the first time it sees the board move
  between states, and recognises it from either side afterwards.
- Erasing a board now takes **two confirmations**, the second one requiring the
  last four characters of that board's serial.
- Italian and English interface, switchable live. Responsive layout.
- Single-file portable executable with flashrom embedded; Inno Setup installer;
  Authenticode signing script that does not need the Windows SDK.
- 168 automated checks, including an end-to-end write against an emulated
  16 MiB chip.

### Verified on hardware
- Firmware installation on a factory-fresh Raspberry Pi Pico: detected in
  BOOTSEL, programmed, and answering serprog on a new COM port one second later.
- Factory reset, and the 1200-baud return to BOOTSEL, on the same board.
- Naming: a board named while running is still recognised by name after being
  sent to BOOTSEL, where its serial is a different number.
- Updating a board over the wire, with no button: 1.0 → 1.1, verified by asking
  the board afterwards. flashrom reads the new name back as
  `pico-serprog1.1`.

### Notes
- The first target is the AMD BC-250 (`J4004` header). The wiring diagram,
  known fingerprints and default layout are specific to it.
- `flashrom.exe` is not distributed in this repository; see
  `flashrom/PROVENANCE.md`.

[1.1.0]: https://github.com/MTSistemi/SPIranha/releases/tag/v1.1.0
