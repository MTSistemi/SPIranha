# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/1.1.0/), and
the project uses [semantic versioning](https://semver.org/).

## [1.2.1] — 2026-08-30

Housekeeping that turned into four fixes. The whole codebase is now in
English — file names, identifiers, comments, translation keys — because the
audience for source code is not the person who wrote it. The interface still
speaks Italian and English, and the Italian documentation stays Italian.

### Fixed
- **The name given to a board was lost on upgrade.** Up to 1.2.0 the board
  registry stored it under , and the new code only looked for ,
  so a named programmer came back anonymous. Found on the bench, installing
  1.2.1 over 1.2.0 with the board on the desk.
- **Three attribute names looked up by string** were left behind by the
  rename, so the code silently found nothing: the window no longer reflowed
  between one and two columns, the region names never reached the write
  confirmation, and the theme fallback for a detached window did nothing.
- **A profile mismatch would have crashed the message**: the fields passed in
  (`atteso`, `trovato`, `quali`) no longer matched the holes in the sentence
  (`{expected}`, `{hit}`, `{which}`).
- **The installer referenced a file that no longer exists**
  (`docs\it\LEGGIMI.md`), which stopped the setup from being built at all.
- **CI was red for three commits** without anyone noticing: two of its checks
  run as inline Python and were still importing the modules by their old
  names.

### Changed
- **Settings are stored under English names** (`language`, `folder`,
  `profile`, …). A `config.json` written by an earlier version is migrated on
  first load, profile `generico` included: nothing is lost.
- **Backups are named `<profile>-read-`, `-verify-` and `-after-`** instead of
  the Italian prefixes. The comparison with the previous backup still accepts
  the old names, so the files already on disk keep being compared.
- Translation keys, canvas tags, ttk styles, thread states, log tags and the
  CSS classes of the printable page are all in English, and the printed page
  now declares the language it was produced in.

## [1.2.0] — 2026-08-28

Everything below came after the first release, and most of it came from a
failure that did not announce itself.

### Added
- **A printable PDF of the schematic with its bill of materials.** Two A4
  sheets — the circuit, then the parts and the notes as real tables. The
  drawing is not re-drawn for print: it is read back off the canvas and
  emitted as SVG, so there is only ever one schematic. Colours are inverted
  for paper (lightness only, so a red wire stays red), because a dark
  schematic costs a cartridge and reads badly. An English copy lives in
  `docs/level-shifter-1v8.pdf`.
- **Screenshots in the README**, all in English, taken with neutral paths.
- Log files are named after the program (`SPIranha.log`), not after the
  project it grew out of.
- **All 492 supported SPI chips in the model list, with a search.** Read from
  `flashrom -L`, so it follows the binary in use; multi-line names are stitched
  back together because that is the name flashrom accepts. The search shows
  size, working voltage and what flashrom says it has tested on that part.
- **The 1.8 V schematic carries a real bill of materials** — manufacturer part
  numbers, values, packages — plus the two things that are easy to get wrong:
  the 2N7002 that looks like a BSS138 and never turns on at 1.8 V, and the
  10 kΩ pull-ups that are an I²C habit and are too slow for SPI.
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
- 206 automated checks, including an end-to-end write against an emulated
  16 MiB chip.

### Verified on hardware
- Updating a board over the wire, with no button: 1.0 → 1.1 → 1.2, asking the
  board its version after each step. flashrom reads the new name back as
  `pico-serprog1.2`.
- The firmware hang, both ways round: on 1.1 the board vanished from Windows
  and had to be unplugged; on 1.2 the same sequence answers `00 00 00` and the
  board still responds afterwards.
- The JEDEC probe with nothing attached: reported as *no chip*, which is the
  distinction it exists to make.
- A 16 MiB BC-250 dump read end to end through the whole chain — identify,
  protection, two reads, fingerprints compared, regions derived — and matching
  the file it came from byte for byte.

### Fixed
- **Naming a board now shows up in the port list straight away.** The port was
  the same, so the label was left alone — and the name you had just typed
  looked lost.
- **Overlapping text in the diagrams.** The notes under the small headings were
  anchored at their centre, so the first line of a wrapped note climbed on top
  of the heading.
- **A write-protected chip no longer looks like a successful write.** It
  accepts the erase and the write and stays as it was; the protection is now
  read with the chip and blocks the write when it covers the target.
- **A firmware copy that never started is reported as failed.** Any `OSError`
  used to count as the normal end-of-copy detach, and a board fresh into
  BOOTSEL answers `Permission denied` until Windows finishes mounting it — so
  the firmware was never written and the program said it was.
- **An SPI operation can no longer hang the board** (firmware 1.2). With the
  peripheral disabled it never returned, which stopped the USB task and made
  the board vanish until unplugged — and flashrom leaves the peripheral
  disabled when it exits.
- **The tests no longer overwrite the user's settings**: they build the real
  window and saved over the real configuration.
- The language switch now updates the language selector and the status bar too.

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

### Verified on hardware
- Firmware installation on a factory-fresh Raspberry Pi Pico: detected in
  BOOTSEL, programmed, and answering serprog on a new COM port one second later.
- Factory reset, and the 1200-baud return to BOOTSEL, on the same board.
- Naming: a board named while running is still recognised by name after being
  sent to BOOTSEL, where its serial is a different number.

### Notes
- The first target is the AMD BC-250 (`J4004` header). The wiring diagram,
  known fingerprints and default layout are specific to it.
- `flashrom.exe` is not distributed in this repository; see
  `flashrom/PROVENANCE.md`.

[1.2.0]: https://github.com/MTSistemi/SPIranha/releases/tag/v1.2.0
[1.1.0]: https://github.com/MTSistemi/SPIranha/releases/tag/v1.1.0
