@echo off
setlocal enabledelayedexpansion

:: =============================================================================
:: scripts/apply_patch.bat — Bootstrap OTA Patch Applicator
:: Arguments:
::   %1 = PID of the running Certificate Manager process
::   %2 = Full path to the downloaded patch ZIP file
::   %3 = Application root directory
::   %4 = Application executable name (e.g. CertificateManager.exe or main.py)
::   %5 = Folder for system_log.txt (optional; default: the application folder)
:: =============================================================================

set "TARGET_PID=%~1"
set "ZIP_PATH=%~2"
set "APP_DIR=%~3"
set "EXE_NAME=%~4"
set "LOG_DIR=%~5"
if "%LOG_DIR%"=="" set "LOG_DIR=%APP_DIR%"

if "%TARGET_PID%"=="" goto USAGE_ERROR
if "%ZIP_PATH%"=="" goto USAGE_ERROR
if "%APP_DIR%"=="" goto USAGE_ERROR

set "LOG_FILE=%LOG_DIR%\system_log.txt"
echo [%date% %time%] [OTA_PATCH] Starting update bootstrap for PID %TARGET_PID% >> "%LOG_FILE%"

:: 1. Wait for the main application process to terminate
echo Waiting for Certificate Manager process (PID: %TARGET_PID%) to exit...
:WAIT_LOOP
tasklist /FI "PID eq %TARGET_PID%" 2>NUL | find /I "%TARGET_PID%" >NUL
if not errorlevel 1 (
    timeout /t 1 /nobreak >NUL
    goto WAIT_LOOP
)

echo Certificate Manager closed. Extracting update package...
echo [%date% %time%] [OTA_PATCH] Certificate Manager process stopped. Unpacking patch from %ZIP_PATH% >> "%LOG_FILE%"

:: 2. Keep this laptop's own connection settings (server address, HTTPS, app key, college CA).
::    A patch must never replace them with the settings of the PC that built it.
set "KEEP_DIR=%TEMP%\cm_keep_%RANDOM%%RANDOM%"
mkdir "%KEEP_DIR%" >NUL 2>&1
if exist "%APP_DIR%\server_config.json" copy /y "%APP_DIR%\server_config.json" "%KEEP_DIR%\" >NUL
if exist "%APP_DIR%\certs" xcopy /e /i /y /q "%APP_DIR%\certs" "%KEEP_DIR%\certs" >NUL

:: 3. Extract ZIP archive overwriting existing application files
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%APP_DIR%' -Force"
if errorlevel 1 (
    echo [ERROR] Failed to extract update package!
    echo [%date% %time%] [OTA_PATCH] [ERROR] Extraction failed for %ZIP_PATH% >> "%LOG_FILE%"
    pause
    exit /b 1
)

:: 4. Put the laptop's own settings back
if exist "%KEEP_DIR%\server_config.json" copy /y "%KEEP_DIR%\server_config.json" "%APP_DIR%\server_config.json" >NUL
if exist "%KEEP_DIR%\certs" xcopy /e /i /y /q "%KEEP_DIR%\certs" "%APP_DIR%\certs" >NUL
rmdir /s /q "%KEEP_DIR%" >NUL 2>&1
echo [%date% %time%] [OTA_PATCH] Kept local server_config.json and certs. >> "%LOG_FILE%"

echo Update files successfully extracted.
echo [%date% %time%] [OTA_PATCH] Extraction successful. Cleaning up temporary files. >> "%LOG_FILE%"

:: 5. Clean up the patch archive
if exist "%ZIP_PATH%" (
    del /f /q "%ZIP_PATH%" >NUL 2>&1
)

:: Test hook: tests/test_updater.py sets CM_PATCH_NO_RELAUNCH=1 to stop here.
if "%CM_PATCH_NO_RELAUNCH%"=="1" exit /b 0

:: 6. Relaunch the updated application
echo Relaunching application...
echo [%date% %time%] [OTA_PATCH] Relaunching application: %EXE_NAME% >> "%LOG_FILE%"

cd /d "%APP_DIR%"

if /I "%EXE_NAME:~-4%"==".exe" (
    start "" "%APP_DIR%\%EXE_NAME%"
) else (
    start "" python "%APP_DIR%\%EXE_NAME%"
)

echo [%date% %time%] [OTA_PATCH] Update workflow complete. >> "%LOG_FILE%"
:: This copy lives in %TEMP% (services/updater.py): delete it on the way out
(goto) 2>nul & del "%~f0"

:USAGE_ERROR
echo [ERROR] Missing required arguments for apply_patch.bat.
echo Usage: apply_patch.bat PID ZIP_PATH APP_DIR EXE_NAME
exit /b 1
