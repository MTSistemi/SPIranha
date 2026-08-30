# -*- coding: utf-8 -*-
"""Is there a newer release, and how to install it safely.

The program asks GitHub once at startup, and if a newer version exists it
says so and offers to install it. Nothing happens without being asked.

⚠️ THE POINT OF THIS FILE IS THE REFUSALS, not the download. A program that
fetches an executable off the internet and runs it is a way in, and this one
already has the privileges to rewrite a BIOS. So:

  - only https, and only to github.com / githubusercontent.com;
  - the installer is Authenticode-verified BEFORE being run, and not merely
    "is it signed": the signing certificate must be OUR certificate, matched
    by thumbprint. A validly signed installer from anybody else is refused;
  - the sha-256 is computed and shown, so what ran can be told apart later;
  - it is never run without a confirmation, and never on its own;
  - failures are silent to the interface and loud in the log: a program that
    cannot reach GitHub is not a program in trouble.

⚠️ The check can be turned off and the answer is remembered. Somebody
programming a BIOS on an isolated bench should not have a tool that talks to
the internet behind their back.
"""
from __future__ import unicode_literals

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

try:
    from urllib.request import Request, urlopen
    from urllib.error import URLError
except ImportError:                      # pragma: no cover - Python 2
    from urllib2 import Request, urlopen, URLError

from serprog import is_older
from version import VERSION

OWNER = "MTSistemi"
REPOSITORY = "SPIranha"
API = "https://api.github.com/repos/%s/%s/releases/latest" % (OWNER, REPOSITORY)

# ⚠️ Our signing certificate, pinned. If the certificate is ever renewed or
# replaced this constant has to be updated in the same commit, or the update
# will politely refuse itself -- which is the correct way round for it to
# fail. See sign.ps1 and trust-certificate.ps1.
SIGNER = "09D323E0775E2E66942A3DF3832CC5294363345F"
SIGNER_NAME = "MTSistemi"

ALLOWED_HOSTS = ("github.com", "githubusercontent.com")
SETUP_NAME = re.compile(r"^SPIranha-Setup-[0-9.]+\.exe$", re.IGNORECASE)
NO_WINDOW = 0x08000000 if os.name == "nt" else 0

TIMEOUT = 6.0
MAX_BYTES = 80 * 1024 * 1024       # an installer is ~13 MiB; this is a wall


class Release(object):
    """What GitHub says the latest release is."""

    def __init__(self, version=None, url=None, page=None, size=0, error=None):
        self.version = version
        self.url = url                  # the installer
        self.page = page                # the release page, for a human
        self.size = size
        self.error = error

    @property
    def ok(self):
        return self.error is None and bool(self.version)

    @property
    def newer(self):
        """Newer than what is running. Same version, or older: nothing to do."""
        return bool(self.ok and is_older(VERSION, self.version))


def _https_to_github(url):
    """Only our own release assets. Everything else is not our business."""
    if not url or not url.lower().startswith("https://"):
        return False
    host = url.split("/")[2].split(":")[0].lower()
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


def latest(timeout=TIMEOUT, url=API, opener=None):
    """Asks GitHub. Never raises: a Release carrying the reason comes back."""
    opener = opener or urlopen
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        # GitHub refuses a request with no user agent
        "User-Agent": "SPIranha/%s" % VERSION,
    })
    try:
        answer = opener(request, timeout=timeout)
        raw = answer.read(2 * 1024 * 1024)
    except (URLError, OSError, ValueError) as e:
        return Release(error="%s" % e)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        return Release(error="%s" % e)
    return from_json(data)


def from_json(data):
    """The interesting part of GitHub's answer. Split out to be testable."""
    tag = (data.get("tag_name") or "").strip()
    version = tag[1:] if tag[:1].lower() == "v" else tag
    if not re.match(r"^\d+(\.\d+)*$", version or ""):
        return Release(error="unreadable tag: %r" % tag)
    if data.get("draft") or data.get("prerelease"):
        return Release(error="the latest release is a draft or a pre-release")
    for asset in data.get("assets") or []:
        name = asset.get("name") or ""
        url = asset.get("browser_download_url") or ""
        if SETUP_NAME.match(name) and _https_to_github(url):
            return Release(version=version, url=url,
                           page=data.get("html_url"),
                           size=int(asset.get("size") or 0))
    return Release(version=version, page=data.get("html_url"),
                   error="that release carries no installer")


def download(url, folder=None, on_progress=None, stop_flag=None, opener=None):
    """The installer, into a folder of ours. Returns (path, sha256) or raises."""
    if not _https_to_github(url):
        raise ValueError("this address is not a GitHub one: %s" % url)
    opener = opener or urlopen
    folder = folder or tempfile.mkdtemp(prefix="SPIranha-update-")
    path = os.path.join(folder, os.path.basename(url.split("?")[0]))
    digest = hashlib.sha256()
    written = 0
    answer = opener(Request(url, headers={"User-Agent": "SPIranha/%s" % VERSION}),
                    timeout=30)
    with open(path, "wb") as f:
        while True:
            if stop_flag is not None and stop_flag.is_set():
                raise IOError("stopped")
            chunk = answer.read(256 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > MAX_BYTES:
                raise IOError("the file is bigger than %d bytes" % MAX_BYTES)
            f.write(chunk)
            digest.update(chunk)
            if on_progress:
                on_progress(written)
    return path, digest.hexdigest()


def signature(path):
    """(status, thumbprint, subject) as Windows sees them. ('', '', '') if
    the question cannot be asked at all."""
    if os.name != "nt":
        return "", "", ""
    script = (
        "$s = Get-AuthenticodeSignature -LiteralPath '%s'; "
        "Write-Output $s.Status; "
        "Write-Output $s.SignerCertificate.Thumbprint; "
        "Write-Output $s.SignerCertificate.Subject"
    ) % path.replace("'", "''")
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-Command", script],
            stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
    except (OSError, subprocess.CalledProcessError):
        return "", "", ""
    lines = [l.strip() for l in out.decode("utf-8", "replace").splitlines()]
    lines += ["", "", ""]
    return lines[0], lines[1].upper(), lines[2]


def trusted(path, signer=SIGNER):
    """Is this OUR installer? (yes/no, what to say about it).

    ⚠️ 'Valid' on its own is not enough. Anybody can buy a certificate and
    sign anything with it; what matters is that this file was signed with
    the key this project signs with.
    """
    status, thumbprint, subject = signature(path)
    if not status:
        return False, "the signature cannot be checked on this system"
    if status != "Valid":
        return False, "signature not valid (%s)" % status
    if thumbprint != signer.upper():
        return False, "signed by somebody else (%s)" % (subject or thumbprint)
    return True, subject or SIGNER_NAME


def install(path):
    """Runs the installer and lets it get on with it. (started, reason)."""
    ok, why = trusted(path)
    if not ok:
        return False, why
    try:
        subprocess.Popen([path], close_fds=True)
    except OSError as e:
        return False, "%s" % e
    return True, ""
