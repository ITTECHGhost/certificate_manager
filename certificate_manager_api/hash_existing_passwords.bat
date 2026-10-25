@echo off
REM =============================================================================
REM hash_existing_passwords.bat - convert all plain-text passwords in MySQL to hashes
REM (SERVER laptop, once). Lists the accounts first and asks before changing anything.
REM =============================================================================
cd /d "%~dp0"
set "PYTHON_EXE="
for /f "delims=" %%P in ('where python 2^>nul ^| findstr /v /i "WindowsApps"') do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
if not defined PYTHON_EXE if exist "C:\Users\IT_TECK\AppData\Local\Python\pythoncore-3.14-64\python.exe" set "PYTHON_EXE=C:\Users\IT_TECK\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if not defined PYTHON_EXE (
    echo [ERROR] Python was not found.
    pause
    exit /b 1
)
"%PYTHON_EXE%" hash_existing_passwords.py
pause
