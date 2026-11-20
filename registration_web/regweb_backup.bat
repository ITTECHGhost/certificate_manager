@echo off
rem Nightly backup (scheduled task "RegWeb nightly backup"); also safe to run by hand.
cd /d "%~dp0"
for /f "usebackq delims=" %%d in (`.venv\Scripts\python.exe -c "import json;print(json.load(open('service_config.json'))['data_dir'])"`) do set REGWEB_DATA_DIR=%%d
.venv\Scripts\python.exe manage.py backup_regweb >> "%REGWEB_DATA_DIR%\logs\backup.log" 2>&1
