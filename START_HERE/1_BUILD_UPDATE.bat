@echo off
REM =============================================================================
REM 1_BUILD_UPDATE.bat - make a new update. Double-click it.
REM Asks for the new version, saves it, builds everything, and puts the result in
REM START_HERE\output\  (the folder for USB + the .zip for the Settings page).
REM =============================================================================
setlocal
cd /d "%~dp0.."

for /f "usebackq delims=" %%v in (`py -3 -c "import app_version; print(app_version.APP_VERSION)"`) do set "CUR=%%v"
echo Current version: %CUR%
set "NEW="
set /p "NEW=New version (for example 2.3.0): "
if "%NEW%"=="" (
    echo [ERROR] No version given. The server only accepts a version newer than it has.
    pause
    exit /b 1
)

py -3 scripts\set_version.py %NEW%
if errorlevel 1 (
    pause
    exit /b 1
)
set "GOT="
for /f "usebackq delims=" %%v in (`py -3 -c "import app_version; print(app_version.APP_VERSION)"`) do set "GOT=%%v"
if not "%GOT%"=="%NEW%" (
    echo [ERROR] app_version.py still says %GOT%, not %NEW%. Nothing was built.
    pause
    exit /b 1
)
git add app_version.py
git commit -q -m "release: %NEW%"

call scripts\build_release.bat
if errorlevel 1 (
    echo [ERROR] The build failed. Nothing was copied to START_HERE\output.
    pause
    exit /b 1
)

set "OUTDIR=%~dp0output"
if exist "%OUTDIR%" rmdir /s /q "%OUTDIR%"
mkdir "%OUTDIR%"
robocopy "dist\release\%NEW%\CertificateManagerUpdate-%NEW%" "%OUTDIR%\CertificateManagerUpdate-%NEW%" /E /NFL /NDL /NJH /NJS /NP >nul
copy /y "dist\release\%NEW%\CertificateManagerUpdate-%NEW%.zip" "%OUTDIR%\" >nul
echo.
echo READY in %OUTDIR%:
echo   CertificateManagerUpdate-%NEW%\      copy to the server by USB, run Update.bat there
echo   CertificateManagerUpdate-%NEW%.zip   or upload it in Settings - Server update
explorer "%OUTDIR%"
pause
