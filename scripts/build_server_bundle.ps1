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
robocopy (Join-Path $root "installer\server\prereqs") (Join-Path $bundle "prereqs") /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy of the prereqs failed (code $LASTEXITCODE)" }

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
