# install_service.ps1 - install or update registration_web on the server laptop.
# Run as Administrator from this folder:
#   powershell -ExecutionPolicy Bypass -File install_service.ps1 -ServerAddress 172.50.1.100
# Options: -DataDir C:\registration_data  -Port 2040  -BackupTime 02:00
# Safe to run again (update / new IP): keeps the DB, the secret key and the backups.
# Independent of Apache (AppServ or WAMP): own service on its own port.
param(
    [string]$ServerAddress = "",
    [string]$DataDir = "C:\registration_data",
    [int]$Port = 2040,
    [string]$BackupTime = "02:00"
)
$ErrorActionPreference = "Stop"
function Ok($m)   { Write-Host "[OK]   $m" -ForegroundColor Green }
function Fail($m) { Write-Host "[FAIL] $m" -ForegroundColor Red; exit 1 }

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Fail "Run PowerShell as Administrator." }
$app = $PSScriptRoot
$serviceName = "RegWebRegistration"

# 1. Python: the same system python that runs the API service (has pywin32)
$python = Get-Command python.exe -All -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch "WindowsApps" } | Select-Object -First 1 -ExpandProperty Source
if (-not $python) { Fail "python.exe not found on PATH (install Python 3 64-bit for all users)." }
& $python -c "import win32serviceutil" 2>$null
if ($LASTEXITCODE -ne 0) { Fail "pywin32 is missing in $python (the API setup installs it: setup_server.bat)." }
Ok "Python: $python"

# 2. Data folder, secret key (made once, kept), settings.json (port + allowed hosts)
New-Item -ItemType Directory -Force -Path $DataDir, "$DataDir\media", "$DataDir\backups", "$DataDir\logs" | Out-Null
$keyFile = Join-Path $DataDir "secret_key.txt"
if (-not (Test-Path $keyFile)) {
    & $python -c "import secrets; print(secrets.token_urlsafe(50))" | Out-File -Encoding ascii $keyFile
    Ok "Secret key created: $keyFile"
} else { Ok "Secret key kept" }
& icacls $DataDir /inheritance:r /grant:r "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F" | Out-Null

$settingsFile = Join-Path $DataDir "settings.json"
$hosts = @("localhost", "127.0.0.1", $env:COMPUTERNAME)
if (Test-Path $settingsFile) {
    $old = Get-Content $settingsFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $hosts += @($old.allowed_hosts)
}
if ($ServerAddress) { $hosts += $ServerAddress }
$hosts = $hosts | Where-Object { $_ } | Select-Object -Unique
$json = @{ port = $Port; allowed_hosts = @($hosts) } | ConvertTo-Json
[IO.File]::WriteAllText($settingsFile, $json, (New-Object Text.UTF8Encoding $false))
Ok "settings.json: port $Port, hosts $($hosts -join ', ')"

$svcCfg = @{ data_dir = $DataDir } | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $app "service_config.json"), $svcCfg, (New-Object Text.UTF8Encoding $false))

# 3. venv (sees the system pywin32), packages, DB, static files
$venvPy = Join-Path $app ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) { & $python -m venv --system-site-packages (Join-Path $app ".venv") }
& $venvPy -m pip install --disable-pip-version-check -q -r (Join-Path $app "requirements.txt")
if ($LASTEXITCODE -ne 0) { Fail "pip install failed." }
$env:REGWEB_DATA_DIR = $DataDir
Remove-Item Env:REGWEB_DEBUG -ErrorAction SilentlyContinue
Push-Location $app
& $venvPy manage.py migrate --noinput;        if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "migrate failed." }
& $venvPy manage.py collectstatic --noinput -v 0; if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "collectstatic failed." }
& $venvPy manage.py check --deploy --fail-level ERROR | Out-Null
$usersFile = Join-Path $DataDir "trial_users.json"
if (-not (Test-Path $usersFile)) { Copy-Item (Join-Path $app "trial_users.example.json") $usersFile }
& $venvPy manage.py create_trial_users $usersFile; if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "create_trial_users failed." }
Pop-Location
Ok "Database, static files and trial users ready (passwords: $DataDir\trial_passwords.txt)"

# 4. Windows service (pywin32, same as the API), auto start, restart on failure
$svc = Get-Service $serviceName -ErrorAction SilentlyContinue
if ($svc) {
    if ($svc.Status -ne "Stopped") { Stop-Service $serviceName -Force }
    & $python (Join-Path $app "regweb_service.py") --startup auto update | Out-Null
} else {
    & $python (Join-Path $app "regweb_service.py") --startup auto install | Out-Null
}
& sc.exe failure $serviceName reset= 86400 actions= restart/10000/restart/10000/restart/60000 | Out-Null
Start-Service $serviceName
Ok "Service $serviceName running"

# 5. Firewall: this port, Domain + Private (LAN) only, never Public
$ruleName = "RegWeb Registration (TCP $Port)"
Get-NetFirewallRule -DisplayName "RegWeb Registration*" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow -Profile Domain,Private | Out-Null
Ok "Firewall: $ruleName (Domain, Private)"
$profiles = Get-NetConnectionProfile | Where-Object NetworkCategory -eq "Public"
if ($profiles) { Write-Host "[WARN] Network '$($profiles.Name -join ', ')' is Public: other PCs cannot connect until it is set to Private." -ForegroundColor Yellow }

# 6. Nightly backup task (SYSTEM)
$action = New-ScheduledTaskAction -Execute (Join-Path $app "regweb_backup.bat") -WorkingDirectory $app
$trigger = New-ScheduledTaskTrigger -Daily -At $BackupTime
Register-ScheduledTask -TaskName "RegWeb nightly backup" -Action $action -Trigger $trigger -User "SYSTEM" -RunLevel Highest -Force | Out-Null
Ok "Nightly backup at $BackupTime -> $DataDir\backups (30 days) + sweep_parts (.part older than 24 h)"

Write-Host ""
Write-Host "Open from another PC: http://$(if ($ServerAddress) { $ServerAddress } else { $env:COMPUTERNAME }):$Port/admin/"
Write-Host "First admin user:  cd `"$app`"; `$env:REGWEB_DATA_DIR='$DataDir'; .venv\Scripts\python manage.py createsuperuser"
