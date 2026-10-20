# 📦 Installation & Deployment Guide: Server & Client Workstations

**Certificate Manager System**  
**Version:** 2.0+ (NiceGUI Native UI + FastAPI Backend + MySQL + SQLite Offline Engine)

---

## 📑 Overview

The Certificate Manager system utilizes a hybrid, offline-first client-server architecture:
- **Central Server:** Runs MySQL 8.0, AppServ/Apache 2.4, and the FastAPI Windows service (`127.0.0.1:2030`).
- **Client Laptops:** Run a standalone NiceGUI executable (`native=True`) with a local SQLite database (`local_cache.db`) and local `.docx` templates. They communicate with the server over LAN via REST/HTTP and automatically operate offline when disconnected.

---

## 🖥️ Part 1: Central Server Installation

### 1. Prerequisites on the Server
- **Operating System:** Windows 10, Windows 11, or Windows Server 2019/2022.
- **Web & DB Stack:** AppServ (Apache 2.4 + MySQL 8.0) or standalone Apache 2.4 and MySQL 8.0.
- **Python:** Python 3.10 to 3.14 (64-bit) installed. Ensure Python and `pip` are added to the system `PATH`.

---

### 2. MySQL Database Setup
1. Open MySQL Command Line or phpMyAdmin on the server.
2. Create the database:
   ```sql
   CREATE DATABASE IF NOT EXISTS certificate_manager CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
3. Import the database schema and Stored Procedures:
   - Execute `sql/schema.sql` (Creates all tables and indexes).
   - Execute `sql/SP.sql` (Creates all Stored Procedures and functions).
4. **Security Hardening (Strict Database Isolation):**
   - Open MySQL configuration file (`my.ini`) typically located at `C:\AppServ\MySQL\my.ini`.
   - Ensure the bind address is set to localhost only:
     ```ini
     [mysqld]
     bind-address = 127.0.0.1
     ```
   - Restart the MySQL service. (This prevents client machines from directly accessing port 3306).

---

### 3. FastAPI Backend Service Installation
1. Copy the backend API directory from the project to the server web directory:
   - Source: `certificate_manager_api/`
   - Destination: `C:\AppServ\www\certificate_manager_api\`
2. Copy the official templates into the API template repository:
   - Copy all files from `templets/` to `C:\AppServ\www\certificate_manager_api\templets\`
3. Create the update patches folder:
   - Create `C:\AppServ\www\updates\patches\`
4. Open Command Prompt as **Administrator** and install the Python dependencies:
   ```cmd
   pip install fastapi uvicorn mysql-connector-python pydantic pywin32 requests
   ```
5. Register and start the **Windows Service**:
   ```cmd
   cd /d C:\AppServ\www\certificate_manager_api
   python fastapi_service.py install
   net start FastAPICertificateManager
   ```
   *(Alternatively, run `scripts\start_service.bat` as Administrator).*

---

### 4. Windows Firewall Configuration (Server)
Allow incoming HTTP connections on port **2030** (or port 80 if using Apache):
1. Open **Windows Defender Firewall with Advanced Security**.
2. Click **Inbound Rules** ➔ **New Rule...**
3. Select **Port** ➔ Click **Next**.
4. Choose **TCP** and enter Specific local ports: `2030, 80` ➔ Click **Next**.
5. Select **Allow the connection** ➔ Click **Next**.
6. Check **Domain, Private, and Public** ➔ Click **Next**.
7. Name the rule: `Certificate Manager API Service` ➔ Click **Finish**.

---

### 5. Apache Reverse Proxy Configuration (Optional / Web Portal)
If you want the web-based version or client requests to route through standard HTTP port 80:
1. Open `C:\AppServ\Apache24\conf\httpd.conf`.
2. Uncomment the following modules (remove the leading `#`):
   ```apache
   LoadModule proxy_module modules/mod_proxy.so
   LoadModule proxy_http_module modules/mod_proxy_http.so
   LoadModule proxy_wstunnel_module modules/mod_proxy_wstunnel.so
   LoadModule rewrite_module modules/mod_rewrite.so
   LoadModule headers_module modules/mod_headers.so
   ```
