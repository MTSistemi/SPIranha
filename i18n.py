# -*- coding: utf-8 -*-
"""The interface strings, in Italian and English.

One table: key -> {"it": ..., "en": ...}. Whoever builds the interface asks
for the key, not the sentence, so switching language redraws nothing by hand.
Sentences with holes are filled in by the caller with .format().

RULE FOR THE TEXT: dry. One line says one thing. No idioms, no colour: the
person reading has a dead board on the desk.

⚠️ The Italian strings stay Italian. This is the one file where that is the
point: the program speaks both languages.
"""
from __future__ import unicode_literals

LANGUAGES = ("it", "en")
LANGUAGE_NAMES = {"it": "Italiano", "en": "English"}

T = {
    # --- window --------------------------------------------------------
    "title": {"it": "SPIranha", "en": "SPIranha"},
    # ⚠️ The subtitle says WHAT is being worked on: the profile name goes
    # inside it, or the header would always talk about a BC-250.
    "subtitle": {
        "it": "Raspberry Pi Pico · pico-serprog · {board}",
        "en": "Raspberry Pi Pico · pico-serprog · {board}",
    },
    "language": {"it": "Lingua", "en": "Language"},

    # --- a newer version --------------------------------------------------
    "up_found": {
        "it": "C'è la versione {version} (questa è la {running}).",
        "en": "Version {version} is out (this one is {running}).",
    },
    "up_install": {"it": "Aggiorna", "en": "Update"},
    "up_page": {"it": "Vedi le novità", "en": "What changed"},
    "up_later": {"it": "Non ora", "en": "Not now"},
    "up_downloading": {
        "it": "Scarico l'aggiornamento… {done} di {total}",
        "en": "Downloading the update… {done} of {total}",
    },
    "up_checking": {"it": "Controllo aggiornamenti…", "en": "Checking for updates…"},
    "up_confirm_title": {"it": "Aggiornare SPIranha", "en": "Update SPIranha"},
    "up_confirm": {
        "it": "Scaricata la versione {version}.\n\nFirma verificata: {signer}\n"
              "sha-256: {hash}\n\nParte l'installatore e questa finestra si "
              "chiude. Nessuna operazione dev'essere in corso.\n\nProcedere?",
        "en": "Version {version} downloaded.\n\nSignature checked: {signer}\n"
              "sha-256: {hash}\n\nThe installer will start and this window "
              "will close. Nothing must be running.\n\nGo ahead?",
    },
    "up_refused": {
        "it": "Aggiornamento rifiutato: {reason}. Il file NON è stato eseguito.",
        "en": "Update refused: {reason}. The file was NOT run.",
    },
    "up_failed": {
        "it": "Non sono riuscito a scaricare l'aggiornamento: {reason}",
        "en": "Could not download the update: {reason}",
    },
    "up_check_at_start": {
        "it": "Cerca aggiornamenti all'avvio",
        "en": "Check for updates at startup",
    },
    "up_check_nota": {
        "it": "Una richiesta a GitHub all'apertura. Niente si installa da solo: "
              "l'installatore parte solo se glielo dici, e solo se è firmato "
              "con il nostro certificato.",
        "en": "One request to GitHub when the program opens. Nothing installs "
              "by itself: the installer runs only if you say so, and only if "
              "it carries our signature.",
    },

    # --- flashrom missing ----------------------------------------------
    "flashrom_missing": {
        "it": "flashrom.exe non trovato. Senza, il chip non è raggiungibile.",
        "en": "flashrom.exe not found. Without it the chip cannot be reached.",
    },
    "flashrom_locate": {"it": "Individua…", "en": "Locate…"},
    "flashrom_found": {"it": "flashrom {version} · {path}",
                         "en": "flashrom {version} · {path}"},
    "flashrom_invalid": {
        "it": "Il file scelto non risponde come flashrom.",
        "en": "The chosen file does not answer like flashrom.",
    },
    "flashrom_pick": {"it": "Scegli flashrom.exe", "en": "Select flashrom.exe"},

    # --- 1. connection --------------------------------------------------
    "sec_connection": {"it": "1 · Collegamento", "en": "1 · Connection"},
    "port": {"it": "Porta", "en": "Port"},
    "detect": {"it": "Rileva", "en": "Detect"},
    "query": {"it": "Interroga", "en": "Query"},
    "speed": {"it": "Velocità", "en": "Speed"},
    "speed_note": {
        "it": "Ridurre se le due letture non coincidono.",
        "en": "Lower it if the two reads disagree.",
    },
    "no_port": {"it": "Nessuna porta seriale.", "en": "No serial port."},
    "pico_known": {
        "it": "{name} · interfaccia v{version} · bus {bus}",
        "en": "{name} · interface v{version} · bus {bus}",
    },
    "pico_wont_open": {"it": "{port} non si apre: {reason}",
                      "en": "{port} will not open: {reason}"},
    "pico_no_spi": {
        "it": "Il programmatore non dichiara SPI.",
        "en": "The programmer does not declare SPI.",
    },
    "pyserial_missing": {
        "it": "pyserial assente: la porta va scritta a mano.",
        "en": "pyserial missing: type the port by hand.",
    },

    # --- firmware version ---------------------------------------------------
    "fw_version_ok": {
        "it": "Firmware {version}, \u00e8 l'ultimo che abbiamo.",
        "en": "Firmware {version}, the latest one we carry.",
    },
    "fw_version_old": {
        "it": "Firmware {version} sulla scheda, qui c'\u00e8 la {newer}.",
        "en": "Firmware {version} on the board, we carry {newer}.",
    },
    "fw_version_silent": {
        "it": "Firmware anteriore alla 1.1: non dice quale sia. Qui c'"
              "\u00e8 la {newer}.",
        "en": "Firmware older than 1.1: it does not say which. We carry "
              "{newer}.",
    },
    "fw_update": {"it": "Aggiorna", "en": "Update"},
    "fw_updating": {
        "it": "Aggiornamento: rimando la scheda in BOOTSEL\u2026",
        "en": "Updating: sending the board back to BOOTSEL\u2026",
    },
    "fw_update_no_bootsel": {
        "it": "La scheda non torna in BOOTSEL da sola: il suo firmware "
              "\u00e8 anteriore alla 1.1, che \u00e8 la versione che ha "
              "aggiunto quel rientro. Serve il pulsante BOOTSEL, una volta "
              "sola: da qui in poi si aggiorna via cavo.",
        "en": "The board will not go back to BOOTSEL by itself: its firmware "
              "predates 1.1, which is the version that added that. The BOOTSEL "
              "button is needed once; after that it updates over the wire.",
    },
    "fw_updated": {
        "it": "Aggiornata alla {version} su {port}.",
        "en": "Updated to {version} on {port}.",
    },
    "fw_update_doubt": {
        "it": "Copia riuscita, ma la scheda dichiara ancora {version}.",
        "en": "Copy went through, but the board still reports {version}.",
    },

    # --- board profiles -----------------------------------------------------
    "profile": {"it": "Scheda", "en": "Board"},
    "prof_bc250_sio": {
        "it": "Sulla scheda ci sono due flash: quella da 16 MiB \u00e8 il BIOS, "
              "quella da 512 KiB \u00e8 il SuperIO. Il J4004 \u00e8 quello "
              "accanto al chip grande.",
        "en": "The board carries two flash chips: the 16 MiB one is the BIOS, "
              "the 512 KiB one is the SuperIO. J4004 is the header next to the "
              "big chip.",
    },
    "prof_gen_clip": {
        "it": "Con la scheda accesa il chip non si legge comunque: il chipset "
              "tiene il bus.",
        "en": "On a powered board the chip cannot be read anyway: the chipset "
              "holds the bus.",
    },
    "prof_size_differs": {
        "it": "Il profilo prevede {expected} byte, il chip ne ha {hit}.",
        "en": "The profile expects {expected} bytes, the chip has {hit}.",
    },
    "prof_chip_differs": {
        "it": "Il profilo prevede {expected}, qui c'\u00e8 {hit}. "
              "Pu\u00f2 essere una revisione diversa della stessa scheda.",
        "en": "The profile expects {expected}, this is {hit}. It may be a "
              "different revision of the same board.",
    },
    "prof_regions_missing": {
        "it": "Regioni attese e non trovate: {which}.",
        "en": "Regions expected and not found: {which}.",
    },
    "prof_as_expected": {
        "it": "Chip come previsto dal profilo.",
        "en": "Chip is what the profile expects.",
    },

    # --- wiring with the clip on the chip -----------------------------------
    "sch_title_clip": {
        "it": "Collegamenti: Pico \u2192 chip SPI in SOIC-8",
        "en": "Wiring: Pico \u2192 SOIC-8 SPI chip",
    },
    "sch_sub_clip": {
        "it": "Raspberry Pi Pico (RP2040) \u2192 pinza sul chip",
        "en": "Raspberry Pi Pico (RP2040) \u2192 clip on the chip",
    },
    "sch_chip_board": {"it": "il chip", "en": "the chip"},
    "sch_chip": {"it": "Chip \u00b7 SOIC-8", "en": "Chip \u00b7 SOIC-8"},
    "sch_chip_note": {
        "it": "Visto da sopra. La tacca \u00e8 dalla parte del piedino 1: "
              "1-4 scendendo a sinistra, 5-8 risalendo a destra.",
        "en": "Seen from above. The notch is on the pin 1 side: 1-4 going down "
              "the left, 5-8 going up the right.",
    },
    "sch_wp_note": {
        "it": "/WP e /HOLD vanno alti. Tenuti bassi, il chip accetta i comandi "
              "e non scrive niente: sui moduli con zoccolo ci pensa il modulo, "
              "sul chip nudo vanno portati a VCC.",
        "en": "/WP and /HOLD must be high. Held low, the chip takes the "
              "commands and writes nothing: breakout modules do it for you, on "
              "a bare chip they go to VCC.",
    },
    "sch_col_chip": {"it": "Chip", "en": "Chip"},
    "sch_clip_note": {
        "it": "I quattro segnali stanno su due lati opposti: i cavetti si "
              "incrociano, e va bene cos\u00ec. Conta il numero del piedino.",
        "en": "The four signals sit on opposite sides: the wires cross, and "
              "that is fine. What counts is the pin number.",
    },
    "sch_clip_warn1": {
        "it": "Scheda staccata dalla corrente, sempre.",
        "en": "Board unplugged from mains, always.",
    },
    "sch_clip_warn2": {
        "it": "La pinza va messa con la tacca dalla parte del piedino 1: al "
              "contrario si mandano 3,3 V sulla massa del chip.",
        "en": "The clip goes on with the notch on the pin 1 side: the other "
              "way round puts 3.3 V on the chip ground.",
    },
    "sch_clip_warn3": {
        "it": "Chip a 1,8 V: il Pico non li regge. Serve un adattatore di "
              "livello, e alimentare il chip a 1,8 V.",
        "en": "1.8 V chips: the Pico cannot drive them. A level shifter is "
              "needed, and 1.8 V power for the chip.",
    },
    "sch_clip_warn4": {
        "it": "Se la scheda alimenta gi\u00e0 il chip da sola, non collegare "
              "VCC: solo massa e i quattro segnali.",
        "en": "If the board already powers the chip, leave VCC unconnected: "
              "ground and the four signals only.",
    },
    # --- 2. chip ---------------------------------------------------------
    "sec_chip": {"it": "2 · Chip", "en": "2 · Chip"},
    "identify": {"it": "Identifica", "en": "Identify"},
    "chip_forced": {"it": "Modello", "en": "Model"},
    "chip_found": {"it": "{chip}", "en": "{chip}"},
    "chip_not_found": {
        "it": "Nessun chip riconosciuto. Verificare i collegamenti.",
        "en": "No chip detected. Check the wiring.",
    },
    "chip_ambiguous": {
        "it": "Più modelli compatibili: sceglierne uno in «Modello».",
        "en": "Several models match: pick one under “Model”.",
    },

    # --- write protection ---------------------------------------------------
    "prot_free": {
        "it": "Chip non protetto in scrittura.",
        "en": "Chip is not write protected.",
    },
    "prot_active": {
        "it": "Protetto: 0x{start:06X}-0x{end:06X} ({description}), modo {mode}.",
        "en": "Protected: 0x{start:06X}-0x{end:06X} ({description}), mode {mode}.",
    },
    "prot_clash": {
        "it": "La protezione copre la regione da scrivere "
              "(0x{start:06X}-0x{end:06X}): la scrittura non passerebbe.",
        "en": "The protection covers the region to write "
              "(0x{start:06X}-0x{end:06X}): the write would not go through.",
    },
    "prot_unknown": {
        "it": "Il chip non risponde sullo stato della protezione.",
        "en": "The chip does not answer about its protection state.",
    },
    "prot_unlock": {"it": "Sblocca", "en": "Unlock"},
    "prot_confirm": {
        "it": "Sto per togliere la protezione in scrittura del chip "
              "{chip}.\n\nNon e' un'impostazione del programma: cambia lo "
              "stato del chip, e resta cos\u00ec anche staccando tutto. Su una "
              "scheda che si accende ancora, un BIOS non protetto \u00e8 pi\u00f9 "
              "esposto.",
        "en": "About to remove the write protection of chip {chip}.\n\nThis is "
              "not a program setting: it changes the chip's own state and "
              "persists after everything is unplugged. On a board that still "
              "boots, an unprotected BIOS is more exposed.",
    },
    "word_unlock": {"it": "SBLOCCA", "en": "UNLOCK"},
    "prot_unlocked": {
        "it": "Protezione tolta.",
        "en": "Protection removed.",
    },
    "prot_not_removed": {
        "it": "Non sono riuscito a togliere la protezione (codice {code}). "
              "Spesso il blocco \u00e8 tenuto dal piedino WP o da /HOLD: va "
              "portato alto, o il chip resta protetto comunque.",
        "en": "Could not remove the protection (code {code}). The lock is "
              "often held by the WP or /HOLD pin: it has to be pulled high, or "
              "the chip stays protected anyway.",
    },
    "req_protection": {"it": "chip protetto in scrittura", "en": "chip is write protected"},
    # --- the chip as we query it (JEDEC/SFDP) -------------------------------
    "jedec_answers": {
        "it": "Il chip risponde: {description}. flashrom non lo conosce: "
              "scegliere in «Modello» un chip della stessa misura e famiglia.",
        "en": "The chip answers: {description}. flashrom does not know it: "
              "pick a chip of the same size and family under \u201cModel\u201d.",
    },
    "jedec_silent": {
        "it": "Il chip non risponde nemmeno all'identificativo JEDEC: "
              "il problema \u00e8 nei collegamenti o nell'alimentazione, "
              "non nel modello.",
        "en": "The chip does not even answer its JEDEC id: the problem is the "
              "wiring or the power, not the model.",
    },
    "jedec_error": {
        "it": "Non sono riuscito a interrogare il chip: {reason}",
        "en": "Could not query the chip: {reason}",
    },
    # --- chip voltage and level shifter -------------------------------------
    "volt_low": {
        "it": "Chip a 1,8 V ({family}). L'RP2040 parla a 3,3 V: "
              "collegato diretto lo rovina, e il MISO non si legge comunque.",
        "en": "1.8 V chip ({family}). The RP2040 speaks at 3.3 V: wired "
              "directly it destroys the chip, and MISO cannot be read anyway.",
    },
    "volt_high": {
        "it": "Chip a 3,3 V ({family}): si collega diretto.",
        "en": "3.3 V chip ({family}): wire it directly.",
    },
    "volt_unknown": {
        "it": "Tensione del chip non deducibile dal modello: guardare la "
              "scheda tecnica prima di collegarlo.",
        "en": "The chip voltage cannot be told from the model: check the "
              "datasheet before wiring it.",
    },
    "volt_schematic": {"it": "Schema 1,8 V", "en": "1.8 V wiring"},
    "tick_shifter": {
        "it": "Adattatore di livello a 1,8 V collegato",
        "en": "1.8 V level shifter in place",
    },
    "req_shifter": {
        "it": "conferma dell'adattatore a 1,8 V",
        "en": "confirmation of the 1.8 V level shifter",
    },

    # --- level-shifter schematic --------------------------------------------
    "ls_col_ref": {"it": "Sigla", "en": "Ref"},
    "ls_col_value": {"it": "Cosa", "en": "What"},
    "ls_col_parts": {"it": "Modelli", "en": "Part numbers"},
    "ls_footer": {
        "it": "SPIranha \u00b7 github.com/MTSistemi/SPIranha \u00b7 "
              "adattatore di livello per flash SPI a 1,8 V",
        "en": "SPIranha \u00b7 github.com/MTSistemi/SPIranha \u00b7 "
              "level shifter for 1.8 V SPI flash",
    },
    "ls_pdf": {"it": "Stampa PDF", "en": "Print to PDF"},
    "ls_pdf_where": {"it": "Salva lo schema in PDF", "en": "Save the schematic as PDF"},
    "ls_pdf_done": {"it": "PDF salvato: {file}", "en": "PDF saved: {file}"},
    "ls_pdf_error": {
        "it": "Non sono riuscito a fare il PDF: {reason}",
        "en": "Could not make the PDF: {reason}",
    },
    "ls_pdf_no_chrome": {
        "it": "Serve Chrome o Edge per la stampa in PDF: non li trovo.",
        "en": "Chrome or Edge is needed to print to PDF: neither was found.",
    },
    "ls_title": {
        "it": "Adattatore di livello per chip a 1,8 V",
        "en": "Level shifter for 1.8 V chips",
    },
    "ls_sub": {
        "it": "Un canale su quattro identici \u00b7 BSS138 \u00b7 regolatore "
              "3,3 \u2192 1,8 V \u00b7 massa in comune",
        "en": "One of four identical channels \u00b7 BSS138 \u00b7 3.3 "
              "\u2192 1.8 V regulator \u00b7 shared ground",
    },
    "ls_rail_high": {"it": "3,3 V \u00b7 Pico", "en": "3.3 V \u00b7 Pico"},
    "ls_rail_low": {"it": "1,8 V \u00b7 chip", "en": "1.8 V \u00b7 chip"},
    "ls_side_pico": {"it": "dal Pico", "en": "from Pico"},
    "ls_side_chip": {"it": "al chip", "en": "to chip"},
    "ls_ldo": {"it": "regolatore 1,8 V", "en": "1.8 V regulator"},
    "ls_ldo_note": {
        "it": "I due condensatori non sono un vezzo: senza, il regolatore "
              "oscilla e l'alimentazione del chip balla.",
        "en": "The two capacitors are not decoration: without them the "
              "regulator oscillates and the chip supply wanders.",
    },
    "ls_orientation": {
        "it": "Il MOSFET non \u00e8 simmetrico: il source (S) guarda il lato "
              "a 1,8 V. Montato al contrario conduce sempre, i due lati "
              "restano attaccati e il chip prende 3,3 V lo stesso.",
        "en": "The MOSFET is not symmetric: the source (S) faces the 1.8 V "
              "side. Fitted the other way round it conducts always, the two "
              "sides stay connected and the chip gets 3.3 V anyway.",
    },
    "ls_table": {"it": "Un canale per segnale",
                   "en": "One channel per signal"},
    "ls_bom": {"it": "Distinta", "en": "Bill of materials"},
    "ls_col_signal": {"it": "Segnale", "en": "Signal"},
    "ls_notes_title": {"it": "Da sapere", "en": "Worth knowing"},
    "ls_note1": {
        "it": "Il chip va alimentato a 1,8 V dal regolatore, NON dal 3V3 del "
              "Pico. Tradurre i segnali e lasciare l'alimentazione a 3,3 "
              "\u00e8 il modo pi\u00f9 rapido di rovinarlo.",
        "en": "The chip takes 1.8 V from the regulator, NOT the Pico's "
              "3V3. Translating the signals and leaving the supply at 3.3 V "
              "is the quickest way to destroy it.",
    },
    "ls_note3": {
        "it": "La salita del segnale la fa la resistenza, non il transistor. "
              "Con 1 k\u03a9 si tengono 4 MHz; con i 10 k\u03a9 dello schema "
              "classico (che vengono dall'I\u00b2C a 100 kHz) si va sui "
              "700 ns di salita, e gi\u00e0 a 1 MHz le due letture non "
              "coincidono.",
        "en": "The rising edge is made by the resistor, not the transistor. "
              "1 k\u03a9 holds 4 MHz; the textbook 10 k\u03a9 (which come "
              "from 100 kHz I\u00b2C) give a 700 ns rise, and the two reads "
              "already disagree at 1 MHz.",
    },
    "ls_note5": {
        "it": "Sul MOSFET conta la soglia, non la corrente: il gate sta a "
              "1,8 V, serve Vgs(th) sotto 1,5 V. Il BSS138 ce l'ha, il "
              "2N7002 no (fino a 2,5 V) e non accende \u2014 stesso "
              "contenitore, stesso prezzo, non funziona.",
        "en": "On the MOSFET what matters is the threshold, not the current: "
              "the gate sits at 1.8 V, so Vgs(th) must be under 1.5 V. The "
              "BSS138 has it, the 2N7002 does not (up to 2.5 V) and never "
              "turns on \u2014 same package, same price, does not work.",
    },
    "ls_ready_made": {
        "it": "Già pronti: SparkFun BOB-12009 o Adafruit 757 "
              "(quattro canali a BSS138), più il regolatore 1,8 V a parte.",
        "en": "Off the shelf: SparkFun BOB-12009 or Adafruit 757 (four BSS138 "
              "channels), plus the 1.8 V regulator separately.",
    },
    "ls_note6": {
        "it": "Per tenere i 12 MHz serve un traduttore a direzione fissa, "
              "TI SN74LVC8T245PWR. Il TXS0108E no: è fatto per bus a "
              "collettore aperto e sull'SPI non va.",
        "en": "To keep 12 MHz you need a fixed-direction translator, TI "
              "SN74LVC8T245PWR. Not the TXS0108E: it is made for open-drain "
              "buses and does not work on SPI.",
    },
    # --- model search -------------------------------------------------------
    "search": {"it": "Cerca\u2026", "en": "Search\u2026"},
    "search_title": {
        "it": "Modelli di chip che flashrom conosce",
        "en": "Chip models flashrom knows",
    },
    "search_field": {"it": "Filtro", "en": "Filter"},
    "search_count": {"it": "{how_many} di {total}", "en": "{how_many} of {total}"},
    "search_col_vendor": {"it": "Produttore", "en": "Vendor"},
    "search_col_model": {"it": "Modello", "en": "Model"},
    "search_col_size": {"it": "Dimensione", "en": "Size"},
    "search_col_volt": {"it": "Volt", "en": "Volts"},
    "search_col_tested": {"it": "Provato", "en": "Tested"},
    "search_note": {
        "it": "Solo chip SPI: gli altri bus, via serprog, non si raggiungono. "
              "«Provato» \u00e8 quello che flashrom dichiara: P riconosce, "
              "R legge, E cancella, W scrive. In arancione i chip a 1,8 V.",
        "en": "SPI chips only: the other buses cannot be reached over serprog. "
              "\u201cTested\u201d is what flashrom declares: P probes, R reads, "
              "E erases, W writes. 1.8 V chips are in amber.",
    },
    "search_pick": {"it": "Scegli", "en": "Pick"},
    "search_cancel": {"it": "Annulla", "en": "Cancel"},
    "search_empty": {
        "it": "flashrom non ha restituito nessun elenco di chip.",
        "en": "flashrom returned no chip list.",
    },
    "search_picked": {
        "it": "Modello scelto: {vendor} {chip}, {size_text}.",
        "en": "Model picked: {vendor} {chip}, {size_text}.",
    },
    # --- 3. reading ------------------------------------------------------
    "sec_read": {"it": "3 · Lettura e backup", "en": "3 · Read and backup"},
    "folder": {"it": "Cartella", "en": "Folder"},
    "browse": {"it": "…", "en": "…"},
    "read": {"it": "Leggi e verifica", "en": "Read and verify"},
    "read_note": {
        "it": "Due letture consecutive, impronte a confronto.",
        "en": "Two consecutive reads, fingerprints compared.",
    },
    "read_1": {"it": "Prima lettura…", "en": "First read…"},
    "read_2": {"it": "Seconda lettura…", "en": "Second read…"},
    "read_ok": {
        "it": "Letture coincidenti · md5 {md5}",
        "en": "Reads match · md5 {md5}",
    },
    "read_differs": {
        "it": "Letture diverse ({a} ≠ {b}). Collegamento non affidabile: "
              "verificare i cavi e ridurre la velocità. Non scrivere.",
        "en": "Reads differ ({a} ≠ {b}). Unreliable connection: check the wires "
              "and lower the speed. Do not write.",
    },
    "read_saved": {"it": "Salvato in {path}", "en": "Saved to {path}"},
    "read_failed": {
        "it": "Lettura fallita (codice {code}). Dettaglio nel registro.",
        "en": "Read failed (code {code}). Details in the log.",
    },
    "known_as": {"it": "Riconosciuto: {what}", "en": "Recognised: {what}"},
    "md5_stock": {
        "it": "BIOS originale P3.00 di questa scheda",
        "en": "original P3.00 BIOS of this board",
    },
    "md5_expected": {
        "it": "risultato atteso dopo la scrittura della regione UEFI",
        "en": "expected result after writing the UEFI region",
    },
    "md5_unknown": {
        "it": "impronta non nota",
        "en": "unknown fingerprint",
    },

    # --- regions derived from the image -------------------------------------
    "reg_derive": {"it": "Ricava", "en": "Derive"},
    "reg_found": {
        "it": "{count} regioni ({source}). Layout scritto: {file}",
        "en": "{count} regions ({source}). Layout written: {file}",
    },
    "reg_none": {
        "it": "L'immagine non dichiara regioni: niente descrittore Intel, "
              "niente FMAP, niente struttura AMD. Il layout va scritto a mano.",
        "en": "The image declares no regions: no Intel descriptor, no FMAP, no "
              "AMD structure. The layout has to be written by hand.",
    },
    "reg_no_image": {
        "it": "Serve un'immagine da cui ricavarle: leggere il chip, "
              "oppure indicare il file atteso.",
        "en": "An image is needed to derive them from: read the chip, or point "
              "at the expected file.",
    },
    "reg_from_ifd": {"it": "descrittore Intel", "en": "Intel descriptor"},
    "reg_from_fmap": {"it": "FMAP", "en": "FMAP"},
    "reg_from_amd": {"it": "struttura AMD", "en": "AMD structure"},
    "reg_not_written": {
        "it": "Non riesco a scrivere il layout: {reason}",
        "en": "Cannot write the layout: {reason}",
    },
    # --- automatic comparison with the previous backup ----------------------
    "cmp_first": {
        "it": "Prima lettura in questa cartella: non c'\u00e8 niente con "
              "cui confrontarla.",
        "en": "First read in this folder: there is nothing to compare it with.",
    },
    "cmp_same": {
        "it": "Identica al backup precedente ({file}). Il chip non \u00e8 "
              "cambiato.",
        "en": "Identical to the previous backup ({file}). The chip has not "
              "changed.",
    },
    "cmp_differs": {
        "it": "Diversa dal backup precedente ({file}): "
              "0x{start:06X}-0x{end:06X}, settori cambiati: {how_many}.",
        "en": "Different from the previous backup ({file}): "
              "0x{start:06X}-0x{end:06X}, sectors changed: {how_many}.",
    },
    "cmp_other_size": {
        "it": "Il backup precedente ({file}) \u00e8 di un'altra misura: "
              "non si confrontano.",
        "en": "The previous backup ({file}) has a different size: they cannot "
              "be compared.",
    },
    # --- 4. writing ------------------------------------------------------
    "sec_write": {"it": "4 · Scrittura", "en": "4 · Writing"},
    "mode": {"it": "Ambito", "en": "Scope"},
    "mode_region": {"it": "Una regione", "en": "One region"},
    "mode_whole": {"it": "Chip intero", "en": "Whole chip"},
    "image": {"it": "Immagine", "en": "Image"},
    "layout_file": {"it": "Layout", "en": "Layout"},
    "region": {"it": "Regione", "en": "Region"},
    "expected": {"it": "Atteso", "en": "Expected"},
    "expected_note": {
        "it": "facoltativo · rilettura e confronto a fine scrittura",
        "en": "optional · re-read and compare after writing",
    },
    "tick_mains": {
        "it": "Scheda staccata dalla corrente",
        "en": "Board unplugged from mains",
    },
    "write": {"it": "Scrivi…", "en": "Write…"},
    "write_blocked": {
        "it": "Manca: {what}",
        "en": "Missing: {what}",
    },
    "req_flashrom": {"it": "flashrom", "en": "flashrom"},
    "req_chip": {"it": "identificazione del chip", "en": "chip identification"},
    "req_read": {
        "it": "lettura verificata",
        "en": "verified read",
    },
    "req_image": {"it": "immagine", "en": "image"},
    "req_layout": {"it": "layout e regione", "en": "layout and region"},
    "req_mains": {"it": "conferma alimentazione", "en": "mains confirmation"},
    "req_size": {
        "it": "immagine di {pending} byte, questa è di {found_one}",
        "en": "image must be {pending} bytes, this one is {found_one}",
    },

    # --- confirmation ----------------------------------------------------
    "confirm_title": {"it": "Confermare la scrittura", "en": "Confirm the write"},
    "confirm_text_region": {
        "it": "Regione «{region}» — {size} byte, da 0x{start:06X} a 0x{end:06X}.\n"
              "Chip {chip}.\nSorgente: {image}\n\n"
              "Il chip viene cancellato a settori e riscritto. In caso di errore "
              "la scheda non si avvia: si riparte da qui con l'immagine di recupero.",
        "en": "Region “{region}” — {size} bytes, 0x{start:06X} to 0x{end:06X}.\n"
              "Chip {chip}.\nSource: {image}\n\n"
              "The chip is erased by sectors and rewritten. On error the board will "
              "not boot: you start again from here with the recovery image.",
    },
    "confirm_text_whole": {
        "it": "Chip intero — {size} byte.\nChip {chip}.\nSorgente: {image}\n\n"
              "Vengono sovrascritte anche le impostazioni del BIOS e la "
              "configurazione della memoria di questo esemplare.",
        "en": "Whole chip — {size} bytes.\nChip {chip}.\nSource: {image}\n\n"
              "The BIOS settings and this board's memory configuration are "
              "overwritten too.",
    },
    "confirm_type": {
        "it": "Digitare {word} per procedere",
        "en": "Type {word} to proceed",
    },
    "word_confirm": {"it": "SCRIVI", "en": "WRITE"},
    "cancel": {"it": "Annulla", "en": "Cancel"},
    "proceed": {"it": "Procedi", "en": "Proceed"},

    # --- write outcomes ---------------------------------------------------
    "write_start": {"it": "Scrittura in corso…", "en": "Writing…"},
    "write_ok": {
        "it": "Scritto e verificato da flashrom.",
        "en": "Written and verified by flashrom.",
    },
    "write_failed": {
        "it": "Scrittura fallita (codice {code}). Non scollegare e non "
              "ricollegare l'alimentazione: leggere il registro.",
        "en": "Write failed (code {code}). Do not disconnect and do not "
              "reconnect mains: read the log.",
    },
    "reread": {"it": "Rilettura di controllo…", "en": "Verification re-read…"},
    "reread_same": {
        "it": "La rilettura coincide con il risultato atteso.",
        "en": "The re-read matches the expected result.",
    },
    "reread_differs": {
        "it": "La rilettura non coincide ({a} ≠ {b}). Non ricollegare "
              "l'alimentazione.",
        "en": "The re-read does not match ({a} ≠ {b}). Do not reconnect mains.",
    },

    # --- log --------------------------------------------------------------
    "sec_log": {"it": "Registro", "en": "Log"},
    "abort": {"it": "Interrompi", "en": "Stop"},
    "clear": {"it": "Pulisci", "en": "Clear"},
    "save_log": {"it": "Salva", "en": "Save"},
    "abort_denied": {
        "it": "Una scrittura non si interrompe.",
        "en": "A write is not interrupted.",
    },
    "aborted": {"it": "Interrotto.", "en": "Stopped."},
    "running": {
        "it": "Operazione già in corso.",
        "en": "An operation is already running.",
    },
    "busy": {"it": "in corso…", "en": "running…"},
    "ready": {"it": "pronto", "en": "ready"},
    "close_while_busy": {
        "it": "Operazione in corso. Chiudere adesso può lasciare il chip a metà. "
              "Chiudere comunque?",
        "en": "An operation is running. Closing now may leave the chip half "
              "written. Close anyway?",
    },

    # --- programmer firmware -----------------------------------------------
    "firmware": {"it": "Firmware", "en": "Firmware"},
    "fw_none": {
        "it": "Nessuna scheda in BOOTSEL. Per programmarne una: staccarla, "
              "tenere premuto BOOTSEL, riattaccarla.",
        "en": "No board in BOOTSEL. To program one: unplug it, hold BOOTSEL, "
              "plug it back in.",
    },
    "fw_found": {
        "it": "{model} su {drive} — pronta per il firmware",
        "en": "{model} on {drive} — ready for firmware",
    },
    "board_name": {"it": "Nome", "en": "Name"},
    "board_name_note": {
        "it": "un nome per riconoscerla fra le altre",
        "en": "a name to tell it from the others",
    },
    "fw_serial": {"it": "seriale {serial}", "en": "serial {serial}"},
    "fw_found_named": {
        "it": "{name} \u00b7 {model} su {drive} \u00b7 {serial}",
        "en": "{name} \u00b7 {model} on {drive} \u00b7 {serial}",
    },
    "fw_found_anon": {
        "it": "{model} su {drive} \u00b7 {serial} \u00b7 senza nome",
        "en": "{model} on {drive} \u00b7 {serial} \u00b7 unnamed",
    },
    "fw_named": {
        "it": "Scheda registrata come \u00ab{name}\u00bb.",
        "en": "Board registered as \u201c{name}\u201d.",
    },
    "fw_forgotten": {
        "it": "Nome tolto: la scheda torna anonima.",
        "en": "Name removed: the board is unnamed again.",
    },
    "word_erase": {"it": "CANCELLA", "en": "ERASE"},
    "fw_erase_one": {
        "it": "Primo consenso su due.\n\nSto per cancellare tutta la flash di "
              "{who}: {size}.\n\nLa scheda smette di essere un programmatore e "
              "torna come appena comprata. Il firmware si potr\u00e0 rimettere da "
              "qui, ma finch\u00e9 non lo fai quella scheda non serve a niente.",
        "en": "First of two confirmations.\n\nAbout to erase the whole flash of "
              "{who}: {size}.\n\nThe board stops being a programmer and goes "
              "back to as-bought. The firmware can be put back from here, but "
              "until you do, that board is of no use.",
    },
    "fw_erase_two": {
        "it": "Secondo consenso.\n\nControlla di avere in mano la scheda "
              "giusta: quella collegata su {drive} ha il seriale\n\n"
              "    {serial}\n\nPer procedere ribatti le ultime quattro cifre.",
        "en": "Second confirmation.\n\nMake sure you are holding the right "
              "board: the one on {drive} has serial\n\n    {serial}\n\n"
              "To proceed, retype its last four characters.",
    },
    "fw_erase_two_noserial": {
        "it": "Secondo consenso.\n\nDi questa scheda non si legge il seriale. "
              "Verifica di persona che quella collegata su {drive} sia quella "
              "che vuoi cancellare.",
        "en": "Second confirmation.\n\nThis board\u2019s serial cannot be read. "
              "Check by hand that the one on {drive} is the one you mean to "
              "erase.",
    },
    "fw_bootsel": {"it": "Riporta in BOOTSEL", "en": "Send to BOOTSEL"},
    "fw_bootsel_trying": {
        "it": "Chiedo alla scheda su {port} di riavviarsi nel bootloader\u2026",
        "en": "Asking the board on {port} to reboot into the bootloader\u2026",
    },
    "fw_bootsel_ok": {
        "it": "Rientrata in BOOTSEL su {drive}, senza toccare il pulsante.",
        "en": "Back in BOOTSEL on {drive}, without touching the button.",
    },
    "fw_bootsel_no": {
        "it": "La scheda non \u00e8 rientrata in BOOTSEL. Con il firmware "
              "precedente al 1200 baud non risponde: staccarla, tenere premuto "
              "BOOTSEL, riattaccarla.",
        "en": "The board did not return to BOOTSEL. Firmware older than the "
              "1200-baud support ignores this: unplug it, hold BOOTSEL, plug it "
              "back in.",
    },
    "fw_install": {"it": "Rendila programmatore", "en": "Make it a programmer"},
    "fw_erase": {"it": "Riporta a nuovo", "en": "Reset to factory"},
    "fw_absent": {
        "it": "firmware/pico_serprog.uf2 non c'e': vedi firmware/README.md",
        "en": "firmware/pico_serprog.uf2 is missing: see firmware/README.md",
    },
    "fw_installing": {"it": "Copio il firmware\u2026", "en": "Copying the firmware\u2026"},
    "fw_waiting": {
        "it": "Firmware copiato. La scheda si riavvia: aspetto la porta seriale\u2026",
        "en": "Firmware copied. The board reboots: waiting for the serial port\u2026",
    },
    "fw_ready": {
        "it": "Programmatore pronto su {port}.",
        "en": "Programmer ready on {port}.",
    },
    "fw_no_return": {
        "it": "Firmware copiato, ma la porta seriale non \u00e8 comparsa. Staccare e "
              "riattaccare la scheda.",
        "en": "Firmware copied, but no serial port appeared. Unplug the board and "
              "plug it back in.",
    },
    "fw_error": {"it": "{reason}", "en": "{reason}"},
    "fw_erase_title": {
        "it": "Riportare la scheda a nuovo",
        "en": "Reset the board to factory",
    },
    "fw_erase_text": {
        "it": "Sto per cancellare tutta la flash di {model} su {drive}: "
              "{size}.\n\nLa scheda torner\u00e0 come appena comprata e ricomparir\u00e0 "
              "come disco RPI-RP2. Il firmware si potr\u00e0 rimettere da qui.",
        "en": "About to erase the whole flash of {model} on {drive}: {size}.\n\n"
              "The board goes back to as-bought and will show up again as the "
              "RPI-RP2 drive. The firmware can be put back from here.",
    },
    "fw_erasing": {"it": "Cancello la flash\u2026", "en": "Erasing the flash\u2026"},
    "fw_erased": {
        "it": "Scheda riportata a nuovo: ricomparir\u00e0 come disco RPI-RP2.",
        "en": "Board reset: it will show up again as the RPI-RP2 drive.",
    },

    # --- chip map ----------------------------------------------------------
    "sec_map": {"it": "Mappa del chip", "en": "Chip map"},
    "leg_pending": {"it": "da fare", "en": "pending"},
    "leg_read": {"it": "letto", "en": "read"},
    "leg_erased": {"it": "cancellato", "en": "erased"},
    "leg_written": {"it": "scritto", "en": "written"},
    "leg_verified": {"it": "verificato", "en": "verified"},
    "leg_mismatch": {"it": "diverso", "en": "mismatch"},
    "map_idle": {
        "it": "{total_size} · {blocks} blocchi da {grain}",
        "en": "{total_size} · {blocks} blocks of {grain}",
    },
    "map_position": {"it": "0x{position:06X}", "en": "0x{position:06X}"},

    # --- dry run ------------------------------------------------------------
    "dry_run": {"it": "Prova a secco", "en": "Dry run"},
    "dry_ok": {
        "it": "Cambieranno {size} in {spans} intervalli, tutti dentro la "
              "regione. md5 atteso {md5}",
        "en": "{size} will change in {spans} ranges, all inside the "
              "region. Expected md5 {md5}",
    },
    "dry_ok_one": {
        "it": "Cambieranno {size} in un solo intervallo, dentro la regione. "
              "md5 atteso {md5}",
        "en": "{size} will change in a single range, inside the region. "
              "Expected md5 {md5}",
    },
    "verify_differs_one": {
        "it": "Un intervallo non coincide ({size}). Non ricollegare "
              "l'alimentazione.",
        "en": "One range does not match ({size}). Do not reconnect mains.",
    },
    "dry_nothing": {
        "it": "Nessuna differenza: il chip contiene già questa immagine.",
        "en": "No difference: the chip already holds this image.",
    },
    "dry_outside": {
        "it": "{spans} intervalli differiscono anche fuori dalla regione: "
              "non verranno scritti. Cambieranno {size} byte. md5 atteso {md5}",
        "en": "{spans} ranges also differ outside the region: they will not "
              "be written. {size} bytes will change. Expected md5 {md5}",
    },
    "dry_expected_differs": {
        "it": "Il risultato calcolato NON coincide con il file «Atteso» "
              "({computed} ≠ {expected}). Controllare immagine, layout e regione.",
        "en": "The computed result does NOT match the “Expected” file "
              "({computed} ≠ {expected}). Check image, layout and region.",
    },
    "dry_expected_same": {
        "it": "Il risultato calcolato coincide con il file «Atteso».",
        "en": "The computed result matches the “Expected” file.",
    },
    "req_dry_run": {"it": "prova a secco", "en": "dry run"},

    # --- qualifying the link -----------------------------------------------
    "qualify": {"it": "Qualifica", "en": "Qualify"},
    "qualify_note": {
        "it": "Cerca la velocità più alta con letture ripetibili.",
        "en": "Finds the highest speed with repeatable reads.",
    },
    "qualify_trying": {"it": "Provo a {speed}…", "en": "Trying {speed}…"},
    "qualify_ok": {
        "it": "Velocità impostata: {speed}. Due letture identiche su {size}.",
        "en": "Speed set to {speed}. Two identical reads over {size}.",
    },
    "qualify_none": {
        "it": "Nessuna velocità dà letture ripetibili. Verificare i cavi e "
              "l'alimentazione del chip.",
        "en": "No speed gives repeatable reads. Check the wires and the chip "
              "supply.",
    },

    # --- progress -----------------------------------------------------------
    "phase_READ": {"it": "lettura", "en": "read"},
    "phase_ERASE": {"it": "cancellazione", "en": "erase"},
    "phase_WRITE": {"it": "scrittura", "en": "write"},
    "phase_VERIFY": {"it": "verifica", "en": "verify"},
    "progress": {
        "it": "{phase} {percent}%",
        "en": "{phase} {percent}%",
    },
    "progress_left": {
        "it": "{phase} {percent}% · {left} alla fine",
        "en": "{phase} {percent}% · {left} left",
    },

    # --- final check --------------------------------------------------------
    "verify_final": {"it": "Verifica finale…", "en": "Final verification…"},
    "verify_ok": {
        "it": "Il chip contiene esattamente la nuova ROM: {size} confrontati, "
              "nessuna differenza.",
        "en": "The chip holds exactly the new ROM: {size} compared, no difference.",
    },
    "verify_differs": {
        "it": "{spans} intervalli non coincidono ({size}). Non ricollegare "
              "l'alimentazione.",
        "en": "{spans} ranges do not match ({size}). Do not reconnect mains.",
    },
    "coherence_ok": {"it": "Regione coerente: {what}.", "en": "Region coherent: {what}."},
    "coherence_none": {
        "it": "Regione scritta, ma senza strutture note al suo interno.",
        "en": "Region written, but with no known structures inside.",
    },
    "coherence_empty": {
        "it": "La regione è tutta 0xFF: cancellata e non riscritta.",
        "en": "The region is all 0xFF: erased and not rewritten.",
    },
    "coherence_zero": {
        "it": "La regione è tutta 0x00.",
        "en": "The region is all 0x00.",
    },

    # --- comparison between images ------------------------------------------
    "cmp_open": {"it": "Confronta", "en": "Compare"},
    "cmp_title": {"it": "Confronto fra immagini", "en": "Image comparison"},
    "cmp_sub": {
        "it": "Intervalli diversi, allineati ai settori da 4 KB, e layout pronto "
              "per flashrom",
        "en": "Differing ranges, aligned to 4 KB sectors, and a layout ready for "
              "flashrom",
    },
    "cmp_sec_files": {"it": "Immagini da confrontare", "en": "Images to compare"},
    "cmp_sec_outcome": {"it": "Differenze", "en": "Differences"},
    "cmp_a": {"it": "Immagine A", "en": "Image A"},
    "cmp_b": {"it": "Immagine B", "en": "Image B"},
    "cmp_run": {"it": "Confronta", "en": "Compare"},
    "cmp_identical": {
        "it": "Le due immagini sono identiche.",
        "en": "The two images are identical.",
    },
    "cmp_result": {
        "it": "{spans} intervalli diversi · {size}",
        "en": "{spans} differing ranges · {size}",
    },
    "cmp_result_one": {
        "it": "1 intervallo diverso · {size}",
        "en": "1 differing range · {size}",
    },
    "cmp_sizes": {
        "it": "Dimensioni diverse: {a} e {b}. Non confrontabili.",
        "en": "Different sizes: {a} and {b}. Not comparable.",
    },
    "cmp_col_span": {"it": "Intervallo (settori)", "en": "Range (sectors)"},
    "cmp_col_exact": {"it": "Confini veri", "en": "True bounds"},
    "cmp_col_size": {"it": "Dimensione", "en": "Size"},
    "cmp_col_what": {"it": "Contenuto", "en": "Contents"},
    "cmp_save_layout": {"it": "Salva layout…", "en": "Save layout…"},
    "cmp_name": {"it": "Nome regione", "en": "Region name"},
    "cmp_saved": {"it": "Layout salvato in {path}",
                     "en": "Layout saved to {path}"},
    "cmp_pick": {"it": "Scegliere due immagini.", "en": "Pick two images."},

    # --- wiring diagram ----------------------------------------------------
    "sch_open": {"it": "Schema", "en": "Diagram"},
    "sch_title": {"it": "Schema dei collegamenti", "en": "Wiring diagram"},
    "sch_sub": {
        "it": "Raspberry Pi Pico (RP2040) → BC-250, connettore J4004",
        "en": "Raspberry Pi Pico (RP2040) → BC-250, header J4004",
    },
    "sch_pico": {"it": "Raspberry Pi Pico", "en": "Raspberry Pi Pico"},
    "sch_pico_note": {
        "it": "Visto da sopra, USB in alto. Piedino 1 in alto a sinistra.",
        "en": "Seen from above, USB at the top. Pin 1 top left.",
    },
    "sch_conn": {"it": "BC-250 · J4004", "en": "BC-250 · J4004"},
    "sch_conn_note": {
        "it": "2×4, passo 2,54 mm. Triangolo bianco in serigrafia = piedino 1 (VCC).",
        "en": "2×4, 2.54 mm pitch. White silkscreen triangle = pin 1 (VCC).",
    },
    "sch_unk": {
        "it": "UNK: funzione ignota, a massa con 10 kΩ. Non collegare.",
        "en": "UNK: unknown function, tied to ground via 10 kΩ. Do not connect.",
    },
    "sch_nc": {"it": "n.d.", "en": "n/a"},
    "sch_table": {"it": "Collegamenti", "en": "Connections"},
    "sch_col_signal": {"it": "Segnale", "en": "Signal"},
    "sch_col_pico": {"it": "Pico", "en": "Pico"},
    "sch_col_conn": {"it": "J4004", "en": "J4004"},
    "sch_gnd_note": {
        "it": "GND dal piedino 3: sta accanto ai quattro segnali, così i cavi "
              "3-4-5-6-7 sono contigui. Va bene qualunque altro GND "
              "(8, 13, 18, 23, 28, 33, 38).",
        "en": "GND from pin 3: it sits next to the four signals, so wires "
              "3-4-5-6-7 are contiguous. Any other GND works too "
              "(8, 13, 18, 23, 28, 33, 38).",
    },
    "sch_warn_title": {"it": "Prima di collegare", "en": "Before connecting"},
    "sch_warn1": {
        "it": "BC-250 staccata dalla corrente. A spina estratta premere il tasto "
              "di accensione 2-3 volte per scaricare i condensatori.",
        "en": "BC-250 unplugged from mains. With the plug out, press the power "
              "button 2-3 times to drain the capacitors.",
    },
    "sch_warn2": {
        "it": "Il bersaglio è BIOS_A1, 16 MB. Non SIO1_R da 512 KB: è il SuperIO "
              "e ne dipende il controllo delle ventole. Se il programma riporta "
              "512 KB, il chip è quello sbagliato.",
        "en": "The target is BIOS_A1, 16 MB. Not SIO1_R at 512 KB: that is the "
              "SuperIO and fan control depends on it. If the program reports "
              "512 KB, it is the wrong chip.",
    },
    "sch_warn3": {
        "it": "Verificare con il tester la continuità del piedino GND con la massa "
              "della scheda prima di alimentare.",
        "en": "With a multimeter, verify continuity between the GND pin and board "
              "ground before powering up.",
    },
    "sch_warn4": {
        "it": "Alimentazione solo dal Pico (3V3, piedino 36).",
        "en": "Power from the Pico only (3V3, pin 36).",
    },
    # --- the standing reminder ---------------------------------------------
    "reminder": {
        "it": "Scheda staccata dalla corrente. Il chip è alimentato dal Pico "
              "(3V3, piedino 36).",
        "en": "Board unplugged from mains. The chip is powered by the Pico "
              "(3V3, pin 36).",
    },
}


class Language(object):
    """Tiene la lingua corrente e restituisce le frasi."""

    def __init__(self, code="it"):
        self.code = code if code in LANGUAGES else "it"

    def __call__(self, key, **fields):
        entry = T.get(key)
        if entry is None:
            return "?" + key + "?"
        text = entry.get(self.code) or entry["it"]
        return text.format(**fields) if fields else text
