# Phase 7 — Server bundle and setup script (Haiku runbook)

Goal:
- one folder (plus a zip of it) holding everything the server laptop needs;
- `setup_server.bat`, which does both the first installation and every later update.

It never overwrites the server's own settings:
- `db_config.json`, `app_keys.json`, `server_settings.json`
- `certs\`, `client_package\`
- `templets\`: only files that are missing get added.

On an old server it also creates `db_config.json` from the old `config.py`.

Everything here is tested only against folders under `%TEMP%`. Running it on the real server is
the user's job (Phase 8). **Never run `setup_server.bat` or `setup_server.ps1` against
`C:\AppServ\www\certificate_manager_api` yourself.**

Read `00-README.md` first. Follow its rules exactly. Run this after Phase 6.

## Before you start

````powershell run skip-validate
git branch --show-current
git status --porcelain | Where-Object { $_ -notmatch '^.. "?(logs/|certificates/|\.nicegui/)' }
py -3 -m pytest
````
Expected: `65 passed, 1 deselected`. The first line must be `refactor/install-ready`, and no `git status` lines may be printed. Otherwise STOP.

## Step 7.1 — Write `installer/server/setup_server.bat` (new file)

````bat file=installer/server/setup_server.bat
@echo off
:: =============================================================================
:: setup_server.bat - first installation AND later updates of the API on the server laptop.
:: Double-click it; Windows asks for Administrator rights. Safe to run again.
:: The work is done by setup_server.ps1 in this folder.
:: =============================================================================
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator rights...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_server.ps1" %*
pause
````

## Step 7.2 — Write `installer/server/setup_server.ps1` (new file)

````powershell file=installer/server/setup_server.ps1
# =============================================================================
# setup_server.ps1 - install or update the Certificate Manager API on the server laptop.
# Run it through setup_server.bat (Administrator). Safe to run again. Never overwritten:
#   db_config.json  app_keys.json  server_settings.json  certs\  client_package\  logs\
#   templets\ (only missing files are added)
# Parameters (tests / special cases):
#   -TargetDir <folder>   default C:\AppServ\www\certificate_manager_api
#   -SkipPip -SkipService -SkipFirewall -SkipDbCheck
# =============================================================================
param(
    [string]$TargetDir = "C:\AppServ\www\certificate_manager_api",
    [switch]$SkipPip,
    [switch]$SkipService,
    [switch]$SkipFirewall,
    [switch]$SkipDbCheck
)
$ErrorActionPreference = "Stop"
$bundle = $PSScriptRoot
$serviceName = "FastAPICertificateManager"

function Ok([string]$Message) { Write-Host "[OK] $Message" -ForegroundColor Green }
function Skip([string]$Message) { Write-Host "[SKIP] $Message" -ForegroundColor DarkGray }
function Warn([string]$Message) { Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
function Fail([string]$Message) { Write-Host "[ERROR] $Message" -ForegroundColor Red; exit 1 }

$version = ""
if (Test-Path (Join-Path $bundle "VERSION.txt")) { $version = (Get-Content (Join-Path $bundle "VERSION.txt") -Raw).Trim() }
Write-Host "=== Certificate Manager server setup $version -> $TargetDir ==="

# 1. Administrator rights and Python (the same python.exe install_service.bat will use)
if (-not ($SkipService -and $SkipFirewall)) {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { Fail "Run setup_server.bat: it asks for Administrator rights." }
}
$python = Get-Command python.exe -All -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch "WindowsApps" } | Select-Object -First 1 -ExpandProperty Source
if (-not $python) { $python = (& py -3 -c "import sys; print(sys.executable)" 2>$null) }
if (-not $python) { Fail "Python was not found. Install Python 3.14 (64-bit) for all users, with 'Add python.exe to PATH'." }
$bits = (& $python -c "import struct; print(struct.calcsize('P') * 8)").Trim()
if ($bits -ne "64") { Fail "Python must be 64-bit: $python" }
Ok "Python: $python"

# 2. Python packages (offline wheels first, then the internet)
if ($SkipPip) { Skip "Python packages" } else {
    & $python -m pip install --disable-pip-version-check -q --no-index --find-links (Join-Path $bundle "wheels") -r (Join-Path $bundle "requirements-server.txt")
    if ($LASTEXITCODE -ne 0) {
        Warn "The bundled packages do not fit this Python; trying the internet..."
        & $python -m pip install --disable-pip-version-check -q -r (Join-Path $bundle "requirements-server.txt")
        if ($LASTEXITCODE -ne 0) { Fail "Installing the Python packages failed." }
    }
    & $python -c "import win32serviceutil" 2>$null
    if ($LASTEXITCODE -ne 0) {
        $postInstall = (& $python -c "import os, sys; print(os.path.join(sys.prefix, 'Scripts', 'pywin32_postinstall.py'))").Trim()
        & $python $postInstall -install | Out-Null
    }
    Ok "Python packages"
}

# 3. Back up the current code, stop the service, copy the new code
$isUpdate = Test-Path (Join-Path $TargetDir "main.py")
if ($isUpdate) {
    $backup = Join-Path $TargetDir "_backup_before_update"
    robocopy $TargetDir $backup *.py *.bat *.ps1 *.md /S /XD _backup_before_update certs client_package logs templets __pycache__ /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { Fail "Backup failed (robocopy code $LASTEXITCODE)." }
    Ok "Current code backed up to $backup"
}
if ((-not $SkipService) -and (Get-Service $serviceName -ErrorAction SilentlyContinue)) {
    Stop-Service $serviceName -Force -ErrorAction SilentlyContinue
    Ok "Service stopped"
}
New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
robocopy (Join-Path $bundle "api") $TargetDir /E /XD certs client_package logs templets __pycache__ _backup_before_update .vscode /XF db_config.json app_keys.json server_settings.json /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Fail "Copying the code failed (robocopy code $LASTEXITCODE)." }
Ok "Code copied"

# 4. Database login (db_config.json)
$dbConfig = Join-Path $TargetDir "db_config.json"
$oldConfig = Join-Path $TargetDir "_backup_before_update\config.py"
if (Test-Path $dbConfig) {
    Ok "db_config.json kept"
} elseif ((Test-Path $oldConfig) -and (Select-String -LiteralPath $oldConfig -Pattern "DB_PASSWORD\s*=\s*'" -Quiet)) {
    $code = "import importlib.util, json, sys; s = importlib.util.spec_from_file_location('old_config', sys.argv[1]); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); c = m.DBConfig; json.dump({'host': c.DB_HOST, 'user': c.DB_USER, 'password': c.DB_PASSWORD, 'database': c.DB_NAME}, open(sys.argv[2], 'w', encoding='utf-8'), indent=2)"
    & $python -c $code $oldConfig $dbConfig
    if ($LASTEXITCODE -ne 0) { Fail "Could not read the MySQL login from the old config.py." }
    Ok "db_config.json created from the old config.py"
} else {
    Write-Host "MySQL login for the API (the certman_api account from sql\fixes\2026-10-27_04_api_db_account.sql):"
    $dbHost = Read-Host "  MySQL host [localhost]"
    if (-not $dbHost) { $dbHost = "localhost" }
    $dbUser = Read-Host "  MySQL user [certman_api]"
    if (-not $dbUser) { $dbUser = "certman_api" }
    $secure = Read-Host "  MySQL password" -AsSecureString
    $dbPass = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
    $json = [ordered]@{ host = $dbHost; user = $dbUser; password = $dbPass; database = "certificate_manager" } | ConvertTo-Json
    [IO.File]::WriteAllText($dbConfig, $json, (New-Object Text.UTF8Encoding $false))
    Ok "db_config.json created"
}

# 5. Templates: add missing files only
robocopy (Join-Path $bundle "templets") (Join-Path $TargetDir "templets") /E /XC /XN /XO /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Fail "Copying the templates failed (robocopy code $LASTEXITCODE)." }
Ok "Templates (missing files added)"

# 6. Apache must not serve this folder
if (Test-Path (Join-Path $TargetDir ".htaccess")) { Ok ".htaccess present" } else { Fail ".htaccess is missing in $TargetDir" }

# 7. Database login check (read-only)
if ($SkipDbCheck) { Skip "Database login check" } else {
    Push-Location $TargetDir
    & $python -c "from config import DBConfig as c; import mysql.connector as m; x = m.connect(host=c.DB_HOST, user=c.DB_USER, password=c.DB_PASSWORD, database=c.DB_NAME); x.cursor().execute('SELECT 1'); print('database ok')"
    $dbOk = ($LASTEXITCODE -eq 0)
    Pop-Location
    if ($dbOk) { Ok "Database login works" } else { Warn "MySQL refused the login in db_config.json. Fix that file, then run setup_server.bat again." }
}

# 8. Windows service (install_service.bat; its final 'pause' is answered by '< nul')
$port = 2030
$https = $false
$settingsFile = Join-Path $TargetDir "server_settings.json"
if (Test-Path $settingsFile) {
    $settings = Get-Content $settingsFile -Raw | ConvertFrom-Json
    if ($settings.port) { $port = [int]$settings.port }
    $https = [bool]$settings.https
}
if ($SkipService) { Skip "Windows service" } else {
    $installBat = Join-Path $TargetDir "install_service.bat"
    $process = Start-Process -FilePath "cmd.exe" -ArgumentList "/s /c `"`"$installBat`" < nul`"" -Wait -PassThru -NoNewWindow
    if ($process.ExitCode -ne 0) { Fail "install_service.bat failed. Double-click it in $TargetDir to see why (log: logs\api_service.log)." }
    Ok "Service installed and started"
}

