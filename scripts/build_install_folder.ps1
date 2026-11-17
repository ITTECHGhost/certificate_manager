# =============================================================================
# build_install_folder.ps1 - the folder handed to user laptops (not the server)
# Output: <ReleaseDir>\CertificateManager-Install-<v>\
#   CertificateManager-Setup-<v>.exe
#   client_package\server_config.json
#   client_package\certs\college_ca.crt
#   <Arabic readme>.txt
# Setup imports client_package\ next to itself, so the user only presses Next and logs in.
# client_package comes from the server (setup_server_https.ps1), never from the repo.
# Its contents are secrets: they are copied, never printed or hashed into SHA256SUMS.txt.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\build_install_folder.ps1 -ReleaseDir <dist\release\v> [-ClientPackage <folder>]
# =============================================================================
param(
    [Parameter(Mandatory = $true)][string]$ReleaseDir,
    [string]$ClientPackage = "F:\CR_PY\client_package"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$version = (& py -3 -c "import sys; sys.path.insert(0, r'$root'); import app_version; print(app_version.APP_VERSION)").Trim()
$setup = Join-Path $ReleaseDir "CertificateManager-Setup-$version.exe"
if (-not (Test-Path -LiteralPath $setup)) { throw "Setup not found: $setup" }

$cfg = Join-Path $ClientPackage "server_config.json"
$ca = Join-Path $ClientPackage "certs\college_ca.crt"
foreach ($f in @($cfg, $ca)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "client_package is incomplete: $f is missing. Copy client_package from the server (C:\AppServ\www\certificate_manager_api\client_package) and pass -ClientPackage <folder>."
    }
}
# Check it is a real package (an address and a key) without printing either value
$json = Get-Content -LiteralPath $cfg -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $json.host -or -not $json.app_key -or "$($json.app_key)" -eq "ask-the-server-admin-for-this-key") {
    throw "server_config.json in $ClientPackage has no server address or no program key."
}

$out = Join-Path $ReleaseDir "CertificateManager-Install-$version"
if (Test-Path -LiteralPath $out) { Remove-Item -LiteralPath $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Join-Path $out "client_package\certs") | Out-Null
Copy-Item -LiteralPath $setup -Destination $out
Copy-Item -LiteralPath $cfg -Destination (Join-Path $out "client_package\server_config.json")
Copy-Item -LiteralPath $ca -Destination (Join-Path $out "client_package\certs\college_ca.crt")

# Readme name in Arabic, built from code points (this script stays ASCII for PowerShell 5.1)
$name = -join ([char[]](0x627, 0x642, 0x631, 0x623, 0x646, 0x64A)) + ".txt"
Copy-Item -LiteralPath (Join-Path $root "installer\client\README_ar.txt") -Destination (Join-Path $out $name)

Write-Host "Install folder: $out (server: $($json.host))"
