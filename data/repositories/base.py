# =============================================================================
# data/repositories/base.py — shared imports, helpers and BaseRepository
# =============================================================================

import os
import json
import hashlib
import functools
import logging
import requests
import api_client
import app_paths
from utils.password_hashing import (
    verify_password, hash_password, is_disabled as is_password_disabled,
)
from datetime import datetime
from typing import Any, List, Dict, Optional, Union, cast
from api_config import API_URL, get_api_url
from sync_engine import (
    is_online, log_offline_insert, log_offline_update,
    cache_read_result, get_cached_read,
    pull_mysql_to_sqlite_background,
    refresh_replica_tables,
    generate_temp_id,
    DB_PATH,
    sqlite_read_all,
    sqlite_read_one,
    get_local_connection,
)
from data.query import (
    get_offline_count_table_rows,
    get_offline_settings,
    get_offline_user_appearance,
    update_offline_user_appearance,
    get_offline_countries,
    get_offline_governorates,
    get_offline_departments,
    get_offline_department_by_id,
    get_offline_study_systems,
    get_offline_active_study_systems,
    get_offline_study_system_by_id,
    get_offline_personnel,
    get_offline_active_personnel,
    get_offline_personnel_by_id,
    get_offline_personnel_by_username,
    get_offline_courses,
    get_offline_courses_by_department,
    get_offline_courses_by_dept_stage_system,
    update_offline_course,
    search_offline_students_paginated,
    get_offline_last_added_students,
    get_offline_student_supplemental_graduation,
    get_offline_students_paginated,
    get_offline_student_by_id,
    search_offline_students,
    get_offline_student_statistics_by_department,
    get_offline_unlinked_students,
    link_offline_students_to_order,
    unlink_offline_students_from_order,
    get_offline_students_by_order_id,
    search_offline_students_by_order,
    get_offline_distinct_admission_years,
    delete_offline_student,
    get_offline_academic_periods_by_student,
    update_offline_academic_period_status,
    update_offline_academic_period_stage,
    delete_offline_academic_period,
    get_offline_enrollments_by_period,
    update_offline_enrollment,
    delete_offline_enrollment,
    get_offline_graduation_orders,
    get_offline_graduation_order_by_id,
    get_offline_audit_logs,
    get_offline_study_routines,
    get_offline_study_routine_by_id,
    get_offline_study_routine_periods,
    get_offline_study_routine_period_courses,
    insert_offline_study_routine,
    update_offline_study_routine,
    delete_offline_study_routine,
    get_offline_issued_certificates_by_student,
    get_offline_issued_certificate_by_id,
    get_offline_issued_certificates_report,
    count_offline_students,
    search_offline_unlinked_students,
    get_offline_unlinked_students_matching,
    get_offline_dashboard_counts,
    insert_offline_study_routine_period,
    insert_offline_study_routine_period_course,
    delete_offline_study_routine_period,
    delete_offline_study_routine_period_course,
)

activity_logger = logging.getLogger("activity")

def safe_cast(val: Any, target_type: type = int, default_val: Any = 0) -> Any:
    """Safely cast a value to target_type with default_val fallback on None or cast failure."""
    if val is None:
        return default_val
    try:
        return target_type(val)
    except (ValueError, TypeError):
        return default_val

from utils.logger import log_activity, log_system


def _local_ready(table: str) -> bool:
    """True when this laptop's copy of a local-first table has data (it is filled at login/sync)."""
    return sqlite_read_one(f"SELECT 1 AS present FROM {table} LIMIT 1") is not None