# 9. Firewall
if ($SkipFirewall) { Skip "Firewall rule" } else {
    if (Get-NetFirewallRule -DisplayName "Certificate Manager API" -ErrorAction SilentlyContinue) { Ok "Firewall rule exists" } else {
        New-NetFirewallRule -DisplayName "Certificate Manager API" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $port | Out-Null
        Ok "Firewall rule added (TCP $port)"
    }
}

# 10. Health check
if (-not $SkipService) {
    Start-Sleep -Seconds 3
    $scheme = "http"
    if ($https) { $scheme = "https" }
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    [Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
    try {
        $answer = Invoke-RestMethod -Uri "${scheme}://127.0.0.1:$port/ping" -TimeoutSec 10
        Ok "API answers on ${scheme}://127.0.0.1:$port/ping ($($answer.status))"
    } catch {
        Warn "The API does not answer yet. See $TargetDir\logs\api_service.log"
    }
}

Write-Host ""
Write-Host "Still to do by hand (only once each):"
if (-not (Test-Path (Join-Path $TargetDir "certs\server.crt"))) { Write-Host "  - HTTPS: run setup_server_https.bat in $TargetDir (SERVER_SETUP_GUIDE.md, step 4)" }
Write-Host "  - Database: run the files in sql\fixes\ that were not run yet, in number order (phpMyAdmin, SQL tab)"
Write-Host "  - After 2026-10-27_04: put the certman_api login into $dbConfig, then run setup_server.bat again"
Write-Host "  - Passwords: run hash_existing_passwords.bat in $TargetDir if that was not done yet"
Write-Host "[DONE] Server setup finished"
````

## Step 7.3 — Write `scripts/build_server_bundle.ps1` (new file)

````powershell file=scripts/build_server_bundle.ps1
# =============================================================================
# build_server_bundle.ps1 - make the server bundle on the developer laptop.
# Output: dist\release\<version>\CertificateManagerServer-<version>\  and the same as .zip
# The bundle never contains this laptop's secrets (db_config.json, app_keys.json,
# server_settings.json, certs\, client_package\).
# Usage: powershell -ExecutionPolicy Bypass -File scripts\build_server_bundle.ps1 [-OutDir <folder>] [-SkipWheels]
# =============================================================================
param([string]$OutDir = "", [switch]$SkipWheels)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

$verLine = Select-String -Path (Join-Path $root "app_version.py") -Pattern '^APP_VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
if (-not $verLine) { throw "APP_VERSION not found in app_version.py" }
$version = $verLine.Matches[0].Groups[1].Value
if (-not $OutDir) { $OutDir = Join-Path $root "dist\release\$version" }
$bundle = Join-Path $OutDir "CertificateManagerServer-$version"
if (Test-Path $bundle) { Remove-Item -Recurse -Force $bundle }
New-Item -ItemType Directory -Force -Path $bundle | Out-Null

# 1. API code, without this laptop's settings and secrets
robocopy (Join-Path $root "certificate_manager_api") (Join-Path $bundle "api") /E /XD certs client_package logs templets __pycache__ _backup_before_update .vscode /XF app_keys.json server_settings.json db_config.json *.log *.key /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy of the API failed (code $LASTEXITCODE)" }

# 2. Templates, database scripts, requirements, setup scripts, guide, version
robocopy (Join-Path $root "templets") (Join-Path $bundle "templets") /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy of the templates failed (code $LASTEXITCODE)" }
New-Item -ItemType Directory -Force -Path (Join-Path $bundle "sql\fixes") | Out-Null
Copy-Item -LiteralPath (Join-Path $root "sql\schema.sql"), (Join-Path $root "sql\SP.sql") -Destination (Join-Path $bundle "sql")
Copy-Item -Path (Join-Path $root "sql\fixes\*.sql") -Destination (Join-Path $bundle "sql\fixes")
Copy-Item -LiteralPath (Join-Path $root "requirements-server.txt") -Destination $bundle
Copy-Item -LiteralPath (Join-Path $root "installer\server\setup_server.bat"), (Join-Path $root "installer\server\setup_server.ps1") -Destination $bundle
Copy-Item -LiteralPath (Join-Path $root "certificate_manager_api\SERVER_SETUP_GUIDE.md") -Destination $bundle
Set-Content -Encoding ascii -LiteralPath (Join-Path $bundle "VERSION.txt") -Value $version

# 3. Python packages for a server without internet
if (-not $SkipWheels) {
    & py -3 -m pip download --disable-pip-version-check -q --only-binary=:all: -r (Join-Path $root "requirements-server.txt") -d (Join-Path $bundle "wheels")
    if ($LASTEXITCODE -ne 0) { throw "pip download failed" }
}

# 4. Zip
$zip = "$bundle.zip"
if (Test-Path $zip) { Remove-Item -Force $zip }
Compress-Archive -Path $bundle -DestinationPath $zip
Write-Output "[SUCCESS] Server bundle $version"
Write-Output "  Folder: $bundle"
Write-Output "  Zip:    $zip"
````

## Step 7.4 — Write `installer/server/test_setup_server.ps1` (new file)

````powershell file=installer/server/test_setup_server.ps1
# =============================================================================
# test_setup_server.ps1 - runs setup_server.ps1 against folders under %TEMP% only
# (no service, firewall, pip or MySQL). Never touches C:\AppServ.
# Usage: powershell -ExecutionPolicy Bypass -File installer\server\test_setup_server.ps1 -Bundle <bundle folder>
# =============================================================================
param([Parameter(Mandatory = $true)][string]$Bundle)
$ErrorActionPreference = "Stop"
$root = Join-Path $env:TEMP "cm_srv_test"
if (Test-Path $root) { Remove-Item -Recurse -Force $root }
$setup = Join-Path $Bundle "setup_server.ps1"
$common = @("-SkipPip", "-SkipService", "-SkipFirewall", "-SkipDbCheck")
$fails = @()

# Case A: a configured server is updated twice; its own files must not change.
$a = Join-Path $root "configured server"
New-Item -ItemType Directory -Force -Path (Join-Path $a "certs"), (Join-Path $a "templets") | Out-Null
'{"host": "localhost", "user": "u", "password": "p", "database": "certificate_manager"}' | Set-Content -Encoding ascii -LiteralPath (Join-Path $a "db_config.json")
'{"enforce": true, "apps": {"x": "y"}}' | Set-Content -Encoding ascii -LiteralPath (Join-Path $a "app_keys.json")
'{"port": 2030, "https": true}' | Set-Content -Encoding ascii -LiteralPath (Join-Path $a "server_settings.json")
"KEY" | Set-Content -Encoding ascii -LiteralPath (Join-Path $a "certs\server.key")
"CUSTOM" | Set-Content -Encoding ascii -LiteralPath (Join-Path $a "templets\custom.docx")
"old main" | Set-Content -Encoding ascii -LiteralPath (Join-Path $a "main.py")
$keep = @("db_config.json", "app_keys.json", "server_settings.json", "certs\server.key", "templets\custom.docx")
$before = @{}
foreach ($f in $keep) { $before[$f] = (Get-FileHash -LiteralPath (Join-Path $a $f)).Hash }
foreach ($run in 1, 2) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setup -TargetDir $a @common | Out-Null
    if ($LASTEXITCODE -ne 0) { $fails += "case A run $run exit code $LASTEXITCODE" }
}
foreach ($f in $keep) { if ((Get-FileHash -LiteralPath (Join-Path $a $f)).Hash -ne $before[$f]) { $fails += "case A changed $f" } }
if ((Get-Content -LiteralPath (Join-Path $a "main.py") -Raw) -match "old main") { $fails += "case A main.py was not updated" }
if (-not (Test-Path -LiteralPath (Join-Path $a ".htaccess"))) { $fails += "case A .htaccess missing" }
if (-not (Test-Path -LiteralPath (Join-Path $a "templets\templates_config.json"))) { $fails += "case A templates were not added" }

