# Install registration_web on the server (step by step)

Before you start: the server already runs the certificate_manager API, so Python 3 and pywin32 are there.
The address is 172.50.1.100 and the port is 2040. The app runs as its own service and does not use Apache or WAMP.

1. **Get the code.** On the server, open the repo folder and run `git pull`.
2. **Open PowerShell as Administrator.** Start menu → PowerShell → right click → Run as administrator.
3. **Go to the folder.** `cd <repo>\registration_web`
4. **Install.** `powershell -ExecutionPolicy Bypass -File install_service.ps1 -ServerAddress 172.50.1.100`
   Every line should say [OK]. If a line says [FAIL], stop and send that line.
5. **Make your own admin account.** Run these two commands:
   `$env:REGWEB_DATA_DIR='C:\registration_data'`
   `.venv\Scripts\python manage.py createsuperuser`
6. **Get the trial passwords.** Open `C:\registration_data\trial_passwords.txt`. It has 6 trial users, 2 per unit.
   Give each password to its user, then delete the file.
7. **Test from another PC.** Open http://172.50.1.100:2040/admin/ and log in as a trial user.
8. **Test the backup.** Run `regweb_backup.bat`. A folder with today's date should appear in `C:\registration_data\backups\`.

- **Start / stop:** use `regweb_start.bat` / `regweb_stop.bat` as Administrator,
  or services.msc → "Registration Web (التسجيل)".
- **New IP:** run step 4 again with the new `-ServerAddress`. Your data is kept.
- **Logs:** `C:\registration_data\logs\`
- **Restore:** see `RESTORE.md`.
