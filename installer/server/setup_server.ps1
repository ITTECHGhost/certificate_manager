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

# 1. Administrator rights
if (-not ($SkipService -and $SkipFirewall)) {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { Fail "Run setup_server.bat: it asks for Administrator rights." }
}

# 1b. AppServ (Apache + MySQL): install from prereqs\ when missing, then start both with Windows
$prereqs = Join-Path $bundle "prereqs"
function Find-Installer([string]$Pattern) {
    if (Test-Path $prereqs) { Get-ChildItem -LiteralPath $prereqs -Filter $Pattern -File | Select-Object -First 1 -ExpandProperty FullName }
}
function Find-AppServServices { @(Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^(apache|mysql)' }) }
if ($SkipService) { Skip "Apache and MySQL" } else {
    $services = Find-AppServServices
    if (-not ($services | Where-Object Name -match '^apache') -or -not ($services | Where-Object Name -match '^mysql')) {
        $appservSetup = Find-Installer "appserv*.exe"
        if (-not $appservSetup) { Fail "Apache/MySQL (AppServ) is not installed. Put the AppServ installer (appserv-*.exe) in $prereqs, or install AppServ by hand, then run setup_server.bat again." }
        Write-Host "Apache/MySQL not found. Starting the AppServ installer - finish its steps (keep the default folder C:\AppServ)..."
        Start-Process -FilePath $appservSetup -Wait
        $services = Find-AppServServices
        if (-not ($services | Where-Object Name -match '^apache') -or -not ($services | Where-Object Name -match '^mysql')) { Fail "AppServ was installed but the Apache or MySQL service is still missing." }
    }
    foreach ($svc in $services) {
        Set-Service -Name $svc.Name -StartupType Automatic
        if ($svc.Status -ne "Running") { Start-Service -Name $svc.Name }
        Ok "$($svc.Name): starts with Windows, running"
    }
}

# 1c. Python (the same python.exe install_service.bat will use): install from prereqs when missing
function Find-Python {
    $found = Get-Command python.exe -All -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch "WindowsApps" } | Select-Object -First 1 -ExpandProperty Source
    if (-not $found) { $found = (& py -3 -c "import sys; print(sys.executable)" 2>$null) }
    if (-not $found) { $found = Get-ChildItem "$env:ProgramFiles\Python3*\python.exe" -ErrorAction SilentlyContinue | Select-Object -Last 1 -ExpandProperty FullName }
    $found
}
$python = Find-Python
if (-not $python) {
    $pythonSetup = Find-Installer "python-*-amd64.exe"
    if (-not $pythonSetup) { Fail "Python was not found. Put the Python installer (python-3.x-amd64.exe) in $prereqs, or install Python 3 (64-bit) for all users with 'Add python.exe to PATH'." }
    Write-Host "Installing Python (all users, silent)..."
    $process = Start-Process -FilePath $pythonSetup -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait -PassThru
    if ($process.ExitCode -ne 0) { Fail "The Python installer failed (code $($process.ExitCode))." }
    $python = Find-Python
    if (-not $python) { Fail "Python was installed but python.exe was not found. Restart Windows, then run setup_server.bat again." }
}
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

# 8. HTTPS, first installation only: certificates, app key, client package, https = true
$settingsFile = Join-Path $TargetDir "server_settings.json"
if ($SkipService) { Skip "HTTPS" } elseif (-not (Test-Path (Join-Path $TargetDir "certs\server.crt"))) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $TargetDir "setup_server_https.ps1")
    if ($LASTEXITCODE -ne 0) { Fail "HTTPS setup failed. Run setup_server.bat again." }
    $current = [ordered]@{ port = 2030; https = $true }
    if (Test-Path $settingsFile) { $old = Get-Content $settingsFile -Raw | ConvertFrom-Json; if ($old.port) { $current.port = [int]$old.port } }
    [IO.File]::WriteAllText($settingsFile, ($current | ConvertTo-Json), (New-Object Text.UTF8Encoding $false))
    Ok "HTTPS set up. Copy $TargetDir\client_package\ to the clients (README.txt inside)."
} else { Ok "HTTPS certificates kept" }

# 9. Windows service: starts with Windows, restarts on failure (install_service.bat; its final 'pause' is answered by '< nul')
$port = 2030
$https = $false
if (Test-Path $settingsFile) {
    $settings = Get-Content $settingsFile -Raw | ConvertFrom-Json
    if ($settings.port) { $port = [int]$settings.port }
    $https = ($settings.https -eq $true) -or ("$($settings.https)" -eq "true")
}
if ($SkipService) { Skip "Windows service" } else {
    $installBat = Join-Path $TargetDir "install_service.bat"
    $process = Start-Process -FilePath "cmd.exe" -ArgumentList "/s /c `"`"$installBat`" < nul`"" -Wait -PassThru -NoNewWindow
    if ($process.ExitCode -ne 0) { Fail "install_service.bat failed. Double-click it in $TargetDir to see why (log: logs\api_service.log)." }
    Ok "Service installed and started"
}

# 10. Firewall
if ($SkipFirewall) { Skip "Firewall rule" } else {
    if (Get-NetFirewallRule -DisplayName "Certificate Manager API" -ErrorAction SilentlyContinue) { Ok "Firewall rule exists" } else {
        New-NetFirewallRule -DisplayName "Certificate Manager API" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $port | Out-Null
        Ok "Firewall rule added (TCP $port)"
    }
}

# 11. Health check
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
Write-Host "  - Database: run the files in sql\fixes\ that were not run yet, in number order (phpMyAdmin, SQL tab)"
Write-Host "  - After 2026-10-27_04: put the certman_api login into $dbConfig, then run setup_server.bat again"
Write-Host "  - Passwords: run hash_existing_passwords.bat in $TargetDir if that was not done yet"
Write-Host "[DONE] Server setup finished"
