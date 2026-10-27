# Phase 1 — Repo hygiene and secrets (Haiku runbook)

Goal: stop tracking secrets, student data and runtime files in git; move duplicate and
stray files; pin the requirements; move the MySQL login out of code.
The program's behaviour does not change.

Read `00-README.md` first. Follow its rules exactly.

## Before you start

````powershell run skip-validate
git branch --show-current
git status --porcelain | Where-Object { $_ -notmatch '^.. "?(logs/|certificates/|\.nicegui/)' }
py -3 -m pytest
````
Expected: `41 passed, 1 deselected`. The first line must be `refactor/install-ready`, and no `git status` lines may be printed. Otherwise STOP.

## Step 1.1 — Ignore runtime files, secrets and archives

Edit `.gitignore`.

**Find:**
````text edit-old=.gitignore
.pytest_cache/
````
**Replace with:**
````text edit-new=.gitignore
.pytest_cache/

# Generated documents, local data dumps and build output
certificates/
sql/SQLite.sql
dist/
build/

# Archived files that hold data or passwords (kept on disk, never in git)
old/sql_dumps/
old/root_duplicates/

# Per-install secrets (server and client)
certificate_manager_api/db_config.json
.storage_secret
````

## Step 1.2 — Untrack runtime folders (the files stay on disk)

````powershell run
git rm -r -q --cached -- .nicegui logs certificates sql/SQLite.sql
git ls-files -- .nicegui logs certificates sql/SQLite.sql | Measure-Object | Select-Object -ExpandProperty Count
````
Expected: `0`

## Step 1.3 — Move the SQL dumps out of git (they hold student data)

````powershell run
New-Item -ItemType Directory -Force -Path old\sql_dumps | Out-Null
$keep = @('schema.sql', 'SP.sql', 'SQLite.sql')
Get-ChildItem -LiteralPath sql -File | Where-Object { $keep -notcontains $_.Name } | ForEach-Object {
    git rm -q --cached -- "sql/$($_.Name)"
    Move-Item -LiteralPath $_.FullName -Destination old\sql_dumps\
}
git ls-files -- sql
````
Expected: `sql/schema.sql`. The output must be exactly these 5 lines (in any order): `sql/SP.sql`, `sql/fixes/2026-10-24_01_fix_result_status_zero.sql`, `sql/fixes/2026-10-24_02_accounts_roles_passwords.sql`, `sql/fixes/2026-10-24_03_change_tracking_and_cert_blocks.sql`, `sql/schema.sql`.

## Step 1.4 — Commit

````powershell run
git add -- .gitignore
git commit -q -m "chore: stop tracking runtime files, student documents and SQL dumps"
git log --oneline -1
````
Expected: `chore: stop tracking runtime files`

## Step 1.5 — Move duplicates, tools, docs and the logo

````powershell run
New-Item -ItemType Directory -Force -Path old\root_duplicates | Out-Null
git rm -q --cached -- db.py config.py
Move-Item -LiteralPath db.py, config.py -Destination old\root_duplicates\
git mv export_db.py tools/export_db.py
git mv get_db_schema.py tools/get_db_schema.py
git mv "nicegui_ui/theme copy.css" "old/theme copy.css"
git mv db_schema_report.md docs/db_schema_report.md
git mv template_mapping_guide.md docs/template_mapping_guide.md
git mv UI_OVERVIEW.md docs/UI_OVERVIEW.md
git mv csit.png assets/csit.png
git status --porcelain -- csit.png assets/csit.png
````
Expected: `R  csit.png -> assets/csit.png`

## Step 1.6 — Write `tools/export_db.py` (Read it first, then replace the whole file)

The old version had the MySQL password written in it. The new version takes the login
from the API folder's `config.py`. Everything below the header is unchanged.

````python file=tools/export_db.py
import os
import sqlite3
import sys
from pathlib import Path

import mysql.connector

# The MySQL login comes from the API folder's config.py (which reads db_config.json there).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "certificate_manager_api"))
from config import DBConfig  # noqa: E402

MYSQL_CONFIG = {
    'host': DBConfig.DB_HOST,
    'user': DBConfig.DB_USER,
    'password': DBConfig.DB_PASSWORD,
    'database': DBConfig.DB_NAME
}

SQLITE_DB_PATH = 'local_cache.db'
OUTPUT_DIR = 'sql'

def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)

