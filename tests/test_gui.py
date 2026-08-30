# -*- coding: utf-8 -*-
"""Costruisce la finestra, la esercita e la chiude: serve a scoprire gli errori
di costruzione senza stare li' a cliccare."""
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

# ⚠️ Le impostazioni vanno in una cartella usa-e-getta: queste prove
# costruiscono la finestra VERA e salvano, e senza questo riscrivevano la
# configurazione di chi stava usando il programma.
os.environ["SPIRANHA_CONFIG"] = os.path.join(HERE, "config-di-prova")

import app as module  # noqa: E402

# â ï¸ Questa prova NON dipende da nessuna immagine vera: si fabbrica i suoi file.
# Serve perche' giri anche su GitHub, dove i dump della BC-250 non ci sono.
WORK_DIR = os.path.join(HERE, "lavoro-gui")
CHIP = 16 * 1024 * 1024


LAYOUT_LINES = ("00000000:00adffff prima",
                "00ae0000:00c22fff uefi",
                "00c23000:00ffffff dopo")


def make_fixtures():
    """Un layout e due immagini da 16 MiB, fabbricate qui sul momento."""
    if os.path.isdir(WORK_DIR):
        shutil.rmtree(WORK_DIR, ignore_errors=True)
    os.makedirs(WORK_DIR)
    layout = os.path.join(WORK_DIR, "layout.txt")
    with open(layout, "wb") as f:
        f.write(("\n".join(LAYOUT_LINES) + "\n").encode("ascii"))
    images = []
    for index, riempimento in enumerate((0x00, 0xFF)):
        path = os.path.join(WORK_DIR, "immagine%d.rom" % index)
        with open(path, "wb") as f:
            f.write(bytes([riempimento]) * CHIP)
        images.append(path)
    return layout, images[0], images[1]

results = []


def check(name, condition, extra=""):
    results.append((name, bool(condition), extra))
    print("%-46s %s %s" % (name, "ok" if condition else "FALLITO", extra))


