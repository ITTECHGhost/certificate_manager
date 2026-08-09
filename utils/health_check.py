# =============================================================================
# utils/health_check.py — System Startup Health Check & Diagnostics
# =============================================================================

import sys
import logging
from pathlib import Path

# Ensure workspace root is in sys.path when running or importing from subdirectories
workspace_root = str(Path(__file__).resolve().parent.parent)
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

# Import database, sync engine, logger, and configuration modules
from db import get_connection
from sync_engine import (
    is_online,
    set_online,
    check_network_status,
    get_local_connection,
    sqlite_read_one,
    init_local_db,
    _LOCAL_DB_PATH,
)
from utils.logger import log_system

log = logging.getLogger(__name__)

_has_run: bool = False


def run_system_health_checks() -> bool:
    """
    Executes a sequential diagnostic health check of the network, database connections,
    stored procedures, and offline SQLite resources. Writes diagnostic results to system_log.txt.
    Guarded to run at most once per application run.
    """
    global _has_run
    if _has_run:
        return True
    _has_run = True

    log_system("SYSTEM STARTUP DIAGNOSTIC CHECK STARTED", "INFO")
    all_passed = True

    # -------------------------------------------------------------------------
    # [CHECK 1] Network & API Connectivity
    # -------------------------------------------------------------------------
    api_online = False
    try:
        api_online = check_network_status()
        set_online(api_online)
    except Exception as err:
        log.debug("Network connectivity check exception: %s", err)
        set_online(False)

    if api_online:
        log_system("[CHECK 1/4] FastAPI Connection Check ... [OK]", "OK")
    else:
        log_system("[CHECK 1/4] FastAPI Connection Check ... [OFFLINE MODE]", "WARNING")

    # -------------------------------------------------------------------------
    # [CHECK 2] Primary Database (MySQL) / Local Database (SQLite)
    # -------------------------------------------------------------------------
    if is_online():
        try:
            conn = get_connection()
            if conn and conn.is_connected():
                conn.close()
                log_system("[CHECK 2/4] MySQL Database Connection ... [OK]", "OK")
            else:
                log_system("[CHECK 2/4] MySQL Database Connection ... [FAILED]", "ERROR")
                set_online(False)
        except Exception as err:
            log.warning("MySQL database connection check failed: %s", err)
            log_system(f"[CHECK 2/4] MySQL Database Connection ... [FAILED] ({err})", "ERROR")
            set_online(False)

    if not is_online():
        try:
            init_local_db()
            row = sqlite_read_one("SELECT 1")
            if row:
                log_system("[CHECK 2/4] SQLite Replica Database Connection ... [OK]", "OK")
            else:
                log_system("[CHECK 2/4] SQLite Replica Database Connection ... [FAILED]", "ERROR")
                all_passed = False
        except Exception as err:
            log.error("SQLite local database check failed: %s", err)
            log_system(f"[CHECK 2/4] SQLite Replica Database Connection ... [FAILED] ({err})", "ERROR")
            all_passed = False

    # -------------------------------------------------------------------------
    # [CHECK 3] Stored Procedures & Queries Validation
    # -------------------------------------------------------------------------
    if is_online():
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT ROUTINE_NAME 
                FROM information_schema.ROUTINES 
                WHERE ROUTINE_SCHEMA = DATABASE() 
                  AND ROUTINE_TYPE = 'PROCEDURE'
            """)
            raw_routines = cursor.fetchall()
            routines = set()
            for r in raw_routines:
                if isinstance(r, dict) and "ROUTINE_NAME" in r:
                    routines.add(str(r["ROUTINE_NAME"]).lower())
                elif isinstance(r, (tuple, list)) and len(r) > 0:
                    routines.add(str(r[0]).lower())

            cursor.close()
            conn.close()

            # Verify essential stored procedures exist in MySQL catalog
            has_auth = any(sp in routines for sp in ["authenticateuser", "sp_authenticateuser", "getuserbyusername"])
            has_settings = any(sp in routines for sp in ["get_user_settings", "getuserpreferences", "sp_getuserappearance"])

            if has_auth and has_settings:
                log_system("[CHECK 3/4] Authentication & Core SP Checks ... [OK]", "OK")
            else:
                log_system("[CHECK 3/4] Authentication & Core SP Checks ... [FAILED]", "ERROR")
                all_passed = False
        except Exception as err:
            log.warning("Stored procedure verification failed: %s", err)
            log_system(f"[CHECK 3/4] Authentication & Core SP Checks ... [FAILED] ({err})", "ERROR")
            all_passed = False
    else:
        # Offline mode: verify local tables for authentication & settings
        try:
            init_local_db()
            r1 = sqlite_read_one("SELECT 1 FROM personnel LIMIT 1")
            r2 = sqlite_read_one("SELECT 1 FROM settings LIMIT 1")
            log_system("[CHECK 3/4] Authentication & Core SP Checks ... [OFFLINE MODE]", "OK")
        except Exception as err:
            log.error("Offline table query verification failed: %s", err)
            log_system(f"[CHECK 3/4] Authentication & Core SP Checks ... [FAILED] ({err})", "ERROR")
            all_passed = False

    # -------------------------------------------------------------------------
    # [CHECK 4] Session & Offline Engine Readiness
    # -------------------------------------------------------------------------
    try:
        init_local_db()
        if _LOCAL_DB_PATH.exists():
            s_conn = get_local_connection()
            cur = s_conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sync_queue'")
            sync_table = cur.fetchone()
            s_conn.close()

            if sync_table:
                log_system("[CHECK 4/4] Sync Engine & Local Replica Check ... [OK]", "OK")
            else:
                log_system("[CHECK 4/4] Sync Engine & Local Replica Check ... [FAILED]", "ERROR")
                all_passed = False
        else:
            log_system("[CHECK 4/4] Sync Engine & Local Replica Check ... [FAILED]", "ERROR")
            all_passed = False
    except Exception as err:
        log.error("Sync engine & local replica check failed: %s", err)
        log_system(f"[CHECK 4/4] Sync Engine & Local Replica Check ... [FAILED] ({err})", "ERROR")
        all_passed = False

    # -------------------------------------------------------------------------
    # Status Summary
    # -------------------------------------------------------------------------
    if all_passed:
        if is_online():
            log_system("Status: ALL CHECKS PASSED. PROCEEDING TO LOGIN/DASHBOARD.", "OK")
        else:
            log_system("Status: OFFLINE MODE ACTIVE. PROCEEDING TO LOGIN/DASHBOARD.", "OK")
    else:
        log_system("Status: DIAGNOSTIC COMPLETED WITH WARNINGS.", "WARNING")

    return all_passed


if __name__ == "__main__":
    run_system_health_checks()
