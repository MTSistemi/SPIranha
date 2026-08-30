# -*- coding: utf-8 -*-
"""Build SPIranha.exe, and the Inno Setup installer if Inno Setup is present.

It makes its own virtualenv inside this folder: the system Python is left
alone. Network access is needed only the first time, to fetch pyserial and
pyinstaller.

    python build.py                    # the executable
    python build.py --setup            # executable + installer
    python build.py --setup --sign     # and sign them both (see sign.ps1)
    python build.py --clean            # throw away build/ dist/ .venv/
"""
from __future__ import unicode_literals

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(HERE, ".venv")
PYTHON_VENV = os.path.join(VENV, "Scripts", "python.exe")
DEPENDENCIES = ["pyserial>=3.5", "pyinstaller>=6.0"]
NAME = "SPIranha"
ISCC = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]


def run(args, **kw):
    print(">", " ".join(args))
    return subprocess.call(args, cwd=HERE, **kw)


def prepare_venv():
    if not os.path.isfile(PYTHON_VENV):
        print("Creating the virtual environment in .venv")
        if run([sys.executable, "-m", "venv", VENV]) != 0:
            sys.exit("cannot create .venv")
    if run([PYTHON_VENV, "-m", "pip", "install", "--upgrade", "pip"]) != 0:
        sys.exit("pip will not upgrade")
    if run([PYTHON_VENV, "-m", "pip", "install"] + DEPENDENCIES) != 0:
        sys.exit("the dependencies will not install (the network is needed)")


VERSION = "1.2.0"


def prepare_resources():
    """Icon and file properties: they matter for something you hand out."""
    icon_path = os.path.join(HERE, "SPIranha.ico")
    if not os.path.isfile(icon_path):
        print("Generating the icon")
        run([sys.executable, os.path.join(HERE, "icon.py")])
    version = os.path.join(HERE, "build", "version.txt")
    parts = VERSION.split(".") + ["0", "0", "0", "0"]
    n = tuple(int(p) for p in parts[:4])
    os.makedirs(os.path.dirname(version), exist_ok=True)
    with open(version, "w", encoding="utf-8") as f:
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
""" % (n, n, VERSION, NAME, NAME, VERSION))
    return icon_path, version


def build_exe():
    icon_path, version = prepare_resources()
    flashrom = os.path.join(HERE, "flashrom", "flashrom.exe")
    args = [
        PYTHON_VENV, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", NAME,
        "--icon", icon_path,
        "--version-file", version,
        "--hidden-import", "serial.tools.list_ports",
        "--exclude-module", "numpy",
        "--exclude-module", "PIL",
    ]
    # ⚠️ flashrom travels INSIDE the executable: that is what makes it
    # portable. Without it, another machine would show the red banner.
    if os.path.isfile(flashrom):
        args += ["--add-binary", "%s%sflashrom" % (flashrom, os.pathsep)]
    else:
        print("⚠️ flashrom/flashrom.exe is missing: the executable will NOT be portable")
    # the programmer firmware travels inside too, when it is there
    fw = os.path.join(HERE, "firmware", "pico_serprog.uf2")
    if os.path.isfile(fw):
        args += ["--add-data", "%s%sfirmware" % (fw, os.pathsep)]
    else:
        print("⚠️ firmware/pico_serprog.uf2 is missing: no firmware install "
              "from the executable")
    args.append(os.path.join(HERE, "SPIranha.pyw"))
    if run(args) != 0:
        sys.exit("PyInstaller failed")
    exe = os.path.join(HERE, "dist", NAME + ".exe")
    print("\nDone: %s (%.1f MiB)" % (exe, os.path.getsize(exe) / 1048576.0))
    return exe


def sig(paths):
    """Sign with sign.ps1. ⚠️ ORDER MATTERS: the executable first, then the
    installer that carries it. Signing only at the end would leave the exe
    inside the setup unsigned."""
    script = os.path.join(HERE, "sign.ps1")
    if not os.path.isfile(script):
        print("sign.ps1 is missing: skipping the signature")
        return
    args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", script, "-Path"] + list(paths)
    run(args)


def write_iss_version():
    """The version number for Inno Setup: one only, generated from here."""
    folder = os.path.join(HERE, "build")
    if not os.path.isdir(folder):
        os.makedirs(folder)
    path = os.path.join(folder, "version.iss")
    with open(path, "w", encoding="utf-8") as f:
        f.write('#define Version "%s"\n' % VERSION)
    return path


def build_setup():
    write_iss_version()
    iscc = next((p for p in ISCC if os.path.isfile(p)), None)
    if not iscc:
        print("Inno Setup not found: skipping the installer.")
        return None
    if run([iscc, os.path.join(HERE, NAME + ".iss")]) != 0:
        sys.exit("Inno Setup failed")
    return os.path.join(HERE, "dist")


def clean():
    for name in ("build", "dist", ".venv", NAME + ".spec", "__pycache__"):
        path = os.path.join(HERE, name)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.isfile(path):
            os.remove(path)
    print("cleaned")


def main():
    if "--clean" in sys.argv:
        clean()
        return 0
    prepare_venv()
    exe = build_exe()
    wants_signature = "--sign" in sys.argv
    if wants_signature:
        sig([exe])
    if "--setup" in sys.argv:
        build_setup()
        setup = os.path.join(HERE, "dist",
                             "%s-Setup-%s.exe" % (NAME, VERSION))
        if wants_signature and os.path.isfile(setup):
            sig([setup])
    return 0


if __name__ == "__main__":
    sys.exit(main())
