# Dichiara affidabile il certificato MTSistemi su QUESTA macchina.
#
#   .\fidati-del-certificato.ps1            importa
#   .\fidati-del-certificato.ps1 -Rimuovi   toglie
#   .\fidati-del-certificato.ps1 -Verifica  dice solo com'e' messa
#
# ⚠️ VA ESEGUITO COME AMMINISTRATORE: tocca i depositi della macchina, non
# quelli dell'utente.
#
# ⚠️ COSA COMPORTA, in chiaro. Il certificato finisce in due posti:
#   Root             = diventa una RADICE ATTENDIBILE. Da quel momento questa
#                      macchina si fida di QUALUNQUE cosa firmata con quella
#                      chiave privata, non solo del Programmatore BIOS.
#   TrustedPublisher = l'editore e' riconosciuto, quindi niente avvisi.
# La chiave privata sta nel profilo del PC su cui e' stata creata. Chi entra in
# possesso di quella chiave puo' firmare software che le macchine con questo
# certificato importato accetteranno senza avvisi. Va custodita di conseguenza,
# e se si sospetta che sia uscita, il certificato va rimosso da tutte le
# macchine (-Rimuovi) e rifatto.

[CmdletBinding()]
param(
    [string] $Certificato,
    [string] $ImprontaAttesa = "09D323E0775E2E66942A3DF3832CC5294363345F",
    [switch] $Rimuovi,
    [switch] $Verifica
)

$ErrorActionPreference = "Stop"
$DEPOSITI = @("Root", "TrustedPublisher")
# ⚠️ $PSScriptRoot non e' ancora popolato quando PowerShell valuta i valori
# predefiniti dei parametri: la cartella si risolve qui, nel corpo.
$QUI = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $Certificato) { $Certificato = Join-Path $QUI "MTSistemi.cer" }

function Amministratore {
    $identita = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal $identita).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Stato($impronta) {
    foreach ($deposito in $DEPOSITI) {
        $trovato = Get-ChildItem "Cert:\LocalMachine\$deposito" -ErrorAction SilentlyContinue |
                   Where-Object { $_.Thumbprint -eq $impronta }
        "{0,-18} {1}" -f $deposito, $(if ($trovato) { "presente" } else { "assente" })
    }
}

if (-not (Test-Path $Certificato)) { throw "non trovo $Certificato" }
$cer = New-Object Security.Cryptography.X509Certificates.X509Certificate2 $Certificato

Write-Host "Certificato: $($cer.Subject)"
Write-Host "Impronta   : $($cer.Thumbprint)"
Write-Host "Scade      : $($cer.NotAfter)"
Write-Host ""

# ⚠️ Si controlla l'impronta PRIMA di importare: importare per sbaglio il
# certificato sbagliato fra le radici attendibili e' esattamente il genere di
# errore che non si vuole fare.
if ($ImprontaAttesa -and $cer.Thumbprint -ne $ImprontaAttesa) {
    throw ("l'impronta non corrisponde a quella attesa ({0}). " -f $ImprontaAttesa) +
          "Se il certificato e' stato rifatto, passare -ImprontaAttesa con quella nuova."
}

if ($Verifica) {
    Stato $cer.Thumbprint
    exit 0
}

if (-not (Amministratore)) {
    Write-Host "Serve una finestra di PowerShell come amministratore." -ForegroundColor Yellow
    Write-Host "Tasto destro su PowerShell -> Esegui come amministratore, poi:"
    Write-Host "  cd '$QUI'"
    Write-Host "  .\fidati-del-certificato.ps1$(if ($Rimuovi) { ' -Rimuovi' })"
    exit 1
}

foreach ($deposito in $DEPOSITI) {
    if ($Rimuovi) {
        Get-ChildItem "Cert:\LocalMachine\$deposito" |
            Where-Object { $_.Thumbprint -eq $cer.Thumbprint } |
            ForEach-Object {
                Remove-Item $_.PSPath -Force
                Write-Host "tolto da $deposito" -ForegroundColor Yellow
            }
    } else {
        Import-Certificate -FilePath $Certificato `
            -CertStoreLocation "Cert:\LocalMachine\$deposito" | Out-Null
        Write-Host "importato in $deposito" -ForegroundColor Green
    }
}

Write-Host ""
Stato $cer.Thumbprint

# prova sul campo: adesso la firma dovrebbe risultare valida
$exe = Join-Path $QUI "dist\SPIranha.exe"
if (Test-Path $exe) {
    $s = Get-AuthenticodeSignature $exe
    Write-Host ""
    Write-Host ("firma di SPIranha.exe: {0}" -f $s.Status) -ForegroundColor $(
        if ($s.Status -eq "Valid") { "Green" } else { "Yellow" })
}
