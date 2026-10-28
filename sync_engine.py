# =============================================================================
# sync_engine.py — Offline Sync Engine & Temporary ID Mapping
# =============================================================================
#
# PURPOSE:
#   Allow users to create records (students, academic periods, enrollments)
#   while offline by assigning temporary negative IDs in a local SQLite DB.
#   When the system comes back online, the sync loop pushes queued writes
#   to MySQL and resolves temp IDs to real auto-increment IDs across all
#   local relational tables.
#
# ARCHITECTURE:
#   ┌────────────┐   offline   ┌──────────────┐
#   │   UI Layer │ ──────────► │ local_cache.db│  (SQLite)
#   └────────────┘             └──────┬───────┘
#                                     │  online
#                                     ▼
#                              ┌──────────────┐
#                              │  MySQL (SPs)  │
#                              └──────────────┘
#
# TABLES IN local_cache.db:
#   sync_queue        — ordered log of pending write operations
#   temp_id_counter   — monotonically decreasing counter for unique neg IDs
#   local_students    — offline-created student rows
#   local_academic_periods — offline-created period rows
#   local_enrollments — offline-created enrollment rows
#
# PUBLIC API:
#   init_local_db()                        → create tables if absent
#   generate_temp_id()                     → next unique negative int
#   log_offline_insert(table, payload)     → queue a write, return temp_id
#   sync_offline_queue_to_mysql(mysql_conn)→ flush queue & resolve IDs
#
# =============================================================================

import hashlib
import json
import logging
import sqlite3
import threading
from datetime import date, datetime
from pathlib import Path
import requests
import api_client
import app_paths
from api_config import API_URL, get_api_url

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Network Status — cached flag + pinger
# ---------------------------------------------------------------------------

_is_online: bool = True   # assume online until first check


def is_online() -> bool:
    """Return the cached network status flag (no I/O)."""
    return _is_online


def set_online(status: bool) -> None:
    """Update the cached network status flag (called by the polling loop)."""
    global _is_online
    _is_online = status


def check_network_status(target_url: str | None = None) -> bool:
    """
    Attempt a fast, low-timeout HTTP GET request to the FastAPI server ping endpoint.

    Returns True if FastAPI is reachable, False otherwise.
    This function is called every ~8 seconds from the UI polling loop.
    It does NOT update the cached flag — the caller must call set_online().
    """
    url = target_url or get_api_url()
    try:
        response = api_client.get(f"{url}/ping", timeout=2.0)
        return response.status_code == 200
    except requests.RequestException:
        return False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LOCAL_DB_PATH = app_paths.data_path("local_cache.db")
DB_PATH = str(_LOCAL_DB_PATH)

# Maps a logical table name to:
#   - local_table:  the SQLite mirror table
#   - columns:      column list for INSERT (excluding 'id', which is the temp PK)
#   - sp_name:      the MySQL Stored Procedure used for INSERT
#   - sp_args:      ordered list of payload keys matching the SP's positional args
#   - fk_cascades:  list of (child_local_table, fk_column) pairs whose values
#                   must be updated when this table's temp_id is resolved
_TABLE_REGISTRY: dict[str, dict] = {
    "students": {
        "local_table": "local_students",
        "columns": [
            "full_name_ar", "full_name_en", "gender",
            "sequence_number", "postgraduation_number", "date_of_birth",
            "birthplace_id", "birthplace_other", "nationality_id", "national_id",
            "department_id", "study_system_id", "degree_level",
            "order_id", "admission_year", "summer_training_data",
            "average", "graduation_date", "graduation_semester",
        ],
        "sp_name": "InsertStudent",
        "sp_args": [
            "full_name_ar", "full_name_en", "gender",
            "sequence_number", "postgraduation_number", "date_of_birth",
            "birthplace_id", "birthplace_other", "nationality_id", "national_id",
            "department_id", "study_system_id", "degree_level",
            "order_id", "admission_year", "summer_training_data",
            "average", "graduation_date", "graduation_semester",
        ],
        "fk_cascades": [
            ("local_academic_periods", "student_id"),
            ("local_issued_certificates", "student_id"),
        ],
    },
    "academic_periods": {
        "local_table": "local_academic_periods",
        "columns": [
            "student_id", "academic_year", "study_system_id",
            "stage_number", "semester_num", "result_status",
        ],
        "sp_name": None,  # uses raw INSERT (no SP in current repo)
        "sp_args": [],
        "insert_sql": (
            "INSERT INTO academic_periods "
            "(student_id, academic_year, study_system_id, stage_number, semester_num, result_status) "
            "VALUES (%s, %s, %s, %s, %s, %s)"
        ),
        "insert_keys": [
            "student_id", "academic_year", "study_system_id",
            "stage_number", "semester_num", "result_status",
        ],
        "fk_cascades": [
            ("local_enrollments", "period_id"),
        ],
    },
    "enrollments": {
        "local_table": "local_enrollments",
        "columns": [
            "period_id", "course_id", "score", "passed_round",
        ],
        "sp_name": None,
        "sp_args": [],
        "insert_sql": (
            "INSERT INTO enrollments "
            "(period_id, course_id, score, passed_round) "
            "VALUES (%s, %s, %s, %s)"
        ),
        "insert_keys": [
            "period_id", "course_id", "score", "passed_round",
        ],
        "fk_cascades": [],
    },
    "issued_certificates": {
        "local_table": "local_issued_certificates",
        "columns": [
            "student_id", "to_title", "template_type", "issue_date", "certificate_number",
        ],
        "sp_name": "InsertIssuedCertificate",
        "sp_args": [
            "student_id", "to_title", "template_type", "issue_date", "certificate_number",
        ],
        "fk_cascades": [],
    },
    "study_routines": {
        "local_table": "study_routines",
        "columns": [
            "name_ar", "name_en", "department_id", "study_system_id",
        ],
        "sp_name": "InsertStudyRoutine",
        "sp_args": [
            "name_ar", "name_en", "department_id", "study_system_id",
        ],
        "fk_cascades": [
            ("study_routine_period", "routine_id"),
        ],
    },
    "study_routine_period": {
        "local_table": "study_routine_period",
        "columns": [
            "routine_id", "stage_number", "semester_num",
        ],
        "sp_name": "InsertStudyRoutinePeriod",
        "sp_args": [
            "routine_id", "stage_number", "semester_num",
        ],
        "fk_cascades": [
            ("study_routine_courses", "period_id"),
        ],
    },
    "study_routine_courses": {
        "local_table": "study_routine_courses",
        "columns": [
            "routine_id", "course_id",
        ],
        "sp_name": "InsertStudyRoutineCourse",
        "sp_args": [
            "routine_id", "course_id",
        ],
        "fk_cascades": [],
    },
    "study_routine_period_courses": {
        "local_table": "study_routine_courses",
        "columns": [
            "period_id", "course_id",
        ],
        "sp_name": "InsertStudyRoutinePeriodCourse",
        "sp_args": [
            "period_id", "course_id",
        ],
        "fk_cascades": [],
    },
}


# ---------------------------------------------------------------------------
# JSON Helpers — safe serialisation of dates and None
# ---------------------------------------------------------------------------

class _SafeEncoder(json.JSONEncoder):
    """Encode date/datetime objects as ISO strings; None passes through."""
    def default(self, o):
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        return super().default(o)


def _json_dumps(payload) -> str:
    return json.dumps(payload, cls=_SafeEncoder, ensure_ascii=False)


def _json_loads(text: str) -> dict:
    return json.loads(text)


# ---------------------------------------------------------------------------
# Task 1 — Initialise the Local SQLite Database & Sync Queue
# ---------------------------------------------------------------------------

def _get_local_conn() -> sqlite3.Connection:
    """Return a connection to the local SQLite cache database."""
    conn = sqlite3.connect(str(_LOCAL_DB_PATH))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def get_local_connection() -> sqlite3.Connection:
    """Public access to a local SQLite connection for offline reads.

    Returns a connection with row_factory=sqlite3.Row so that rows
    can be accessed by column name.  Callers MUST close the connection.
    """
    return _get_local_conn()


