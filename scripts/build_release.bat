@echo off
setlocal

:: =============================================================================
:: scripts/build_release.bat - one command for a full client release
::   1. tests   2. dist\CertificateManager   3. update ZIP   4. installer   5. server bundle   6. SHA256SUMS.txt + install_package
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

:: Uncommitted edits would ship inside the installer (e.g. data\roles_config.json is a seed file).
set "DIRTY="
for /f "delims=" %%s in ('git status --porcelain --untracked-files^=no') do set "DIRTY=1"
if defined DIRTY (
    echo [ERROR] The working tree has uncommitted changes. Commit or stash them first:
    git status --short --untracked-files=no
    exit /b 1
)

echo [1/6] Tests...
py -3 -m pytest
if errorlevel 1 (
    echo [ERROR] Tests failed. Nothing was built.
    exit /b 1
)

echo [2/6] Program folder...
call scripts\build_client.bat /nopause
if errorlevel 1 exit /b 1

echo [3/6] Update ZIP...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\make_client_patch.ps1
if errorlevel 1 exit /b 1

echo [4/6] Installer...
if not exist "%OUT%" mkdir "%OUT%"
"%ISCC%" /Q "/DAppVersion=%VER%" "/O%OUT%" installer\client\CertificateManager.iss
if errorlevel 1 (
    echo [ERROR] Inno Setup failed.
    exit /b 1
)

echo [5/6] Server bundle...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scriptsuild_server_bundle.ps1 -OutDir "%OUT%"
if errorlevel 1 exit /b 1

echo [6/6] Checksums and install package...
move /y "dist\patch_v%VER%.zip" "%OUT%\" >nul
powershell.exe -NoProfile -Command "Get-ChildItem -LiteralPath '%OUT%' -File | Where-Object { $_.Name -ne 'SHA256SUMS.txt' } | ForEach-Object { '{0}  {1}' -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Name } | Set-Content -Encoding ascii -LiteralPath '%OUT%\SHA256SUMS.txt'"

set "PKG=%CD%\dist\install_package"
if exist "%PKG%" rmdir /s /q "%PKG%"
mkdir "%PKG%\client" "%PKG%\server"
copy /y "%OUT%\CertificateManager-Setup-%VER%.exe" "%PKG%\client\" >nul
copy /y "%OUT%\patch_v%VER%.zip" "%PKG%\server\" >nul
robocopy "%OUT%\CertificateManagerServer-%VER%" "%PKG%\server\CertificateManagerServer-%VER%" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 exit /b 1
echo RELEASE READY: %OUT%
echo INSTALL PACKAGE: %PKG%
exit /b 0