3. At the bottom of `httpd.conf`, add:
   ```apache
   Include "F:/CR_PY/certificate_manager/config/apache_certificate_manager.conf"
   ```
4. Restart Apache:
   ```cmd
   net stop apache24
   net start apache24
   ```

---

## 💻 Part 2: Client Laptop Installation

### Method A: Standalone Executable (Recommended for Staff / Workstations)

No Python installation is required on the client laptop.

#### Step 1: Compile the Package on the Build PC
1. On the build workstation, run the automated build script:
   ```cmd
   scripts\build_client.bat
   ```
2. The compilation will produce a portable folder:
   `dist\CertificateManager\`

#### Step 2: Copy to the New Laptop
1. Copy the entire folder `dist\CertificateManager\` onto the new laptop (e.g., to `C:\CertificateManager` or `C:\Program Files\CertificateManager`).
2. Verify that **Microsoft Edge WebView2 Runtime** is installed (installed by default on Windows 10 and Windows 11). If missing, download and install the Evergreen Bootstrapper from Microsoft.

#### Step 3: Configure Server Connection
1. Open `C:\CertificateManager\server_config.json` in Notepad.
2. Change the `"host"` value to the Central Server's Local IP address:
   ```json
   {
       "host": "192.168.1.100",
       "port": 2030,
       "secret": "certificate_manager_secret_key",
       "timeout": 5.0,
       "auto_sync": true
   }
   ```
   *(Replace `192.168.1.100` with the actual IP address of your central server).*
3. Save and close the file.

#### Step 4: First-Time Launch & Initialization
1. Right-click `CertificateManager.exe` ➔ **Send to** ➔ **Desktop (create shortcut)**.
2. Double-click the shortcut to launch Certificate Manager.
3. **Initial Online Sync:** Log in with the staff member's credentials while connected to the university Wi-Fi or LAN.
   - The app will automatically replicate all student profiles, study systems, and departments into `local_cache.db`.
   - The app will silently download all official Word templates into `templets/`.
4. **Offline Readiness:** The laptop is now completely independent. Even if the network cable is disconnected or the server goes down, staff can log in, search records, input grades, and print certificates offline!

---

### Method B: Developer / Source Code Installation

For IT developers or administrators running from source code.

1. **Install Python:**
   - Download and install Python 3.11, 3.12, or 3.14 (64-bit) from [python.org](https://www.python.org/).
   - Check the box **"Add python.exe to PATH"** during installation.

2. **Download / Copy Workspace:**
   - Copy the project repository `certificate_manager` to the laptop (e.g., `D:\certificate_manager`).

3. **Install Dependencies:**
   Open PowerShell or Command Prompt in the project folder and run:
   ```cmd
   pip install nicegui pywebview requests python-docx openpyxl psutil
   ```

4. **Configure Server IP:**
   - Edit `server_config.json` and set `"host"` to the server's LAN IP address.

5. **Run the Application:**
   - **Native Desktop Window:**
     ```cmd
     python main.py
     ```
   - **Web Browser Intranet Mode:**
     ```cmd
     python main.py --web
     ```
     *(Accessible in Chrome/Edge at `http://localhost:2323` or across LAN at `http://<laptop-ip>:2323`).*

---

## 🔍 Verification & Health Checks

1. **Server Health:**
   - Open a browser on the laptop and visit:
     `http://<SERVER_IP>:2030/ping`
     You should see: `{"status": "ok"}`
   - Visit:
     `http://<SERVER_IP>:2030/api/templates/manifest`
     You should see the JSON list of Word templates with SHA-256 hashes.
2. **Client Health Indicator:**
   - On the client top header bar, verify the network badge:
     - 🟢 **Online (متصل)**: Connected to the central server; changes automatically sync.
     - 🔴 **Offline (غير متصل)**: Server unreachable; working securely from `local_cache.db`.
3. **Template Sync Test:**
   - Go to **Settings (الإعدادات)** ➔ **Templates (نماذج الوثائق)**.
   - Click **"Sync from Server (مزامنة مع الخادم)"** to verify template synchronization.
