# Server Laptop Guide: Service, HTTPS, Program Key and Updates

This guide is for the **server laptop** (the laptop that runs MySQL and the
FastAPI server). Everything is done with the `.bat` files in this folder;
double-click them. Files marked **(admin)** ask Windows for Administrator
rights - click **Yes**.

> The certificates on the **developer laptop** were made only for testing.
> The server laptop makes **its own** in step 4. Never copy the developer
> laptop's `certs` folder to the server laptop.

---

## The tools in this folder

| File | What it does |
|---|---|
| `install_service.bat` **(admin)** | Installs (or updates) the Windows service, starts it, starts it with Windows, restarts it automatically if it fails. No CMD window. |
| `setup_server_https.bat` | Makes the HTTPS certificates, the program key and the **client package**. |
| `switch_server_mode.bat` **(admin)** | Switches the service between `https` and `http` and restarts it. |
| `update_server.bat` **(admin)** | Installs new server code from a folder, keeping this server's settings. |
| `publish_client_update.bat` | Offers a new version of the client program to every laptop. |
| `start_server.bat` / `start_server_https.bat` | Run the server in a console window (testing only; stop the service first). |

The service writes its output to `logs\api_service.log` in this folder.

---

## First installation

### 1. Before you start
1. **Fixed IP.** Windows Settings → Network & Internet → (Ethernet / Wi-Fi) → IP assignment → Edit → **Manual**,
   or ask the network admin to reserve an IP for this laptop. Write it down (example: `192.168.1.20`).
2. **AppServ** (Apache + MySQL) is installed, and the database is restored.
3. **Python** is installed for all users, with these packages:

       python -m pip install fastapi uvicorn mysql-connector-python pydantic python-multipart pywin32

4. Copy the project's `certificate_manager_api` folder to `C:\AppServ\www\certificate_manager_api\`.
5. Check `config.py` in that folder: the MySQL login (`DBConfig`) must be correct for this laptop.
   Updates never overwrite `config.py`.

### 2. Make sure Apache cannot serve this folder
The folder is inside Apache's web folder. Open in a browser:

    http://<server-ip>/certificate_manager_api/config.py

You must see **403 Forbidden**. If the file opens, the `.htaccess` file is missing from this folder -
copy it from the project's `certificate_manager_api\` folder. (Without it, anyone on the network can
read the database password.)

### 3. Install the service (HTTP first)
Double-click **`install_service.bat`** (admin). It creates `server_settings.json`
(`{"port": 2030, "https": false}`), installs the service, and starts it.
You should see `[SUCCESS] API is listening on port 2030 (HTTP)`.

### 4. HTTPS certificates, program key and client package
Double-click **`setup_server_https.bat`**. Type the **fixed IP** when asked. It creates:

- `certs\ca\college_ca.key` - college CA **private key**. Secret. Back it up somewhere safe. Never copy it to clients.
- `certs\college_ca.crt` - college CA certificate (public, for clients).
- `certs\server.crt` + `certs\server.key` - this server's certificate.
- `app_keys.json` - the certificate program's secret key (audit mode: logs, does not block yet).
- `client_package\` - `server_config.json` + `certs\college_ca.crt` for the client laptops.

If it says there is no firewall rule, open **Command Prompt as Administrator** once and run:

    netsh advfirewall firewall add rule name="Certificate Manager API" dir=in action=allow protocol=TCP localport=2030

### 5. Switch the clients and the server to HTTPS (same day)
The server speaks **either** HTTP **or** HTTPS on port 2030, so do these together:

1. On every client laptop, copy from `client_package\` into the Certificate Manager program folder:

   | From `client_package\` | To the client's program folder |
   |---|---|
   | `server_config.json` | replace the existing `server_config.json` |
   | `certs\college_ca.crt` | `certs\college_ca.crt` (create the `certs` folder) |

2. On the server: **`switch_server_mode.bat https`** (admin), or double-click it and type `https`.
3. Restart the program on the clients. The top bar should show **Online**.

Check from any laptop's browser: `https://<server-ip>:2030/ping` → `{"status":"online"}`
(the browser warns about the certificate because it does not know the college CA - that is expected;
the Certificate Manager program trusts it).

> **Building the client program?** Put the server's `certs\college_ca.crt` into the project's `certs\`
> folder before `scripts\build_client.bat`, so new installations trust the server.

### 6. Turn on the program key (after ALL clients are switched)
In audit mode the server log (`logs\api_service.log`) shows lines like:

    [app-key audit] 192.168.1.35 called /students without a valid X-App-Key

When no such lines appear any more:
1. Open `app_keys.json`, change `"enforce": false` to `"enforce": true`, save.
2. Restart the service: **`switch_server_mode.bat https`** (admin).

Requests without the right key now get **401** and are refused.

---

## Updates

### How updates work

```
Developer laptop                              Server laptop                         Client laptops
----------------                              -------------                         --------------
Server code changed  ── copy folder ──▶  update_server.bat <folder>
                                         (stops service, copies code,
                                          keeps settings, starts service)

