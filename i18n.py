# -*- coding: utf-8 -*-
"""Le scritte dell'interfaccia, in italiano e in inglese.

Una sola tabella: chiave -> {"it": ..., "en": ...}. Chi disegna l'interfaccia
chiede la chiave, non la frase, cosi' cambiare lingua non ridisegna niente a
mano. Le frasi con dei buchi si completano con .format() dal chiamante.

REGOLA DEL TESTO: asciutto. Una riga dice una cosa. Niente modi di dire, niente
frasi di colore: chi legge ha una scheda morta sul tavolo.

The interface strings, in Italian and English.
"""
from __future__ import unicode_literals

LINGUE = ("it", "en")
NOMI_LINGUA = {"it": "Italiano", "en": "English"}

T = {
    # --- finestra ------------------------------------------------------
    "titolo": {
        "it": "SPIranha — BC-250",
        "en": "SPIranha — BC-250",
    },
    "sottotitolo": {
        "it": "Raspberry Pi Pico · pico-serprog · connettore J4004",
        "en": "Raspberry Pi Pico · pico-serprog · header J4004",
    },
    "lingua": {"it": "Lingua", "en": "Language"},

    # --- flashrom mancante ---------------------------------------------
    "flashrom_assente": {
        "it": "flashrom.exe non trovato. Senza, il chip non è raggiungibile.",
        "en": "flashrom.exe not found. Without it the chip cannot be reached.",
    },
    "flashrom_individua": {"it": "Individua…", "en": "Locate…"},
    "flashrom_trovato": {"it": "flashrom {versione} · {percorso}",
                         "en": "flashrom {versione} · {percorso}"},
    "flashrom_non_valido": {
        "it": "Il file scelto non risponde come flashrom.",
        "en": "The chosen file does not answer like flashrom.",
    },
    "flashrom_scegli": {"it": "Scegli flashrom.exe", "en": "Select flashrom.exe"},

    # --- 1. collegamento ------------------------------------------------
    "sez_collegamento": {"it": "1 · Collegamento", "en": "1 · Connection"},
    "porta": {"it": "Porta", "en": "Port"},
    "rileva": {"it": "Rileva", "en": "Detect"},
    "prova": {"it": "Interroga", "en": "Query"},
    "velocita": {"it": "Velocità", "en": "Speed"},
    "velocita_nota": {
        "it": "Ridurre se le due letture non coincidono.",
        "en": "Lower it if the two reads disagree.",
    },
    "nessuna_porta": {"it": "Nessuna porta seriale.", "en": "No serial port."},
    "pico_riconosciuto": {
        "it": "{nome} · interfaccia v{versione} · bus {bus}",
        "en": "{nome} · interface v{versione} · bus {bus}",
    },
    "pico_non_apre": {"it": "{porta} non si apre: {motivo}",
                      "en": "{porta} will not open: {motivo}"},
    "pico_no_spi": {
        "it": "Il programmatore non dichiara SPI.",
        "en": "The programmer does not declare SPI.",
    },
    "seriale_assente": {
        "it": "pyserial assente: la porta va scritta a mano.",
        "en": "pyserial missing: type the port by hand.",
    },

    # --- 2. chip ---------------------------------------------------------
    "sez_chip": {"it": "2 · Chip", "en": "2 · Chip"},
    "identifica": {"it": "Identifica", "en": "Identify"},
    "chip_forzato": {"it": "Modello", "en": "Model"},
    "chip_trovato": {"it": "{chip}", "en": "{chip}"},
    "chip_non_trovato": {
        "it": "Nessun chip riconosciuto. Verificare i collegamenti.",
        "en": "No chip detected. Check the wiring.",
    },
    "chip_ambiguo": {
        "it": "Più modelli compatibili: sceglierne uno in «Modello».",
        "en": "Several models match: pick one under “Model”.",
    },

    # --- 3. lettura ------------------------------------------------------
    "sez_lettura": {"it": "3 · Lettura e backup", "en": "3 · Read and backup"},
    "cartella": {"it": "Cartella", "en": "Folder"},
    "sfoglia": {"it": "…", "en": "…"},
    "leggi": {"it": "Leggi e verifica", "en": "Read and verify"},
    "leggi_nota": {
        "it": "Due letture consecutive, impronte a confronto.",
        "en": "Two consecutive reads, fingerprints compared.",
    },
    "lettura_1": {"it": "Prima lettura…", "en": "First read…"},
    "lettura_2": {"it": "Seconda lettura…", "en": "Second read…"},
    "lettura_ok": {
        "it": "Letture coincidenti · md5 {md5}",
        "en": "Reads match · md5 {md5}",
    },
    "lettura_diversa": {
        "it": "Letture diverse ({a} ≠ {b}). Collegamento non affidabile: "
              "verificare i cavi e ridurre la velocità. Non scrivere.",
        "en": "Reads differ ({a} ≠ {b}). Unreliable connection: check the wires "
              "and lower the speed. Do not write.",
    },
    "lettura_salvata": {"it": "Salvato in {percorso}", "en": "Saved to {percorso}"},
    "lettura_fallita": {
        "it": "Lettura fallita (codice {codice}). Dettaglio nel registro.",
        "en": "Read failed (code {codice}). Details in the log.",
    },
    "riconosciuto_come": {"it": "Riconosciuto: {cosa}", "en": "Recognised: {cosa}"},
    "md5_stock": {
        "it": "BIOS originale P3.00 di questa scheda",
        "en": "original P3.00 BIOS of this board",
    },
    "md5_atteso": {
        "it": "risultato atteso dopo la scrittura della regione UEFI",
        "en": "expected result after writing the UEFI region",
    },
    "md5_sconosciuto": {
        "it": "impronta non nota",
        "en": "unknown fingerprint",
    },

    # --- 4. scrittura ----------------------------------------------------
    "sez_scrittura": {"it": "4 · Scrittura", "en": "4 · Writing"},
    "modo": {"it": "Ambito", "en": "Scope"},
    "modo_regione": {"it": "Una regione", "en": "One region"},
    "modo_intero": {"it": "Chip intero", "en": "Whole chip"},
    "immagine": {"it": "Immagine", "en": "Image"},
    "file_layout": {"it": "Layout", "en": "Layout"},
    "regione": {"it": "Regione", "en": "Region"},
    "atteso": {"it": "Atteso", "en": "Expected"},
    "atteso_nota": {
        "it": "facoltativo · rilettura e confronto a fine scrittura",
        "en": "optional · re-read and compare after writing",
    },
    "spunta_alimentazione": {
        "it": "BC-250 staccata dalla corrente",
        "en": "BC-250 unplugged from mains",
    },
    "scrivi": {"it": "Scrivi…", "en": "Write…"},
    "scrivi_bloccato": {
        "it": "Manca: {cosa}",
        "en": "Missing: {cosa}",
    },
    "req_flashrom": {"it": "flashrom", "en": "flashrom"},
    "req_chip": {"it": "identificazione del chip", "en": "chip identification"},
    "req_lettura": {
        "it": "lettura verificata",
        "en": "verified read",
    },
    "req_immagine": {"it": "immagine", "en": "image"},
    "req_layout": {"it": "layout e regione", "en": "layout and region"},
    "req_alimentazione": {"it": "conferma alimentazione", "en": "mains confirmation"},
    "req_dimensione": {
        "it": "immagine di {attesa} byte, questa è di {trovata}",
        "en": "image must be {attesa} bytes, this one is {trovata}",
    },

    # --- conferma --------------------------------------------------------
    "conferma_titolo": {"it": "Confermare la scrittura", "en": "Confirm the write"},
    "conferma_testo_regione": {
        "it": "Regione «{regione}» — {byte} byte, da 0x{inizio:06X} a 0x{fine:06X}.\n"
              "Chip {chip}.\nSorgente: {immagine}\n\n"
              "Il chip viene cancellato a settori e riscritto. In caso di errore "
              "la scheda non si avvia: si riparte da qui con l'immagine di recupero.",
        "en": "Region “{regione}” — {byte} bytes, 0x{inizio:06X} to 0x{fine:06X}.\n"
              "Chip {chip}.\nSource: {immagine}\n\n"
              "The chip is erased by sectors and rewritten. On error the board will "
              "not boot: you start again from here with the recovery image.",
    },
    "conferma_testo_intero": {
        "it": "Chip intero — {byte} byte.\nChip {chip}.\nSorgente: {immagine}\n\n"
              "Vengono sovrascritte anche le impostazioni del BIOS e la "
              "configurazione della memoria di questo esemplare.",
        "en": "Whole chip — {byte} bytes.\nChip {chip}.\nSource: {immagine}\n\n"
              "The BIOS settings and this board's memory configuration are "
              "overwritten too.",
    },
    "conferma_digita": {
        "it": "Digitare {parola} per procedere",
        "en": "Type {parola} to proceed",
    },
    "parola_conferma": {"it": "SCRIVI", "en": "WRITE"},
    "annulla": {"it": "Annulla", "en": "Cancel"},
    "procedi": {"it": "Procedi", "en": "Proceed"},

    # --- esiti scrittura --------------------------------------------------
    "scrittura_avvio": {"it": "Scrittura in corso…", "en": "Writing…"},
    "scrittura_ok": {
        "it": "Scritto e verificato da flashrom.",
        "en": "Written and verified by flashrom.",
    },
    "scrittura_fallita": {
        "it": "Scrittura fallita (codice {codice}). Non scollegare e non "
              "ricollegare l'alimentazione: leggere il registro.",
        "en": "Write failed (code {codice}). Do not disconnect and do not "
              "reconnect mains: read the log.",
    },
    "rilettura": {"it": "Rilettura di controllo…", "en": "Verification re-read…"},
    "rilettura_uguale": {
        "it": "La rilettura coincide con il risultato atteso.",
        "en": "The re-read matches the expected result.",
    },
    "rilettura_diversa": {
        "it": "La rilettura non coincide ({a} ≠ {b}). Non ricollegare "
              "l'alimentazione.",
        "en": "The re-read does not match ({a} ≠ {b}). Do not reconnect mains.",
    },

    # --- registro ---------------------------------------------------------
    "sez_registro": {"it": "Registro", "en": "Log"},
    "interrompi": {"it": "Interrompi", "en": "Stop"},
    "pulisci": {"it": "Pulisci", "en": "Clear"},
    "salva_registro": {"it": "Salva", "en": "Save"},
    "interruzione_vietata": {
        "it": "Una scrittura non si interrompe.",
        "en": "A write is not interrupted.",
    },
    "interrotto": {"it": "Interrotto.", "en": "Stopped."},
    "in_corso": {
        "it": "Operazione già in corso.",
        "en": "An operation is already running.",
    },
    "occupato": {"it": "in corso…", "en": "running…"},
    "pronto": {"it": "pronto", "en": "ready"},
    "chiudere_mentre_lavora": {
        "it": "Operazione in corso. Chiudere adesso può lasciare il chip a metà. "
              "Chiudere comunque?",
        "en": "An operation is running. Closing now may leave the chip half "
              "written. Close anyway?",
    },

    # --- firmware del programmatore ----------------------------------------
    "firmware": {"it": "Firmware", "en": "Firmware"},
    "fw_nessuna": {
        "it": "Nessuna scheda in BOOTSEL. Per programmarne una: staccarla, "
              "tenere premuto BOOTSEL, riattaccarla.",
        "en": "No board in BOOTSEL. To program one: unplug it, hold BOOTSEL, "
              "plug it back in.",
    },
    "fw_trovata": {
        "it": "{modello} su {unita} — pronta per il firmware",
        "en": "{modello} on {unita} — ready for firmware",
    },
    "nome_scheda": {"it": "Nome", "en": "Name"},
    "nome_scheda_nota": {
        "it": "un nome per riconoscerla fra le altre",
        "en": "a name to tell it from the others",
    },
    "fw_seriale": {"it": "seriale {seriale}", "en": "serial {seriale}"},
    "fw_trovata_nome": {
        "it": "{nome} \u00b7 {modello} su {unita} \u00b7 {seriale}",
        "en": "{nome} \u00b7 {modello} on {unita} \u00b7 {seriale}",
    },
    "fw_trovata_anonima": {
        "it": "{modello} su {unita} \u00b7 {seriale} \u00b7 senza nome",
        "en": "{modello} on {unita} \u00b7 {seriale} \u00b7 unnamed",
    },
    "fw_battezzata": {
        "it": "Scheda registrata come \u00ab{nome}\u00bb.",
        "en": "Board registered as \u201c{nome}\u201d.",
    },
    "fw_dimenticata": {
        "it": "Nome tolto: la scheda torna anonima.",
        "en": "Name removed: the board is unnamed again.",
    },
    "parola_cancella": {"it": "CANCELLA", "en": "ERASE"},
    "fw_azzera_uno": {
        "it": "Primo consenso su due.\n\nSto per cancellare tutta la flash di "
              "{chi}: {byte}.\n\nLa scheda smette di essere un programmatore e "
              "torna come appena comprata. Il firmware si potr\u00e0 rimettere da "
              "qui, ma finch\u00e9 non lo fai quella scheda non serve a niente.",
        "en": "First of two confirmations.\n\nAbout to erase the whole flash of "
              "{chi}: {byte}.\n\nThe board stops being a programmer and goes "
              "back to as-bought. The firmware can be put back from here, but "
              "until you do, that board is of no use.",
    },
    "fw_azzera_due": {
        "it": "Secondo consenso.\n\nControlla di avere in mano la scheda "
              "giusta: quella collegata su {unita} ha il seriale\n\n"
              "    {seriale}\n\nPer procedere ribatti le ultime quattro cifre.",
        "en": "Second confirmation.\n\nMake sure you are holding the right "
              "board: the one on {unita} has serial\n\n    {seriale}\n\n"
              "To proceed, retype its last four characters.",
    },
    "fw_azzera_due_senza": {
        "it": "Secondo consenso.\n\nDi questa scheda non si legge il seriale. "
              "Verifica di persona che quella collegata su {unita} sia quella "
              "che vuoi cancellare.",
        "en": "Second confirmation.\n\nThis board\u2019s serial cannot be read. "
              "Check by hand that the one on {unita} is the one you mean to "
              "erase.",
    },
    "fw_bootsel": {"it": "Riporta in BOOTSEL", "en": "Send to BOOTSEL"},
    "fw_bootsel_provo": {
        "it": "Chiedo alla scheda su {porta} di riavviarsi nel bootloader\u2026",
        "en": "Asking the board on {porta} to reboot into the bootloader\u2026",
    },
    "fw_bootsel_ok": {
        "it": "Rientrata in BOOTSEL su {unita}, senza toccare il pulsante.",
        "en": "Back in BOOTSEL on {unita}, without touching the button.",
    },
    "fw_bootsel_no": {
        "it": "La scheda non \u00e8 rientrata in BOOTSEL. Con il firmware "
              "precedente al 1200 baud non risponde: staccarla, tenere premuto "
              "BOOTSEL, riattaccarla.",
        "en": "The board did not return to BOOTSEL. Firmware older than the "
              "1200-baud support ignores this: unplug it, hold BOOTSEL, plug it "
              "back in.",
    },
    "fw_installa": {"it": "Rendila programmatore", "en": "Make it a programmer"},
    "fw_azzera": {"it": "Riporta a nuovo", "en": "Reset to factory"},
    "fw_assente": {
        "it": "firmware/pico_serprog.uf2 non c\u0027e\u0027: vedi firmware/README.md",
        "en": "firmware/pico_serprog.uf2 is missing: see firmware/README.md",
    },
    "fw_installando": {"it": "Copio il firmware\u2026", "en": "Copying the firmware\u2026"},
    "fw_attendo": {
        "it": "Firmware copiato. La scheda si riavvia: aspetto la porta seriale\u2026",
        "en": "Firmware copied. The board reboots: waiting for the serial port\u2026",
    },
    "fw_pronto": {
        "it": "Programmatore pronto su {porta}.",
        "en": "Programmer ready on {porta}.",
    },
    "fw_non_riappare": {
        "it": "Firmware copiato, ma la porta seriale non \u00e8 comparsa. Staccare e "
              "riattaccare la scheda.",
        "en": "Firmware copied, but no serial port appeared. Unplug the board and "
              "plug it back in.",
    },
    "fw_errore": {"it": "{motivo}", "en": "{motivo}"},
    "fw_azzera_titolo": {
        "it": "Riportare la scheda a nuovo",
        "en": "Reset the board to factory",
    },
    "fw_azzera_testo": {
        "it": "Sto per cancellare tutta la flash di {modello} su {unita}: "
              "{byte}.\n\nLa scheda torner\u00e0 come appena comprata e ricomparir\u00e0 "
              "come disco RPI-RP2. Il firmware si potr\u00e0 rimettere da qui.",
        "en": "About to erase the whole flash of {modello} on {unita}: {byte}.\n\n"
              "The board goes back to as-bought and will show up again as the "
              "RPI-RP2 drive. The firmware can be put back from here.",
    },
    "fw_azzerando": {"it": "Cancello la flash\u2026", "en": "Erasing the flash\u2026"},
    "fw_azzerato": {
        "it": "Scheda riportata a nuovo: ricomparir\u00e0 come disco RPI-RP2.",
        "en": "Board reset: it will show up again as the RPI-RP2 drive.",
    },

    # --- mappa del chip ----------------------------------------------------
    "sez_mappa": {"it": "Mappa del chip", "en": "Chip map"},
    "leg_ignoto": {"it": "da fare", "en": "pending"},
    "leg_letto": {"it": "letto", "en": "read"},
    "leg_cancellato": {"it": "cancellato", "en": "erased"},
    "leg_scritto": {"it": "scritto", "en": "written"},
    "leg_verificato": {"it": "verificato", "en": "verified"},
    "leg_diverso": {"it": "diverso", "en": "mismatch"},
    "mappa_riposo": {
        "it": "{dimensione} · {blocchi} blocchi da {grana}",
        "en": "{dimensione} · {blocchi} blocks of {grana}",
    },
    "mappa_posizione": {"it": "0x{posizione:06X}", "en": "0x{posizione:06X}"},

    # --- prova a secco ------------------------------------------------------
    "prova_secco": {"it": "Prova a secco", "en": "Dry run"},
    "secco_ok": {
        "it": "Cambieranno {byte} in {intervalli} intervalli, tutti dentro la "
              "regione. md5 atteso {md5}",
        "en": "{byte} will change in {intervalli} ranges, all inside the "
              "region. Expected md5 {md5}",
    },
    "secco_ok_uno": {
        "it": "Cambieranno {byte} in un solo intervallo, dentro la regione. "
              "md5 atteso {md5}",
        "en": "{byte} will change in a single range, inside the region. "
              "Expected md5 {md5}",
    },
    "verifica_diversa_uno": {
        "it": "Un intervallo non coincide ({byte}). Non ricollegare "
              "l'alimentazione.",
        "en": "One range does not match ({byte}). Do not reconnect mains.",
    },
    "secco_nulla": {
        "it": "Nessuna differenza: il chip contiene già questa immagine.",
        "en": "No difference: the chip already holds this image.",
    },
    "secco_fuori": {
        "it": "{intervalli} intervalli differiscono anche fuori dalla regione: "
              "non verranno scritti. Cambieranno {byte} byte. md5 atteso {md5}",
        "en": "{intervalli} ranges also differ outside the region: they will not "
              "be written. {byte} bytes will change. Expected md5 {md5}",
    },
    "secco_atteso_diverso": {
        "it": "Il risultato calcolato NON coincide con il file «Atteso» "
              "({calcolato} ≠ {atteso}). Controllare immagine, layout e regione.",
        "en": "The computed result does NOT match the “Expected” file "
              "({calcolato} ≠ {atteso}). Check image, layout and region.",
    },
    "secco_atteso_uguale": {
        "it": "Il risultato calcolato coincide con il file «Atteso».",
        "en": "The computed result matches the “Expected” file.",
    },
    "req_secco": {"it": "prova a secco", "en": "dry run"},

    # --- qualifica del collegamento ----------------------------------------
    "qualifica": {"it": "Qualifica", "en": "Qualify"},
    "qualifica_nota": {
        "it": "Cerca la velocità più alta con letture ripetibili.",
        "en": "Finds the highest speed with repeatable reads.",
    },
    "qualifica_prova": {"it": "Provo a {velocita}…", "en": "Trying {velocita}…"},
    "qualifica_ok": {
        "it": "Velocità impostata: {velocita}. Due letture identiche su {byte}.",
        "en": "Speed set to {velocita}. Two identical reads over {byte}.",
    },
    "qualifica_nessuna": {
        "it": "Nessuna velocità dà letture ripetibili. Verificare i cavi e "
              "l'alimentazione del chip.",
        "en": "No speed gives repeatable reads. Check the wires and the chip "
              "supply.",
    },

    # --- avanzamento --------------------------------------------------------
    "fase_READ": {"it": "lettura", "en": "read"},
    "fase_ERASE": {"it": "cancellazione", "en": "erase"},
    "fase_WRITE": {"it": "scrittura", "en": "write"},
    "fase_VERIFY": {"it": "verifica", "en": "verify"},
    "avanzamento": {
        "it": "{fase} {percento}%",
        "en": "{fase} {percento}%",
    },
    "avanzamento_resta": {
        "it": "{fase} {percento}% · {resta} alla fine",
        "en": "{fase} {percento}% · {resta} left",
    },

    # --- verifica finale ----------------------------------------------------
    "verifica_finale": {"it": "Verifica finale…", "en": "Final verification…"},
    "verifica_ok": {
        "it": "Il chip contiene esattamente la nuova ROM: {byte} confrontati, "
              "nessuna differenza.",
        "en": "The chip holds exactly the new ROM: {byte} compared, no difference.",
    },
    "verifica_diversa": {
        "it": "{intervalli} intervalli non coincidono ({byte}). Non ricollegare "
              "l'alimentazione.",
        "en": "{intervalli} ranges do not match ({byte}). Do not reconnect mains.",
    },
    "coerenza_ok": {"it": "Regione coerente: {cosa}.", "en": "Region coherent: {cosa}."},
    "coerenza_nulla": {
        "it": "Regione scritta, ma senza strutture note al suo interno.",
        "en": "Region written, but with no known structures inside.",
    },
    "coerenza_vuota": {
        "it": "La regione è tutta 0xFF: cancellata e non riscritta.",
        "en": "The region is all 0xFF: erased and not rewritten.",
    },
    "coerenza_zero": {
        "it": "La regione è tutta 0x00.",
        "en": "The region is all 0x00.",
    },

    # --- confronto fra immagini ---------------------------------------------
    "conf_apri": {"it": "Confronta", "en": "Compare"},
    "conf_titolo": {"it": "Confronto fra immagini", "en": "Image comparison"},
    "conf_sotto": {
        "it": "Intervalli diversi, allineati ai settori da 4 KB, e layout pronto "
              "per flashrom",
        "en": "Differing ranges, aligned to 4 KB sectors, and a layout ready for "
              "flashrom",
    },
    "conf_sez_file": {"it": "Immagini da confrontare", "en": "Images to compare"},
    "conf_sez_esito": {"it": "Differenze", "en": "Differences"},
    "conf_a": {"it": "Immagine A", "en": "Image A"},
    "conf_b": {"it": "Immagine B", "en": "Image B"},
    "conf_esegui": {"it": "Confronta", "en": "Compare"},
    "conf_uguali": {
        "it": "Le due immagini sono identiche.",
        "en": "The two images are identical.",
    },
    "conf_risultato": {
        "it": "{intervalli} intervalli diversi · {byte}",
        "en": "{intervalli} differing ranges · {byte}",
    },
    "conf_risultato_uno": {
        "it": "1 intervallo diverso · {byte}",
        "en": "1 differing range · {byte}",
    },
    "conf_dimensioni": {
        "it": "Dimensioni diverse: {a} e {b}. Non confrontabili.",
        "en": "Different sizes: {a} and {b}. Not comparable.",
    },
    "conf_col_intervallo": {"it": "Intervallo (settori)", "en": "Range (sectors)"},
    "conf_col_esatto": {"it": "Confini veri", "en": "True bounds"},
    "conf_col_dim": {"it": "Dimensione", "en": "Size"},
    "conf_col_cosa": {"it": "Contenuto", "en": "Contents"},
    "conf_salva_layout": {"it": "Salva layout…", "en": "Save layout…"},
    "conf_nome": {"it": "Nome regione", "en": "Region name"},
    "conf_salvato": {"it": "Layout salvato in {percorso}",
                     "en": "Layout saved to {percorso}"},
    "conf_scegli": {"it": "Scegliere due immagini.", "en": "Pick two images."},

    # --- schema dei collegamenti -------------------------------------------
    "sch_apri": {"it": "Schema", "en": "Diagram"},
    "sch_titolo": {"it": "Schema dei collegamenti", "en": "Wiring diagram"},
    "sch_sotto": {
        "it": "Raspberry Pi Pico (RP2040) → BC-250, connettore J4004",
        "en": "Raspberry Pi Pico (RP2040) → BC-250, header J4004",
    },
    "sch_pico": {"it": "Raspberry Pi Pico", "en": "Raspberry Pi Pico"},
    "sch_pico_nota": {
        "it": "Visto da sopra, USB in alto. Piedino 1 in alto a sinistra.",
        "en": "Seen from above, USB at the top. Pin 1 top left.",
    },
    "sch_conn": {"it": "BC-250 · J4004", "en": "BC-250 · J4004"},
    "sch_conn_nota": {
        "it": "2×4, passo 2,54 mm. Triangolo bianco in serigrafia = piedino 1 (VCC).",
        "en": "2×4, 2.54 mm pitch. White silkscreen triangle = pin 1 (VCC).",
    },
    "sch_unk": {
        "it": "UNK: funzione ignota, a massa con 10 kΩ. Non collegare.",
        "en": "UNK: unknown function, tied to ground via 10 kΩ. Do not connect.",
    },
    "sch_nc": {"it": "n.d.", "en": "n/a"},
    "sch_tabella": {"it": "Collegamenti", "en": "Connections"},
    "sch_col_segnale": {"it": "Segnale", "en": "Signal"},
    "sch_col_pico": {"it": "Pico", "en": "Pico"},
    "sch_col_conn": {"it": "J4004", "en": "J4004"},
    "sch_gnd_nota": {
        "it": "GND dal piedino 3: sta accanto ai quattro segnali, così i cavi "
              "3-4-5-6-7 sono contigui. Va bene qualunque altro GND "
              "(8, 13, 18, 23, 28, 33, 38).",
        "en": "GND from pin 3: it sits next to the four signals, so wires "
              "3-4-5-6-7 are contiguous. Any other GND works too "
              "(8, 13, 18, 23, 28, 33, 38).",
    },
    "sch_av_titolo": {"it": "Prima di collegare", "en": "Before connecting"},
    "sch_av1": {
        "it": "BC-250 staccata dalla corrente. A spina estratta premere il tasto "
              "di accensione 2-3 volte per scaricare i condensatori.",
        "en": "BC-250 unplugged from mains. With the plug out, press the power "
              "button 2-3 times to drain the capacitors.",
    },
    "sch_av2": {
        "it": "Il bersaglio è BIOS_A1, 16 MB. Non SIO1_R da 512 KB: è il SuperIO "
              "e ne dipende il controllo delle ventole. Se il programma riporta "
              "512 KB, il chip è quello sbagliato.",
        "en": "The target is BIOS_A1, 16 MB. Not SIO1_R at 512 KB: that is the "
              "SuperIO and fan control depends on it. If the program reports "
              "512 KB, it is the wrong chip.",
    },
    "sch_av3": {
        "it": "Verificare con il tester la continuità del piedino GND con la massa "
              "della scheda prima di alimentare.",
        "en": "With a multimeter, verify continuity between the GND pin and board "
              "ground before powering up.",
    },
    "sch_av4": {
        "it": "Alimentazione solo dal Pico (3V3, piedino 36).",
        "en": "Power from the Pico only (3V3, pin 36).",
    },
    # --- promemoria fisso --------------------------------------------------
    "promemoria": {
        "it": "BC-250 staccata dalla corrente. Il chip è alimentato dal Pico "
              "(3V3, piedino 36).",
        "en": "BC-250 unplugged from mains. The chip is powered by the Pico "
              "(3V3, pin 36).",
    },
}


class Lingua(object):
    """Tiene la lingua corrente e restituisce le frasi."""

    def __init__(self, codice="it"):
        self.codice = codice if codice in LINGUE else "it"

    def __call__(self, chiave, **campi):
        voce = T.get(chiave)
        if voce is None:
            return "?" + chiave + "?"
        testo = voce.get(self.codice) or voce["it"]
        return testo.format(**campi) if campi else testo
