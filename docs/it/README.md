# Programmatore BIOS — BC-250

Finestra Windows per usare il Pico con `pico-serprog` sul connettore **J4004**
della BC-250, senza scrivere comandi a mano.

*English version: [README.md](README.md).*

**A cosa serve.** Quando serve questo programma la scheda è già morta e si ha
fretta. Le cose che oggi bisogna ricordarsi a mente — leggere due volte e
confrontare le impronte, tenere la BC-250 staccata dalla corrente, rileggere
prima di riattaccare — qui le impone il programma: il tasto di scrittura resta
spento finché non tornano tutte.

**Cosa NON fa.** Non parla lui col chip. Il codice che cancella settori e scrive
pagine resta quello di `flashrom`, collaudato da vent'anni. Questo programma
costruisce le righe di comando giuste, le esegue e legge gli esiti.

## flashrom: c'è già

`flashrom.exe` è in `flashrom\`, **compilato da noi** il 27/08/2026 dal sorgente
ufficiale v1.7.0 (flashrom.org non pubblica binari Windows). È autonomo: non
gli serve nessuna DLL esterna, non serve MSYS2 installato. Dettagli, checksum e
opzioni di compilazione in [flashrom-PROVENANCE.md](flashrom-PROVENANCE.md).

Se un giorno lo si sposta, il programma lo cerca accanto all'eseguibile, in
`flashrom\` e nel `PATH`; se non lo trova mostra una fascia rossa con
**Individua…** per indicarlo a mano, e ricorda il percorso scelto.

## Come si presenta

Tema **«quadro strumenti»**:
fondo ardesia, filetti sottili, micro-etichette maiuscole, registro a
spaziatura fissa, e il colore forte speso in un punto solo.

L'interfaccia è **adattabile**: sopra i 940 px le schede si dispongono su due
colonne, sotto si impilano in una sola. Lingua **italiana o inglese**, dalla
tendina in alto a destra: cambia a caldo, schema compreso.

## Schema dei collegamenti

Il pulsante **Schema** apre il disegno di dove vanno i cavetti, da una parte e
dall'altra. È disegnato a codice: si ridimensiona senza sgranare e sta dentro
l'eseguibile.

| J4004 | Pico | |
|---|---|---|
| 1 VCC | 36 | 3V3 OUT |
| 2 GND | **3** | GND |
| 3 CS | 7 | GP5 |
| 4 SCLK | 4 | GP2 |
| 5 MISO | 6 | GP4 |
| 6 MOSI | 5 | GP3 |

**GND si prende dal piedino 3**, non dal 38: sta accanto ai quattro segnali, e
così i cavi occupano i piedini **3-4-5-6-7 contigui** — un solo pettine da
cinque, più il 3V3 sul 36.

Il connettore è **2×4**, non 2×3:

```
[ GND SCLK MOSI UNK ]
[ VCC  CS  MISO     ]
   ^  piedino 1 = VCC, triangolo bianco in serigrafia
