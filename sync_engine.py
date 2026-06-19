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


def check_network_status() -> bool:
    """
    Attempt a fast, low-timeout HTTP GET request to the FastAPI server ping endpoint.

    Returns True if FastAPI is reachable, False otherwise.
    This function is called every ~8 seconds from the UI polling loop.
    It does NOT update the cached flag — the caller must call set_online().
    """
    try:
        response = requests.get("http://127.0.0.1:8000/ping", timeout=2.0)
        return response.status_code == 200
    except requests.RequestException:
        return False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LOCAL_DB_PATH = Path(__file__).resolve().parent / "local_cache.db"

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
            "sequence_number", "postgraduation_no", "date_of_birth",
            "birthplace_id", "birthplace_other", "nationality_id",
            "department_id", "study_system_id", "degree_level",
            "order_id", "admission_year", "summer_training_data",
            "average", "graduation_date", "graduation_semester",
        ],
        "sp_name": "InsertStudent",
        "sp_args": [
            "full_name_ar", "full_name_en", "gender",
            "sequence_number", "postgraduation_no", "date_of_birth",
            "birthplace_id", "birthplace_other", "nationality_id",
            "department_id", "study_system_id", "degree_level",
            "order_id", "admission_year", "summer_training_data",
            "average", "graduation_date", "graduation_semester",
        ],
        "fk_cascades": [
            ("local_academic_periods", "student_id"),
        ],
    },
    "academic_periods": {
        "local_table": "local_academic_periods",
        "columns": [
            "student_id", "academic_year", "study_system_id",
            "stage_number", "semester_num",
        ],
        "sp_name": None,  # uses raw INSERT (no SP in current repo)
        "sp_args": [],
        "insert_sql": (
            "INSERT INTO academic_periods "
            "(student_id, academic_year, study_system_id, stage_number, semester_num) "
            "VALUES (%s, %s, %s, %s, %s)"
        ),
        "insert_keys": [
            "student_id", "academic_year", "study_system_id",
            "stage_number", "semester_num",
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
    conn.execute("PRAGMA journal_mode=WAL")      # safer for concurrent reads
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
                gender              TEXT DEFAULT 'M',
                sequence_number     INTEGER,
                postgraduation_no   INTEGER,
                date_of_birth       TEXT,
                birthplace_id       INTEGER,
                birthplace_other    TEXT,
                nationality_id      INTEGER,
                department_id       INTEGER,
                study_system_id     INTEGER,
                degree_level        TEXT DEFAULT 'Bachelor',
                order_id            INTEGER,
                admission_year      INTEGER,
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
                semester_num    INTEGER
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

        # -- Read cache: transparent SP result cache for offline reads -------
        cur.execute("""
            CREATE TABLE IF NOT EXISTS read_cache (
                cache_key   TEXT PRIMARY KEY,
                result_json TEXT NOT NULL,
                cached_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # -- Replica tables: full read-only mirrors of MySQL tables ----------
        # These are populated by pull_mysql_to_sqlite() whenever the app
        # is online, so that offline reads can query structured data.

        cur.execute("""
            CREATE TABLE IF NOT EXISTS personnel (
                id                    INTEGER PRIMARY KEY,
                name_ar               TEXT,
                name_en               TEXT,
                academic_title_ar     TEXT,
                academic_title_en     TEXT,
                responsibility_ar     TEXT,
                responsibility_en     TEXT,
                display_order         INTEGER DEFAULT 0,
                username              TEXT,
                password_hash         TEXT,
                personnel_role        TEXT DEFAULT 'user',
                settings_id           INTEGER DEFAULT 1,
                university_settings_id INTEGER DEFAULT 1,
                page_location         TEXT DEFAULT 'front',
                is_active             INTEGER DEFAULT 1,
                created_at            TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id                    INTEGER PRIMARY KEY,
                full_name_ar          TEXT,
                full_name_en          TEXT,
                gender                TEXT DEFAULT 'M',
                sequence_number       INTEGER,
                postgraduation_no     INTEGER,
                postgraduation_number INTEGER,
                date_of_birth         TEXT,
                birthplace_id         INTEGER,
                birthplace_other      TEXT,
                nationality_id        INTEGER DEFAULT 1,
                department_id         INTEGER,
                study_system_id       INTEGER,
                degree_level          TEXT DEFAULT 'Bachelor',
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
                semester_num    INTEGER DEFAULT 1
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
                is_second_round INTEGER DEFAULT 0,
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
                stage_number    INTEGER,
                study_system_id INTEGER,
                is_shared       INTEGER DEFAULT 0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                id                    INTEGER PRIMARY KEY,
                name_ar               TEXT,
                name_en               TEXT,
                study_day_type        TEXT DEFAULT 'Morning',
                university_settings_id INTEGER DEFAULT 1
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS study_systems (
                id                  INTEGER PRIMARY KEY,
                name_ar             TEXT,
                name_en             TEXT,
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
            CREATE TABLE IF NOT EXISTS course_departments (
                course_id     INTEGER NOT NULL,
                department_id INTEGER NOT NULL,
                PRIMARY KEY (course_id, department_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                id              INTEGER PRIMARY KEY,
                personnel_id    INTEGER,
                theme           TEXT DEFAULT 'System',
                accent_color    TEXT DEFAULT 'blue',
                font_family     TEXT DEFAULT 'Arial',
                font_size_base  INTEGER DEFAULT 13,
                rtl             INTEGER DEFAULT 1
            )
        """)

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
    ("departments",         "SELECT * FROM departments"),
    ("study_systems",       "SELECT * FROM study_systems"),
    ("personnel",           "SELECT * FROM personnel"),
    ("courses",             "SELECT * FROM courses"),
    ("course_departments",  "SELECT * FROM course_departments"),
    ("graduation_orders",   "SELECT * FROM graduation_orders"),
    ("students",            "SELECT * FROM students"),
    ("academic_periods",    "SELECT * FROM academic_periods"),
    ("enrollments",         "SELECT * FROM enrollments"),
]


def pull_mysql_to_sqlite(mysql_conn, sqlite_conn=None) -> dict:
    """
    Download a full read-only replica of essential MySQL tables into SQLite.

    Strategy (safe for <100k rows):
        1. DELETE FROM local_table
        2. SELECT * FROM mysql_table
        3. INSERT INTO local_table (all fetched rows)

    Args:
        mysql_conn: An open mysql.connector connection.
        sqlite_conn: Optional pre-opened SQLite connection.
                     If None, one is created internally.

    Returns:
        {"tables_synced": int, "total_rows": int, "errors": list[str]}
    """
    own_sqlite = sqlite_conn is None
    if own_sqlite:
        sqlite_conn = _get_local_conn()

    tables_synced = 0
    total_rows = 0
    errors: list[str] = []

    try:
        my_cur = mysql_conn.cursor(dictionary=True)

        for table_name, select_sql in _REPLICA_TABLES:
            try:
                # Fetch from MySQL
                my_cur.execute(select_sql)
                rows = my_cur.fetchall()

                if not rows:
                    # Still clear local data even if MySQL table is empty
                    sqlite_conn.execute(f"DELETE FROM {table_name}")
                    sqlite_conn.commit()
                    tables_synced += 1
                    continue

                # Determine columns from the first row
                columns = list(rows[0].keys())
                col_clause = ", ".join(columns)
                placeholders = ", ".join(["?"] * len(columns))

                # Clear + insert
                sqlite_conn.execute(f"DELETE FROM {table_name}")
                for row in rows:
                    values = tuple(
                        str(v) if isinstance(v, (date, datetime)) else v
                        for v in (row.get(c) for c in columns)
                    )
                    sqlite_conn.execute(
                        f"INSERT OR REPLACE INTO {table_name} ({col_clause}) VALUES ({placeholders})",
                        values,
                    )

                sqlite_conn.commit()
                tables_synced += 1
                total_rows += len(rows)
                log.debug("Replicated %s: %d rows", table_name, len(rows))

            except Exception as exc:
                log.error("Failed to replicate table %s: %s", table_name, exc)
                errors.append(f"{table_name}: {exc}")

        my_cur.close()

    finally:
        if own_sqlite:
            sqlite_conn.close()

    summary = {"tables_synced": tables_synced, "total_rows": total_rows, "errors": errors}
    log.info("Inbound sync complete: %s", summary)
    return summary


def download_mysql_snapshot(mysql_conn, sqlite_conn):
    """
    Perform a fast, safe replication of core data from MySQL to SQLite.
    Optimized to dynamically drop and recreate the SQLite cache tables to
    match the MySQL schema perfectly.
    """
    tables = ['departments', 'courses', 'study_systems', 'students', 'academic_periods', 'enrollments', 'settings', 'personnel', 'graduation_orders']
    my_cursor = mysql_conn.cursor(dictionary=True)
    sq_cursor = sqlite_conn.cursor()
    
    def safe_cast(val):
        if val is None: return None
        if isinstance(val, (int, float)): return val 
        if isinstance(val, (bytearray, bytes)):
            try:
                return val.decode('utf-8')
            except UnicodeDecodeError:
                return str(val)
        return str(val)
        
    for table in tables:
        src_table = table
        dest_table = table
        if table == 'settings':
            dest_table = 'university_settings'
            try:
                my_cursor.execute("SELECT * FROM university_settings LIMIT 1;")
                my_cursor.fetchall()
                src_table = 'university_settings'
            except Exception:
                src_table = 'settings'
                
        try:
            # 1. Fetch fresh rows from MySQL
            my_cursor.execute(f"SELECT * FROM {src_table};")
            rows = my_cursor.fetchall()
            if not rows: continue
            
            columns = list(rows[0].keys())
            
            # 2. Build optimized column definitions
            cols_def_parts = []
            for col in columns:
                if col.lower() == 'id':
                    cols_def_parts.append(f"{col} INTEGER PRIMARY KEY")
                else:
                    cols_def_parts.append(f"{col}")
            cols_def = ", ".join(cols_def_parts)
            
            # 3. Drop and Recreate
            sq_cursor.execute(f"DROP TABLE IF EXISTS {dest_table};")
            sq_cursor.execute(f"CREATE TABLE {dest_table} ({cols_def});")
            
            # 4. Insert Data
            placeholders = ", ".join(["?"] * len(columns))
            sql_insert = f"INSERT INTO {dest_table} ({', '.join(columns)}) VALUES ({placeholders});"
            insert_data = [tuple(safe_cast(row[col]) for col in columns) for row in rows]
            sq_cursor.executemany(sql_insert, insert_data)
            
            # 5. Generate Performance Indexes for Foreign Keys
            for col in columns:
                if col.lower().endswith('_id'):
                    idx_name = f"idx_{dest_table}_{col}"
                    sq_cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {dest_table}({col});")
        except Exception as e:
            print(f"Error syncing table {table}: {e}")
            
    sqlite_conn.commit()


def pull_mysql_to_sqlite_background() -> None:
    """
    Run pull_mysql_to_sqlite in a background thread.

    Safe to call from the UI thread — spawns a daemon thread that
    opens its own MySQL and SQLite connections.
    """
    def _worker():
        try:
            import mysql.connector
            from config import DBConfig
            my_conn = mysql.connector.connect(
                host=DBConfig.DB_HOST,
                user=DBConfig.DB_USER,
                password=DBConfig.DB_PASSWORD,
                database=DBConfig.DB_NAME,
                connection_timeout=5,
            )
            pull_mysql_to_sqlite(my_conn)
            my_conn.close()
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


# ---------------------------------------------------------------------------
# Task 4 — Synchronisation & ID Resolution Loop
# ---------------------------------------------------------------------------

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
            if fk_col in payload and payload[fk_col] == temp_id:
                payload[fk_col] = real_id
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
        cur = sqlite_conn.execute(
            "SELECT id, table_name, operation, temp_id, payload "
            "FROM sync_queue ORDER BY id ASC"
        )
        queue_rows = cur.fetchall()

        if not queue_rows:
            log.info("Sync queue is empty — nothing to do.")
            return {"synced": 0, "failed": 0, "id_map": {}}

        log.info("Starting sync: %d queued operations.", len(queue_rows))

        # 1. Build the payload for the FastAPI sync endpoint
        actions = []
        for row in queue_rows:
            actions.append({
                "id": row["id"],
                "table_name": row["table_name"],
                "operation": row["operation"],
                "temp_id": row["temp_id"],
                "payload": _json_loads(row["payload"])
            })

        payload = {"actions": actions}

        # 2. POST the payload to the API
        try:
            response = requests.post("http://127.0.0.1:8000/sync", json=payload, timeout=10.0)
            if response.status_code != 200:
                log.error("API sync request failed with status %d: %s", response.status_code, response.text)
                return {"synced": 0, "failed": len(queue_rows), "id_map": {}}
            
            resp_data = response.json()
            # Convert JSON string keys to integers
            api_id_map = {int(k): int(v) for k, v in resp_data.get("id_map", {}).items()}
        except Exception as exc:
            log.error("Failed to connect or communicate with FastAPI sync endpoint: %s", exc)
            return {"synced": 0, "failed": len(queue_rows), "id_map": {}}

        # 3. Process the resolved IDs in FIFO order
        for row in queue_rows:
            queue_id = row["id"]
            table_name = row["table_name"]
            temp_id = row["temp_id"]

            if temp_id in api_id_map:
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
            "pending": 3,
            "entries": [
                {"id": 1, "table_name": "students", "temp_id": -1, "created_at": "..."},
                ...
            ]
        }
    """
    conn = _get_local_conn()
    try:
        cur = conn.execute(
            "SELECT id, table_name, operation, temp_id, created_at "
            "FROM sync_queue ORDER BY id ASC"
        )
        rows = [dict(r) for r in cur.fetchall()]
        return {"pending": len(rows), "entries": rows}
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
