; =============================================================================
; CertificateManager.iss - Inno Setup script for the client laptops
; Build: scripts\build_release.bat (passes /DAppVersion=<APP_VERSION from app_version.py>)
; Installs per user, no admin rights: program in %LOCALAPPDATA%\Programs\CertificateManager,
; data in %LOCALAPPDATA%\CertificateManager (the program fills it on first start).
; Command line (tests, silent installs):
;   /OldDir=<folder>   import server_config.json, certs\ and the old local_cache.db from <folder>
;   /DataDir=<folder>  use another data folder (tests only)
; =============================================================================

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Certificate Manager"
#define AppExe "CertificateManager.exe"

[Setup]
AppId={{770A9D8E-3159-48F2-B3E4-39B642A4FC6B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Certificate Manager
DefaultDirName={localappdata}\Programs\CertificateManager
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist\release
OutputBaseFilename=CertificateManager-Setup-{#AppVersion}
SetupIconFile=..\..\assets\app.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\..\dist\CertificateManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  ModePage: TInputOptionWizardPage;
  ImportPage: TInputDirWizardPage;
  AddressPage: TInputQueryWizardPage;

function DataDir: String;
begin
  Result := ExpandConstant('{param:DataDir|}');
  if Result = '' then
    Result := ExpandConstant('{localappdata}\CertificateManager');
end;

function HasWebView2: Boolean;
var
  Version: String;
begin
  Result := False;
  if RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) then
    Result := (Version <> '') and (Version <> '0.0.0.0');
  if (not Result) and RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) then
    Result := (Version <> '') and (Version <> '0.0.0.0');
end;

procedure InitializeWizard;
var
  OldDir: String;
begin
  ModePage := CreateInputOptionPage(wpSelectDir, 'Server connection',
    'How should this laptop find the Certificate Manager server?',
    'Importing is best: the client_package folder (from the server) or the old program folder brings the server address, the program key and the college certificate.',
    True, False);
  ModePage.Add('Import settings from a folder (client_package, or the old program folder)');
  ModePage.Add('Type the server address (no program key: only while the server is in audit mode)');
  ModePage.Add('Keep the settings already on this laptop');
  if FileExists(AddBackslash(DataDir) + 'server_config.json') then
    ModePage.SelectedValueIndex := 2
  else
    ModePage.SelectedValueIndex := 0;

  ImportPage := CreateInputDirPage(ModePage.ID, 'Import settings',
    'Choose the folder that contains server_config.json',
    'For example the client_package folder copied from the server, or the old C:\CertificateManager folder.',
    False, '');
  ImportPage.Add('');

  AddressPage := CreateInputQueryPage(ImportPage.ID, 'Server address',
    'Type the address of the server laptop', 'Ask the server administrator for these values.');
  AddressPage.Add('Server IP or name (example: 192.168.1.20):', False);
  AddressPage.Add('Port:', False);
  AddressPage.Add('Scheme (http or https):', False);
  AddressPage.Values[1] := '2030';
  AddressPage.Values[2] := 'https';

  OldDir := ExpandConstant('{param:OldDir|}');
  if OldDir <> '' then
  begin
    ModePage.SelectedValueIndex := 0;
    ImportPage.Values[0] := OldDir;
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if PageID = ImportPage.ID then
    Result := ModePage.SelectedValueIndex <> 0
  else if PageID = AddressPage.ID then
    Result := ModePage.SelectedValueIndex <> 1;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Port: Integer;
  Scheme: String;
begin
  Result := True;
  if CurPageID = wpWelcome then
  begin
    if not HasWebView2 then
      MsgBox('Microsoft Edge WebView2 Runtime was not found. Certificate Manager needs it to show its window.' + #13#10 +
             'Install the WebView2 "Evergreen Bootstrapper" from Microsoft before starting the program.', mbInformation, MB_OK);
    if not RegKeyExists(HKCR, 'Word.Application') then
      MsgBox('Microsoft Word was not found. Certificates can still be created as .docx files, but preview, PDF and printing need Word.', mbInformation, MB_OK);
  end
  else if CurPageID = ImportPage.ID then
  begin
    if not FileExists(AddBackslash(ImportPage.Values[0]) + 'server_config.json') then
    begin
      MsgBox('server_config.json was not found in that folder.', mbError, MB_OK);
      Result := False;
    end;
  end
  else if CurPageID = AddressPage.ID then
  begin
    Port := StrToIntDef(Trim(AddressPage.Values[1]), 0);
    Scheme := LowerCase(Trim(AddressPage.Values[2]));
    if (Trim(AddressPage.Values[0]) = '') or (Port <= 0) or (Port > 65535) or ((Scheme <> 'http') and (Scheme <> 'https')) then
    begin
      MsgBox('Fill in the server address, a port number and http or https.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CopyIfExists(const Source, Target: String; Overwrite: Boolean);
begin
  if FileExists(Source) and (Overwrite or not FileExists(Target)) then
  begin
    ForceDirectories(ExtractFileDir(Target));
    FileCopy(Source, Target, False);
  end;
end;

procedure ImportFrom(const Folder: String);
var
  Dir, Data: String;
begin
  Dir := AddBackslash(Folder);
  Data := AddBackslash(DataDir);
  CopyIfExists(Dir + 'server_config.json', Data + 'server_config.json', True);
  CopyIfExists(Dir + 'certs\college_ca.crt', Data + 'certs\college_ca.crt', True);
  // Offline edits of an old portable install: copied once, never overwritten.
  CopyIfExists(Dir + '_internal\local_cache.db', Data + 'local_cache.db', False);
  CopyIfExists(Dir + 'local_cache.db', Data + 'local_cache.db', False);
end;

procedure WriteServerConfig;
var
  Json: String;
begin
  Json := '{' + #13#10 +
    '  "host": "' + Trim(AddressPage.Values[0]) + '",' + #13#10 +
    '  "port": ' + Trim(AddressPage.Values[1]) + ',' + #13#10 +
    '  "scheme": "' + LowerCase(Trim(AddressPage.Values[2])) + '",' + #13#10 +
    '  "timeout": 5.0,' + #13#10 +
    '  "auto_sync": true,' + #13#10 +
    '  "app_key": "",' + #13#10 +
    '  "ca_cert": "certs/college_ca.crt"' + #13#10 +
    '}' + #13#10;
  ForceDirectories(DataDir);
  SaveStringToFile(AddBackslash(DataDir) + 'server_config.json', Json, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    ForceDirectories(DataDir);
    if (ModePage.SelectedValueIndex = 0) and (ImportPage.Values[0] <> '') then
      ImportFrom(ImportPage.Values[0])
    else if ModePage.SelectedValueIndex = 1 then
      WriteServerConfig;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Data: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Data := ExpandConstant('{localappdata}\CertificateManager');
    if DirExists(Data) and (not UninstallSilent) then
      if MsgBox('Also delete the Certificate Manager data on this laptop?' + #13#10 + Data + #13#10 + #13#10 +
                'This removes the offline cache (including edits not yet synced) and the generated certificates.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(Data, True, True, True);
  end;
end;
