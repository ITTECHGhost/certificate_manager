# Installation & Deployment Guide

**Certificate Manager 2.1** — NiceGUI client (installed per user) + FastAPI server (Windows service) + MySQL + offline SQLite cache.

- **Server laptop:** MySQL 8 (AppServ), the FastAPI Windows service `FastAPICertificateManager` on port 2030,
  code in `C:\AppServ\www\certificate_manager_api\`.
- **Client laptops:** `CertificateManager.exe`, installed per user with `CertificateManager-Setup-<version>.exe`
  (no admin rights needed). Works offline from its own SQLite cache and syncs when the server is reachable.

| What | Where |
|---|---|
| Client program | `%LOCALAPPDATA%\Programs\CertificateManager\` (replaced by updates) |
| Client data: offline cache, logs, templates, generated certificates, `server_config.json`, `certs\college_ca.crt` | `%LOCALAPPDATA%\CertificateManager\` (kept by updates and by uninstall) |
| Server code and settings (`db_config.json`, `app_keys.json`, `server_settings.json`, `certs\`) | `C:\AppServ\www\certificate_manager_api\` |

---

## 1. Building a release (developer laptop)

Needs: Python 3.14 (64-bit), `py -3 -m pip install -r requirements-dev.txt`, Inno Setup 6.

1. Raise `APP_VERSION` in `app_version.py` (clients compare it to decide whether to update).
2. Client: `scripts\build_release.bat` → `dist\release\<version>\`:
   - `CertificateManager-Setup-<version>.exe`: for new laptops
   - `patch_v<version>.zip`: in-app update for installed laptops
   - `SHA256SUMS.txt`
3. Server: `powershell -ExecutionPolicy Bypass -File scripts\build_server_bundle.ps1` →
   `dist\release\<version>\CertificateManagerServer-<version>.zip` (code, templates, SQL, offline Python packages, `setup_server.bat`).

---

## 2. Server laptop

### First installation
1. Give the laptop a fixed IP (Windows Settings → Network → IP assignment → Manual), and note it down.
2. Install AppServ (Apache + MySQL 8). Restore the `certificate_manager` database, or create it from
   `sql\schema.sql` + `sql\SP.sql` in the bundle. In `C:\AppServ\MySQL\my.ini` keep `bind-address = 127.0.0.1`.
3. Run `sql\fixes\*.sql` in number order in phpMyAdmin (SQL tab). For `2026-10-27_04_api_db_account.sql`,
   first replace the two `CHANGE-ME` passwords: it creates the `certman_api` account and changes the root password.
4. Install Python 3.14 (64-bit) **for all users**, with "Add python.exe to PATH".
5. Unzip `CertificateManagerServer-<version>.zip` (e.g. to `D:\release\`) and double-click **`setup_server.bat`**.
   It asks for Administrator rights, installs the Python packages, copies the code, asks once for the MySQL login
   (use `certman_api`), installs and starts the service, opens port 2030 in the firewall and checks `/ping`.
6. HTTPS, program key and client package: follow `SERVER_SETUP_GUIDE.md`, steps 4–6 (`setup_server_https.bat`).

### Updating the server
Unzip the new bundle (not into the live folder) and double-click `setup_server.bat` again. Never overwritten:
`db_config.json`, `app_keys.json`, `server_settings.json`, `certs\`, `client_package\`, `logs\`.
`templets\` only gets the templates it is missing. The first update from a version before 2.1 creates
`db_config.json` from the old `config.py` automatically.

---

## 3. Client laptops

### Prerequisites
- Windows 10/11, 64-bit.
- **Microsoft Edge WebView2 Runtime** (normally preinstalled; the setup warns if it is missing).
- **Microsoft Word**, for preview, PDF and printing (the setup warns if it is missing; `.docx` files still work without it).

### New installation
1. Copy `CertificateManager-Setup-<version>.exe` and the server's `client_package\` folder to the laptop.
2. Run the setup. On **Server connection** choose **Import settings from a folder** and pick `client_package`.
3. Start Certificate Manager from the Start menu and log in while connected to the network once.
   The first online login fills the offline cache and downloads the Word templates.

### Laptops that used the old portable folder (e.g. `C:\CertificateManager`)
1. Open the old program **online** and check Settings → Server: the offline queue must be **0**.
2. Run the setup and choose **Import settings from a folder** → the old program folder. The setup copies
   `server_config.json`, `certs\college_ca.crt` and the old offline cache (`_internal\local_cache.db`),
   and never overwrites an existing cache.
3. After checking the new program, delete the old folder.

### Updates
- In the program: Settings → Check for updates (after the server published `patch_v<version>.zip` with
  `publish_client_update.bat`). The laptop keeps its own `server_config.json` and `certs\`.
- Or run the new `CertificateManager-Setup-<version>.exe`, choosing **Keep the settings already on this laptop**.

### Uninstall
Windows Settings → Apps → Certificate Manager. It asks whether to delete the data folder; the default is **No**.

---

## 4. Running from source (developers)

```cmd
py -3 -m pip install -r requirements-dev.txt
py -3 main.py            :: native window
py -3 main.py --web      :: browser mode on http://localhost:2323
py -3 -m pytest          :: tests (add -m mysql for the read-only API comparisons)
```
From source, all data stays in the project folder, as before.

---

## 5. Checks

- Server: `https://<server-ip>:2030/ping` → `{"status":"online"}` (the browser warns about the college CA; that is expected).
- Client: the top bar shows **Online (متصل)**. With the server off it shows **Offline (غير متصل)**,
  and searching and printing keep working from the offline cache.