def sqlite_read_all(query: str, params: tuple = ()) -> list[dict]:
    """Execute a SELECT on the local SQLite replica and return all rows as dicts."""
    conn = _get_local_conn()
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.debug("sqlite_read_all failed: %s | %s", query, exc)
        return []
    finally:
        conn.close()


def sqlite_read_one(query: str, params: tuple = ()) -> dict | None:
    """Execute a SELECT on the local SQLite replica and return one row as dict."""
    conn = _get_local_conn()
    try:
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None
    except Exception as exc:
        log.debug("sqlite_read_one failed: %s | %s", query, exc)
        return None
    finally:
        conn.close()


def init_local_db() -> None:
    """
    Create the local SQLite tables if they do not already exist.

    Called once at application startup, right after (or instead of) init_db().
    """
    conn = _get_local_conn()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        cur = conn.cursor()

        # -- Sync queue: ordered log of pending offline writes ----------------
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sync_queue (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name  TEXT    NOT NULL,
                operation   TEXT    NOT NULL DEFAULT 'INSERT',
                temp_id     INTEGER NOT NULL,
                payload     TEXT    NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # -- Temp ID counter: single-row table holding the last issued ID -----
        cur.execute("""
            CREATE TABLE IF NOT EXISTS temp_id_counter (
                id      INTEGER PRIMARY KEY CHECK (id = 1),
                last_id INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Seed the counter row if it doesn't exist
        cur.execute(
            "INSERT OR IGNORE INTO temp_id_counter (id, last_id) VALUES (1, 0)"
        )

        # -- Local mirror tables ---------------------------------------------
        cur.execute("""
            CREATE TABLE IF NOT EXISTS local_students (
                id                  INTEGER PRIMARY KEY,
                full_name_ar        TEXT,
                full_name_en        TEXT,
                gender              INTEGER DEFAULT 1,
                sequence_number     INTEGER,
                postgraduation_number   INTEGER,
                date_of_birth       TEXT,
                birthplace_id       INTEGER,
                birthplace_other    TEXT,
                nationality_id      INTEGER,
                national_id         TEXT,
                department_id       INTEGER,
                study_system_id     INTEGER,
                degree_level        INTEGER DEFAULT 1,
                order_id            INTEGER,
                admission_year      TEXT,
                summer_training_data TEXT,
                average             REAL,
                graduation_date     TEXT,
                graduation_semester TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS local_academic_periods (
                id              INTEGER PRIMARY KEY,
                student_id      INTEGER NOT NULL,
                academic_year   TEXT,
                study_system_id INTEGER,
                stage_number    INTEGER,
                semester_num    INTEGER,
                result_status   INTEGER DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS local_enrollments (
                id           INTEGER PRIMARY KEY,
                period_id    INTEGER NOT NULL,
                course_id    INTEGER NOT NULL,
                score        REAL,
                passed_round TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS local_issued_certificates (
                id                 INTEGER PRIMARY KEY,
                student_id         INTEGER NOT NULL,
                to_title           TEXT DEFAULT 'من يهمه الأمر',
                template_type      TEXT DEFAULT 'ARABIC',
                certificate_number TEXT,
                issue_date         TEXT,
                created_at         TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # -- Read cache: transparent SP result cache for offline reads -------
        cur.execute("""
            CREATE TABLE IF NOT EXISTS read_cache (
                cache_key   TEXT PRIMARY KEY,
                result_json TEXT NOT NULL,
                cached_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # -- Predefined Study Routines & Template Courses tables --------------
        cur.execute("""
            CREATE TABLE IF NOT EXISTS study_routines (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name_ar         TEXT NOT NULL,
                name_en         TEXT NOT NULL,
                department_id   INTEGER NOT NULL,
                study_system_id INTEGER NOT NULL DEFAULT 1,
                stage_number    INTEGER NOT NULL DEFAULT 1,
                semester_num    INTEGER NOT NULL DEFAULT 1,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS study_routine_courses (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                period_id       INTEGER NOT NULL,
                course_id       INTEGER NOT NULL,
                UNIQUE(period_id, course_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS study_routine_period (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                routine_id      INTEGER NOT NULL,
                stage_number    INTEGER NOT NULL DEFAULT 1,
                semester_num    INTEGER NOT NULL DEFAULT 1
            )
        """)

        # removed obsolete ALTER TABLE for study_routine_courses


        # -- Replica tables: full read-only mirrors of MySQL tables ----------
        # These are populated by pull_mysql_to_sqlite() whenever the app
        # is online, so that offline reads can query structured data.

        cur.execute("""
            CREATE TABLE IF NOT EXISTS personnel (
                id                     INTEGER PRIMARY KEY,
                name_ar                TEXT,
                name_en                TEXT,
                academic_title_ar      TEXT,
                academic_title_en      TEXT,
                responsibility_ar      TEXT,
                responsibility_en      TEXT,
                display_order          INTEGER DEFAULT 0,
                username               TEXT,
                password_hash          TEXT,
                personnel_role         TEXT DEFAULT 'user',
                university_settings_id INTEGER DEFAULT 1,
                is_active              INTEGER DEFAULT 1,
                created_at             TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id                    INTEGER PRIMARY KEY,
                full_name_ar          TEXT,
                full_name_en          TEXT,
                gender                INTEGER DEFAULT 1,
                sequence_number       INTEGER,
                postgraduation_number INTEGER,
                date_of_birth         TEXT,
                birthplace_id         INTEGER,
                birthplace_other      TEXT,
                nationality_id        INTEGER DEFAULT 1,
                national_id           TEXT,
                department_id         INTEGER,
                study_system_id       INTEGER,
                degree_level          INTEGER DEFAULT 1,
                order_id              INTEGER,
                admission_year        TEXT,
                summer_training_data  TEXT,
                average               REAL,
                graduation_date       TEXT,
                graduation_semester   TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS academic_periods (
                id              INTEGER PRIMARY KEY,
                student_id      INTEGER NOT NULL,
                academic_year   TEXT,
                study_system_id INTEGER,
                stage_number    INTEGER,
                semester_num    INTEGER DEFAULT 1,
                result_status   INTEGER DEFAULT 1
            )
        """)
        try:
            cur.execute("ALTER TABLE academic_periods ADD COLUMN semester_num INTEGER DEFAULT 1;")
        except sqlite3.OperationalError:
            pass


        cur.execute("""
            CREATE TABLE IF NOT EXISTS enrollments (
                id              INTEGER PRIMARY KEY,
                period_id       INTEGER NOT NULL,
                course_id       INTEGER NOT NULL,
                score           REAL,
                passed_round    TEXT DEFAULT '1'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id              INTEGER PRIMARY KEY,
                name_ar         TEXT,
                name_en         TEXT,
                credit_hours    INTEGER,
                department_id   INTEGER,
                stage_number    INTEGER
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                id                     INTEGER PRIMARY KEY,
                name_ar                TEXT,
                name_en                TEXT,
                university_settings_id INTEGER DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS study_systems (
                id                  INTEGER PRIMARY KEY,
                name_ar             TEXT,
                name_en             TEXT,
                study_day_type      TEXT DEFAULT 'Morning',
                calculation_rule    TEXT DEFAULT 'annual',
                calculation_weights TEXT DEFAULT '10:20:30:40',
                period_display      TEXT DEFAULT 'semester',
                is_active           INTEGER DEFAULT 1,
                created_at          TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS graduation_orders (
                id                  INTEGER PRIMARY KEY,
                order_number        TEXT,
                order_date          TEXT,
                department_id       INTEGER,
                study_type          TEXT,
                graduation_year     INTEGER,
                admission_year      INTEGER,
                graduation_semester TEXT,
                num_students        INTEGER,
                notes               TEXT,
                study_system_id     INTEGER DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS university_settings (
                id              INTEGER PRIMARY KEY,
                univ_name_ar    TEXT,
                univ_name_en    TEXT,
                college_name_ar TEXT,
                college_name_en TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS countries (
                id       INTEGER PRIMARY KEY,
                name_ar  TEXT,
                name_en  TEXT,
                iso_code TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS governorates (
                id      INTEGER PRIMARY KEY,
                name_ar TEXT,
                name_en TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings(
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                EMP_ID          INTEGER UNIQUE,
                theme           TEXT DEFAULT 'System',
                accent_color    TEXT DEFAULT 'blue',
                font_family     TEXT DEFAULT 'Arial',
                font_size_base  INTEGER DEFAULT 13,
                is_arabic_rtl   INTEGER DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS student_supervisors (
                id               INTEGER PRIMARY KEY,
                student_id       INTEGER NOT NULL,
                personnel_id     INTEGER NOT NULL,
                supervision_role TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS thesis_records (
                id                 INTEGER PRIMARY KEY,
                student_id         INTEGER NOT NULL,
                title_ar           TEXT,
                title_en           TEXT,
                defense_date       TEXT,
                committee_decision TEXT,
                final_grade        REAL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS issued_certificates (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id         INTEGER NOT NULL,
                to_title           TEXT NOT NULL DEFAULT 'من يهمه الأمر',
                template_type      TEXT NOT NULL DEFAULT 'ARABIC',
                certificate_number TEXT,
                issue_date         TEXT NOT NULL,
                created_at         TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS permissions (
                permission_key TEXT PRIMARY KEY,
                category       TEXT,
                name_ar        TEXT,
                name_en        TEXT,
                description_ar TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS personnel_permissions (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                personnel_id   INTEGER NOT NULL,
                permission_key TEXT NOT NULL,
                is_granted     INTEGER DEFAULT 1,
                created_at     TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(personnel_id, permission_key)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id               TEXT PRIMARY KEY,
                name_ar          TEXT NOT NULL,
                name_en          TEXT NOT NULL,
                description_ar   TEXT,
                base_role        TEXT NOT NULL DEFAULT 'user',
                allowed_pages    TEXT NOT NULL DEFAULT '[]',
                allowed_actions  TEXT NOT NULL DEFAULT '[]',
                department_scope TEXT NOT NULL DEFAULT 'all',
                is_system        INTEGER NOT NULL DEFAULT 0,
                created_at       TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Self-healing migration: personnel.must_change_password (forced password change)
        try:
            cur.execute("PRAGMA table_info(personnel)")
            if "must_change_password" not in [row[1] for row in cur.fetchall()]:
                cur.execute("ALTER TABLE personnel ADD COLUMN must_change_password INTEGER DEFAULT 0")
        except Exception as _pw_mig_err:
            log.warning("personnel migration notice: %s", _pw_mig_err)

        # Roles copied from MySQL (roles / user_roles); also used before the server has them
        cur.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id               TEXT PRIMARY KEY,
                name_ar          TEXT NOT NULL,
                name_en          TEXT NOT NULL,
                description_ar   TEXT,
                base_role        TEXT NOT NULL DEFAULT 'user',
                allowed_pages    TEXT NOT NULL DEFAULT '[]',
                allowed_actions  TEXT NOT NULL DEFAULT '[]',
                department_scope TEXT NOT NULL DEFAULT 'all',
                is_system        INTEGER NOT NULL DEFAULT 0,
                created_at       TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_roles (
                personnel_id INTEGER PRIMARY KEY,
                role_id      TEXT NOT NULL,
                updated_at   TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Change-only download: per-table "since" marker and the time of the last full download
        cur.execute("""
            CREATE TABLE IF NOT EXISTS replica_sync_state (
                table_name TEXT PRIMARY KEY,
                since      TEXT,
                last_full  TEXT
            )
        """)
        # This laptop's reserved block of certificate numbers (offline printing)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cert_number_block (
                id          INTEGER PRIMARY KEY CHECK (id = 1),
                year_suffix TEXT NOT NULL,
                start_no    INTEGER NOT NULL,
                end_no      INTEGER NOT NULL,
                next_no     INTEGER NOT NULL
            )
        """)
        # Stable identifier of this laptop (sent when reserving certificate numbers)
        cur.execute("CREATE TABLE IF NOT EXISTS device_info (key TEXT PRIMARY KEY, value TEXT)")

        # Self-healing migration: sync_queue tracking columns (pending / failed, last error, attempts)
        try:
            cur.execute("PRAGMA table_info(sync_queue)")
            sq_cols = [row[1] for row in cur.fetchall()]
            if "status" not in sq_cols:
                log.info("Migrating SQLite sync_queue table: adding status/last_error/attempts columns...")
                cur.execute("ALTER TABLE sync_queue ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
                cur.execute("ALTER TABLE sync_queue ADD COLUMN last_error TEXT")
                cur.execute("ALTER TABLE sync_queue ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
        except Exception as _sq_mig_err:
            log.warning("sync_queue migration notice: %s", _sq_mig_err)

        # Self-healing migration: add certificate_number column to issued_certificates & local_issued_certificates if missing
        try:
            cur.execute("PRAGMA table_info(issued_certificates)")
            ic_cols = [row[1] for row in cur.fetchall()]
            if "certificate_number" not in ic_cols:
                log.info("Migrating SQLite issued_certificates table: adding certificate_number column...")
                cur.execute("ALTER TABLE issued_certificates ADD COLUMN certificate_number TEXT")

            cur.execute("PRAGMA table_info(local_issued_certificates)")
            lic_cols = [row[1] for row in cur.fetchall()]
            if "certificate_number" not in lic_cols:
                log.info("Migrating SQLite local_issued_certificates table: adding certificate_number column...")
                cur.execute("ALTER TABLE local_issued_certificates ADD COLUMN certificate_number TEXT")
        except Exception as _mig_err:
            log.warning(f"Self-healing certificate_number migration notice: {_mig_err}")

        # Self-healing migration: drop obsolete settings_id column if it exists
        try:
            cur.execute("PRAGMA table_info(personnel)")
            personnel_cols = [row[1] for row in cur.fetchall()]

            if "settings_id" in personnel_cols:
                log.info("Migrating SQLite personnel table: dropping settings_id column...")
                cur.execute("""
                    CREATE TABLE personnel_temp (
                        id                     INTEGER PRIMARY KEY,
                        name_ar                TEXT,
                        name_en                TEXT,
                        academic_title_ar      TEXT,
                        academic_title_en      TEXT,
                        responsibility_ar      TEXT,
                        responsibility_en      TEXT,
                        display_order          INTEGER DEFAULT 0,
                        username               TEXT,
                        password_hash          TEXT,
                        personnel_role         TEXT DEFAULT 'user',
                        university_settings_id INTEGER DEFAULT 1,
                        is_active              INTEGER DEFAULT 1,
                        created_at             TEXT
                    )
                """)
                cur.execute("""
                    INSERT INTO personnel_temp (
                        id, name_ar, name_en, academic_title_ar, academic_title_en,
                        responsibility_ar, responsibility_en, display_order,
                        username, password_hash, personnel_role,
                        university_settings_id, is_active, created_at
                    )
                    SELECT
                        id, name_ar, name_en, academic_title_ar, academic_title_en,
                        responsibility_ar, responsibility_en, display_order,
                        username, password_hash, personnel_role,
                        university_settings_id, is_active, created_at
                    FROM personnel
                """)
                cur.execute("DROP TABLE personnel")
                cur.execute("ALTER TABLE personnel_temp RENAME TO personnel")
        except Exception as exc:
            log.warning("Migration for personnel table failed: %s", exc)

        try:
            cur.execute("PRAGMA table_info(settings)")
            settings_cols = [row[1] for row in cur.fetchall()]
            if "EMP_ID" not in settings_cols:
                log.info("Migrating SQLite settings table: adding EMP_ID column...")
                cur.execute("ALTER TABLE settings ADD COLUMN EMP_ID INTEGER;")
                cur.execute("UPDATE settings SET EMP_ID = 1 WHERE EMP_ID IS NULL;")
        except Exception as exc:
            log.warning("Migration for settings table failed: %s", exc)

        try:
            cur.execute("ALTER TABLE local_students ADD COLUMN admission_year TEXT DEFAULT NULL;")
        except sqlite3.OperationalError:
            pass

        try:
            cur.execute("ALTER TABLE students ADD COLUMN admission_year TEXT DEFAULT NULL;")
        except sqlite3.OperationalError:
            pass

        try:
            cur.execute("ALTER TABLE local_students ADD COLUMN national_id TEXT DEFAULT NULL;")
        except sqlite3.OperationalError:
            pass

        try:
            cur.execute("ALTER TABLE students ADD COLUMN national_id TEXT DEFAULT NULL;")
        except sqlite3.OperationalError:
            pass

        try:
            cur.execute("ALTER TABLE graduation_orders ADD COLUMN admission_year INTEGER DEFAULT NULL;")
        except sqlite3.OperationalError:
            pass

        try:
            cur.execute("ALTER TABLE graduation_orders ADD COLUMN graduation_year INTEGER DEFAULT NULL;")
        except sqlite3.OperationalError:
            pass

        try:
            cur.execute("ALTER TABLE university_settings ADD COLUMN univ_logo_path TEXT DEFAULT 'assets/univ_logo.png';")
        except sqlite3.OperationalError:
            pass

        try:
            cur.execute("ALTER TABLE university_settings ADD COLUMN college_logo_path TEXT DEFAULT 'assets/college_logo.png';")
        except sqlite3.OperationalError:
            pass

        conn.commit()
        log.info("Local SQLite cache initialised at %s", _LOCAL_DB_PATH)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Inbound Sync — pull full MySQL tables into SQLite replica
# ---------------------------------------------------------------------------

# Tables to replicate and their SELECT queries.
# Order matters: parent tables first so FK references are valid.
_REPLICA_TABLES: list[tuple[str, str]] = [
    ("university_settings", "SELECT * FROM university_settings"),
    ("countries",           "SELECT * FROM countries"),
    ("governorates",        "SELECT * FROM governorates"),
    ("settings",            "SELECT * FROM settings"),
    ("departments",         "SELECT * FROM departments"),
    ("study_systems",       "SELECT * FROM study_systems"),
    ("personnel",           "SELECT * FROM personnel"),
    ("courses",             "SELECT * FROM courses"),
    ("graduation_orders",   "SELECT * FROM graduation_orders"),
    ("students",            "SELECT * FROM students"),
    ("academic_periods",    "SELECT * FROM academic_periods"),
    ("enrollments",         "SELECT * FROM enrollments"),
    ("student_supervisors", "SELECT * FROM student_supervisors"),
    ("thesis_records",      "SELECT * FROM thesis_records"),
    ("issued_certificates", "SELECT * FROM issued_certificates"),
    ("study_routines",      "SELECT * FROM study_routines"),
    ("study_routine_period", "SELECT * FROM study_routine_period"),
    ("study_routine_courses", "SELECT * FROM study_routine_courses"),
    ("permissions",         "SELECT * FROM permissions"),
    ("personnel_permissions", "SELECT * FROM personnel_permissions"),
    ("roles",               "SELECT * FROM roles"),
    ("user_roles",          "SELECT * FROM user_roles"),
]

# Tables a laptop must not wipe when the server returns no rows: an empty roles
# table means the server is not set up for roles yet, not "delete every role".
_KEEP_LOCAL_IF_SERVER_EMPTY = {"roles", "user_roles"}


FULL_REPLICA_EVERY_HOURS = 24

# MySQL deletes these child rows automatically (ON DELETE CASCADE) but cascaded deletes do
# not fire the delete triggers, so the change-only download never reports them:
# parent table -> [(child table, foreign key column)]
_CASCADE_CHILDREN = {
    "students": [("academic_periods", "student_id"), ("student_supervisors", "student_id"),
                 ("thesis_records", "student_id"), ("issued_certificates", "student_id")],
    "academic_periods": [("enrollments", "period_id")],
    "study_routines": [("study_routine_period", "routine_id")],
    "study_routine_period": [("study_routine_courses", "period_id")],
    "personnel": [("personnel_permissions", "personnel_id"), ("settings", "EMP_ID")],
}


def _hours_since(timestamp_text: str) -> float:
    try:
        return (datetime.now() - datetime.strptime(str(timestamp_text)[:19], "%Y-%m-%d %H:%M:%S")).total_seconds() / 3600
    except (TypeError, ValueError):
        return float("inf")


def _save_sync_state(sqlite_conn, table_name: str, since: str | None, last_full: str | None) -> None:
    sqlite_conn.execute(
        "INSERT INTO replica_sync_state (table_name, since, last_full) VALUES (?, ?, ?) "
        "ON CONFLICT(table_name) DO UPDATE SET since = excluded.since, last_full = excluded.last_full",
        (table_name, since, last_full),
    )


def _remove_orphaned_children(sqlite_conn, parents: set[str]) -> None:
    """After rows were deleted from parent tables, delete local child rows that lost their parent."""
    todo = list(parents)
    while todo:
        parent = todo.pop()
        for child, fk in _CASCADE_CHILDREN.get(parent, []):
            try:
                cur = sqlite_conn.execute(
                    f"DELETE FROM {child} WHERE {fk} IS NOT NULL AND {fk} NOT IN (SELECT id FROM {parent})"
                )
                if cur.rowcount:
                    log.info("Removed %d %s rows whose %s was deleted on the server", cur.rowcount, child, parent)
                    todo.append(child)
            except Exception as exc:
                log.debug("Orphan cleanup %s.%s skipped: %s", child, fk, exc)
    sqlite_conn.commit()


def pull_mysql_to_sqlite(mysql_conn=None, sqlite_conn=None, tables: list[str] | None = None,
                         force_full: bool = False) -> dict:
    """
    Download a full read-only replica of essential MySQL tables into SQLite, through FastAPI.

    Strategy (safe for <100k rows), per table:
        1. GET /replica/{table} from the API
        2. DELETE FROM local_table
        3. INSERT INTO local_table (all fetched rows)

    Args:
        mysql_conn: Unused; kept so older callers keep working. MySQL is only reached through FastAPI.
        sqlite_conn: Optional pre-opened SQLite connection. If None, one is created internally.
        tables: Only these tables (None = all replicated tables).
        force_full: Download every row even when a change-only download is possible.

    Once the server has updated_at columns (sql/fixes/2026-10-24_03), only rows changed
    since the last download (and deleted ids) are fetched; a full download still happens
    once every FULL_REPLICA_EVERY_HOURS.

    Returns:
        {"tables_synced": int, "total_rows": int, "errors": list[str]}
    """
    own_sqlite = sqlite_conn is None
    if own_sqlite:
        sqlite_conn = _get_local_conn()

    tables_synced = 0
    total_rows = 0
    errors: list[str] = []

    def safe_cast(val):
        if val is None: return None
        if isinstance(val, (int, float)): return val
        if isinstance(val, (date, datetime)): return str(val)
        if isinstance(val, (bytearray, bytes)):
            try:
                return val.decode('utf-8')
            except UnicodeDecodeError:
                return str(val)
        return str(val)

    api_url = get_api_url()
    sqlite_conn.execute(
        "CREATE TABLE IF NOT EXISTS replica_sync_state (table_name TEXT PRIMARY KEY, since TEXT, last_full TEXT)"
    )
    sync_state = {
        r["table_name"]: (r["since"], r["last_full"])
        for r in sqlite_conn.execute("SELECT table_name, since, last_full FROM replica_sync_state").fetchall()
    }
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tables_with_deletions: set[str] = set()
    try:
        for table_name, _select_sql in _REPLICA_TABLES:
            if tables is not None and table_name not in tables:
                continue
            try:
                # Change-only download when this table has a marker and had a full download in
                # the last 24 h; otherwise everything (the daily full download also corrects
                # anything a change-only download cannot see)
                since, last_full = sync_state.get(table_name, (None, None))
                params = {}
                if since and not force_full and last_full and _hours_since(last_full) < FULL_REPLICA_EVERY_HOURS:
                    params["since"] = since

                # Fetch from MySQL through FastAPI
                resp = api_client.get(f"{api_url}/replica/{table_name}", params=params, timeout=60.0)
                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                body = resp.json()
                columns = body.get("columns") or []
                rows = body.get("rows") or []
                is_delta = body.get("mode") == "delta"

                if not rows and not is_delta:
                    if table_name in _KEEP_LOCAL_IF_SERVER_EMPTY:
                        log.info("Server has no %s rows yet; keeping this laptop's copy", table_name)
                        continue
                    # Still clear local data even if MySQL table is empty
                    sqlite_conn.execute(f"DELETE FROM {table_name}")
                    _save_sync_state(sqlite_conn, table_name, body.get("next_since"), now_text)
                    sqlite_conn.commit()
                    tables_synced += 1
                    continue

                # A column added in MySQL (e.g. by an update SQL file) is added here too,
                # otherwise every INSERT for this table would fail with "no such column"
                local_cols = {r[1] for r in sqlite_conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
                for col in columns:
                    if local_cols and col not in local_cols:
                        sqlite_conn.execute(f'ALTER TABLE {table_name} ADD COLUMN "{col}"')
                        log.info("Added column %s.%s to the local copy", table_name, col)

                col_clause = ", ".join(columns)
                placeholders = ", ".join(["?"] * len(columns))
                insert_data = [tuple(safe_cast(v) for v in row) for row in rows]

                if is_delta:
                    # Only changed rows: upsert them, remove rows deleted on the server
                    deleted_ids = [int(i) for i in (body.get("deleted_ids") or [])]
                    if deleted_ids:
                        sqlite_conn.executemany(f"DELETE FROM {table_name} WHERE id = ?", [(i,) for i in deleted_ids])
                        tables_with_deletions.add(table_name)
                    if insert_data:
                        sqlite_conn.executemany(
                            f"INSERT OR REPLACE INTO {table_name} ({col_clause}) VALUES ({placeholders})",
                            insert_data,
                        )
                    _save_sync_state(sqlite_conn, table_name, body.get("next_since"), last_full)
                else:
                    # Clear + insert
                    sqlite_conn.execute(f"DELETE FROM {table_name}")
                    sqlite_conn.executemany(
                        f"INSERT OR REPLACE INTO {table_name} ({col_clause}) VALUES ({placeholders})",
                        insert_data,
                    )
                    _save_sync_state(sqlite_conn, table_name, body.get("next_since"), now_text)
                sqlite_conn.commit()
                tables_synced += 1
                total_rows += len(rows)
                log.debug("Replicated %s (%s): %d rows", table_name, "changes" if is_delta else "full", len(rows))

            except requests.exceptions.ConnectionError as exc:
                # Server unreachable: stop instead of waiting on every remaining table
                log.warning("Cannot reach API to pull replica: %s", exc)
                errors.append(f"{table_name}: {exc}")
                break
            except Exception as exc:
                log.error("Failed to replicate table %s: %s", table_name, exc)
                errors.append(f"{table_name}: {exc}")

        if tables_with_deletions:
            _remove_orphaned_children(sqlite_conn, tables_with_deletions)

    finally:
        if own_sqlite and sqlite_conn:
            sqlite_conn.close()

    # Role assignments may have changed: drop the in-memory copy so the next lookup reads the new data
    try:
        import data.repositories as _repos
        _repos._USER_ROLE_CACHE = None
    except Exception:
        pass

    summary = {"tables_synced": tables_synced, "total_rows": total_rows, "errors": errors}
    log.info("Inbound sync complete: %s", summary)
    return summary


# Reference tables screens read from the local copy first (repositories, "local-first").
# They are small, change rarely, and their local rows match the API's rows field for field.
LOCAL_FIRST_TABLES = ["departments", "study_systems", "courses", "countries", "governorates", "graduation_orders"]


def refresh_replica_tables(tables: list[str]) -> bool:
    """Re-download just these tables (e.g. right after a change was saved online). True on success."""
    if not is_online():
        return False
    result = pull_mysql_to_sqlite(tables=list(tables))
    return not result["errors"]


def refresh_replica_tables_background(tables: list[str]) -> None:
    """Same as refresh_replica_tables, on a background thread (never blocks the UI)."""
    threading.Thread(target=lambda: refresh_replica_tables(tables), daemon=True,
                     name="replica-refresh").start()


def pull_mysql_to_sqlite_background() -> None:
    """
    Run pull_mysql_to_sqlite in a background thread.

    Safe to call from the UI thread — spawns a daemon thread that
    downloads through FastAPI and opens its own SQLite connection.
    """
    def _worker():
        try:
            pull_mysql_to_sqlite()
        except Exception as exc:
            log.error("Background inbound sync failed: %s", exc)

    t = threading.Thread(target=_worker, daemon=True, name="inbound-sync")
    t.start()


# ---------------------------------------------------------------------------
# Read Cache — transparent SP result caching for offline browsing
# ---------------------------------------------------------------------------

def _make_cache_key(proc_name: str, args: tuple) -> str:
    """Build a deterministic cache key from a procedure name and its args."""
    raw = f"{proc_name}:{_json_dumps_for_key(args)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _json_dumps_for_key(obj) -> str:
    """Serialize args tuple to a stable JSON string for hashing."""
    return json.dumps(obj, cls=_SafeEncoder, ensure_ascii=False, sort_keys=True)


def cache_read_result(proc_name: str, args: tuple, result: list[dict]) -> None:
    """
    Store a MySQL SP read result in the local SQLite cache.

    Called transparently after every successful online read so that
    the data is available for offline browsing.
    """
    key = _make_cache_key(proc_name, args)
    conn = _get_local_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO read_cache (cache_key, result_json, cached_at) "
            "VALUES (?, ?, CURRENT_TIMESTAMP)",
            (key, _json_dumps(result)),
        )
        conn.commit()
    except Exception as exc:
        log.debug("Failed to cache read result for %s: %s", proc_name, exc)
    finally:
        conn.close()


def get_cached_read(proc_name: str, args: tuple) -> list[dict] | None:
    """
    Retrieve a previously cached SP result from SQLite.

    Returns the deserialized list of dicts, or None if no cache entry exists.
    """
    key = _make_cache_key(proc_name, args)
    conn = _get_local_conn()
    try:
        row = conn.execute(
            "SELECT result_json FROM read_cache WHERE cache_key = ?", (key,)
        ).fetchone()
        if row:
            return json.loads(row["result_json"])
        return None
    except Exception as exc:
        log.debug("Failed to read cache for %s: %s", proc_name, exc)
        return None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Task 2 — Temporary ID Generator
# ---------------------------------------------------------------------------

def generate_temp_id() -> int:
    """
    Return the next unique negative integer.

    Uses a monotonically decreasing counter stored in SQLite:
        0 → -1 → -2 → -3 → …

    Thread-safe within a single process because SQLite serialises writes.
    """
    conn = _get_local_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE temp_id_counter SET last_id = last_id - 1 WHERE id = 1"
        )
        cur.execute("SELECT last_id FROM temp_id_counter WHERE id = 1")
        row = cur.fetchone()
        conn.commit()
        temp_id = row["last_id"]
        log.debug("Generated temp_id: %d", temp_id)
        return temp_id
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Task 3 — Offline Write Router
# ---------------------------------------------------------------------------

def log_offline_insert(table_name: str, payload_dict: dict) -> int:
    """
    Queue an INSERT for later sync and store the record locally.

    Steps:
        1. Generate a unique negative temp_id.
        2. Inject it as the record's ``id``.
        3. Write the row into the appropriate local_* SQLite table.
        4. Append a tracking entry to ``sync_queue``.
        5. Return the temp_id so the UI can reference the record immediately.

    Args:
        table_name:   Logical table name (e.g. ``'students'``).
        payload_dict: Column→value mapping for the new record.
                      Must **not** contain an ``'id'`` key.

    Returns:
        The negative temporary ID assigned to the record.

    Raises:
        ValueError: If *table_name* is not in the registry.
    """
    if table_name not in _TABLE_REGISTRY:
        raise ValueError(
            f"Unknown table '{table_name}'. "
            f"Registered tables: {list(_TABLE_REGISTRY.keys())}"
        )

    meta = _TABLE_REGISTRY[table_name]
    local_table = meta["local_table"]
    columns = meta["columns"]

    # 1. Generate temp ID
    temp_id = generate_temp_id()

    # 2. Inject into payload
    payload_dict["id"] = temp_id

    # 3. Write to local mirror table
    col_names = ["id"] + columns
    placeholders = ", ".join(["?"] * len(col_names))
    col_clause = ", ".join(col_names)
    values = tuple(payload_dict.get(c) for c in col_names)

    conn = _get_local_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO {local_table} ({col_clause}) VALUES ({placeholders})",
            values,
        )

        # 4. Append to sync queue
        cur.execute(
            "INSERT INTO sync_queue (table_name, operation, temp_id, payload) "
            "VALUES (?, 'INSERT', ?, ?)",
            (table_name, temp_id, _json_dumps(payload_dict)),
        )

        conn.commit()
        log.info(
            "Offline INSERT queued: %s temp_id=%d", table_name, temp_id
        )
    finally:
        conn.close()

    # 5. Return temp_id
    return temp_id


def log_offline_update(table_name: str, record_id: int, payload_dict: dict) -> None:
    """
    Queue an UPDATE for later sync and immediately apply it to the local cache.
    """
    if table_name not in _TABLE_REGISTRY:
        raise ValueError(
            f"Unknown table '{table_name}'. "
            f"Registered tables: {list(_TABLE_REGISTRY.keys())}"
        )

    meta = _TABLE_REGISTRY[table_name]
    local_table = meta["local_table"]
    # If record_id is positive, it's synced (primary replica table). 
    # If negative, it's offline (mirror table).
    target_table = local_table if record_id < 0 else table_name

    keys = list(payload_dict.keys())
    if not keys:
        return

    set_clause = ", ".join([f"{k} = ?" for k in keys])
    values = [payload_dict[k] for k in keys]
    values.append(record_id)

    conn = _get_local_conn()
    try:
        cur = conn.cursor()
        # Version of the server record this edit starts from (conflict check at sync time)
        base_updated_at = None
        if record_id > 0:
            try:
                base_row = cur.execute(f"SELECT updated_at FROM {target_table} WHERE id = ?", (record_id,)).fetchone()
                base_updated_at = base_row[0] if base_row else None
            except sqlite3.OperationalError:
                pass  # no updated_at column yet (server SQL not run)
        cur.execute(f"UPDATE {target_table} SET {set_clause} WHERE id = ?", tuple(values))

        if record_id < 0:
            cur.execute(
                "SELECT payload FROM sync_queue WHERE temp_id = ? AND operation = 'INSERT'", 
                (record_id,)
            )
            row = cur.fetchone()
            if row:
                existing_payload = _json_loads(row["payload"])
                existing_payload.update(payload_dict)
                cur.execute(
                    "UPDATE sync_queue SET payload = ? WHERE temp_id = ? AND operation = 'INSERT'",
                    (_json_dumps(existing_payload), record_id)
                )
        else:
            cur.execute(
                "SELECT id, payload FROM sync_queue WHERE temp_id = ? AND operation = 'UPDATE' AND table_name = ?", 
                (record_id, table_name)
            )
            row = cur.fetchone()
            if row:
                existing_payload = _json_loads(row["payload"])
                existing_payload.update(payload_dict)
                cur.execute(
                    "UPDATE sync_queue SET payload = ? WHERE id = ?",
                    (_json_dumps(existing_payload), row["id"])
                )
            else:
                queued = dict(payload_dict)
                if base_updated_at:
                    queued["_base_updated_at"] = base_updated_at
                cur.execute(
                    "INSERT INTO sync_queue (table_name, operation, temp_id, payload) "
                    "VALUES (?, 'UPDATE', ?, ?)",
                    (table_name, record_id, _json_dumps(queued))
                )

        conn.commit()
        log.info("Offline UPDATE queued/merged: %s id=%d", table_name, record_id)
    finally:
        conn.close()


def log_offline_delete(table_name: str, record_id: int) -> None:
    """
    Queue a DELETE for later sync and immediately remove the record from local cache.
    If record_id < 0 (un-synced offline temp record):
      Removes its pending operations from sync_queue and local tables.
    If record_id > 0 (synced record in MySQL):
      Appends a DELETE operation to sync_queue and purges any pending UPDATEs for that record.
    """
    if table_name not in _TABLE_REGISTRY:
        raise ValueError(
            f"Unknown table '{table_name}'. "
            f"Registered tables: {list(_TABLE_REGISTRY.keys())}"
        )

    meta = _TABLE_REGISTRY[table_name]
    local_table = meta["local_table"]
    primary_table = table_name

    conn = _get_local_conn()
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {local_table} WHERE id = ?", (record_id,))
        cur.execute(f"DELETE FROM {primary_table} WHERE id = ?", (record_id,))
        cur.execute(
            "DELETE FROM sync_queue WHERE temp_id = ? AND table_name = ?",
            (record_id, table_name)
        )

        if record_id > 0:
            cur.execute(
                "INSERT INTO sync_queue (table_name, operation, temp_id, payload) "
                "VALUES (?, 'DELETE', ?, '{}')",
                (table_name, record_id)
            )

        conn.commit()
        log.info("Offline DELETE queued: %s id=%d", table_name, record_id)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Task 4 — Synchronisation & ID Resolution Loop
# ---------------------------------------------------------------------------

def get_device_id() -> str:
    """Stable id of this laptop (computer name + random suffix), created on first use."""
    conn = _get_local_conn()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS device_info (key TEXT PRIMARY KEY, value TEXT)")
        row = conn.execute("SELECT value FROM device_info WHERE key = 'device_id'").fetchone()
        if row:
            return row["value"]
        import socket
        import uuid
        device_id = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        conn.execute("INSERT INTO device_info (key, value) VALUES ('device_id', ?)", (device_id,))
        conn.commit()
        return device_id
    finally:
        conn.close()


def get_cert_number_block() -> dict | None:
    """This laptop's reserved certificate numbers: {year_suffix, start_no, end_no, next_no} or None."""
    try:
        return sqlite_read_one("SELECT year_suffix, start_no, end_no, next_no FROM cert_number_block WHERE id = 1")
    except Exception:
        return None


def save_cert_number_block(year_suffix: str, start_no: int, end_no: int) -> None:
    """Store a newly reserved block (replaces the previous one)."""
    conn = _get_local_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO cert_number_block (id, year_suffix, start_no, end_no, next_no) VALUES (1, ?, ?, ?, ?)",
            (year_suffix, start_no, end_no, start_no),
        )
        conn.commit()
    finally:
        conn.close()


def mark_cert_number_used(certificate_number: str) -> None:
    """After a certificate is saved: if its number came from this laptop's block, move past it."""
    import re
    m = re.match(r"^\s*(\d+)\s*/\s*(\S+)\s*$", str(certificate_number or ""))
    if not m:
        return
    number, suffix = int(m.group(1)), m.group(2)
    conn = _get_local_conn()
    try:
        conn.execute(
            "UPDATE cert_number_block SET next_no = ? "
            "WHERE id = 1 AND year_suffix = ? AND ? BETWEEN start_no AND end_no AND ? >= next_no",
            (number + 1, suffix, number, number),
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass  # table not created yet
    finally:
        conn.close()


def set_local_personnel_password(personnel_id: int, password_hash: str, must_change: bool) -> None:
    """Store a password hash (and the must-change flag) in this laptop's personnel copy."""
    conn = _get_local_conn()
    try:
        conn.execute(
            "UPDATE personnel SET password_hash = ?, must_change_password = ? WHERE id = ?",
            (password_hash, 1 if must_change else 0, personnel_id),
        )
        conn.commit()
    finally:
        conn.close()


def queue_password_change(personnel_id: int, new_hash: str, base_hash: str, must_change: bool) -> None:
    """
    Queue a password set offline. Only the HASH is queued, never the typed password.
    base_hash is the server's hash this laptop knew; the server refuses the change if
    its password changed since. One pending change per person: a newer one replaces an
    older pending one but keeps the older base_hash (still the server's last value).
    """
    conn = _get_local_conn()
    try:
        prev = conn.execute(
            "SELECT id, payload FROM sync_queue WHERE table_name = 'personnel_password' "
            "AND temp_id = ? AND COALESCE(status, 'pending') = 'pending' ORDER BY id ASC LIMIT 1",
            (personnel_id,),
        ).fetchone()
        if prev:
            base_hash = _json_loads(prev["payload"]).get("base_hash", base_hash)
            conn.execute(
                "DELETE FROM sync_queue WHERE table_name = 'personnel_password' AND temp_id = ? "
                "AND COALESCE(status, 'pending') = 'pending'",
                (personnel_id,),
            )
        payload = {"password_hash": new_hash, "base_hash": base_hash, "must_change": bool(must_change)}
        conn.execute(
            "INSERT INTO sync_queue (table_name, operation, temp_id, payload) VALUES ('personnel_password', 'UPDATE', ?, ?)",
            (personnel_id, _json_dumps(payload)),
        )
        conn.commit()
    finally:
        conn.close()


def _resolve_temp_id(
    sqlite_conn: sqlite3.Connection,
    table_name: str,
    temp_id: int,
    real_id: int,
) -> None:
    """
    Replace *temp_id* with *real_id* in the local mirror table's PK and in
    every child table that references it via a foreign-key column.

    This is **The Resolution Step**: after MySQL assigns the real
    auto-increment ID, we cascade-update the local SQLite graph so that
    downstream queued rows (e.g. enrollments pointing at a temp period_id)
    carry the correct real FK value when *they* are synced.
    """
    meta = _TABLE_REGISTRY[table_name]
    local_table = meta["local_table"]

    # Update the primary record's own ID
    sqlite_conn.execute(
        f"UPDATE {local_table} SET id = ? WHERE id = ?",
        (real_id, temp_id),
    )

    # Move resolved record from local mirror table to primary replica table
    try:
        primary_table = table_name
        # Copy by column NAME: the two tables can differ (e.g. updated_at exists only in the copy
        # of the server table), and a positional SELECT * would fail
        primary_cols = {r[1] for r in sqlite_conn.execute(f"PRAGMA table_info({primary_table})")}
        common = [r[1] for r in sqlite_conn.execute(f"PRAGMA table_info({local_table})") if r[1] in primary_cols]
        col_list = ", ".join(f'"{c}"' for c in common)
        sqlite_conn.execute(
            f"INSERT OR REPLACE INTO {primary_table} ({col_list}) SELECT {col_list} FROM {local_table} WHERE id = ?",
            (real_id,)
        )
        sqlite_conn.execute(
            f"DELETE FROM {local_table} WHERE id = ? OR id = ?",
            (real_id, temp_id)
        )
    except Exception as _move_err:
        log.debug("Move to primary table notice: %s", _move_err)

    # Cascade to child tables
    for child_table, fk_col in meta["fk_cascades"]:
        sqlite_conn.execute(
            f"UPDATE {child_table} SET {fk_col} = ? WHERE {fk_col} = ?",
            (real_id, temp_id),
        )

    # Also update any still-queued payloads in sync_queue that reference
    # this temp_id as a foreign-key value.
    cur = sqlite_conn.execute(
        "SELECT id, payload FROM sync_queue ORDER BY id"
    )
    for row in cur.fetchall():
        payload = _json_loads(row["payload"])
        changed = False
        for child_table, fk_col in meta["fk_cascades"]:
            if fk_col in payload:
                # Handle both integer and stringified integer representations of temp_id
                val = payload[fk_col]
                if str(val) == str(temp_id):
                    # Keep the original type (if it was string, keep it as string, though real_id as int is usually fine/better)
                    payload[fk_col] = real_id if isinstance(val, int) else str(real_id)
                    changed = True
        if changed:
            sqlite_conn.execute(
                "UPDATE sync_queue SET payload = ? WHERE id = ?",
                (_json_dumps(payload), row["id"]),
            )

    log.info(
        "Resolved %s temp_id=%d → real_id=%d (cascaded to %d children)",
        table_name, temp_id, real_id, len(meta["fk_cascades"]),
    )


def _execute_mysql_insert(mysql_conn, table_name: str, payload: dict) -> int:
    """
    Execute the INSERT on MySQL for one queued record and return the
    real auto-increment ID.

    Uses either a Stored Procedure (for students) or a raw INSERT
    (for academic_periods / enrollments), matching the patterns already
    established in ``data/repositories.py``.
    """
    meta = _TABLE_REGISTRY[table_name]
    cur = mysql_conn.cursor(dictionary=True)

    try:
        if meta["sp_name"]:
            # Stored Procedure path (e.g. InsertStudent)
            sp_args = tuple(payload.get(k) for k in meta["sp_args"])
            cur.callproc(meta["sp_name"], sp_args)
            mysql_conn.commit()

            # The SP is expected to return a rowset with 'new_id'
            for result in cur.stored_results():
                row = result.fetchone()
                if row and "new_id" in row:
                    return row["new_id"]

            # Fallback: LAST_INSERT_ID()
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            return cur.fetchone()["new_id"]

        else:
            # Raw INSERT path
            insert_sql = meta["insert_sql"]
            insert_keys = meta["insert_keys"]
            values = tuple(payload.get(k) for k in insert_keys)
            cur.execute(insert_sql, values)
            mysql_conn.commit()
            return cur.lastrowid

    finally:
        cur.close()


def sync_offline_queue_to_mysql(mysql_conn=None) -> dict:
    """
    Flush the offline sync queue via FastAPI HTTP sync endpoint and resolve all temp IDs.

    Called when the application detects that the network connection is
    available again. Processes rows in FIFO order (id ASC) so that
    parent records (students) are synced before children (enrollments).

    Args:
        mysql_conn: Deprecated connection object, kept for signature compatibility.

    Returns:
        A summary dict:
            {
                "synced":  4,       # rows successfully pushed
                "failed":  0,       # rows that errored (left in queue)
                "id_map":  {        # temp_id → real_id for every resolved record
                    -1: 542,
                    -2: 87,
                    ...
                }
            }
    """
    sqlite_conn = _get_local_conn()
    synced = 0
    failed = 0
    id_map: dict[int, int] = {}

    try:
        # Only pending rows are sent; rows marked 'failed' wait for the user to retry or discard them
        cur = sqlite_conn.execute(
            "SELECT id, table_name, operation, temp_id, payload "
            "FROM sync_queue WHERE COALESCE(status, 'pending') = 'pending' ORDER BY id ASC"
        )
        queue_rows = cur.fetchall()

        if not queue_rows:
            log.info("Sync queue has no pending rows — nothing to do.")
            return {"synced": 0, "failed": 0, "id_map": {}}

        log.info("Starting sync: %d queued operations.", len(queue_rows))

        # 1. Build the payload for the FastAPI sync endpoint
        actions = []
        for row in queue_rows:
            if row["table_name"] == "settings":
                try:
                    payload = _json_loads(row["payload"])
                    emp_id = row["temp_id"]
                    resp = api_client.put(f"{get_api_url()}/settings/appearance/{emp_id}", json=payload, timeout=5.0)
                    if resp.status_code == 200:
                        sqlite_conn.execute("DELETE FROM sync_queue WHERE id = ?", (row["id"],))
                        sqlite_conn.commit()
                        synced += 1
                        log.info("Synced offline settings for user %d", emp_id)
                    else:
                        failed += 1
                        log.warning("Failed to sync offline settings for user %d: %s", emp_id, resp.text)
                except Exception as exc:
                    failed += 1
                    log.error("Error syncing offline settings for user %d: %s", row["temp_id"], exc)
                continue

            actions.append({
                "id": row["id"],
                "table_name": row["table_name"],
                "operation": row["operation"],
                "temp_id": row["temp_id"],
                "payload": _json_loads(row["payload"])
            })

        if not actions:
            return {"synced": synced, "failed": failed, "id_map": {}}

        payload = {"actions": actions}

        # 2. POST the payload to the API
        try:
            # Rows are saved one by one on the server, so allow more time for large queues
            response = api_client.post(f"{get_api_url()}/sync", json=payload, timeout=120.0)
            if response.status_code != 200:
                log.error("API sync request failed with status %d: %s", response.status_code, response.text)
                return {"synced": 0, "failed": len(queue_rows), "id_map": {}}

            resp_data = response.json()
            # Convert JSON string keys to integers
            api_id_map = {int(k): int(v) for k, v in resp_data.get("id_map", {}).items()}
            # Rows the server could not save: {queue_id: error message}
            api_failed = {int(f["queue_id"]): str(f.get("error") or "") for f in resp_data.get("failed", [])}
        except Exception as exc:
            log.error("Failed to connect or communicate with FastAPI sync endpoint: %s", exc)
            return {"synced": 0, "failed": len(queue_rows), "id_map": {}}

        # 3. Process the resolved IDs in FIFO order
        for row in queue_rows:
            queue_id = row["id"]
            table_name = row["table_name"]
            temp_id = row["temp_id"]

            if table_name == "settings":
                continue  # handled above, outside the batch

            if queue_id not in api_failed and table_name not in _TABLE_REGISTRY and temp_id in api_id_map:
                # Actions without a local mirror table (e.g. personnel_password): nothing to resolve
                sqlite_conn.execute("DELETE FROM sync_queue WHERE id = ?", (queue_id,))
                sqlite_conn.commit()
                synced += 1
                log.info("Synced %s for id=%d", table_name, temp_id)
                continue

            if queue_id in api_failed:
                # Keep the row, but stop retrying it until the user retries or discards it
                sqlite_conn.execute(
                    "UPDATE sync_queue SET status = 'failed', last_error = ?, attempts = attempts + 1 WHERE id = ?",
                    (api_failed[queue_id], queue_id),
                )
                sqlite_conn.commit()
                failed += 1
                log.warning("Sync failed for queue id=%d (%s temp_id=%d): %s",
                            queue_id, table_name, temp_id, api_failed[queue_id])
            elif temp_id in api_id_map:
                real_id = api_id_map[temp_id]
                try:
                    # Resolve: cascade the real ID through local tables & queue
                    _resolve_temp_id(sqlite_conn, table_name, temp_id, real_id)
                    id_map[temp_id] = real_id

                    # Remove the successfully synced entry
                    sqlite_conn.execute(
                        "DELETE FROM sync_queue WHERE id = ?", (queue_id,)
                    )
                    sqlite_conn.commit()
                    synced += 1
                    log.info(
                        "Synced %s: temp_id=%d → real_id=%d", table_name, temp_id, real_id
                    )
                except Exception as exc:
                    log.error(
                        "Failed to resolve local DB for queue id=%d (%s temp_id=%d): %s",
                        queue_id, table_name, temp_id, exc
                    )
                    failed += 1
            else:
                log.warning(
                    "Queue id=%d (%s temp_id=%d) was not returned in API id_map.",
                    queue_id, table_name, temp_id
                )
                failed += 1

    finally:
        sqlite_conn.close()

    summary = {"synced": synced, "failed": failed, "id_map": id_map}
    log.info("Sync complete: %s", summary)
    return summary


# ---------------------------------------------------------------------------
# Convenience: queue status inspection
# ---------------------------------------------------------------------------

def get_queue_status() -> dict:
    """
    Return a snapshot of the current sync queue.

    Returns:
        {
            "pending": 3,      # waiting to be sent
            "failed": 1,       # rejected by the server, waiting for retry/discard
            "entries": [
                {"id": 1, "table_name": "students", "temp_id": -1, "status": "pending", ...},
                ...
            ]
        }
    """
    conn = _get_local_conn()
    try:
        cur = conn.execute(
            "SELECT id, table_name, operation, temp_id, created_at, payload, "
            "COALESCE(status, 'pending') AS status, last_error, attempts "
            "FROM sync_queue ORDER BY id ASC"
        )
        rows = [dict(r) for r in cur.fetchall()]
        return {
            "pending": sum(1 for r in rows if r["status"] == "pending"),
            "failed": sum(1 for r in rows if r["status"] == "failed"),
            "entries": rows,
        }
    finally:
        conn.close()


def retry_failed_queue_rows(override: bool = False) -> int:
    """
    Put every failed queue row back to pending so the next sync sends it again. Returns the count.
    override=True: the user checked the failures and wants this laptop's data saved anyway -
    the server then skips the "changed on the server meanwhile" and "possible duplicate
    student" checks for these rows (other errors still fail).
    """
    conn = _get_local_conn()
    try:
        if override:
            rows = conn.execute("SELECT id, payload FROM sync_queue WHERE status = 'failed'").fetchall()
            for r in rows:
                payload = _json_loads(r["payload"])
                payload["_override"] = True
                payload["_allow_duplicate"] = True
                conn.execute("UPDATE sync_queue SET payload = ? WHERE id = ?", (_json_dumps(payload), r["id"]))
        cur = conn.execute("UPDATE sync_queue SET status = 'pending' WHERE status = 'failed'")
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def discard_failed_queue_rows(queue_ids: list[int] | None = None) -> int:
    """
    Permanently drop failed queue rows (all of them, or only *queue_ids*) and the
    offline-only local_* records they created. Server data is never touched.
    Returns the number of queue rows removed.
    """
    conn = _get_local_conn()
    try:
        sql = "SELECT id, table_name, operation, temp_id FROM sync_queue WHERE status = 'failed'"
        params: tuple = ()
        if queue_ids:
            sql += f" AND id IN ({', '.join('?' * len(queue_ids))})"
            params = tuple(queue_ids)
        rows = conn.execute(sql, params).fetchall()
        for r in rows:
            meta = _TABLE_REGISTRY.get(r["table_name"])
            if meta and r["operation"] == "INSERT" and r["temp_id"] < 0:
                conn.execute(f"DELETE FROM {meta['local_table']} WHERE id = ?", (r["temp_id"],))
            conn.execute("DELETE FROM sync_queue WHERE id = ?", (r["id"],))
        conn.commit()
        if rows:
            log.warning("Discarded %d failed sync_queue row(s).", len(rows))
        return len(rows)
    finally:
        conn.close()


def clear_synced_local_data() -> None:
    """
    Purge all resolved records from local mirror tables.

    Call after a successful full sync to reclaim disk space.
    Only deletes rows whose IDs are positive (i.e. already resolved).
    Rows with negative IDs (still pending) are preserved.
    """
    conn = _get_local_conn()
    try:
        for meta in _TABLE_REGISTRY.values():
            conn.execute(
                f"DELETE FROM {meta['local_table']} WHERE id > 0"
            )
        conn.commit()
        log.info("Cleared resolved records from local mirror tables.")
    finally:
        conn.close()