def export_mysql_schema():
    ensure_output_dir()
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    out_path = os.path.join(OUTPUT_DIR, 'schema.sql')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("-- ========================================================\n")
        f.write("-- MySQL Database Schema Export: certificate_manager\n")
        f.write("-- ========================================================\n\n")
        f.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")

        # 1. Tables
        cursor.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
        tables = [list(row.values())[0] for row in cursor.fetchall()]

        for table in tables:
            cursor.execute(f"SHOW CREATE TABLE `{table}`")
            row = cursor.fetchone()
            create_stmt = row['Create Table']
            f.write(f"-- --------------------------------------------------------\n")
            f.write(f"-- Table structure for table `{table}`\n")
            f.write(f"-- --------------------------------------------------------\n")
            f.write(f"DROP TABLE IF EXISTS `{table}`;\n")
            f.write(f"{create_stmt};\n\n")

        # 2. Views
        cursor.execute("SHOW FULL TABLES WHERE Table_type = 'VIEW'")
        views = [list(row.values())[0] for row in cursor.fetchall()]

        for view in views:
            cursor.execute(f"SHOW CREATE VIEW `{view}`")
            row = cursor.fetchone()
            create_stmt = row.get('Create View') or list(row.values())[1]
            f.write(f"-- --------------------------------------------------------\n")
            f.write(f"-- View structure for `{view}`\n")
            f.write(f"-- --------------------------------------------------------\n")
            f.write(f"DROP VIEW IF EXISTS `{view}`;\n")
            f.write(f"{create_stmt};\n\n")

        f.write("SET FOREIGN_KEY_CHECKS = 1;\n")

    cursor.close()
    conn.close()
    print(f"Exported MySQL schema to {out_path}")

def export_mysql_sps():
    ensure_output_dir()
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    out_path = os.path.join(OUTPUT_DIR, 'SP.sql')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("-- ========================================================\n")
        f.write("-- MySQL Stored Procedures Export: certificate_manager\n")
        f.write("-- ========================================================\n\n")

        cursor.execute("SHOW PROCEDURE STATUS WHERE Db = %s", (MYSQL_CONFIG['database'],))
        sps = [row['Name'] for row in cursor.fetchall()]

        for sp in sorted(sps):
            try:
                cursor.execute(f"SHOW CREATE PROCEDURE `{sp}`")
                row = cursor.fetchone()
                create_stmt = row.get('Create Procedure')
                if create_stmt:
                    f.write(f"-- --------------------------------------------------------\n")
                    f.write(f"-- Stored Procedure `{sp}`\n")
                    f.write(f"-- --------------------------------------------------------\n")
                    f.write("DELIMITER //\n")
                    f.write(f"DROP PROCEDURE IF EXISTS `{sp}` //\n")
                    f.write(f"{create_stmt} //\n")
                    f.write("DELIMITER ;\n\n")
            except Exception as e:
                print(f"Error exporting SP {sp}: {e}")

    cursor.close()
    conn.close()
    print(f"Exported MySQL Stored Procedures to {out_path}")

def export_sqlite_schema():
    ensure_output_dir()
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"SQLite DB '{SQLITE_DB_PATH}' not found.")
        return

    conn = sqlite3.connect(SQLITE_DB_PATH)
    out_path = os.path.join(OUTPUT_DIR, 'SQLite.sql')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("-- ========================================================\n")
        f.write(f"-- SQLite Database Schema & Dump: {SQLITE_DB_PATH}\n")
        f.write("-- ========================================================\n\n")
        for line in conn.iterdump():
            f.write(f"{line}\n")
    conn.close()
    print(f"Exported SQLite schema to {out_path}")

if __name__ == '__main__':
    export_mysql_schema()
    export_mysql_sps()
    export_sqlite_schema()
````

## Step 1.7 — Edit `tools/get_db_schema.py`

**Find:**
````text edit-old=tools/get_db_schema.py
# Try importing DB connection from project db.py
try:
````
**Replace with:**
````text edit-new=tools/get_db_schema.py
# Try importing the DB connection from the API folder (certificate_manager_api/db.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "certificate_manager_api"))
try:
````

## Step 1.8 — Point the logo fallbacks at `assets/csit.png`

Edit `nicegui_screens/login_screen.py`.

**Find:**
````text edit-old=nicegui_screens/login_screen.py
                    elif os.path.exists("csit.png"):
                        logo_src = "csit.png"
````
**Replace with:**
````text edit-new=nicegui_screens/login_screen.py
                    elif os.path.exists("assets/csit.png"):
                        logo_src = "assets/csit.png"
````

Edit `nicegui_screens/settings_screen.py`.

**Find:**
````text edit-old=nicegui_screens/settings_screen.py
                            elif os.path.exists("csit.png"):
                                col_src = "csit.png"
