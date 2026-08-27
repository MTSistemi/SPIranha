# Security policy

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting** (Security → Report a
vulnerability) rather than opening a public issue.

We will acknowledge within a few working days. There is no bounty programme.

## What counts here

This is a desktop tool that drives a flash programmer. The things worth
reporting are the ones that could damage hardware or hand someone a bad image:

- a path that lets a write start without the checks — an unverified read, a
  skipped dry run, a bypassed confirmation;
- the block map, the log or the final verification reporting success when the
  chip does not actually match;
- the image-size guard failing to catch the wrong chip (writing a 512 KB
  SuperIO instead of a 16 MB BIOS bricks fan control on a BC-250);
- anything that causes the tool to write outside the region the user selected.

Also in scope: code execution through a crafted layout file or BIOS image.

## What does not count

- flashrom's own vulnerabilities — please report those to
  [flashrom](https://flashrom.org) directly. We invoke it as a child process
  and do not patch it.
- The unsigned or self-signed state of a build you made yourself.
- Damage caused by connecting the programmer to a powered board. The tool warns
  about it in three places; it cannot prevent it.

## Builds and signatures

Official builds are signed. Verify before running one you did not build:

```powershell
Get-AuthenticodeSignature .\SPIranha.exe | Format-List Status, SignerCertificate
```

A build signed with a self-signed certificate reports `UnknownError` unless that
certificate has been explicitly trusted on the machine — that is expected, not a
failure. `MTSistemi.cer` in this repository is the public half of the
certificate used for internal builds.