# Case B: an old server whose config.py still holds the login gets db_config.json from it.
$b = Join-Path $root "old server"
New-Item -ItemType Directory -Force -Path $b | Out-Null
"old main" | Set-Content -Encoding ascii -LiteralPath (Join-Path $b "main.py")
@("class DBConfig:", "    DB_HOST = 'dbhost'", "    DB_USER = 'olduser'", "    DB_PASSWORD = 'oldpass'", "    DB_NAME = 'certificate_manager'") | Set-Content -Encoding ascii -LiteralPath (Join-Path $b "config.py")
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setup -TargetDir $b @common | Out-Null
if ($LASTEXITCODE -ne 0) { $fails += "case B exit code $LASTEXITCODE" }
$migrated = Get-Content -LiteralPath (Join-Path $b "db_config.json") -Raw | ConvertFrom-Json
if ($migrated.host -ne "dbhost" -or $migrated.user -ne "olduser" -or $migrated.password -ne "oldpass") { $fails += "case B db_config.json was not migrated" }
if ((Get-Content -LiteralPath (Join-Path $b "config.py") -Raw) -match "oldpass") { $fails += "case B config.py still holds the password" }

if ($fails.Count -gt 0) { $fails | ForEach-Object { "FAIL: $_" }; exit 1 }
"ALL CHECKS PASSED"
````

