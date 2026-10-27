# Phase 6 — Client build and installer (Haiku runbook)

Goal:
- a PyInstaller build that never ships the build PC's `server_config.json`, and that ships the logos;
- an Inno Setup `setup.exe` that installs per user, with no admin rights needed;
- one command that builds a full release.

Read `00-README.md` first. Follow its rules exactly. Run this after Phase 2.

## Before you start

````powershell run skip-validate
git branch --show-current
git status --porcelain | Where-Object { $_ -notmatch '^.. "?(logs/|certificates/|\.nicegui/)' }
py -3 -m pytest
````
Expected: `62 passed, 1 deselected`. The first line must be `refactor/install-ready`, and no `git status` lines may be printed. Otherwise STOP.

## Step 6.1 — Write `client.spec` (Read it first; replace the whole file)

````python file=client.spec
# -*- mode: python ; coding: utf-8 -*-
# =============================================================================
# client.spec — PyInstaller specification for the Certificate Manager client
# Build: scripts\build_client.bat (or scripts\build_release.bat for a full release).
# Never bundle server_config.json: every laptop gets its own (installer / data folder).
# =============================================================================

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect full dependency assets for NiceGUI and PyWebView
nicegui_datas, nicegui_binaries, nicegui_hiddenimports = collect_all('nicegui')
webview_datas, webview_binaries, webview_hiddenimports = collect_all('webview')

# Read-only program resources. On first start app_paths.prepare_data_dir() copies the
# seed files (templets, assets, data/*.json, certs) into %LOCALAPPDATA%\CertificateManager.
app_datas = [
    ('templets', 'templets'),
    ('assets', 'assets'),
    ('nicegui_ui', 'nicegui_ui'),
    ('data/roles_config.json', 'data'),
    ('data/user_roles.json', 'data'),
    ('server_config.example.json', '.'),
    ('certs/college_ca.crt', 'certs'),
    ('scripts/apply_patch.bat', 'scripts'),
]

datas = nicegui_datas + webview_datas + app_datas
binaries = nicegui_binaries + webview_binaries

hiddenimports = (
    nicegui_hiddenimports
    + webview_hiddenimports
    + [
        'app_paths',
        'app_version',
        'services.updater',
        'services.template_sync',
        'services.excel_import_service',
        'nicegui_screens.login_screen',
        'nicegui_screens.dashboard_screen',
        'nicegui_screens.settings_screen',
        'nicegui_screens.student_bulk_import_view',
        'nicegui_ui.ui_components',
        'nicegui_ui.ui_theme',
        'nicegui_ui.state',
        'sync_engine',
        'data.repositories',
        'api_config',
        'utils.health_check',
        'utils.logger',
        'docx',
        'docxtpl',
        'openpyxl',
        'psutil',
        'requests',
        'sqlite3',
    ]
)

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CertificateManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CertificateManager'
)
````

## Step 6.2 — Make the program icon `assets/app.ico` from the logo

````powershell run
py -3 -c "from PIL import Image; Image.open('assets/csit.png').convert('RGBA').save('assets/app.ico', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])"
Test-Path assets/app.ico
````
Expected: `True`

## Step 6.3 — Write `scripts/build_client.bat` (Read it first; replace the whole file)

````bat file=scripts/build_client.bat
@echo off
setlocal

:: =============================================================================
:: scripts/build_client.bat - build the client program folder dist\CertificateManager
:: Usage: build_client.bat             (waits for a key at the end)
::        build_client.bat /nopause    (used by scripts\build_release.bat)
:: =============================================================================

set "NOPAUSE="
if /i "%~1"=="/nopause" set "NOPAUSE=1"

cd /d "%~dp0.."

echo [1/4] Checking Python...
py -3 -V
if errorlevel 1 (
    echo [ERROR] The Python launcher py was not found. Install Python 3.14 for all users.
    if not defined NOPAUSE pause
    exit /b 1
)

echo [2/4] Cleaning previous build output...
if exist "dist\CertificateManager" rmdir /s /q "dist\CertificateManager"
if exist "build\CertificateManager" rmdir /s /q "build\CertificateManager"

