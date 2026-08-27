; Installatore per Programmatore BIOS — BC-250
; Si costruisce con:  python costruisci.py --setup
; Installer for the BIOS Programmer tool. Build with: python costruisci.py --setup

#define Nome "SPIranha"
#define Versione "1.1.0"
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
SetupIconFile=programmatore.ico
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
Source: "LEGGIMI.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
; flashrom, se e' stato messo accanto al progetto, viene portato dentro.
Source: "flashrom\*"; DestDir: "{app}\flashrom"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist

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