```

`UNK` è a massa tramite 10 kΩ e non si collega. Piedinatura da
`mothenjoyer69/bc250-documentation` e `elektricM/amd-bc250-docs`, che
concordano.

⚠️ **La scheda ha due chip di flash.** Il bersaglio è `BIOS_A1` da 16 MB.
`SIO1_R` da 512 KB è il SuperIO e ne dipende il controllo delle ventole: se il
programma riporta 512 KB, il chip è quello sbagliato. Il controllo sulla
dimensione dell'immagine lo intercetta da sé.

## La mappa del chip

Sotto le quattro schede c'è un rettangolo di quadratini: è la flash, divisa in
blocchi, e ognuno si colora per quello che gli sta succedendo — da fare, letto,
cancellato, scritto, verificato, diverso. Passandoci sopra il mouse, in basso a
destra compare l'indirizzo.

**Non è un'animazione di comodo.** I colori arrivano da quello che flashrom
dice davvero: con `-V` stampa un marcatore `E(inizio:fine)` per ogni blocco che
cancella (sulla regione UEFI sono 21, venti da 64 KB e uno da 4 KB) e
`W(inizio:fine)` per l'intervallo scritto; `--progress` dà la percentuale delle
tre fasi. Il programma li legge dal flusso e li riporta sulla mappa.

La stessa cosa vale per la barra in basso: mostra la fase in corso, la
percentuale vera e **quanto manca alla fine**.

## Prova a secco

**È obbligatoria.** Il tasto **Scrivi…** non si accende finché non è stata
fatta, e decade da sola se cambi immagine, layout, regione o rifai la lettura.

Prende la lettura verificata e l'immagine da scrivere, e calcola **in memoria**
come verrà la flash, senza toccarla:

- l'**md5 atteso**, prima di cancellare qualsiasi cosa;
- **quanti byte cambieranno e in quanti intervalli**, elencati nel registro;
- soprattutto: se l'immagine differisce **anche fuori dalla regione scelta**,
  te lo dice. Quelle differenze non verranno scritte, ed è il sintomo classico
  del layout sbagliato o dell'immagine di un'altra scheda;
- se hai indicato un file **Atteso**, confronta il risultato calcolato con
  quello e si rifiuta se non coincidono.

Il risultato calcolato è anche l'immagine con cui il chip verrà verificato alla
fine.

## Qualifica del collegamento

Il pulsante **Qualifica** rilegge 256 KB due volte a 12, 8, 4, 2, 1 MHz e
500 kHz, e si ferma alla prima velocità che dà due letture identiche,
impostandola da sé. Sul J4004 con i cavetti volanti il collegamento incerto è
il rischio principale, e così lo si scopre in pochi secondi invece che con due
letture intere da 16 MiB.

## Confronto fra immagini

Il pulsante **Confronta**, accanto alla lettura, apre una finestra a parte:
date due immagini, elenca gli **intervalli diversi allineati ai settori da
4 KB**, i confini veri byte per byte, la dimensione e cosa c'è dentro (volumi
UEFI, variabili `NVAR`, `APCB`, direttori `$PSP`). E scrive il **file di layout
per flashrom** già pronto.

È lo stesso lavoro fatto a mano il 22/08/2026 per trovare le quattro zone in
cui il BIOS modificato differiva da quello della scheda. Ora dura un secondo.

## La procedura, nell'ordine

### 1. Collegamento
**Rileva** elenca le porte seriali e mette per prima quella che somiglia al Pico
(`CAFE:4001`, che è TinyUSB). **Interroga il Pico** apre la porta e gli chiede chi
è, nel protocollo serprog: se risponde `pico-serprog`, interfaccia 1, bus
`0x08 = SPI`, il firmware è quello giusto. Serve perché presentarsi come porta
seriale non vuol dire niente — lo farebbe qualunque firmware sbagliato.

La **velocità SPI** parte da quella del firmware (12 MHz). Si scende solo se le
due letture non coincidono.

### 2. Chip
**Identifica il chip** chiama `flashrom --flash-name`. Se risponde che i modelli
possibili sono più d'uno, i candidati finiscono nella tendina **Forza il
modello** e se ne sceglie uno (per questa scheda: `MX25L12835F/MX25L12873F`).

### 3. Lettura e backup
**Leggi e verifica** legge il chip **due volte** e confronta gli md5:

- uguali → la prima lettura resta come `bc250-letto-<data>.rom`, la seconda si
  cancella, e il programma dice se l'impronta è una di quelle note (il BIOS
  originale della scheda, o il risultato atteso);
- diversi → messaggio rosso. Collegamento incerto: si ricontrollano i fili e si
  abbassa la velocità. **Non si scrive.**

Una lettura verificata **in questa sessione** è uno dei requisiti per scrivere:
se cambi porta o velocità, decade e va rifatta.

### 4. Scrittura
Due modi:

| modo | cosa fa |
|---|---|
| **Solo una regione** | `-l layout -i regione -w immagine`: per la sola regione UEFI, tenendo impostazioni e configurazione della memoria |
| **Il chip intero** | `-w immagine`: il ripristino, quando si riparte dall'immagine originale |

Il tasto **Scrivi…** è spento finché non ci sono tutti: flashrom trovato, chip
identificato, lettura verificata, immagine della dimensione giusta del chip,
layout e regione (nel primo modo), la spunta **la BC-250 è STACCATA dalla
corrente** e la **prova a secco**. Quello che manca è scritto sotto al tasto.

Poi si conferma **scrivendo la parola** `SCRIVI` (`WRITE` in inglese): un «sì»
non basta.

### Verifica finale

Finita la scrittura, il programma **rilegge tutto il chip** e lo confronta byte
per byte con l'immagine che la prova a secco aveva calcolato. È una verifica
**indipendente** da quella che fa flashrom per conto suo.

Poi controlla che la regione scritta sia **coerente**: che non sia rimasta tutta
`0xFF` (cancellata e mai riscritta) o tutta `0x00`, e riporta quali strutture
note contiene. Se qualcosa non torna, gli intervalli che non coincidono
diventano rossi sulla mappa e vengono elencati nel registro.

È l'ultimo controllo prima di riattaccare la corrente.

## I file da usare

Stanno in `..\bios-backup\`:

| file | |
|---|---|
| `bc250-stock.rom` | l'immagine di recupero, md5 `3487f648…` |
| `bc250-risultato-atteso.rom` | come dev'essere dopo, md5 `f7632f2f…` |
| `bc250-layout.txt` | le tre regioni: `prima`, **`uefi`**, `dopo` |

Le due impronte il programma le riconosce da sé e le dice a parole.

## ⚠️ Le regole che non cambiano

- **BC-250 staccata dalla corrente.** Il chip lo alimenta il Pico (3V3, piedino
  36). Due padroni sullo stesso bus non funzionano e possono far danni.
- **Due letture diverse = non si scrive.** Mai.
- **Durante una scrittura non si interrompe.** Il tasto **Interrompi** si
  rifiuta di farlo, e va bene così: un chip cancellato a metà non si avvia.
- **Prima di riattaccare la corrente**, si rilegge e si confronta.

## Registro

Tutto quello che dice flashrom finisce nel riquadro in basso e, a fine
operazione, in coda a `SPIranha.log` dentro la cartella di lavoro. La
spunta `-V` accende il registro dettagliato di flashrom: serve quando qualcosa
non torna.

## L'eseguibile portatile

`dist\ProgrammatoreBIOS.exe` è **un file solo, e basta quello**: 9,7 MiB con
dentro Python, pyserial, l'interfaccia e **flashrom**. Si copia su una chiavetta
e funziona su qualunque Windows 10 o 11 a 64 bit, senza installare niente.

All'avvio flashrom viene scompattato in una cartella temporanea e il programma
lo usa da lì — nella barra di stato si vede il percorso `…\_MEI…\flashrom\`.
Provato davvero: copiato l'exe da solo in una cartella vuota, con la
configurazione e la cartella `flashrom\` nascoste, parte e lo trova.

Se accanto all'exe c'è una cartella `flashrom\`, quella ha comunque la
precedenza: si può aggiornare flashrom senza ricostruire niente.

| | |
|---|---|
| `ProgrammatoreBIOS.exe` | portatile, 9,7 MiB, sha256 `164dd0bd…` |
| `ProgrammatoreBIOS-Setup-1.1.0.exe` | installatore, 11,6 MiB, sha256 `85d9f7fc…` |

⚠️ Le impronte cambiano a ogni firma: la marca temporale è diversa ogni volta.
Quelle qui sopra valgono per la build del 27/08/2026.

## La firma

Entrambi sono firmati **MTSistemi** (`CN=MTSistemi, O=MTSistemi, C=IT`) con
marca temporale Sectigo, così la firma resta valida anche quando il certificato
scadrà.

```bash
python build.py --setup --sign
```

L'ordine conta ed è quello: si costruisce l'exe, **lo si firma**, poi si
costruisce l'installatore che se lo porta dentro, poi si firma anche quello.
Firmando solo alla fine, l'exe dentro il setup resterebbe nudo.

Non serve il Windows SDK: `firma.ps1` usa `Set-AuthenticodeSignature`, che è
dentro PowerShell.

| comando | |
|---|---|
| `.\firma.ps1` | firma `dist\*.exe` col certificato MTSistemi |
| `.\firma.ps1 -Elenca` | mostra i certificati di firma disponibili |
| `.\firma.ps1 -Impronta <thumbprint>` | ne sceglie uno preciso |
| `.\firma.ps1 -Pfx <percorso>` | usa un `.pfx` (la password la chiede PowerShell) |
| `.\firma.ps1 -CreaAutofirmato` | rifà il certificato autofirmato |

⚠️ **Il certificato attuale è autofirmato**, creato su questa macchina il
27/08/2026 (impronta `09D323E0775E2E66942A3DF3832CC5294363345F`, scade nel
2031). Questo vuol dire che:

- la firma **c'è** e dice chi è l'autore, ma la catena non è verificabile da
  fuori: `Get-AuthenticodeSignature` riporta `UnknownError`;
- **SmartScreen continuerà ad avvisare** sulle macchine altrui.

Due strade per togliere l'avviso, secondo a chi va il programma:

1. **Solo macchine nostre.** Si dichiara affidabile il certificato una volta per
   macchina, con lo script pronto — **da PowerShell come amministratore**:
   ```powershell
   .\fidati-del-certificato.ps1
   ```
   Prima di importare controlla che l'impronta sia quella attesa, poi verifica
   da solo che la firma dell'eseguibile risulti `Valid`.
   `-Verifica` dice com'è messa senza toccare niente, `-Rimuovi` disfa tutto.

   Per la flotta, invece che macchina per macchina: **Criteri di gruppo** →
   *Configurazione computer* → *Criteri* → *Impostazioni di Windows* →
   *Impostazioni sicurezza* → *Criteri chiave pubblica*, e si importa
   `MTSistemi.cer` in **Autorità di certificazione radice attendibili** e in
   **Editori attendibili**.

   ⚠️ **Cosa comporta davvero.** In `Root` il certificato diventa una *radice
   attendibile*: da quel momento quelle macchine si fidano di qualunque cosa
   sia firmata con quella chiave privata, non solo di questo programma. La
   chiave sta nel profilo utente del PC dove è stata creata
   (`Cert:\CurrentUser\My`). Chi se ne impossessa può firmare software che la
   flotta accetterà senza avvisi. Se il sospetto viene, si passa
   `-Rimuovi` ovunque e si rifà il certificato.
2. **Anche fuori.** Serve un certificato OV o EV di una CA, intestato a
   MTSistemi. Dal 2023 questi certificati stanno su token hardware o HSM: una
   volta collegato il token a questa macchina, `.\firma.ps1 -Elenca` lo vede e
   `build.py --setup --sign` firma con quello senza altre modifiche.

## Come si avvia

Con Python (serve `pyserial`, altrimenti la porta va scritta a mano):

```bash
python ProgrammatoreBIOS.pyw
```

Per farne un eseguibile unico, in un ambiente virtuale tutto suo (il Python di
sistema non viene toccato):

```bash
python build.py --setup
```

Escono `dist\ProgrammatoreBIOS.exe` e, se c'è Inno Setup 6,
`dist\ProgrammatoreBIOS-Setup-1.0.0.exe`.

## Com'è fatto dentro

| file | |
|---|---|
| `app.py` | la finestra e i requisiti di scrittura |
| `flashrom.py` | costruisce i comandi, lancia il processo, legge le risposte |
| `serprog.py` | interroga il Pico e il chip (JEDEC, SFDP) |
| `pico.py` | BOOTSEL, formato UF2, installazione e ritorno a nuovo |
| `i18n.py` | le scritte in italiano e in inglese |
| `build.py` | l'eseguibile e l'installatore |
| `analysis.py` | confronto, prova a secco, firme, layout generato |
| `regions.py` | le regioni lette dall'immagine (IFD, FMAP, struttura AMD) |
| `profiles.py` | i profili di scheda |
| `voltage.py` | la tensione del chip dedotta dal modello |
| `boards.py` | i nomi dati ai programmatori |
| `chipmap.py` | la mappa a blocchi e la sua legenda |
| `compare.py` | la finestra di confronto fra immagini |
| `chip_search.py` | la ricerca fra i modelli che flashrom conosce |
| `wiring.py` | lo schema dei collegamenti |
| `level_shifter.py` | lo schema dell'adattatore a 1,8 V |
| `printing.py` | la stampa in PDF |
| `theme.py` | il tema «quadro strumenti» |
| `tests\` | i controlli automatici, vedi [tests-README.md](tests-README.md) |

## Com'è stato collaudato

`tests	est_full.py` fa girare la finestra vera con flashrom vero su un
chip da 16 MiB **emulato**: parte dal BIOS originale, scrive la sola regione
`uefi` presa dal BIOS modificato, e controlla che il risultato sia identico byte
per byte a `bc250-risultato-atteso.rom`. È la stessa identica operazione che si
farà sulla scheda. Verifica anche che due letture diverse blocchino tutto e che
la conferma non si accenda senza la parola giusta.

⚠️ Nota di protocollo: **`0x10` è `SYNCNOP`**, e la risposta giusta è `0x15`
(NAK) **seguito da** `0x06` (ACK). Non è un comando inesistente. Verificato sul
Pico vero il 27/08/2026.

## Autori

**Copyright © 2026 Mattia Tadini.** Scritto da Mattia Tadini e Claude (Opus 5),
a quattro mani: la storia dei commit lo dice commit per commit, invece che in
una nota a fondo pagina. L'hardware, il banco e le decisioni che contavano sono
di Mattia. Vedi [AUTHORS](../../AUTHORS).
