# =============================================================================
# test_install.ps1 - silent install / reinstall / uninstall test of the client installer.
# Uses folders under %TEMP% only; never touches the real data folder.
# Usage: powershell -ExecutionPolicy Bypass -File installer\client\test_install.ps1 -Setup <path to setup.exe>
# =============================================================================
param([Parameter(Mandatory = $true)][string]$Setup)
$ErrorActionPreference = "Stop"

$arabic = -join ([char[]](0x0628, 0x064A, 0x0627, 0x0646, 0x0627, 0x062A))
$root = Join-Path $env:TEMP "cm_install_test"
if (Test-Path $root) { Remove-Item -Recurse -Force $root }
$app = Join-Path $root "app folder"
$data = Join-Path $root "data $arabic"
$old = Join-Path $root "old portable"
New-Item -ItemType Directory -Force -Path (Join-Path $old "_internal"), (Join-Path $old "certs") | Out-Null
'{"host": "10.0.0.5", "port": 2030, "scheme": "https", "app_key": "k"}' | Set-Content -Encoding ascii -LiteralPath (Join-Path $old "server_config.json")
"CA" | Set-Content -Encoding ascii -LiteralPath (Join-Path $old "certs\college_ca.crt")
"OLD-DB" | Set-Content -Encoding ascii -LiteralPath (Join-Path $old "_internal\local_cache.db")

function Invoke-Setup([string]$From) {
    $arguments = @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/DIR=`"$app`"", "/DataDir=`"$data`"", "/OldDir=`"$From`"")
    $process = Start-Process -FilePath $Setup -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "setup exit code $($process.ExitCode)" }
}

$fails = @()
Invoke-Setup $old
if (-not (Test-Path -LiteralPath (Join-Path $app "CertificateManager.exe"))) { $fails += "exe missing after install" }
if ((Get-Content -LiteralPath (Join-Path $data "server_config.json") -Raw) -notmatch "10\.0\.0\.5") { $fails += "server_config.json not imported" }
if (-not (Test-Path -LiteralPath (Join-Path $data "certs\college_ca.crt"))) { $fails += "college_ca.crt not imported" }
if ((Get-Content -LiteralPath (Join-Path $data "local_cache.db") -Raw).Trim() -ne "OLD-DB") { $fails += "local_cache.db not imported" }

"NEW-DB" | Set-Content -Encoding ascii -LiteralPath (Join-Path $old "_internal\local_cache.db")
Invoke-Setup $old
if ((Get-Content -LiteralPath (Join-Path $data "local_cache.db") -Raw).Trim() -ne "OLD-DB") { $fails += "a second install overwrote local_cache.db" }

Start-Process -FilePath (Join-Path $app "unins000.exe") -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") -Wait | Out-Null
for ($i = 0; $i -lt 30 -and (Test-Path -LiteralPath (Join-Path $app "CertificateManager.exe")); $i++) { Start-Sleep -Seconds 1 }
if (Test-Path -LiteralPath (Join-Path $app "CertificateManager.exe")) { $fails += "uninstall left CertificateManager.exe" }
if (-not (Test-Path -LiteralPath (Join-Path $data "local_cache.db"))) { $fails += "uninstall deleted the data folder" }

if ($fails.Count -gt 0) { $fails | ForEach-Object { "FAIL: $_" }; exit 1 }
"ALL CHECKS PASSED"
