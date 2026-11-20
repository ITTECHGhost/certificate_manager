# registration_web — restore from backup (and the monthly restore test)

Backups: `<DataDir>\backups\YYYY-MM-DD\` (default DataDir `C:\registration_data`), made nightly
at 02:00 by the task "RegWeb nightly backup"; 30 days kept. Log: `<DataDir>\logs\backup.log`.
Each folder holds `registration.sqlite3` (SQLite online backup, checked with integrity_check) and `media\`.

## Restore test (monthly, does NOT touch the live data)
1. PowerShell (not admin): `cd F:\...\registration_web`
2. `$t = "C:\regweb_restore_test"; New-Item -ItemType Directory $t`
3. Copy one backup into it: `Copy-Item C:\registration_data\backups\<date>\* $t -Recurse`
4. `Copy-Item C:\registration_data\secret_key.txt $t`
5. `$env:REGWEB_DATA_DIR=$t; .venv\Scripts\python manage.py check`
6. `.venv\Scripts\python manage.py shell -c "from registry.models import Student; print(Student.objects.count())"`
   → the number of students on that date.
7. `.venv\Scripts\python manage.py runserver 127.0.0.1:8099` → log in at http://127.0.0.1:8099/admin/, open a student and a document.
8. Close it, `Remove-Item $t -Recurse`. Write the date and result in `.ai/releases.md`.

## Real restore (DB lost or damaged)
1. As Administrator: `regweb_stop.bat` (or `net stop RegWebRegistration`).
2. Rename the broken data: `Rename-Item C:\registration_data\registration.sqlite3 registration.broken.sqlite3`
   and `Rename-Item C:\registration_data\media media.broken` (never delete until the restore is checked).
3. Copy from the chosen backup: `registration.sqlite3` and `media\` into `C:\registration_data\`.
4. `regweb_start.bat`, open http://<server>:2040/admin/ and check the latest students.
5. Work entered after that backup is lost: tell the units the backup date.
