# Authenticode-sign the built executables.
#
#   .\sign.ps1                        sign dist\*.exe with the MTSistemi cert
#   .\sign.ps1 -Thumbprint <hash>     pick a specific certificate
#   .\sign.ps1 -Pfx C:\path\cert.pfx  use a PFX file
#   .\sign.ps1 -List                  show the available signing certificates
#   .\sign.ps1 -SelfSigned            create a self-signed MTSistemi certificate
#
# The Windows SDK is NOT required: Set-AuthenticodeSignature ships with
# PowerShell.
#
# NOTE: if the certificate lives in a password-protected .pfx, PowerShell asks
# for the password itself. Do not put it in this file and do not pass it on the
# command line.

[CmdletBinding()]
param(
    [string]   $Thumbprint,
    [string]   $Subject = "MTSistemi",
    [string]   $Pfx,
    [string[]] $Path,
    [string]   $TimestampServer = "http://timestamp.sectigo.com",
    [switch]   $List,
    [switch]   $SelfSigned
)

$ErrorActionPreference = "Stop"
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path

function Get-SigningCertificates {
    Get-ChildItem Cert:\CurrentUser\My, Cert:\LocalMachine\My -CodeSigningCert `
        -ErrorAction SilentlyContinue | Where-Object { $_.HasPrivateKey }
}

if ($List) {
    $found = Get-SigningCertificates
    if (-not $found) {
        Write-Host "No signing certificate with a private key." -ForegroundColor Yellow
        Write-Host "Create a self-signed one with:  .\sign.ps1 -SelfSigned"
        exit 1
    }
    $found | Select-Object Subject, NotAfter, Thumbprint, PSParentPath | Format-List
    exit 0
}

if ($SelfSigned) {
    # NOTE: a self-signed certificate does NOT remove the SmartScreen warning on
    # other people's machines. It only counts where that certificate has been
    # explicitly trusted. For public distribution you need an OV/EV certificate
    # from a CA.
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject "CN=MTSistemi, O=MTSistemi, C=IT" `
        -FriendlyName "MTSistemi - application signing" `
        -CertStoreLocation Cert:\CurrentUser\My `
        -KeyAlgorithm RSA -KeyLength 3072 -HashAlgorithm SHA256 `
        -KeyUsage DigitalSignature `
        -NotAfter (Get-Date).AddYears(5)
    Write-Host "Created: $($cert.Subject)" -ForegroundColor Green
    Write-Host "Thumbprint: $($cert.Thumbprint)"
    $public = Join-Path $HERE "MTSistemi.cer"
    Export-Certificate -Cert $cert -FilePath $public -Type CERT | Out-Null
    Write-Host "Public half exported to $public"
    Write-Host ""
    Write-Host "To have a machine trust it, as administrator:" -ForegroundColor Yellow
    Write-Host "  .\trust-certificate.ps1"
    exit 0
}

# --- which certificate ------------------------------------------------------
if ($Pfx) {
    if (-not (Test-Path $Pfx)) { throw "cannot find $Pfx" }
    # PowerShell prompts for the password itself, if there is one
    $cert = Get-PfxCertificate -FilePath $Pfx
} elseif ($Thumbprint) {
    $cert = Get-SigningCertificates | Where-Object { $_.Thumbprint -eq $Thumbprint } |
            Select-Object -First 1
    if (-not $cert) { throw "no certificate with thumbprint $Thumbprint" }
} else {
    $cert = Get-SigningCertificates | Where-Object { $_.Subject -like "*$Subject*" } |
            Sort-Object NotAfter -Descending | Select-Object -First 1
    if (-not $cert) {
        throw "no signing certificate for '$Subject'. Try -List, or -SelfSigned."
    }
}

# --- which files ------------------------------------------------------------
if (-not $Path) {
    $Path = Get-ChildItem (Join-Path $HERE "dist") -Filter *.exe -ErrorAction SilentlyContinue |
            ForEach-Object { $_.FullName }
}
if (-not $Path) { throw "nothing to sign in dist\" }

Write-Host "Certificate: $($cert.Subject)" -ForegroundColor Cyan
Write-Host "Thumbprint : $($cert.Thumbprint)"
Write-Host "Timestamp  : $TimestampServer"
Write-Host ""

$problems = 0
foreach ($f in $Path) {
    $name = Split-Path -Leaf $f
    try {
        Set-AuthenticodeSignature -FilePath $f -Certificate $cert `
            -HashAlgorithm SHA256 -TimestampServer $TimestampServer `
            -IncludeChain All -ErrorAction Stop | Out-Null
    } catch {
        # without network the timestamp fails: sign anyway, but then the
        # signature expires with the certificate instead of outliving it
        Write-Host "  ${name}: timestamping failed, signing without" -ForegroundColor Yellow
        Set-AuthenticodeSignature -FilePath $f -Certificate $cert `
            -HashAlgorithm SHA256 -IncludeChain All | Out-Null
    }
    $state = Get-AuthenticodeSignature -FilePath $f
    $colour = if ($state.Status -eq "Valid") { "Green" } else { "Yellow" }
    Write-Host ("  {0,-42} {1}" -f $name, $state.Status) -ForegroundColor $colour
    if ($state.Status -ne "Valid") { $problems++ }
}

if ($problems) {
    Write-Host ""
    Write-Host "Signed, but not validated on this machine." -ForegroundColor Yellow
    Write-Host "That is normal for a self-signed certificate that has not been" -ForegroundColor Yellow
    Write-Host "trusted here: the signature is there, the chain is not." -ForegroundColor Yellow
}