````
**Replace with:**
````text edit-new=nicegui_screens/settings_screen.py
                            elif os.path.exists("assets/csit.png"):
                                col_src = "assets/csit.png"
````

Edit `client.spec` (two edits).

**Find:**
````text edit-old=client.spec
    ('csit.png', '.'),
````
**Replace with:**
````text edit-new=client.spec
    ('assets/csit.png', 'assets'),
````

**Find:**
````text edit-old=client.spec
    icon='csit.png'
````
**Replace with:**
````text edit-new=client.spec
    icon='assets/csit.png'
````

## Step 1.9 — Edit `tests/check_no_direct_mysql.py`

**Find:**
````text edit-old=tests/check_no_direct_mysql.py
EXCLUDED_DIRS = {"old", "certificate_manager_api", "tests", ".git", ".claude", ".agent", ".gemini", "__pycache__"}
EXCLUDED_FILES = {"db.py", "config.py", "export_db.py", "get_db_schema.py"}
````
**Replace with:**
````text edit-new=tests/check_no_direct_mysql.py
EXCLUDED_DIRS = {"old", "certificate_manager_api", "tests", "tools", "installer", "build", "dist", ".venv",
                 ".git", ".claude", ".agent", ".gemini", ".nicegui", "__pycache__"}
EXCLUDED_FILES: set[str] = set()
````

## Step 1.10 — Edit `.ai/anatomy.md` (four edits)

