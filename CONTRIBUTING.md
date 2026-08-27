# Contributing

Thanks for looking. This tool writes to flash chips on hardware people cannot
easily replace, so the bar for changes is a little different from usual.

## The one rule

**A change must not make it easier to write something unverified.** The safety
rails — two agreeing reads, the mandatory dry run, the typed confirmation, the
independent final verification — are the product. If a change removes one,
weakens one, or adds a path around one, it needs a very good reason and it needs
to say so plainly in the pull request.

Convenience is not a good enough reason.

## Before opening a pull request

Run both test suites on Windows:

```bash
python tests\test_gui.py        # 150 checks, no hardware
python tests\test_full.py   # 44 checks, needs flashrom built with 'dummy'
```

The tests build the **real** window, so they point `SPIRANHA_CONFIG` at a
throw-away folder before importing `app`. Without it they save over the settings
of whoever is using the program — profile, paths and board names included. Keep
that line at the top of any new test that constructs `App()`.

⚠️ `test_gui.py` runs in CI on a machine with **no `flashrom.exe`**, and that is
a different code path: the window falls back to placeholders. If you touch
anything that reads the flashrom object, run the suite once with the binary
moved aside — that is exactly what CI does, and it has caught a failure that
passed locally.


`test_full.py` drives the real window and the real flashrom against an
emulated chip. If your change touches the write path, the map, the dry run or
the verification, **add a check there** rather than describing the behaviour in
the pull request. A check that fails before your fix and passes after is worth
more than a paragraph.

Both suites skip with an explanation when their inputs are missing, so a red
result means something is genuinely wrong.

## House style

The code is written in Italian: identifiers, comments and docstrings. That is
deliberate and consistent — please follow it rather than mixing languages in the
same file. User-facing strings never appear inline: they live in `i18n.py` with
an Italian and an English version, and both must be filled in.

Comments explain **why**, and flag traps with `⚠️`. The repository is full of
notes like "this looks wrong but is correct, and here is why" — those exist
because someone lost an hour to it. Add yours.

Line length 88, four spaces, no tabs.

## Reporting hardware behaviour

If a chip, board or programmer behaves differently from what the tool expects,
that is a valuable report. Please include:

- the exact flashrom line from the log (turn on `-V` if you can);
- the chip as `flashrom --flash-name` reports it;
- what you expected and what happened;
- whether two consecutive reads agreed.

Please do not attach BIOS images: they are large and often contain your
machine's own settings and serial numbers.

## What this project is not

It is not a general flashrom replacement, and it does not aim to reimplement
SPI. flashrom does the erasing and writing, and that is on purpose: it is
twenty years more tested than anything we would write.
