# Server Laptop Setup: HTTPS and Application Key

This guide is for the **server laptop** (the laptop that runs FastAPI and MySQL).
Read it before you install the server there. Most steps are done for you by
one file: `setup_server_https.bat`.

> The certificates on the **developer laptop** were made only for testing.
> The server laptop makes **its own** certificates in step 3. Do not copy the
> developer laptop's `certs` folder to the server laptop.

---

## What this gives you

| Feature | What it does |
|---|---|
| **HTTPS** | Everything between the client laptops and the server is encrypted (passwords, student data, the program key). Clients only talk to the real server: they check its certificate against the college certificate (`college_ca.crt`). |
| **Application key** | FastAPI only accepts requests from programs that send the right key. The certificate program has its own key. Future programs get their own keys. |

---

## Before you start

1. **Give the server laptop a fixed IP address.**
   Windows: Settings → Network & Internet → (Ethernet or Wi-Fi) → IP assignment → Edit → Manual.
   Or ask the network admin to reserve an IP for this laptop on the router.
   Write the IP down, for example `192.168.1.20`.
2. The API files are installed in `C:\AppServ\www\certificate_manager_api\`
   (or wherever you put them) and the server already works with `start_server.bat`.
3. Apache (AppServ) is installed. The setup uses its `openssl.exe`
   (`C:\AppServ\Apache24\bin\openssl.exe`).

---

## Step-by-step

### 1. Stop the server
Close the `start_server.bat` console window if it is open.

### 2. Make sure Apache cannot serve the API folder
The API folder is inside Apache's web folder. The file
`certificate_manager_api\.htaccess` must be there (it blocks Apache from
serving the code, the database password and the keys). Check it in a browser:

    http://<server-ip>/certificate_manager_api/config.py

You must see **403 Forbidden**. If you can see the file, copy `.htaccess`
from the project's `certificate_manager_api\` folder into the API folder.

### 3. Run the setup (double-click)
Double-click **`setup_server_https.bat`** in the API folder.

- It shows the laptop's IP addresses and asks for the **fixed IP**. Type it and press Enter.
- It creates:
  - `certs\ca\college_ca.key` - the college CA **private key**. Keep it secret, never copy it to clients.
  - `certs\college_ca.crt` - the college CA certificate (public, goes to clients).
  - `certs\server.crt` + `certs\server.key` - this server's certificate.
  - `app_keys.json` - the certificate program's secret key (first run only).
  - `client_package\` - the files every client laptop needs.
- It checks the Windows Firewall (step 4).

### 4. Allow port 2030 in the Windows Firewall (once)
If the setup says there is no firewall rule, open **Command Prompt as
Administrator** and run:

    netsh advfirewall firewall add rule name="Certificate Manager API" dir=in action=allow protocol=TCP localport=2030

### 5. Start the server with HTTPS
Double-click **`start_server_https.bat`** (instead of `start_server.bat`).
Closing its console window stops the server, as before.

Quick check on the server laptop, in a browser:

    https://<server-ip>:2030/ping

The browser will warn that the certificate is not trusted (browsers do not
know the college CA). That is expected: the Certificate Manager program
trusts it. You should see `{"status":"online"}` after accepting the warning.

### 6. Set up every client laptop
Copy the two files from `client_package\` into the Certificate Manager
program folder on each client laptop:

| From `client_package\` | To the program folder on the client |
|---|---|
| `server_config.json` | replace the existing `server_config.json` |
| `certs\college_ca.crt` | `certs\college_ca.crt` (create the `certs` folder if missing) |

Restart the program. The top bar should show **Online**.

> **Building the client program (`client.spec`)?** Put the server's
> `certs\college_ca.crt` into the project's `certs\` folder first, so the
> built program contains the right college certificate.

### 7. Turn on key enforcement (after ALL clients are updated)
At first the server runs in **audit mode**: requests without the key are
allowed, and the server console prints a line like:

    [app-key audit] 192.168.1.35 called /students without a valid X-App-Key

When no such lines appear any more (every client sends the key):

1. Open `app_keys.json` in the API folder.
2. Change `"enforce": false` to `"enforce": true`.
3. Restart the server (`start_server_https.bat`).

Now requests without the right key get **401** and are refused.

---

## When the server IP changes

Run `setup_server_https.bat` again and type the new IP. It keeps the college
CA and the program key, makes a new server certificate, and refreshes
`client_package\`. Copy the new `server_config.json` to the clients
(the `college_ca.crt` stays the same, so you do not need to copy it again).
Then restart the server with `start_server_https.bat`.

## Going back to plain HTTP (emergency)

1. Start the server with `start_server.bat` (HTTP) instead of `start_server_https.bat`.
2. On each client, in `server_config.json`, change `"scheme": "https"` to
   `"scheme": "http"` and `"api_url"` to `http://<server-ip>:2030`.

The server can only speak one of HTTP or HTTPS on port 2030 at a time, so
switch the server and all clients on the same day.

## Adding a new program later

Each program gets its own key. Add a line to `app_keys.json`:

```json
{
    "enforce": true,
    "apps": {
        "certificate_manager": "<existing key>",
        "new_program_name": "<a new long random key>"
    }
}
```

Restart the server. The new program must send its key in the `X-App-Key`
header on every request.

## Files and what to keep secret

| File | Where | Secret? |
|---|---|---|
| `certs\ca\college_ca.key` | server only | **YES** - with it anyone can make a fake server. Back it up somewhere safe. |
| `certs\server.key` | server only | **YES** |
| `app_keys.json` | server only | **YES** |
| `client_package\server_config.json` | server + clients | **YES** (contains the program key) |
| `certs\college_ca.crt` | server + clients | no (public) |
| `.htaccess` | API folder | no - but it must be there |

None of the secret files are committed to git (see `.gitignore`).

## Troubleshooting

| Problem | Fix |
|---|---|
| Client shows **Offline** after switching to HTTPS | Check `server_config.json` on the client (`scheme`, `host`, `api_url`), that `certs\college_ca.crt` is in the program folder, and that the server was started with `start_server_https.bat`. |
| `SSLError` / certificate verify failed in the client log | The client has a different `college_ca.crt` than the server. Copy the server's `certs\college_ca.crt` again. |
| Clients on other laptops cannot connect at all | Firewall rule (step 4) or wrong IP. Test from the client: `https://<server-ip>:2030/ping` in a browser. |
| `401 Missing or invalid application key` | The client's `app_key` in `server_config.json` does not match `app_keys.json` on the server. Copy `client_package\server_config.json` again. |
| `openssl` errors during setup | Check that `C:\AppServ\Apache24\bin\openssl.exe` exists. |
