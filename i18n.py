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
    # --- finestra ------------------------------------------------------
    "titolo": {"it": "SPIranha", "en": "SPIranha"},
    # ⚠️ The subtitle says WHAT is being worked on: the profile name goes
    # inside it, or the header would always talk about a BC-250.
    "sottotitolo": {
        "it": "Raspberry Pi Pico · pico-serprog · {board}",
        "en": "Raspberry Pi Pico · pico-serprog · {board}",
    },
    "lingua": {"it": "Lingua", "en": "Language"},

    # --- flashrom mancante ---------------------------------------------
    "flashrom_assente": {
        "it": "flashrom.exe non trovato. Senza, il chip non è raggiungibile.",
        "en": "flashrom.exe not found. Without it the chip cannot be reached.",
    },
    "flashrom_individua": {"it": "Individua…", "en": "Locate…"},
    "flashrom_trovato": {"it": "flashrom {version} · {path}",
                         "en": "flashrom {version} · {path}"},
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
        "it": "{name} · interfaccia v{version} · bus {bus}",
        "en": "{name} · interface v{version} · bus {bus}",
    },
    "pico_non_apre": {"it": "{port} non si apre: {reason}",
                      "en": "{port} will not open: {reason}"},
    "pico_no_spi": {
        "it": "Il programmatore non dichiara SPI.",
        "en": "The programmer does not declare SPI.",
    },
    "seriale_assente": {
        "it": "pyserial assente: la porta va scritta a mano.",
        "en": "pyserial missing: type the port by hand.",
    },

    # --- versione del firmware ----------------------------------------------
    "fw_versione_ok": {
        "it": "Firmware {version}, \u00e8 l\u0027ultimo che abbiamo.",
        "en": "Firmware {version}, the latest one we carry.",
    },
    "fw_versione_vecchia": {
        "it": "Firmware {version} sulla scheda, qui c\u0027\u00e8 la {newer}.",
        "en": "Firmware {version} on the board, we carry {newer}.",
    },
    "fw_versione_muta": {
        "it": "Firmware anteriore alla 1.1: non dice quale sia. Qui c\u0027"
              "\u00e8 la {newer}.",
        "en": "Firmware older than 1.1: it does not say which. We carry "
              "{newer}.",
    },
    "fw_aggiorna": {"it": "Aggiorna", "en": "Update"},
    "fw_aggiorno": {
        "it": "Aggiornamento: rimando la scheda in BOOTSEL\u2026",
        "en": "Updating: sending the board back to BOOTSEL\u2026",
    },
    "fw_aggiorna_no_bootsel": {
        "it": "La scheda non torna in BOOTSEL da sola: il suo firmware "
              "\u00e8 anteriore alla 1.1, che \u00e8 la versione che ha "
              "aggiunto quel rientro. Serve il pulsante BOOTSEL, una volta "
              "sola: da qui in poi si aggiorna via cavo.",
        "en": "The board will not go back to BOOTSEL by itself: its firmware "
              "predates 1.1, which is the version that added that. The BOOTSEL "
              "button is needed once; after that it updates over the wire.",
    },
    "fw_aggiornato": {
        "it": "Aggiornata alla {version} su {port}.",
        "en": "Updated to {version} on {port}.",
    },
    "fw_aggiorna_dubbio": {
        "it": "Copia riuscita, ma la scheda dichiara ancora {version}.",
        "en": "Copy went through, but the board still reports {version}.",
    },

    # --- profili di scheda --------------------------------------------------
    "profilo": {"it": "Scheda", "en": "Board"},
    "prof_bc250_sio": {
        "it": "Sulla scheda ci sono due flash: quella da 16 MiB \u00e8 il BIOS, "
              "quella da 512 KiB \u00e8 il SuperIO. Il J4004 \u00e8 quello "
              "accanto al chip grande.",
        "en": "The board carries two flash chips: the 16 MiB one is the BIOS, "
              "the 512 KiB one is the SuperIO. J4004 is the header next to the "
              "big chip.",
    },
    "prof_gen_pinza": {
        "it": "Con la scheda accesa il chip non si legge comunque: il chipset "
              "tiene il bus.",
        "en": "On a powered board the chip cannot be read anyway: the chipset "
              "holds the bus.",
    },
    "prof_dim_diversa": {
        "it": "Il profilo prevede {expected} byte, il chip ne ha {hit}.",
        "en": "The profile expects {expected} bytes, the chip has {hit}.",
    },
    "prof_chip_diverso": {
        "it": "Il profilo prevede {expected}, qui c\u0027\u00e8 {hit}. "
              "Pu\u00f2 essere una revisione diversa della stessa scheda.",
        "en": "The profile expects {expected}, this is {hit}. It may be a "
              "different revision of the same board.",
    },
    "prof_regioni_mancanti": {
        "it": "Regioni attese e non trovate: {which}.",
        "en": "Regions expected and not found: {which}.",
    },
    "prof_come_previsto": {
        "it": "Chip come previsto dal profilo.",
        "en": "Chip is what the profile expects.",
    },

    # --- schema con la pinza sul chip ---------------------------------------
    "sch_titolo_pinza": {
        "it": "Collegamenti: Pico \u2192 chip SPI in SOIC-8",
        "en": "Wiring: Pico \u2192 SOIC-8 SPI chip",
    },
    "sch_sotto_pinza": {
        "it": "Raspberry Pi Pico (RP2040) \u2192 pinza sul chip",
        "en": "Raspberry Pi Pico (RP2040) \u2192 clip on the chip",
    },
    "sch_chip_scheda": {"it": "il chip", "en": "the chip"},
    "sch_chip": {"it": "Chip \u00b7 SOIC-8", "en": "Chip \u00b7 SOIC-8"},
    "sch_chip_nota": {
        "it": "Visto da sopra. La tacca \u00e8 dalla parte del piedino 1: "
              "1-4 scendendo a sinistra, 5-8 risalendo a destra.",
        "en": "Seen from above. The notch is on the pin 1 side: 1-4 going down "
              "the left, 5-8 going up the right.",
    },
    "sch_wp_nota": {
        "it": "/WP e /HOLD vanno alti. Tenuti bassi, il chip accetta i comandi "
              "e non scrive niente: sui moduli con zoccolo ci pensa il modulo, "
              "sul chip nudo vanno portati a VCC.",
        "en": "/WP and /HOLD must be high. Held low, the chip takes the "
              "commands and writes nothing: breakout modules do it for you, on "
              "a bare chip they go to VCC.",
    },
    "sch_col_chip": {"it": "Chip", "en": "Chip"},
    "sch_pz_nota": {
        "it": "I quattro segnali stanno su due lati opposti: i cavetti si "
              "incrociano, e va bene cos\u00ec. Conta il numero del piedino.",
        "en": "The four signals sit on opposite sides: the wires cross, and "
              "that is fine. What counts is the pin number.",
    },
    "sch_pz_av1": {
        "it": "Scheda staccata dalla corrente, sempre.",
        "en": "Board unplugged from mains, always.",
    },
    "sch_pz_av2": {
        "it": "La pinza va messa con la tacca dalla parte del piedino 1: al "
              "contrario si mandano 3,3 V sulla massa del chip.",
        "en": "The clip goes on with the notch on the pin 1 side: the other "
              "way round puts 3.3 V on the chip ground.",
    },
    "sch_pz_av3": {
        "it": "Chip a 1,8 V: il Pico non li regge. Serve un adattatore di "
              "livello, e alimentare il chip a 1,8 V.",
        "en": "1.8 V chips: the Pico cannot drive them. A level shifter is "
              "needed, and 1.8 V power for the chip.",
    },
    "sch_pz_av4": {
        "it": "Se la scheda alimenta gi\u00e0 il chip da sola, non collegare "
              "VCC: solo massa e i quattro segnali.",
        "en": "If the board already powers the chip, leave VCC unconnected: "
              "ground and the four signals only.",
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

    # --- protezione in scrittura --------------------------------------------
    "prot_libera": {
        "it": "Chip non protetto in scrittura.",
        "en": "Chip is not write protected.",
    },
    "prot_attiva": {
        "it": "Protetto: 0x{start:06X}-0x{end:06X} ({description}), modo {mode}.",
        "en": "Protected: 0x{start:06X}-0x{end:06X} ({description}), mode {mode}.",
    },
    "prot_scontro": {
        "it": "La protezione copre la regione da scrivere "
              "(0x{start:06X}-0x{end:06X}): la scrittura non passerebbe.",
        "en": "The protection covers the region to write "
              "(0x{start:06X}-0x{end:06X}): the write would not go through.",
    },
    "prot_ignota": {
        "it": "Il chip non risponde sullo stato della protezione.",
        "en": "The chip does not answer about its protection state.",
    },
    "prot_sblocca": {"it": "Sblocca", "en": "Unlock"},
    "prot_conferma": {
        "it": "Sto per togliere la protezione in scrittura del chip "
              "{chip}.\n\nNon e\u0027 un\u0027impostazione del programma: cambia lo "
              "stato del chip, e resta cos\u00ec anche staccando tutto. Su una "
              "scheda che si accende ancora, un BIOS non protetto \u00e8 pi\u00f9 "
              "esposto.",
        "en": "About to remove the write protection of chip {chip}.\n\nThis is "
              "not a program setting: it changes the chip\u0027s own state and "
              "persists after everything is unplugged. On a board that still "
              "boots, an unprotected BIOS is more exposed.",
    },
    "parola_sblocca": {"it": "SBLOCCA", "en": "UNLOCK"},
    "prot_sbloccato": {
        "it": "Protezione tolta.",
        "en": "Protection removed.",
    },
    "prot_non_tolta": {
        "it": "Non sono riuscito a togliere la protezione (codice {code}). "
              "Spesso il blocco \u00e8 tenuto dal piedino WP o da /HOLD: va "
              "portato alto, o il chip resta protetto comunque.",
        "en": "Could not remove the protection (code {code}). The lock is "
              "often held by the WP or /HOLD pin: it has to be pulled high, or "
              "the chip stays protected anyway.",
    },
    "req_protezione": {"it": "chip protetto in scrittura", "en": "chip is write protected"},
    # --- il chip interrogato da noi (JEDEC/SFDP) ----------------------------
    "jedec_risponde": {
        "it": "Il chip risponde: {description}. flashrom non lo conosce: "
              "scegliere in «Modello» un chip della stessa misura e famiglia.",
        "en": "The chip answers: {description}. flashrom does not know it: "
              "pick a chip of the same size and family under \u201cModel\u201d.",
    },
    "jedec_muto": {
        "it": "Il chip non risponde nemmeno all\u0027identificativo JEDEC: "
              "il problema \u00e8 nei collegamenti o nell\u0027alimentazione, "
              "non nel modello.",
        "en": "The chip does not even answer its JEDEC id: the problem is the "
              "wiring or the power, not the model.",
    },
    "jedec_errore": {
        "it": "Non sono riuscito a interrogare il chip: {reason}",
        "en": "Could not query the chip: {reason}",
    },
    # --- tensione del chip e adattatore di livello --------------------------
    "tens_bassa": {
        "it": "Chip a 1,8 V ({family}). L\u0027RP2040 parla a 3,3 V: "
              "collegato diretto lo rovina, e il MISO non si legge comunque.",
        "en": "1.8 V chip ({family}). The RP2040 speaks at 3.3 V: wired "
              "directly it destroys the chip, and MISO cannot be read anyway.",
    },
    "tens_alta": {
        "it": "Chip a 3,3 V ({family}): si collega diretto.",
        "en": "3.3 V chip ({family}): wire it directly.",
    },
    "tens_ignota": {
        "it": "Tensione del chip non deducibile dal modello: guardare la "
              "scheda tecnica prima di collegarlo.",
        "en": "The chip voltage cannot be told from the model: check the "
              "datasheet before wiring it.",
    },
    "tens_schema": {"it": "Schema 1,8 V", "en": "1.8 V wiring"},
    "spunta_adattatore": {
        "it": "Adattatore di livello a 1,8 V collegato",
        "en": "1.8 V level shifter in place",
    },
    "req_adattatore": {
        "it": "conferma dell\u0027adattatore a 1,8 V",
        "en": "confirmation of the 1.8 V level shifter",
    },

    # --- schema dell'adattatore ---------------------------------------------
    "ad_col_sigla": {"it": "Sigla", "en": "Ref"},
    "ad_col_valore": {"it": "Cosa", "en": "What"},
    "ad_col_modelli": {"it": "Modelli", "en": "Part numbers"},
    "ad_piede": {
        "it": "SPIranha \u00b7 github.com/MTSistemi/SPIranha \u00b7 "
              "adattatore di livello per flash SPI a 1,8 V",
        "en": "SPIranha \u00b7 github.com/MTSistemi/SPIranha \u00b7 "
              "level shifter for 1.8 V SPI flash",
    },
    "ad_pdf": {"it": "Stampa PDF", "en": "Print to PDF"},
    "ad_pdf_dove": {"it": "Salva lo schema in PDF", "en": "Save the schematic as PDF"},
    "ad_pdf_fatto": {"it": "PDF salvato: {file}", "en": "PDF saved: {file}"},
    "ad_pdf_errore": {
        "it": "Non sono riuscito a fare il PDF: {reason}",
        "en": "Could not make the PDF: {reason}",
    },
    "ad_pdf_niente_chrome": {
        "it": "Serve Chrome o Edge per la stampa in PDF: non li trovo.",
        "en": "Chrome or Edge is needed to print to PDF: neither was found.",
    },
    "ad_titolo": {
        "it": "Adattatore di livello per chip a 1,8 V",
        "en": "Level shifter for 1.8 V chips",
    },
    "ad_sotto": {
        "it": "Un canale su quattro identici \u00b7 BSS138 \u00b7 regolatore "
              "3,3 \u2192 1,8 V \u00b7 massa in comune",
        "en": "One of four identical channels \u00b7 BSS138 \u00b7 3.3 "
              "\u2192 1.8 V regulator \u00b7 shared ground",
    },
    "ad_rail_alto": {"it": "3,3 V \u00b7 Pico", "en": "3.3 V \u00b7 Pico"},
    "ad_rail_basso": {"it": "1,8 V \u00b7 chip", "en": "1.8 V \u00b7 chip"},
    "ad_lato_pico": {"it": "dal Pico", "en": "from Pico"},
    "ad_lato_chip": {"it": "al chip", "en": "to chip"},
    "ad_ldo": {"it": "regolatore 1,8 V", "en": "1.8 V regulator"},
    "ad_ldo_nota": {
        "it": "I due condensatori non sono un vezzo: senza, il regolatore "
              "oscilla e l\u0027alimentazione del chip balla.",
        "en": "The two capacitors are not decoration: without them the "
              "regulator oscillates and the chip supply wanders.",
    },
    "ad_verso": {
        "it": "Il MOSFET non \u00e8 simmetrico: il source (S) guarda il lato "
              "a 1,8 V. Montato al contrario conduce sempre, i due lati "
              "restano attaccati e il chip prende 3,3 V lo stesso.",
        "en": "The MOSFET is not symmetric: the source (S) faces the 1.8 V "
              "side. Fitted the other way round it conducts always, the two "
              "sides stay connected and the chip gets 3.3 V anyway.",
    },
    "ad_tabella": {"it": "Un canale per segnale",
                   "en": "One channel per signal"},
    "ad_distinta": {"it": "Distinta", "en": "Bill of materials"},
    "ad_col_segnale": {"it": "Segnale", "en": "Signal"},
    "ad_note_titolo": {"it": "Da sapere", "en": "Worth knowing"},
    "ad_nota1": {
        "it": "Il chip va alimentato a 1,8 V dal regolatore, NON dal 3V3 del "
              "Pico. Tradurre i segnali e lasciare l\u0027alimentazione a 3,3 "
              "\u00e8 il modo pi\u00f9 rapido di rovinarlo.",
        "en": "The chip takes 1.8 V from the regulator, NOT the Pico\u0027s "
              "3V3. Translating the signals and leaving the supply at 3.3 V "
              "is the quickest way to destroy it.",
    },
    "ad_nota3": {
        "it": "La salita del segnale la fa la resistenza, non il transistor. "
              "Con 1 k\u03a9 si tengono 4 MHz; con i 10 k\u03a9 dello schema "
              "classico (che vengono dall\u0027I\u00b2C a 100 kHz) si va sui "
              "700 ns di salita, e gi\u00e0 a 1 MHz le due letture non "
              "coincidono.",
        "en": "The rising edge is made by the resistor, not the transistor. "
              "1 k\u03a9 holds 4 MHz; the textbook 10 k\u03a9 (which come "
              "from 100 kHz I\u00b2C) give a 700 ns rise, and the two reads "
              "already disagree at 1 MHz.",
    },
    "ad_nota5": {
        "it": "Sul MOSFET conta la soglia, non la corrente: il gate sta a "
              "1,8 V, serve Vgs(th) sotto 1,5 V. Il BSS138 ce l\u0027ha, il "
              "2N7002 no (fino a 2,5 V) e non accende \u2014 stesso "
              "contenitore, stesso prezzo, non funziona.",
        "en": "On the MOSFET what matters is the threshold, not the current: "
              "the gate sits at 1.8 V, so Vgs(th) must be under 1.5 V. The "
              "BSS138 has it, the 2N7002 does not (up to 2.5 V) and never "
              "turns on \u2014 same package, same price, does not work.",
    },
    "ad_gia_pronti": {
        "it": "Già pronti: SparkFun BOB-12009 o Adafruit 757 "
              "(quattro canali a BSS138), più il regolatore 1,8 V a parte.",
        "en": "Off the shelf: SparkFun BOB-12009 or Adafruit 757 (four BSS138 "
              "channels), plus the 1.8 V regulator separately.",
    },
    "ad_nota6": {
        "it": "Per tenere i 12 MHz serve un traduttore a direzione fissa, "
              "TI SN74LVC8T245PWR. Il TXS0108E no: è fatto per bus a "
              "collettore aperto e sull'SPI non va.",
        "en": "To keep 12 MHz you need a fixed-direction translator, TI "
              "SN74LVC8T245PWR. Not the TXS0108E: it is made for open-drain "
              "buses and does not work on SPI.",
    },
    # --- ricerca del modello ------------------------------------------------
    "cerca": {"it": "Cerca\u2026", "en": "Search\u2026"},
    "cerca_titolo": {
        "it": "Modelli di chip che flashrom conosce",
        "en": "Chip models flashrom knows",
    },
    "cerca_campo": {"it": "Filtro", "en": "Filter"},
    "cerca_conteggio": {"it": "{how_many} di {total}", "en": "{how_many} of {total}"},
    "cerca_col_produttore": {"it": "Produttore", "en": "Vendor"},
    "cerca_col_modello": {"it": "Modello", "en": "Model"},
    "cerca_col_misura": {"it": "Dimensione", "en": "Size"},
    "cerca_col_volt": {"it": "Volt", "en": "Volts"},
    "cerca_col_prove": {"it": "Provato", "en": "Tested"},
    "cerca_nota": {
        "it": "Solo chip SPI: gli altri bus, via serprog, non si raggiungono. "
              "«Provato» \u00e8 quello che flashrom dichiara: P riconosce, "
              "R legge, E cancella, W scrive. In arancione i chip a 1,8 V.",
        "en": "SPI chips only: the other buses cannot be reached over serprog. "
              "\u201cTested\u201d is what flashrom declares: P probes, R reads, "
              "E erases, W writes. 1.8 V chips are in amber.",
    },
    "cerca_scegli": {"it": "Scegli", "en": "Pick"},
    "cerca_annulla": {"it": "Annulla", "en": "Cancel"},
    "cerca_vuoto": {
        "it": "flashrom non ha restituito nessun elenco di chip.",
        "en": "flashrom returned no chip list.",
    },
    "cerca_scelto": {
        "it": "Modello scelto: {vendor} {chip}, {size_text}.",
        "en": "Model picked: {vendor} {chip}, {size_text}.",
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
    "lettura_salvata": {"it": "Salvato in {path}", "en": "Saved to {path}"},
    "lettura_fallita": {
        "it": "Lettura fallita (codice {code}). Dettaglio nel registro.",
        "en": "Read failed (code {code}). Details in the log.",
    },
    "riconosciuto_come": {"it": "Riconosciuto: {what}", "en": "Recognised: {what}"},
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

    # --- regioni ricavate dall'immagine -------------------------------------
    "reg_ricava": {"it": "Ricava", "en": "Derive"},
    "reg_trovate": {
        "it": "{count} regioni ({source}). Layout scritto: {file}",
        "en": "{count} regions ({source}). Layout written: {file}",
    },
    "reg_niente": {
        "it": "L\u0027immagine non dichiara regioni: niente descrittore Intel, "
              "niente FMAP, niente struttura AMD. Il layout va scritto a mano.",
        "en": "The image declares no regions: no Intel descriptor, no FMAP, no "
              "AMD structure. The layout has to be written by hand.",
    },
    "reg_senza_immagine": {
        "it": "Serve un\u0027immagine da cui ricavarle: leggere il chip, "
              "oppure indicare il file atteso.",
        "en": "An image is needed to derive them from: read the chip, or point "
              "at the expected file.",
    },
    "reg_origine_ifd": {"it": "descrittore Intel", "en": "Intel descriptor"},
    "reg_origine_fmap": {"it": "FMAP", "en": "FMAP"},
    "reg_origine_amd": {"it": "struttura AMD", "en": "AMD structure"},
    "reg_non_scrivo": {
        "it": "Non riesco a scrivere il layout: {reason}",
        "en": "Cannot write the layout: {reason}",
    },
    # --- confronto automatico col backup precedente -------------------------
    "conf_primo": {
        "it": "Prima lettura in questa cartella: non c\u0027\u00e8 niente con "
              "cui confrontarla.",
        "en": "First read in this folder: there is nothing to compare it with.",
    },
    "conf_uguale": {
        "it": "Identica al backup precedente ({file}). Il chip non \u00e8 "
              "cambiato.",
        "en": "Identical to the previous backup ({file}). The chip has not "
              "changed.",
    },
    "conf_diverso": {
        "it": "Diversa dal backup precedente ({file}): "
              "0x{start:06X}-0x{end:06X}, settori cambiati: {how_many}.",
        "en": "Different from the previous backup ({file}): "
              "0x{start:06X}-0x{end:06X}, sectors changed: {how_many}.",
    },
    "conf_altra_misura": {
        "it": "Il backup precedente ({file}) \u00e8 di un\u0027altra misura: "
              "non si confrontano.",
        "en": "The previous backup ({file}) has a different size: they cannot "
              "be compared.",
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
        "it": "Scheda staccata dalla corrente",
        "en": "Board unplugged from mains",
    },
    "scrivi": {"it": "Scrivi…", "en": "Write…"},
    "scrivi_bloccato": {
        "it": "Manca: {what}",
        "en": "Missing: {what}",
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
        "it": "immagine di {pending} byte, questa è di {found_one}",
        "en": "image must be {pending} bytes, this one is {found_one}",
    },

    # --- conferma --------------------------------------------------------
    "conferma_titolo": {"it": "Confermare la scrittura", "en": "Confirm the write"},
    "conferma_testo_regione": {
        "it": "Regione «{region}» — {size} byte, da 0x{start:06X} a 0x{end:06X}.\n"
              "Chip {chip}.\nSorgente: {image}\n\n"
              "Il chip viene cancellato a settori e riscritto. In caso di errore "
              "la scheda non si avvia: si riparte da qui con l'immagine di recupero.",
        "en": "Region “{region}” — {size} bytes, 0x{start:06X} to 0x{end:06X}.\n"
              "Chip {chip}.\nSource: {image}\n\n"
              "The chip is erased by sectors and rewritten. On error the board will "
              "not boot: you start again from here with the recovery image.",
    },
    "conferma_testo_intero": {
        "it": "Chip intero — {size} byte.\nChip {chip}.\nSorgente: {image}\n\n"
              "Vengono sovrascritte anche le impostazioni del BIOS e la "
              "configurazione della memoria di questo esemplare.",
        "en": "Whole chip — {size} bytes.\nChip {chip}.\nSource: {image}\n\n"
              "The BIOS settings and this board's memory configuration are "
              "overwritten too.",
    },
    "conferma_digita": {
        "it": "Digitare {word} per procedere",
        "en": "Type {word} to proceed",
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
        "it": "Scrittura fallita (codice {code}). Non scollegare e non "
              "ricollegare l'alimentazione: leggere il registro.",
        "en": "Write failed (code {code}). Do not disconnect and do not "
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
        "it": "{model} su {drive} — pronta per il firmware",
        "en": "{model} on {drive} — ready for firmware",
    },
    "nome_scheda": {"it": "Nome", "en": "Name"},
    "nome_scheda_nota": {
        "it": "un nome per riconoscerla fra le altre",
        "en": "a name to tell it from the others",
    },
    "fw_seriale": {"it": "seriale {serial}", "en": "serial {serial}"},
    "fw_trovata_nome": {
        "it": "{name} \u00b7 {model} su {drive} \u00b7 {serial}",
        "en": "{name} \u00b7 {model} on {drive} \u00b7 {serial}",
    },
    "fw_trovata_anonima": {
        "it": "{model} su {drive} \u00b7 {serial} \u00b7 senza nome",
        "en": "{model} on {drive} \u00b7 {serial} \u00b7 unnamed",
    },
    "fw_battezzata": {
        "it": "Scheda registrata come \u00ab{name}\u00bb.",
        "en": "Board registered as \u201c{name}\u201d.",
    },
    "fw_dimenticata": {
        "it": "Nome tolto: la scheda torna anonima.",
        "en": "Name removed: the board is unnamed again.",
    },
    "parola_cancella": {"it": "CANCELLA", "en": "ERASE"},
    "fw_azzera_uno": {
        "it": "Primo consenso su due.\n\nSto per cancellare tutta la flash di "
              "{who}: {size}.\n\nLa scheda smette di essere un programmatore e "
              "torna come appena comprata. Il firmware si potr\u00e0 rimettere da "
              "qui, ma finch\u00e9 non lo fai quella scheda non serve a niente.",
        "en": "First of two confirmations.\n\nAbout to erase the whole flash of "
              "{who}: {size}.\n\nThe board stops being a programmer and goes "
              "back to as-bought. The firmware can be put back from here, but "
              "until you do, that board is of no use.",
    },
    "fw_azzera_due": {
        "it": "Secondo consenso.\n\nControlla di avere in mano la scheda "
              "giusta: quella collegata su {drive} ha il seriale\n\n"
              "    {serial}\n\nPer procedere ribatti le ultime quattro cifre.",
        "en": "Second confirmation.\n\nMake sure you are holding the right "
              "board: the one on {drive} has serial\n\n    {serial}\n\n"
              "To proceed, retype its last four characters.",
    },
    "fw_azzera_due_senza": {
        "it": "Secondo consenso.\n\nDi questa scheda non si legge il seriale. "
              "Verifica di persona che quella collegata su {drive} sia quella "
              "che vuoi cancellare.",
        "en": "Second confirmation.\n\nThis board\u2019s serial cannot be read. "
              "Check by hand that the one on {drive} is the one you mean to "
              "erase.",
    },
    "fw_bootsel": {"it": "Riporta in BOOTSEL", "en": "Send to BOOTSEL"},
    "fw_bootsel_provo": {
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
        "it": "Programmatore pronto su {port}.",
        "en": "Programmer ready on {port}.",
    },
    "fw_non_riappare": {
        "it": "Firmware copiato, ma la porta seriale non \u00e8 comparsa. Staccare e "
              "riattaccare la scheda.",
        "en": "Firmware copied, but no serial port appeared. Unplug the board and "
              "plug it back in.",
    },
    "fw_errore": {"it": "{reason}", "en": "{reason}"},
    "fw_azzera_titolo": {
        "it": "Riportare la scheda a nuovo",
        "en": "Reset the board to factory",
    },
    "fw_azzera_testo": {
        "it": "Sto per cancellare tutta la flash di {model} su {drive}: "
              "{size}.\n\nLa scheda torner\u00e0 come appena comprata e ricomparir\u00e0 "
              "come disco RPI-RP2. Il firmware si potr\u00e0 rimettere da qui.",
        "en": "About to erase the whole flash of {model} on {drive}: {size}.\n\n"
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
        "it": "{total_size} · {blocks} blocchi da {grain}",
        "en": "{total_size} · {blocks} blocks of {grain}",
    },
    "mappa_posizione": {"it": "0x{position:06X}", "en": "0x{position:06X}"},

    # --- prova a secco ------------------------------------------------------
    "prova_secco": {"it": "Prova a secco", "en": "Dry run"},
    "secco_ok": {
        "it": "Cambieranno {size} in {spans} intervalli, tutti dentro la "
              "regione. md5 atteso {md5}",
        "en": "{size} will change in {spans} ranges, all inside the "
              "region. Expected md5 {md5}",
    },
    "secco_ok_uno": {
        "it": "Cambieranno {size} in un solo intervallo, dentro la regione. "
              "md5 atteso {md5}",
        "en": "{size} will change in a single range, inside the region. "
              "Expected md5 {md5}",
    },
    "verifica_diversa_uno": {
        "it": "Un intervallo non coincide ({size}). Non ricollegare "
              "l'alimentazione.",
        "en": "One range does not match ({size}). Do not reconnect mains.",
    },
    "secco_nulla": {
        "it": "Nessuna differenza: il chip contiene già questa immagine.",
        "en": "No difference: the chip already holds this image.",
    },
    "secco_fuori": {
        "it": "{spans} intervalli differiscono anche fuori dalla regione: "
              "non verranno scritti. Cambieranno {size} byte. md5 atteso {md5}",
        "en": "{spans} ranges also differ outside the region: they will not "
              "be written. {size} bytes will change. Expected md5 {md5}",
    },
    "secco_atteso_diverso": {
        "it": "Il risultato calcolato NON coincide con il file «Atteso» "
              "({computed} ≠ {expected}). Controllare immagine, layout e regione.",
        "en": "The computed result does NOT match the “Expected” file "
              "({computed} ≠ {expected}). Check image, layout and region.",
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
    "qualifica_prova": {"it": "Provo a {speed}…", "en": "Trying {speed}…"},
    "qualifica_ok": {
        "it": "Velocità impostata: {speed}. Due letture identiche su {size}.",
        "en": "Speed set to {speed}. Two identical reads over {size}.",
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
        "it": "{phase} {percent}%",
        "en": "{phase} {percent}%",
    },
    "avanzamento_resta": {
        "it": "{phase} {percent}% · {left} alla fine",
        "en": "{phase} {percent}% · {left} left",
    },

    # --- verifica finale ----------------------------------------------------
    "verifica_finale": {"it": "Verifica finale…", "en": "Final verification…"},
    "verifica_ok": {
        "it": "Il chip contiene esattamente la nuova ROM: {size} confrontati, "
              "nessuna differenza.",
        "en": "The chip holds exactly the new ROM: {size} compared, no difference.",
    },
    "verifica_diversa": {
        "it": "{spans} intervalli non coincidono ({size}). Non ricollegare "
              "l'alimentazione.",
        "en": "{spans} ranges do not match ({size}). Do not reconnect mains.",
    },
    "coerenza_ok": {"it": "Regione coerente: {what}.", "en": "Region coherent: {what}."},
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
        "it": "{spans} intervalli diversi · {size}",
        "en": "{spans} differing ranges · {size}",
    },
    "conf_risultato_uno": {
        "it": "1 intervallo diverso · {size}",
        "en": "1 differing range · {size}",
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
    "conf_salvato": {"it": "Layout salvato in {path}",
                     "en": "Layout saved to {path}"},
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
