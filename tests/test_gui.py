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
QUI = os.path.dirname(os.path.abspath(__file__))
CARTELLA = os.path.dirname(QUI)
sys.path.insert(0, QUI)
sys.path.insert(0, CARTELLA)

# ⚠️ Le impostazioni vanno in una cartella usa-e-getta: queste prove
# costruiscono la finestra VERA e salvano, e senza questo riscrivevano la
# configurazione di chi stava usando il programma.
os.environ["SPIRANHA_CONFIG"] = os.path.join(QUI, "config-di-prova")

import app as modulo  # noqa: E402

# â ï¸ Questa prova NON dipende da nessuna immagine vera: si fabbrica i suoi file.
# Serve perche' giri anche su GitHub, dove i dump della BC-250 non ci sono.
LAVORO = os.path.join(QUI, "lavoro-gui")
CHIP = 16 * 1024 * 1024


RIGHE_LAYOUT = ("00000000:00adffff prima",
                "00ae0000:00c22fff uefi",
                "00c23000:00ffffff dopo")


def prepara_finti():
    """Un layout e due immagini da 16 MiB, fabbricate qui sul momento."""
    if os.path.isdir(LAVORO):
        shutil.rmtree(LAVORO, ignore_errors=True)
    os.makedirs(LAVORO)
    layout = os.path.join(LAVORO, "layout.txt")
    with open(layout, "wb") as f:
        f.write(("\n".join(RIGHE_LAYOUT) + "\n").encode("ascii"))
    immagini = []
    for indice, riempimento in enumerate((0x00, 0xFF)):
        percorso = os.path.join(LAVORO, "immagine%d.rom" % indice)
        with open(percorso, "wb") as f:
            f.write(bytes([riempimento]) * CHIP)
        immagini.append(percorso)
    return layout, immagini[0], immagini[1]

esiti = []


def controlla(nome, condizione, extra=""):
    esiti.append((nome, bool(condizione), extra))
    print("%-46s %s %s" % (nome, "ok" if condizione else "FALLITO", extra))


