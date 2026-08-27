# -*- coding: utf-8 -*-
"""Costruisce la finestra, la esercita e la chiude: serve a scoprire gli errori
di costruzione senza stare li' a cliccare."""
import io
import os
import shutil
import sys
import traceback

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
QUI = os.path.dirname(os.path.abspath(__file__))
CARTELLA = os.path.dirname(QUI)
sys.path.insert(0, QUI)
sys.path.insert(0, CARTELLA)

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
        finestra.flash = vero_flash or object()
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
