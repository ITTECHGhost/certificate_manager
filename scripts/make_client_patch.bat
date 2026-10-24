@echo off
REM =============================================================================
REM make_client_patch.bat - make the client update ZIP (run on the developer laptop
REM after scripts\build_client.bat). See make_client_patch.ps1 for details.
REM =============================================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0make_client_patch.ps1"
pause
