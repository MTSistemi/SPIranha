; Installer for SPIranha — BC-250
; Build it with:  python build.py --setup
; Inno Setup script for SPIranha.

#define AppTitle "SPIranha"
; ⚠️ The version is NOT written here: build.py generates it into
; build/version.iss, because with two numbers to keep in step the installer
; already came out once with the old version -- and therefore unsigned,
; because build.py was looking for a file under the other name.
#include "build/version.iss"
#define Publisher "MTSistemi"
#define Executable "SPIranha.exe"

[Setup]
AppId={{5F2A9C10-7E44-4B8D-9A31-5350495241484E}
AppName={#AppTitle}
AppVersion={#Version}
AppPublisher={#Publisher}
AppCopyright=© 2026 Mattia Tadini — GPL-2.0
DefaultDirName={autopf}\SPIranha
DefaultGroupName={#AppTitle}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=SPIranha-Setup-{#Version}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=SPIranha.ico
UninstallDisplayIcon={app}\{#Executable}
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
it.CreateIcon=Crea un collegamento sul desktop
en.CreateIcon=Create a desktop shortcut
it.FlashromMissing=flashrom.exe non è incluso. Mettilo nella cartella "flashrom" dentro il programma, oppure indicalo alla prima apertura.
en.FlashromMissing=flashrom.exe is not bundled. Put it in the "flashrom" folder inside the program, or point to it on first run.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#Executable}"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "docs\it\README.md"; DestDir: "{app}\docs\it"; Flags: ignoreversion
; flashrom and the programmer firmware, if they were put next to the project
Source: "flashrom\*"; DestDir: "{app}\flashrom"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist
Source: "firmware\*"; DestDir: "{app}\firmware"; Flags: ignoreversion recursesubdirs skipifsourcedoesntexist

[Icons]
Name: "{group}\{#AppTitle}"; Filename: "{app}\{#Executable}"
Name: "{autodesktop}\{#AppTitle}"; Filename: "{app}\{#Executable}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#Executable}"; Description: "{cm:LaunchProgram,{#AppTitle}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    if not FileExists(ExpandConstant('{app}\flashrom\flashrom.exe')) then
      MsgBox(ExpandConstant('{cm:FlashromMissing}'), mbInformation, MB_OK);
end;
