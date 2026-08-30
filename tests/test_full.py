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
os.environ["SPIRANHA_CONFIG"] = os.path.join(HERE, "config-di-prova")


import common as comune  # noqa: E402

BACKUP = comune.backup_or_skip()
EXE = comune.flashrom_or_skip()
WORK_DIR = os.path.join(HERE, "lavoro")

import app as module  # noqa: E402
import flashrom as fr  # noqa: E402

STOCK, EXPECTED, LAYOUT = comune.test_files(BACKUP)
FAKE_CHIP = os.path.join(WORK_DIR, "chip-emulato.rom")

results = []


def check(name, condition, extra=""):
    results.append((name, bool(condition)))
    print("%-52s %s %s" % (name, "ok" if condition else "FALLITO", extra))
    return bool(condition)


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def pump_until_idle(window, seconds=300):
    """Spins the event loop until the operation is done."""
    scadenza = time.time() + seconds
    while window.busy and time.time() < scadenza:
        window.update()
        time.sleep(0.02)
    window.update()
    return not window.busy


def dummy_programmer():
    return "dummy:emulate=W25Q128FV,image=%s" % FAKE_CHIP


def _scrivi_temp(text):
    path = os.path.join(WORK_DIR, "layout-generato.txt")
    with open(path, "wb") as f:
        f.write(text.encode("ascii"))
    return path


