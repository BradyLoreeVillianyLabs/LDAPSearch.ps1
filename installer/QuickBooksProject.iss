; Inno Setup installer script for QuickBooksProject (Windows 11 Pro)
#define MyAppName "QuickBooksProject"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "QuickBooksProject"
#define MyAppExeName "QuickBooksProject.exe"

[Setup]
AppId={{E8BCE5D3-26D1-4D69-A8A7-734E31ED5E2D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppComments=Self-hosted QuickBooks Desktop ↔ WooCommerce sync utility.
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=dist\installer
OutputBaseFilename=QuickBooksProject-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "dist\app\QuickBooksProject.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} first-run setup"; Flags: nowait postinstall skipifsilent; Parameters: "--first-run"
