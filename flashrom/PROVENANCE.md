# Where flashrom.exe comes from

`flashrom.exe` is **not in this repository**, and it is not downloaded
pre-built either. It has to be compiled — this file says exactly how, so that
anyone can reproduce the same binary.

*Versione italiana: [`docs/it/flashrom-PROVENIENZA.md`](../docs/it/flashrom-PROVENIENZA.md).*

## Why build it

flashrom.org publishes **source only**: there are no official Windows binaries.
Unofficial builds exist, unsigned and of unclear provenance. This is a tool you
reach for when a board no longer starts, so the half hour of compiling is worth
it.

## The source

| | |
|---|---|
| origin | `https://download.flashrom.org/releases/flashrom-v1.7.0.tar.xz` |
| version | v1.7.0, released 2026-03-02 |
| size | 5,298,400 bytes |
| sha256 | `4328ace9833f7efe7c334bdd73482cde8286819826cc00149e83fba96bf3ab4f` |
| checked against | `flashrom-v1.7.0.tar.xz.sha256sum`, published next to it → **OK** |

⚠️ **The PGP signature was not verified.** The tarball is signed (DSA key
`6E6EF9A0BA478006E2776E4CC037BB413134D111`), but the public key was not in the
local keyring and `keys.openpgp.org` did not return it. So the guarantee here is
a checksum published **on the same server** as the tarball: that protects
against a corrupted download, not against a compromised server. To close the
loop, fetch the key from another source and run `gpg --verify`.

## How it was built

MSYS2 (installer 2026-06-11, hash verified by winget), **UCRT64** shell,
GCC 16.2.0, meson with ninja 1.13.2.

```bash
pacman -S mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-meson \
          mingw-w64-ucrt-x86_64-ninja mingw-w64-ucrt-x86_64-pkg-config

meson setup builddir --buildtype=release \
      -Dprogrammer=serprog,dummy \
      -Dtests=disabled -Ddocumentation=disabled -Dman-pages=disabled \
      -Dbash_completion=disabled -Dich_descriptors_tool=disabled \
      -Drpmc=disabled \
      -Dc_link_args=-static
meson compile -C builddir
```

Then copy `builddir/flashrom.exe` into this folder.

**Every option, and why:**

- `serprog` is the only programmer needed: the RP2040 on the target's SPI
  header. No `internal` — that one runs on the machine being flashed, and on
  Windows it would not work anyway (`libpci` is unavailable).
- `dummy` emulates a flash chip in memory. **Keep it**: it is what the test
  suite drives, so the whole chain — identify, read, double-check, write a
  region, verify — can be exercised with nothing connected.
- `rpmc=disabled` **removes the OpenSSL dependency**. With RPMC enabled the
  executable demands `libcrypto-3-x64.dll` and, outside MSYS2, fails to start
  with no message at all. RPMC (JESD260) is irrelevant here.
- `-static` for libgcc and friends.

## The result

| | |
|---|---|
| file | `flashrom.exe`, 1,271,005 bytes |
| sha256 | `9476ed25a91538c635be1fa16345e878356fb104c0227507b1ad5d51e140a041` |
| version | `flashrom v1.7.0 on Windows 10.0 (x86_64)` |
| external DLLs | **none** — only `KERNEL32` and the `api-ms-win-crt-*` (UCRT, part of Windows 10 and 11) |

Tested with `PATH` cut down to `C:\Windows\system32;C:\Windows`, that is,
outside MSYS2: it starts and answers. That is the part that matters, because on
the day you need it nobody remembers to open the right shell.

## Licence

flashrom is **GPL-2.0**: mostly `GPL-2.0-or-later`, but 84 files are
`GPL-2.0-only`, which makes the resulting binary v2 and not upgradable to v3.
A few files are BSD-3-Clause or MIT.

If you redistribute this binary — on its own, or embedded in a SPIranha build —
you must also make the **exact corresponding source** available, keep the
copyright notices and the licence text, and keep the warranty disclaimer
intact. The simplest way: attach `flashrom-v1.7.0.tar.xz` to the same release
as the binary.

Nothing in the source was modified. Only build options were chosen, and they
are listed above.
