; Inno Setup script: Bitwig Remote desktop app + optional VST3 plug-ins + optional Bitwig controller script.
; Build: python packaging/build_app.py (PyInstaller), then ISCC packaging\BitwigRemote.iss  ->  dist\BitwigRemote-Setup.exe
#define AppVer "8.4.0"
[Setup]
AppId={{6C1B3A52-7D0E-4C0B-9B53-B17F1BE5A001}
AppName=Bitwig Remote
AppVersion={#AppVer}
AppPublisher=S.Simpson
DefaultDirName={autopf}\Bitwig Remote
DefaultGroupName=Bitwig Remote
OutputDir=..\dist
OutputBaseFilename=BitwigRemote-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\bwmcp\monitor\assets\bitwig_remote.ico
UninstallDisplayIcon={app}\Bitwig Remote.exe
LicenseFile=..\LICENSE
[Tasks]
Name: desktopicon; Description: "Desktop shortcut"
[Components]
Name: app; Description: "Bitwig Remote desktop app"; Types: full custom; Flags: fixed
Name: vst; Description: "BW Remote and BW True Peak VST3 plug-ins"; Types: full
Name: script; Description: "Bitwig controller script (Documents\Bitwig Studio\Controller Scripts\BitwigMCP)"; Types: full
[Files]
Source: "..\dist\Bitwig Remote\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion; Components: app
Source: "..\vst\build\BWRemote_artefacts\Release\VST3\BW Remote.vst3\*"; DestDir: "{commoncf64}\VST3\BW Remote.vst3"; Flags: recursesubdirs ignoreversion; Components: vst
Source: "..\vst\build\BWTruePeak_artefacts\Release\VST3\BW True Peak.vst3\*"; DestDir: "{commoncf64}\VST3\BW True Peak.vst3"; Flags: recursesubdirs ignoreversion; Components: vst
Source: "..\bitwig_script\*.js"; DestDir: "{userdocs}\Bitwig Studio\Controller Scripts\BitwigMCP"; Flags: ignoreversion; Components: script
[Icons]
Name: "{group}\Bitwig Remote"; Filename: "{app}\Bitwig Remote.exe"
Name: "{autodesktop}\Bitwig Remote"; Filename: "{app}\Bitwig Remote.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\Bitwig Remote.exe"; Description: "Start Bitwig Remote"; Flags: postinstall nowait skipifsilent