Client program changed:
 1. raise CURRENT_APP_VERSION in
    services\updater.py (e.g. 2.1.0)
 2. scripts\build_client.bat
 3. scripts\make_client_patch.bat
    → dist\patch_v2.1.0.zip   ── copy ZIP ──▶  publish_client_update.bat <zip>  ──▶  Settings ›
                                                (version.json + ZIP in            Check for updates
                                                 C:\AppServ\www\updates)           → download → restart
```

### Updating the server code
1. Copy the new `certificate_manager_api` folder from the developer laptop to the server laptop,
   somewhere **other** than the live folder (e.g. `D:\release\certificate_manager_api`).
2. In the live folder, run **`update_server.bat "D:\release\certificate_manager_api"`** (admin),
   or double-click it and paste the path.
3. It backs up the current code to `_backup_before_update\`, stops the service, copies the new code,
   and starts the service again.

**Never overwritten by an update:** `certs\`, `client_package\`, `logs\`, `templets\` (Word templates),
`app_keys.json`, `server_settings.json`, `config.py` (MySQL login), `update_server.bat`.
If the new code fails to start: copy the files from `_backup_before_update\` back and run
`install_service.bat`.

### Updating the client program
1. Developer laptop: raise `CURRENT_APP_VERSION` in `services\updater.py` (e.g. `2.0.0` → `2.1.0`).
   **Do not skip this** - clients compare this number to decide if there is an update.
2. Run `scripts\build_client.bat`, then `scripts\make_client_patch.bat` → `dist\patch_v2.1.0.zip`.
3. Copy the ZIP to the server laptop and drag it onto **`publish_client_update.bat`**.
4. On each client: Settings › Server, Maintenance & Logs › **Check for updates** → install.

Each laptop **keeps its own** `server_config.json` (server IP, HTTPS, program key) and `certs\`
during an update - the patch never contains `server_config.json`, and the updater restores both.

> **Order matters with the program key:** clients get the key from `client_package\` (step 5),
> not from updates. Turn on `enforce` only after every client has the new `server_config.json`,
> otherwise old clients cannot even download updates.

---

## When the server IP changes
1. Run `setup_server_https.bat` again with the new IP. The college CA and the program key are kept;
   a new server certificate and a new `client_package\` are made.
2. Restart the service: `switch_server_mode.bat https` (admin).
3. Copy the new `client_package\server_config.json` to every client (the `college_ca.crt` did not change).

## Going back to plain HTTP (emergency)
1. Server: `switch_server_mode.bat http` (admin).
2. Each client's `server_config.json`: `"scheme": "http"` and `"api_url": "http://<server-ip>:2030"`.

## Adding another program later
Each program gets its own key. Add it to `app_keys.json`, then restart the service:

```json
{
    "enforce": true,
    "apps": {
        "certificate_manager": "<existing key>",
        "new_program_name": "<a new long random key>"
    }
}
```

The new program must send its key in the `X-App-Key` header on every request.

---

## Files and what to keep secret

| File | Where | Secret? |
|---|---|---|
| `certs\ca\college_ca.key` | server only | **YES** - with it anyone can make a fake server. Keep a backup. |
| `certs\server.key` | server only | **YES** |
| `app_keys.json` | server only | **YES** |
| `config.py` | server only | **YES** (MySQL password) |
| `client_package\server_config.json` | server + clients | **YES** (program key) |
| `certs\college_ca.crt` | server + clients | no (public) |
| `.htaccess` (here and in `C:\AppServ\www\updates`) | server | no - but must exist |

None of the secret files are in git (see `.gitignore`).

## Troubleshooting

| Problem | Fix |
|---|---|
| Service does not start | Read `logs\api_service.log`. Common causes: port 2030 used by a `start_server.bat` window (close it), HTTPS mode without certificates (run `setup_server_https.bat`), wrong MySQL login in `config.py`, `pywin32` not installed. |
| Client shows **Offline** after switching to HTTPS | Client `server_config.json` (`scheme`, `host`, `api_url`), `certs\college_ca.crt` in the program folder, server in HTTPS mode, firewall rule. |
| `SSLError` / certificate verify failed in the client log | The client has a different `college_ca.crt` than the server. Copy the server's `certs\college_ca.crt` again. |
| `401 Missing or invalid application key` | The client's `app_key` differs from `app_keys.json`. Copy `client_package\server_config.json` again. |
| Clients never see the new client version | `CURRENT_APP_VERSION` was not raised before building, or `publish_client_update.bat` was not run. |
| `openssl` errors during setup | `C:\AppServ\Apache24\bin\openssl.exe` must exist. |
