# =============================================================================
# test_setup_server.ps1 - runs setup_server.ps1 against folders under %TEMP% only
# (no service, firewall, pip or MySQL). Never touches C:\AppServ.
# Usage: powershell -ExecutionPolicy Bypass -File installer\server\test_setup_server.ps1 -Bundle <bundle folder>
# =============================================================================
param([Parameter(Mandatory = $true)][string]$Bundle)
$ErrorActionPreference = "Stop"
$root = Join-Path $env:TEMP "cm_srv_test"
if (Test-Path $root) { Remove-Item -Recurse -Force $root }
$setup = Join-Path $Bundle "setup_server.ps1"
$common = @("-SkipPip", "-SkipService", "-SkipFirewall", "-SkipDbCheck")
$fails = @()

# Case A: a configured server is updated twice; its own files must not change.
$a = Join-Path $root "configured server"
New-Item -ItemType Directory -Force -Path (Join-Path $a "certs"), (Join-Path $a "templets") | Out-Null
'{"host": "localhost", "user": "u", "password": "p", "database": "certificate_manager"}' | Set-Content -Encoding ascii -LiteralPath (Join-Path $a "db_config.json")
'{"enforce": true, "apps": {"x": "y"}}' | Set-Content -Encoding ascii -LiteralPath (Join-Path $a "app_keys.json")
'{"port": 2030, "https": true}' | Set-Content -Encoding ascii -LiteralPath (Join-Path $a "server_settings.json")
"KEY" | Set-Content -Encoding ascii -LiteralPath (Join-Path $a "certs\server.key")
"CUSTOM" | Set-Content -Encoding ascii -LiteralPath (Join-Path $a "templets\custom.docx")
"old main" | Set-Content -Encoding ascii -LiteralPath (Join-Path $a "main.py")
$keep = @("db_config.json", "app_keys.json", "server_settings.json", "certs\server.key", "templets\custom.docx")
$before = @{}
foreach ($f in $keep) { $before[$f] = (Get-FileHash -LiteralPath (Join-Path $a $f)).Hash }
foreach ($run in 1, 2) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setup -TargetDir $a @common | Out-Null
    if ($LASTEXITCODE -ne 0) { $fails += "case A run $run exit code $LASTEXITCODE" }
}
foreach ($f in $keep) { if ((Get-FileHash -LiteralPath (Join-Path $a $f)).Hash -ne $before[$f]) { $fails += "case A changed $f" } }
if ((Get-Content -LiteralPath (Join-Path $a "main.py") -Raw) -match "old main") { $fails += "case A main.py was not updated" }
if (-not (Test-Path -LiteralPath (Join-Path $a ".htaccess"))) { $fails += "case A .htaccess missing" }
if (-not (Test-Path -LiteralPath (Join-Path $a "templets\templates_config.json"))) { $fails += "case A templates were not added" }

# Case B: an old server whose config.py still holds the login gets db_config.json from it.
$b = Join-Path $root "old server"
New-Item -ItemType Directory -Force -Path $b | Out-Null
"old main" | Set-Content -Encoding ascii -LiteralPath (Join-Path $b "main.py")
@("class DBConfig:", "    DB_HOST = 'dbhost'", "    DB_USER = 'olduser'", "    DB_PASSWORD = 'oldpass'", "    DB_NAME = 'certificate_manager'") | Set-Content -Encoding ascii -LiteralPath (Join-Path $b "config.py")
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $setup -TargetDir $b @common | Out-Null
if ($LASTEXITCODE -ne 0) { $fails += "case B exit code $LASTEXITCODE" }
$migrated = Get-Content -LiteralPath (Join-Path $b "db_config.json") -Raw | ConvertFrom-Json
if ($migrated.host -ne "dbhost" -or $migrated.user -ne "olduser" -or $migrated.password -ne "oldpass") { $fails += "case B db_config.json was not migrated" }
if ((Get-Content -LiteralPath (Join-Path $b "config.py") -Raw) -match "oldpass") { $fails += "case B config.py still holds the password" }

if ($fails.Count -gt 0) { $fails | ForEach-Object { "FAIL: $_" }; exit 1 }
"ALL CHECKS PASSED"
