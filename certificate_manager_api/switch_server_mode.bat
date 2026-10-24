@echo off
REM =============================================================================
REM switch_server_mode.bat - switch the API service between HTTP and HTTPS.
REM Usage (or double-click and type the mode):
REM   switch_server_mode.bat https
REM   switch_server_mode.bat http
REM Writes server_settings.json and restarts the service. Asks for Administrator.
REM Clients must use the same mode ("scheme" in their server_config.json).
REM =============================================================================
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator rights...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%~1' -Verb RunAs"
    exit /b
)
setlocal
cd /d "%~dp0"
set "SVC=FastAPICertificateManager"
set "MODE=%~1"
if "%MODE%"=="" set /p "MODE=Type https or http and press Enter: "
if /i "%MODE%"=="https" (set "HTTPS=$true") else if /i "%MODE%"=="http" (set "HTTPS=$false") else (
    echo [ERROR] Mode must be https or http.
    pause
    exit /b 1
)
if /i "%MODE%"=="https" if not exist "certs\server.crt" (
    echo [ERROR] certs\server.crt not found. Run setup_server_https.bat first.
    pause
    exit /b 1
)

powershell -NoProfile -Command "$f = 'server_settings.json'; $s = [ordered]@{ port = 2030; https = $false }; if (Test-Path $f) { $old = Get-Content $f -Raw | ConvertFrom-Json; if ($old.port) { $s.port = [int]$old.port } }; $s.https = %HTTPS%; [IO.File]::WriteAllText((Resolve-Path '.').Path + '\' + $f, ($s | ConvertTo-Json), (New-Object Text.UTF8Encoding $false)); Write-Host ('server_settings.json -> ' + ($s | ConvertTo-Json -Compress))"

echo Restarting the service...
net stop %SVC% >nul 2>&1
net start %SVC%
if errorlevel 1 (
    echo [ERROR] The service did not start. See logs\api_service.log in this folder.
    pause
    exit /b 1
)
timeout /t 3 /nobreak >nul
powershell -NoProfile -Command "$s = Get-Content 'server_settings.json' -Raw | ConvertFrom-Json; if (Get-NetTCPConnection -LocalPort $s.port -State Listen -ErrorAction SilentlyContinue) { Write-Host ('[SUCCESS] API is running in ' + $(if ($s.https) {'HTTPS'} else {'HTTP'}) + ' mode on port ' + $s.port + '.') -ForegroundColor Green } else { Write-Host '[WARNING] Nothing is listening yet. Check logs\api_service.log.' -ForegroundColor Yellow }"
echo Remember: every client's server_config.json must use the same scheme (%MODE%).
pause
