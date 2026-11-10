# =============================================================================
# build_update.ps1 - make the update folder for the server laptop (USB or network copy)
# Uses what build_release.bat already made in dist\release\<version>\:
#   CertificateManagerServer-<v>\   patch_v<v>.zip   CertificateManager-Setup-<v>.exe
# Output: dist\release\<v>\CertificateManagerUpdate-<v>\
#   Update.bat  update.ps1  VERSION.txt  checksums.txt
#   server\CertificateManagerServer-<v>\   client\patch_v<v>.zip  client\CertificateManager-Setup-<v>.exe
# Usage: powershell -ExecutionPolicy Bypass -File scripts\build_update.ps1 [-ReleaseDir <folder>] [-Notes "text"]
# =============================================================================
param([string]$ReleaseDir = "", [string]$Notes = "")
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

$verLine = Select-String -Path (Join-Path $root "app_version.py") -Pattern '^APP_VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
if (-not $verLine) { throw "APP_VERSION not found in app_version.py" }
$version = $verLine.Matches[0].Groups[1].Value
if (-not $ReleaseDir) { $ReleaseDir = Join-Path $root "dist\release\$version" }

$serverBundle = Join-Path $ReleaseDir "CertificateManagerServer-$version"
if (-not (Test-Path (Join-Path $serverBundle "setup_server.ps1"))) { throw "Server bundle not found: $serverBundle (run build_server_bundle.ps1 or build_release.bat first)" }

$out = Join-Path $ReleaseDir "CertificateManagerUpdate-$version"
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force -Path (Join-Path $out "server"), (Join-Path $out "client") | Out-Null

robocopy $serverBundle (Join-Path $out "server\CertificateManagerServer-$version") /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Copying the server bundle failed (robocopy code $LASTEXITCODE)" }

$found = 0
foreach ($name in "patch_v$version.zip", "CertificateManager-Setup-$version.exe") {
    $src = Join-Path $ReleaseDir $name
    if (-not (Test-Path $src)) { $src = Join-Path $root "dist\$name" }
    if (Test-Path $src) { Copy-Item -LiteralPath $src -Destination (Join-Path $out "client"); $found++ }
    else { Write-Host "[WARNING] $name not found: the update folder will not contain it" -ForegroundColor Yellow }
}
if ($Notes) { [IO.File]::WriteAllText((Join-Path $out "client\CHANGES.txt"), $Notes, (New-Object Text.UTF8Encoding $false)) }

Copy-Item -LiteralPath (Join-Path $root "installer\update\Update.bat"), (Join-Path $root "installer\update\update.ps1") -Destination $out
Set-Content -Encoding ascii -LiteralPath (Join-Path $out "VERSION.txt") -Value $version

# Checksums of every file, relative paths; update.ps1 checks them before changing anything
$prefix = $out.TrimEnd("\") + "\"
$lines = Get-ChildItem -LiteralPath $out -Recurse -File | Where-Object { $_.Name -ne "checksums.txt" } | Sort-Object FullName | ForEach-Object {
    "{0}  {1}" -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.FullName.Substring($prefix.Length)
}
Set-Content -Encoding utf8 -LiteralPath (Join-Path $out "checksums.txt") -Value $lines

# The same folder as one zip: upload it in Settings -> Server update (after the first USB install)
$zip = "$out.zip"
if (Test-Path $zip) { Remove-Item -Force $zip }
Compress-Archive -Path $out -DestinationPath $zip

Write-Output "UPDATE FOLDER READY: $out  ($($lines.Count) files, client files: $found of 2)"
Write-Output "  USB: copy the folder to the server laptop and double-click Update.bat there."
Write-Output "  Settings: upload $zip in Settings -> Server update."