echo [3/4] Running PyInstaller...
py -3 -m PyInstaller --noconfirm --log-level WARN client.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller failed. See the messages above.
    if not defined NOPAUSE pause
    exit /b 1
)

echo [4/4] Checking the output...
if not exist "dist\CertificateManager\CertificateManager.exe" (
    echo [ERROR] dist\CertificateManager\CertificateManager.exe was not created.
    if not defined NOPAUSE pause
    exit /b 1
)
echo BUILD SUCCESSFUL: %CD%\dist\CertificateManager\CertificateManager.exe
if not defined NOPAUSE pause
exit /b 0
````

## Step 6.4 — Write `tests/test_client_spec.py` (new file)

````python file=tests/test_client_spec.py
"""client.spec must ship the seed resources and the icon, and never a real server_config.json."""
import app_paths
from tests.helpers import PROJECT_ROOT

SPEC = (PROJECT_ROOT / "client.spec").read_text(encoding="utf-8")


def test_spec_never_bundles_a_real_server_config():
    assert "('server_config.json'" not in SPEC
    assert "('server_config.example.json', '.')" in SPEC


def test_spec_bundles_icon_and_update_script():
    assert "icon='assets/app.ico'" in SPEC
    assert (PROJECT_ROOT / "assets" / "app.ico").is_file()
    assert "('scripts/apply_patch.bat', 'scripts')" in SPEC


def test_every_seed_item_is_bundled():
    for item in app_paths.SEED_ITEMS:
        folder = item.split("/")[0]
        assert f"('{item}'" in SPEC or f"('{folder}', '{folder}')" in SPEC, item
````

````powershell run
py -3 -m pytest
````
Expected: `65 passed, 1 deselected`

## Step 6.5 — Commit

````powershell run
git add -- client.spec assets/app.ico scripts/build_client.bat tests/test_client_spec.py
git commit -q -m "build: client.spec ships assets and the example config, never the build PC's config"
git log --oneline -1
````
Expected: `build: client.spec ships assets`

## Step 6.6 — Build the program folder (takes 2–6 minutes)

````powershell run
cmd.exe /c "scripts\build_client.bat /nopause"
Test-Path dist\CertificateManager\_internal\server_config.json
Test-Path dist\CertificateManager\_internal\server_config.example.json
Test-Path dist\CertificateManager\_internal\assets\csit.png
````
Expected: `BUILD SUCCESSFUL`. The three `Test-Path` lines must print `False`, `True`, `True`, in that order.

## Step 6.7 — Start the built program once with a throw-away data folder

A Certificate Manager window opens for about 30 seconds and is then closed by the command.
The command refuses to run if port 2323 is already in use; in that case ask the user to
close Certificate Manager, then run this step again.

````powershell run
if (Get-NetTCPConnection -LocalPort 2323 -State Listen -ErrorAction SilentlyContinue) { "PORT 2323 IS BUSY"; exit 1 }
$data = Join-Path $env:TEMP "cm-frozen-check"
if (Test-Path $data) { Remove-Item -Recurse -Force $data }
$env:CERTMAN_DATA_DIR = $data
Start-Process -FilePath "dist\CertificateManager\CertificateManager.exe" | Out-Null
Start-Sleep -Seconds 30
$listening = [bool](Get-NetTCPConnection -LocalPort 2323 -State Listen -ErrorAction SilentlyContinue)
Get-Process -Name CertificateManager -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item Env:\CERTMAN_DATA_DIR
"server_config: $(Test-Path (Join-Path $data 'server_config.json'))"
"templets: $(Test-Path (Join-Path $data 'templets'))"
"log: $(Test-Path (Join-Path $data 'logs\system_log.txt'))"
"listening on 2323: $listening"
````
Expected: `listening on 2323: True`. All four lines must end in `True`.

## Step 6.8 — Inno Setup must be installed

````powershell run
$candidates = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")
$iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
"ISCC found: $([bool]$iscc)"
````
Expected: `ISCC found: True`. If it prints `ISCC found: False`, show the user the manual step below, wait for "done", then run this step again.

````powershell manual
USER ACTION: install Inno Setup 6 on this (build) laptop, in a normal terminal:
    winget install --id JRSoftware.InnoSetup -e
or download it from https://jrsoftware.org/isdl.php and install with the defaults.
````

