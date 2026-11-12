@echo off
REM =============================================================================
REM finish_update.bat - finish a server update that stopped after the service started
REM (2.5.0 on servers installed before 2.3.0: "schtasks.exe : ERROR: The system cannot
REM find the file specified"). Double-click it on the SERVER laptop. It asks for
REM Administrator, then:
REM   1. creates the server update task if it is missing,
REM   2. publishes the client patch of the installed server version (patch_vX.Y.Z.zip,
REM      found next to this file or in Downloads), unless it is already published,
REM   3. checks that the API answers.
REM It changes nothing in the API code or the database. Safe to run again.
REM =============================================================================
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator rights...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
REM The PowerShell part is below the #POWERSHELL# line of this same file
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$self = '%~f0'; $text = [IO.File]::ReadAllText($self); Invoke-Expression ($text.Substring($text.LastIndexOf('#' + 'POWERSHELL#') + 12))"
set "RC=%errorlevel%"
echo.
pause
exit /b %RC%

#POWERSHELL#
$ErrorActionPreference = "Stop"
$TargetDir = "C:\AppServ\www\certificate_manager_api"
$taskName = "CertificateManagerServerUpdater"
function Ok([string]$m) { Write-Host "[OK] $m" -ForegroundColor Green }
function Warn([string]$m) { Write-Host "[WARNING] $m" -ForegroundColor Yellow }
function Fail([string]$m) { Write-Host "[ERROR] $m" -ForegroundColor Red; exit 1 }

Write-Host "=== Finish the server update ==="
if (-not (Test-Path (Join-Path $TargetDir "main.py"))) { Fail "The API was not found in $TargetDir." }
$versionFile = Join-Path $TargetDir "server_version.txt"
if (-not (Test-Path $versionFile)) { Fail "$versionFile is missing: the server update did not reach the database step. Run Update.bat again." }
$installed = (Get-Content $versionFile -Raw).Trim()
Ok "Server version: $installed"

# 1. Server update task (the same task setup_server.ps1 creates)
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) { Ok "Server update task exists" } else {
    $updater = Join-Path $TargetDir "server_updater.ps1"
    if (-not (Test-Path $updater)) { Fail "$updater is missing." }
    $action = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$updater`""
    & schtasks.exe /Create /TN $taskName /SC MINUTE /MO 1 /RU SYSTEM /RL HIGHEST /F /TR $action | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "Could not create the server update task." }
    Ok "Server update task created (updates can now be uploaded from Settings)"
}

# 2. Client patch of the installed version
$updatesDir = if (Test-Path "C:\AppServ\www") { "C:\AppServ\www\updates" } else { Join-Path $TargetDir "updates" }
$published = ""
$manifest = Join-Path $updatesDir "version.json"
if (Test-Path $manifest) {
    try { $published = [string](Get-Content $manifest -Raw -Encoding UTF8 | ConvertFrom-Json).latest_version } catch { }
}
if ($published -eq $installed) { Ok "Client update $installed is already published" } else {
    $patchName = "patch_v$installed.zip"
    $roots = @((Split-Path $self), (Join-Path $env:USERPROFILE "Downloads"))
    $patch = $roots | ForEach-Object { Get-ChildItem $_ -Recurse -Depth 4 -Filter $patchName -ErrorAction SilentlyContinue } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $patch) { Fail "$patchName was not found next to this file or in Downloads. Drag it onto $TargetDir\publish_client_update.bat." }
    Ok "Client patch: $($patch.FullName)"
    $notesFile = Join-Path $patch.DirectoryName "CHANGES.txt"
    $notes = if (Test-Path $notesFile) { (Get-Content $notesFile -Raw -Encoding UTF8).Trim() } else { "" }
    & (Join-Path $TargetDir "publish_client_update.ps1") -Zip $patch.FullName -Notes $notes
    if ($LASTEXITCODE -ne 0) { Fail "Publishing the client update failed (see the lines above)." }
    Ok "Client update $installed published: clients offer it at their next start"
}

# 3. Health check
$port = 2030
$https = $false
$settingsFile = Join-Path $TargetDir "server_settings.json"
if (Test-Path $settingsFile) {
    $settings = Get-Content $settingsFile -Raw | ConvertFrom-Json
    if ($settings.port) { $port = [int]$settings.port }
    $https = ($settings.https -eq $true) -or ("$($settings.https)" -eq "true")
}
$scheme = if ($https) { "https" } else { "http" }
# Windows PowerShell 5.1 cannot run a script-block certificate callback on the TLS thread
# ("There is no Runspace available"), so the check never passed over HTTPS. Use curl.exe -k
# (self-signed certificate), or a compiled callback where curl.exe is missing.
$pingUrl = "${scheme}://127.0.0.1:$port/ping"
$status = ""
if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
    $status = [string](& curl.exe -s -k -m 10 -o NUL -w "%{http_code}" $pingUrl)
} else {
    try {
        if (-not ("FinishUpdateTrustAll" -as [type])) {
            Add-Type -TypeDefinition "public static class FinishUpdateTrustAll { public static void Install() { System.Net.ServicePointManager.ServerCertificateValidationCallback = (s, c, ch, e) => true; } }"
        }
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        [FinishUpdateTrustAll]::Install()
        $status = [string](Invoke-WebRequest -Uri $pingUrl -TimeoutSec 10 -UseBasicParsing).StatusCode
    } catch { $status = "" }
}
if ($status -eq "200") {
    Ok "API answers on $pingUrl"
} else {
    Warn "The API does not answer on $pingUrl (status: $status). See $TargetDir\logs\api_service.log"
}
Write-Host ""
Write-Host "[DONE] Server update $installed finished" -ForegroundColor Green
exit 0
