# =============================================================================
# db.py — Certificate Manager: Database Initialization & Utilities
# =============================================================================

import logging
import shutil
import subprocess
from pathlib import Path
import mysql.connector
from config import DBConfig

log = logging.getLogger(__name__)


def get_connection():
    """Returns a MySQL connection with dictionary cursor support by default (via repository)."""
    return mysql.connector.connect(
        host=DBConfig.DB_HOST,
        user=DBConfig.DB_USER,
        password=DBConfig.DB_PASSWORD,
        database=DBConfig.DB_NAME,
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )


def init_db() -> None:
    """Check MySQL connection on startup and ensure required tables and columns exist."""
    log.info("Checking MySQL database connection to %s@%s...", DBConfig.DB_USER, DBConfig.DB_HOST)
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Verify and create course_departments table if it does not exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS course_departments (
                course_id     INT NOT NULL,
                department_id INT NOT NULL,
                PRIMARY KEY (course_id, department_id),
                FOREIGN KEY (course_id) REFERENCES courses(id) ON UPDATE CASCADE ON DELETE CASCADE,
                FOREIGN KEY (department_id) REFERENCES departments(id) ON UPDATE CASCADE ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        # Verify and add missing columns to the students table for full compatibility
        cursor.execute("DESCRIBE students")
        student_cols = [row[0] for row in cursor.fetchall()]

        if "graduation_date" not in student_cols:
            log.info("Adding graduation_date column to students table...")
            cursor.execute("ALTER TABLE students ADD COLUMN graduation_date DATE DEFAULT NULL")

        if "graduation_semester" not in student_cols:
            log.info("Adding graduation_semester column to students table...")
            cursor.execute("ALTER TABLE students ADD COLUMN graduation_semester VARCHAR(50) DEFAULT NULL")

        if "postgraduation_no" not in student_cols:
            log.info("Adding postgraduation_no column to students table...")
            cursor.execute("ALTER TABLE students ADD COLUMN postgraduation_no INT DEFAULT NULL")
            if "postgraduation_number" in student_cols:
                cursor.execute("UPDATE students SET postgraduation_no = postgraduation_number WHERE postgraduation_no IS NULL")

        # Verify and add missing columns to the graduation_orders table for full compatibility
        cursor.execute("DESCRIBE graduation_orders")
        order_cols = [row[0] for row in cursor.fetchall()]

        if "admission_year" not in order_cols:
            log.info("Adding admission_year column to graduation_orders table...")
            cursor.execute("ALTER TABLE graduation_orders ADD COLUMN admission_year INT DEFAULT NULL")

        if "study_type" not in order_cols:
            log.info("Adding study_type column to graduation_orders table...")
            cursor.execute("ALTER TABLE graduation_orders ADD COLUMN study_type VARCHAR(50) DEFAULT NULL")

        if "notes" not in order_cols:
            log.info("Adding notes column to graduation_orders table...")
            cursor.execute("ALTER TABLE graduation_orders ADD COLUMN notes VARCHAR(255) DEFAULT NULL")

        conn.commit()
        cursor.close()
        conn.close()
        log.info("Database connection successful, tables verified, and schemas reconciled.")
    except Exception as e:
        log.error("Database connection or schema verification failed: %s", e)
        raise


# ---------------------------------------------------------------------------
# Grade Helper
# ---------------------------------------------------------------------------

def get_grade(average: int) -> tuple[str, str]:
    if average >= 90:
        return ("امتياز",   "Excellent")
    elif average >= 80:
        return ("جيد جداً", "Very Good")
    elif average >= 70:
        return ("جيد",      "Good")
    elif average >= 60:
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