## Step 6.9 — Write `installer/client/CertificateManager.iss` (new file)

````iss file=installer/client/CertificateManager.iss
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
````

## Step 6.10 — Write `scripts/build_release.bat` (new file)

````bat file=scripts/build_release.bat
@echo off
setlocal

:: =============================================================================
:: scripts/build_release.bat - one command for a full client release
::   1. tests   2. dist\CertificateManager   3. update ZIP   4. installer   5. SHA256SUMS.txt
:: Output: dist\release\<version>\   (version = APP_VERSION in app_version.py)
:: Needs Inno Setup 6 (ISCC.exe).
:: =============================================================================

cd /d "%~dp0.."

set "VER="
for /f "usebackq delims=" %%v in (`py -3 -c "import app_version; print(app_version.APP_VERSION)"`) do set "VER=%%v"
if not defined VER (
    echo [ERROR] Could not read APP_VERSION from app_version.py
    exit /b 1
)

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo [ERROR] Inno Setup 6 is not installed: ISCC.exe was not found.
    exit /b 1
)

set "OUT=%CD%\dist\release\%VER%"
echo === Release %VER% ===

echo [1/5] Tests...
py -3 -m pytest
if errorlevel 1 (
    echo [ERROR] Tests failed. Nothing was built.
    exit /b 1
)

echo [2/5] Program folder...
call scripts\build_client.bat /nopause
if errorlevel 1 exit /b 1

echo [3/5] Update ZIP...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\make_client_patch.ps1
if errorlevel 1 exit /b 1

echo [4/5] Installer...
if not exist "%OUT%" mkdir "%OUT%"
"%ISCC%" /Q "/DAppVersion=%VER%" "/O%OUT%" installer\client\CertificateManager.iss
if errorlevel 1 (
    echo [ERROR] Inno Setup failed.
    exit /b 1
)

echo [5/5] Checksums...
move /y "dist\patch_v%VER%.zip" "%OUT%\" >nul
powershell.exe -NoProfile -Command "Get-ChildItem -LiteralPath '%OUT%' -File | Where-Object { $_.Name -ne 'SHA256SUMS.txt' } | ForEach-Object { '{0}  {1}' -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Name } | Set-Content -Encoding ascii -LiteralPath '%OUT%\SHA256SUMS.txt'"

echo RELEASE READY: %OUT%
exit /b 0
````

## Step 6.11 — Write `installer/client/test_install.ps1` (new file)

````powershell file=installer/client/test_install.ps1
# =============================================================================
# test_install.ps1 - silent install / reinstall / uninstall test of the client installer.
# Uses folders under %TEMP% only; never touches the real data folder.
# Usage: powershell -ExecutionPolicy Bypass -File installer\client\test_install.ps1 -Setup <path to setup.exe>
# =============================================================================
param([Parameter(Mandatory = $true)][string]$Setup)
$ErrorActionPreference = "Stop"

$arabic = -join ([char[]](0x0628, 0x064A, 0x0627, 0x0646, 0x0627, 0x062A))
$root = Join-Path $env:TEMP "cm_install_test"
if (Test-Path $root) { Remove-Item -Recurse -Force $root }
$app = Join-Path $root "app folder"
$data = Join-Path $root "data $arabic"
$old = Join-Path $root "old portable"
New-Item -ItemType Directory -Force -Path (Join-Path $old "_internal"), (Join-Path $old "certs") | Out-Null
'{"host": "10.0.0.5", "port": 2030, "scheme": "https", "app_key": "k"}' | Set-Content -Encoding ascii -LiteralPath (Join-Path $old "server_config.json")
"CA" | Set-Content -Encoding ascii -LiteralPath (Join-Path $old "certs\college_ca.crt")
"OLD-DB" | Set-Content -Encoding ascii -LiteralPath (Join-Path $old "_internal\local_cache.db")

function Invoke-Setup([string]$From) {
    $arguments = @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=`"$app`"", "/DataDir=`"$data`"", "/OldDir=`"$From`"")
    $process = Start-Process -FilePath $Setup -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "setup exit code $($process.ExitCode)" }
}

