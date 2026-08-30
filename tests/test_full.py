# -*- coding: utf-8 -*-
"""The test that counts: the whole chain, against a chip EMULATED by flashrom.

It does not simulate the program: it drives the real window, its buttons and
its checks, with the real flashrom. The only difference is the programmer,
which instead of serprog is `dummy` -- a 16 MiB chip in memory, backed by a
file.

The central test follows the real BC-250 operation exactly: start from the
stock BIOS, write ONLY the uefi region taken from the modified BIOS, and at
the end the chip must be byte-for-byte identical to
bc250-risultato-atteso.rom.
"""
import hashlib
import io
import os
import shutil
import sys
import time
import traceback

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT_DIR)
# ⚠️ Settings go to a throw-away folder: these tests build the REAL
# window and save, and without this they rewrote the configuration of
# whoever was using the program.
os.environ["SPIRANHA_CONFIG"] = os.path.join(HERE, "config-for-tests")


import common as common_  # noqa: E402

BACKUP = common_.backup_or_skip()
EXE = common_.flashrom_or_skip()
WORK_DIR = os.path.join(HERE, "work")

import app as module  # noqa: E402
import flashrom as fr  # noqa: E402

STOCK, EXPECTED, LAYOUT = common_.test_files(BACKUP)
FAKE_CHIP = os.path.join(WORK_DIR, "chip-emulato.rom")

results = []


def check(name, condition, extra=""):
    results.append((name, bool(condition)))
    print("%-52s %s %s" % (name, "ok" if condition else "FAILED", extra))
    return bool(condition)


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def pump_until_idle(window, seconds=300):
    """Spins the event loop until the operation is done."""
    deadline = time.time() + seconds
    while window.busy and time.time() < deadline:
        window.update()
        time.sleep(0.02)
    window.update()
    return not window.busy


def dummy_programmer():
    return "dummy:emulate=W25Q128FV,image=%s" % FAKE_CHIP


def _write_temp(text):
    path = os.path.join(WORK_DIR, "layout-generato.txt")
    with open(path, "wb") as f:
        f.write(text.encode("ascii"))
    return path


