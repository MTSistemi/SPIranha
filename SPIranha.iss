; Installer for SPIranha — BC-250
; Build it with:  python build.py --setup
; Inno Setup script for SPIranha.

#define Nome "SPIranha"
; ⚠️ La versione NON si scrive qui: la genera build.py in build/versione.iss,
; perche' con due numeri da tenere allineati l'installer e' gia' uscito una
; volta con la versione vecchia -- e quindi senza firma, perche' build.py
; cercava un file con l'altro nome.
#include "build/versione.iss"
#define Editore "MTSistemi"
#define Eseguibile "SPIranha.exe"

[Setup]
AppId={{5F2A9C10-7E44-4B8D-9A31-5350495241484E}
AppName={#Nome}
AppVersion={#Versione}
AppPublisher={#Editore}
DefaultDirName={autopf}\SPIranha
DefaultGroupName={#Nome}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=SPIranha-Setup-{#Versione}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=SPIranha.ico
UninstallDisplayIcon={app}\{#Eseguibile}
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
it.CreaIcona=Crea un collegamento sul desktop
en.CreaIcona=Create a desktop shortcut
it.FlashromMancante=flashrom.exe non è incluso. Mettilo nella cartella "flashrom" dentro il programma, oppure indicalo alla prima apertura.
en.FlashromMancante=flashrom.exe is not bundled. Put it in the "flashrom" folder inside the program, or point to it on first run.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreaIcona}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#Eseguibile}"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "docs\it\LEGGIMI.md"; DestDir: "{app}\docs"; Flags: ignoreversion
; flashrom and the programmer firmware, if they were put next to the project
Source: "flashrom\*"; DestDir: "{app}\flashrom"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "firmware\*"; DestDir: "{app}\firmware"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist

[Icons]
Name: "{group}\{#Nome}"; Filename: "{app}\{#Eseguibile}"
Name: "{autodesktop}\{#Nome}"; Filename: "{app}\{#Eseguibile}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#Eseguibile}"; Description: "{cm:LaunchProgram,{#Nome}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    if not FileExists(ExpandConstant('{app}\flashrom\flashrom.exe')) then
      MsgBox(ExpandConstant('{cm:FlashromMancante}'), mbInformation, MB_OK);
end;
