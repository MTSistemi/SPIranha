# Make this machine trust the MTSistemi signing certificate.
#
#   .\trust-certificate.ps1           import
#   .\trust-certificate.ps1 -Remove   undo
#   .\trust-certificate.ps1 -Check    report only, change nothing
#
# MUST BE RUN AS ADMINISTRATOR: it touches the machine stores, not the user's.
#
# WHAT THIS ACTUALLY DOES, plainly. The certificate goes into two stores:
#   Root             = it becomes a TRUST ANCHOR. From then on this machine
#                      trusts ANYTHING signed with that private key, not just
#                      SPIranha.
#   TrustedPublisher = the publisher is recognised, so no warnings.
# The private key lives in the user profile of the PC where it was created.
# Whoever gets hold of that key can sign software these machines will accept
# without a word. Guard it accordingly, and if you suspect it leaked, remove the
# certificate everywhere (-Remove) and issue a new one.

[CmdletBinding()]
param(
    [string] $Certificate,
    [string] $ExpectedThumbprint = "09D323E0775E2E66942A3DF3832CC5294363345F",
    [switch] $Remove,
    [switch] $Check
)

$ErrorActionPreference = "Stop"
$STORES = @("Root", "TrustedPublisher")
# NOTE: $PSScriptRoot is not populated yet when PowerShell evaluates parameter
# defaults, so the folder is resolved here, in the body.
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Certificate) { $Certificate = Join-Path $HERE "MTSistemi.cer" }

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal $identity).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Show-State($thumbprint) {
    foreach ($store in $STORES) {
        $found = Get-ChildItem "Cert:\LocalMachine\$store" -ErrorAction SilentlyContinue |
                 Where-Object { $_.Thumbprint -eq $thumbprint }
        "{0,-18} {1}" -f $store, $(if ($found) { "present" } else { "absent" })
    }
}

if (-not (Test-Path $Certificate)) { throw "cannot find $Certificate" }
$cer = New-Object Security.Cryptography.X509Certificates.X509Certificate2 $Certificate

Write-Host "Certificate: $($cer.Subject)"
Write-Host "Thumbprint : $($cer.Thumbprint)"
Write-Host "Expires    : $($cer.NotAfter)"
Write-Host ""

# NOTE: the thumbprint is checked BEFORE importing. Accidentally adding the
# wrong certificate to the trust anchors is exactly the mistake worth avoiding.
if ($ExpectedThumbprint -and $cer.Thumbprint -ne $ExpectedThumbprint) {
    throw ("thumbprint does not match the expected one ({0}). " -f $ExpectedThumbprint) +
          "If the certificate was reissued, pass -ExpectedThumbprint with the new value."
}

if ($Check) {
    Show-State $cer.Thumbprint
    exit 0
}

if (-not (Test-Administrator)) {
    Write-Host "An elevated PowerShell window is required." -ForegroundColor Yellow
    Write-Host "Right-click PowerShell -> Run as administrator, then:"
    Write-Host "  cd '$HERE'"
    Write-Host "  .\trust-certificate.ps1$(if ($Remove) { ' -Remove' })"
    exit 1
}

foreach ($store in $STORES) {
    if ($Remove) {
        Get-ChildItem "Cert:\LocalMachine\$store" |
            Where-Object { $_.Thumbprint -eq $cer.Thumbprint } |
            ForEach-Object {
                Remove-Item $_.PSPath -Force
                Write-Host "removed from $store" -ForegroundColor Yellow
            }
    } else {
        Import-Certificate -FilePath $Certificate `
            -CertStoreLocation "Cert:\LocalMachine\$store" | Out-Null
        Write-Host "imported into $store" -ForegroundColor Green
    }
}

Write-Host ""
Show-State $cer.Thumbprint

# field test: the signature should now come out valid
$exe = Join-Path $HERE "dist\SPIranha.exe"
if (Test-Path $exe) {
    $s = Get-AuthenticodeSignature $exe
    Write-Host ""
    Write-Host ("SPIranha.exe signature: {0}" -f $s.Status) -ForegroundColor $(
        if ($s.Status -eq "Valid") { "Green" } else { "Yellow" })
}
