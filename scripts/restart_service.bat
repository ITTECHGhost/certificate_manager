@echo off
echo Restarting FastAPI Certificate Manager Windows Service (requires Administrator privileges)...
net stop FastAPICertificateManager
timeout /t 1 /nobreak >nul
net start FastAPICertificateManager
if errorlevel 1 (
    echo [ERROR] Failed to restart service. Make sure Command Prompt is run as Administrator.
) else (
    echo [SUCCESS] FastAPICertificateManager successfully restarted.
)
pause
