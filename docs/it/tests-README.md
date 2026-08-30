# Le prove

Si lanciano con il Python del `.venv` del progetto (ha `pyserial`):

```bash
..\.venv\Scripts\python.exe prova_gui.py
..\.venv\Scripts\python.exe prova_completa.py
```

Aprono e chiudono la finestra da sole: non c'è niente da cliccare.

## `prova_gui.py` — 21 controlli

La finestra e le sue regole, senza toccare flashrom: costruzione, cambio lingua
IT↔EN, blocco totale quando flashrom manca, lettura del file di layout, e i
requisiti di scrittura che si accendono e si spengono uno per uno (fra cui
un'immagine di dimensione sbagliata, che dev'essere rifiutata).

Verifica anche la regola della **prova a secco**: senza, il tasto di scrittura
resta spento; e se cambia l'immagine la prova decade da sola.

## `prova_completa.py` — 37 controlli

**Questa è quella che conta.** Usa la finestra vera e flashrom vero; l'unica
differenza è il programmatore, che invece di `serprog` è `dummy`, cioè un chip
da 16 MiB emulato in memoria e salvato su file.

La prova centrale ricalca **esattamente** l'operazione vera sulla BC-250:

1. il chip emulato viene inizializzato con `bc250-stock.rom`;
2. si scrive la **sola** regione `uefi`, presa da `bc250-risultato-atteso.rom`,
   con `bc250-layout.txt`;
3. alla fine il chip emulato dev'essere identico byte per byte a
   `bc250-risultato-atteso.rom` (md5 `f7632f2f…`).

Copre anche tutto quello che è stato aggiunto dopo:

- la **qualifica del collegamento** sceglie una velocità e ripulisce i suoi file;
- la **prova a secco** calcola md5 `f7632f2f…`, un solo intervallo, 1.321.026
  byte, niente fuori regione — e senza di lei non si scrive;
- la **verifica finale** rilegge tutto il chip, non trova differenze e dichiara
  la regione coerente (`volume UEFI ×1`);
- la **mappa** finisce tutta verde, senza un solo blocco rosso;
- il **layout generato** dal confronto ha gli stessi tre intervalli di
  `bc250-layout.txt` scritto a mano ad agosto (cambiano solo i nomi delle
  regioni di contorno: `salta0`/`salta2` invece di `prima`/`dopo`), e flashrom
  lo rilegge.

Verifica anche le due sicurezze che contano davvero:

- **due letture diverse**: viene simulato un md5 ballerino, e la lettura non
  deve essere validata, il tasto di scrittura deve restare spento e **entrambi**
  i file vanno tenuti per poterli guardare;
- **la conferma**: parte spenta, resta spenta con la parola sbagliata, si accende
  solo con `SCRIVI`.

⚠️ Serve `..\flashrom\flashrom.exe` (compilato con il programmatore `dummy`
attivo, vedi `flashrom\PROVENANCE.md`). Le prove scrivono in `tests\work\`,
che si può cancellare.
