"""Shared building blocks of the API: logger, MySQL pool (get_db) and the helpers the routers share.

main.py re-imports every name here, so `from main import get_db` keeps working.
"""
import os
from datetime import date
from decimal import Decimal
import logging
from typing import List, Dict, Any, Optional

from mysql.connector import pooling
from fastapi import HTTPException

logger = logging.getLogger("api")

# Database Configuration: config.py (DBConfig) in this folder is the server's own
# settings file and is never overwritten by update_server.bat; environment variables win.
try:
    from config import DBConfig as _DBConfig
except Exception:
    _DBConfig = None
DB_HOST = os.environ.get("DB_HOST", getattr(_DBConfig, "DB_HOST", "localhost"))
DB_USER = os.environ.get("DB_USER", getattr(_DBConfig, "DB_USER", "root"))
DB_PASSWORD = os.environ.get("DB_PASSWORD", getattr(_DBConfig, "DB_PASSWORD", "12345678"))
DB_NAME = os.environ.get("DB_NAME", getattr(_DBConfig, "DB_NAME", "certificate_manager"))

# Global API Connection Pool
_api_connection_pool = None


def get_db():
    """Dependency to retrieve a MySQL database connection from the connection pool."""
    global _api_connection_pool
    if _api_connection_pool is None:
        _api_connection_pool = pooling.MySQLConnectionPool(
            pool_name="api_pool",
            pool_size=15,
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
        )
    conn = _api_connection_pool.get_connection()
    try:
        yield conn
    finally:
        conn.close()


def decode_db_value(obj: Any) -> Any:
    """Recursively decode bytes, bytearray, date, or Decimal values to Python primitives."""
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8")
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: decode_db_value(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decode_db_value(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(decode_db_value(v) for v in obj)
    return obj


def execute_sp_fetchall(conn, sp_name: str, args: tuple = ()) -> List[Dict[str, Any]]:
    """
    Execute a stored procedure and fetch all rows across all result sets,
    fully consuming cursor result sets (nextset) and decoding any byte payloads.
    """
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc(sp_name, args)
        rows = []
        if hasattr(cur, "stored_results"):
            for result_set in cur.stored_results():
                rows.extend(result_set.fetchall())
        else:
            rows = cur.fetchall()

        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        return decode_db_value(rows)
    finally:
        cur.close()


def execute_sp_fetchone(conn, sp_name: str, args: tuple = ()) -> Optional[Dict[str, Any]]:
    """
    Execute a stored procedure and fetch the first matching row,
    draining all cursor result sets and decoding any byte payloads.
    """
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc(sp_name, args)
        row = None
        if hasattr(cur, "stored_results"):
            for result_set in cur.stored_results():
                r = result_set.fetchone()
                if r:
                    row = r
                    break
        else:
            row = cur.fetchone()

        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        return decode_db_value(row) if row else None
    finally:
        cur.close()


_UPDATED_AT_CACHE: Dict[str, tuple] = {}


def table_has_updated_at(conn, table_name: str) -> bool:
    """True when the table has the updated_at column (added by sql/fixes/2026-10-24_03). Cached 5 min."""
    import time as _time
    hit = _UPDATED_AT_CACHE.get(table_name)
    if hit and _time.time() - hit[1] < 300:
        return hit[0]
    cur = conn.cursor(buffered=True)
    try:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = 'updated_at'",
            (table_name,)
        )
        value = bool(cur.fetchone()[0])
    except Exception:
        value = False
    finally:
        cur.close()
    _UPDATED_AT_CACHE[table_name] = (value, _time.time())
    return value


def _require_admin(conn, personnel_id: Optional[int]) -> None:
    """Refuse the request unless personnel_id belongs to an active admin account."""
    if not personnel_id:
        raise HTTPException(status_code=403, detail="Admin account required")
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT personnel_role, is_active FROM personnel WHERE id = %s", (personnel_id,))
        row = cur.fetchone()
    finally:
        cur.close()
    if not row or str(row.get("personnel_role") or "").lower() != "admin" or not row.get("is_active"):
        raise HTTPException(status_code=403, detail="Admin account required")


def _set_must_change_password(conn, person_id: int, value: bool) -> None:
    cur = conn.cursor()
    try:
        cur.execute("UPDATE personnel SET must_change_password = %s WHERE id = %s", (1 if value else 0, person_id))
    except Exception:
        pass  # column not created yet: nothing to record
    finally:
        cur.close()


STATUS_STR_TO_INT = {
    "PASSED": 1, "1": 1, 1: 1,
    "FAILED_REPEAT": 2, "FAILED": 2, "2": 2, 2: 2,
    "EXCEPTIONAL_PASS": 3, "3": 3, 3: 3,
    "CARRIED_OVER": 4, "4": 4, 4: 4,
    "DEFERRED": 5, "5": 5, 5: 5,
    "DISMISSED": 6, "6": 6, 6: 6,
}


def result_status_code(value) -> int:
    """academic_periods.result_status is an INT column (1=PASSED ... 6=DISMISSED).
    Writing a status key such as 'PASSED' into it stores 0, so convert every write."""
    if value is None or value == "":
        return 1
    return STATUS_STR_TO_INT.get(value, STATUS_STR_TO_INT.get(str(value).strip().upper(), 1))
