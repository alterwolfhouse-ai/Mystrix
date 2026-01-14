#define AppName "Mystrix"
#define AppVersion "1.0.0"

#ifndef StagingDir
  #define StagingDir "..\\build\\installer\\app"
#endif
#ifndef OutputDir
  #define OutputDir "..\\build\\installer\\output"
#endif

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Mystrix
DefaultGroupName=Mystrix
OutputDir={#OutputDir}
OutputBaseFilename=MystrixSetup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Files]
Source: "{#StagingDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Mystrix (Start)"; Filename: "{app}\MystrixStart.cmd"
Name: "{group}\Mystrix (Stop)"; Filename: "{app}\MystrixStop.cmd"
Name: "{group}\Mystrix Live Console"; Filename: "http://127.0.0.1:8000/static/live_mystrix+.html"

[Run]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\scripts\register_autostart.ps1"""; Flags: runhidden

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\scripts\unregister_autostart.ps1"""; Flags: runhidden
