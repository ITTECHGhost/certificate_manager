@echo off
setlocal enabledelayedexpansion

:: =============================================================================
:: scripts/build_client.bat — Build Standalone Client Package
:: =============================================================================

echo =======================================================================
echo  Certificate Manager — Client Executable Build Pipeline
echo =======================================================================

set "PYTHON_EXE=C:\Users\IT_TECK\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

echo [1/4] Checking Python environment...
"%PYTHON_EXE%" -V
if errorlevel 1 (
    echo [ERROR] Python interpreter not accessible!
    pause
    exit /b 1
)

echo [2/4] Cleaning previous build artifacts...
if exist "dist\CertificateManager" (
    rmdir /s /q "dist\CertificateManager"
)
if exist "build\CertificateManager" (
    rmdir /s /q "build\CertificateManager"
)

echo [3/4] Compiling client executable via PyInstaller...
"%PYTHON_EXE%" -m PyInstaller --noconfirm client.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller compilation failed! Check output logs above.
    pause
    exit /b 1
)

echo [4/4] Verifying packaged output...
if exist "dist\CertificateManager\CertificateManager.exe" (
    echo =======================================================================
    echo  BUILD SUCCESSFUL!
    echo  Standalone distribution ready at:
    echo  %PROJECT_ROOT%\dist\CertificateManager\CertificateManager.exe
    echo =======================================================================
) else (
    echo [ERROR] Output executable was not found in dist\CertificateManager!
    pause
    exit /b 1
)

pause
