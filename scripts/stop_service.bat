@echo off
echo Stopping FastAPI Certificate Manager Windows Service (requires Administrator privileges)...
net stop FastAPICertificateManager
if errorlevel 1 (
    echo [ERROR] Failed to stop service. Make sure Command Prompt is run as Administrator.
) else (
    echo [SUCCESS] FastAPICertificateManager stopped.
)
pause
