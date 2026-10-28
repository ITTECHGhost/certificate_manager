@echo off
setlocal

:: =============================================================================
:: scripts/build_release.bat - one command for a full client release
::   1. tests   2. dist\CertificateManager   3. update ZIP   4. installer   5. SHA256SUMS.txt
:: Output: dist\release\<version>\   (version = APP_VERSION in app_version.py)
:: Needs Inno Setup 6 (ISCC.exe).
:: =============================================================================

cd /d "%~dp0.."

set "VER="
for /f "usebackq delims=" %%v in (`py -3 -c "import app_version; print(app_version.APP_VERSION)"`) do set "VER=%%v"
if not defined VER (
    echo [ERROR] Could not read APP_VERSION from app_version.py
    exit /b 1
)

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo [ERROR] Inno Setup 6 is not installed: ISCC.exe was not found.
    exit /b 1
)

set "OUT=%CD%\dist\release\%VER%"
echo === Release %VER% ===

echo [1/5] Tests...
py -3 -m pytest
if errorlevel 1 (
    echo [ERROR] Tests failed. Nothing was built.
    exit /b 1
)

echo [2/5] Program folder...
call scripts\build_client.bat /nopause
if errorlevel 1 exit /b 1

echo [3/5] Update ZIP...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\make_client_patch.ps1
if errorlevel 1 exit /b 1

echo [4/5] Installer...
if not exist "%OUT%" mkdir "%OUT%"
"%ISCC%" /Q "/DAppVersion=%VER%" "/O%OUT%" installer\client\CertificateManager.iss
if errorlevel 1 (
    echo [ERROR] Inno Setup failed.
    exit /b 1
)

echo [5/5] Checksums...
move /y "dist\patch_v%VER%.zip" "%OUT%\" >nul
powershell.exe -NoProfile -Command "Get-ChildItem -LiteralPath '%OUT%' -File | Where-Object { $_.Name -ne 'SHA256SUMS.txt' } | ForEach-Object { '{0}  {1}' -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Name } | Set-Content -Encoding ascii -LiteralPath '%OUT%\SHA256SUMS.txt'"

echo RELEASE READY: %OUT%
exit /b 0
