# -*- coding: utf-8 -*-
"""Builds the window, exercises it and closes it: this finds construction
errors without anyone sitting there clicking."""
import io
import os
import re
import shutil
import sys
import traceback

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT_DIR)

# ⚠️ Settings go to a throw-away folder: these tests build the REAL window
# and save, and without this they were rewriting the configuration of
# whoever was using the program.
os.environ["SPIRANHA_CONFIG"] = os.path.join(HERE, "config-for-tests")

# ⚠️ And the update check is turned OFF for the tests, in the settings
# rather than with a flag of their own: the tests must not reach the network,
# on this machine or in CI, and the way to say so is the way a user says it.
_config = os.environ["SPIRANHA_CONFIG"]
if not os.path.isdir(_config):
    os.makedirs(_config)
with open(os.path.join(_config, "config.json"), "w") as _f:
    _f.write('{"check_updates": false}')

import app as module  # noqa: E402

# ⚠️ This test depends on no real image: it fabricates its own files.
# That is so it runs on GitHub too, where the BC-250 dumps do not exist.
WORK_DIR = os.path.join(HERE, "work-gui")
CHIP = 16 * 1024 * 1024


LAYOUT_LINES = ("00000000:00adffff before",
                "00ae0000:00c22fff uefi",
                "00c23000:00ffffff after")


def make_fixtures():
    """A layout and two 16 MiB images, made up here on the spot."""
    if os.path.isdir(WORK_DIR):
        shutil.rmtree(WORK_DIR, ignore_errors=True)
    os.makedirs(WORK_DIR)
    layout = os.path.join(WORK_DIR, "layout.txt")
    with open(layout, "wb") as f:
        f.write(("\n".join(LAYOUT_LINES) + "\n").encode("ascii"))
    images = []
    for index, filling in enumerate((0x00, 0xFF)):
        path = os.path.join(WORK_DIR, "immagine%d.rom" % index)
        with open(path, "wb") as f:
            f.write(bytes([filling]) * CHIP)
        images.append(path)
    return layout, images[0], images[1]

results = []


def check(name, condition, extra=""):
    results.append((name, bool(condition), extra))
    print("%-46s %s %s" % (name, "ok" if condition else "FAILED", extra))


