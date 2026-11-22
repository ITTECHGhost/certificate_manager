@echo off
rem SERVER laptop, one click: pull main, backup DB + file folders, run migrations, restart the API.
cd /d "%~dp0.."
git pull --ff-only origin main || (echo PULL FAILED - nothing changed & pause & exit /b 1)
py -3 scripts\backup_and_migrate.py --server --backup-dir "C:\AppServ\db_backups"
if errorlevel 1 (echo STOPPED - see above & pause & exit /b 1)
call scripts\restart_service.bat
pause
