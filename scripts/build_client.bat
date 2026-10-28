@echo off
setlocal

:: =============================================================================
:: scripts/build_client.bat - build the client program folder dist\CertificateManager
:: Usage: build_client.bat             (waits for a key at the end)
::        build_client.bat /nopause    (used by scripts\build_release.bat)
:: =============================================================================

set "NOPAUSE="
if /i "%~1"=="/nopause" set "NOPAUSE=1"

cd /d "%~dp0.."

echo [1/4] Checking Python...
py -3 -V
if errorlevel 1 (
    echo [ERROR] The Python launcher py was not found. Install Python 3.14 for all users.
    if not defined NOPAUSE pause
    exit /b 1
)

echo [2/4] Cleaning previous build output...
if exist "dist\CertificateManager" rmdir /s /q "dist\CertificateManager"
if exist "build\CertificateManager" rmdir /s /q "build\CertificateManager"

echo [3/4] Running PyInstaller...
py -3 -m PyInstaller --noconfirm --log-level WARN client.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller failed. See the messages above.
    if not defined NOPAUSE pause
    exit /b 1
)

echo [4/4] Checking the output...
if not exist "dist\CertificateManager\CertificateManager.exe" (
    echo [ERROR] dist\CertificateManager\CertificateManager.exe was not created.
    if not defined NOPAUSE pause
    exit /b 1
)
echo BUILD SUCCESSFUL: %CD%\dist\CertificateManager\CertificateManager.exe
if not defined NOPAUSE pause
exit /b 0
