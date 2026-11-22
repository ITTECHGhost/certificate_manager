@echo off
rem DEV laptop: backup the dev DB to F:\CR_PY\db_backups_dev, then run new migrations.
cd /d "%~dp0.."
py -3 scripts\backup_and_migrate.py --backup-dir "F:\CR_PY\db_backups_dev"
pause