**Find:**
````text edit-old=.ai/anatomy.md
- `db.py`: MySQL connection factory (`get_connection`), read-only schema check (`init_db`), grade helper, and backup/restore via `mysqldump`/`mysql` CLI. (Client use of this is an architecture violation being phased out — see Bug Ledger #226.)
````
**Replace with:**
````text edit-new=.ai/anatomy.md
- `db.py` (old root copy): archived to `old/root_duplicates/` (not in git). Only the API folder's own `certificate_manager_api/db.py` is used: MySQL connection factory (`get_connection`), read-only schema check (`init_db`), grade helper, backup/restore via `mysqldump`/`mysql` CLI.
````

**Find:**
````text edit-old=.ai/anatomy.md
- `config.py`: Holds `DBConfig` (still used by `db.py`); the rest is dead CustomTkinter-era theme code.
````
**Replace with:**
````text edit-new=.ai/anatomy.md
- `config.py` (old root copy): archived with `db.py`. The API's `certificate_manager_api/config.py` holds `DBConfig`, read from `certificate_manager_api/db_config.json` (not in git; template `db_config.example.json`).
````

**Find:**
````text edit-old=.ai/anatomy.md
- `tools/`: empty package (the old `migrate_mysql.py` is in `old/tools/`). `export_db.py`, `get_db_schema.py`: DB inspection tools. `sql/`: exported schema/SP files.
````
**Replace with:**
````text edit-new=.ai/anatomy.md
- `tools/`: developer DB tools `export_db.py` and `get_db_schema.py` (they use the API folder's `config.py`/`db.py`; the old `migrate_mysql.py` is in `old/tools/`). `sql/`: `schema.sql`, `SP.sql` and `fixes/` in git; `SQLite.sql` is a local dump (ignored); old dumps are in `old/sql_dumps/` (ignored). `docs/`: guides, `db_schema_report.md`, `template_mapping_guide.md`, `UI_OVERVIEW.md`. `assets/csit.png`: fallback logo.
````

**Find:**
````text edit-old=.ai/anatomy.md
run `export_db.py` then check
````
**Replace with:**
````text edit-new=.ai/anatomy.md
run `py -3 tools/export_db.py` then check
````

## Step 1.11 — Check the moved tools and the tests

````powershell run
py -3 tools/get_db_schema.py --help | Select-Object -First 1
py -3 -m py_compile tools/export_db.py
py -3 -m pytest
````
Expected: `41 passed, 1 deselected`. The first line must start with `usage:`.

## Step 1.12 — Commit

````powershell run
git add -- tools/export_db.py tools/get_db_schema.py nicegui_screens/login_screen.py nicegui_screens/settings_screen.py client.spec tests/check_no_direct_mysql.py .ai/anatomy.md
git commit -q -m "refactor: move DB tools to tools/, archive duplicate root db/config, move docs and logo"
git log --oneline -1
git status --porcelain | Where-Object { $_ -notmatch '^.. "?(logs/|certificates/|\.nicegui/)' }
````
Expected: `refactor: move DB tools to tools/`. Nothing else may be printed after the log line.

## Step 1.13 — Pinned requirements

Write `requirements.txt` (Read it first; replace the whole file):

````text file=requirements.txt
# Client program (CertificateManager.exe / py -3 main.py). Exact versions = tested versions.
nicegui==3.14.0
pywebview==6.2.1
requests==2.34.2
python-docx==1.2.0
docxtpl==0.20.2
openpyxl==3.1.5
psutil==7.2.2
pywin32==311
````

Write `requirements-server.txt` (new file):

````text file=requirements-server.txt
# FastAPI server (certificate_manager_api). Exact versions = tested versions.
fastapi==0.137.2
uvicorn==0.49.0
pydantic==2.13.4
mysql-connector-python==9.7.0
python-multipart==0.0.32
pywin32==311
````

Write `requirements-dev.txt` (new file):

````text file=requirements-dev.txt
# Developer PC: everything to run, test and build both programs.
-r requirements.txt
-r requirements-server.txt
pyinstaller==6.21.0
pytest==9.1.1
httpx==0.28.1
pillow==12.2.0
````

````powershell run
git add -- requirements.txt requirements-server.txt requirements-dev.txt
git commit -q -m "build: split and pin client, server and dev requirements"
git log --oneline -1
````
Expected: `build: split and pin client, server and dev requirements`

## Step 1.14 — Record golden API answers with the OLD database login code

````powershell run
py -3 -m pytest -m mysql --record-golden
````
Expected: `1 passed`. If the output mentions `Can't connect to MySQL`, STOP and ask the user to start MySQL (AppServ).

## Step 1.15 — Create `certificate_manager_api/db_config.json` from the current login

This file is git-ignored. The command copies the values from the current `config.py`,
so no password is typed anywhere.

````powershell run
py -3 -c "import json, sys; sys.path.insert(0, 'certificate_manager_api'); import config as c; d = {'host': c.DBConfig.DB_HOST, 'user': c.DBConfig.DB_USER, 'password': c.DBConfig.DB_PASSWORD, 'database': c.DBConfig.DB_NAME}; open('certificate_manager_api/db_config.json', 'w', encoding='utf-8').write(json.dumps(d, indent=2))"
(Get-Content certificate_manager_api/db_config.json -Raw | ConvertFrom-Json).database
git check-ignore certificate_manager_api/db_config.json
````
Expected: `certificate_manager`. The last line must print `certificate_manager_api/db_config.json`, which proves the file is ignored.

## Step 1.16 — Keep a local copy of the old API `config.py`, then replace it

````powershell run
Copy-Item -LiteralPath certificate_manager_api/config.py -Destination old/root_duplicates/api_config_before_db_json.py
Test-Path old/root_duplicates/api_config_before_db_json.py
````
Expected: `True`

Write `certificate_manager_api/config.py` (Read it first; replace the whole file):

````python file=certificate_manager_api/config.py
# =============================================================================
# config.py — MySQL login for the FastAPI server
#
# The login lives in db_config.json next to this file. That file is never in git.
# Template: db_config.example.json. setup_server.bat creates the real file.
# (The old CustomTkinter theme code that lived here is in old/root_duplicates/.)
# =============================================================================

import json
from pathlib import Path

DB_CONFIG_FILE = Path(__file__).resolve().parent / "db_config.json"


def load_db_settings(path: Path = DB_CONFIG_FILE) -> dict:
    """Read the MySQL login from db_config.json and return host, user, password and database."""
    if not path.exists():
        raise RuntimeError(f"db_config.json missing at {path} - run setup_server.bat (or copy db_config.example.json)")
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    return {
        "host": str(data.get("host", "localhost")),
        "user": str(data["user"]),
        "password": str(data["password"]),
        "database": str(data.get("database", "certificate_manager")),
    }


class DBConfig:
    """MySQL login used by db.py, main.py and hash_existing_passwords.py."""
    _settings = load_db_settings()
    DB_HOST = _settings["host"]
    DB_USER = _settings["user"]
    DB_PASSWORD = _settings["password"]
    DB_NAME = _settings["database"]
````

Write `certificate_manager_api/db_config.example.json` (new file):

````json file=certificate_manager_api/db_config.example.json
{
  "host": "localhost",
  "user": "certman_api",
  "password": "put-the-certman_api-password-here",
  "database": "certificate_manager"
}
````

Write `tests/test_server_config.py` (new file):

````python file=tests/test_server_config.py
import importlib.util
import re
import subprocess

import pytest

from tests.helpers import API_DIR, PROJECT_ROOT


def _load_api_config():
    spec = importlib.util.spec_from_file_location("api_server_config", API_DIR / "config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_db_config_reads_json(tmp_path):
    config = _load_api_config()
    path = tmp_path / "db_config.json"
    path.write_text('{"host": "h", "user": "u", "password": "p", "database": "d"}', encoding="utf-8")
    assert config.load_db_settings(path) == {"host": "h", "user": "u", "password": "p", "database": "d"}


def test_db_config_missing_names_setup(tmp_path):
    config = _load_api_config()
    with pytest.raises(RuntimeError, match="setup_server.bat"):
        config.load_db_settings(tmp_path / "db_config.json")


def test_no_db_password_literal_in_tracked_python():
    listing = subprocess.run(["git", "ls-files", "-z", "--", "*.py"], cwd=PROJECT_ROOT,
                             capture_output=True, check=True).stdout.decode("utf-8")
    pattern = re.compile(r"""DB_PASSWORD\s*=\s*['"]|['"]password['"]\s*:\s*['"][^'"]+['"]""")
    hits = [p for p in listing.split("\0")
            if p and not p.startswith(("old/", "tests/"))
            and pattern.search((PROJECT_ROOT / p).read_text(encoding="utf-8", errors="ignore"))]
    assert hits == []
````

Write `sql/fixes/2026-10-27_04_api_db_account.sql` (new file):

````sql file=sql/fixes/2026-10-27_04_api_db_account.sql
-- =============================================================================
-- 2026-10-27_04_api_db_account.sql
-- Run ONCE in phpMyAdmin (SQL tab) while logged in as root: on the developer laptop
-- and on the server laptop. FIRST replace the two CHANGE-ME passwords (keep the quotes).
--
-- 1. A dedicated MySQL account for the FastAPI server, with rights on the
--    certificate_manager database only (instead of root).
-- 2. A new root password. The old one was committed to GitHub: treat it as public.
--
-- Afterwards put the new account into certificate_manager_api\db_config.json:
--   {"host": "localhost", "user": "certman_api", "password": "<password from step 1>", "database": "certificate_manager"}
-- and restart the API (server: switch_server_mode.bat https|http; developer laptop: start_server.bat).
--
-- If Settings -> Backup later fails with "PROCESS privilege", also run:
--   GRANT PROCESS ON *.* TO 'certman_api'@'localhost';
-- A full restore of a dump whose procedures have DEFINER=`root` must still be done as root.
-- =============================================================================

CREATE USER IF NOT EXISTS 'certman_api'@'localhost' IDENTIFIED BY 'CHANGE-ME-api-password';
GRANT ALL PRIVILEGES ON certificate_manager.* TO 'certman_api'@'localhost';
FLUSH PRIVILEGES;

ALTER USER 'root'@'localhost' IDENTIFIED BY 'CHANGE-ME-new-root-password';
````

## Step 1.17 — Check: same API answers with the NEW login code, and all tests

````powershell run
py -3 -m pytest -m mysql
py -3 -m pytest
````
Expected: `44 passed, 1 deselected`. The first run must print `1 passed`.

## Step 1.18 — Commit

````powershell run
git add -- certificate_manager_api/config.py certificate_manager_api/db_config.example.json tests/test_server_config.py sql/fixes/2026-10-27_04_api_db_account.sql
git commit -q -m "security: API reads the MySQL login from db_config.json; add API DB account SQL"
git log --oneline -1
git status --porcelain | Where-Object { $_ -notmatch '^.. "?(logs/|certificates/|\.nicegui/)' }
````
Expected: `security: API reads the MySQL login from db_config.json`. Nothing else may be printed after the log line.

## Step 1.19 — Prove the requirement files are complete (clean virtual environment)

This downloads all packages into a temporary folder. It takes several minutes and needs internet.

````powershell run
$venv = Join-Path $env:TEMP "cm-venv-check"
if (Test-Path $venv) { Remove-Item -Recurse -Force $venv }
py -3 -m venv $venv
& "$venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements-dev.txt
& "$venv\Scripts\python.exe" -m pytest
````
Expected: `44 passed, 1 deselected`. If pip reports a network error, STOP and tell the user. Do not change any version number.

## Step 1.20 — Tell the user (do not do this yourself)

````powershell manual
USER ACTION (later, any time before Phase 7): open phpMyAdmin as root and run
sql/fixes/2026-10-27_04_api_db_account.sql after replacing the two CHANGE-ME passwords.
Then edit certificate_manager_api/db_config.json on this laptop: user "certman_api" and the new password.
````

## Done

````powershell run
git log --oneline -5
````
Expected: `security: API reads the MySQL login from db_config.json`
