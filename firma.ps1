# Firma gli eseguibili come MTSistemi.
#
#   .\firma.ps1                          firma dist\*.exe col certificato MTSistemi
#   .\firma.ps1 -Impronta <thumbprint>   sceglie un certificato preciso
#   .\firma.ps1 -Pfx C:\percorso\cert.pfx
#   .\firma.ps1 -Elenca                  mostra i certificati di firma disponibili
#   .\firma.ps1 -CreaAutofirmato         crea un certificato MTSistemi autofirmato
#
# NON serve il Windows SDK: Set-AuthenticodeSignature e' dentro PowerShell.
#
# ATTENZIONE: se il certificato sta in un .pfx protetto da password, la password
# la chiede PowerShell direttamente a chi lancia lo script. Non va scritta qui
# dentro e non va passata sulla riga di comando.

[CmdletBinding()]
param(
    [string]   $Impronta,
    [string]   $Soggetto = "MTSistemi",
    [string]   $Pfx,
    [string[]] $File,
    [string]   $MarcaTemporale = "http://timestamp.sectigo.com",
    [switch]   $Elenca,
    [switch]   $CreaAutofirmato
)

$ErrorActionPreference = "Stop"
$QUI = Split-Path -Parent $MyInvocation.MyCommand.Path

function Certificati {
    Get-ChildItem Cert:\CurrentUser\My, Cert:\LocalMachine\My -CodeSigningCert `
        -ErrorAction SilentlyContinue | Where-Object { $_.HasPrivateKey }
}

if ($Elenca) {
    $trovati = Certificati
    if (-not $trovati) {
        Write-Host "Nessun certificato di firma con chiave privata." -ForegroundColor Yellow
        Write-Host "Crearne uno autofirmato con:  .\firma.ps1 -CreaAutofirmato"
        exit 1
    }
    $trovati | Select-Object Subject, NotAfter, Thumbprint, PSParentPath | Format-List
    exit 0
}

if ($CreaAutofirmato) {
    # ⚠️ Un certificato AUTOFIRMATO non toglie l'avviso di SmartScreen sulle
    # macchine altrui: vale solo dove quel certificato e' stato dichiarato
    # affidabile. Per il pubblico serve un certificato OV/EV di una CA.
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject "CN=MTSistemi, O=MTSistemi, C=IT" `
        -FriendlyName "MTSistemi - firma applicativi" `
        -CertStoreLocation Cert:\CurrentUser\My `
        -KeyAlgorithm RSA -KeyLength 3072 -HashAlgorithm SHA256 `
        -KeyUsage DigitalSignature `
        -NotAfter (Get-Date).AddYears(5)
    Write-Host "Creato: $($cert.Subject)" -ForegroundColor Green
    Write-Host "Impronta: $($cert.Thumbprint)"
    $pubblico = Join-Path $QUI "MTSistemi.cer"
    Export-Certificate -Cert $cert -FilePath $pubblico -Type CERT | Out-Null
    Write-Host "Parte pubblica esportata in $pubblico"
    Write-Host ""
    Write-Host "Per farlo riconoscere su una macchina (da amministratore):" -ForegroundColor Yellow
    Write-Host "  Import-Certificate -FilePath MTSistemi.cer -CertStoreLocation Cert:\LocalMachine\Root"
    Write-Host "  Import-Certificate -FilePath MTSistemi.cer -CertStoreLocation Cert:\LocalMachine\TrustedPublisher"
    exit 0
}

# --- quale certificato ------------------------------------------------------
if ($Pfx) {
    if (-not (Test-Path $Pfx)) { throw "non trovo $Pfx" }
    # PowerShell chiede lui la password, se serve
    $cert = Get-PfxCertificate -FilePath $Pfx
} elseif ($Impronta) {
    $cert = Certificati | Where-Object { $_.Thumbprint -eq $Impronta } | Select-Object -First 1
    if (-not $cert) { throw "nessun certificato con impronta $Impronta" }
} else {
    $cert = Certificati | Where-Object { $_.Subject -like "*$Soggetto*" } |
            Sort-Object NotAfter -Descending | Select-Object -First 1
    if (-not $cert) {
        throw "nessun certificato di firma per «$Soggetto». Usare -Elenca, oppure -CreaAutofirmato."
    }
}

# --- quali file -------------------------------------------------------------
if (-not $File) {
    $File = Get-ChildItem (Join-Path $QUI "dist") -Filter *.exe -ErrorAction SilentlyContinue |
            ForEach-Object { $_.FullName }
}
if (-not $File) { throw "nessun file da firmare in dist\" }

Write-Host "Certificato: $($cert.Subject)" -ForegroundColor Cyan
Write-Host "Impronta   : $($cert.Thumbprint)"
Write-Host "Marca ora  : $MarcaTemporale"
Write-Host ""

$problemi = 0
foreach ($f in $File) {
    $nome = Split-Path -Leaf $f
    try {
        $esito = Set-AuthenticodeSignature -FilePath $f -Certificate $cert `
                    -HashAlgorithm SHA256 -TimestampServer $MarcaTemporale `
                    -IncludeChain All -ErrorAction Stop
    } catch {
        # senza rete la marca temporale fallisce: si firma comunque, ma la
        # firma scade con il certificato invece di restare valida
        Write-Host "  $nome : marca temporale non riuscita, firmo senza" -ForegroundColor Yellow
        $esito = Set-AuthenticodeSignature -FilePath $f -Certificate $cert `
                    -HashAlgorithm SHA256 -IncludeChain All
    }
    $stato = (Get-AuthenticodeSignature -FilePath $f)
    $colore = if ($stato.Status -eq "Valid") { "Green" } else { "Yellow" }
    Write-Host ("  {0,-42} {1}" -f $nome, $stato.Status) -ForegroundColor $colore
    if ($stato.Status -ne "Valid") { $problemi++ }
}

if ($problemi) {
    Write-Host ""
    Write-Host "Firma apposta, ma non convalidata su questa macchina." -ForegroundColor Yellow
    Write-Host "E' normale con un certificato autofirmato che non e' stato" -ForegroundColor Yellow
    Write-Host "dichiarato affidabile: la firma c'e', la catena no." -ForegroundColor Yellow
}