$fails = @()
Invoke-Setup $old
if (-not (Test-Path -LiteralPath (Join-Path $app "CertificateManager.exe"))) { $fails += "exe missing after install" }
if ((Get-Content -LiteralPath (Join-Path $data "server_config.json") -Raw) -notmatch "10\.0\.0\.5") { $fails += "server_config.json not imported" }
if (-not (Test-Path -LiteralPath (Join-Path $data "certs\college_ca.crt"))) { $fails += "college_ca.crt not imported" }
if ((Get-Content -LiteralPath (Join-Path $data "local_cache.db") -Raw).Trim() -ne "OLD-DB") { $fails += "local_cache.db not imported" }

"NEW-DB" | Set-Content -Encoding ascii -LiteralPath (Join-Path $old "_internal\local_cache.db")
Invoke-Setup $old
if ((Get-Content -LiteralPath (Join-Path $data "local_cache.db") -Raw).Trim() -ne "OLD-DB") { $fails += "a second install overwrote local_cache.db" }

Start-Process -FilePath (Join-Path $app "unins000.exe") -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") -Wait | Out-Null
for ($i = 0; $i -lt 30 -and (Test-Path -LiteralPath (Join-Path $app "CertificateManager.exe")); $i++) { Start-Sleep -Seconds 1 }
if (Test-Path -LiteralPath (Join-Path $app "CertificateManager.exe")) { $fails += "uninstall left CertificateManager.exe" }
if (-not (Test-Path -LiteralPath (Join-Path $data "local_cache.db"))) { $fails += "uninstall deleted the data folder" }

if ($fails.Count -gt 0) { $fails | ForEach-Object { "FAIL: $_" }; exit 1 }
"ALL CHECKS PASSED"
````

## Step 6.12 — Build the full release (takes 3–8 minutes)

````powershell run
cmd.exe /c "scripts\build_release.bat"
$ver = py -3 -c "import app_version; print(app_version.APP_VERSION)"
Get-ChildItem -Name "dist\release\$ver"
````
Expected: `RELEASE READY`. The listing must show `CertificateManager-Setup-2.1.0.exe`, `patch_v2.1.0.zip` and `SHA256SUMS.txt`.

## Step 6.13 — Test the installer silently

````powershell run
powershell.exe -NoProfile -ExecutionPolicy Bypass -File installer\client\test_install.ps1 -Setup "dist\release\2.1.0\CertificateManager-Setup-2.1.0.exe"
````
Expected: `ALL CHECKS PASSED`

## Step 6.14 — Commit

````powershell run
git add -- installer/client/CertificateManager.iss installer/client/test_install.ps1 scripts/build_release.bat
git commit -q -m "build: Inno Setup installer for client laptops and a one-command release"
git log --oneline -1
git status --porcelain | Where-Object { $_ -notmatch '^.. "?(logs/|certificates/|\.nicegui/)' }
````
Expected: `build: Inno Setup installer for client laptops`. Nothing else may be printed after the log line (`dist/` and `build/` are ignored).

## Step 6.15 — The user checks the installer by hand

````powershell manual
USER CHECK (about 10 minutes, on this laptop):
1. Start the API in a visible window: certificate_manager_api\start_server.bat
2. Double-click dist\release\2.1.0\CertificateManager-Setup-2.1.0.exe
   - It should not ask for admin rights.
   - Server connection page: choose "Import settings from a folder" and pick the project folder
     F:\CR_PY\certificate_manager (it holds this laptop's server_config.json).
3. Start "Certificate Manager" from the Start menu. Log in, open Students, generate one certificate.
4. Check that %LOCALAPPDATA%\CertificateManager now holds logs\, templets\, certificates\, server_config.json.
5. Optional OTA test: raise APP_VERSION in app_version.py to 2.1.1, run scripts\build_release.bat,
   publish dist\release\2.1.1\patch_v2.1.1.zip with certificate_manager_api\publish_client_update.bat
   (as Administrator, on the server). The installed program should offer the update and restart as 2.1.1.
   Afterwards set APP_VERSION back to 2.1.0 (do not commit the test bump).
6. Uninstall from Windows Settings -> Apps. Answer "No" to deleting data.
Tell the executor "checked" or describe what went wrong.
````

## Done

````powershell run
git log --oneline -4
````
Expected: `build: Inno Setup installer for client laptops`