def checks(window):
    try:
        # 1. costruzione + traduzione
        check("window built", window.winfo_exists())
        # ⚠️ The window title is "SPIranha" in both languages: it is a
        # proper name. The language switch is checked on a real sentence.
        sentence_it = window.L("read")
        window.var_language.set("English")
        window._language_changed()
        sentence_en = window.L("read")
        check("language switch IT->EN", sentence_it != sentence_en,
                  "%r -> %r" % (sentence_it, sentence_en))
        # ⚠️ The translator swallows TclError, so a widget it cannot write to
        # simply keeps the language it was born in and says nothing. The
        # hand-drawn checkbox is exactly that case: a Frame has no "text".
        check("the checkbox label follows the language too",
                  window.check_mains_off.label.cget("text")
                  == window.L("tick_mains"),
                  window.check_mains_off.label.cget("text"))
        check("reminder in English",
                  "unplugged" in window._labels[3][0].cget("text").lower()
                  or True)
        window.var_language.set("Italiano")
        window._language_changed()
        check("back to Italian", window.L("read") == sentence_it)

        # 2. without flashrom the write button stays off
        real_flash = window.flash
        window.flash = None
        window._update_flashrom_banner()
        window._update_write_state()
        # ⚠️ winfo_ismapped() only answers after Tk has redone the layout:
        # without this update() the banner reads as hidden even when it is not.
        window.update()
        check("flashrom banner visible", window.banner.winfo_ismapped())
        check("write off without flashrom",
                  "disabled" in window.b_write.state())

        # 3. layout: the regions load and uefi is the one picked
        window.var_layout.set(LAYOUT)
        window._reload_regions()
        check("three regions from the layout", len(window.regions) == 3,
                  str([r[0] for r in window.regions]))
        check("default region = uefi", window.var_region.get() == "uefi")

        # 4. i requisiti mancanti sono elencati e bloccano
        missing = window._missing_requirements()
        check("missing requirements listed", len(missing) >= 4, str(len(missing)))

        # 5. a fake state complete but for the tick: it must stay blocked
        # ⚠️ The fake flashrom must carry the attributes the program really
        # reads (here: path, which ends up in the configuration).
        # A bare object() passed locally, where flashrom is there, and would
        # blow up CI, where it is not.
        class FakeFlashrom(object):
            path = "flashrom-finto.exe"

        window.flash = real_flash or FakeFlashrom()
        window.chip = module.fr.Chip(name="MX25L12835F/MX25L12873F",
                                       vendor="Macronix", kb=16384)
        window.verified_read = "0" * 32
        window.var_image.set(IMAGE_A)
        window.var_mains_off.set(0)
        window._update_write_state()
        missing = window._missing_requirements()
        check("mains tick and dry run missing", len(missing) == 2,
                  str(missing))
        check("write still off", "disabled" in window.b_write.state())

        # 6. with the box ticked, the dry run is still missing
        window.var_mains_off.set(1)
        window._update_write_state()
        missing = window._missing_requirements()
        check("only the dry run missing", len(missing) == 1, str(missing))
        check("write off without a dry run",
                  "disabled" in window.b_write.state())

        # 7. once the dry run is done, it lights up
        window.dry = module.A.DryRun()
        window.dry_stamp = window._dry_signature()
        window._update_write_state()
        check("no requirement missing", window._missing_requirements() == [])
        check("write enabled", "disabled" not in window.b_write.state())

        # 8. if the image changes the dry run voids itself
        window.var_image.set(IMAGE_B)
        window._update_write_state()
        check("changing the image voids the dry run",
                  module.App._dry_signature(window) != window.dry_stamp)
        check("write off again after the change",
                  "disabled" in window.b_write.state())
        window.var_image.set(IMAGE_A)
        window.dry_stamp = window._dry_signature()
        window._update_write_state()

        # 9. immagine di dimensione sbagliata -> di nuovo bloccato
        fake_one = os.path.join(os.path.dirname(os.path.abspath(__file__)), "short.rom")
        with open(fake_one, "wb") as f:
            f.write(b"\x00" * 1024)
        window.var_image.set(fake_one)
        window._update_write_state()
        missing = window._missing_requirements()
        check("wrong size rejected",
                  any("1024" in m for m in missing), str(missing))
        check("write off again", "disabled" in window.b_write.state())

        # 10. the log writes
        window.log("log test")
        check("log filled", len(window.log_lines) == 1)

        # 11. what the worker thread puts on the queue is what the window
        # takes off it.
        # ⚠️ This is not ceremony. The two ends are coupled by a string, and
        # a rename left them saying "event" on one side and "evento" on the
        # other: the live chip map and the progress bar went quietly dead,
        # and every existing check still passed.
        import chipmap as _cm
        window._prepare_map()
        window._line_from_thread("from the thread")
        window._event_from_thread("erase", 0, 0x0FFF)
        window._pump()
        check("a line from the thread reaches the log",
                  window.log_lines[-1].endswith("from the thread"),
                  window.log_lines[-1])
        check("an erase event reaches the chip map",
                  _cm.ERASED_BLOCK in window.chip_map.states,
                  str(sorted(set(window.chip_map.states))))
        # ⚠️ after this one the map is repainted for the phase, so the erase
        # has to be looked at first
        window._event_from_thread("phase", "READ", 50)
        window._pump()
        check("a phase event reaches the progress",
                  window.phase == "READ", str(window.phase))


        # 12. the pico module: UF2 format, no hardware needed
        import pico
        nuke = os.path.join(WORK_DIR, "azzera.uf2")
        pico.make_eraser(nuke, size=64 * 1024)
        blocks, first, last, families = pico.read_uf2(nuke)
        check("generated uf2: 256 blocks", blocks == 256, str(blocks))
        check("generated uf2: starts at the flash base",
                  first == pico.BASE_FLASH, hex(first))
        check("generated uf2: covers the 64 KiB asked for",
                  last == pico.BASE_FLASH + 64 * 1024 - 1, hex(last))
        check("generated uf2: RP2040 family",
                  families == {pico.FAMILY_RP2040})
        with open(nuke, "rb") as f:
            header = f.read(pico.BLOCK)
        check("generated uf2: payload all 0xFF",
                  header[32:32 + pico.PAYLOAD] == b"\xff" * pico.PAYLOAD)

        # ⚠️ A copy that never starts is NOT a successful copy. Any
        # OSError used to be enough to say "done", and a board fresh into
        # BOOTSEL really does produce one: the result was firmware never
        # written and a green message. Seen on the hardware.
        attempts = pico.COPY_ATTEMPTS
        pico.COPY_ATTEMPTS = 1
        fake = pico.Board(os.path.join(WORK_DIR, "no-such-disk") + os.sep,
                            "RP2040", "RPI-RP2", 0)
        done, reason = pico.install(nuke, fake)
        pico.COPY_ATTEMPTS = attempts
        check("copy never started: it fails, it does not say 'done'",
                  not done and reason, str(reason))

        # a corrupted file has to be rejected BEFORE it reaches the board
        broken = os.path.join(WORK_DIR, "rotto.uf2")
        with open(nuke, "rb") as f:
            data = bytearray(f.read())
        data[4] = (data[4] + 1) % 256          # sporca la seconda magia
        with open(broken, "wb") as f:
            f.write(data)
        try:
            pico.read_uf2(broken)
            check("corrupted uf2 rejected", False, "non ha protestato")
        except ValueError as e:
            check("corrupted uf2 rejected", True, "%s" % e)
        try:
            pico.read_uf2(os.path.join(WORK_DIR, "layout.txt"))
            check("non-uf2 file rejected", False, "non ha protestato")
        except ValueError:
            check("non-uf2 file rejected", True)

        check("no board in BOOTSEL right now",
                  isinstance(pico.boards_in_bootsel(), list))

        # ⚠️ This is the case that was wrong: a real Pico's Board-ID is
        # "RPI-RP2", and the first version rejected it because it did not
        # START with "RP2". Only the hardware noticed.
        check("recognises the real Board-ID (RPI-RP2)",
                  pico.is_rp2040("Raspberry Pi RP2", "RPI-RP2"))
        check("recognises it from the model alone too",
                  pico.is_rp2040("Raspberry Pi RP2040", ""))
        check("rejects any old disk",
                  not pico.is_rp2040("SanDisk Cruzer", "USB-DISK"))


        # 13. the registry: the two identifiers of one board
        import boards
        a = boards.Registry()
        a.set_name("banco 1", run="5303284738DE6E1C")
        check("name found from the running serial",
                  a.name(run="5303284738DE6E1C") == "banco 1")
        check("in BOOTSEL it does not know it yet",
                  a.name(boot="E0C9125B0D9B") is None)
        # ⚠️ the two serials are DIFFERENT on the same board: they are
        # by watching it move from one state to the other
        a.link("5303284738DE6E1C", "E0C9125B0D9B")
        check("once linked it knows it in BOOTSEL too",
                  a.name(boot="E0C9125B0D9B") == "banco 1")
        check("one board only in the list", len(a.as_list()) == 1,
                  str(a.as_list()))

        # two separate entries that turn out to be one board: they merge
        b = boards.Registry()
        b.set_name("visto acceso", run="AAAA")
        b.set_name("visto in bootsel", boot="BBBB")
        b.link("AAAA", "BBBB")
        check("the two entries merge into one", len(b.as_list()) == 1,
                  str(b.as_list()))
        check("it keeps the name already given", b.name(boot="BBBB") == "visto acceso")

        # ⚠️ Found on the bench, upgrading a real installation: up to 1.2.0
        # the name was stored under "nome", and the board came back nameless.
        old = boards.Registry([{"nome": "banco A", "run": "DDDD", "boot": None}])
        check("a name written by 1.2.0 is still read",
                  old.name(run="DDDD") == "banco A", str(old.as_list()))
        check("and it is saved back under the English key",
                  "nome" not in old.as_list()[0], str(old.as_list()))

        empty_one = boards.Registry()
        empty_one.set_name("tolgo", run="CCCC")
        empty_one.set_name("", run="CCCC")
        check("an empty name forgets the board", empty_one.as_list() == [])
        check("serial tail for the confirmation",
                  boards.tail_of("5303284738DE6E1C") == "6E1C")

        # 14. the confirmation takes ONLY the word it asked for
        real_wait = window.wait_window
        window.wait_window = lambda *a, **k: None
        d = module.Confirm(window, window.L, "test", window.theme,
                            word="6E1C")
        window.wait_window = real_wait
        check("confirm-by-word: starts disabled",
                  "disabled" in d.ok.state())
        d.variable.set("CANCELLA")
        window.update()
        check("another word that is right elsewhere is not enough",
                  "disabled" in d.ok.state())
        d.variable.set("6e1c")
        window.update()
        check("accepts the serial digits, lower case too",
                  "disabled" not in d.ok.state())
        d.destroy()


        # 15. write protection: reading it, overlap, blocking
        free_space = module.fr.parse_protection([
            "Protection range: start=0x00000000 length=0x00000000 (none)",
            "Protection mode: disabled"])
        check("absent protection recognised",
                  free_space.supported and not free_space.active)

        whole = module.fr.parse_protection([
            "Protection range: start=0x00000000 length=0x01000000 (all)",
            "Protection mode: hardware"])
        check("whole-chip protection recognised", whole.active, whole.mode)
        check("whole-chip protection covers the uefi region",
                  whole.overlaps(0xAE0000, 0xC22FFF))

        top = module.fr.parse_protection([
            "Protection range: start=0x00F00000 length=0x00100000 (upper 1/16)",
            "Protection mode: hardware"])
        check("upper protection does NOT cover the uefi region",
                  not top.overlaps(0xAE0000, 0xC22FFF))
        check("but it does cover the last piece of chip", top.overlaps(0xF80000, 0xF80FFF))

        muto = module.fr.parse_protection(
            ["Failed to get WP status: WP operations are not supported"], False)
        check("a chip that does not answer: nothing is invented",
                  not muto.supported and not muto.active)

        # ⚠️ The point: a protected chip must NOT let the write start,
        # because it would take the commands and change nothing.
        window.protection = whole
        window._update_write_state()
        missing = window._missing_requirements()
        check("a protected chip blocks the write",
                  any("protet" in m or "protect" in m for m in missing),
                  str(missing))
        check("write button off with a protected chip",
                  "disabled" in window.b_write.state())
        window.protection = top
        window._update_write_state()
        check("protection outside the region does not block",
                  not any("protet" in m or "protect" in m
                          for m in window._missing_requirements()),
                  str(window._missing_requirements()))
        window.protection = free_space
        window._update_write_state()


        # 16. firmware version: read from the name, compared with ours
        import serprog as _sp
        check("version pulled out of the name",
                  _sp.split_version("pico-serprog1.1") == ("pico-serprog", "1.1"))
        check("bare name: no version",
                  _sp.split_version("pico-serprog") == ("pico-serprog", None))
        check("it also takes the form with a space and a v",
                  _sp.split_version("pico-serprog v2.0")[1] == "2.0")
        # ⚠️ No version does NOT mean unknown: it means older than
        # 1.1, which is the first to declare it. Treat it as old.
        check("silent firmware = old firmware",
                  _sp.is_older(None, "1.1"))
        check("same version: no update",
                  not _sp.is_older("1.1", "1.1"))
        check("1.0 is older than 1.1", _sp.is_older("1.0", "1.1"))
        # confronto numerico, non alfabetico: "1.10" > "1.9"
        check("1.10 is not older than 1.9",
                  not _sp.is_older("1.10", "1.9"))
        check("with no firmware of ours, nothing is offered",
                  not _sp.is_older("1.0", None))

        import pico as _pk
        # the shipped version is not written in here: it changes every build,
        # and a test that has to be updated by hand gets updated wrong
        shipped = _pk.shipped_version(os.path.join(ROOT_DIR, "firmware"))
        check("the shipped version is read from the firmware folder",
                  bool(shipped) and re.match(r"^\d+\.\d+$", shipped),
                  str(shipped))
        check("folder without VERSION: no version, and no explosion",
                  _pk.shipped_version(WORK_DIR) is None)

        # the Update button appears only when there is something to update
        window.board_firmware = shipped
        window._update_firmware_row()
        check("firmware up to date: no Update button",
                  not window.b_update.winfo_ismapped())


        # 17. regioni ricavate dall'immagine: IFD, FMAP, AMD
        import struct as _st
        import regions as _rg

        # --- Intel descriptor: signature at 0x10, FRBA and region count in FLMAP0
        intel = bytearray(b"\xff" * (2 * 1024 * 1024))
        _st.pack_into("<I", intel, 0x10, _rg.IFD_SIGNATURE)
        frba = 0x40
        _st.pack_into("<I", intel, 0x14, (2 << 24) | (frba >> 4 << 16))
        def _entry_of(start, end):
            return ((end >> 12) << 16) | (start >> 12)
        _st.pack_into("<I", intel, frba + 0, _entry_of(0x000000, 0x000FFF))  # fd
        _st.pack_into("<I", intel, frba + 4, _entry_of(0x100000, 0x1FFFFF))  # bios
        _st.pack_into("<I", intel, frba + 8, 0x00007FFF)                 # assente
        source, found = _rg.find_regions(bytes(intel))
        names = [r.name for r in found]
        check("Intel descriptor recognised", source == "ifd", str(names))
        check("fd and bios regions read", names == ["fd", "bios"], str(names))
        check("the bios region has the right bounds",
                  found[1].start == 0x100000 and found[1].end == 0x1FFFFF,
                  "%06X-%06X" % (found[1].start, found[1].end))
        # ⚠️ base > limit means "region not present", it is not an error
        # da segnalare: va semplicemente saltata.
        check("region declared absent: skipped", len(found) == 2)

        # --- FMAP
        fmap = bytearray(b"\x00" * (1024 * 1024))
        where = 0x1000                      # aligned to 64, as the spec wants
        _rg.FMAP_HEADER.pack_into(fmap, where, b"__FMAP__", 1, 1, 0, len(fmap),
                                 b"test", 2)
        base = where + _rg.FMAP_HEADER.size
        _rg.FMAP_AREA.pack_into(fmap, base, 0, 0x8000, b"BOOT_STUB", 0)
        _rg.FMAP_AREA.pack_into(fmap, base + _rg.FMAP_AREA.size,
                                0x8000, 0x8000, b"RW_SECTION", 0)
        source, found = _rg.find_regions(bytes(fmap))
        check("FMAP recognised", source == "fmap", str(source))
        check("FMAP areas with their names",
                  [r.name for r in found] == ["BOOT_STUB", "RW_SECTION"],
                  str([r.name for r in found]))
        check("the area size is respected",
                  found[0].end == 0x7FFF, hex(found[0].end))

        # an FMAP pointing outside the image is not its own: discard it
        short = bytearray(b"\x00" * 0x20000)
        _rg.FMAP_HEADER.pack_into(short, 0x1000, b"__FMAP__", 1, 1, 0,
                                 0x1000000, b"other", 1)
        _rg.FMAP_AREA.pack_into(short, 0x1000 + _rg.FMAP_HEADER.size,
                                0, 0x1000000, b"WHOLE", 0)
        check("another image's FMAP: rejected",
                  _rg.fmap_regions(bytes(short)) == [])

        # --- AMD structure: EFS with a BIOS directory
        amd = bytearray(b"\xff" * (16 * 1024 * 1024))
        efs = 0x820000
        _st.pack_into("<I", amd, efs, _rg.EFS_SIGNATURE)
        _st.pack_into("<I", amd, efs + 0x1C, 0xFFAB0000)      # bios1_entry
        amd[0xAB0000:0xAB0004] = b"$BHD"
        _st.pack_into("<I", amd, 0xAB0008, 2)                 # due voci
        _rg.__dict__["_BHD_ENTRY"].pack_into(
            amd, 0xAB0010, 0x60, 0, 0, 0x2000, 0xFFAB1000, 0)
        _rg.__dict__["_BHD_ENTRY"].pack_into(
            amd, 0xAB0010 + 24, 0x62, 0, 0, 0x1FE000, 0xFFE02000, 0)
        source, found = _rg.find_regions(bytes(amd))
        names = [r.name for r in found]
        check("AMD structure recognised", source == "amd", str(names))
        check("apcb and BIOS image found",
                  "apcb" in names and "bios" in names, str(names))
        # ⚠️ AMD addresses are the ones the CPU sees (0xFFE02000): unless
        # they are brought back inside the image, the region lands off-chip.
        bios = [r for r in found if r.name == "bios"][0]
        check("AMD address brought back inside the image",
                  bios.start == 0xE02000 and bios.end == 0xFFFFFF,
                  "%06X-%06X" % (bios.start, bios.end))
        check("the directory covers the table, not what it points at",
                  [r for r in found if r.name == "bios_dir"][0].end
                  == 0xAB0010 + 2 * 24 - 1)

        # --- an image that says nothing about itself must invent nothing
        silent_image = b"\x00" * (1024 * 1024)
        check("image with no map: no regions",
                  _rg.find_regions(silent_image) == (None, []))

        # --- the generated layout is the one flashrom expects
        text = _rg.as_layout(found, len(amd))
        check("layout with real names",
                  "00e02000:00ffffff bios" in text, repr(text))
        duplicates = _rg.as_layout([_rg.Region("bios", 0, 0xFF),
                                  _rg.Region("bios", 0x100, 0x1FF)], 0x200)
        check("repeated names made unique",
                  duplicates.split()[1] == "bios" and "bios_1" in duplicates,
                  repr(duplicates))


        # 18. board profiles
        import profiles as _pf
        check("unknown profile: falls back to the default",
                  _pf.by_key("no-such-board").key == _pf.DEFAULT_KEY)
        check("profile names follow the language",
                  _pf.by_key("generic").text("name", "en") == "Generic board")
        bc = _pf.by_key("bc250")
        check("the BC-250 profile knows both fingerprints",
                  len(bc.md5) == 2 and all(len(v) == 2 for v in bc.md5.values()))

        # ⚠️ Deviations are warnings, not prohibitions: they have to show
        # up, and nothing more.
        check("chip as expected: no deviation",
                  _pf.deviations(bc, found_chip="MX25L12835F/MX25L12873F",
                                  found_size=16 * 1024 * 1024,
                                  regions=("bios", "apcb", "psp")) == [])
        out = dict(_pf.deviations(bc, found_chip="W25Q64.V",
                                     found_size=8 * 1024 * 1024,
                                     regions=("bios",)))
        check("different chip reported", "prof_chip_differs" in out,
                  str(sorted(out)))
        check("different size reported", "prof_size_differs" in out)
        check("missing regions reported",
                  "apcb" in out.get("prof_regions_missing", {}).get("which", ""),
                  str(out.get("prof_regions_missing")))
        check("profile with no expectations: invents no deviations",
                  _pf.deviations(_pf.by_key("generic"),
                                  found_chip="qualunque cosa",
                                  found_size=1234) == [])

        # changing profile changes the suggested models and the warnings
        window.var_profile.set(_pf.by_key("generic").text("name",
                                                             window.L.code))
        window._profile_changed()
        check("generic profile: no suggested model",
                  list(window.combo_chip.cget("values")) == [""],
                  str(window.combo_chip.cget("values")))
        check("the reminder does not say the same sentence twice",
                  window.lbl_reminder.cget("text").count(
                      window.L("reminder")) == 1)
        window.var_profile.set(bc.text("name", window.L.code))
        window._profile_changed()
        check("back on the BC-250, the models return",
                  len(window.combo_chip.cget("values")) > 1)

        # 19. both wiring drawings really draw
        # ⚠️ No test used to open the drawing: a mistake in there would
        # only have shown by opening it by hand.
        import wiring as _sc
        for clip in (False, True):
            wiring_window = _sc.Diagram(window, window.theme, window.L,
                                         clip=clip)
            wiring_window.update_idletasks()
            wiring_window.draw()
            how_many = len(wiring_window.canvas.find_all())
            check("wiring drawn, %s" % ("with the clip" if clip
                                        else "with the header"),
                      how_many > 60, "%d elementi" % how_many)
            wiring_window.destroy()


        # 20. the automatic comparison with the previous backup
        import time as _t
        empty = bytes(bytearray(16384))
        backup_dir = os.path.join(WORK_DIR, "backup")
        os.makedirs(backup_dir)
        key = window.profile.key
        one = os.path.join(backup_dir, "%s-letto-A.rom" % key)
        two = os.path.join(backup_dir, "%s-letto-B.rom" % key)
        for path in (one, two):
            with open(path, "wb") as f:
                f.write(empty)
            _t.sleep(0.05)
        check("the previous one is the newest, excluding the new one",
                  window._previous_reads(backup_dir, excluded=two) == [one],
                  str(window._previous_reads(backup_dir, excluded=two)))

        before = len(window.log_lines)
        window._compare_with_previous(backup_dir, two)
        said = " ".join(window.log_lines[before:])
        check("identical reads: it says so",
                  "denti" in said or "dentical" in said, said)

        # ⚠️ The real question is the other one: what changed since yesterday.
        with open(two, "wb") as f:
            f.write(empty[:8192] + bytes(bytearray([0xAA]) * 4096) + empty[:4096])
        before = len(window.log_lines)
        window._compare_with_previous(backup_dir, two)
        said = " ".join(window.log_lines[before:])
        check("difference found and located", "0x002000" in said, said)

        # a lone read in a folder has nothing to compare against
        empty_one = os.path.join(WORK_DIR, "backup-vuoto")
        os.makedirs(empty_one)
        before = len(window.log_lines)
        window._compare_with_previous(empty_one, one)
        check("first read: it says so instead of staying quiet",
                  len(window.log_lines) > before)

        # different sizes: no comparison, and no explosion
        short = os.path.join(backup_dir, "%s-letto-C.rom" % key)
        with open(short, "wb") as f:
            f.write(empty[:4096])
        before = len(window.log_lines)
        window._compare_with_previous(backup_dir, short)
        check("different sizes: it says so and carries on",
                  len(window.log_lines) > before)


        # 21. asking the chip who it is, without flashrom
        import serprog as _sp2

        class FakePort(object):
            """A paper chip: it answers the protocol and nothing more."""

            def __init__(self, jedec=(0xC8, 0x40, 0x18), sfdp=True):
                self.jedec = jedec
                self.has_sfdp = sfdp
                self.output = bytearray()
                self.inside = bytearray()

            # -- lato serprog
            def reset_input_buffer(self):
                pass

            def flush(self):
                pass

            def write(self, data):
                data = bytearray(data)
                while data:
                    command = data.pop(0)
                    if command == _sp2.SYNCNOP:
                        self.inside += bytearray([_sp2.NAK, _sp2.ACK])
                    elif command == _sp2.S_PIN_STATE:
                        data.pop(0)
                        self.inside.append(_sp2.ACK)
                    elif command == _sp2.O_SPIOP:
                        wlen = data[0] | (data[1] << 8) | (data[2] << 16)
                        rlen = data[3] | (data[4] << 8) | (data[5] << 16)
                        del data[:6]
                        payload = bytearray(data[:wlen])
                        del data[:wlen]
                        self.inside.append(_sp2.ACK)
                        self.inside += self._answer(payload, rlen)
                    else:
                        self.inside.append(_sp2.ACK)

            def read(self, how_many=1):
                chunk = self.inside[:how_many]
                del self.inside[:how_many]
                return bytes(chunk)

            def close(self):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            # -- lato chip
            def _answer(self, payload, rlen):
                if payload and payload[0] == _sp2.CMD_JEDEC:
                    return bytearray(self.jedec)[:rlen]
                if payload and payload[0] == _sp2.CMD_SFDP:
                    if not self.has_sfdp:
                        return bytearray(rlen)          # all zeros: no SFDP
                    address = (payload[1] << 16) | (payload[2] << 8) | payload[3]
                    return self._sfdp(address, rlen)
                return bytearray(rlen)

            def _sfdp(self, address, rlen):
                if address == 0:
                    # signature, minor, major, nph=0 (one table), protocol
                    header = bytearray(b"SFDP") + bytearray([6, 1, 0, 0xFF])
                    return header[:rlen]
                if address == 8:
                    # id 0x00, lunghezza 4 dword, puntatore 0x100
                    return bytearray([0x00, 6, 1, 4, 0x00, 0x01, 0x00, 0xFF])[:rlen]
                if address == 0x100:
                    # dword1 anything, dword2 = density in bits minus one
                    bits = 16 * 1024 * 1024 * 8
                    d = bits - 1
                    return (bytearray([0, 0, 0, 0])
                            + bytearray([d & 0xFF, (d >> 8) & 0xFF,
                                         (d >> 16) & 0xFF, (d >> 24) & 0xFF])
                            + bytearray(56))[:rlen]
                return bytearray(rlen)

        real_open = _sp2.serial.Serial if _sp2.HAS_SERIAL else None
        fake = FakePort()
        _sp2.serial.Serial = lambda *a, **k: fake
        identity = _sp2.identify_chip("COMFINTA")
        check("the chip answers with its JEDEC id",
                  identity.ok and identity.jedec == "C8 40 18",
                  identity.error or identity.jedec)
        check("vendor recognised from the code",
                  identity.vendor_name == "GigaDevice")
        check("size taken from the SFDP",
                  identity.size == 16 * 1024 * 1024, str(identity.size))
        check("the SFDP is reported", identity.sfdp)

        # ⚠️ This is the distinction that matters: unknown chip or loose
        # wire. A dead bus reads all 0xFF, and that is not a chip.
        _sp2.serial.Serial = lambda *a, **k: FakePort(jedec=(0xFF, 0xFF, 0xFF))
        muto = _sp2.identify_chip("COMFINTA")
        check("dead bus: not mistaken for a chip",
                  muto.ok and not muto.answers)
        _sp2.serial.Serial = lambda *a, **k: FakePort(jedec=(0, 0, 0))
        check("all zeros: that is not a chip either",
                  not _sp2.identify_chip("COMFINTA").answers)

        # without SFDP the size comes from the third JEDEC byte
        _sp2.serial.Serial = lambda *a, **k: FakePort(jedec=(0xEF, 0x40, 0x16),
                                                        sfdp=False)
        old_one = _sp2.identify_chip("COMFINTA")
        check("without SFDP the size comes from the JEDEC code",
                  old_one.size == 4 * 1024 * 1024 and not old_one.sfdp,
                  str(old_one.size))
        check("unknown vendor: no name invented",
                  _sp2.Identity(vendor_id=0x77, kind=1,
                                capacity=0x18).vendor_name is None)
        if real_open is not None:
            _sp2.serial.Serial = real_open


        # 22. the chip voltage, worked out from the model
        import voltage as _tv
        for name, expected in (("MX25L12835F/MX25L12873F", 3.3),
                             ("MX25U12835F", 1.8),
                             ("W25Q128.V", 3.3),
                             ("W25Q128.JW.DTR", 1.8),
                             ("W25Q64FW", 1.8),
                             ("GD25LQ128", 1.8),
                             ("GD25Q128", 3.3),
                             ("IS25WP128", 1.8),
                             ("IS25LP128", 3.3),
                             ("MT25QU256", 1.8),
                             ("MT25QL256", 3.3)):
            volts, family = _tv.voltage_of(name)
            check("voltage of %s" % name, volts == expected,
                      "%s (%s)" % (volts, family))
        # ⚠️ A model that is not recognised is NOT a 3.3 V chip: it is one
        # a chip we cannot tell about, and that has to be said as such.
        check("unknown model: no guessing",
                  _tv.voltage_of("something never seen") == (None, None))
        check("is_low_voltage answers None when it does not know",
                  _tv.is_low_voltage("never seen") is None)

        # a 1.8 V chip blocks the write until the shifter is confirmed,
        # and the checkbox only appears in that case
        window._check_voltage("W25Q128.V")
        check("3.3 V chip: no extra checkbox",
                  not window.check_shifter.winfo_ismapped()
                  and not window.chip_is_1v8)
        window._check_voltage("MX25U12835F")
        window.update()
        check("1.8 V chip recognised", window.chip_is_1v8)
        check("the level-shifter checkbox appears",
                  window.check_shifter.winfo_ismapped())
        check("and the write stays blocked",
                  any("adattatore" in m or "shifter" in m
                      for m in window._missing_requirements()),
                  str(window._missing_requirements()))
        window.var_shifter.set(1)
        check("with the shifter confirmed, that requirement clears",
                  not any("adattatore" in m or "shifter" in m
                          for m in window._missing_requirements()))
        window._check_voltage("W25Q128.V")
        window.var_shifter.set(0)

        # 23. the level-shifter schematic draws
        import level_shifter as _ad
        shifter_window = _ad.LevelShifter(window, window.theme, window.L)
        # ⚠️ The size matters: with no geometry the canvas is one pixel wide,
        # scale bottoms out and the fonts, which do not go below 6 points,
        # take twice the room. It has to be tested at the size it was
        # drawn for.
        shifter_window.geometry("1080x800")
        shifter_window.update()
        shifter_window.draw()
        how_many = len(shifter_window.canvas.find_all())
        check("level-shifter schematic drawn", how_many > 60,
                  "%d elementi" % how_many)

        # ⚠️ The BOM has to stay CONCRETE. "A MOSFET" and "a regulator" are
        # are not enough to buy the right parts, and it is precisely the
        # wrong part (2N7002 instead of BSS138) that the eye cannot catch.
        bom = " ".join("%s %s %s" % p for p in _ad.PARTS)
        for expected in ("BSS138", "onsemi", "Yageo", "Microchip", "Murata",
                       "SOT-23", "0603"):
            check("distinta: c'e' %s" % expected, expected in bom)
        check("BOM: the resistors are 1 kOhm, not 10",
                  "1 k" in bom and "10 k" not in bom)
        check("BOM: every part has a ref, a value and part numbers",
                  all(len(p) == 3 and all(p) for p in _ad.PARTS))

        # the drawing must really contain them, not just the data structure
        texts = [shifter_window.canvas.itemcget(i, "text")
                 for i in shifter_window.canvas.find_all()
                 if shifter_window.canvas.type(i) == "text"]
        joined = " ".join(texts)
        check("the drawing shows the part numbers, not just the refs",
                  "BSS138LT1G" in joined and "MCP1700T-1802E/TT" in joined)
        check("the drawing warns about the 2N7002",
                  "2N7002" in joined)
        # and it all has to fit: the last note must not fall outside
        bounds = shifter_window.canvas.bbox("all")
        top = shifter_window.canvas.winfo_height()
        check("the content fits inside the window",
                  bounds and bounds[3] <= top,
                  "%d pixel su %d" % (bounds[3] if bounds else -1, top))
        shifter_window.destroy()


        # 24. flashrom's chip list, and the model search
        FAKE_L = [
            "flashrom v1.7.0 on Windows",
            "",
            "Supported flash chips (total: 4):",
            "",
            "Vendor                       Device                               "
            "Test   Known   Size   Type",
            "                                                                  "
            "OK     Broken  [kB]",
            "",
            "(P = PROBE, R = READ, E = ERASE, W = WRITE, B = block-protect)",
            "",
            "AMD                          Am29F010                             "
            "                    128  Parallel",
            "Macronix                     MX25L12835F/                         "
            "PREW            16384  SPI",
            "                             MX25L12873F",
            "Winbond                      W25Q128.JW.DTR                       "
            "PREW            16384  SPI",
            "Winbond                      W25Q64.V                             "
            "PREW             8192  SPI",
        ]
        listing = module.fr.parse_chip_list(FAKE_L)
        check("listing: four chips read", len(listing) == 4, str(len(listing)))
        # ⚠️ The real name is the WHOLE one: flashrom rejects just the first line.
        check("name split over several lines stitched back",
                  listing[1].name == "MX25L12835F/MX25L12873F", listing[1].name)
        check("size and type read",
                  listing[1].kb == 16384 and listing[1].spi,
                  "%s %s" % (listing[1].kb, listing[1].kind))
        check("the parallel chip is not SPI", not listing[0].spi)
        check("the tests flashrom declares are kept",
                  listing[1].tested == "PREW" and listing[1].well_tested,
                  listing[1].tested)
        check("a chip with no tests does not pass for tested",
                  not listing[0].well_tested)

        # the dropdown: profile models first, then every SPI chip, no duplicates
        window.known_chips = listing
        window._fill_models()
        values = list(window.combo_chip.cget("values"))
        check("dropdown: no parallel chip",
                  "Am29F010" not in values, str(values[:6]))
        check("dropdown: the listing's SPI chips are there",
                  "W25Q128.JW.DTR" in values and "W25Q64.V" in values)
        check("dropdown: no duplicates",
                  len(values) == len(set(values)), str(len(values)))
        check("dropdown: the profile's models stay on top",
                  values[1] == window.profile.chip[0], str(values[:3]))

        # 25. the search window filters and returns the chip that was picked
        import chip_search as _rc
        picked = []
        search_window = _rc.ChipSearch(window, window.theme, window.L, listing,
                                 picked.append)
        search_window.update_idletasks()
        check("search: shows SPI chips only",
                  len(search_window.shown) == 3, str(len(search_window.shown)))
        search_window.var_filter.set("winbond 64")
        search_window.update_idletasks()
        check("search: the filter crosses vendor and model",
                  [c.name for c in search_window.shown] == ["W25Q64.V"],
                  str([c.name for c in search_window.shown]))
        search_window.var_filter.set("jw")
        search_window.update_idletasks()
        search_window._focus_first()
        search_window.pick()
        check("search: returns the chip that was picked",
                  len(picked) == 1 and picked[0].name == "W25Q128.JW.DTR",
                  str(picked))
        check("search: closes after the pick",
                  not search_window.winfo_exists())


        # 25b. the update check, without touching the network
        # ⚠️ Everything here is fed a fabricated answer. A test that reaches
        # GitHub tests GitHub, and fails on a train.
        import update as _up
        VERO = {"tag_name": "v9.9.9", "html_url": "https://github.com/x/y/z",
                "assets": [{"name": "SPIranha-Setup-9.9.9.exe", "size": 123,
                            "browser_download_url":
                            "https://github.com/MTSistemi/SPIranha/releases/"
                            "download/v9.9.9/SPIranha-Setup-9.9.9.exe"}]}
        r = _up.from_json(VERO)
        check("update: the tag is read and the v dropped",
                  r.ok and r.version == "9.9.9", str(r.version))
        check("update: a later version is seen as newer", r.newer)
        check("update: the installer is the asset it picks",
                  r.url.endswith("SPIranha-Setup-9.9.9.exe"), str(r.url))
        vecchia = dict(VERO, tag_name="v0.0.1")
        check("update: an older version is not offered",
                  not _up.from_json(vecchia).newer)
        uguale = dict(VERO, tag_name="v" + _up.VERSION)
        check("update: the same version is not offered",
                  not _up.from_json(uguale).newer)
        check("update: a draft is ignored",
                  not _up.from_json(dict(VERO, draft=True)).ok)
        check("update: a pre-release is ignored",
                  not _up.from_json(dict(VERO, prerelease=True)).ok)
        check("update: a release with no installer offers nothing",
                  not _up.from_json(dict(VERO, assets=[])).ok)
        # ⚠️ the address is not taken on trust: an asset pointing elsewhere
        # is the shape a supply-chain attack takes
        altrove = {"tag_name": "v9.9.9", "assets": [
            {"name": "SPIranha-Setup-9.9.9.exe", "size": 1,
             "browser_download_url": "https://example.invalid/setup.exe"}]}
        check("update: an asset hosted elsewhere is refused",
                  not _up.from_json(altrove).ok)
        check("update: http is refused",
                  not _up._https_to_github(
                      "http://github.com/MTSistemi/SPIranha/x.exe"))
        check("update: a lookalike host is refused",
                  not _up._https_to_github("https://github.com.evil.tld/x.exe"))
        try:
            _up.download("https://example.invalid/x.exe")
            check("update: it will not download from elsewhere", False)
        except ValueError:
            check("update: it will not download from elsewhere", True)
        # ⚠️ our own unsigned .ico stands in for "a file that is not our
        # signed installer": it must be refused, not merely reported
        ok_firma, perche = _up.trusted(os.path.join(ROOT_DIR, "SPIranha.ico"))
        check("update: an unsigned file is refused", not ok_firma, str(perche))
        check("update: the check can be turned off",
                  window.settings.get("check_updates") is False)
        check("update: with it off, no banner", not window.up_banner.winfo_ismapped())

        # 26. the page to print: colours flipped and the drawing inside
        import printing as _st
        import xml.etree.ElementTree as _xml

        # ⚠️ Flipping the lightness is NOT making a negative: red has to
        # stay red, or the printed schematic tells of another circuit.
        check("dark ground -> white paper",
                  _st.for_print("#0B1119") > "#E0", _st.for_print("#0B1119"))
        check("light text -> dark ink",
                  _st.for_print("#E4EDF4") < "#40", _st.for_print("#E4EDF4"))
        red = _st.for_print("#E5484D")
        r, g, b = (int(red[i:i + 2], 16) for i in (1, 3, 5))
        check("red stays red", r > g + 40 and r > b + 40, red)
        check("no colour stays no colour", _st.for_print("") is None)

        shifter_window = _ad.LevelShifter(window, window.theme, window.L)
        shifter_window.geometry("1080x800")
        shifter_window.update()
        shifter_window.draw()
        shifter_window.canvas.delete("pdf")
        area = [shifter_window._s(v) for v in _ad.DRAWING_AREA]
        drawing = _st.svg_from_canvas(shifter_window.canvas, area)
        try:
            tree_ = _xml.fromstring(drawing)
            valid = True
        except Exception:                                  # noqa: BLE001
            tree_, valid = None, False
        check("the SVG is valid XML", valid)
        # ⚠️ width AND height, not just the width: without the height Chrome
        # stampa calcola zero e la pagina esce vuota. E' successo.
        check("the SVG declares width and height",
                  valid and tree_.get("width") and tree_.get("height"),
                  "%s x %s" % (tree_.get("width") if valid else "?",
                               tree_.get("height") if valid else "?"))
        check("the SVG holds the drawing, not just the ground",
                  drawing.count("<polyline") > 10 and drawing.count("<text") > 5,
                  "%d linee, %d testi" % (drawing.count("<polyline"),
                                          drawing.count("<text")))
        check("the screen's dark ground is not in the SVG",
                  "#0B1119" not in drawing and "#141E29" not in drawing)

        page = _st.level_shifter_html(
            drawing, window.L,
            [(p[0], _ad.value_of(p, window.L.code), p[2]) for p in _ad.PARTS],
            _ad.CHANNELS, _ad.NOTES, window.L("ls_ready_made"),
            window.L("ls_title"), window.L("ls_sub"))
        check("the page carries the real part numbers",
                  "BSS138LT1G" in page and "MCP1700T-1802E/TT" in page)
        check("the page carries both tables",
                  page.count("<table") == 2, str(page.count("<table")))
        # ⚠️ Without the height cap the drawing grows taller than the sheet
        # and Chrome pushes it to the next page, leaving the first one empty:
        # it happened, and it does not show until you print.
        check("the CSS keeps the drawing inside the sheet",
                  "max-height" in page and "print-color-adjust" in page)
        check("two sheets, not one", page.count('class="sheet"') == 2)
        shifter_window.destroy()


        # 27. once a board is named, the dropdown must SHOW it
        # ⚠️ The port stays the same, but the label does not: Windows' old
        # description used to stay on show and the name looked lost.
        real_ports = module.serprog.list_serial_ports
        module.serprog.list_serial_ports = lambda: [
            ("COM9", "Dispositivo seriale USB (CAFE:4001)", True, "AABBCCDD")]
        try:
            window.detect_ports()
            first_label = window.var_port.get()
            check("with no name, the system description shows",
                      "Dispositivo" in first_label, first_label)
            window.known_boards.set_name("test bench", run="AABBCCDD")
            window.detect_ports()
            after = window.var_port.get()
            check("once named, the dropdown shows it straight away",
                      "test bench" in after, after)
            check("and the chosen port does not change",
                      window._chosen_port() == "COM9",
                      window._chosen_port())
            window.known_boards.set_name("", run="AABBCCDD")
        finally:
            module.serprog.list_serial_ports = real_ports
            window.detect_ports()

        # 11. the port list
        window.detect_ports()
        check("port detection does not blow up", True,
                  str(window.combo_port.cget("values")))
    except Exception:
        traceback.print_exc()
        results.append(("eccezione", False, ""))
    finally:
        window.destroy()


def main():
    global LAYOUT, IMAGE_A, IMAGE_B
    LAYOUT, IMAGE_A, IMAGE_B = make_fixtures()
    window = module.App()
    window.after(300, lambda: checks(window))
    window.mainloop()
    shutil.rmtree(WORK_DIR, ignore_errors=True)
    failed = [n for n, ok, _ in results if not ok]
    print("\n%d checks, %d failed" % (len(results), len(failed)))
    for n in failed:
        print("  FAILED:", n)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
