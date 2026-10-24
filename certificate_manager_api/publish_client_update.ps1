# =============================================================================
# publish_client_update.ps1 - offer a new client version to every laptop (SERVER laptop)
# Started by publish_client_update.bat. Copies patch_vX.Y.Z.zip into the updates
# folder and writes version.json (version, SHA-256, size). No restart needed.
# =============================================================================
param([string]$Zip = "", [string]$Notes = $null, [string]$BaseDir = "")

$ErrorActionPreference = "Stop"
if (-not $Zip) { $Zip = Read-Host "Path to the patch ZIP (patch_vX.Y.Z.zip)" }
$Zip = $Zip.Trim('"', ' ')
if (-not (Test-Path $Zip)) { Write-Host "[ERROR] Not found: $Zip" -ForegroundColor Red; exit 1 }

$name = Split-Path $Zip -Leaf
if ($name -notmatch '^patch_v(\d+\.\d+\.\d+)\.zip$') {
    Write-Host "[ERROR] The file name must look like patch_v2.1.0.zip (made by scripts\make_client_patch.bat)." -ForegroundColor Red
    exit 1
}
$version = $Matches[1]

# Same folder the API's /api/update endpoints read (routers/updates.py)
$base = if ($BaseDir) { $BaseDir } elseif (Test-Path "C:\AppServ\www") { "C:\AppServ\www\updates" } else { Join-Path $PSScriptRoot "updates" }
$patches = Join-Path $base "patches"
New-Item -ItemType Directory -Force -Path $patches | Out-Null
$target = Join-Path $patches $name
Copy-Item $Zip $target -Force

$manifestPath = Join-Path $base "version.json"
$minimum = "2.0.0"
if (Test-Path $manifestPath) {
    try {
        $old = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($old.minimum_supported_version) { $minimum = [string]$old.minimum_supported_version }
    } catch { }
}
if ($null -eq $Notes) { $Notes = Read-Host "Short description of this update (optional)" }

$manifest = [ordered]@{
    latest_version            = $version
    minimum_supported_version = $minimum
    release_date              = (Get-Date -Format "yyyy-MM-dd")
    changelog_ar              = $Notes
    changelog_en              = $Notes
    patch_filename            = $name
    download_url              = "/api/update/download/$name"
    sha256                    = (Get-FileHash $target -Algorithm SHA256).Hash.ToLower()
    size_bytes                = (Get-Item $target).Length
    mandatory                 = $false
}
[System.IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json), (New-Object System.Text.UTF8Encoding($false)))
Write-Host "[SUCCESS] Version $version published. Clients can update from Settings > Check for updates." -ForegroundColor Green
exit 0
