@echo off
REM =============================================================================
REM publish_client_update.bat - offer a new client version to every laptop (SERVER laptop)
REM Usage: drag patch_vX.Y.Z.zip onto this file, or:
REM        publish_client_update.bat "<path to patch_vX.Y.Z.zip>"
REM See publish_client_update.ps1 for details.
REM =============================================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish_client_update.ps1" -Zip "%~1"
pause
