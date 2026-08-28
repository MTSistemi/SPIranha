# -*- coding: utf-8 -*-
"""Build SPIranha.exe, and the Inno Setup installer if Inno Setup is present.

It makes its own virtualenv inside this folder: the system Python is left
alone. Network access is needed only the first time, to fetch pyserial and
pyinstaller.

    python build.py                    # the executable
    python build.py --setup            # executable + installer
    python build.py --setup --sign     # and sign them both (see sign.ps1)
    python build.py --clean            # throw away build/ dist/ .venv/

NOTE: the module below is written in Italian, like the rest of the codebase.
"""
from __future__ import unicode_literals

import os
import shutil
import subprocess
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(QUI, ".venv")
PYTHON_VENV = os.path.join(VENV, "Scripts", "python.exe")
DIPENDENZE = ["pyserial>=3.5", "pyinstaller>=6.0"]
NOME = "SPIranha"
ISCC = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]


def esegui(args, **kw):
    print(">", " ".join(args))
    return subprocess.call(args, cwd=QUI, **kw)


def prepara_venv():
    if not os.path.isfile(PYTHON_VENV):
        print("Creo l'ambiente virtuale in .venv")
        if esegui([sys.executable, "-m", "venv", VENV]) != 0:
            sys.exit("non riesco a creare .venv")
    if esegui([PYTHON_VENV, "-m", "pip", "install", "--upgrade", "pip"]) != 0:
        sys.exit("pip non si aggiorna")
    if esegui([PYTHON_VENV, "-m", "pip", "install"] + DIPENDENZE) != 0:
        sys.exit("le dipendenze non si installano (serve la rete)")


VERSIONE = "1.2.0"


def prepara_risorse():
    """Icona e proprieta' del file: per qualcosa che si distribuisce contano."""
    icona = os.path.join(QUI, "SPIranha.ico")
    if not os.path.isfile(icona):
        print("Genero l'icona")
        esegui([sys.executable, os.path.join(QUI, "icona.py")])
    versione = os.path.join(QUI, "build", "versione.txt")
    parti = VERSIONE.split(".") + ["0", "0", "0", "0"]
    n = tuple(int(p) for p in parti[:4])
    os.makedirs(os.path.dirname(versione), exist_ok=True)
    with open(versione, "w", encoding="utf-8") as f:
        f.write("""VSVersionInfo(
  ffi=FixedFileInfo(filevers=%r, prodvers=%r, mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040C04B0', [
      StringStruct('CompanyName', 'MTSistemi'),
      StringStruct('LegalCopyright',
                   '\\u00a9 2026 Mattia Tadini \\u2014 GPL-2.0'),
      StringStruct('FileDescription',
                   'SPIranha \\u2014 BIOS and SPI flash programmer'),
      StringStruct('FileVersion', '%s'),
      StringStruct('InternalName', '%s'),
      StringStruct('OriginalFilename', '%s.exe'),
      StringStruct('ProductName', 'SPIranha'),
      StringStruct('ProductVersion', '%s'),
      StringStruct('Comments',
                   'Raspberry Pi Pico with pico-serprog. flashrom included. '
                   'By Mattia Tadini and Claude.')])]),
    VarFileInfo([VarStruct('Translation', [1036, 1200])])]
)
""" % (n, n, VERSIONE, NOME, NOME, VERSIONE))
    return icona, versione


def costruisci_exe():
    icona, versione = prepara_risorse()
    flashrom = os.path.join(QUI, "flashrom", "flashrom.exe")
    args = [
        PYTHON_VENV, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", NOME,
        "--icon", icona,
        "--version-file", versione,
        "--hidden-import", "serial.tools.list_ports",
        "--exclude-module", "numpy",
        "--exclude-module", "PIL",
    ]
    # ⚠️ flashrom viaggia DENTRO l'eseguibile: e' cio' che lo rende portatile.
    # Senza, su un'altra macchina comparirebbe la fascia rossa.
    if os.path.isfile(flashrom):
        args += ["--add-binary", "%s%sflashrom" % (flashrom, os.pathsep)]
    else:
        print("⚠️ flashrom/flashrom.exe non c'e': l'eseguibile NON sara' portatile")
    # anche il firmware del programmatore viaggia dentro, se c'e'
    fw = os.path.join(QUI, "firmware", "pico_serprog.uf2")
    if os.path.isfile(fw):
        args += ["--add-data", "%s%sfirmware" % (fw, os.pathsep)]
    else:
        print("⚠️ firmware/pico_serprog.uf2 non c'e': niente installazione del "
              "firmware dall'eseguibile")
    args.append(os.path.join(QUI, "SPIranha.pyw"))
    if esegui(args) != 0:
        sys.exit("PyInstaller ha fallito")
    exe = os.path.join(QUI, "dist", NOME + ".exe")
    print("\nFatto: %s (%.1f MiB)" % (exe, os.path.getsize(exe) / 1048576.0))
    return exe


def firma(percorsi):
    """Firma con sign.ps1. ⚠️ L'ORDINE CONTA: prima l'eseguibile, poi
    l'installatore che se lo porta dentro. Firmando solo alla fine, l'exe
    dentro il setup resterebbe non firmato."""
    script = os.path.join(QUI, "sign.ps1")
    if not os.path.isfile(script):
        print("sign.ps1 non c'e': salto la firma")
        return
    args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", script, "-Path"] + list(percorsi)
    esegui(args)


def scrivi_versione_iss():
    """Il numero di versione per Inno Setup: uno solo, generato da qui."""
    cartella = os.path.join(QUI, "build")
    if not os.path.isdir(cartella):
        os.makedirs(cartella)
    percorso = os.path.join(cartella, "versione.iss")
    with open(percorso, "w", encoding="utf-8") as f:
        f.write('#define Versione "%s"\n' % VERSIONE)
    return percorso


def costruisci_setup():
    scrivi_versione_iss()
    iscc = next((p for p in ISCC if os.path.isfile(p)), None)
    if not iscc:
        print("Inno Setup non trovato: salto l'installatore.")
        return None
    if esegui([iscc, os.path.join(QUI, NOME + ".iss")]) != 0:
        sys.exit("Inno Setup ha fallito")
    return os.path.join(QUI, "dist")


def pulisci():
    for nome in ("build", "dist", ".venv", NOME + ".spec", "__pycache__"):
        percorso = os.path.join(QUI, nome)
        if os.path.isdir(percorso):
            shutil.rmtree(percorso, ignore_errors=True)
        elif os.path.isfile(percorso):
            os.remove(percorso)
    print("pulito")


def main():
    if "--clean" in sys.argv:
        pulisci()
        return 0
    prepara_venv()
    exe = costruisci_exe()
    vuole_firma = "--sign" in sys.argv
    if vuole_firma:
        firma([exe])
    if "--setup" in sys.argv:
        costruisci_setup()
        setup = os.path.join(QUI, "dist",
                             "%s-Setup-%s.exe" % (NOME, VERSIONE))
        if vuole_firma and os.path.isfile(setup):
            firma([setup])
    return 0


if __name__ == "__main__":
    sys.exit(main())
