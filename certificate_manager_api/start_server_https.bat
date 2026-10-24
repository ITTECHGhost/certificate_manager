@echo off
set PYTHON_PATH="C:\Users\IT_TECK\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if not exist %PYTHON_PATH% (
    set PYTHON_PATH=python
)

cd /d "%~dp0"
if not exist "certs\server.crt" (
    echo [ERROR] certs\server.crt not found. Run: make_https_cert.bat ^<server-ip^>
    pause
    exit /b 1
)

echo Starting FastAPI Uvicorn Server with HTTPS on port 2030...
start /B "FastAPI_Server" %PYTHON_PATH% -m uvicorn main:app --host 0.0.0.0 --port 2030 --timeout-keep-alive 30 --ssl-keyfile certs\server.key --ssl-certfile certs\server.crt
echo Server start command executed in background.
