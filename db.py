# =============================================================================
# db.py — Certificate Manager: Database Initialization & Utilities
# =============================================================================

import logging
import shutil
import subprocess
from pathlib import Path
import mysql.connector
from mysql.connector import pooling
from config import DBConfig

log = logging.getLogger(__name__)


# Global connection pool placeholder
_connection_pool = None


def get_connection():
    """Returns a MySQL connection from a connection pool (dictionary cursor support by default via repository)."""
    global _connection_pool
    if _connection_pool is None:
        try:
            # Initialize connection pool lazily
            _connection_pool = pooling.MySQLConnectionPool(
                pool_name="cert_mgr_pool",
                pool_size=10,
                host=DBConfig.DB_HOST,
                user=DBConfig.DB_USER,
                password=DBConfig.DB_PASSWORD,
                database=DBConfig.DB_NAME,
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci'
            )
        except Exception as err:
            log.warning("Could not initialize MySQL Connection Pool: %s. Falling back to direct connections.", err)
            # Fallback to direct connections if pool creation fails (e.g. MySQL server not available yet)
            return mysql.connector.connect(
                host=DBConfig.DB_HOST,
                user=DBConfig.DB_USER,
                password=DBConfig.DB_PASSWORD,
                database=DBConfig.DB_NAME,
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci'
            )
    return _connection_pool.get_connection()


def init_db() -> None:
    """Check MySQL connection on startup and verify that required tables and columns exist without mutating the schema."""
    log.info("Checking MySQL database connection to %s@%s...", DBConfig.DB_USER, DBConfig.DB_HOST)
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Verify if course_departments table exists
        cursor.execute("SHOW TABLES LIKE 'course_departments'")
        if cursor.fetchone():
            log.warning("Database schema warning: 'course_departments' table still exists in MySQL, but is dropped in local cache.")

        # Verify students table columns
        cursor.execute("DESCRIBE students")
        raw_student_rows = cursor.fetchall()
        student_cols = [row[0] for row in raw_student_rows]  # type: ignore

        for col in ["graduation_date", "graduation_semester", "postgraduation_number", "admission_year"]:
            if col not in student_cols:
                log.warning("Database schema warning: column '%s' is missing from 'students' table.", col)

        # Verify graduation_orders table columns
        cursor.execute("DESCRIBE graduation_orders")
        raw_order_rows = cursor.fetchall()
        order_cols = [row[0] for row in raw_order_rows]  # type: ignore

        for col in ["graduation_year", "admission_year", "study_type", "notes"]:
            if col not in order_cols:
                log.warning("Database schema warning: column '%s' is missing from 'graduation_orders' table.", col)

        # Verify academic_periods table columns
        cursor.execute("DESCRIBE academic_periods")
        raw_ap_rows = cursor.fetchall()
        ap_cols = [row[0] for row in raw_ap_rows]  # type: ignore

        if "study_system_id" not in ap_cols:
            log.warning("Database schema warning: column 'study_system_id' is missing from 'academic_periods' table.")

        # Verify courses table columns
        cursor.execute("DESCRIBE courses")
        raw_course_rows = cursor.fetchall()
        course_cols = [row[0] for row in raw_course_rows]  # type: ignore

        if "study_system_id" in course_cols:
            log.warning("Database schema warning: column 'study_system_id' still exists in 'courses' table.")

        if "is_shared" in course_cols:
            log.warning("Database schema warning: column 'is_shared' still exists in 'courses' table.")

        if "department_id" not in course_cols:
            log.warning("Database schema warning: column 'department_id' is missing from 'courses' table.")

        # Ensure composite unique index name_dep exists on (name_en, department_id, credit_hours)
        cursor.execute("SHOW INDEX FROM courses WHERE Key_name = 'name_dep'")
        if not cursor.fetchall():
            log.warning("Database schema warning: composite unique index 'name_dep' is missing from 'courses' table.")

        log.info("Database schema verification completed successfully (read-only verification).")
    except Exception as e:
        log.error("Database connection or schema verification failed: %s", e)
        raise
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Grade Helper
# ---------------------------------------------------------------------------

