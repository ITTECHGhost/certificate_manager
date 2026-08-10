# Certificate Manager — Analysis & Server Migration Guide

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Local Architecture (SQLite)](#2-local-architecture-sqlite)
3. [Server Architecture (MySQL)](#3-server-architecture-mysql)
4. [Schema Comparison: SQLite vs MySQL](#4-schema-comparison-sqlite-vs-mysql)
5. [Safe Database Replacement Steps](#5-safe-database-replacement-steps)
6. [Converting the Program to Server-Based](#6-converting-the-program-to-server-based)
7. [Offline-First with Sync Strategy](#7-offline-first-with-sync-strategy)
8. [Recommended Project Structure](#8-recommended-project-structure)
9. [Security Checklist](#9-security-checklist)

---

## 1. Project Overview

The Certificate Manager is a desktop application (Python with a custom Tkinter front-end) for printing student graduation certificates at **Wasit University — College of Engineering** (now redesigned for **University of Basrah — College of Computer Science and Information Technology**). Its back-end is being migrated from a local SQLite file to a remote MySQL database hosted on an Apache server, while keeping a local cache for offline resilience.

| Item | Local (Current) | Server (Target) |
|---|---|---|
| Language | Python | Python + PHP/REST API |
| Database | SQLite (`certificate_manager.db`) | MySQL (`certificate_manager`) |
| DB driver | `sqlite3` (stdlib) | `mysql-connector-python` or `PyMySQL` |
| Host | `localhost` (file on disk) | Apache + MySQL server |
| Auth | Username/password in DB | Same, with hashed passwords |
| Students | ~1,600+ records | Same data migrated |

---

## 2. Local Architecture (SQLite)

### 2.1 Tables (13 total)

| Table | Purpose | Key Columns |
|---|---|---|
| `settings` | Single-row app config (UI + university info) | `id=1`, `univ_name_ar/en`, `college_name_ar/en`, `theme`, `accent_color`, `font_family`, `font_size_base` |
| `personnel` | Staff/signatories + user accounts | `id`, `name_ar/en`, `username`, `password`, `role (admin\|user)`, `academic_title_ar/en`, `responsibility_ar/en`, `display_order`, `page_location (front\|back)`, `is_active`, `is_signature`, `template_appearance_id` |
| `user_preferences` | Per-user UI settings | `user_id` → FK `personnel`, `theme`, `accent_color`, `font_family`, `font_size_base` |
| `certificate_logs` | Audit trail of printed certificates | `student_id`, `generated_by`, `generated_at` |
| `study_systems` | Grading systems (Annual / Semester) | `name_ar/en`, `calculation_rule`, `semester_weight`, `year_weight`, `prefix`, `display_type`, `weight_type`, `is_active` |
| `departments` | Academic departments | `name_ar/en`, `study_years` |
| `countries` | 195 countries (ISO codes) | `name_ar/en`, `iso_code` |
| `governorates` | 18 Iraqi governorates | `name_ar/en` |
| `graduation_orders` | Official ministerial graduation orders | `order_number`, `order_date`, `department_id`, `study_type`, `admission_year`, `graduation_semester`, `num_students`, `notes` |
| `courses` | Courses per department / system | `name_ar/en`, `credit_hours`, `department_id`, `stage_number`, `study_system_id`, `is_shared` |
| `students` | Student records | `full_name_ar/en`, `gender`, `sequence_number`, `postgraduation_no`, `date_of_birth`, `birthplace_id`, `nationality_id`, `department_id`, `study_system_id`, `order_id`, `admission_year` (INTEGER), `study_type`, `graduation_date`, `graduation_semester`, `average` |
| `academic_periods` | One row per student per academic year per stage | `student_id`, `academic_year`, `study_system_id`, `stage_number`, `passed_round` |
| `enrollments` | Course grades per period | `period_id`, `course_id`, `score`, `is_second_round` |

### 2.2 `db.py` Design Patterns

- **`get_connection()`** — returns a connection with `row_factory = sqlite3.Row`, UTF-8 encoding, and foreign keys enforced.
- **`init_db()`** — idempotent initialiser: creates tables, runs migrations, creates indexes, seeds study systems, governorates, and 195 countries.
- **`_migrate_db()`** — handles schema evolution with `ALTER TABLE … ADD COLUMN` wrapped in `try/except sqlite3.OperationalError`, making it safe to run repeatedly.
- **`backup_db()` / `restore_db()`** — file-copy utilities.
- **`get_grade()`** — pure function mapping numeric average to Arabic/English grade string.

---

## 3. Server Architecture (MySQL)

### 3.1 Tables (11 total in SQL dump)

| Table | Changes vs SQLite |
|---|---|
| `university_settings` | **New.** Extracted from `settings`. Holds `univ_name_ar/en`, `college_name_ar/en`. |
| `settings` | **Slimmed down.** Now only holds UI preferences (`theme`, `accent_color`, `font_family`, `font_size_base`, `is_arabic_rtl`). |
| `personnel` | **Renamed & extended.** `role` → `personnel_role`; `password` → `password_hash`; added `settings_id` FK, `university_settings_id` FK, `created_at` timestamp; removed `page_location`, `is_signature`, `template_appearance_id`. |
| `departments` | **Extended.** Added `study_day_type ENUM('Morning','Evening','Other')` and `university_settings_id` FK. Removed `study_years`. |
| `study_systems` | **Simplified.** `calculation_rule` is now `ENUM('annual','semester')`; `period_display` replaces `display_type`; removed `semester_weight`, `year_weight`, `prefix`, `weight_type`. Added `created_at`. |
| `students` | **Restructured.** `admission_year` changed to `VARCHAR(9)`; `postgraduation_no` → `postgraduation_number`; `study_type` removed; `graduation_date`+`graduation_semester` replaced by `summer_training_data`; `birthplace_id` default changed to `1`. |
| `graduation_orders` | **Simplified.** Removed `study_type`, `admission_year`, `notes`; `graduation_semester` is now `ENUM('first','second','summer')`. |
| `academic_periods` | **Simplified.** `passed_round` moved to `enrollments`. |
| `enrollments` | **Extended.** `passed_round ENUM('1','2','3')` added here (was in `academic_periods` in SQLite). |
| `courses` | Unchanged in structure. |
| `countries` / `governorates` | Same structure. |

### 3.2 Notable MySQL-Only Features

- **Triggers on `personnel`:** `unique_signatories_insert` and `unique_signatories_update` prevent two signatories from sharing the same `display_order` slot (1–6).
- **InnoDB + utf8mb4:** Full Unicode support including emoji.
- **Referential integrity:** All FK relationships declared with `ON UPDATE CASCADE` and appropriate `ON DELETE` actions.

---

## 4. Schema Comparison: SQLite vs MySQL

### 4.1 Column-Level Differences

| Table | SQLite Column | MySQL Equivalent | Change Type |
|---|---|---|---|
| `settings` | `univ_name_ar/en`, `college_name_ar/en` | Moved to `university_settings` | Split table |
| `personnel` | `role` | `personnel_role` | Renamed |
| `personnel` | `password` | `password_hash` | Renamed (semantic) |
| `personnel` | `page_location`, `is_signature`, `template_appearance_id` | Not present | Removed |
| `departments` | `study_years` | Not present | Removed |
| `departments` | *(none)* | `study_day_type`, `university_settings_id` | Added |
| `students` | `admission_year INTEGER` | `admission_year VARCHAR(9)` | Type change |
| `students` | `postgraduation_no` | `postgraduation_number` | Renamed |
| `students` | `study_type`, `graduation_date`, `graduation_semester` | Removed / replaced by `summer_training_data` | Restructured |
| `graduation_orders` | `study_type`, `admission_year`, `notes` | Not present | Removed |
| `academic_periods` | `passed_round` | Removed | Moved to `enrollments` |
| `enrollments` | *(none)* | `passed_round ENUM('1','2','3')` | Added |
| `study_systems` | `semester_weight`, `year_weight`, `prefix`, `display_type`, `weight_type` | Not present | Removed |
| `study_systems` | *(none)* | `period_display`, `created_at` | Added |

### 4.2 Data That Must Be Transformed During Migration

| Field | SQLite Value | MySQL Requirement |
|---|---|---|
| `students.admission_year` | Integer e.g. `2015` | String e.g. `'2015'` |
| `academic_periods.passed_round` | Stored here | Must be moved to `enrollments.passed_round` |
| `settings` (single row) | Contains university name | Must be split: UI prefs → `settings`, names → `university_settings` |
| `personnel.role` | `'admin'` / `'user'` | `personnel_role` column |
| `personnel.password` | Plain text or hash | `password_hash` — ensure bcrypt hashing before migration |

---

## 5. Safe Database Replacement Steps

> **Rule #1: Never touch the production database without a verified backup.**

### Step 1 — Back Up the SQLite Database

```bash
# In your local program folder:
python -c "from db import backup_db; from pathlib import Path; backup_db(Path('certificate_manager_BACKUP_$(date +%Y%m%d).db'))"
```

Also make a raw file copy:

```bash
cp certificate_manager.db certificate_manager_BACKUP_$(date +%Y%m%d).db
```

### Step 2 — Export SQLite Data to JSON

Write a one-time export script (`export_sqlite.py`) that reads every table and writes JSON files. Example:

```python
import sqlite3, json
from pathlib import Path

conn = sqlite3.connect("certificate_manager.db")
conn.row_factory = sqlite3.Row

tables = [
    "study_systems", "countries", "governorates", "settings",
    "departments", "personnel", "graduation_orders", "courses",
    "students", "academic_periods", "enrollments", "certificate_logs"
]

for table in tables:
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    data = [dict(r) for r in rows]
    Path(f"export_{table}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"Exported {len(data)} rows from {table}")

conn.close()
```

### Step 3 — Transform the Data

Write a transformation script (`transform_data.py`) that handles the differences:

```python
import json

# 1. Split settings into settings + university_settings
settings = json.loads(open("export_settings.json").read())[0]
univ_settings = {
    "id": 1,
    "univ_name_ar": settings.pop("univ_name_ar"),
    "univ_name_en": settings.pop("univ_name_en"),
    "college_name_ar": settings.pop("college_name_ar"),
    "college_name_en": settings.pop("college_name_en"),
}
settings["is_arabic_rtl"] = 1  # add new field

# 2. Rename personnel fields
personnel = json.loads(open("export_personnel.json").read())
for p in personnel:
    p["personnel_role"] = p.pop("role")
    p["password_hash"] = p.pop("password")  # re-hash with bcrypt here!
    p["settings_id"] = 1
    p["university_settings_id"] = 1
    p.pop("page_location", None)
    p.pop("is_signature", None)
    p.pop("template_appearance_id", None)

# 3. Fix students
students = json.loads(open("export_students.json").read())
for s in students:
    s["admission_year"] = str(s["admission_year"])    # INTEGER → VARCHAR
    s["postgraduation_number"] = s.pop("postgraduation_no", None)
    s.pop("study_type", None)
    s["summer_training_data"] = s.pop("graduation_date", None)  # approximate
    s.pop("graduation_semester", None)

# 4. Move passed_round from academic_periods to enrollments
periods = json.loads(open("export_academic_periods.json").read())
period_rounds = {p["id"]: p.pop("passed_round", "1") for p in periods}

enrollments = json.loads(open("export_enrollments.json").read())
for e in enrollments:
    e["passed_round"] = period_rounds.get(e["period_id"], "1")

# 5. Fix departments
departments = json.loads(open("export_departments.json").read())
for d in departments:
    d["study_day_type"] = "Morning"  # default
    d["university_settings_id"] = 1
    d.pop("study_years", None)

# Save all transformed data
for name, data in [
    ("university_settings", [univ_settings]),
    ("settings", [settings]),
    ("personnel", personnel),
    ("students", students),
    ("academic_periods", periods),
    ("enrollments", enrollments),
    ("departments", departments),
]:
    open(f"transformed_{name}.json", "w").write(
        json.dumps(data, ensure_ascii=False, indent=2)
    )
```

### Step 4 — Import Into MySQL

```python
import json
import mysql.connector

conn = mysql.connector.connect(
    host="your_server_ip",
    user="cert_user",
    password="strong_password",
    database="certificate_manager"
)
cursor = conn.cursor()

# Import each table in FK-safe order:
import_order = [
    "university_settings", "settings", "study_systems", "countries",
    "governorates", "departments", "personnel", "graduation_orders",
    "courses", "students", "academic_periods", "enrollments"
]

for table in import_order:
    rows = json.loads(open(f"transformed_{table}.json").read())
    if not rows:
        continue
    cols = ", ".join(f"`{k}`" for k in rows[0].keys())
    placeholders = ", ".join(["%s"] * len(rows[0]))
    sql = f"INSERT IGNORE INTO `{table}` ({cols}) VALUES ({placeholders})"
    for row in rows:
        cursor.execute(sql, list(row.values()))
    conn.commit()
    print(f"Imported {len(rows)} rows into {table}")

cursor.close()
conn.close()
```

### Step 5 — Verify the Migration

Run row-count checks between SQLite and MySQL for every table, and spot-check 5–10 student records manually against their certificates.

### Step 6 — Retire the Old SQLite File

Once verified, rename (do not delete) the old file:

```bash
mv certificate_manager.db certificate_manager_RETIRED_$(date +%Y%m%d).db
```

---

## 6. Converting the Program to Server-Based

### 6.1 Create a Database Abstraction Layer

Replace direct `sqlite3` calls with a unified `db.py` that routes to either MySQL (when online) or SQLite (when offline):

```python
# db.py (new version)
import sqlite3
import mysql.connector
from pathlib import Path
import logging

log = logging.getLogger(__name__)

SQLITE_PATH = Path("certificate_manager_local.db")
MYSQL_CONFIG = {
    "host": "your_server_ip",
    "port": 3306,
    "user": "cert_user",
    "password": "strong_password",
    "database": "certificate_manager",
    "connection_timeout": 5,
}

def get_mysql_connection():
    return mysql.connector.connect(**MYSQL_CONFIG)

def get_sqlite_connection():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def is_server_available() -> bool:
    try:
        c = get_mysql_connection()
        c.close()
        return True
    except Exception:
        return False
```

### 6.2 Use a Repository Pattern

Wrap all queries in a `Repository` class that accepts either connection type:

```python
class StudentRepository:
    def __init__(self, conn):
        self.conn = conn
        self.is_mysql = hasattr(conn, 'get_server_info')  # MySQL check

    def placeholder(self):
        return "%s" if self.is_mysql else "?"

    def find_by_name(self, name: str):
        ph = self.placeholder()
        sql = f"SELECT * FROM students WHERE full_name_ar LIKE {ph}"
        cur = self.conn.cursor()
        cur.execute(sql, (f"%{name}%",))
        return cur.fetchall()
```

### 6.3 Configure the Apache Server

**On the server**, install and configure MySQL:

```bash
sudo apt install mysql-server
sudo mysql_secure_installation

# Create the database and user:
mysql -u root -p <<EOF
CREATE DATABASE certificate_manager CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'cert_user'@'%' IDENTIFIED BY 'strong_password';
GRANT ALL PRIVILEGES ON certificate_manager.* TO 'cert_user'@'%';
FLUSH PRIVILEGES;
EOF

# Import your schema:
mysql -u cert_user -p certificate_manager < certificate_manager.sql
```

**Open the MySQL port** (3306) in the firewall only to your office's IP range — never to the public internet:

```bash
sudo ufw allow from YOUR_OFFICE_IP_RANGE to any port 3306
```

Alternatively (and more securely), route all DB traffic through an SSH tunnel or expose only a REST API via Apache+PHP, never the raw MySQL port.

---

## 7. Offline-First with Sync Strategy

This is the most important architectural decision. The recommended approach is **write-ahead local queue with reconciliation on reconnect**.

### 7.1 Add a Sync Queue Table to the Local SQLite

```sql
CREATE TABLE IF NOT EXISTS sync_queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name  TEXT NOT NULL,
    operation   TEXT NOT NULL CHECK(operation IN ('INSERT','UPDATE','DELETE')),
    record_id   INTEGER NOT NULL,
    payload     TEXT NOT NULL,   -- JSON snapshot of the row
    created_at  TEXT DEFAULT (datetime('now','localtime')),
    synced      INTEGER DEFAULT 0
);
```

### 7.2 Every Local Write Goes Through a Wrapper

```python
import json
from datetime import datetime

def write_locally_and_queue(sqlite_conn, table, operation, record_id, data: dict):
    # 1. Perform the local write
    if operation == "INSERT":
        cols = ", ".join(data.keys())
        phs  = ", ".join(["?"] * len(data))
        sqlite_conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({phs})", list(data.values()))
    elif operation == "UPDATE":
        sets = ", ".join(f"{k}=?" for k in data.keys())
        sqlite_conn.execute(f"UPDATE {table} SET {sets} WHERE id=?", [*data.values(), record_id])
    elif operation == "DELETE":
        sqlite_conn.execute(f"DELETE FROM {table} WHERE id=?", (record_id,))

    # 2. Queue the change for server sync
    sqlite_conn.execute(
        "INSERT INTO sync_queue (table_name, operation, record_id, payload) VALUES (?,?,?,?)",
        (table, operation, record_id, json.dumps(data, ensure_ascii=False))
    )
    sqlite_conn.commit()
```

### 7.3 Sync Worker (Runs on Reconnect or on a Timer)

```python
def sync_to_server(sqlite_conn, mysql_conn):
    pending = sqlite_conn.execute(
        "SELECT * FROM sync_queue WHERE synced=0 ORDER BY id"
    ).fetchall()

    if not pending:
        return

    mysql_cur = mysql_conn.cursor()
    for row in pending:
        data = json.loads(row["payload"])
        try:
            if row["operation"] == "INSERT":
                cols = ", ".join(f"`{k}`" for k in data.keys())
                phs  = ", ".join(["%s"] * len(data))
                mysql_cur.execute(
                    f"INSERT IGNORE INTO `{row['table_name']}` ({cols}) VALUES ({phs})",
                    list(data.values())
                )
            elif row["operation"] == "UPDATE":
                sets = ", ".join(f"`{k}`=%s" for k in data.keys())
                mysql_cur.execute(
                    f"UPDATE `{row['table_name']}` SET {sets} WHERE id=%s",
                    [*data.values(), row["record_id"]]
                )
            elif row["operation"] == "DELETE":
                mysql_cur.execute(
                    f"DELETE FROM `{row['table_name']}` WHERE id=%s",
                    (row["record_id"],)
                )
            mysql_conn.commit()
            sqlite_conn.execute(
                "UPDATE sync_queue SET synced=1 WHERE id=?", (row["id"],)
            )
            sqlite_conn.commit()
        except Exception as e:
            log.error("Sync failed for queue row %s: %s", row["id"], e)
            mysql_conn.rollback()
            break  # stop on first error, retry next time
```

### 7.4 Offline Reads

For reading (searching students, loading departments, etc.) the app always reads from local SQLite first. Periodically (or on reconnect) it pulls fresh data from MySQL into the local cache:

```python
def refresh_local_cache(sqlite_conn, mysql_conn, table: str):
    mysql_cur = mysql_conn.cursor(dictionary=True)
    mysql_cur.execute(f"SELECT * FROM `{table}`")
    rows = mysql_cur.fetchall()
    sqlite_conn.execute(f"DELETE FROM {table}")
    if rows:
        cols = ", ".join(rows[0].keys())
        phs  = ", ".join(["?"] * len(rows[0]))
        sqlite_conn.executemany(
            f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({phs})",
            [list(r.values()) for r in rows]
        )
    sqlite_conn.commit()
```

### 7.5 Connection Status in the UI

Add a status indicator in the application window:

```python
def update_connection_status(app_window):
    if is_server_available():
        app_window.status_label.config(text="● متصل بالخادم", fg="green")
        sync_to_server(local_conn, mysql_conn)
    else:
        app_window.status_label.config(text="● غير متصل — وضع محلي", fg="orange")
```

---

## 8. Recommended Project Structure

```
certificate_manager/
│
├── db/
│   ├── db.py               # Connection factory (SQLite / MySQL)
│   ├── schema_sqlite.sql   # SQLite schema (local cache)
│   ├── schema_mysql.sql    # MySQL schema (server)
│   └── migrations/         # Versioned migration scripts
│
├── repositories/
│   ├── student_repo.py
│   ├── personnel_repo.py
│   └── ...
│
├── sync/
│   ├── sync_worker.py      # Queue processor
│   └── cache_refresh.py    # Pull-down from server
│
├── ui/
│   ├── main_window.py
│   └── ...
│
├── certificate_manager_local.db   # Local SQLite cache (runtime)
└── config.py                      # Server host, credentials
```

---

## 9. Security Checklist

- [ ] **Hash all passwords** with `bcrypt` before inserting into MySQL (`personnel.password_hash`). Never store plain text.
- [ ] **Use environment variables** (`.env` file or OS env) for the MySQL host, username, and password. Do not hardcode them in source code.
- [ ] **Restrict MySQL access** by IP. The MySQL port (3306) should only be reachable from your office network or via VPN — not the open internet.
- [ ] **Use a least-privilege DB user** for the application — `SELECT`, `INSERT`, `UPDATE`, `DELETE` only on the `certificate_manager` database. No `DROP`, `CREATE`, or `GRANT`.
- [ ] **Encrypt traffic** with SSL/TLS between the client and MySQL server (`ssl_ca`, `ssl_cert`, `ssl_key` in the connector config).
- [ ] **Keep the sync queue clean** — periodically purge rows where `synced=1` older than 30 days.
- [ ] **Log all certificate prints** to both `certificate_logs` tables (local and server) for audit purposes.
- [ ] **Back up MySQL daily** via `mysqldump` and store securely off-server.
- [ ] **Never expose raw MySQL** through Apache. If you need HTTP access, build a thin PHP or Python REST API on the server instead.
- [ ] **Test the offline scenario** deliberately by disconnecting the network and confirming the app still reads, writes, and queues correctly before going live.
