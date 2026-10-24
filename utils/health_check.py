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

# Import sync engine, logger, and configuration modules (MySQL is only reached through FastAPI)
import api_client
from api_config import get_api_url
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
    routines: set[str] = set()
    if is_online():
        try:
            resp = api_client.get(f"{get_api_url()}/health/db", timeout=5.0)
            if resp.status_code == 200 and resp.json().get("database") == "ok":
                routines = {str(p).lower() for p in resp.json().get("procedures") or []}
                log_system("[CHECK 2/4] MySQL Database Connection (via API) ... [OK]", "OK")
            else:
                log_system(f"[CHECK 2/4] MySQL Database Connection (via API) ... [FAILED] (HTTP {resp.status_code})", "ERROR")
                set_online(False)
        except Exception as err:
            log.warning("MySQL database connection check failed: %s", err)
            log_system(f"[CHECK 2/4] MySQL Database Connection (via API) ... [FAILED] ({err})", "ERROR")
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
            # Verify essential stored procedures exist in MySQL catalog (list fetched in CHECK 2)
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
