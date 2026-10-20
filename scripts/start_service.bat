@echo off
echo Starting FastAPI Certificate Manager Windows Service (requires Administrator privileges)...
net start FastAPICertificateManager
if errorlevel 1 (
    echo [ERROR] Failed to start service. Make sure Command Prompt is run as Administrator.
) else (
    echo [SUCCESS] FastAPICertificateManager started.
)
pause
