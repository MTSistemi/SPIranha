# Da dove viene questo flashrom.exe

Compilato da noi il **27/08/2026**, non scaricato già fatto.

**Perché.** `flashrom.org` non pubblica binari Windows: il sito ha solo i
sorgenti, e la documentazione ufficiale dice di compilarlo con MSYS2. In giro
si trovano build di terzi, non firmate — e questo attrezzo deve funzionare il
giorno in cui la BC-250 non si accende più. Stessa scelta fatta per il firmware
del Pico.

*Built by us, not downloaded: flashrom.org publishes no Windows binaries.*

## Il sorgente

| | |
|---|---|
| origine | `https://download.flashrom.org/releases/flashrom-v1.7.0.tar.xz` |
| versione | v1.7.0, del 02/03/2026 |
| dimensione | 5.298.400 byte |
| sha256 | `4328ace9833f7efe7c334bdd73482cde8286819826cc00149e83fba96bf3ab4f` |
| verifica | confrontato con `flashrom-v1.7.0.tar.xz.sha256sum` pubblicato accanto → **OK** |

⚠️ **La firma PGP NON è stata verificata.** Il tarball è firmato (chiave DSA
`6E6EF9A0BA478006E2776E4CC037BB413134D111`), ma la chiave pubblica non è nel
portachiavi locale e il keyserver `keys.openpgp.org` non l'ha restituita. Quindi
la garanzia che abbiamo è lo sha256 pubblicato **sullo stesso server** del
tarball: protegge da un download corrotto, non da un server compromesso. Se un
giorno si vuole chiudere il cerchio, si recupera la chiave da un'altra fonte e
si rifà `gpg --verify`.

## Come è stato compilato

MSYS2 (installer 2026-06-11, hash verificato da winget), shell **UCRT64**,
GCC 16.2.0, meson + ninja 1.13.2.

```bash
meson setup builddir --buildtype=release \
      -Dprogrammer=serprog,dummy \
      -Dtests=disabled -Ddocumentation=disabled -Dman-pages=disabled \
      -Dbash_completion=disabled -Dich_descriptors_tool=disabled \
      -Drpmc=disabled \
      -Dc_link_args=-static
meson compile -C builddir
```

**Le scelte, una per una:**

- `serprog` è l'unico programmatore che serve: il Pico sul J4004. Niente
  `internal` — quello si usa da Linux sulla scheda stessa, e su Windows non
  funzionerebbe comunque (`libpci` non è disponibile).
- `dummy` emula un chip in memoria: serve per provare tutta la catena
  (identificazione, lettura, doppia verifica, scrittura di una regione) senza
  attaccare niente a niente. È così che è stato collaudato il programma.
- `rpmc=disabled` **toglie la dipendenza da OpenSSL**. Con RPMC attivo l'exe
  pretende `libcrypto-3-x64.dll` e fuori da MSYS2 non parte proprio. RPMC
  (JESD260) su un MX25L128 non serve.
- `-static` per libgcc e compagnia.

## Il risultato

| | |
|---|---|
| file | `flashrom.exe`, 1.271.005 byte |
| sha256 | `9476ed25a91538c635be1fa16345e878356fb104c0227507b1ad5d51e140a041` |
| versione | `flashrom v1.7.0 on Windows 10.0 (x86_64)` |
| DLL esterne | **nessuna** — solo `KERNEL32` e le `api-ms-win-crt-*` (UCRT, dentro Windows 10 e 11) |

Provato con il `PATH` ridotto a `C:\Windows\system32;C:\Windows`, cioè fuori da
MSYS2: parte e risponde. È quello che conta, perché il giorno che serve nessuno
si ricorda di aprire la shell giusta.
