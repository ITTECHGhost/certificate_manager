# =============================================================================
# update.ps1 - started by Update.bat on the SERVER laptop. Never run on a client.
#   1. checksums.txt: every file of this folder is intact
#   2. version: newer than the installed server (server_version.txt)
#   3. server\setup_server.ps1: code + database (it backs up and rolls back itself)
#   4. client\patch_vX.Y.Z.zip: published, so every client offers the update
# A log is written next to this file: update-log-<time>.txt
# Test parameters: -TargetDir -UpdatesDir -Yes -Force -SkipPip -SkipService -SkipFirewall -SkipDbCheck
# =============================================================================
param(
    [string]$TargetDir = "C:\AppServ\www\certificate_manager_api",
    [string]$UpdatesDir = "",
    [switch]$Yes,
    [switch]$Force,
    [switch]$SkipPip,
    [switch]$SkipService,
    [switch]$SkipFirewall,
    [switch]$SkipDbCheck
)
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot

function Ok([string]$m) { Write-Host "[OK] $m" -ForegroundColor Green }
function Fail([string]$m) { Write-Host "[ERROR] $m" -ForegroundColor Red; try { Stop-Transcript | Out-Null } catch {}; exit 1 }

function Compare-Version([string]$a, [string]$b) {
    $pa = @($a.Split(".") | ForEach-Object { [int]$_ }) + @(0, 0, 0)
    $pb = @($b.Split(".") | ForEach-Object { [int]$_ }) + @(0, 0, 0)
    for ($i = 0; $i -lt 3; $i++) { if ($pa[$i] -ne $pb[$i]) { return [math]::Sign($pa[$i] - $pb[$i]) } }
    return 0
}

$log = Join-Path $here ("update-log-{0:yyyyMMdd-HHmmss}.txt" -f (Get-Date))
try { Start-Transcript -Path $log | Out-Null } catch { $log = $null }

$version = (Get-Content (Join-Path $here "VERSION.txt") -Raw).Trim()
Write-Host "=== Certificate Manager update $version ==="

# 1. Files intact
$sums = Join-Path $here "checksums.txt"
if (-not (Test-Path $sums)) { Fail "checksums.txt is missing: this is not a complete update folder." }
$bad = @()
foreach ($line in Get-Content $sums) {
    if ($line -notmatch '^([0-9a-f]{64})  (.+)$') { continue }
    $path = Join-Path $here $Matches[2]
    if (-not (Test-Path -LiteralPath $path)) { $bad += "missing: $($Matches[2])"; continue }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower() -ne $Matches[1]) { $bad += "changed: $($Matches[2])" }
}
if ($bad.Count) { $bad | Select-Object -First 10 | ForEach-Object { Write-Host "  $_" }; Fail "$($bad.Count) file(s) damaged or missing. Copy the update folder again." }
Ok "All files intact"

# 2. Version
$installedFile = Join-Path $TargetDir "server_version.txt"
$installed = if (Test-Path $installedFile) { (Get-Content $installedFile -Raw).Trim() } else { "" }
if ($installed) {
    $cmp = Compare-Version $version $installed
    if ($cmp -le 0 -and -not $Force) { Fail "The server already has version $installed (this update is $version). Nothing was changed." }
    Ok "Installed server: $installed -> $version"
} else {
    Write-Host "Installed server version is unknown (installed before 2.3.0)."
}
if (-not $Yes) {
    $answer = Read-Host "Update the server to $version now? The API stops for about a minute. (y/n)"
    if ($answer -notmatch '^(y|yes)$') { Fail "Cancelled. Nothing was changed." }
}

# 3. Server code + database
$setup = Get-ChildItem (Join-Path $here "server") -Filter setup_server.ps1 -Recurse | Select-Object -First 1
if (-not $setup) { Fail "server\...\setup_server.ps1 not found in the update folder." }
$args2 = @{ TargetDir = $TargetDir }
foreach ($s in "SkipPip", "SkipService", "SkipFirewall", "SkipDbCheck") { if ((Get-Variable $s).Value) { $args2[$s] = $true } }
& $setup.FullName @args2
if ($LASTEXITCODE -ne 0) { Fail "The server update stopped (see the lines above). The client update was NOT published." }
Ok "Server updated to $version"

# 4. Client patch
$patch = Get-ChildItem (Join-Path $here "client") -Filter "patch_v*.zip" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $patch) {
    Write-Host "[SKIP] No client patch in this update."
} else {
    $notesFile = Join-Path $here "client\CHANGES.txt"
    $notes = if (Test-Path $notesFile) { (Get-Content $notesFile -Raw -Encoding UTF8).Trim() } else { "" }
    $publish = Join-Path $TargetDir "publish_client_update.ps1"
    $pubArgs = @{ Zip = $patch.FullName; Notes = $notes }
    if ($UpdatesDir) { $pubArgs["BaseDir"] = $UpdatesDir }
    & $publish @pubArgs
    if ($LASTEXITCODE -ne 0) { Fail "The server is updated, but publishing the client update failed. Run publish_client_update.bat with $($patch.FullName)." }
    Ok "Client update $($patch.BaseName) published: clients offer it at their next start"
}

Write-Host ""
Write-Host "[SUCCESS] Update $version finished." -ForegroundColor Green
if ($log) { Write-Host "Log: $log" }
try { Stop-Transcript | Out-Null } catch {}
exit 0
