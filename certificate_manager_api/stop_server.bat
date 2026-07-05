@echo off
echo Stopping FastAPI Uvicorn Server...
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe' AND CommandLine LIKE '%%uvicorn%%'\" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Server stopped.
