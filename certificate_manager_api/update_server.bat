@echo off
REM =============================================================================
REM update_server.bat - install a new version of the API code on the SERVER laptop.
REM Usage: update_server.bat <folder with the new certificate_manager_api files>
REM   e.g. update_server.bat "E:\release\certificate_manager_api"
REM Or double-click and type/paste the folder path.
REM
REM Stops the service, copies the new code here, starts the service again.
REM NEVER overwritten (this server's own settings and data):
REM   certs\  client_package\  logs\  templets\  app_keys.json  server_settings.json
REM   config.py (database login)  update_server.bat (this file)
REM Asks for Administrator.
REM =============================================================================
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator rights...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '\"%~1\"' -Verb RunAs"
    exit /b
)
setlocal
set "SVC=FastAPICertificateManager"
set "DEST=%~dp0"
if "%DEST:~-1%"=="\" set "DEST=%DEST:~0,-1%"
cd /d "%DEST%"
set "SRC=%~1"
if "%SRC%"=="" set /p "SRC=Folder with the NEW certificate_manager_api files: "
set "SRC=%SRC:"=%"
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"

if not exist "%SRC%\main.py" (
    echo [ERROR] "%SRC%\main.py" not found. Give the folder that contains the new main.py.
    pause
    exit /b 1
)
if /i "%SRC%"=="%DEST%" (
    echo [ERROR] The source folder is this folder. Copy the new files somewhere else first.
    pause
    exit /b 1
)

echo Backing up the current code to "%DEST%\_backup_before_update"...
robocopy "%DEST%" "%DEST%\_backup_before_update" *.py *.bat *.ps1 *.md /S /XD _backup_before_update certs client_package logs templets __pycache__ /NFL /NDL /NJH /NJS /R:1 /W:1 >nul

echo Stopping the service...
net stop %SVC% >nul 2>&1

echo Copying the new code...
robocopy "%SRC%" "%DEST%" /E /XD certs client_package logs templets __pycache__ _backup_before_update /XF app_keys.json server_settings.json config.py update_server.bat *.log /NFL /NDL /NJH /NP /R:2 /W:2
if %errorlevel% geq 8 (
    echo [ERROR] Copy failed ^(robocopy code %errorlevel%^). Restoring the backup...
    robocopy "%DEST%\_backup_before_update" "%DEST%" /E /NFL /NDL /NJH /NJS /R:1 /W:1 >nul
    net start %SVC%
    pause
    exit /b 1
)

echo Starting the service...
net start %SVC%
if errorlevel 1 (
    echo [ERROR] The service did not start with the new code. See logs\api_service.log.
    echo To roll back: copy the files from _backup_before_update back into this folder and start the service.
    pause
    exit /b 1
)
timeout /t 3 /nobreak >nul
powershell -NoProfile -Command "$p = 2030; if (Test-Path 'server_settings.json') { $p = (Get-Content 'server_settings.json' -Raw | ConvertFrom-Json).port }; if (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) { Write-Host ('[SUCCESS] Server updated and running on port ' + $p + '.') -ForegroundColor Green } else { Write-Host '[WARNING] Nothing is listening yet. Check logs\api_service.log.' -ForegroundColor Yellow }"
pause
