# Phase 8 — Docs, final release, rollout (Haiku runbook)

Goal: update the guides to match the new installers, build the final release (client +
server), and hand the rollout checklist to the user.

Run this **last**: after Phases 0, 1, 2, 6 and 7 (Haiku), and after Phases 3, 4 and 5 (Sonnet/Opus).

Read `00-README.md` first. Follow its rules exactly.

## Before you start

````powershell run skip-validate
git branch --show-current
git status --porcelain | Where-Object { $_ -notmatch '^.. "?(logs/|certificates/|\.nicegui/)' }
py -3 -m pytest
````
Expected: `passed`. The first line must be `refactor/install-ready`, and no `git status` lines may be printed. The pytest summary line must contain `passed` and must not contain `failed` or `error`. Otherwise STOP.

## Step 8.1 — Write `docs/installation_guide.md` (Read it first; replace the whole file)

````markdown file=docs/installation_guide.md
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
````

## Step 8.2 — Edit `certificate_manager_api/SERVER_SETUP_GUIDE.md` (eight edits)

**Find:**
````text edit-old=certificate_manager_api/SERVER_SETUP_GUIDE.md
3. **Python** is installed for all users, with these packages:

       python -m pip install fastapi uvicorn mysql-connector-python pydantic python-multipart pywin32

4. Copy the project's `certificate_manager_api` folder to `C:\AppServ\www\certificate_manager_api\`.
5. Check `config.py` in that folder: the MySQL login (`DBConfig`) must be correct for this laptop.
   Updates never overwrite `config.py`.
