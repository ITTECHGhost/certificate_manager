@echo off
REM =============================================================================
REM Update.bat - update this SERVER laptop from this folder (USB or network copy).
REM Double-click it. It asks for Administrator, then:
REM   checks the files, updates the API + database (backup first, roll-back on error),
REM   and offers the new client version to every laptop.
REM =============================================================================
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator rights...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0update.ps1" %*
set "RC=%errorlevel%"
echo.
pause
exit /b %RC%
