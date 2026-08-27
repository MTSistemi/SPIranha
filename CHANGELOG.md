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
  it was built from and the patch that makes it compile with GCC 15.
- Italian and English interface, switchable live. Responsive layout.
- Single-file portable executable with flashrom embedded; Inno Setup installer;
  Authenticode signing script that does not need the Windows SDK.
- 69 automated checks, including an end-to-end write against an emulated
  16 MiB chip.

### Verified on hardware
- Firmware installation on a factory-fresh Raspberry Pi Pico: detected in
  BOOTSEL, programmed, and answering serprog on a new COM port one second
  later.

### Notes
- The first target is the AMD BC-250 (`J4004` header). The wiring diagram,
  known fingerprints and default layout are specific to it.
- `flashrom.exe` is not distributed in this repository; see
  `flashrom/PROVENANCE.md`.

[1.1.0]: https://github.com/MTSistemi/SPIranha/releases/tag/v1.1.0