def checks(window):
    try:
        # the emulated chip starts out with the board's STOCK BIOS
        shutil.copyfile(STOCK, FAKE_CHIP)
        check("emulated chip = stock BIOS", md5(FAKE_CHIP) == md5(STOCK))

        window.flash = fr.Flashrom(EXE, programmer=dummy_programmer())
        window.flashrom_version = window.flash.version() or ""
        check("flashrom answers", "flashrom" in window.flashrom_version.lower(),
                  window.flashrom_version)
        window.var_folder.set(WORK_DIR)
        window._update_flashrom_banner()

        # ---- 1. identificazione ------------------------------------
        window.identify_chip()
        pump_until_idle(window)
        check("chip identified", window.chip is not None,
                  window.chip.description if window.chip else "")
        check("size recognised = 16 MiB",
                  window.chip and window.chip.size == 16 * 1024 * 1024)

        check("protection read together with the chip",
                  window.protection is not None)
        check("the emulated chip is not protected",
                  window.protection is not None
                  and window.protection.supported
                  and not window.protection.active,
                  (window.protection.mode or "?") if window.protection else "")

        # ---- 2. the double read ------------------------------------
        window.read_and_verify()
        pump_until_idle(window)
        check("double read verified",
                  window.verified_read == md5(STOCK),
                  str(window.verified_read)[:12])
        read_bytes = [f for f in os.listdir(WORK_DIR) if f.startswith("bc250-read-")]
        verifications = [f for f in os.listdir(WORK_DIR) if f.startswith("bc250-verify-")]
        check("backup saved", len(read_bytes) == 1, str(read_bytes))
        check("second read deleted", verifications == [], str(verifications))
        check("known fingerprint recognised",
                  any("originale" in r for r in window.log_lines))

        # ---- 3. the block when the two reads disagree ---------------
        real_md5 = module.md5_of_file
        calls = {"n": 0}

        def md5_wobbly(path, stop_flag=None):
            calls["n"] += 1
            real = real_md5(path, stop_flag)
            return real if calls["n"] % 2 else "0" * 32   # the first one lies

        window.verified_read = None
        module.md5_of_file = md5_wobbly
        window.read_and_verify()
        pump_until_idle(window)
        module.md5_of_file = real_md5
        check("reads disagree -> read NOT validated",
                  window.verified_read is None)
        check("reads disagree -> write blocked",
                  "disabled" in window.b_write.state())
        left_behind = [f for f in os.listdir(WORK_DIR) if f.startswith("bc250-verify-")]
        check("reads disagree -> both files kept", len(left_behind) == 1)

        # put a good read back in place
        for f in left_behind:
            os.remove(os.path.join(WORK_DIR, f))
        window.read_and_verify()
        pump_until_idle(window)
        check("good read taken again", window.verified_read == md5(STOCK))

        # ---- 4. the confirmation dialog ----------------------------
        real_wait = window.wait_window
        window.wait_window = lambda *a, **k: None
        dialog = module.Confirm(window, window.L, "test")
        window.wait_window = real_wait
        check("confirm: starts disabled", "disabled" in dialog.ok.state())
        dialog.variable.set("scrivo")
        window.update()
        check("confirm: the wrong word leaves it disabled",
                  "disabled" in dialog.ok.state())
        dialog.variable.set("SCRIVI")
        window.update()
        check("confirm: the right word enables it",
                  "disabled" not in dialog.ok.state())
        dialog.destroy()

        # ---- 5. qualifying the link --------------------------------
        window.qualify_link()
        pump_until_idle(window, 300)
        check("qualify: it picks a speed",
                  window.var_speed.get() in module.SPEEDS,
                  repr(window.var_speed.get()))
        check("qualify: it cleans up its test files",
                  not any(f.startswith("qualifica-") for f in os.listdir(WORK_DIR)),
                  str([f for f in os.listdir(WORK_DIR) if f.startswith("qualifica-")]))
        # qualifying voids the read: it has to be taken again
        window.read_and_verify()
        pump_until_idle(window)
        check("read taken again after qualifying",
                  window.verified_read == md5(STOCK))

        # ---- 6. the dry run ----------------------------------------
        window.var_mode.set("region")
        window.var_image.set(EXPECTED)
        window.var_layout.set(LAYOUT)
        window._reload_regions()
        window.var_region.set("uefi")
        window.var_expected.set(EXPECTED)
        window.var_mains_off.set(1)
        window._update_write_state()

        check("no write without a dry run",
                  window._missing_requirements() == ["prova a secco"],
                  str(window._missing_requirements()))
        window.dry_run()
        pump_until_idle(window, 300)
        dry = window.dry
        check("dry run done", dry is not None)
        check("dry run: md5 = expected result",
                  dry and dry.md5 == md5(EXPECTED),
                  (dry.md5[:8] if dry else "") + " vs " + md5(EXPECTED)[:8])
        check("dry run: a single span",
                  dry and len(dry.changes) == 1,
                  str([(hex(a), hex(b)) for a, b in (dry.changes if dry else [])]))
        check("dry run: nothing outside the region",
                  dry and dry.outside == [])
        check("dry run: bytes counted",
                  dry and dry.bytes_changed == 1321026,
                  str(dry.bytes_changed if dry else 0))

        # ---- 7. writing the uefi region alone ----------------------
        real_confirm = module.Confirm

        class FakeConfirm(object):
            def __init__(self, *a, **k):
                self.confirmed = True

        module.Confirm = FakeConfirm

        check("every requirement met",
                  window._missing_requirements() == [],
                  str(window._missing_requirements()))
        check("write button enabled", "disabled" not in window.b_write.state())

        window.write()
        pump_until_idle(window, 600)
        module.Confirm = real_confirm

        check("the emulated chip is now the expected result",
                  md5(FAKE_CHIP) == md5(EXPECTED),
                  "%s vs %s" % (md5(FAKE_CHIP)[:8], md5(EXPECTED)[:8]))
        check("final check: no difference",
                  any("nessuna differenza" in r or "no difference" in r
                      for r in window.log_lines))
        check("final check: region is coherent",
                  any("coerente" in r or "coherent" in r
                      for r in window.log_lines),
                  next((r for r in window.log_lines if "coerent" in r), ""))
        check("verification re-read saved",
                  any(f.startswith("bc250-after-") for f in os.listdir(WORK_DIR)))
        check("log written to file",
                  os.path.isfile(os.path.join(WORK_DIR, "SPIranha.log")))

        # ---- 8. la mappa ha visto passare i blocchi veri ------------
        import chipmap as M
        states = set(window.chip_map.states)
        check("map: blocks verified", M.VERIFIED in states)
        check("map: no mismatched block", M.MISMATCH not in states,
                  str(sorted(states)))

        # ---- 9. confronto e layout generato ------------------------
        import analysis as A
        settings = A.compare_images(A.read(STOCK), A.read(EXPECTED))
        check("comparison: one aligned span",
                  len(settings["aligned"]) == 1,
                  str([(hex(a), hex(b)) for a, b in settings["aligned"]]))
        check("comparison: the true bounds are known",
                  settings["exact"] == [(0xAE0088, 0xC228C9)],
                  str([(hex(a), hex(b)) for a, b in settings["exact"]]))
        text = A.make_layout(settings["aligned"], 16 * 1024 * 1024, "uefi")
        expected_layout = ("00000000:00adffff skip0\n"
                         "00ae0000:00c22fff uefi\n"
                         "00c23000:00ffffff skip2\n")
        check("generated layout covers the whole chip", text == expected_layout,
                  repr(text))
        check("generated layout accepted by flashrom",
                  len(fr.read_layout(_write_temp(text))) == 3)

        # ---- 10. regions derived from the real dump, and really used -
        # ⚠️ Nothing is fabricated here: it is a BC-250 dump, which has
        # neither an Intel descriptor nor an FMAP. If the AMD detection
        # breaks, on this board the feature stops being any use.
        import regions as _rg
        stock_data = A.read(STOCK)
        source, found = _rg.find_regions(stock_data)
        by_name = dict((r.name, r) for r in found)
        check("real dump: AMD structure recognised", source == "amd",
                  str(source))
        check("real dump: BIOS image located",
                  "bios" in by_name and by_name["bios"].start == 0xE02000,
                  str(sorted(by_name)))
        check("real dump: memory configuration located",
                  "apcb" in by_name, str(sorted(by_name)))

        regions_path = os.path.join(WORK_DIR, "regioni.layout")
        with open(regions_path, "wb") as f:
            f.write(_rg.as_layout(found, len(stock_data)).encode("ascii"))
        extracted = os.path.join(WORK_DIR, "bios-only.rom")
        result = window.flash.read_region(regions_path, "bios",
                                             extracted, "dummy")
        check("flashrom reads the derived region", result.ok,
                  " ".join(result.lines[-2:]))
        if result.ok:
            with open(extracted, "rb") as f:
                read_back = f.read()
            region = by_name["bios"]
            check("the extracted bytes are the region's",
                      read_back == stock_data[region.start:region.end + 1],
                      "%d byte, attesi %d" % (len(read_back), region.size))

    except Exception:
        traceback.print_exc()
        results.append(("eccezione", False))
    finally:
        window.destroy()


def main():
    if os.path.isdir(WORK_DIR):
        shutil.rmtree(WORK_DIR, ignore_errors=True)
    os.makedirs(WORK_DIR)
    window = module.App()
    window.after(300, lambda: checks(window))
    window.mainloop()
    failed = [n for n, ok in results if not ok]
    print("\n%d checks, %d failed" % (len(results), len(failed)))
    for n in failed:
        print("   FAILED:", n)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
