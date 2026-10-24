@echo off
REM =============================================================================
REM install_service.bat - install (or update) the FastAPI Windows service and start it.
REM Double-click; Windows asks for Administrator. Safe to run again.
REM   - service starts automatically with Windows and restarts itself if it fails
REM   - mode (HTTP/HTTPS) and port come from server_settings.json
REM     (change with switch_server_mode.bat)
REM =============================================================================
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator rights...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
setlocal
cd /d "%~dp0"
set "SVC=FastAPICertificateManager"

call :find_python
if not defined PYTHON_EXE (
    echo [ERROR] Python was not found. Install Python, or set PYTHON_EXE at the top of find_python in this file.
    pause
    exit /b 1
)
echo Using Python: %PYTHON_EXE%

if not exist "server_settings.json" (
    > "server_settings.json" echo {"port": 2030, "https": false}
    echo Created server_settings.json ^(HTTP on port 2030^).
)

echo Stopping the old service ^(if running^)...
net stop %SVC% >nul 2>&1

echo Installing / updating the service...
"%PYTHON_EXE%" fastapi_service.py --startup auto install >nul 2>&1
if errorlevel 1 "%PYTHON_EXE%" fastapi_service.py --startup auto update
if errorlevel 1 (
    echo [ERROR] Service installation failed. Is pywin32 installed?  "%PYTHON_EXE%" -m pip install pywin32
    pause
    exit /b 1
)

REM Restart automatically after a failure (5 s, 10 s, then 30 s)
sc failure %SVC% reset= 86400 actions= restart/5000/restart/10000/restart/30000 >nul
sc failureflag %SVC% 1 >nul

echo Starting the service...
net start %SVC%
if errorlevel 1 (
    echo [ERROR] The service did not start. See logs\api_service.log in this folder.
    pause
    exit /b 1
)
call :check_port
pause
exit /b 0

:find_python
set "PYTHON_EXE="
for /f "delims=" %%P in ('where python 2^>nul ^| findstr /v /i "WindowsApps"') do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
if not defined PYTHON_EXE if exist "C:\Users\IT_TECK\AppData\Local\Python\pythoncore-3.14-64\python.exe" set "PYTHON_EXE=C:\Users\IT_TECK\AppData\Local\Python\pythoncore-3.14-64\python.exe"
exit /b 0

:check_port
timeout /t 3 /nobreak >nul
powershell -NoProfile -Command "$s = Get-Content 'server_settings.json' -Raw | ConvertFrom-Json; if (Get-NetTCPConnection -LocalPort $s.port -State Listen -ErrorAction SilentlyContinue) { Write-Host ('[SUCCESS] API is listening on port ' + $s.port + ' (' + $(if ($s.https) {'HTTPS'} else {'HTTP'}) + ').') -ForegroundColor Green } else { Write-Host '[WARNING] Nothing is listening yet. Check logs\api_service.log in this folder.' -ForegroundColor Yellow }"
exit /b 0