def get_grade(average) -> tuple[str, str]:
    try:
        avg_val = float(average)
    except (ValueError, TypeError):
        return ("—", "—")
        
    if avg_val >= 90:
        return ("امتياز",   "Excellent")
    elif avg_val >= 80:
        return ("جيد جداً", "Very Good")
    elif avg_val >= 70:
        return ("جيد",      "Good")
    elif avg_val >= 60:
        return ("متوسط",    "Medium")
    else:
        return ("مقبول",    "Accepted")


# ---------------------------------------------------------------------------
# Backup & Restore  (MySQL — uses mysqldump / mysql CLI)
# ---------------------------------------------------------------------------

def _mysql_env() -> dict:
    """
    Build an environment dict with MYSQL_PWD set so the password is never
    exposed on the command line (visible in process lists).
    """
    import os
    env = os.environ.copy()
    env["MYSQL_PWD"] = DBConfig.DB_PASSWORD
    return env


def backup_db(dest_path: Path) -> None:
    """
    Dump the certificate_manager database to *dest_path* (a .sql file).

    Requires **mysqldump** to be installed and available on PATH.
    If it is missing a descriptive RuntimeError is raised so the UI can
    surface a friendly message — the application never crashes on import.

    Args:
        dest_path: Destination file path (e.g. Path("backup_2026.sql")).

    Raises:
        RuntimeError: mysqldump not found, or the dump process exits non-zero.
    """
    mysqldump = shutil.which("mysqldump")
    if not mysqldump:
        raise RuntimeError(
            "mysqldump غير موجود في PATH.\n"
            "mysqldump not found on PATH. "
            "Please install MySQL client tools and make sure mysqldump is accessible."
        )

    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        mysqldump,
        "--no-defaults",
        f"--host={DBConfig.DB_HOST}",
        f"--user={DBConfig.DB_USER}",
        "--single-transaction",
        "--routines",
        "--triggers",
        DBConfig.DB_NAME,
    ]

    log.info("Starting backup: %s → %s", " ".join(cmd), dest_path)

    with dest_path.open("wb") as out_file:
        result = subprocess.run(
            cmd,
            stdout=out_file,
            stderr=subprocess.PIPE,
            env=_mysql_env(),
        )

    if result.returncode != 0:
        stderr_msg = result.stderr.decode(errors="replace")
        raise RuntimeError(f"mysqldump failed (exit {result.returncode}):\n{stderr_msg}")

    log.info("Backup completed: %s", dest_path)


def restore_db(src_path: Path) -> None:
    """
    Restore the database from a .sql dump file at *src_path*.

    Requires the **mysql** CLI client to be installed and on PATH.

    ⚠ WARNING: This replaces all current data in the database.

    Args:
        src_path: Path to the .sql dump file to restore from.

    Raises:
        FileNotFoundError: *src_path* does not exist.
        RuntimeError: mysql CLI not found, or the restore process exits non-zero.
    """
    mysql_cli = shutil.which("mysql")
    if not mysql_cli:
        raise RuntimeError(
            "mysql CLI غير موجود في PATH.\n"
            "mysql not found on PATH. "
            "Please install MySQL client tools and make sure mysql is accessible."
        )

    src_path = Path(src_path)
    if not src_path.exists():
        raise FileNotFoundError(f"Backup file not found: {src_path}")

    cmd = [
        mysql_cli,
        f"--host={DBConfig.DB_HOST}",
        f"--user={DBConfig.DB_USER}",
        DBConfig.DB_NAME,
    ]

    log.info("Starting restore from: %s", src_path)

    with src_path.open("rb") as in_file:
        result = subprocess.run(
            cmd,
            stdin=in_file,
            stderr=subprocess.PIPE,
            env=_mysql_env(),
        )

    if result.returncode != 0:
        stderr_msg = result.stderr.decode(errors="replace")
        raise RuntimeError(f"mysql restore failed (exit {result.returncode}):\n{stderr_msg}")

    log.info("Restore completed from: %s", src_path)


if __name__ == "__main__":
    init_db()
    print("db.py is working correctly.\n")
