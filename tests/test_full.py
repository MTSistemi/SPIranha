# -*- coding: utf-8 -*-
"""La prova che conta: tutta la catena, con un chip EMULATO da flashrom.

Non simula il programma: usa la finestra vera, i suoi pulsanti e i suoi
controlli, con flashrom vero. L'unica differenza e' il programmatore, che invece
di serprog e' `dummy`, cioe' un chip da 16 MiB in memoria salvato su file.

La prova centrale ricalca esattamente l'operazione vera sulla BC-250:
si parte dal BIOS originale, si scrive la SOLA regione uefi prendendola dal
BIOS modificato, e alla fine il chip deve risultare identico byte per byte a
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

QUI = os.path.dirname(os.path.abspath(__file__))
CARTELLA = os.path.dirname(QUI)
sys.path.insert(0, QUI)
sys.path.insert(0, CARTELLA)

import common as comune  # noqa: E402

BACKUP = comune.backup_o_salta()
EXE = comune.flashrom_o_salta()
LAVORO = os.path.join(QUI, "lavoro")

import app as modulo  # noqa: E402
import flashrom as fr  # noqa: E402

STOCK, ATTESO, LAYOUT = comune.file_prova(BACKUP)
CHIP_FINTO = os.path.join(LAVORO, "chip-emulato.rom")

esiti = []


def controlla(nome, condizione, extra=""):
    esiti.append((nome, bool(condizione)))
    print("%-52s %s %s" % (nome, "ok" if condizione else "FALLITO", extra))
    return bool(condizione)


def md5(percorso):
    return hashlib.md5(open(percorso, "rb").read()).hexdigest()


def aspetta(finestra, secondi=300):
    """Gira il ciclo degli eventi finche' l'operazione non finisce."""
    scadenza = time.time() + secondi
    while finestra.occupato and time.time() < scadenza:
        finestra.update()
        time.sleep(0.02)
    finestra.update()
    return not finestra.occupato


def programmatore_finto():
    return "dummy:emulate=W25Q128FV,image=%s" % CHIP_FINTO


def _scrivi_temp(testo):
    percorso = os.path.join(LAVORO, "layout-generato.txt")
    with open(percorso, "wb") as f:
        f.write(testo.encode("ascii"))
    return percorso


def prova(finestra):
    try:
        # il chip emulato parte con il BIOS ORIGINALE della scheda
        shutil.copyfile(STOCK, CHIP_FINTO)
        controlla("chip emulato = BIOS originale", md5(CHIP_FINTO) == md5(STOCK))

        finestra.flash = fr.Flashrom(EXE, programmatore=programmatore_finto())
        finestra.versione_flashrom = finestra.flash.versione() or ""
        controlla("flashrom risponde", "flashrom" in finestra.versione_flashrom.lower(),
                  finestra.versione_flashrom)
        finestra.var_cartella.set(LAVORO)
        finestra._aggiorna_stato_flashrom()

        # ---- 1. identificazione ------------------------------------
        finestra.identifica_chip()
        aspetta(finestra)
        controlla("chip identificato", finestra.chip is not None,
                  finestra.chip.descrizione if finestra.chip else "")
        controlla("dimensione riconosciuta = 16 MiB",
                  finestra.chip and finestra.chip.byte == 16 * 1024 * 1024)

        controlla("protezione letta insieme al chip",
                  finestra.protezione is not None)
        controlla("il chip emulato non e' protetto",
                  finestra.protezione is not None
                  and finestra.protezione.sostenuta
                  and not finestra.protezione.attiva,
                  (finestra.protezione.modo or "?") if finestra.protezione else "")

        # ---- 2. lettura doppia -------------------------------------
        finestra.leggi_e_verifica()
        aspetta(finestra)
        controlla("lettura doppia verificata",
                  finestra.lettura_verificata == md5(STOCK),
                  str(finestra.lettura_verificata)[:12])
        letti = [f for f in os.listdir(LAVORO) if f.startswith("bc250-letto-")]
        verifiche = [f for f in os.listdir(LAVORO) if f.startswith("bc250-verifica-")]
        controlla("backup salvato", len(letti) == 1, str(letti))
        controlla("seconda lettura cancellata", verifiche == [], str(verifiche))
        controlla("impronta nota riconosciuta",
                  any("originale" in r for r in finestra.righe_registro))

        # ---- 3. il blocco quando le due letture differiscono --------
        vero_md5 = modulo.md5_file
        chiamate = {"n": 0}

        def md5_ballerino(percorso, fermati=None):
            chiamate["n"] += 1
            reale = vero_md5(percorso, fermati)
            return reale if chiamate["n"] % 2 else "0" * 32   # il primo mente

        finestra.lettura_verificata = None
        modulo.md5_file = md5_ballerino
        finestra.leggi_e_verifica()
        aspetta(finestra)
        modulo.md5_file = vero_md5
        controlla("letture diverse -> lettura NON validata",
                  finestra.lettura_verificata is None)
        controlla("letture diverse -> scrittura bloccata",
                  "disabled" in finestra.b_scrivi.state())
        rimaste = [f for f in os.listdir(LAVORO) if f.startswith("bc250-verifica-")]
        controlla("letture diverse -> tengo entrambi i file", len(rimaste) == 1)

        # rimetto a posto una lettura buona
        for f in rimaste:
            os.remove(os.path.join(LAVORO, f))
        finestra.leggi_e_verifica()
        aspetta(finestra)
        controlla("lettura buona rifatta", finestra.lettura_verificata == md5(STOCK))

        # ---- 4. la finestra di conferma ----------------------------
        vera_attesa = finestra.wait_window
        finestra.wait_window = lambda *a, **k: None
        dialogo = modulo.Conferma(finestra, finestra.L, "prova")
        finestra.wait_window = vera_attesa
        controlla("conferma: parte spenta", "disabled" in dialogo.ok.state())
        dialogo.var.set("scrivo")
        finestra.update()
        controlla("conferma: parola sbagliata resta spenta",
                  "disabled" in dialogo.ok.state())
        dialogo.var.set("SCRIVI")
        finestra.update()
        controlla("conferma: parola giusta accende",
                  "disabled" not in dialogo.ok.state())
        dialogo.destroy()

        # ---- 5. la qualifica del collegamento ----------------------
        finestra.qualifica_collegamento()
        aspetta(finestra, 300)
        controlla("qualifica: sceglie una velocità",
                  finestra.var_velocita.get() in modulo.VELOCITA,
                  repr(finestra.var_velocita.get()))
        controlla("qualifica: ripulisce i file di prova",
                  not any(f.startswith("qualifica-") for f in os.listdir(LAVORO)),
                  str([f for f in os.listdir(LAVORO) if f.startswith("qualifica-")]))
        # la qualifica invalida la lettura: si rifa'
        finestra.leggi_e_verifica()
        aspetta(finestra)
        controlla("lettura rifatta dopo la qualifica",
                  finestra.lettura_verificata == md5(STOCK))

        # ---- 6. la prova a secco -----------------------------------
        finestra.var_modo.set("regione")
        finestra.var_immagine.set(ATTESO)
        finestra.var_layout.set(LAYOUT)
        finestra._ricarica_regioni()
        finestra.var_regione.set("uefi")
        finestra.var_atteso.set(ATTESO)
        finestra.var_alimentazione.set(1)
        finestra._aggiorna_scrittura()

        controlla("senza prova a secco non si scrive",
                  finestra._requisiti_mancanti() == ["prova a secco"],
                  str(finestra._requisiti_mancanti()))
        finestra.prova_a_secco()
        aspetta(finestra, 300)
        secco = finestra.secco
        controlla("prova a secco eseguita", secco is not None)
        controlla("prova a secco: md5 = risultato atteso",
                  secco and secco.md5 == md5(ATTESO),
                  (secco.md5[:8] if secco else "") + " vs " + md5(ATTESO)[:8])
        controlla("prova a secco: un solo intervallo",
                  secco and len(secco.cambia) == 1,
                  str([(hex(a), hex(b)) for a, b in (secco.cambia if secco else [])]))
        controlla("prova a secco: niente fuori regione",
                  secco and secco.fuori == [])
        controlla("prova a secco: byte contati",
                  secco and secco.byte_cambiati == 1321026,
                  str(secco.byte_cambiati if secco else 0))

        # ---- 7. la scrittura della sola regione uefi ---------------
        vera_conferma = modulo.Conferma

        class ConfermaFinta(object):
            def __init__(self, *a, **k):
                self.confermato = True

        modulo.Conferma = ConfermaFinta

        controlla("tutti i requisiti soddisfatti",
                  finestra._requisiti_mancanti() == [],
                  str(finestra._requisiti_mancanti()))
        controlla("tasto scrivi acceso", "disabled" not in finestra.b_scrivi.state())

        finestra.scrivi()
        aspetta(finestra, 600)
        modulo.Conferma = vera_conferma

        controlla("il chip emulato ora e' il risultato atteso",
                  md5(CHIP_FINTO) == md5(ATTESO),
                  "%s vs %s" % (md5(CHIP_FINTO)[:8], md5(ATTESO)[:8]))
        controlla("verifica finale: nessuna differenza",
                  any("nessuna differenza" in r or "no difference" in r
                      for r in finestra.righe_registro))
        controlla("verifica finale: regione coerente",
                  any("coerente" in r or "coherent" in r
                      for r in finestra.righe_registro),
                  next((r for r in finestra.righe_registro if "coerent" in r), ""))
        controlla("rilettura di controllo salvata",
                  any(f.startswith("bc250-dopo-") for f in os.listdir(LAVORO)))
        controlla("registro su file",
                  os.path.isfile(os.path.join(LAVORO, "programmatore-bios.log")))

        # ---- 8. la mappa ha visto passare i blocchi veri ------------
        import mappa as M
        stati = set(finestra.mappa.stati)
        controlla("mappa: blocchi verificati", M.VERIFICATO in stati)
        controlla("mappa: nessun blocco diverso", M.DIVERSO not in stati,
                  str(sorted(stati)))

        # ---- 9. confronto e layout generato ------------------------
        import analisi as A
        conf = A.confronta(A.leggi(STOCK), A.leggi(ATTESO))
        controlla("confronto: un intervallo allineato",
                  len(conf["allineati"]) == 1,
                  str([(hex(a), hex(b)) for a, b in conf["allineati"]]))
        controlla("confronto: confini veri noti",
                  conf["esatti"] == [(0xAE0088, 0xC228C9)],
                  str([(hex(a), hex(b)) for a, b in conf["esatti"]]))
        testo = A.genera_layout(conf["allineati"], 16 * 1024 * 1024, "uefi")
        atteso_layout = ("00000000:00adffff salta0\n"
                         "00ae0000:00c22fff uefi\n"
                         "00c23000:00ffffff salta2\n")
        controlla("layout generato copre tutto il chip", testo == atteso_layout,
                  repr(testo))
        controlla("layout generato accettato da flashrom",
                  len(fr.leggi_layout(_scrivi_temp(testo))) == 3)

    except Exception:
        traceback.print_exc()
        esiti.append(("eccezione", False))
    finally:
        finestra.destroy()


def main():
    if os.path.isdir(LAVORO):
        shutil.rmtree(LAVORO, ignore_errors=True)
    os.makedirs(LAVORO)
    finestra = modulo.App()
    finestra.after(300, lambda: prova(finestra))
    finestra.mainloop()
    falliti = [n for n, ok in esiti if not ok]
    print("\n%d controlli, %d falliti" % (len(esiti), len(falliti)))
    for n in falliti:
        print("   FALLITO:", n)
    return 1 if falliti else 0


if __name__ == "__main__":
    sys.exit(main())