## Step 7.5 — Write `tests/test_server_bundle.py` (new file)

````python file=tests/test_server_bundle.py
"""The server bundle holds what setup_server needs, and never this laptop's secrets."""
import subprocess

import pytest

from tests.helpers import PROJECT_ROOT

SECRET_NAMES = {"app_keys.json", "db_config.json", "server_settings.json", "server_config.json"}
REQUIRED = [
    "api/main.py", "api/.htaccess", "api/install_service.bat", "api/config.py", "api/db_config.example.json",
    "sql/schema.sql", "sql/SP.sql", "sql/fixes/2026-10-27_04_api_db_account.sql",
    "templets/templates_config.json", "requirements-server.txt", "setup_server.bat", "setup_server.ps1",
    "SERVER_SETUP_GUIDE.md", "VERSION.txt",
]


@pytest.fixture(scope="module")
def built_bundle(tmp_path_factory):
    out = tmp_path_factory.mktemp("bundle")
    subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(PROJECT_ROOT / "scripts" / "build_server_bundle.ps1"), "-OutDir", str(out), "-SkipWheels"],
                   check=True, capture_output=True, timeout=600)
    return next(path for path in out.iterdir() if path.is_dir())


def test_bundle_has_no_secrets(built_bundle):
    names = [path.relative_to(built_bundle).as_posix() for path in built_bundle.rglob("*") if path.is_file()]
    leaked = [name for name in names
              if name.endswith(".key") or name.rsplit("/", 1)[-1] in SECRET_NAMES
              or name.startswith(("api/certs/", "api/client_package/", "api/logs/"))]
    assert leaked == []


