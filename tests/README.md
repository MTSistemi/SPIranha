# Tests

Run them with a Python that has `pyserial` — the project's own virtualenv will
do:

```bash
..\.venv\Scripts\python.exe test_gui.py
..\.venv\Scripts\python.exe test_full.py
```

They open and close the window by themselves; there is nothing to click.

*Versione italiana: [`docs/it/prove-LEGGIMI.md`](../docs/it/prove-LEGGIMI.md).*

## `test_gui.py` — 79 checks

The window and its rules, without touching flashrom: construction, live
IT↔EN switching, everything disabled when flashrom is missing, layout file
parsing, and the write requirements lighting up and going out one by one —
including an image of the wrong size, which must be rejected.

It also checks the **dry-run rule**: without one the write button stays off, and
changing the image makes a previous dry run lapse by itself.

It also covers the UF2 handling in `pico.py`: the generated reset image is
read back and checked block by block, and both a corrupted file and a
non-UF2 file must be refused before they could ever reach a board. And it
pins down the board recognition against the real `Board-ID: RPI-RP2` string,
which an earlier version got wrong.

It covers region detection on images it builds itself — an Intel descriptor,
an FMAP, an AMD structure — including the cases that must *not* produce a
result: a region the descriptor marks as absent, an FMAP belonging to a
different image, and an image carrying no map at all.

It covers the firmware version too: reading it out of the name the board
reports, comparing versions numerically (so `1.10` is newer than `1.9`), and
treating a board that reports no version as *older*, not unknown. And it checks
that a copy which never started is reported as a failure — that one came from
the bench, where a board fresh into BOOTSEL refused the copy and the old code
called it a success.

It covers write protection without a chip: the three answers flashrom can
give (no protection, a range, no answer at all), whether a protected range
overlaps the region being written, and — the one that matters — that a protected
chip turns the write button off.

It covers the board registry too: a name given against the running serial is
not known from the BOOTSEL side until the two are linked, two separate entries
merge when they turn out to be one board, and an empty name forgets it. Plus the
confirmation dialog with a caller-chosen word, which is what makes the second
erase consent ask for the serial's last four characters.

**This test fabricates its own fixtures** — a layout file and two 16 MiB images
— so it needs nothing from outside and runs in CI on every push.

## `test_full.py` — 44 checks

**This is the one that matters.** It drives the real window and the real
flashrom; the only difference is the programmer, which is `dummy` instead of
`serprog` — a 16 MiB chip emulated in memory and persisted to a file.

The central check mirrors the real operation exactly:

1. the emulated chip is initialised with the stock BIOS image;
2. the **`uefi` region alone** is written, taken from the expected-result image,
   through the layout file;
3. afterwards the emulated chip must be byte-for-byte identical to the expected
   result (md5 `f7632f2f…`).

It also covers everything added later:

- **link qualification** picks a speed and cleans up its own scratch files;
- the **dry run** computes md5 `f7632f2f…`, one range, 1,321,026 bytes, nothing
  outside the region — and without it the write is refused;
- the **final verification** re-reads the whole chip, finds no difference and
  reports the region coherent (`UEFI volume ×1`);
- the **chip map** ends up entirely green, with not one red block;
- the **generated layout** has the same three ranges as the hand-written
  `bc250-layout.txt` (only the filler region names differ: `salta0`/`salta2`
  instead of `prima`/`dopo`), and flashrom parses it back.

And the two safety rails that actually matter:

- **two differing reads**: a wobbling md5 is simulated, and the read must not be
  validated, the write button must stay off, and **both** files must be kept so
  they can be examined;
- **the confirmation**: off to begin with, still off with the wrong word, on
  only with the right one.

## What they need

`test_full.py` needs two things that are **not in this repository**:

| | |
|---|---|
| `flashrom.exe` | built with the `dummy` programmer — see [`flashrom/PROVENANCE.md`](../flashrom/PROVENANCE.md) |
| BC-250 BIOS images | `bc250-stock.rom`, `bc250-risultato-atteso.rom`, `bc250-layout.txt` |

Point `SPIRANHA_BIOS_BACKUP` at the folder holding the images, or put them in a
`bios-backup` folder next to the project.

When something is missing both suites **skip with an explanation and exit 0**,
rather than failing. A red result means something is genuinely wrong.

Scratch files go into `tests\lavoro\`, which can be deleted.
