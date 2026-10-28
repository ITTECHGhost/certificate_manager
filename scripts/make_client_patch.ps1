# =============================================================================
# make_client_patch.ps1 - build the update ZIP for client laptops (developer laptop)
# Run through make_client_patch.bat AFTER scripts\build_client.bat.
#
# Version = APP_VERSION in app_version.py (raise it before building,
# otherwise clients keep seeing the same version and never update).
# The ZIP holds the contents of dist\CertificateManager EXCEPT server_config.json,
# so an update never replaces a laptop's server address, HTTPS setting or app key.
# =============================================================================
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$distApp = Join-Path $root "dist\CertificateManager"

$verLine = Select-String -Path (Join-Path $root "app_version.py") -Pattern '^APP_VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
if (-not $verLine) { Write-Host "[ERROR] APP_VERSION not found in app_version.py" -ForegroundColor Red; exit 1 }
$version = $verLine.Matches[0].Groups[1].Value

if (-not (Test-Path (Join-Path $distApp "CertificateManager.exe"))) {
    Write-Host "[ERROR] $distApp\CertificateManager.exe not found. Run scripts\build_client.bat first." -ForegroundColor Red
    exit 1
}

$zipPath = Join-Path $root "dist\patch_v$version.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
$count = 0
$skipped = @()
try {
    Get-ChildItem $distApp -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($distApp.Length + 1)
        if ($_.Name -ieq "server_config.json") { $skipped += $rel; return }
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $_.FullName, $rel.Replace("\", "/"), [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
        $count++
    }
} finally {
    $zip.Dispose()
}

$hash = (Get-FileHash $zipPath -Algorithm SHA256).Hash.ToLower()
$sizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host ""
Write-Host "[SUCCESS] Client update v$version" -ForegroundColor Green
Write-Host "  File:    $zipPath  ($sizeMb MB, $count files)"
Write-Host "  SHA-256: $hash"
if ($skipped.Count) { Write-Host "  Left out (laptop settings): $($skipped -join ', ')" }
Write-Host ""
Write-Host "Next: copy the ZIP to the server laptop and run there:"
Write-Host "  certificate_manager_api\publish_client_update.bat `"<path to patch_v$version.zip>`""
exit 0
