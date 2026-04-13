; Inno Setup script for Audio Processor + Transcription Studio
; Build with: "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
; Or via: python build.py both --installer

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{B8F3A2E1-4C6D-4F8A-9E2B-1A3C5D7E9F0B}
AppName=Audio Processor Suite
AppVersion={#AppVersion}
AppPublisher=Tim Litwiller
DefaultDirName={autopf}\AudioProcessor
DefaultGroupName=Audio Processor
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=AudioProcessor-Setup-v{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayName=Audio Processor Suite

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcuts"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "dist\AudioProcessor\*"; DestDir: "{app}\AudioProcessor"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "dist\TranscriptionStudio\*"; DestDir: "{app}\TranscriptionStudio"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Audio Processor"; Filename: "{app}\AudioProcessor\AudioProcessor.exe"
Name: "{group}\Transcription Studio"; Filename: "{app}\TranscriptionStudio\TranscriptionStudio.exe"
Name: "{group}\Uninstall Audio Processor Suite"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Audio Processor"; Filename: "{app}\AudioProcessor\AudioProcessor.exe"; Tasks: desktopicon
Name: "{autodesktop}\Transcription Studio"; Filename: "{app}\TranscriptionStudio\TranscriptionStudio.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AudioProcessor\AudioProcessor.exe"; Description: "Launch Audio Processor"; Flags: nowait postinstall skipifsilent unchecked
