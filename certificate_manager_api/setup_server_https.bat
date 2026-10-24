@echo off
REM =============================================================================
REM setup_server_https.bat - double-click on the SERVER laptop to set up HTTPS
REM and the application key. Full guide: SERVER_HTTPS_SETUP.md (same folder)
REM =============================================================================
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_server_https.ps1" %*
echo.
pause
