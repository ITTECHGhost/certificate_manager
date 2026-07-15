@echo off
set PYTHON_PATH=python

:: Check if a virtual environment exists in the parent directory
if exist "%~dp0..\.venv\Scripts\python.exe" (
    set PYTHON_PATH="%~dp0..\.venv\Scripts\python.exe"
) else if exist "%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe" (
    set PYTHON_PATH="%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe"
) else if exist "%USERPROFILE%\AppData\Local\Python\pythoncore-3.14-64\python.exe" (
    set PYTHON_PATH="%USERPROFILE%\AppData\Local\Python\pythoncore-3.14-64\python.exe"
)

echo Starting FastAPI Uvicorn Server on port 8000...
cd /d "%~dp0"
start /B "FastAPI_Server" %PYTHON_PATH% -m uvicorn main:app --host 0.0.0.0 --port 8000
echo Server start command executed in background.