def _refreshes_local_copy(*tables: str):
    """
    Decorator for writes to local-first tables: after the write succeeds online, re-download
    those tables so screens (which read the local copy) show the change immediately.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            result = fn(*args, **kwargs)
            if is_online():
                try:
                    refresh_replica_tables(list(tables))
                except Exception as exc:
                    log_system(f"Local copy refresh after {fn.__qualname__} failed: {exc}", "WARNING")
            return result
        return wrapper
    return decorator


class OfflineModeError(Exception):
    """Raised when a destructive operation (UPDATE/DELETE) is attempted offline."""
    def __init__(self, msg: str | None = None):
        super().__init__(
            msg or
            "لا يمكن التعديل أو الحذف في وضع عدم الاتصال\n"
            "Cannot edit or delete records in Offline Mode."
        )


class BaseRepository:
    """Base repository with online/offline routing for MySQL SPs."""

    def __init__(self, api_url: str | None = None):
        self._api_url = api_url

    @property
    def api_url(self) -> str:
        return self._api_url or get_api_url()

    @api_url.setter
    def api_url(self, value: str) -> None:
        self._api_url = value

    def _post_sp(self, endpoint: str, proc_name: str, args: tuple) -> dict:
        """Send a stored-procedure call to the FastAPI gateway (/sp/read or /sp/write) and return its JSON body."""
        body = json.dumps({"proc": proc_name, "args": list(args)}, default=str, ensure_ascii=False)
        resp = api_client.post(
            f"{self.api_url}/sp/{endpoint}",
            data=body.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            timeout=15.0,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"API /sp/{endpoint} {proc_name} failed ({resp.status_code}): {resp.text}")
        return resp.json()

    def _call_write(self, proc_name: str, args: tuple = ()) -> int | None:
        """Execute a write procedure (INSERT/UPDATE/DELETE) through FastAPI, which commits it.

        Returns the new row ID when the procedure reports one.
        Raises OfflineModeError if the system is offline.
        """
        if not is_online():
            raise OfflineModeError()
        return self._post_sp("write", proc_name, args).get("new_id")

    def _read_datasets(self, proc_name: str, args: tuple) -> list[list[dict]] | None:
        """Fetch every result set of a read procedure through FastAPI; None means the server is unreachable."""
        try:
            return self._post_sp("read", proc_name, args).get("datasets") or []
        except requests.exceptions.RequestException as exc:
            log_system(f"API read {proc_name} unreachable, using offline cache: {exc}", "WARNING")
            return None

    def _call_read_all(self, proc_name: str, args: tuple = ()) -> list[dict]:
        """Execute a read procedure and return all rows. Caches results for offline use."""
        datasets = self._read_datasets(proc_name, args) if is_online() else None
        if datasets is None:
            cached = get_cached_read(proc_name, args)
            return cached if cached is not None else []
        rows = datasets[0] if datasets else []
        if datasets:
            cache_read_result(proc_name, args, rows)
        return rows

    def _call_read_one(self, proc_name: str, args: tuple = ()) -> dict | None:
        """Execute a read procedure and return a single row. Caches results for offline use."""
        datasets = self._read_datasets(proc_name, args) if is_online() else None
        if datasets is None:
            cached = get_cached_read(proc_name, args)
            if cached and len(cached) > 0:
                return cached[0]
            return None
        if not datasets:
            return None
        row = datasets[0][0] if datasets[0] else None
        # Cache as a single-element list so get_cached_read returns consistently
        cache_read_result(proc_name, args, [row] if row else [])
        return row

    def _call_read_multi(self, proc_name: str, args: tuple = ()) -> list[list[dict]]:
        """Execute a procedure returning multiple datasets. Caches the first for offline use."""
        datasets = self._read_datasets(proc_name, args) if is_online() else None
        if datasets is None:
            # Multi-dataset cache is complex; return cached first dataset or empty
            cached = get_cached_read(proc_name, args)
            return [cached] if cached else []
        # Cache all datasets as a nested list
        if datasets:
            cache_read_result(proc_name, args, datasets)
        return datasets

    def count_table_rows(self, table: str, filter_clause: str = "") -> int:
        """Count rows in a table (FastAPI when online; filtered counts use the local replica)."""
        allowed_tables = ["students", "departments", "courses", "personnel", "graduation_orders", "study_systems"]
        if table not in allowed_tables:
            return 0
        if not is_online() or filter_clause:
            return get_offline_count_table_rows(table, filter_clause)
        try:
            resp = api_client.get(f"{self.api_url}/table-count/{table}", timeout=5.0)
            if resp.status_code == 200:
                return int(resp.json().get("count", 0))
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
        return get_offline_count_table_rows(table, filter_clause)