def test_bundle_has_required_files(built_bundle):
    missing = [name for name in REQUIRED if not (built_bundle / name).is_file()]
    assert missing == []
````

````powershell run
py -3 -m pytest tests/test_server_bundle.py
py -3 -m pytest
````
Expected: `67 passed, 1 deselected`. The first run must print `2 passed`.

## Step 7.6 — `update_server.bat` must keep `db_config.json`, not `config.py`

Edit `certificate_manager_api/update_server.bat` (two edits).

**Find:**
````text edit-old=certificate_manager_api/update_server.bat
REM   config.py (database login)  update_server.bat (this file)
````
**Replace with:**
````text edit-new=certificate_manager_api/update_server.bat
REM   db_config.json (database login)  update_server.bat (this file)
REM Prefer setup_server.bat from the server bundle: it also migrates an old config.py.
````

**Find:**
````text edit-old=certificate_manager_api/update_server.bat
/XF app_keys.json server_settings.json config.py update_server.bat *.log
````
**Replace with:**
````text edit-new=certificate_manager_api/update_server.bat
/XF app_keys.json server_settings.json db_config.json update_server.bat *.log
````

## Step 7.7 — Build a bundle and run the setup test against temp folders

````powershell run
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build_server_bundle.ps1 -OutDir "$env:TEMP\cm_bundle_check" -SkipWheels
powershell.exe -NoProfile -ExecutionPolicy Bypass -File installer\server\test_setup_server.ps1 -Bundle "$env:TEMP\cm_bundle_check\CertificateManagerServer-2.1.0"
````
Expected: `ALL CHECKS PASSED`. The first command must also print `[SUCCESS] Server bundle 2.1.0`.

## Step 7.8 — Commit

````powershell run
git add -- installer/server/setup_server.bat installer/server/setup_server.ps1 installer/server/test_setup_server.ps1 scripts/build_server_bundle.ps1 tests/test_server_bundle.py certificate_manager_api/update_server.bat
git commit -q -m "build: server bundle and idempotent setup_server for first install and updates"
git log --oneline -1
git status --porcelain | Where-Object { $_ -notmatch '^.. "?(logs/|certificates/|\.nicegui/)' }
````
Expected: `build: server bundle and idempotent setup_server`. Nothing else may be printed after the log line.

## Done

````powershell run
git log --oneline -3
````
Expected: `build: server bundle and idempotent setup_server`