def checks(window):
    try:
        # the emulated chip starts out with the board's STOCK BIOS
        shutil.copyfile(STOCK, FAKE_CHIP)
        check("chip emulato = BIOS originale", md5(FAKE_CHIP) == md5(STOCK))

        window.flash = fr.Flashrom(EXE, programmatore=dummy_programmer())
        window.flashrom_version = window.flash.version() or ""
        check("flashrom risponde", "flashrom" in window.flashrom_version.lower(),
                  window.flashrom_version)
        window.var_folder.set(WORK_DIR)
        window._update_flashrom_banner()

        # ---- 1. identificazione ------------------------------------
        window.identify_chip()
        pump_until_idle(window)
        check("chip identificato", window.chip is not None,
                  window.chip.description if window.chip else "")
        check("dimensione riconosciuta = 16 MiB",
                  window.chip and window.chip.size == 16 * 1024 * 1024)

        check("protezione letta insieme al chip",
                  window.protection is not None)
        check("il chip emulato non e' protetto",
                  window.protection is not None
                  and window.protection.supported
                  and not window.protection.active,
                  (window.protection.mode or "?") if window.protection else "")

        # ---- 2. lettura doppia -------------------------------------
        window.read_and_verify()
        pump_until_idle(window)
        check("lettura doppia verificata",
                  window.verified_read == md5(STOCK),
                  str(window.verified_read)[:12])
        read_bytes = [f for f in os.listdir(WORK_DIR) if f.startswith("bc250-letto-")]
        verifiche = [f for f in os.listdir(WORK_DIR) if f.startswith("bc250-verifica-")]
        check("backup salvato", len(read_bytes) == 1, str(read_bytes))
        check("seconda lettura cancellata", verifiche == [], str(verifiche))
        check("impronta nota riconosciuta",
                  any("originale" in r for r in window.log_lines))

        # ---- 3. the block when the two reads disagree ---------------
        vero_md5 = module.md5_of_file
        chiamate = {"n": 0}

        def md5_ballerino(path, stop_flag=None):
            chiamate["n"] += 1
            reale = vero_md5(path, stop_flag)
            return reale if chiamate["n"] % 2 else "0" * 32   # il primo mente

        window.verified_read = None
        module.md5_of_file = md5_ballerino
        window.read_and_verify()
        pump_until_idle(window)
        module.md5_of_file = vero_md5
        check("letture diverse -> lettura NON validata",
                  window.verified_read is None)
        check("letture diverse -> scrittura bloccata",
                  "disabled" in window.b_write.state())
        rimaste = [f for f in os.listdir(WORK_DIR) if f.startswith("bc250-verifica-")]
        check("letture diverse -> tengo entrambi i file", len(rimaste) == 1)

        # rimetto a posto una lettura buona
        for f in rimaste:
            os.remove(os.path.join(WORK_DIR, f))
        window.read_and_verify()
        pump_until_idle(window)
        check("lettura buona rifatta", window.verified_read == md5(STOCK))

        # ---- 4. la finestra di conferma ----------------------------
        vera_attesa = window.wait_window
        window.wait_window = lambda *a, **k: None
        dialog = module.Confirm(window, window.L, "prova")
        window.wait_window = vera_attesa
        check("conferma: parte spenta", "disabled" in dialog.ok.state())
        dialog.variable.set("scrivo")
        window.update()
        check("conferma: parola sbagliata resta spenta",
                  "disabled" in dialog.ok.state())
        dialog.variable.set("SCRIVI")
        window.update()
        check("conferma: parola giusta accende",
                  "disabled" not in dialog.ok.state())
        dialog.destroy()

        # ---- 5. la qualifica del collegamento ----------------------
        window.qualify_link()
        pump_until_idle(window, 300)
        check("qualifica: sceglie una velocità",
                  window.var_speed.get() in module.SPEEDS,
                  repr(window.var_speed.get()))
        check("qualifica: ripulisce i file di prova",
                  not any(f.startswith("qualifica-") for f in os.listdir(WORK_DIR)),
                  str([f for f in os.listdir(WORK_DIR) if f.startswith("qualifica-")]))
        # la qualifica invalida la lettura: si rifa'
        window.read_and_verify()
        pump_until_idle(window)
        check("lettura rifatta dopo la qualifica",
                  window.verified_read == md5(STOCK))

        # ---- 6. la prova a secco -----------------------------------
        window.var_mode.set("regione")
        window.var_image.set(EXPECTED)
        window.var_layout.set(LAYOUT)
        window._reload_regions()
        window.var_region.set("uefi")
        window.var_expected.set(EXPECTED)
        window.var_mains_off.set(1)
        window._update_write_state()

        check("senza prova a secco non si scrive",
                  window._missing_requirements() == ["prova a secco"],
                  str(window._missing_requirements()))
        window.dry_run()
        pump_until_idle(window, 300)
        dry = window.dry
        check("prova a secco eseguita", dry is not None)
        check("prova a secco: md5 = risultato atteso",
                  dry and dry.md5 == md5(EXPECTED),
                  (dry.md5[:8] if dry else "") + " vs " + md5(EXPECTED)[:8])
        check("prova a secco: un solo intervallo",
                  dry and len(dry.changes) == 1,
                  str([(hex(a), hex(b)) for a, b in (dry.changes if dry else [])]))
        check("prova a secco: niente fuori regione",
                  dry and dry.outside == [])
        check("prova a secco: byte contati",
                  dry and dry.bytes_changed == 1321026,
                  str(dry.bytes_changed if dry else 0))

        # ---- 7. la scrittura della sola regione uefi ---------------
        vera_conferma = module.Confirm

        class ConfermaFinta(object):
            def __init__(self, *a, **k):
                self.confirmed = True

        module.Confirm = ConfermaFinta

        check("tutti i requisiti soddisfatti",
                  window._missing_requirements() == [],
                  str(window._missing_requirements()))
        check("tasto scrivi acceso", "disabled" not in window.b_write.state())

        window.write()
        pump_until_idle(window, 600)
        module.Confirm = vera_conferma

        check("il chip emulato ora e' il risultato atteso",
                  md5(FAKE_CHIP) == md5(EXPECTED),
                  "%s vs %s" % (md5(FAKE_CHIP)[:8], md5(EXPECTED)[:8]))
        check("verifica finale: nessuna differenza",
                  any("nessuna differenza" in r or "no difference" in r
                      for r in window.log_lines))
        check("verifica finale: regione coerente",
                  any("coerente" in r or "coherent" in r
                      for r in window.log_lines),
                  next((r for r in window.log_lines if "coerent" in r), ""))
        check("rilettura di controllo salvata",
                  any(f.startswith("bc250-dopo-") for f in os.listdir(WORK_DIR)))
        check("registro su file",
                  os.path.isfile(os.path.join(WORK_DIR, "SPIranha.log")))

        # ---- 8. la mappa ha visto passare i blocchi veri ------------
        import chipmap as M
        states = set(window.chip_map.states)
        check("mappa: blocchi verificati", M.VERIFIED in states)
        check("mappa: nessun blocco diverso", M.MISMATCH not in states,
                  str(sorted(states)))

        # ---- 9. confronto e layout generato ------------------------
        import analysis as A
        settings = A.compare_images(A.read(STOCK), A.read(EXPECTED))
        check("confronto: un intervallo allineato",
                  len(settings["allineati"]) == 1,
                  str([(hex(a), hex(b)) for a, b in settings["allineati"]]))
        check("confronto: confini veri noti",
                  settings["esatti"] == [(0xAE0088, 0xC228C9)],
                  str([(hex(a), hex(b)) for a, b in settings["esatti"]]))
        text = A.make_layout(settings["allineati"], 16 * 1024 * 1024, "uefi")
        atteso_layout = ("00000000:00adffff salta0\n"
                         "00ae0000:00c22fff uefi\n"
                         "00c23000:00ffffff salta2\n")
        check("layout generato copre tutto il chip", text == atteso_layout,
                  repr(text))
        check("layout generato accettato da flashrom",
                  len(fr.read_layout(_scrivi_temp(text))) == 3)

        # ---- 10. regioni ricavate dal dump vero, e usate davvero -----
        # ⚠️ Nothing is fabricated here: it is a BC-250 dump, which has
        # neither an Intel descriptor nor an FMAP. If the AMD detection
        # breaks, on this board the feature stops being any use.
        import regions as _rg
        dati_stock = A.read(STOCK)
        source, found = _rg.find_regions(dati_stock)
        names_of = dict((r.name, r) for r in found)
        check("dump vero: struttura AMD riconosciuta", source == "amd",
                  str(source))
        check("dump vero: immagine BIOS individuata",
                  "bios" in names_of and names_of["bios"].start == 0xE02000,
                  str(sorted(names_of)))
        check("dump vero: configurazione memoria individuata",
                  "apcb" in names_of, str(sorted(names_of)))

        percorso_regioni = os.path.join(WORK_DIR, "regioni.layout")
        with open(percorso_regioni, "wb") as f:
            f.write(_rg.as_layout(found, len(dati_stock)).encode("ascii"))
        estratto = os.path.join(WORK_DIR, "solo-bios.rom")
        result = window.flash.read_region(percorso_regioni, "bios",
                                             estratto, "dummy")
        check("flashrom legge la regione ricavata", result.ok,
                  " ".join(result.lines[-2:]))
        if result.ok:
            with open(estratto, "rb") as f:
                letto = f.read()
            region = names_of["bios"]
            check("i byte estratti sono quelli della regione",
                      letto == dati_stock[region.start:region.end + 1],
                      "%d byte, attesi %d" % (len(letto), region.size))

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
    print("\n%d controlli, %d falliti" % (len(results), len(failed)))
    for n in failed:
        print("   FALLITO:", n)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