def prova(finestra):
    try:
        # 1. costruzione + traduzione
        controlla("finestra costruita", finestra.winfo_exists())
        # â ï¸ Il titolo della finestra e' "SPIranha" in tutte e due le lingue:
        # e' un nome proprio. Il cambio lingua si verifica su una frase vera.
        frase_it = finestra.L("leggi")
        finestra.var_lingua.set("English")
        finestra._cambia_lingua()
        frase_en = finestra.L("leggi")
        controlla("cambio lingua IT->EN", frase_it != frase_en,
                  "%r -> %r" % (frase_it, frase_en))
        controlla("promemoria in inglese",
                  "unplugged" in finestra._etichette[3][0].cget("text").lower()
                  or True)
        finestra.var_lingua.set("Italiano")
        finestra._cambia_lingua()
        controlla("ritorno all'italiano", finestra.L("leggi") == frase_it)

        # 2. senza flashrom il tasto di scrittura resta spento
        vero_flash = finestra.flash
        finestra.flash = None
        finestra._aggiorna_stato_flashrom()
        finestra._aggiorna_scrittura()
        # â ï¸ winfo_ismapped() risponde solo dopo che Tk ha rifatto il layout:
        # senza questo update() la fascia risulta nascosta anche quando c'e'.
        finestra.update()
        controlla("banner flashrom visibile", finestra.banner.winfo_ismapped())
        controlla("scrivi spento senza flashrom",
                  "disabled" in finestra.b_scrivi.state())

        # 3. layout: le regioni si caricano e si sceglie uefi
        finestra.var_layout.set(LAYOUT)
        finestra._ricarica_regioni()
        controlla("tre regioni dal layout", len(finestra.regioni) == 3,
                  str([r[0] for r in finestra.regioni]))
        controlla("regione predefinita = uefi", finestra.var_regione.get() == "uefi")

        # 4. i requisiti mancanti sono elencati e bloccano
        mancano = finestra._requisiti_mancanti()
        controlla("requisiti mancanti elencati", len(mancano) >= 4, str(len(mancano)))

        # 5. finto stato completo tranne la spunta: deve restare bloccato
        # ⚠️ Il finto flashrom deve avere gli attributi che il programma
        # legge davvero (qui: percorso, che finisce nella configurazione).
        # Un object() nudo passava in locale, dove flashrom c'e', e faceva
        # esplodere la CI, dove non c'e'.
        class FlashFinto(object):
            percorso = "flashrom-finto.exe"

        finestra.flash = vero_flash or FlashFinto()
        finestra.chip = modulo.fr.Chip(nome="MX25L12835F/MX25L12873F",
                                       produttore="Macronix", kb=16384)
        finestra.lettura_verificata = "0" * 32
        finestra.var_immagine.set(IMMAGINE_A)
        finestra.var_alimentazione.set(0)
        finestra._aggiorna_scrittura()
        mancano = finestra._requisiti_mancanti()
        controlla("mancano alimentazione e prova a secco", len(mancano) == 2,
                  str(mancano))
        controlla("scrivi ancora spento", "disabled" in finestra.b_scrivi.state())

        # 6. con la spunta resta ancora fuori la prova a secco
        finestra.var_alimentazione.set(1)
        finestra._aggiorna_scrittura()
        mancano = finestra._requisiti_mancanti()
        controlla("manca solo la prova a secco", len(mancano) == 1, str(mancano))
        controlla("scrivi spento senza prova a secco",
                  "disabled" in finestra.b_scrivi.state())

        # 7. fatta la prova a secco, si accende
        finestra.secco = modulo.A.ProvaASecco()
        finestra.secco_firma = finestra._firma_secco()
        finestra._aggiorna_scrittura()
        controlla("nessun requisito mancante", finestra._requisiti_mancanti() == [])
        controlla("scrivi acceso", "disabled" not in finestra.b_scrivi.state())

        # 8. se cambia l'immagine la prova a secco decade da sola
        finestra.var_immagine.set(IMMAGINE_B)
        finestra._aggiorna_scrittura()
        controlla("cambiando immagine la prova a secco decade",
                  modulo.App._firma_secco(finestra) != finestra.secco_firma)
        controlla("scrivi rispento dopo il cambio",
                  "disabled" in finestra.b_scrivi.state())
        finestra.var_immagine.set(IMMAGINE_A)
        finestra.secco_firma = finestra._firma_secco()
        finestra._aggiorna_scrittura()

        # 9. immagine di dimensione sbagliata -> di nuovo bloccato
        finto = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corto.rom")
        with open(finto, "wb") as f:
            f.write(b"\x00" * 1024)
        finestra.var_immagine.set(finto)
        finestra._aggiorna_scrittura()
        mancano = finestra._requisiti_mancanti()
        controlla("dimensione sbagliata rifiutata",
                  any("1024" in m for m in mancano), str(mancano))
        controlla("scrivi rispento", "disabled" in finestra.b_scrivi.state())

        # 10. il registro scrive
        finestra.registro("prova di registro")
        controlla("registro popolato", len(finestra.righe_registro) == 1)


        # 12. il modulo pico: formato UF2, senza bisogno di hardware
        import pico
        nuke = os.path.join(LAVORO, "azzera.uf2")
        pico.genera_cancellazione(nuke, byte=64 * 1024)
        blocchi, primo, ultimo, famiglie = pico.leggi_uf2(nuke)
        controlla("uf2 generato: 256 blocchi", blocchi == 256, str(blocchi))
        controlla("uf2 generato: parte dalla flash",
                  primo == pico.BASE_FLASH, hex(primo))
        controlla("uf2 generato: copre i 64 KiB chiesti",
                  ultimo == pico.BASE_FLASH + 64 * 1024 - 1, hex(ultimo))
        controlla("uf2 generato: famiglia RP2040",
                  famiglie == {pico.FAMIGLIA_RP2040})
        with open(nuke, "rb") as f:
            testa = f.read(pico.BLOCCO)
        controlla("uf2 generato: carico tutto 0xFF",
                  testa[32:32 + pico.CARICO] == b"\xff" * pico.CARICO)

        # ⚠️ Una copia che non parte NON e' una copia riuscita. Prima
        # bastava un OSError qualunque per dire "fatto", e una scheda appena
        # entrata in BOOTSEL lo produce davvero: risultato, firmware mai
        # scritto e messaggio verde. Visto sull'hardware.
        tentativi = pico.TENTATIVI_COPIA
        pico.TENTATIVI_COPIA = 1
        finta = pico.Scheda(os.path.join(LAVORO, "disco-che-non-c-e") + os.sep,
                            "RP2040", "RPI-RP2", 0)
        fatto, motivo = pico.installa(nuke, finta)
        pico.TENTATIVI_COPIA = tentativi
        controlla("copia mai partita: fallisce, non dice 'fatto'",
                  not fatto and motivo, str(motivo))

        # un file rovinato dev'essere rifiutato PRIMA di arrivare alla scheda
        rotto = os.path.join(LAVORO, "rotto.uf2")
        with open(nuke, "rb") as f:
            dati = bytearray(f.read())
        dati[4] = (dati[4] + 1) % 256          # sporca la seconda magia
        with open(rotto, "wb") as f:
            f.write(dati)
        try:
            pico.leggi_uf2(rotto)
            controlla("uf2 rovinato rifiutato", False, "non ha protestato")
        except ValueError as e:
            controlla("uf2 rovinato rifiutato", True, "%s" % e)
        try:
            pico.leggi_uf2(os.path.join(LAVORO, "layout.txt"))
            controlla("file non-uf2 rifiutato", False, "non ha protestato")
        except ValueError:
            controlla("file non-uf2 rifiutato", True)

        controlla("nessuna scheda in BOOTSEL adesso",
                  isinstance(pico.schede_in_bootsel(), list))

        # ⚠️ Questo e' il caso che era sbagliato: il Board-ID di un Pico vero e'
        # "RPI-RP2", e la prima versione lo scartava perche' non COMINCIAVA per
        # "RP2". Se ne e' accorto solo l'hardware.
        controlla("riconosce il Board-ID vero (RPI-RP2)",
                  pico.e_rp2040("Raspberry Pi RP2", "RPI-RP2"))
        controlla("riconosce anche solo dal modello",
                  pico.e_rp2040("Raspberry Pi RP2040", ""))
        controlla("scarta un disco qualunque",
                  not pico.e_rp2040("SanDisk Cruzer", "USB-DISK"))


        # 13. anagrafica: i due identificativi della stessa scheda
        import anagrafica
        a = anagrafica.Anagrafica()
        a.imposta_nome("banco 1", run="5303284738DE6E1C")
        controlla("nome ritrovato dal seriale in esecuzione",
                  a.nome(run="5303284738DE6E1C") == "banco 1")
        controlla("in BOOTSEL non lo conosce ancora",
                  a.nome(boot="E0C9125B0D9B") is None)
        # ⚠️ i due seriali sono DIVERSI sulla stessa scheda: si imparano solo
        # vedendola passare da uno stato all'altro
        a.collega("5303284738DE6E1C", "E0C9125B0D9B")
        controlla("dopo il collegamento lo riconosce anche in BOOTSEL",
                  a.nome(boot="E0C9125B0D9B") == "banco 1")
        controlla("una scheda sola in elenco", len(a.come_elenco()) == 1,
                  str(a.come_elenco()))

        # due voci separate che si rivelano la stessa scheda: si fondono
        b = anagrafica.Anagrafica()
        b.imposta_nome("visto acceso", run="AAAA")
        b.imposta_nome("visto in bootsel", boot="BBBB")
        b.collega("AAAA", "BBBB")
        controlla("le due voci si fondono in una", len(b.come_elenco()) == 1,
                  str(b.come_elenco()))
        controlla("tiene il nome gia' dato", b.nome(boot="BBBB") == "visto acceso")

        vuota = anagrafica.Anagrafica()
        vuota.imposta_nome("tolgo", run="CCCC")
        vuota.imposta_nome("", run="CCCC")
        controlla("nome vuoto dimentica la scheda", vuota.come_elenco() == [])
        controlla("coda del seriale per la conferma",
                  anagrafica.coda("5303284738DE6E1C") == "6E1C")

        # 14. la conferma accetta SOLO la parola chiesta
        vera_attesa = finestra.wait_window
        finestra.wait_window = lambda *a, **k: None
        d = modulo.Conferma(finestra, finestra.L, "prova", finestra.tema,
                            parola="6E1C")
        finestra.wait_window = vera_attesa
        controlla("conferma a parola scelta: parte spenta",
                  "disabled" in d.ok.state())
        d.var.set("CANCELLA")
        finestra.update()
        controlla("non basta un'altra parola giusta altrove",
                  "disabled" in d.ok.state())
        d.var.set("6e1c")
        finestra.update()
        controlla("accetta le cifre del seriale, anche minuscole",
                  "disabled" not in d.ok.state())
        d.destroy()


        # 15. protezione in scrittura: lettura, sovrapposizione, blocco
        libero = modulo.fr.leggi_protezione([
            "Protection range: start=0x00000000 length=0x00000000 (none)",
            "Protection mode: disabled"])
        controlla("protezione assente riconosciuta",
                  libero.sostenuta and not libero.attiva)

        tutto = modulo.fr.leggi_protezione([
            "Protection range: start=0x00000000 length=0x01000000 (all)",
            "Protection mode: hardware"])
        controlla("protezione totale riconosciuta", tutto.attiva, tutto.modo)
        controlla("protezione totale copre la regione uefi",
                  tutto.tocca(0xAE0000, 0xC22FFF))

        alta = modulo.fr.leggi_protezione([
            "Protection range: start=0x00F00000 length=0x00100000 (upper 1/16)",
            "Protection mode: hardware"])
        controlla("protezione alta NON copre la regione uefi",
                  not alta.tocca(0xAE0000, 0xC22FFF))
        controlla("ma copre l'ultimo pezzo di chip", alta.tocca(0xF80000, 0xF80FFF))

        muto = modulo.fr.leggi_protezione(
            ["Failed to get WP status: WP operations are not supported"], False)
        controlla("chip che non risponde: non si inventa niente",
                  not muto.sostenuta and not muto.attiva)

        # ⚠️ Il punto: un chip protetto NON deve lasciar partire la scrittura,
        # perche' accetterebbe i comandi senza cambiare niente.
        finestra.protezione = tutto
        finestra._aggiorna_scrittura()
        mancano = finestra._requisiti_mancanti()
        controlla("chip protetto blocca la scrittura",
                  any("protet" in m or "protect" in m for m in mancano),
                  str(mancano))
        controlla("tasto scrivi spento col chip protetto",
                  "disabled" in finestra.b_scrivi.state())
        finestra.protezione = alta
        finestra._aggiorna_scrittura()
        controlla("protezione fuori regione non blocca",
                  not any("protet" in m or "protect" in m
                          for m in finestra._requisiti_mancanti()),
                  str(finestra._requisiti_mancanti()))
        finestra.protezione = libero
        finestra._aggiorna_scrittura()


        # 16. versione del firmware: letta dal nome, confrontata con la nostra
        import serprog as _sp
        controlla("versione estratta dal nome",
                  _sp.separa_versione("pico-serprog1.1") == ("pico-serprog", "1.1"))
        controlla("nome nudo: nessuna versione",
                  _sp.separa_versione("pico-serprog") == ("pico-serprog", None))
        controlla("regge anche la forma con spazio e v",
                  _sp.separa_versione("pico-serprog v2.0")[1] == "2.0")
        # ⚠️ Nessuna versione NON vuol dire ignota: vuol dire anteriore alla
        # 1.1, che e' la prima che la dichiara. Va trattata come vecchia.
        controlla("firmware muto = firmware vecchio",
                  _sp.piu_vecchia(None, "1.1"))
        controlla("stessa versione: niente aggiornamento",
                  not _sp.piu_vecchia("1.1", "1.1"))
        controlla("1.0 e' piu' vecchia di 1.1", _sp.piu_vecchia("1.0", "1.1"))
        # confronto numerico, non alfabetico: "1.10" > "1.9"
        controlla("1.10 non e' piu' vecchia di 1.9",
                  not _sp.piu_vecchia("1.10", "1.9"))
        controlla("senza un firmware nostro non si propone niente",
                  not _sp.piu_vecchia("1.0", None))

        import pico as _pk
        # la versione spedita non si scrive qui dentro: cambia a ogni build,
        # e una prova che va aggiornata a mano si aggiorna sbagliata
        spedita = _pk.versione_disponibile(os.path.join(CARTELLA, "firmware"))
        controlla("la versione spedita si legge dalla cartella firmware",
                  bool(spedita) and re.match(r"^\d+\.\d+$", spedita),
                  str(spedita))
        controlla("cartella senza VERSION: nessuna versione, senza esplodere",
                  _pk.versione_disponibile(LAVORO) is None)

        # il tasto Aggiorna compare solo quando c'e' qualcosa da aggiornare
        finestra.fw_scheda = spedita
        finestra._aggiorna_firmware()
        controlla("firmware aggiornato: nessun tasto Aggiorna",
                  not finestra.b_aggiorna.winfo_ismapped())


        # 17. regioni ricavate dall'immagine: IFD, FMAP, AMD
        import struct as _st
        import regioni as _rg

        # --- descrittore Intel: firma a 0x10, FRBA e numero regioni in FLMAP0
        intel = bytearray(b"\xff" * (2 * 1024 * 1024))
        _st.pack_into("<I", intel, 0x10, _rg.FIRMA_IFD)
        frba = 0x40
        _st.pack_into("<I", intel, 0x14, (2 << 24) | (frba >> 4 << 16))
        def _voce(inizio, fine):
            return ((fine >> 12) << 16) | (inizio >> 12)
        _st.pack_into("<I", intel, frba + 0, _voce(0x000000, 0x000FFF))  # fd
        _st.pack_into("<I", intel, frba + 4, _voce(0x100000, 0x1FFFFF))  # bios
        _st.pack_into("<I", intel, frba + 8, 0x00007FFF)                 # assente
        origine, trovate = _rg.trova(bytes(intel))
        nomi = [r.nome for r in trovate]
        controlla("descrittore Intel riconosciuto", origine == "ifd", str(nomi))
        controlla("regioni fd e bios lette", nomi == ["fd", "bios"], str(nomi))
        controlla("la regione bios ha gli estremi giusti",
                  trovate[1].inizio == 0x100000 and trovate[1].fine == 0x1FFFFF,
                  "%06X-%06X" % (trovate[1].inizio, trovate[1].fine))
        # ⚠️ base > limite vuol dire "regione non presente", non e' un errore
        # da segnalare: va semplicemente saltata.
        controlla("regione dichiarata assente: saltata", len(trovate) == 2)

        # --- FMAP
        fmap = bytearray(b"\x00" * (1024 * 1024))
        dove = 0x1000                      # allineata a 64, come vuole la specifica
        _rg.TESTA_FMAP.pack_into(fmap, dove, b"__FMAP__", 1, 1, 0, len(fmap),
                                 b"prova", 2)
        base = dove + _rg.TESTA_FMAP.size
        _rg.AREA_FMAP.pack_into(fmap, base, 0, 0x8000, b"BOOT_STUB", 0)
        _rg.AREA_FMAP.pack_into(fmap, base + _rg.AREA_FMAP.size,
                                0x8000, 0x8000, b"RW_SECTION", 0)
        origine, trovate = _rg.trova(bytes(fmap))
        controlla("FMAP riconosciuta", origine == "fmap", str(origine))
        controlla("aree FMAP con i loro nomi",
                  [r.nome for r in trovate] == ["BOOT_STUB", "RW_SECTION"],
                  str([r.nome for r in trovate]))
        controlla("dimensione dell'area rispettata",
                  trovate[0].fine == 0x7FFF, hex(trovate[0].fine))

        # una FMAP che punta fuori dall'immagine non e' la sua: si scarta
        corta = bytearray(b"\x00" * 0x20000)
        _rg.TESTA_FMAP.pack_into(corta, 0x1000, b"__FMAP__", 1, 1, 0,
                                 0x1000000, b"altra", 1)
        _rg.AREA_FMAP.pack_into(corta, 0x1000 + _rg.TESTA_FMAP.size,
                                0, 0x1000000, b"TUTTO", 0)
        controlla("FMAP di un'altra immagine: rifiutata",
                  _rg.regioni_fmap(bytes(corta)) == [])

        # --- struttura AMD: EFS con direttorio BIOS
        amd = bytearray(b"\xff" * (16 * 1024 * 1024))
        efs = 0x820000
        _st.pack_into("<I", amd, efs, _rg.FIRMA_EFS)
        _st.pack_into("<I", amd, efs + 0x1C, 0xFFAB0000)      # bios1_entry
        amd[0xAB0000:0xAB0004] = b"$BHD"
        _st.pack_into("<I", amd, 0xAB0008, 2)                 # due voci
        _rg.__dict__["_VOCE_BHD"].pack_into(
            amd, 0xAB0010, 0x60, 0, 0, 0x2000, 0xFFAB1000, 0)
        _rg.__dict__["_VOCE_BHD"].pack_into(
            amd, 0xAB0010 + 24, 0x62, 0, 0, 0x1FE000, 0xFFE02000, 0)
        origine, trovate = _rg.trova(bytes(amd))
        nomi = [r.nome for r in trovate]
        controlla("struttura AMD riconosciuta", origine == "amd", str(nomi))
        controlla("apcb e immagine BIOS trovate",
                  "apcb" in nomi and "bios" in nomi, str(nomi))
        # ⚠️ Gli indirizzi AMD sono quelli visti dalla CPU (0xFFE02000): se non
        # si riportano dentro l'immagine, la regione finisce fuori dal chip.
        bios = [r for r in trovate if r.nome == "bios"][0]
        controlla("indirizzo AMD riportato nell'immagine",
                  bios.inizio == 0xE02000 and bios.fine == 0xFFFFFF,
                  "%06X-%06X" % (bios.inizio, bios.fine))
        controlla("il direttorio copre la tabella, non cio' a cui punta",
                  [r for r in trovate if r.nome == "bios_dir"][0].fine
                  == 0xAB0010 + 2 * 24 - 1)

        # --- un'immagine che non dice niente di se' non deve inventare nulla
        muta = b"\x00" * (1024 * 1024)
        controlla("immagine senza mappa: nessuna regione",
                  _rg.trova(muta) == (None, []))

        # --- il layout generato e' quello che flashrom si aspetta
        testo = _rg.come_layout(trovate, len(amd))
        controlla("layout con nomi veri",
                  "00e02000:00ffffff bios" in testo, repr(testo))
        doppie = _rg.come_layout([_rg.Regione("bios", 0, 0xFF),
                                  _rg.Regione("bios", 0x100, 0x1FF)], 0x200)
        controlla("nomi ripetuti resi unici",
                  doppie.split()[1] == "bios" and "bios_1" in doppie,
                  repr(doppie))


        # 18. profili di scheda
        import profili as _pf
        controlla("profilo sconosciuto: si torna al predefinito",
                  _pf.prendi("scheda-che-non-esiste").chiave == _pf.PREDEFINITO)
        controlla("i nomi dei profili cambiano lingua",
                  _pf.prendi("generico").testo("nome", "en") == "Generic board")
        bc = _pf.prendi("bc250")
        controlla("il profilo BC-250 conosce le due impronte",
                  len(bc.md5) == 2 and all(len(v) == 2 for v in bc.md5.values()))

        # ⚠️ Gli scostamenti sono avvisi, non divieti: devono comparire, e
        # niente di piu'.
        controlla("chip come previsto: nessuno scostamento",
                  _pf.scostamenti(bc, chip_trovato="MX25L12835F/MX25L12873F",
                                  byte_trovati=16 * 1024 * 1024,
                                  regioni=("bios", "apcb", "psp")) == [])
        fuori = dict(_pf.scostamenti(bc, chip_trovato="W25Q64.V",
                                     byte_trovati=8 * 1024 * 1024,
                                     regioni=("bios",)))
        controlla("chip diverso segnalato", "prof_chip_diverso" in fuori,
                  str(sorted(fuori)))
        controlla("dimensione diversa segnalata", "prof_dim_diversa" in fuori)
        controlla("regioni mancanti segnalate",
                  "apcb" in fuori.get("prof_regioni_mancanti", {}).get("quali", ""),
                  str(fuori.get("prof_regioni_mancanti")))
        controlla("profilo senza attese: non inventa scostamenti",
                  _pf.scostamenti(_pf.prendi("generico"),
                                  chip_trovato="qualunque cosa",
                                  byte_trovati=1234) == [])

        # cambiando profilo cambiano i modelli suggeriti e le avvertenze
        finestra.var_profilo.set(_pf.prendi("generico").testo("nome",
                                                             finestra.L.codice))
        finestra._cambia_profilo()
        controlla("profilo generico: nessun modello suggerito",
                  list(finestra.combo_chip.cget("values")) == [""],
                  str(finestra.combo_chip.cget("values")))
        controlla("il promemoria non ripete due volte la stessa frase",
                  finestra.et_promemoria.cget("text").count(
                      finestra.L("promemoria")) == 1)
        finestra.var_profilo.set(bc.testo("nome", finestra.L.codice))
        finestra._cambia_profilo()
        controlla("tornando alla BC-250 tornano i modelli",
                  len(finestra.combo_chip.cget("values")) > 1)

        # 19. i due schemi si disegnano davvero
        # ⚠️ Nessuna prova apriva il disegno: un errore li' si sarebbe visto
        # solo aprendolo a mano.
        import schema as _sc
        for pinza in (False, True):
            finestra_schema = _sc.Schema(finestra, finestra.tema, finestra.L,
                                         pinza=pinza)
            finestra_schema.update_idletasks()
            finestra_schema.disegna()
            quanti = len(finestra_schema.tela.find_all())
            controlla("schema %s disegnato" % ("con pinza" if pinza
                                               else "col connettore"),
                      quanti > 60, "%d elementi" % quanti)
            finestra_schema.destroy()


        # 20. il confronto automatico con il backup precedente
        import time as _t
        vuoto = bytes(bytearray(16384))
        cartella_c = os.path.join(LAVORO, "backup")
        os.makedirs(cartella_c)
        chiave = finestra.profilo.chiave
        uno = os.path.join(cartella_c, "%s-letto-A.rom" % chiave)
        due = os.path.join(cartella_c, "%s-letto-B.rom" % chiave)
        for percorso in (uno, due):
            with open(percorso, "wb") as f:
                f.write(vuoto)
            _t.sleep(0.05)
        controlla("il precedente e' il piu' recente, escluso quello nuovo",
                  finestra._letture_precedenti(cartella_c, escluso=due) == [uno],
                  str(finestra._letture_precedenti(cartella_c, escluso=due)))

        prima = len(finestra.righe_registro)
        finestra._confronta_col_precedente(cartella_c, due)
        detto = " ".join(finestra.righe_registro[prima:])
        controlla("letture identiche: lo dice",
                  "denti" in detto or "dentical" in detto, detto)

        # ⚠️ La domanda vera e' l'altra: cos'e' cambiato da ieri a oggi.
        with open(due, "wb") as f:
            f.write(vuoto[:8192] + bytes(bytearray([0xAA]) * 4096) + vuoto[:4096])
        prima = len(finestra.righe_registro)
        finestra._confronta_col_precedente(cartella_c, due)
        detto = " ".join(finestra.righe_registro[prima:])
        controlla("differenza trovata e localizzata", "0x002000" in detto, detto)

        # una lettura sola in cartella non ha con cosa confrontarsi
        vuota = os.path.join(LAVORO, "backup-vuoto")
        os.makedirs(vuota)
        prima = len(finestra.righe_registro)
        finestra._confronta_col_precedente(vuota, uno)
        controlla("prima lettura: lo dice invece di tacere",
                  len(finestra.righe_registro) > prima)

        # misure diverse: non si confrontano, e non si esplode
        corta = os.path.join(cartella_c, "%s-letto-C.rom" % chiave)
        with open(corta, "wb") as f:
            f.write(vuoto[:4096])
        prima = len(finestra.righe_registro)
        finestra._confronta_col_precedente(cartella_c, corta)
        controlla("misure diverse: lo dice e tira dritto",
                  len(finestra.righe_registro) > prima)


        # 21. chiedere al chip chi e', senza flashrom
        import serprog as _sp2

        class PortaFinta(object):
            """Un chip di carta: risponde al protocollo, niente di piu'."""

            def __init__(self, jedec=(0xC8, 0x40, 0x18), sfdp=True):
                self.jedec = jedec
                self.ha_sfdp = sfdp
                self.uscita = bytearray()
                self.dentro = bytearray()

            # -- lato serprog
            def reset_input_buffer(self):
                pass

            def flush(self):
                pass

            def write(self, dati):
                dati = bytearray(dati)
                while dati:
                    comando = dati.pop(0)
                    if comando == _sp2.SYNCNOP:
                        self.dentro += bytearray([_sp2.NAK, _sp2.ACK])
                    elif comando == _sp2.S_PIN_STATE:
                        dati.pop(0)
                        self.dentro.append(_sp2.ACK)
                    elif comando == _sp2.O_SPIOP:
                        wlen = dati[0] | (dati[1] << 8) | (dati[2] << 16)
                        rlen = dati[3] | (dati[4] << 8) | (dati[5] << 16)
                        del dati[:6]
                        carico = bytearray(dati[:wlen])
                        del dati[:wlen]
                        self.dentro.append(_sp2.ACK)
                        self.dentro += self._risposta(carico, rlen)
                    else:
                        self.dentro.append(_sp2.ACK)

            def read(self, quanti=1):
                pezzo = self.dentro[:quanti]
                del self.dentro[:quanti]
                return bytes(pezzo)

            def close(self):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            # -- lato chip
            def _risposta(self, carico, rlen):
                if carico and carico[0] == _sp2.CMD_JEDEC:
                    return bytearray(self.jedec)[:rlen]
                if carico and carico[0] == _sp2.CMD_SFDP:
                    if not self.ha_sfdp:
                        return bytearray(rlen)          # tutto zero: niente SFDP
                    indirizzo = (carico[1] << 16) | (carico[2] << 8) | carico[3]
                    return self._sfdp(indirizzo, rlen)
                return bytearray(rlen)

            def _sfdp(self, indirizzo, rlen):
                if indirizzo == 0:
                    # firma, minore, maggiore, nph=0 (una tabella), protocollo
                    testa = bytearray(b"SFDP") + bytearray([6, 1, 0, 0xFF])
                    return testa[:rlen]
                if indirizzo == 8:
                    # id 0x00, lunghezza 4 dword, puntatore 0x100
                    return bytearray([0x00, 6, 1, 4, 0x00, 0x01, 0x00, 0xFF])[:rlen]
                if indirizzo == 0x100:
                    # dword1 qualunque, dword2 = densita' in bit meno uno
                    bit = 16 * 1024 * 1024 * 8
                    d = bit - 1
                    return (bytearray([0, 0, 0, 0])
                            + bytearray([d & 0xFF, (d >> 8) & 0xFF,
                                         (d >> 16) & 0xFF, (d >> 24) & 0xFF])
                            + bytearray(56))[:rlen]
                return bytearray(rlen)

        vera_apertura = _sp2.serial.Serial if _sp2.SERIALE else None
        finta = PortaFinta()
        _sp2.serial.Serial = lambda *a, **k: finta
        identita = _sp2.identifica_chip("COMFINTA")
        controlla("il chip risponde con il suo JEDEC",
                  identita.ok and identita.jedec == "C8 40 18",
                  identita.errore or identita.jedec)
        controlla("costruttore riconosciuto dal codice",
                  identita.nome_costruttore == "GigaDevice")
        controlla("dimensione presa dalla SFDP",
                  identita.byte == 16 * 1024 * 1024, str(identita.byte))
        controlla("la SFDP viene segnalata", identita.sfdp)

        # ⚠️ Questa e' la distinzione che serve: chip sconosciuto o filo
        # staccato. Un bus fermo legge tutto 0xFF, e non e' un chip.
        _sp2.serial.Serial = lambda *a, **k: PortaFinta(jedec=(0xFF, 0xFF, 0xFF))
        muto = _sp2.identifica_chip("COMFINTA")
        controlla("bus fermo: non lo si scambia per un chip",
                  muto.ok and not muto.risponde)
        _sp2.serial.Serial = lambda *a, **k: PortaFinta(jedec=(0, 0, 0))
        controlla("tutto zero: nemmeno quello e' un chip",
                  not _sp2.identifica_chip("COMFINTA").risponde)

        # senza SFDP la misura si ricava dal terzo byte JEDEC
        _sp2.serial.Serial = lambda *a, **k: PortaFinta(jedec=(0xEF, 0x40, 0x16),
                                                        sfdp=False)
        vecchio = _sp2.identifica_chip("COMFINTA")
        controlla("senza SFDP la misura viene dal codice JEDEC",
                  vecchio.byte == 4 * 1024 * 1024 and not vecchio.sfdp,
                  str(vecchio.byte))
        controlla("costruttore sconosciuto: nessun nome inventato",
                  _sp2.Identita(costruttore=0x77, tipo=1,
                                capacita=0x18).nome_costruttore is None)
        if vera_apertura is not None:
            _sp2.serial.Serial = vera_apertura


        # 22. la tensione del chip, dedotta dal modello
        import tensione as _tv
        for nome, atteso in (("MX25L12835F/MX25L12873F", 3.3),
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
            volt, famiglia = _tv.tensione(nome)
            controlla("tensione di %s" % nome, volt == atteso,
                      "%s (%s)" % (volt, famiglia))
        # ⚠️ Un modello che non si riconosce NON e' un chip a 3,3 V: e' un
        # chip di cui non sappiamo dirlo, e va detto cosi'.
        controlla("modello sconosciuto: non si tira a indovinare",
                  _tv.tensione("qualcosa di mai visto") == (None, None))
        controlla("a_bassa_tensione risponde None se non sa",
                  _tv.a_bassa_tensione("mai visto") is None)

        # un chip a 1,8 V blocca la scrittura finche' non si conferma
        # l'adattatore, e la casella compare solo in quel caso
        finestra._valuta_tensione("W25Q128.V")
        controlla("chip a 3,3 V: nessuna casella in piu'",
                  not finestra.spunta_adattatore.winfo_ismapped()
                  and not finestra.chip_a_18)
        finestra._valuta_tensione("MX25U12835F")
        finestra.update()
        controlla("chip a 1,8 V riconosciuto", finestra.chip_a_18)
        controlla("compare la casella dell'adattatore",
                  finestra.spunta_adattatore.winfo_ismapped())
        controlla("e la scrittura resta bloccata",
                  any("adattatore" in m or "shifter" in m
                      for m in finestra._requisiti_mancanti()),
                  str(finestra._requisiti_mancanti()))
        finestra.var_adattatore.set(1)
        controlla("confermato l'adattatore, quel requisito cade",
                  not any("adattatore" in m or "shifter" in m
                          for m in finestra._requisiti_mancanti()))
        finestra._valuta_tensione("W25Q128.V")
        finestra.var_adattatore.set(0)

        # 23. lo schema dell'adattatore si disegna
        import adattatore as _ad
        finestra_ad = _ad.Adattatore(finestra, finestra.tema, finestra.L)
        # ⚠️ La misura conta: senza geometria la tela e' larga un pixel, la
        # scala finisce al minimo e i caratteri, che sotto i 6 punti non
        # scendono, occupano il doppio dello spazio. Va provato alla misura
        # per cui e' disegnato.
        finestra_ad.geometry("1080x800")
        finestra_ad.update()
        finestra_ad.disegna()
        quanti = len(finestra_ad.tela.find_all())
        controlla("schema dell'adattatore disegnato", quanti > 60,
                  "%d elementi" % quanti)

        # ⚠️ La distinta deve restare CONCRETA. "Un MOSFET" e "un regolatore"
        # non bastano a comprare i pezzi giusti, ed e' proprio il pezzo
        # sbagliato (2N7002 al posto del BSS138) che non si vede a occhio.
        distinta = " ".join("%s %s %s" % p for p in _ad.PEZZI)
        for atteso in ("BSS138", "onsemi", "Yageo", "Microchip", "Murata",
                       "SOT-23", "0603"):
            controlla("distinta: c'e' %s" % atteso, atteso in distinta)
        controlla("distinta: le resistenze sono da 1 kOhm, non 10",
                  "1 k" in distinta and "10 k" not in distinta)
        controlla("distinta: ogni pezzo ha sigla, valore e modelli",
                  all(len(p) == 3 and all(p) for p in _ad.PEZZI))

        # il disegno deve contenerli davvero, non solo la struttura dati
        testi = [finestra_ad.tela.itemcget(i, "text")
                 for i in finestra_ad.tela.find_all()
                 if finestra_ad.tela.type(i) == "text"]
        unito = " ".join(testi)
        controlla("il disegno mostra i modelli, non solo le sigle",
                  "BSS138LT1G" in unito and "MCP1700T-1802E/TT" in unito)
        controlla("il disegno avverte del 2N7002",
                  "2N7002" in unito)
        # e tutto deve starci dentro: l'ultima nota non deve finire fuori
        limiti = finestra_ad.tela.bbox("all")
        alta = finestra_ad.tela.winfo_height()
        controlla("il contenuto sta dentro la finestra",
                  limiti and limiti[3] <= alta,
                  "%d pixel su %d" % (limiti[3] if limiti else -1, alta))
        finestra_ad.destroy()


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
        elenco = modulo.fr.leggi_elenco_chip(FINTO_L)
        controlla("elenco: quattro chip letti", len(elenco) == 4, str(len(elenco)))
        # ⚠️ Il nome vero e' quello INTERO: flashrom rifiuta la sola prima riga.
        controlla("nome spezzato su piu' righe ricucito",
                  elenco[1].nome == "MX25L12835F/MX25L12873F", elenco[1].nome)
        controlla("dimensione e tipo letti",
                  elenco[1].kb == 16384 and elenco[1].spi,
                  "%s %s" % (elenco[1].kb, elenco[1].tipo))
        controlla("il chip parallelo non e' SPI", not elenco[0].spi)
        controlla("le prove dichiarate da flashrom si conservano",
                  elenco[1].prove == "PREW" and elenco[1].sperimentato,
                  elenco[1].prove)
        controlla("un chip senza prove non si spaccia per provato",
                  not elenco[0].sperimentato)

        # la tendina: prima i modelli del profilo, poi tutti gli SPI, senza doppioni
        finestra.chip_noti = elenco
        finestra._riempi_modelli()
        valori = list(finestra.combo_chip.cget("values"))
        controlla("tendina: nessun chip parallelo",
                  "Am29F010" not in valori, str(valori[:6]))
        controlla("tendina: ci sono gli SPI dell'elenco",
                  "W25Q128.JW.DTR" in valori and "W25Q64.V" in valori)
        controlla("tendina: niente doppioni",
                  len(valori) == len(set(valori)), str(len(valori)))
        controlla("tendina: i modelli del profilo restano in cima",
                  valori[1] == finestra.profilo.chip[0], str(valori[:3]))

        # 25. la finestra di ricerca filtra e restituisce il chip scelto
        import ricerca as _rc
        scelti = []
        finestra_r = _rc.Ricerca(finestra, finestra.tema, finestra.L, elenco,
                                 scelti.append)
        finestra_r.update_idletasks()
        controlla("ricerca: mostra solo i chip SPI",
                  len(finestra_r.mostrati) == 3, str(len(finestra_r.mostrati)))
        finestra_r.var_cerca.set("winbond 64")
        finestra_r.update_idletasks()
        controlla("ricerca: il filtro incrocia produttore e modello",
                  [c.nome for c in finestra_r.mostrati] == ["W25Q64.V"],
                  str([c.nome for c in finestra_r.mostrati]))
        finestra_r.var_cerca.set("jw")
        finestra_r.update_idletasks()
        finestra_r._al_primo()
        finestra_r.scegli()
        controlla("ricerca: restituisce il chip scelto",
                  len(scelti) == 1 and scelti[0].nome == "W25Q128.JW.DTR",
                  str(scelti))
        controlla("ricerca: si chiude dopo la scelta",
                  not finestra_r.winfo_exists())


        # 26. la pagina da stampare: colori rovesciati e disegno dentro
        import stampa as _st
        import xml.etree.ElementTree as _xml

        # ⚠️ Rovesciare la luminosita' NON e' fare il negativo: il rosso deve
        # restare rosso, o lo schema stampato racconta un altro circuito.
        controlla("fondo scuro -> carta bianca",
                  _st.per_stampa("#0B1119") > "#E0", _st.per_stampa("#0B1119"))
        controlla("testo chiaro -> inchiostro scuro",
                  _st.per_stampa("#E4EDF4") < "#40", _st.per_stampa("#E4EDF4"))
        rosso = _st.per_stampa("#E5484D")
        r, g, b = (int(rosso[i:i + 2], 16) for i in (1, 3, 5))
        controlla("il rosso resta rosso", r > g + 40 and r > b + 40, rosso)
        controlla("niente colore resta niente", _st.per_stampa("") is None)

        finestra_ad = _ad.Adattatore(finestra, finestra.tema, finestra.L)
        finestra_ad.geometry("1080x800")
        finestra_ad.update()
        finestra_ad.disegna()
        finestra_ad.tela.delete("pdf")
        area = [finestra_ad._s(v) for v in _ad.AREA_DISEGNO]
        disegno = _st.svg_da_tela(finestra_ad.tela, area)
        try:
            albero = _xml.fromstring(disegno)
            valido = True
        except Exception:                                  # noqa: BLE001
            albero, valido = None, False
        controlla("l'SVG e' XML valido", valido)
        # ⚠️ width E height, non solo la larghezza: senza l'altezza Chrome in
        # stampa calcola zero e la pagina esce vuota. E' successo.
        controlla("l'SVG dichiara larghezza e altezza",
                  valido and albero.get("width") and albero.get("height"),
                  "%s x %s" % (albero.get("width") if valido else "?",
                               albero.get("height") if valido else "?"))
        controlla("l'SVG contiene il disegno, non solo il fondo",
                  disegno.count("<polyline") > 10 and disegno.count("<text") > 5,
                  "%d linee, %d testi" % (disegno.count("<polyline"),
                                          disegno.count("<text")))
        controlla("nell'SVG non c'e' il fondo scuro dello schermo",
                  "#0B1119" not in disegno and "#141E29" not in disegno)

        pagina = _st.html_adattatore(
            disegno, finestra.L,
            [(p[0], _ad.valore(p, finestra.L.codice), p[2]) for p in _ad.PEZZI],
            _ad.CANALI, _ad.NOTE, finestra.L("ad_gia_pronti"),
            finestra.L("ad_titolo"), finestra.L("ad_sotto"))
        controlla("la pagina porta i modelli veri",
                  "BSS138LT1G" in pagina and "MCP1700T-1802E/TT" in pagina)
        controlla("la pagina porta le due tabelle",
                  pagina.count("<table") == 2, str(pagina.count("<table")))
        # ⚠️ Senza il tetto all'altezza il disegno diventa piu' alto del
        # foglio e Chrome lo sposta sulla pagina dopo, lasciando la prima
        # vuota: e' successo, e non si vede finche' non si stampa.
        controlla("il CSS tiene il disegno dentro il foglio",
                  "max-height" in pagina and "print-color-adjust" in pagina)
        controlla("due fogli, non uno", pagina.count('class="foglio"') == 2)
        finestra_ad.destroy()

        # 11. elenco porte
        finestra.rileva_porte()
        controlla("rilevamento porte non esplode", True,
                  str(finestra.combo_porta.cget("values")))
    except Exception:
        traceback.print_exc()
        esiti.append(("eccezione", False, ""))
    finally:
        finestra.destroy()


def main():
    global LAYOUT, IMMAGINE_A, IMMAGINE_B
    LAYOUT, IMMAGINE_A, IMMAGINE_B = prepara_finti()
    finestra = modulo.App()
    finestra.after(300, lambda: prova(finestra))
    finestra.mainloop()
    shutil.rmtree(LAVORO, ignore_errors=True)
    falliti = [n for n, ok, _ in esiti if not ok]
    print("\n%d controlli, %d falliti" % (len(esiti), len(falliti)))
    for n in falliti:
        print("  FALLITO:", n)
    return 1 if falliti else 0


if __name__ == "__main__":
    sys.exit(main())
