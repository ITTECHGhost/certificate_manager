@echo off
set PYTHON_PATH=python

echo Starting FastAPI Uvicorn Server on port 8000...
cd /d "%~dp0"
start /B "FastAPI_Server" %PYTHON_PATH% -m uvicorn main:app --host 0.0.0.0 --port 8000
echo Server start command executed in background.
