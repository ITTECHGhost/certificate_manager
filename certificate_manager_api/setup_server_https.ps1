# =============================================================================
# setup_server_https.ps1 - One-time HTTPS + application key setup on the SERVER laptop
# Started by setup_server_https.bat (double-click). Safe to run again, e.g. after
# the server IP changes: the CA and the app key are kept, only the server
# certificate and the client package are renewed.
#
#   1. Asks for the server laptop's fixed IP
#   2. Creates the college CA (first run only) and the server certificate
#   3. Creates app_keys.json with a random key for the certificate program (first run only)
#   4. Builds client_package\ (server_config.json + certs\college_ca.crt) to copy to every client
#   5. Checks that Windows Firewall lets clients reach port 2030
# =============================================================================
param([string]$Ip = "")

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$port = 2030
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }

# ---------------------------------------------------------------- 1. Server IP
Write-Step "1/5  Server IP address"
$ips = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike "169.254*" -and $_.IPAddress -ne "127.0.0.1" } |
    Select-Object -ExpandProperty IPAddress)
if ($ips.Count -gt 0) { Write-Host "IP addresses on this laptop: $($ips -join ', ')" }
if (-not $Ip) {
    $default = if ($ips.Count -gt 0) { $ips[0] } else { "" }
    $Ip = Read-Host "Type this server laptop's FIXED IP address (press Enter for $default)"
    if (-not $Ip) { $Ip = $default }
}
$parsed = $null
if (-not [System.Net.IPAddress]::TryParse($Ip, [ref]$parsed)) {
    Write-Host "[ERROR] '$Ip' is not a valid IP address." -ForegroundColor Red
    exit 1
}
if ($ips.Count -gt 0 -and $ips -notcontains $Ip) {
    Write-Host "[WARNING] $Ip is not an address of this laptop right now. Fix the IP in Windows first, or continue if you will set it later." -ForegroundColor Yellow
}

# ---------------------------------------------------------------- 2. Certificates
Write-Step "2/5  HTTPS certificates for $Ip"
& cmd.exe /c "`"$here\make_https_cert.bat`" $Ip"
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Certificate creation failed." -ForegroundColor Red; exit 1 }
$caCrt = Join-Path $here "certs\college_ca.crt"

# ---------------------------------------------------------------- 3. App key
Write-Step "3/5  Application key"
$keysFile = Join-Path $here "app_keys.json"
$appKey = ""
$enforce = $false
if (Test-Path $keysFile) {
    $keys = Get-Content $keysFile -Raw -Encoding UTF8 | ConvertFrom-Json
    $enforce = [bool]$keys.enforce
    if ($keys.apps -and $keys.apps.certificate_manager) { $appKey = [string]$keys.apps.certificate_manager }
}
if (-not $appKey) {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $appKey = [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
    $json = [ordered]@{ enforce = $enforce; apps = [ordered]@{ certificate_manager = $appKey } } | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText($keysFile, $json, $utf8NoBom)
    Write-Host "Created app_keys.json with a new key (audit mode: not blocking yet)."
} else {
    Write-Host "Kept the existing key in app_keys.json (enforce = $enforce)."
}

# ---------------------------------------------------------------- 4. Client package
Write-Step "4/5  Client package"
$pkg = Join-Path $here "client_package"
New-Item -ItemType Directory -Force -Path (Join-Path $pkg "certs") | Out-Null
Copy-Item $caCrt (Join-Path $pkg "certs\college_ca.crt") -Force
$clientCfg = [ordered]@{
    host      = $Ip
    port      = $port
    scheme    = "https"
    secret    = "certificate_manager_secret_key"
    timeout   = 5.0
    auto_sync = $true
    ca_cert   = "certs/college_ca.crt"
    app_key   = $appKey
    api_url   = "https://${Ip}:$port"
} | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText((Join-Path $pkg "server_config.json"), $clientCfg, $utf8NoBom)
$readme = @"
Certificate Manager - client connection files
Server: https://${Ip}:$port   (created $(Get-Date -Format 'yyyy-MM-dd HH:mm'))

On EVERY client laptop, copy into the Certificate Manager program folder
(the folder that has the program and its current server_config.json):
  server_config.json        -> replace the existing one
  certs\college_ca.crt      -> into a folder named certs (create it if missing)
Then restart the program.

server_config.json contains the program's secret key. Do not share it outside the college.
"@
[System.IO.File]::WriteAllText((Join-Path $pkg "README.txt"), $readme, $utf8NoBom)
Write-Host "Client files are in: $pkg"

# ---------------------------------------------------------------- 5. Firewall
Write-Step "5/5  Windows Firewall (port $port)"
$rule = Get-NetFirewallRule -DisplayName "Certificate Manager API" -ErrorAction SilentlyContinue
if ($rule) {
    Write-Host "Firewall rule 'Certificate Manager API' exists."
} else {
    Write-Host "No firewall rule found. Other laptops may not reach this server until you allow port $port." -ForegroundColor Yellow
    Write-Host "Open Command Prompt AS ADMINISTRATOR and run:"
    Write-Host "  netsh advfirewall firewall add rule name=`"Certificate Manager API`" dir=in action=allow protocol=TCP localport=$port"
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host " DONE. Next steps (details: SERVER_SETUP_GUIDE.md):" -ForegroundColor Green
Write-Host "  1. Copy client_package\ files to every client laptop (see client_package\README.txt)"
Write-Host "  2. Switch the server to HTTPS:  switch_server_mode.bat https"
Write-Host "     (the same day the clients get the new server_config.json)"
Write-Host "  3. Later, when every client sends the key: set `"enforce`": true in app_keys.json"
Write-Host "     and restart the service (switch_server_mode.bat https)"
Write-Host "================================================================" -ForegroundColor Green
exit 0
