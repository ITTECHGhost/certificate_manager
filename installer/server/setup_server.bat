@echo off
:: =============================================================================
:: setup_server.bat - first installation AND later updates of the API on the server laptop.
:: Double-click it; Windows asks for Administrator rights. Safe to run again.
:: The work is done by setup_server.ps1 in this folder.
:: =============================================================================
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator rights...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_server.ps1" %*
pause