````
**Replace with:**
````text edit-new=certificate_manager_api/SERVER_SETUP_GUIDE.md
3. **Python 3.14 (64-bit)** is installed **for all users**, with "Add python.exe to PATH".
4. Unzip the server bundle `CertificateManagerServer-<version>.zip` (made on the developer laptop with
   `scripts\build_server_bundle.ps1`) somewhere, e.g. `D:\release\`.
5. Double-click **`setup_server.bat`** in the unzipped folder (admin). It installs the Python packages
   (from the bundle's `wheels\`, no internet needed), copies the code to `C:\AppServ\www\certificate_manager_api\`,
   asks once for the MySQL login and saves it in `db_config.json`, adds the templates, installs and starts the
   service (HTTP first), opens the firewall port and checks `/ping`. Steps 3 and the firewall command in step 4
   below are then already done; they stay here for reference. Updates never overwrite `db_config.json`.
````

**Find:**
````text edit-old=certificate_manager_api/SERVER_SETUP_GUIDE.md
1. On every client laptop, copy from `client_package\` into the Certificate Manager program folder:

   | From `client_package\` | To the client's program folder |
   |---|---|
   | `server_config.json` | replace the existing `server_config.json` |
   | `certs\college_ca.crt` | `certs\college_ca.crt` (create the `certs` folder) |
````
**Replace with:**
````text edit-new=certificate_manager_api/SERVER_SETUP_GUIDE.md
1. On every client laptop, give the program the files from `client_package\`:
   - **Installed with the setup (2.1.0 or later):** run the setup again and choose "Import settings from a
     folder" → `client_package`. Or copy the files into `%LOCALAPPDATA%\CertificateManager\`:

     | From `client_package\` | To `%LOCALAPPDATA%\CertificateManager\` |
     |---|---|
     | `server_config.json` | replace the existing `server_config.json` |
     | `certs\college_ca.crt` | `certs\college_ca.crt` (create the `certs` folder) |

   - **Old portable folder (before 2.1.0):** copy them into the program folder, as before.
````

**Find:**
````text edit-old=certificate_manager_api/SERVER_SETUP_GUIDE.md
Server code changed  ── copy folder ──▶  update_server.bat <folder>
                                         (stops service, copies code,
                                          keeps settings, starts service)

Client program changed:
 1. raise CURRENT_APP_VERSION in
    services\updater.py (e.g. 2.1.0)
 2. scripts\build_client.bat
 3. scripts\make_client_patch.bat
    → dist\patch_v2.1.0.zip   ── copy ZIP ──▶  publish_client_update.bat <zip>  ──▶  Settings ›
````
**Replace with:**
````text edit-new=certificate_manager_api/SERVER_SETUP_GUIDE.md
Server code changed:
 scripts\build_server_bundle.ps1 ── copy ZIP ──▶  unzip, setup_server.bat
                                         (backs up, stops service, copies code,
                                          keeps settings, starts service)

Client program changed:
 1. raise APP_VERSION in
    app_version.py (e.g. 2.1.1)
 2. scripts\build_release.bat
    → dist\release\2.1.1\patch_v2.1.1.zip
      (+ CertificateManager-Setup-2.1.1.exe for new laptops)
                              ── copy ZIP ──▶  publish_client_update.bat <zip>  ──▶  Settings ›
````

**Find:**
````text edit-old=certificate_manager_api/SERVER_SETUP_GUIDE.md
1. Copy the new `certificate_manager_api` folder from the developer laptop to the server laptop,
   somewhere **other** than the live folder (e.g. `D:\release\certificate_manager_api`).
2. In the live folder, run **`update_server.bat "D:\release\certificate_manager_api"`** (admin),
   or double-click it and paste the path.
3. It backs up the current code to `_backup_before_update\`, stops the service, copies the new code,
   and starts the service again.

**Never overwritten by an update:** `certs\`, `client_package\`, `logs\`, `templets\` (Word templates),
`app_keys.json`, `server_settings.json`, `config.py` (MySQL login), `update_server.bat`.
````
**Replace with:**
````text edit-new=certificate_manager_api/SERVER_SETUP_GUIDE.md
1. Developer laptop: `powershell -ExecutionPolicy Bypass -File scripts\build_server_bundle.ps1`
   → `dist\release\<version>\CertificateManagerServer-<version>.zip`.
2. Server laptop: unzip it somewhere **other** than the live folder and double-click **`setup_server.bat`** (admin).
3. It backs up the current code to `_backup_before_update\`, stops the service, copies the new code,
   keeps this server's settings, and starts the service again.
   (`update_server.bat <folder>` still works for a code-only update.)

**Never overwritten by an update:** `certs\`, `client_package\`, `logs\`, `templets\` (only missing templates are added),
`app_keys.json`, `server_settings.json`, `db_config.json` (MySQL login). The first update from a version
before 2.1 creates `db_config.json` from the old `config.py` automatically.
````

**Find:**
````text edit-old=certificate_manager_api/SERVER_SETUP_GUIDE.md
1. Developer laptop: raise `CURRENT_APP_VERSION` in `services\updater.py` (e.g. `2.0.0` → `2.1.0`).
   **Do not skip this** - clients compare this number to decide if there is an update.
2. Run `scripts\build_client.bat`, then `scripts\make_client_patch.bat` → `dist\patch_v2.1.0.zip`.
````
**Replace with:**
````text edit-new=certificate_manager_api/SERVER_SETUP_GUIDE.md
1. Developer laptop: raise `APP_VERSION` in `app_version.py` (e.g. `2.1.0` → `2.1.1`).
   **Do not skip this** - clients compare this number to decide if there is an update.
2. Run `scripts\build_release.bat` → `dist\release\2.1.1\patch_v2.1.1.zip` (plus the setup for new laptops).
````

**Find:**
````text edit-old=certificate_manager_api/SERVER_SETUP_GUIDE.md
3. Copy the new `client_package\server_config.json` to every client (the `college_ca.crt` did not change).
````
**Replace with:**
````text edit-new=certificate_manager_api/SERVER_SETUP_GUIDE.md
3. Copy the new `client_package\server_config.json` to every client: into `%LOCALAPPDATA%\CertificateManager\`
   (installed program) or the program folder (old portable version). The `college_ca.crt` did not change.
````

**Find:**
````text edit-old=certificate_manager_api/SERVER_SETUP_GUIDE.md
| `config.py` | server only | **YES** (MySQL password) |
````
**Replace with:**
````text edit-new=certificate_manager_api/SERVER_SETUP_GUIDE.md
| `db_config.json` | server only | **YES** (MySQL password) |
````

**Find:**
````text edit-old=certificate_manager_api/SERVER_SETUP_GUIDE.md
wrong MySQL login in `config.py`, `pywin32` not installed. |
````
**Replace with:**
````text edit-new=certificate_manager_api/SERVER_SETUP_GUIDE.md
wrong MySQL login in `db_config.json`, `pywin32` not installed. |
````

## Step 8.3 — Write `README.md` (Read it first; replace the whole file)

````markdown file=README.md
# Certificate Manager

Management of academic records and official certificates for the college: students, courses,
graduation orders, Word-template certificates (Arabic/English), printing, and an offline mode.

## Parts

| Part | Folder / file | Runs on |
|---|---|---|
| Client program (NiceGUI, native window via pywebview) | `main.py`, `nicegui_screens/`, `nicegui_ui/`, `data/`, `services/`, `utils/`, `sync_engine.py` | every staff laptop, installed with `CertificateManager-Setup-<version>.exe` |
| API server (FastAPI, Windows service, port 2030) | `certificate_manager_api/` | the server laptop, installed with the server bundle's `setup_server.bat` |
| Database | MySQL 8 (`sql/schema.sql`, `sql/SP.sql`, changes in `sql/fixes/`) | the server laptop |
| Offline cache | SQLite `local_cache.db` | each client's data folder |

The client never talks to MySQL directly. Everything goes through the API (`api_client.py`), which a test enforces.

## Where files live

`app_paths.py` decides where the program reads and writes:
- **From source:** the project folder, as always.
- **Installed:** the program sits in `%LOCALAPPDATA%\Programs\CertificateManager`, and all data
  (cache, logs, templates, certificates, `server_config.json`) is in `%LOCALAPPDATA%\CertificateManager`.

## Developer quick start

```cmd
py -3 -m pip install -r requirements-dev.txt
certificate_manager_api\start_server.bat      :: API in a visible console (needs certificate_manager_api\db_config.json)
py -3 main.py                                 :: client (add --web for browser mode on port 2323)
py -3 -m pytest                               :: tests; py -3 -m pytest -m mysql for read-only API comparisons
```

## Releases

1. Raise `APP_VERSION` in `app_version.py`.
2. `scripts\build_release.bat`: tests, PyInstaller build, update ZIP, Inno Setup installer, checksums.
3. `powershell -ExecutionPolicy Bypass -File scripts\build_server_bundle.ps1`: the server bundle.

Full instructions: `docs/installation_guide.md` and `certificate_manager_api/SERVER_SETUP_GUIDE.md`.
The refactor plan and its step-by-step runbooks are in `docs/superpowers/plans/`.

## Legacy code

Old CustomTkinter screens, scratch scripts and SQL dumps are in `old/` (dumps and old copies holding
passwords or student data are kept on disk only, never in git).
````

## Step 8.4 — Edit `.ai/anatomy.md` (add the new modules)

**Find:**
````text edit-old=.ai/anatomy.md
- `logs/system_log.txt`, `logs/activity_log.txt`: runtime logs.
````
**Replace with:**
````text edit-new=.ai/anatomy.md
- `logs/system_log.txt`, `logs/activity_log.txt`: runtime logs (in the data folder; see `app_paths.py`).
- `app_paths.py`: the only place that decides file locations. From source everything is in the project folder; installed, the data (cache, logs, templets, certificates, server_config.json) is in `%LOCALAPPDATA%\CertificateManager` and the program in `%LOCALAPPDATA%\Programs\CertificateManager`. `CERTMAN_DATA_DIR` overrides the data folder (tests).
- `app_version.py`: `APP_VERSION`, the one version number (updater, patch ZIP, installer).
- `installer/client/CertificateManager.iss` (+ `test_install.ps1`): Inno Setup per-user installer. `installer/server/setup_server.bat|ps1` (+ `test_setup_server.ps1`): server install/update. `scripts/build_release.bat`: client release. `scripts/build_server_bundle.ps1`: server bundle.
- `tests/`: pytest suite. `py -3 -m pytest` (fast); `-m mysql` compares read-only API answers with `tests/.golden/` (ignored, holds student data). Snapshots in `tests/snapshots/` (API route order, public names) guard refactors.
- `docs/superpowers/plans/`: the refactor plan and the Haiku runbooks.
````

## Step 8.5 — Commit the docs

````powershell run
git add -- docs/installation_guide.md certificate_manager_api/SERVER_SETUP_GUIDE.md README.md .ai/anatomy.md
git commit -q -m "docs: installation guide, server guide, README and anatomy for the installers"
git log --oneline -1
````
Expected: `docs: installation guide, server guide, README and anatomy`

## Step 8.6 — Final client release and server bundle (needs internet for the server wheels; 5–10 minutes)

````powershell run
cmd.exe /c "scripts\build_release.bat"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build_server_bundle.ps1
$ver = py -3 -c "import app_version; print(app_version.APP_VERSION)"
Get-ChildItem -Name "dist\release\$ver"
````
Expected: `RELEASE READY`. The second command must print `[SUCCESS] Server bundle`. The listing must show the setup `.exe`, `patch_v….zip`, `SHA256SUMS.txt`, the `CertificateManagerServer-…` folder and its `.zip`.

````powershell run
$ver = py -3 -c "import app_version; print(app_version.APP_VERSION)"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File installer\client\test_install.ps1 -Setup "dist\release\$ver\CertificateManager-Setup-$ver.exe"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File installer\server\test_setup_server.ps1 -Bundle "dist\release\$ver\CertificateManagerServer-$ver"
````
Expected: `ALL CHECKS PASSED`. Both scripts must print `ALL CHECKS PASSED`.

## Step 8.7 — Hand over to the user (show this text exactly; do not do any of it yourself)

````powershell manual
USER ROLLOUT CHECKLIST (version from app_version.py; files in dist\release\<version>\)

A. Git: review the branch, then push it and open a pull request into main:
     git push -u origin refactor/install-ready
   (then "Compare & pull request" on GitHub)

B. Database (phpMyAdmin, logged in as root), on the developer laptop AND the server laptop:
   run sql\fixes\2026-10-27_04_api_db_account.sql after replacing both CHANGE-ME passwords.
   Then put user "certman_api" + its password into certificate_manager_api\db_config.json (developer laptop).

C. Server laptop: unzip CertificateManagerServer-<version>.zip, double-click setup_server.bat.
   It migrates the old config.py login. Then edit C:\AppServ\www\certificate_manager_api\db_config.json
   to the certman_api login, and run setup_server.bat once more. Check https://<server-ip>:2030/ping

D. Pilot laptop: open the old program ONLINE, Settings -> Server: offline queue must be 0.
   Run CertificateManager-Setup-<version>.exe -> "Import settings from a folder" -> the old program folder.
   Log in, search a student, generate a certificate, go offline, generate again, come back online.

E. Other laptops: same as D, or publish patch_v<version>.zip with publish_client_update.bat (server, admin)
   for laptops that stay on the portable folder.

F. A week later, when logs\api_service.log shows no "[app-key audit]" lines: set "enforce": true in
   app_keys.json and restart the service (SERVER_SETUP_GUIDE.md step 6).

G. .ai/cerebrum.md still has rules from the CustomTkinter era ("use the themes in config.py",
   "use customtkinter (CTk) classes", "SidePanel/RecordList patterns"). Decide whether to delete them.
````

## Done

````powershell run
git log --oneline -12
````
Expected: `docs: installation guide, server guide, README and anatomy`