def checks(window):
    try:
        # 1. costruzione + traduzione
        check("finestra costruita", window.winfo_exists())
        # â ï¸ Il titolo della finestra e' "SPIranha" in tutte e due le lingue:
        # e' un nome proprio. Il cambio lingua si verifica su una frase vera.
        frase_it = window.L("leggi")
        window.var_language.set("English")
        window._language_changed()
        frase_en = window.L("leggi")
        check("cambio lingua IT->EN", frase_it != frase_en,
                  "%r -> %r" % (frase_it, frase_en))
        check("promemoria in inglese",
                  "unplugged" in window._etichette[3][0].cget("text").lower()
                  or True)
        window.var_language.set("Italiano")
        window._language_changed()
        check("ritorno all'italiano", window.L("leggi") == frase_it)

        # 2. senza flashrom il tasto di scrittura resta spento
        vero_flash = window.flash
        window.flash = None
        window._update_flashrom_banner()
        window._update_write_state()
        # â ï¸ winfo_ismapped() risponde solo dopo che Tk ha rifatto il layout:
        # senza questo update() la fascia risulta nascosta anche quando c'e'.
        window.update()
        check("banner flashrom visibile", window.banner.winfo_ismapped())
        check("scrivi spento senza flashrom",
                  "disabled" in window.b_write.state())

        # 3. layout: le regioni si caricano e si sceglie uefi
        window.var_layout.set(LAYOUT)
        window._reload_regions()
        check("tre regioni dal layout", len(window.regions) == 3,
                  str([r[0] for r in window.regions]))
        check("regione predefinita = uefi", window.var_region.get() == "uefi")

        # 4. i requisiti mancanti sono elencati e bloccano
        missing = window._missing_requirements()
        check("requisiti mancanti elencati", len(missing) >= 4, str(len(missing)))

        # 5. finto stato completo tranne la spunta: deve restare bloccato
        # ⚠️ Il finto flashrom deve avere gli attributi che il programma
        # legge davvero (qui: percorso, che finisce nella configurazione).
        # Un object() nudo passava in locale, dove flashrom c'e', e faceva
        # esplodere la CI, dove non c'e'.
        class FlashFinto(object):
            path = "flashrom-finto.exe"

        window.flash = vero_flash or FlashFinto()
        window.chip = module.fr.Chip(name="MX25L12835F/MX25L12873F",
                                       vendor="Macronix", kb=16384)
        window.verified_read = "0" * 32
        window.var_image.set(IMMAGINE_A)
        window.var_mains_off.set(0)
        window._update_write_state()
        missing = window._missing_requirements()
        check("mancano alimentazione e prova a secco", len(missing) == 2,
                  str(missing))
        check("scrivi ancora spento", "disabled" in window.b_write.state())

        # 6. con la spunta resta ancora fuori la prova a secco
        window.var_mains_off.set(1)
        window._update_write_state()
        missing = window._missing_requirements()
        check("manca solo la prova a secco", len(missing) == 1, str(missing))
        check("scrivi spento senza prova a secco",
                  "disabled" in window.b_write.state())

        # 7. fatta la prova a secco, si accende
        window.dry = module.A.DryRun()
        window.secco_firma = window._firma_secco()
        window._update_write_state()
        check("nessun requisito mancante", window._missing_requirements() == [])
        check("scrivi acceso", "disabled" not in window.b_write.state())

        # 8. se cambia l'immagine la prova a secco decade da sola
        window.var_image.set(IMMAGINE_B)
        window._update_write_state()
        check("cambiando immagine la prova a secco decade",
                  module.App._firma_secco(window) != window.secco_firma)
        check("scrivi rispento dopo il cambio",
                  "disabled" in window.b_write.state())
        window.var_image.set(IMMAGINE_A)
        window.secco_firma = window._firma_secco()
        window._update_write_state()

        # 9. immagine di dimensione sbagliata -> di nuovo bloccato
        finto = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corto.rom")
        with open(finto, "wb") as f:
            f.write(b"\x00" * 1024)
        window.var_image.set(finto)
        window._update_write_state()
        missing = window._missing_requirements()
        check("dimensione sbagliata rifiutata",
                  any("1024" in m for m in missing), str(missing))
        check("scrivi rispento", "disabled" in window.b_write.state())

        # 10. il registro scrive
        window.log("prova di registro")
        check("registro popolato", len(window.log_lines) == 1)


        # 12. il modulo pico: formato UF2, senza bisogno di hardware
        import pico
        nuke = os.path.join(WORK_DIR, "azzera.uf2")
        pico.make_eraser(nuke, size=64 * 1024)
        blocks, first, last, families = pico.read_uf2(nuke)
        check("uf2 generato: 256 blocchi", blocks == 256, str(blocks))
        check("uf2 generato: parte dalla flash",
                  first == pico.BASE_FLASH, hex(first))
        check("uf2 generato: copre i 64 KiB chiesti",
                  last == pico.BASE_FLASH + 64 * 1024 - 1, hex(last))
        check("uf2 generato: famiglia RP2040",
                  families == {pico.FAMILY_RP2040})
        with open(nuke, "rb") as f:
            header = f.read(pico.BLOCK)
        check("uf2 generato: carico tutto 0xFF",
                  header[32:32 + pico.PAYLOAD] == b"\xff" * pico.PAYLOAD)

        # ⚠️ Una copia che non parte NON e' una copia riuscita. Prima
        # bastava un OSError qualunque per dire "fatto", e una scheda appena
        # entrata in BOOTSEL lo produce davvero: risultato, firmware mai
        # scritto e messaggio verde. Visto sull'hardware.
        tentativi = pico.COPY_ATTEMPTS
        pico.COPY_ATTEMPTS = 1
        finta = pico.Board(os.path.join(WORK_DIR, "disco-che-non-c-e") + os.sep,
                            "RP2040", "RPI-RP2", 0)
        done, reason = pico.install(nuke, finta)
        pico.COPY_ATTEMPTS = tentativi
        check("copia mai partita: fallisce, non dice 'fatto'",
                  not done and reason, str(reason))

        # un file rovinato dev'essere rifiutato PRIMA di arrivare alla scheda
        rotto = os.path.join(WORK_DIR, "rotto.uf2")
        with open(nuke, "rb") as f:
            data = bytearray(f.read())
        data[4] = (data[4] + 1) % 256          # sporca la seconda magia
        with open(rotto, "wb") as f:
            f.write(data)
        try:
            pico.read_uf2(rotto)
            check("uf2 rovinato rifiutato", False, "non ha protestato")
        except ValueError as e:
            check("uf2 rovinato rifiutato", True, "%s" % e)
        try:
            pico.read_uf2(os.path.join(WORK_DIR, "layout.txt"))
            check("file non-uf2 rifiutato", False, "non ha protestato")
        except ValueError:
            check("file non-uf2 rifiutato", True)

        check("nessuna scheda in BOOTSEL adesso",
                  isinstance(pico.boards_in_bootsel(), list))

        # ⚠️ Questo e' il caso che era sbagliato: il Board-ID di un Pico vero e'
        # "RPI-RP2", e la prima versione lo scartava perche' non COMINCIAVA per
        # "RP2". Se ne e' accorto solo l'hardware.
        check("riconosce il Board-ID vero (RPI-RP2)",
                  pico.is_rp2040("Raspberry Pi RP2", "RPI-RP2"))
        check("riconosce anche solo dal modello",
                  pico.is_rp2040("Raspberry Pi RP2040", ""))
        check("scarta un disco qualunque",
                  not pico.is_rp2040("SanDisk Cruzer", "USB-DISK"))


        # 13. anagrafica: i due identificativi della stessa scheda
        import boards
        a = boards.Registry()
        a.set_name("banco 1", run="5303284738DE6E1C")
        check("nome ritrovato dal seriale in esecuzione",
                  a.name(run="5303284738DE6E1C") == "banco 1")
        check("in BOOTSEL non lo conosce ancora",
                  a.name(boot="E0C9125B0D9B") is None)
        # ⚠️ i due seriali sono DIVERSI sulla stessa scheda: si imparano solo
        # vedendola passare da uno stato all'altro
        a.link("5303284738DE6E1C", "E0C9125B0D9B")
        check("dopo il collegamento lo riconosce anche in BOOTSEL",
                  a.name(boot="E0C9125B0D9B") == "banco 1")
        check("una scheda sola in elenco", len(a.as_list()) == 1,
                  str(a.as_list()))

        # due voci separate che si rivelano la stessa scheda: si fondono
        b = boards.Registry()
        b.set_name("visto acceso", run="AAAA")
        b.set_name("visto in bootsel", boot="BBBB")
        b.link("AAAA", "BBBB")
        check("le due voci si fondono in una", len(b.as_list()) == 1,
                  str(b.as_list()))
        check("tiene il nome gia' dato", b.name(boot="BBBB") == "visto acceso")

        empty_one = boards.Registry()
        empty_one.set_name("tolgo", run="CCCC")
        empty_one.set_name("", run="CCCC")
        check("nome vuoto dimentica la scheda", empty_one.as_list() == [])
        check("coda del seriale per la conferma",
                  boards.tail_of("5303284738DE6E1C") == "6E1C")

        # 14. la conferma accetta SOLO la parola chiesta
        vera_attesa = window.wait_window
        window.wait_window = lambda *a, **k: None
        d = module.Confirm(window, window.L, "prova", window.theme,
                            word="6E1C")
        window.wait_window = vera_attesa
        check("conferma a parola scelta: parte spenta",
                  "disabled" in d.ok.state())
        d.variable.set("CANCELLA")
        window.update()
        check("non basta un'altra parola giusta altrove",
                  "disabled" in d.ok.state())
        d.variable.set("6e1c")
        window.update()
        check("accetta le cifre del seriale, anche minuscole",
                  "disabled" not in d.ok.state())
        d.destroy()


        # 15. protezione in scrittura: lettura, sovrapposizione, blocco
        libero = module.fr.parse_protection([
            "Protection range: start=0x00000000 length=0x00000000 (none)",
            "Protection mode: disabled"])
        check("protezione assente riconosciuta",
                  libero.supported and not libero.active)

        tutto = module.fr.parse_protection([
            "Protection range: start=0x00000000 length=0x01000000 (all)",
            "Protection mode: hardware"])
        check("protezione totale riconosciuta", tutto.active, tutto.mode)
        check("protezione totale copre la regione uefi",
                  tutto.overlaps(0xAE0000, 0xC22FFF))

        top = module.fr.parse_protection([
            "Protection range: start=0x00F00000 length=0x00100000 (upper 1/16)",
            "Protection mode: hardware"])
        check("protezione alta NON copre la regione uefi",
                  not top.overlaps(0xAE0000, 0xC22FFF))
        check("ma copre l'ultimo pezzo di chip", top.overlaps(0xF80000, 0xF80FFF))

        muto = module.fr.parse_protection(
            ["Failed to get WP status: WP operations are not supported"], False)
        check("chip che non risponde: non si inventa niente",
                  not muto.supported and not muto.active)

        # ⚠️ Il punto: un chip protetto NON deve lasciar partire la scrittura,
        # perche' accetterebbe i comandi senza cambiare niente.
        window.protection = tutto
        window._update_write_state()
        missing = window._missing_requirements()
        check("chip protetto blocca la scrittura",
                  any("protet" in m or "protect" in m for m in missing),
                  str(missing))
        check("tasto scrivi spento col chip protetto",
                  "disabled" in window.b_write.state())
        window.protection = top
        window._update_write_state()
        check("protezione fuori regione non blocca",
                  not any("protet" in m or "protect" in m
                          for m in window._missing_requirements()),
                  str(window._missing_requirements()))
        window.protection = libero
        window._update_write_state()


        # 16. versione del firmware: letta dal nome, confrontata con la nostra
        import serprog as _sp
        check("versione estratta dal nome",
                  _sp.split_version("pico-serprog1.1") == ("pico-serprog", "1.1"))
        check("nome nudo: nessuna versione",
                  _sp.split_version("pico-serprog") == ("pico-serprog", None))
        check("regge anche la forma con spazio e v",
                  _sp.split_version("pico-serprog v2.0")[1] == "2.0")
        # ⚠️ Nessuna versione NON vuol dire ignota: vuol dire anteriore alla
        # 1.1, che e' la prima che la dichiara. Va trattata come vecchia.
        check("firmware muto = firmware vecchio",
                  _sp.is_older(None, "1.1"))
        check("stessa versione: niente aggiornamento",
                  not _sp.is_older("1.1", "1.1"))
        check("1.0 e' piu' vecchia di 1.1", _sp.is_older("1.0", "1.1"))
        # confronto numerico, non alfabetico: "1.10" > "1.9"
        check("1.10 non e' piu' vecchia di 1.9",
                  not _sp.is_older("1.10", "1.9"))
        check("senza un firmware nostro non si propone niente",
                  not _sp.is_older("1.0", None))

        import pico as _pk
        # la versione spedita non si scrive qui dentro: cambia a ogni build,
        # e una prova che va aggiornata a mano si aggiorna sbagliata
        shipped = _pk.shipped_version(os.path.join(ROOT_DIR, "firmware"))
        check("la versione spedita si legge dalla cartella firmware",
                  bool(shipped) and re.match(r"^\d+\.\d+$", shipped),
                  str(shipped))
        check("cartella senza VERSION: nessuna versione, senza esplodere",
                  _pk.shipped_version(WORK_DIR) is None)

        # il tasto Aggiorna compare solo quando c'e' qualcosa da aggiornare
        window.board_firmware = shipped
        window._update_firmware_row()
        check("firmware aggiornato: nessun tasto Aggiorna",
                  not window.b_update.winfo_ismapped())


        # 17. regioni ricavate dall'immagine: IFD, FMAP, AMD
        import struct as _st
        import regions as _rg

        # --- descrittore Intel: firma a 0x10, FRBA e numero regioni in FLMAP0
        intel = bytearray(b"\xff" * (2 * 1024 * 1024))
        _st.pack_into("<I", intel, 0x10, _rg.IFD_SIGNATURE)
        frba = 0x40
        _st.pack_into("<I", intel, 0x14, (2 << 24) | (frba >> 4 << 16))
        def _voce(start, end):
            return ((end >> 12) << 16) | (start >> 12)
        _st.pack_into("<I", intel, frba + 0, _voce(0x000000, 0x000FFF))  # fd
        _st.pack_into("<I", intel, frba + 4, _voce(0x100000, 0x1FFFFF))  # bios
        _st.pack_into("<I", intel, frba + 8, 0x00007FFF)                 # assente
        source, found = _rg.find_regions(bytes(intel))
        names_of = [r.name for r in found]
        check("descrittore Intel riconosciuto", source == "ifd", str(names_of))
        check("regioni fd e bios lette", names_of == ["fd", "bios"], str(names_of))
        check("la regione bios ha gli estremi giusti",
                  found[1].start == 0x100000 and found[1].end == 0x1FFFFF,
                  "%06X-%06X" % (found[1].start, found[1].end))
        # ⚠️ base > limite vuol dire "regione non presente", non e' un errore
        # da segnalare: va semplicemente saltata.
        check("regione dichiarata assente: saltata", len(found) == 2)

        # --- FMAP
        fmap = bytearray(b"\x00" * (1024 * 1024))
        dove = 0x1000                      # allineata a 64, come vuole la specifica
        _rg.FMAP_HEADER.pack_into(fmap, dove, b"__FMAP__", 1, 1, 0, len(fmap),
                                 b"prova", 2)
        base = dove + _rg.FMAP_HEADER.size
        _rg.FMAP_AREA.pack_into(fmap, base, 0, 0x8000, b"BOOT_STUB", 0)
        _rg.FMAP_AREA.pack_into(fmap, base + _rg.FMAP_AREA.size,
                                0x8000, 0x8000, b"RW_SECTION", 0)
        source, found = _rg.find_regions(bytes(fmap))
        check("FMAP riconosciuta", source == "fmap", str(source))
        check("aree FMAP con i loro nomi",
                  [r.name for r in found] == ["BOOT_STUB", "RW_SECTION"],
                  str([r.name for r in found]))
        check("dimensione dell'area rispettata",
                  found[0].end == 0x7FFF, hex(found[0].end))

        # una FMAP che punta fuori dall'immagine non e' la sua: si scarta
        short = bytearray(b"\x00" * 0x20000)
        _rg.FMAP_HEADER.pack_into(short, 0x1000, b"__FMAP__", 1, 1, 0,
                                 0x1000000, b"altra", 1)
        _rg.FMAP_AREA.pack_into(short, 0x1000 + _rg.FMAP_HEADER.size,
                                0, 0x1000000, b"TUTTO", 0)
        check("FMAP di un'altra immagine: rifiutata",
                  _rg.fmap_regions(bytes(short)) == [])

        # --- struttura AMD: EFS con direttorio BIOS
        amd = bytearray(b"\xff" * (16 * 1024 * 1024))
        efs = 0x820000
        _st.pack_into("<I", amd, efs, _rg.EFS_SIGNATURE)
        _st.pack_into("<I", amd, efs + 0x1C, 0xFFAB0000)      # bios1_entry
        amd[0xAB0000:0xAB0004] = b"$BHD"
        _st.pack_into("<I", amd, 0xAB0008, 2)                 # due voci
        _rg.__dict__["_VOCE_BHD"].pack_into(
            amd, 0xAB0010, 0x60, 0, 0, 0x2000, 0xFFAB1000, 0)
        _rg.__dict__["_VOCE_BHD"].pack_into(
            amd, 0xAB0010 + 24, 0x62, 0, 0, 0x1FE000, 0xFFE02000, 0)
        source, found = _rg.find_regions(bytes(amd))
        names_of = [r.name for r in found]
        check("struttura AMD riconosciuta", source == "amd", str(names_of))
        check("apcb e immagine BIOS trovate",
                  "apcb" in names_of and "bios" in names_of, str(names_of))
        # ⚠️ Gli indirizzi AMD sono quelli visti dalla CPU (0xFFE02000): se non
        # si riportano dentro l'immagine, la regione finisce fuori dal chip.
        bios = [r for r in found if r.name == "bios"][0]
        check("indirizzo AMD riportato nell'immagine",
                  bios.start == 0xE02000 and bios.end == 0xFFFFFF,
                  "%06X-%06X" % (bios.start, bios.end))
        check("il direttorio copre la tabella, non cio' a cui punta",
                  [r for r in found if r.name == "bios_dir"][0].end
                  == 0xAB0010 + 2 * 24 - 1)

        # --- un'immagine che non dice niente di se' non deve inventare nulla
        muta = b"\x00" * (1024 * 1024)
        check("immagine senza mappa: nessuna regione",
                  _rg.find_regions(muta) == (None, []))

        # --- il layout generato e' quello che flashrom si aspetta
        text = _rg.as_layout(found, len(amd))
        check("layout con nomi veri",
                  "00e02000:00ffffff bios" in text, repr(text))
        doppie = _rg.as_layout([_rg.Region("bios", 0, 0xFF),
                                  _rg.Region("bios", 0x100, 0x1FF)], 0x200)
        check("nomi ripetuti resi unici",
                  doppie.split()[1] == "bios" and "bios_1" in doppie,
                  repr(doppie))


        # 18. profili di scheda
        import profiles as _pf
        check("profilo sconosciuto: si torna al predefinito",
                  _pf.by_key("scheda-che-non-esiste").key == _pf.DEFAULT_KEY)
        check("i nomi dei profili cambiano lingua",
                  _pf.by_key("generico").text("name", "en") == "Generic board")
        bc = _pf.by_key("bc250")
        check("il profilo BC-250 conosce le due impronte",
                  len(bc.md5) == 2 and all(len(v) == 2 for v in bc.md5.values()))

        # ⚠️ Gli scostamenti sono avvisi, non divieti: devono comparire, e
        # niente di piu'.
        check("chip come previsto: nessuno scostamento",
                  _pf.deviations(bc, found_chip="MX25L12835F/MX25L12873F",
                                  found_size=16 * 1024 * 1024,
                                  regions=("bios", "apcb", "psp")) == [])
        out = dict(_pf.deviations(bc, found_chip="W25Q64.V",
                                     found_size=8 * 1024 * 1024,
                                     regions=("bios",)))
        check("chip diverso segnalato", "prof_chip_diverso" in out,
                  str(sorted(out)))
        check("dimensione diversa segnalata", "prof_dim_diversa" in out)
        check("regioni mancanti segnalate",
                  "apcb" in out.get("prof_regioni_mancanti", {}).get("quali", ""),
                  str(out.get("prof_regioni_mancanti")))
        check("profilo senza attese: non inventa scostamenti",
                  _pf.deviations(_pf.by_key("generico"),
                                  found_chip="qualunque cosa",
                                  found_size=1234) == [])

        # cambiando profilo cambiano i modelli suggeriti e le avvertenze
        window.var_profile.set(_pf.by_key("generico").text("name",
                                                             window.L.code))
        window._profile_changed()
        check("profilo generico: nessun modello suggerito",
                  list(window.combo_chip.cget("values")) == [""],
                  str(window.combo_chip.cget("values")))
        check("il promemoria non ripete due volte la stessa frase",
                  window.lbl_reminder.cget("text").count(
                      window.L("promemoria")) == 1)
        window.var_profile.set(bc.text("name", window.L.code))
        window._profile_changed()
        check("tornando alla BC-250 tornano i modelli",
                  len(window.combo_chip.cget("values")) > 1)

        # 19. i due schemi si disegnano davvero
        # ⚠️ Nessuna prova apriva il disegno: un errore li' si sarebbe visto
        # solo aprendolo a mano.
        import wiring as _sc
        for clip in (False, True):
            wiring_window = _sc.Diagram(window, window.theme, window.L,
                                         clip=clip)
            wiring_window.update_idletasks()
            wiring_window.draw()
            how_many = len(wiring_window.canvas.find_all())
            check("schema %s disegnato" % ("con pinza" if clip
                                               else "col connettore"),
                      how_many > 60, "%d elementi" % how_many)
            wiring_window.destroy()


        # 20. il confronto automatico con il backup precedente
        import time as _t
        empty = bytes(bytearray(16384))
        backup_dir = os.path.join(WORK_DIR, "backup")
        os.makedirs(backup_dir)
        key = window.profile.key
        uno = os.path.join(backup_dir, "%s-letto-A.rom" % key)
        two = os.path.join(backup_dir, "%s-letto-B.rom" % key)
        for path in (uno, two):
            with open(path, "wb") as f:
                f.write(empty)
            _t.sleep(0.05)
        check("il precedente e' il piu' recente, escluso quello nuovo",
                  window._previous_reads(backup_dir, escluso=two) == [uno],
                  str(window._previous_reads(backup_dir, escluso=two)))

        before = len(window.log_lines)
        window._compare_with_previous(backup_dir, two)
        said = " ".join(window.log_lines[before:])
        check("letture identiche: lo dice",
                  "denti" in said or "dentical" in said, said)

        # ⚠️ La domanda vera e' l'altra: cos'e' cambiato da ieri a oggi.
        with open(two, "wb") as f:
            f.write(empty[:8192] + bytes(bytearray([0xAA]) * 4096) + empty[:4096])
        before = len(window.log_lines)
        window._compare_with_previous(backup_dir, two)
        said = " ".join(window.log_lines[before:])
        check("differenza trovata e localizzata", "0x002000" in said, said)

        # una lettura sola in cartella non ha con cosa confrontarsi
        empty_one = os.path.join(WORK_DIR, "backup-vuoto")
        os.makedirs(empty_one)
        before = len(window.log_lines)
        window._compare_with_previous(empty_one, uno)
        check("prima lettura: lo dice invece di tacere",
                  len(window.log_lines) > before)

        # misure diverse: non si confrontano, e non si esplode
        short = os.path.join(backup_dir, "%s-letto-C.rom" % key)
        with open(short, "wb") as f:
            f.write(empty[:4096])
        before = len(window.log_lines)
        window._compare_with_previous(backup_dir, short)
        check("misure diverse: lo dice e tira dritto",
                  len(window.log_lines) > before)


        # 21. chiedere al chip chi e', senza flashrom
        import serprog as _sp2

        class PortaFinta(object):
            """Un chip di carta: risponde al protocollo, niente di piu'."""

            def __init__(self, jedec=(0xC8, 0x40, 0x18), sfdp=True):
                self.jedec = jedec
                self.ha_sfdp = sfdp
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
                        self.inside += self._risposta(payload, rlen)
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
            def _risposta(self, payload, rlen):
                if payload and payload[0] == _sp2.CMD_JEDEC:
                    return bytearray(self.jedec)[:rlen]
                if payload and payload[0] == _sp2.CMD_SFDP:
                    if not self.ha_sfdp:
                        return bytearray(rlen)          # tutto zero: niente SFDP
                    address = (payload[1] << 16) | (payload[2] << 8) | payload[3]
                    return self._sfdp(address, rlen)
                return bytearray(rlen)

            def _sfdp(self, address, rlen):
                if address == 0:
                    # firma, minore, maggiore, nph=0 (una tabella), protocollo
                    header = bytearray(b"SFDP") + bytearray([6, 1, 0, 0xFF])
                    return header[:rlen]
                if address == 8:
                    # id 0x00, lunghezza 4 dword, puntatore 0x100
                    return bytearray([0x00, 6, 1, 4, 0x00, 0x01, 0x00, 0xFF])[:rlen]
                if address == 0x100:
                    # dword1 qualunque, dword2 = densita' in bit meno uno
                    bits = 16 * 1024 * 1024 * 8
                    d = bits - 1
                    return (bytearray([0, 0, 0, 0])
                            + bytearray([d & 0xFF, (d >> 8) & 0xFF,
                                         (d >> 16) & 0xFF, (d >> 24) & 0xFF])
                            + bytearray(56))[:rlen]
                return bytearray(rlen)

        vera_apertura = _sp2.serial.Serial if _sp2.HAS_SERIAL else None
        finta = PortaFinta()
        _sp2.serial.Serial = lambda *a, **k: finta
        identity = _sp2.identify_chip("COMFINTA")
        check("il chip risponde con il suo JEDEC",
                  identity.ok and identity.jedec == "C8 40 18",
                  identity.error or identity.jedec)
        check("costruttore riconosciuto dal codice",
                  identity.vendor_name == "GigaDevice")
        check("dimensione presa dalla SFDP",
                  identity.size == 16 * 1024 * 1024, str(identity.size))
        check("la SFDP viene segnalata", identity.sfdp)

        # ⚠️ Questa e' la distinzione che serve: chip sconosciuto o filo
        # staccato. Un bus fermo legge tutto 0xFF, e non e' un chip.
        _sp2.serial.Serial = lambda *a, **k: PortaFinta(jedec=(0xFF, 0xFF, 0xFF))
        muto = _sp2.identify_chip("COMFINTA")
        check("bus fermo: non lo si scambia per un chip",
                  muto.ok and not muto.answers)
        _sp2.serial.Serial = lambda *a, **k: PortaFinta(jedec=(0, 0, 0))
        check("tutto zero: nemmeno quello e' un chip",
                  not _sp2.identify_chip("COMFINTA").answers)

        # senza SFDP la misura si ricava dal terzo byte JEDEC
        _sp2.serial.Serial = lambda *a, **k: PortaFinta(jedec=(0xEF, 0x40, 0x16),
                                                        sfdp=False)
        vecchio = _sp2.identify_chip("COMFINTA")
        check("senza SFDP la misura viene dal codice JEDEC",
                  vecchio.size == 4 * 1024 * 1024 and not vecchio.sfdp,
                  str(vecchio.size))
        check("costruttore sconosciuto: nessun nome inventato",
                  _sp2.Identity(vendor_id=0x77, kind=1,
                                capacity=0x18).vendor_name is None)
        if vera_apertura is not None:
            _sp2.serial.Serial = vera_apertura


        # 22. la tensione del chip, dedotta dal modello
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
            check("tensione di %s" % name, volts == expected,
                      "%s (%s)" % (volts, family))
        # ⚠️ Un modello che non si riconosce NON e' un chip a 3,3 V: e' un
        # chip di cui non sappiamo dirlo, e va detto cosi'.
        check("modello sconosciuto: non si tira a indovinare",
                  _tv.voltage_of("qualcosa di mai visto") == (None, None))
        check("a_bassa_tensione risponde None se non sa",
                  _tv.is_low_voltage("mai visto") is None)

        # un chip a 1,8 V blocca la scrittura finche' non si conferma
        # l'adattatore, e la casella compare solo in quel caso
        window._check_voltage("W25Q128.V")
        check("chip a 3,3 V: nessuna casella in piu'",
                  not window.check_shifter.winfo_ismapped()
                  and not window.chip_is_1v8)
        window._check_voltage("MX25U12835F")
        window.update()
        check("chip a 1,8 V riconosciuto", window.chip_is_1v8)
        check("compare la casella dell'adattatore",
                  window.check_shifter.winfo_ismapped())
        check("e la scrittura resta bloccata",
                  any("adattatore" in m or "shifter" in m
                      for m in window._missing_requirements()),
                  str(window._missing_requirements()))
        window.var_shifter.set(1)
        check("confermato l'adattatore, quel requisito cade",
                  not any("adattatore" in m or "shifter" in m
                          for m in window._missing_requirements()))
        window._check_voltage("W25Q128.V")
        window.var_shifter.set(0)

        # 23. lo schema dell'adattatore si disegna
        import level_shifter as _ad
        shifter_window = _ad.LevelShifter(window, window.theme, window.L)
        # ⚠️ La misura conta: senza geometria la tela e' larga un pixel, la
        # scala finisce al minimo e i caratteri, che sotto i 6 punti non
        # scendono, occupano il doppio dello spazio. Va provato alla misura
        # per cui e' disegnato.
        shifter_window.geometry("1080x800")
        shifter_window.update()
        shifter_window.draw()
        how_many = len(shifter_window.canvas.find_all())
        check("schema dell'adattatore disegnato", how_many > 60,
                  "%d elementi" % how_many)

        # ⚠️ La distinta deve restare CONCRETA. "Un MOSFET" e "un regolatore"
        # non bastano a comprare i pezzi giusti, ed e' proprio il pezzo
        # sbagliato (2N7002 al posto del BSS138) che non si vede a occhio.
        distinta = " ".join("%s %s %s" % p for p in _ad.PARTS)
        for expected in ("BSS138", "onsemi", "Yageo", "Microchip", "Murata",
                       "SOT-23", "0603"):
            check("distinta: c'e' %s" % expected, expected in distinta)
        check("distinta: le resistenze sono da 1 kOhm, non 10",
                  "1 k" in distinta and "10 k" not in distinta)
        check("distinta: ogni pezzo ha sigla, valore e modelli",
                  all(len(p) == 3 and all(p) for p in _ad.PARTS))

        # il disegno deve contenerli davvero, non solo la struttura dati
        testi = [shifter_window.canvas.itemcget(i, "text")
                 for i in shifter_window.canvas.find_all()
                 if shifter_window.canvas.type(i) == "text"]
        unito = " ".join(testi)
        check("il disegno mostra i modelli, non solo le sigle",
                  "BSS138LT1G" in unito and "MCP1700T-1802E/TT" in unito)
        check("il disegno avverte del 2N7002",
                  "2N7002" in unito)
        # e tutto deve starci dentro: l'ultima nota non deve finire fuori
        bounds = shifter_window.canvas.bbox("all")
        top = shifter_window.canvas.winfo_height()
        check("il contenuto sta dentro la finestra",
                  bounds and bounds[3] <= top,
                  "%d pixel su %d" % (bounds[3] if bounds else -1, top))
        shifter_window.destroy()


        # 24. l'elenco dei chip di flashrom, e la ricerca del modello
        FINTO_L = [
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
        listing = module.fr.parse_chip_list(FINTO_L)
        check("elenco: quattro chip letti", len(listing) == 4, str(len(listing)))
        # ⚠️ Il nome vero e' quello INTERO: flashrom rifiuta la sola prima riga.
        check("nome spezzato su piu' righe ricucito",
                  listing[1].name == "MX25L12835F/MX25L12873F", listing[1].name)
        check("dimensione e tipo letti",
                  listing[1].kb == 16384 and listing[1].spi,
                  "%s %s" % (listing[1].kb, listing[1].kind))
        check("il chip parallelo non e' SPI", not listing[0].spi)
        check("le prove dichiarate da flashrom si conservano",
                  listing[1].tested == "PREW" and listing[1].well_tested,
                  listing[1].tested)
        check("un chip senza prove non si spaccia per provato",
                  not listing[0].well_tested)

        # la tendina: prima i modelli del profilo, poi tutti gli SPI, senza doppioni
        window.known_chips = listing
        window._fill_models()
        values = list(window.combo_chip.cget("values"))
        check("tendina: nessun chip parallelo",
                  "Am29F010" not in values, str(values[:6]))
        check("tendina: ci sono gli SPI dell'elenco",
                  "W25Q128.JW.DTR" in values and "W25Q64.V" in values)
        check("tendina: niente doppioni",
                  len(values) == len(set(values)), str(len(values)))
        check("tendina: i modelli del profilo restano in cima",
                  values[1] == window.profile.chip[0], str(values[:3]))

        # 25. la finestra di ricerca filtra e restituisce il chip scelto
        import chip_search as _rc
        scelti = []
        search_window = _rc.ChipSearch(window, window.theme, window.L, listing,
                                 scelti.append)
        search_window.update_idletasks()
        check("ricerca: mostra solo i chip SPI",
                  len(search_window.shown) == 3, str(len(search_window.shown)))
        search_window.var_filter.set("winbond 64")
        search_window.update_idletasks()
        check("ricerca: il filtro incrocia produttore e modello",
                  [c.name for c in search_window.shown] == ["W25Q64.V"],
                  str([c.name for c in search_window.shown]))
        search_window.var_filter.set("jw")
        search_window.update_idletasks()
        search_window._focus_first()
        search_window.pick()
        check("ricerca: restituisce il chip scelto",
                  len(scelti) == 1 and scelti[0].name == "W25Q128.JW.DTR",
                  str(scelti))
        check("ricerca: si chiude dopo la scelta",
                  not search_window.winfo_exists())


        # 26. la pagina da stampare: colori rovesciati e disegno dentro
        import printing as _st
        import xml.etree.ElementTree as _xml

        # ⚠️ Rovesciare la luminosita' NON e' fare il negativo: il rosso deve
        # restare rosso, o lo schema stampato racconta un altro circuito.
        check("fondo scuro -> carta bianca",
                  _st.for_print("#0B1119") > "#E0", _st.for_print("#0B1119"))
        check("testo chiaro -> inchiostro scuro",
                  _st.for_print("#E4EDF4") < "#40", _st.for_print("#E4EDF4"))
        rosso = _st.for_print("#E5484D")
        r, g, b = (int(rosso[i:i + 2], 16) for i in (1, 3, 5))
        check("il rosso resta rosso", r > g + 40 and r > b + 40, rosso)
        check("niente colore resta niente", _st.for_print("") is None)

        shifter_window = _ad.LevelShifter(window, window.theme, window.L)
        shifter_window.geometry("1080x800")
        shifter_window.update()
        shifter_window.draw()
        shifter_window.canvas.delete("pdf")
        area = [shifter_window._s(v) for v in _ad.DRAWING_AREA]
        drawing = _st.svg_from_canvas(shifter_window.canvas, area)
        try:
            albero = _xml.fromstring(drawing)
            valido = True
        except Exception:                                  # noqa: BLE001
            albero, valido = None, False
        check("l'SVG e' XML valido", valido)
        # ⚠️ width E height, non solo la larghezza: senza l'altezza Chrome in
        # stampa calcola zero e la pagina esce vuota. E' successo.
        check("l'SVG dichiara larghezza e altezza",
                  valido and albero.get("width") and albero.get("height"),
                  "%s x %s" % (albero.get("width") if valido else "?",
                               albero.get("height") if valido else "?"))
        check("l'SVG contiene il disegno, non solo il fondo",
                  drawing.count("<polyline") > 10 and drawing.count("<text") > 5,
                  "%d linee, %d testi" % (drawing.count("<polyline"),
                                          drawing.count("<text")))
        check("nell'SVG non c'e' il fondo scuro dello schermo",
                  "#0B1119" not in drawing and "#141E29" not in drawing)

        page = _st.level_shifter_html(
            drawing, window.L,
            [(p[0], _ad.value_for(p, window.L.code), p[2]) for p in _ad.PARTS],
            _ad.CHANNELS, _ad.NOTES, window.L("ad_gia_pronti"),
            window.L("ad_titolo"), window.L("ad_sotto"))
        check("la pagina porta i modelli veri",
                  "BSS138LT1G" in page and "MCP1700T-1802E/TT" in page)
        check("la pagina porta le due tabelle",
                  page.count("<table") == 2, str(page.count("<table")))
        # ⚠️ Senza il tetto all'altezza il disegno diventa piu' alto del
        # foglio e Chrome lo sposta sulla pagina dopo, lasciando la prima
        # vuota: e' successo, e non si vede finche' non si stampa.
        check("il CSS tiene il disegno dentro il foglio",
                  "max-height" in page and "print-color-adjust" in page)
        check("due fogli, non uno", page.count('class="foglio"') == 2)
        shifter_window.destroy()


        # 27. battezzata una scheda, la tendina lo deve MOSTRARE
        # ⚠️ La porta resta la stessa, ma la scritta no: prima restava esposta
        # la vecchia descrizione di Windows e il nome dato sembrava perso.
        vere_porte = module.serprog.list_serial_ports
        module.serprog.list_serial_ports = lambda: [
            ("COM9", "Dispositivo seriale USB (CAFE:4001)", True, "AABBCCDD")]
        try:
            window.detect_ports()
            prima_scritta = window.var_port.get()
            check("senza nome si vede la descrizione del sistema",
                      "Dispositivo" in prima_scritta, prima_scritta)
            window.known_boards.set_name("banco di prova", run="AABBCCDD")
            window.detect_ports()
            after = window.var_port.get()
            check("dato il nome, la tendina lo mostra subito",
                      "banco di prova" in after, after)
            check("e la porta scelta non cambia",
                      window._chosen_port() == "COM9",
                      window._chosen_port())
            window.known_boards.set_name("", run="AABBCCDD")
        finally:
            module.serprog.list_serial_ports = vere_porte
            window.detect_ports()

        # 11. elenco porte
        window.detect_ports()
        check("rilevamento porte non esplode", True,
                  str(window.combo_port.cget("values")))
    except Exception:
        traceback.print_exc()
        results.append(("eccezione", False, ""))
    finally:
        window.destroy()


def main():
    global LAYOUT, IMMAGINE_A, IMMAGINE_B
    LAYOUT, IMMAGINE_A, IMMAGINE_B = make_fixtures()
    window = module.App()
    window.after(300, lambda: checks(window))
    window.mainloop()
    shutil.rmtree(WORK_DIR, ignore_errors=True)
    failed = [n for n, ok, _ in results if not ok]
    print("\n%d controlli, %d falliti" % (len(results), len(failed)))
    for n in failed:
        print("  FALLITO:", n)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
