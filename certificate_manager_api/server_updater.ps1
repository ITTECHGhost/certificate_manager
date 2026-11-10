# =============================================================================
# server_updater.ps1 - runs every minute as SYSTEM (scheduled task
# "CertificateManagerServerUpdater", created by setup_server.ps1).
# When pending.json (written by POST /api/admin/server-update/upload) is due:
#   unzip the update into work\, run its update.ps1 -Yes, write status.json.
# Never run two updates at once; every run leaves a log in logs\.
# =============================================================================
param([string]$Base = "C:\AppServ\server_updates", [string]$TargetDir = "")
$ErrorActionPreference = "Stop"
if (-not $TargetDir) { $TargetDir = $PSScriptRoot }

New-Item -ItemType Directory -Force -Path $Base | Out-Null
$pendingFile = Join-Path $Base "pending.json"
$statusFile = Join-Path $Base "status.json"
$lockFile = Join-Path $Base "updater.lock"
$utf8 = New-Object Text.UTF8Encoding $false
[IO.File]::WriteAllText((Join-Path $Base "heartbeat.txt"), (Get-Date -Format "yyyy-MM-ddTHH:mm:ss"), $utf8)

function Write-Status([hashtable]$s) {
    [IO.File]::WriteAllText($statusFile, ($s | ConvertTo-Json -Depth 4), $utf8)
}

if (-not (Test-Path $pendingFile)) { exit 0 }
if (Test-Path $lockFile) {
    # A run older than 2 hours is a crashed run, not a running one
    if (((Get-Date) - (Get-Item $lockFile).LastWriteTime).TotalHours -lt 2) { exit 0 }
    Remove-Item -Force $lockFile
}

$pending = Get-Content $pendingFile -Raw -Encoding UTF8 | ConvertFrom-Json
$runAt = [datetime]::ParseExact($pending.run_at, "yyyy-MM-ddTHH:mm", $null)
if ((Get-Date) -lt $runAt) { exit 0 }

[IO.File]::WriteAllText($lockFile, "$PID", $utf8)
$logs = Join-Path $Base "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$log = Join-Path $logs ("update-{0}-{1:yyyyMMdd-HHmmss}.txt" -f $pending.version, (Get-Date))
$status = @{ state = "running"; version = $pending.version; started_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss");
             uploaded_by = $pending.uploaded_by; log = $log }
Write-Status $status
Remove-Item -Force $pendingFile

$exitCode = 1
$message = ""
try {
    $zip = $pending.file
    if (-not (Test-Path $zip)) { throw "Update file not found: $zip" }
    if ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLower() -ne $pending.sha256) { throw "Update file changed after upload" }
    $work = Join-Path $Base "work"
    if (Test-Path $work) { Remove-Item -Recurse -Force $work }
    Expand-Archive -LiteralPath $zip -DestinationPath $work
    $script = Get-ChildItem $work -Filter update.ps1 -Recurse | Select-Object -First 1
    if (-not $script) { throw "update.ps1 not found in the update" }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script.FullName -Yes -TargetDir $TargetDir *> $log
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) { $message = "The update stopped; the old version was kept (see the log)." }
} catch {
    $message = "$_"
    Add-Content -LiteralPath $log -Value "[ERROR] $message"
}

$tail = @()
if (Test-Path $log) { $tail = @(Get-Content $log -Tail 25 | ForEach-Object { [string]$_ }) }  # plain strings: PS 5 would serialise file metadata
$status.state = if ($exitCode -eq 0) { "done" } else { "failed" }
$status.finished_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
$status.message = $message
$status.log_tail = $tail
Write-Status $status
if ($exitCode -eq 0) {
    Remove-Item -Recurse -Force (Join-Path $Base "work") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $Base "incoming") -ErrorAction SilentlyContinue
}
Remove-Item -Force $lockFile -ErrorAction SilentlyContinue
exit 0
