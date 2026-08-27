# =============================================================================
# data/repositories.py — Data Access Layer (MySQL SP Architecture)
# =============================================================================

import os
import hashlib
import logging
import sqlite3
import requests
from typing import Any, List, Dict, Optional, Union, cast
from api_config import API_URL, get_api_url
from db import get_connection
from sync_engine import (
    is_online, log_offline_insert,
    cache_read_result, get_cached_read,
    sqlite_read_all, sqlite_read_one,
    pull_mysql_to_sqlite_background,
    get_local_connection, generate_temp_id,
    DB_PATH,
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


class OfflineModeError(Exception):
    """Raised when a destructive operation (UPDATE/DELETE) is attempted offline."""
    def __init__(self, msg: str | None = None):
        super().__init__(
            msg or
            "\u0644\u0627 \u064a\u0645\u0643\u0646 \u0627\u0644\u062a\u0639\u062f\u064a\u0644 \u0623\u0648 \u0627\u0644\u062d\u0630\u0641 \u0641\u064a \u0648\u0636\u0639 \u0639\u062f\u0645 \u0627\u0644\u0627\u062a\u0635\u0627\u0644\n"
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
        
    def _call_write(self, proc_name: str, args: tuple = ()) -> int | None:
        """Execute a write procedure (INSERT/UPDATE/DELETE) and commit.
        
        Raises OfflineModeError if the system is offline.
        """
        if not is_online():
            raise OfflineModeError()
        conn = get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            cur.callproc(proc_name, args)
            conn.commit()
            
            # Extract LAST_INSERT_ID() if the SP returns a rowset with 'new_id'
            for result in cur.stored_results():
                row = result.fetchone()
                if isinstance(row, dict) and 'new_id' in row:
                    return row['new_id']
            return None
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

    def _call_read_all(self, proc_name: str, args: tuple = ()) -> list[dict]:
        """Execute a read procedure and return all rows. Caches results for offline use."""
        if not is_online():
            cached = get_cached_read(proc_name, args)
            return cached if cached is not None else []
        conn = get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            cur.callproc(proc_name, args)
            for result in cur.stored_results():
                rows = result.fetchall()
                cache_read_result(proc_name, args, rows)
                return rows
            return []
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

    def _call_read_one(self, proc_name: str, args: tuple = ()) -> dict | None:
        """Execute a read procedure and return a single row. Caches results for offline use."""
        if not is_online():
            cached = get_cached_read(proc_name, args)
            if cached and len(cached) > 0:
                return cached[0]
            return None
        conn = get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            cur.callproc(proc_name, args)
            for result in cur.stored_results():
                row = result.fetchone()
                # Cache as a single-element list so get_cached_read returns consistently
                cache_read_result(proc_name, args, [row] if row else [])
                return row
            return None
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

    def _call_read_multi(self, proc_name: str, args: tuple = ()) -> list[list[dict]]:
        """Execute a procedure returning multiple datasets. Caches the first for offline use."""
        if not is_online():
            # Multi-dataset cache is complex; return cached first dataset or empty
            cached = get_cached_read(proc_name, args)
            return [cached] if cached else []
        conn = get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            cur.callproc(proc_name, args)
            datasets = []
            for result in cur.stored_results():
                datasets.append(result.fetchall())
            # Cache all datasets as a nested list
            if datasets:
                cache_read_result(proc_name, args, datasets)
            return datasets
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

    def count_table_rows(self, table: str, filter_clause: str = "") -> int:
        """Count rows in a table securely using an inline query."""
        allowed_tables = ["students", "departments", "courses", "personnel", "graduation_orders", "study_systems"]
        if table not in allowed_tables:
            return 0
        if not is_online():
            # Count from SQLite replica
            try:
                row = sqlite_read_one(f"SELECT COUNT(*) as cnt FROM {table} {filter_clause}")
                return row["cnt"] if row else 0
            except Exception:
                return 0
        query = f"SELECT COUNT(*) FROM {table} {filter_clause}"
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query)
            row = cur.fetchone()
            return row[0] if row else 0
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

# ---------------------------------------------------------------------------
# Module 1: Global Settings & System Configurations
# ---------------------------------------------------------------------------

class SettingsRepository(BaseRepository):
    def get_settings(self) -> dict:
        if not is_online():
            row = sqlite_read_one("SELECT * FROM university_settings WHERE id = 1")
            return row if row else {}
        try:
            resp = requests.get(f"{self.api_url}/settings", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return {}
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return {}

    def update_settings(self, univ_ar: str, univ_en: str, college_ar: str, college_en: str) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            payload = {
                "univ_name_ar": univ_ar,
                "univ_name_en": univ_en,
                "college_name_ar": college_ar,
                "college_name_en": college_en
            }
            resp = requests.put(f"{self.api_url}/settings", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity("تم تحديث إعدادات النظام")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def get_user_appearance(self, emp_id: int) -> dict:
        """
        Fetch appearance preferences tied directly to personnel user via EMP_ID.
        Uses online API routing with automatic fallback to local SQLite cache.
        """
        if not is_online():
            try:
                row = sqlite_read_one(
                    "SELECT EMP_ID, theme, accent_color, font_family, font_size_base, is_arabic_rtl FROM settings WHERE EMP_ID = ?",
                    (emp_id,)
                )
                if not row:
                    return {
                        "EMP_ID": emp_id,
                        "theme": "Dark",
                        "accent_color": "blue",
                        "font_family": "Segoe UI",
                        "font_size_base": 13,
                        "is_arabic_rtl": 1
                    }
                return {
                    "EMP_ID": safe_cast(row.get("EMP_ID", emp_id), int, emp_id),
                    "theme": str(row.get("theme") or "Dark"),
                    "accent_color": str(row.get("accent_color") or "blue"),
                    "font_family": str(row.get("font_family") or "Segoe UI"),
                    "font_size_base": safe_cast(row.get("font_size_base"), int, 13),
                    "is_arabic_rtl": safe_cast(row.get("is_arabic_rtl"), int, 1)
                }
            except Exception as exc:
                log_system(f"[ERROR][SettingsRepository.get_user_appearance] Offline SQLite read failed for user {emp_id}: {exc}", "ERROR")
                return {
                    "EMP_ID": emp_id,
                    "theme": "Dark",
                    "accent_color": "blue",
                    "font_family": "Segoe UI",
                    "font_size_base": 13,
                    "is_arabic_rtl": 1
                }

        try:
            resp = requests.get(f"{self.api_url}/settings/appearance/{emp_id}", timeout=5.0)
            if resp.status_code == 200 and resp.json():
                data = resp.json()
                return {
                    "EMP_ID": int(data.get("EMP_ID") or emp_id),
                    "theme": str(data.get("theme") or "Dark"),
                    "accent_color": str(data.get("accent_color") or "blue"),
                    "font_family": str(data.get("font_family") or "Segoe UI"),
                    "font_size_base": int(data.get("font_size_base") or 13),
                    "is_arabic_rtl": int(data.get("is_arabic_rtl") if data.get("is_arabic_rtl") is not None else 1)
                }
            log_system(f"[WARNING][SettingsRepository.get_user_appearance] API status {resp.status_code}, falling back to SQLite...", "WARNING")
            row = sqlite_read_one("SELECT EMP_ID, theme, accent_color, font_family, font_size_base, is_arabic_rtl FROM settings WHERE EMP_ID = ?", (emp_id,))
            if row:
                return {
                    "EMP_ID": safe_cast(row.get("EMP_ID", emp_id), int, emp_id),
                    "theme": str(row.get("theme") or "Dark"),
                    "accent_color": str(row.get("accent_color") or "blue"),
                    "font_family": str(row.get("font_family") or "Segoe UI"),
                    "font_size_base": safe_cast(row.get("font_size_base"), int, 13),
                    "is_arabic_rtl": safe_cast(row.get("is_arabic_rtl"), int, 1)
                }
            return {
                "EMP_ID": emp_id,
                "theme": "Dark",
                "accent_color": "blue",
                "font_family": "Segoe UI",
                "font_size_base": 13,
                "is_arabic_rtl": 1
            }
        except Exception as e:
            log_system(f"[ERROR][SettingsRepository.get_user_appearance] API/DB connection failure for user {emp_id}: {e}", "ERROR")
            row = sqlite_read_one("SELECT EMP_ID, theme, accent_color, font_family, font_size_base, is_arabic_rtl FROM settings WHERE EMP_ID = ?", (emp_id,))
            if row:
                return {
                    "EMP_ID": safe_cast(row.get("EMP_ID", emp_id), int, emp_id),
                    "theme": str(row.get("theme") or "Dark"),
                    "accent_color": str(row.get("accent_color") or "blue"),
                    "font_family": str(row.get("font_family") or "Segoe UI"),
                    "font_size_base": safe_cast(row.get("font_size_base"), int, 13),
                    "is_arabic_rtl": safe_cast(row.get("is_arabic_rtl"), int, 1)
                }
            return {
                "EMP_ID": emp_id,
                "theme": "Dark",
                "accent_color": "blue",
                "font_family": "Segoe UI",
                "font_size_base": 13,
                "is_arabic_rtl": 1
            }

    def update_user_appearance(self, emp_id: int, theme: str, accent: str, font: str, size: int, rtl: int = 1) -> None:
        """
        Update appearance preferences tied directly to personnel user via EMP_ID.
        """
        if not is_online():
            conn = _get_local_conn()
            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO settings (EMP_ID, theme, accent_color, font_family, font_size_base, is_arabic_rtl)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(EMP_ID) DO UPDATE SET
                        theme = excluded.theme,
                        accent_color = excluded.accent_color,
                        font_family = excluded.font_family,
                        font_size_base = excluded.font_size_base,
                        is_arabic_rtl = excluded.is_arabic_rtl
                """, (emp_id, theme, accent, font, size, rtl))
                
                # Queue this setting update so it gets pushed when we go online
                payload = {
                    "emp_id": emp_id,
                    "theme": theme,
                    "accent_color": accent,
                    "font_family": font,
                    "font_size_base": size,
                    "rtl": rtl
                }
                from sync_engine import _json_dumps
                cur.execute(
                    "INSERT INTO sync_queue (table_name, operation, temp_id, payload) VALUES (?, 'UPDATE', ?, ?)",
                    ("settings", emp_id, _json_dumps(payload))
                )
                conn.commit()
            except Exception as exc:
                log_system(f"[ERROR][SettingsRepository.update_user_appearance] Offline SQLite update failed for user {emp_id}: {exc}", "ERROR")
                raise
            finally:
                conn.close()
            log_activity(f"تم تحديث المظهر للمستخدم ID: {emp_id}")
            return

        try:
            payload = {
                "emp_id": emp_id,
                "theme": theme,
                "accent_color": accent,
                "font_family": font,
                "font_size_base": size,
                "rtl": rtl
            }
            resp = requests.put(f"{self.api_url}/settings/appearance/{emp_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تحديث المظهر للمستخدم ID: {emp_id}")
            else:
                log_system(f"[WARNING][SettingsRepository.update_user_appearance] API returned status {resp.status_code}: {resp.text}, writing to local cache fallback...", "WARNING")
                conn = _get_local_conn()
                try:
                    conn.execute("""
                        INSERT INTO settings (EMP_ID, theme, accent_color, font_family, font_size_base, is_arabic_rtl)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(EMP_ID) DO UPDATE SET
                            theme = excluded.theme,
                            accent_color = excluded.accent_color,
                            font_family = excluded.font_family,
                            font_size_base = excluded.font_size_base,
                            is_arabic_rtl = excluded.is_arabic_rtl
                    """, (emp_id, theme, accent, font, size, rtl))
                    conn.commit()
                finally:
                    conn.close()
                log_activity(f"تم تحديث المظهر للمستخدم ID: {emp_id}")
        except Exception as e:
            log_system(f"[ERROR][SettingsRepository.update_user_appearance] API/DB connection failure for user {emp_id}: {e}", "ERROR")
            conn = _get_local_conn()
            try:
                conn.execute("""
                    INSERT INTO settings (EMP_ID, theme, accent_color, font_family, font_size_base, is_arabic_rtl)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(EMP_ID) DO UPDATE SET
                        theme = excluded.theme,
                        accent_color = excluded.accent_color,
                        font_family = excluded.font_family,
                        font_size_base = excluded.font_size_base,
                        is_arabic_rtl = excluded.is_arabic_rtl
                """, (emp_id, theme, accent, font, size, rtl))
                conn.commit()
            except Exception as ex:
                log_system(f"[ERROR][SettingsRepository.update_user_appearance] Offline SQLite fallback update failed: {ex}", "ERROR")
            finally:
                conn.close()

    def clear_audit_logs(self) -> None:
        if not is_online():
            self._call_write("ClearAuditLogs")
            log_activity("تم مسح سجل التغييرات بالكامل")
            return
        try:
            resp = requests.post(f"{self.api_url}/settings/clear-logs", timeout=5.0)
            if resp.status_code == 200:
                log_activity("تم مسح سجل التغييرات بالكامل")
            else:
                raise RuntimeError(f"API clear logs failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

# ---------------------------------------------------------------------------
# Module 2: Relational Lookups
# ---------------------------------------------------------------------------

class CountryRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all("SELECT id, name_ar, name_en, iso_code FROM countries ORDER BY name_en")
        try:
            resp = requests.get(f"{self.api_url}/lookups/countries", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

class GovernorateRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all("SELECT id, name_ar, name_en FROM governorates ORDER BY id")
        try:
            resp = requests.get(f"{self.api_url}/lookups/governorates", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

class DepartmentRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT d.id, d.name_ar, d.name_en, "
                "       u.college_name_ar AS college_name_ar, "
                "       u.college_name_en AS college_name_en, "
                "       u.college_name_ar AS college_ar, "
                "       u.college_name_en AS college_en, "
                "       4 AS study_years "
                "FROM departments d "
                "LEFT JOIN university_settings u ON d.university_settings_id = u.id "
                "ORDER BY d.name_ar"
            )
        try:
            resp = requests.get(f"{self.api_url}/departments", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []
        
    def get_by_id(self, dept_id: int) -> dict | None:
        if not is_online():
            return sqlite_read_one(
                "SELECT d.id, d.name_ar, d.name_en, "
                "       u.college_name_ar AS college_name_ar, "
                "       u.college_name_en AS college_name_en, "
                "       u.college_name_ar AS college_ar, "
                "       u.college_name_en AS college_en, "
                "       4 AS study_years "
                "FROM departments d "
                "LEFT JOIN university_settings u ON d.university_settings_id = u.id "
                "WHERE d.id = ?",
                (dept_id,)
            )
        try:
            resp = requests.get(f"{self.api_url}/departments/{dept_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return None

    def insert(self, name_ar: str, name_en: str, uni_settings_id: int = 1, **_ignored) -> int:
        if not is_online():
            return self._call_write("InsertDepartment", (name_ar, name_en, uni_settings_id))
        try:
            payload = {
                "name_ar": name_ar,
                "name_en": name_en,
                "university_settings_id": uni_settings_id
            }
            resp = requests.post(f"{self.api_url}/departments", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة قسم جديد: {name_ar}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def update(self, dept_id: int, name_ar: str, name_en: str, uni_settings_id: int = 1, **_ignored) -> None:
        if not is_online():
            self._call_write("UpdateDepartment", (dept_id, name_ar, name_en, uni_settings_id))
            log_activity(f"تم تعديل القسم: {name_ar}")
            return
        try:
            payload = {
                "name_ar": name_ar,
                "name_en": name_en,
                "university_settings_id": uni_settings_id
            }
            resp = requests.put(f"{self.api_url}/departments/{dept_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل القسم: {name_ar}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def delete(self, dept_id: int) -> None:
        if not is_online():
            self._call_write("DeleteDepartment", (dept_id,))
            log_activity(f"تم حذف القسم ID: {dept_id}")
            return
        try:
            resp = requests.delete(f"{self.api_url}/departments/{dept_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف القسم ID: {dept_id}")
            else:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

# ---------------------------------------------------------------------------
# Module 3: Study Systems
# ---------------------------------------------------------------------------

class StudySystemRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all("SELECT * FROM study_systems ORDER BY id")
        try:
            resp = requests.get(f"{self.api_url}/study-systems", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []
        
    def get_active(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all("SELECT * FROM study_systems WHERE is_active = 1 ORDER BY id")
        try:
            resp = requests.get(f"{self.api_url}/study-systems/active", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []
        
    def get_by_id(self, system_id: int) -> dict | None:
        if not is_online():
            return sqlite_read_one("SELECT * FROM study_systems WHERE id = ?", (system_id,))
        try:
            resp = requests.get(f"{self.api_url}/study-systems/{system_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return None

    def insert(self, name_ar: str, name_en: str, calc_rule: str, period_display: str = 'year', calculation_weights: str = None, study_day_type: str = 'Morning') -> int:
        if not is_online():
            return self._call_write("InsertStudySystem", (name_ar, name_en, study_day_type, calc_rule, calculation_weights, period_display, 1))
        try:
            payload = {
                "name_ar": name_ar,
                "name_en": name_en,
                "study_day_type": study_day_type,
                "calculation_rule": calc_rule,
                "calculation_weights": calculation_weights,
                "period_display": period_display,
                "is_active": 1
            }
            resp = requests.post(f"{self.api_url}/study-systems", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة نظام دراسي جديد: {name_ar}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def update(self, sys_id: int, name_ar: str, name_en: str, calc_rule: str, period_display: str = 'year', calculation_weights: str = None, study_day_type: str = 'Morning', is_active: int = 1, **_ignored) -> None:
        if not is_online():
            existing = self.get_by_id(sys_id)
            day_type = study_day_type or (existing.get("study_day_type", "Morning") if existing else "Morning")
            active_val = is_active if is_active is not None else (existing.get("is_active", 1) if existing else 1)
            self._call_write("UpdateStudySystem", (sys_id, name_ar, name_en, day_type, calc_rule, calculation_weights, period_display, active_val))
            log_activity(f"تم تعديل النظام الدراسي: {name_ar}")
            return
        try:
            existing = self.get_by_id(sys_id)
            active_val = is_active if is_active is not None else (existing.get("is_active", 1) if existing else 1)
            day_type = study_day_type or (existing.get("study_day_type", "Morning") if existing else "Morning")
            payload = {
                "name_ar": name_ar,
                "name_en": name_en,
                "study_day_type": day_type,
                "calculation_rule": calc_rule,
                "calculation_weights": calculation_weights,
                "period_display": period_display,
                "is_active": active_val
            }
            resp = requests.put(f"{self.api_url}/study-systems/{sys_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل النظام الدراسي ID: {sys_id}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def toggle(self, sys_id: int, new_status: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = requests.post(f"{self.api_url}/study-systems/{sys_id}/toggle", params={"is_active": new_status}, timeout=5.0)
            if resp.status_code != 200:
                raise RuntimeError(f"API toggle failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def delete(self, sys_id: int) -> None:
        if not is_online():
            self._call_write("DeleteStudySystem", (sys_id,))
            log_activity(f"تم حذف النظام الدراسي ID: {sys_id}")
            return
        try:
            resp = requests.delete(f"{self.api_url}/study-systems/{sys_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف النظام الدراسي ID: {sys_id}")
            else:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

# ---------------------------------------------------------------------------
# Module 4: Personnel Management & Authentication
# ---------------------------------------------------------------------------

class PersonnelRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all("SELECT * FROM personnel")
        try:
            resp = requests.get(f"{self.api_url}/personnel", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []
        
    def get_active(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all("SELECT * FROM personnel WHERE is_active = 1")
        try:
            resp = requests.get(f"{self.api_url}/personnel/active", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def get_by_id(self, person_id: int) -> dict | None:
        if not is_online():
            return sqlite_read_one("SELECT * FROM personnel WHERE id = ?", (person_id,))
        try:
            resp = requests.get(f"{self.api_url}/personnel/{person_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return None

    def authenticate(self, username: str, password_hash: str) -> dict | None:
        """Authenticate a user. Online: check MySQL + trigger background pull.
        Offline: check local SQLite replica."""
        if not is_online():
            # Offline authentication against local SQLite replica
            return sqlite_read_one(
                "SELECT * FROM personnel WHERE username = ? AND password_hash = ? AND is_active = 1",
                (username, password_hash),
            )
        try:
            payload = {"username": username, "password_hash": password_hash}
            resp = requests.post(f"{self.api_url}/personnel/login", json=payload, timeout=5.0)
            if resp.status_code == 200:
                result = resp.json()
                pull_mysql_to_sqlite_background()
                return result
            return None
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return None

    def insert(self, data: dict) -> int:
        if not is_online():
            raise OfflineModeError()
        try:
            payload = {
                "name_ar": data.get("name_ar"),
                "name_en": data.get("name_en"),
                "academic_title_ar": data.get("academic_title_ar"),
                "academic_title_en": data.get("academic_title_en"),
                "responsibility_ar": data.get("responsibility_ar"),
                "responsibility_en": data.get("responsibility_en"),
                # display_order encodes signatory state: 0=none, 1-10=signatory position
                "display_order": int(data.get("display_order") or 0),
                "username": data.get("username"),
                "password_hash": data.get("password_hash") or "",
                "personnel_role": data.get("personnel_role", "user"),
                "university_settings_id": int(data.get("university_settings_id") or 1),
                "is_active": int(data.get("is_active") if data.get("is_active") is not None else 1),
            }

            resp = requests.post(f"{self.api_url}/personnel", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة كادر جديد: {data.get('name_ar')}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise
        
    def update(self, person_id: int, data: dict) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            payload = {
                "name_ar": data.get("name_ar"),
                "name_en": data.get("name_en"),
                "academic_title_ar": data.get("academic_title_ar"),
                "academic_title_en": data.get("academic_title_en"),
                "responsibility_ar": data.get("responsibility_ar"),
                "responsibility_en": data.get("responsibility_en"),
                # display_order encodes signatory state: 0=none, 1-10=signatory position
                "display_order": int(data.get("display_order") or 0),
                "username": data.get("username"),
                "password_hash": data.get("password_hash") or "",
                "personnel_role": data.get("personnel_role", "user"),
                "university_settings_id": int(data.get("university_settings_id") or 1),
                "is_active": int(data.get("is_active") if data.get("is_active") is not None else 1),
            }

            resp = requests.put(f"{self.api_url}/personnel/{person_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل بيانات الكادر ID: {person_id}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def toggle_active(self, person_id: int, is_active: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = requests.post(f"{self.api_url}/personnel/{person_id}/toggle", params={"is_active": is_active}, timeout=5.0)
            if resp.status_code != 200:
                raise RuntimeError(f"API toggle failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise
        
    def delete(self, person_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = requests.delete(f"{self.api_url}/personnel/{person_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف الكادر ID: {person_id}")
            else:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

# ---------------------------------------------------------------------------
# Module 5: Course Catalog
# ---------------------------------------------------------------------------

class CourseRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT c.*, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en "
                "FROM courses c "
                "LEFT JOIN departments d ON c.department_id = d.id "
                "ORDER BY c.name_ar ASC"
            )
        try:
            resp = requests.get(f"{self.api_url}/courses", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            raise RuntimeError(f"API returned status code {resp.status_code}")
        except Exception as e:
            log_system(f"API request failed: {e}. Falling back to SQLite cache.", "WARNING")
            return sqlite_read_all(
                "SELECT c.*, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en "
                "FROM courses c "
                "LEFT JOIN departments d ON c.department_id = d.id "
                "ORDER BY c.name_ar ASC"
            )
        
    def get_by_department(self, dept_id: int) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT c.id, c.name_ar, c.name_en, c.credit_hours, c.department_id, c.stage_number "
                "FROM courses c "
                "WHERE c.department_id = ? "
                "ORDER BY c.stage_number ASC, c.name_ar ASC",
                (dept_id,)
            )
        try:
            resp = requests.get(f"{self.api_url}/courses/by-dept/{dept_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            raise RuntimeError(f"API returned status code {resp.status_code}")
        except Exception as e:
            log_system(f"API request failed: {e}. Falling back to SQLite cache.", "WARNING")
            return sqlite_read_all(
                "SELECT c.id, c.name_ar, c.name_en, c.credit_hours, c.department_id, c.stage_number "
                "FROM courses c "
                "WHERE c.department_id = ? "
                "ORDER BY c.stage_number ASC, c.name_ar ASC",
                (dept_id,)
            )

    def get_by_dept_stage_system(self, dept_id: int, stage: int, system_id: int) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT id, name_ar, name_en, credit_hours, stage_number FROM courses "
                "WHERE department_id = ? AND stage_number <= ? "
                "ORDER BY stage_number, name_ar",
                (dept_id, stage),
            )
        try:
            resp = requests.get(
                f"{self.api_url}/courses/by-dept-stage-system",
                params={"dept_id": dept_id, "stage": stage, "system_id": system_id},
                timeout=5.0
            )
            if resp.status_code == 200:
                return resp.json()
            raise RuntimeError(f"API returned status code {resp.status_code}")
        except Exception as e:
            log_system(f"API request failed: {e}. Falling back to SQLite cache.", "WARNING")
            return sqlite_read_all(
                "SELECT id, name_ar, name_en, credit_hours, stage_number FROM courses "
                "WHERE department_id = ? AND stage_number <= ? "
                "ORDER BY stage_number, name_ar",
                (dept_id, stage),
            )

    def get_shared_dept_ids(self, course_id: int) -> list[int]:
        return []

    def insert(self, data: dict) -> int:
        if not is_online():
            raise OfflineModeError()
        try:
            payload = dict(data)
            payload["credit_hours"] = int(payload["credit_hours"])
            payload["stage_number"] = int(payload["stage_number"])
            if "department_id" in payload and payload["department_id"] is not None:
                payload["department_id"] = int(payload["department_id"])
            
            resp = requests.post(f"{self.api_url}/courses", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة مادة دراسية جديدة: {data.get('name_ar')}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def update(self, course_id: int, data: dict) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            payload = dict(data)
            payload["credit_hours"] = int(payload["credit_hours"])
            payload["stage_number"] = int(payload["stage_number"])
            if "department_id" in payload and payload["department_id"] is not None:
                payload["department_id"] = int(payload["department_id"])
                
            resp = requests.put(f"{self.api_url}/courses/{course_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل بيانات المادة الدراسية ID: {course_id}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def delete(self, course_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = requests.delete(f"{self.api_url}/courses/{course_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف المادة الدراسية ID: {course_id}")
            else:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise


def search_students_sqlite(db_path: str, search_term: str, limit: int = 25, offset: int = 0) -> List[Dict[str, Any]]:
    """Execute paginated student search against local SQLite database."""
    search_term = search_term.strip()

    if len(search_term) < 2:
        query = """
            SELECT 
                s.id AS student_id, 
                s.full_name_ar AS name_ar, 
                s.full_name_en AS name_en, 
                d.name_ar AS department_name_ar, 
                strftime('%Y', s.graduation_date) AS graduation_year, 
                s.average
            FROM (
                SELECT id, full_name_ar, full_name_en, graduation_date, average, department_id FROM students
                UNION ALL
                SELECT id, full_name_ar, full_name_en, graduation_date, average, department_id FROM local_students
            ) s
            LEFT JOIN departments d ON s.department_id = d.id
            ORDER BY s.id DESC
            LIMIT ? OFFSET ?
        """
        params = (limit, offset)
    else:
        query = """
            SELECT 
                s.id AS student_id, 
                s.full_name_ar AS name_ar, 
                s.full_name_en AS name_en, 
                d.name_ar AS department_name_ar, 
                strftime('%Y', s.graduation_date) AS graduation_year, 
                s.average
            FROM (
                SELECT id, full_name_ar, full_name_en, graduation_date, average, department_id FROM students
                UNION ALL
                SELECT id, full_name_ar, full_name_en, graduation_date, average, department_id FROM local_students
            ) s
            LEFT JOIN departments d ON s.department_id = d.id
            WHERE 
                s.full_name_ar LIKE '%' || ? || '%' 
                OR s.full_name_en LIKE '%' || ? || '%'
            ORDER BY 
                CASE 
                    WHEN s.full_name_ar = ? OR s.full_name_en = ? THEN 1
                    WHEN s.full_name_ar LIKE ? || '%' OR s.full_name_en LIKE ? || '%' THEN 2
                    ELSE 3
                END,
                s.full_name_ar ASC
            LIMIT ? OFFSET ?
        """
        params = (search_term, search_term, search_term, search_term, search_term, search_term, limit, offset)

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            
            return [
                {
                    "student_id": safe_cast(dict(row).get("student_id"), int, 0),
                    "name_ar": safe_cast(dict(row).get("name_ar"), str, "Unknown"),
                    "name_en": safe_cast(dict(row).get("name_en"), str, "Unknown"),
                    "department_name_ar": safe_cast(dict(row).get("department_name_ar"), str, "Unknown"),
                    "graduation_year": safe_cast(dict(row).get("graduation_year"), str, "N/A"),
                    "average": safe_cast(dict(row).get("average"), float, 0.0)
                } for row in rows
            ]
    except sqlite3.OperationalError:
        # Fallback query if local_students table is absent in custom db_path
        fallback_query = (
            query.replace(
                "( SELECT id, full_name_ar, full_name_en, graduation_date, average, department_id FROM students UNION ALL SELECT id, full_name_ar, full_name_en, graduation_date, average, department_id FROM local_students ) s",
                "students s"
            ).replace(
                "(\n                SELECT id, full_name_ar, full_name_en, graduation_date, average, department_id FROM students\n                UNION ALL\n                SELECT id, full_name_ar, full_name_en, graduation_date, average, department_id FROM local_students\n            ) s",
                "students s"
            )
        )
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(fallback_query, params)
            rows = cur.fetchall()
            
            return [
                {
                    "student_id": safe_cast(dict(row).get("student_id"), int, 0),
                    "name_ar": safe_cast(dict(row).get("name_ar"), str, "Unknown"),
                    "name_en": safe_cast(dict(row).get("name_en"), str, "Unknown"),
                    "department_name_ar": safe_cast(dict(row).get("department_name_ar"), str, "Unknown"),
                    "graduation_year": safe_cast(dict(row).get("graduation_year"), str, "N/A"),
                    "average": safe_cast(dict(row).get("average"), float, 0.0)
                } for row in rows
            ]


class StudentRepository(BaseRepository):
    def __init__(self, api_url: str | None = None, local_db_path: str = DB_PATH):
        super().__init__(api_url)
        self._api_base_url = api_url
        self.local_db_path = local_db_path

    @property
    def api_base_url(self) -> str:
        return self._api_base_url or get_api_url()

    @api_base_url.setter
    def api_base_url(self, value: str) -> None:
        self._api_base_url = value

    def search_students_paginated(self, query: str = "", limit: int = 25, offset: int = 0) -> List[Dict[str, Any]]:
        """Paginated student search route supporting online API endpoint with offline SQLite fallback."""
        if is_online():
            try:
                response = requests.get(
                    f"{self.api_base_url}/students/search", 
                    params={"query": query, "limit": limit, "offset": offset},
                    timeout=3
                )
                if response.status_code == 200:
                    payload = response.json()
                    return [
                        {
                            "student_id": safe_cast(item.get("student_id"), int, 0),
                            "name_ar": safe_cast(item.get("name_ar"), str, "Unknown"),
                            "name_en": safe_cast(item.get("name_en"), str, "Unknown"),
                            "department_name_ar": safe_cast(item.get("department_name_ar"), str, "Unknown"),
                            "graduation_year": safe_cast(item.get("graduation_year"), str, "N/A"),
                            "average": safe_cast(item.get("average"), float, 0.0)
                        } for item in payload
                    ]
            except Exception as err:
                log_system(f"[WARNING][StudentRepository] API request failed, falling back to SQLite: {err}", "WARNING")

        return search_students_sqlite(self.local_db_path, query, limit, offset)

    def get_last_added_students(self, limit: int = 5) -> list[dict]:
        """Fetch the most recently added students (ordered by id DESC)."""
        query = (
            "SELECT s.id, s.full_name_ar, s.full_name_en, s.admission_year, s.status, "
            "d.name_ar AS dept_name_ar "
            "FROM ("
            "  SELECT id, full_name_ar, full_name_en, CAST(admission_year AS TEXT) AS admission_year, "
            "  CASE WHEN order_id IS NOT NULL THEN 'متخرج' ELSE 'مستمر' END AS status, department_id FROM students "
            "  UNION ALL "
            "  SELECT id, full_name_ar, full_name_en, CAST(admission_year AS TEXT) AS admission_year, 'مستمر' AS status, department_id FROM local_students"
            ") s "
            "LEFT JOIN departments d ON s.department_id = d.id "
            "ORDER BY s.id DESC LIMIT ?"
        )
        try:
            return sqlite_read_all(query, (limit,))
        except Exception as exc:
            log_system(f"Error fetching last added students: {exc}", "WARNING")
            return []

    def get_recent_issued_certificates(self, limit: int = 5) -> list[dict]:
        """Fetch recently issued certificates from issued_certificates table (or graduation orders fallback)."""
        if is_online():
            try:
                resp = requests.get(f"{self.api_url}/issued-certificates", timeout=5.0)
                if resp.status_code == 200:
                    certs = resp.json()
                    if certs:
                        return certs[:limit]
            except Exception as e:
                log_system(f"Failed to fetch issued certificates via SP API: {e}", "WARNING")

        query_ic = (
            "SELECT ic.id, ic.student_id, ic.to_title, ic.template_type, ic.issue_date, "
            "s.full_name_ar, s.full_name_en, d.name_ar AS dept_name_ar "
            "FROM issued_certificates ic "
            "JOIN students s ON ic.student_id = s.id "
            "LEFT JOIN departments d ON s.department_id = d.id "
            "ORDER BY ic.issue_date DESC, ic.id DESC LIMIT ?"
        )
        try:
            res = sqlite_read_all(query_ic, (limit,))
            if res:
                return res
        except Exception:
            pass

        # Fallback to graduation orders if issued_certificates table is empty
        query_fallback = (
            "SELECT s.id, s.full_name_ar, s.full_name_en, "
            "d.name_ar AS dept_name_ar, 'من يهمه الأمر' AS to_title, 'عربي' AS template_type, o.order_number, o.order_date AS issue_date "
            "FROM ("
            "  SELECT id, full_name_ar, full_name_en, department_id, order_id FROM students WHERE order_id IS NOT NULL "
            "  UNION ALL "
            "  SELECT id, full_name_ar, full_name_en, department_id, order_id FROM local_students WHERE order_id IS NOT NULL"
            ") s "
            "JOIN departments d ON s.department_id = d.id "
            "JOIN graduation_orders o ON s.order_id = o.id "
            "ORDER BY o.order_date DESC, s.id DESC LIMIT ?"
        )
        try:
            return sqlite_read_all(query_fallback, (limit,))
        except Exception:
            return []

    def get_recent_printed_certificates(self, limit: int = 5) -> list[dict]:
        """Fetch recently printed certificates."""
        query = (
            "SELECT s.id, s.full_name_ar, s.full_name_en, "
            "d.name_ar AS dept_name_ar, o.order_number, COALESCE(o.order_date, '2024-01-01') AS issue_date "
            "FROM ("
            "  SELECT id, full_name_ar, full_name_en, department_id, order_id FROM students WHERE order_id IS NOT NULL "
            "  UNION ALL "
            "  SELECT id, full_name_ar, full_name_en, department_id, order_id FROM local_students WHERE order_id IS NOT NULL"
            ") s "
            "JOIN departments d ON s.department_id = d.id "
            "JOIN graduation_orders o ON s.order_id = o.id "
            "ORDER BY s.id DESC LIMIT ?"
        )
        try:
            return sqlite_read_all(query, (limit,))
        except Exception:
            return []

    def get_recent_graduates(self, limit: int = 5) -> list[dict]:
        """Fetch recently graduated students (students linked to a graduation order)."""
        return self.get_recent_issued_certificates(limit=limit)

    def _inject_missing_graduation_numbers(self, students_list: list[dict]) -> list[dict]:
        """Supplemental fetch for columns omitted by legacy Stored Procedures."""
        if not students_list:
            return students_list
            
        # Check if the key is missing from the first record
        if students_list and "postgraduation_number" not in students_list[0]:
            try:
                # Extract all IDs currently being processed
                student_ids = [s["id"] for s in students_list if "id" in s]
                if not student_ids: return students_list
                
                # Use the appropriate connection (MySQL if online, SQLite if offline)
                if is_online():
                    # For supplemental columns when online, fetch via the API endpoint
                    supp_data = {}
                    for sid in student_ids:
                        try:
                            resp = requests.get(f"{self.api_url}/students/{sid}", timeout=5.0)
                            if resp.status_code == 200:
                                sdata = resp.json()
                                supp_data[sid] = {
                                    "id": sid,
                                    "sequence_number": sdata.get("sequence_number"),
                                    "postgraduation_number": sdata.get("postgraduation_number")
                                }
                        except Exception as e:
                            log_system(f"API supplemental fetch failed for {sid}: {e}", "WARNING")
                else:
                    conn = get_local_connection()
                    cursor = conn.cursor()
                    format_strings = ','.join(['?'] * len(student_ids))
                    query = f"SELECT id, sequence_number, postgraduation_number FROM students WHERE id IN ({format_strings})"
                    cursor.execute(query, tuple(student_ids))
                    supp_data = {row["id"]: dict(row) for row in cursor.fetchall()}
                    cursor.close()
                    conn.close()
                
                # Inject back into the original list (set both keys for robust compatibility)
                for s in students_list:
                    sid = s.get("id")
                    if sid in supp_data:
                        s["sequence_number"] = supp_data[sid].get("sequence_number")
                        s["postgraduation_number"] = supp_data[sid].get("postgraduation_number")
                        s["postgraduation_number"] = supp_data[sid].get("postgraduation_number")
                        
            except Exception as e:
                log_system(f"Supplemental fetch failed: {e}", "WARNING")
                
        return students_list

    def get_all_paginated(self, limit: int = 25, offset: int = 0, name_query: str = "", dept_id: int = None, year: str | int | None = None) -> list[dict]:
        if not is_online():
            conditions = []
            params = []
            if name_query:
                pattern = f"%{name_query.strip()}%"
                conditions.append("(s.full_name_ar LIKE ? OR s.full_name_en LIKE ?)")
                params += [pattern, pattern]
            if dept_id:
                conditions.append("s.department_id = ?")
                params.append(dept_id)
            if year:
                conditions.append("s.graduation_year = ?")
                params.append(str(year))
                
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            params += [limit, offset]
            
            res = sqlite_read_all(
                "SELECT s.id, s.full_name_ar, s.full_name_en, s.admission_year, s.graduation_year, s.average, s.order_id, "
                "d.name_ar AS dept_name_ar "
                "FROM (SELECT id, full_name_ar, full_name_en, CAST(admission_year AS TEXT) AS admission_year, CAST(strftime('%Y', graduation_date) AS TEXT) AS graduation_year, average, order_id, department_id FROM students "
                "      UNION ALL "
                "      SELECT id, full_name_ar, full_name_en, CAST(admission_year AS TEXT) AS admission_year, CAST(strftime('%Y', graduation_date) AS TEXT) AS graduation_year, average, order_id, department_id FROM local_students) s "
                "LEFT JOIN departments d ON s.department_id = d.id "
                f"{where} ORDER BY s.id DESC LIMIT ? OFFSET ?", tuple(params)
            )
        else:
            try:
                resp = requests.get(
                    f"{self.api_url}/students/paginated",
                    params={
                        "limit": limit,
                        "offset": offset,
                        "name_query": name_query,
                        "dept_id": dept_id,
                        "year": str(year) if year is not None else None
                    },
                    timeout=5.0
                )
                if resp.status_code == 200:
                    res = resp.json()
                    # Sort online results by ID descending as requested by user
                    if not name_query:
                        res.sort(key=lambda x: x.get("id", 0), reverse=True)
                else:
                    res = []
            except Exception as e:
                log_system(f"API request failed: {e}", "WARNING")
                res = []
        return self._inject_missing_graduation_numbers(res)
        
    def get_by_id(self, student_id: int) -> dict | None:
        if not is_online():
            res = sqlite_read_one(
                "SELECT s.*, o.order_number, "
                "COALESCE(s.graduation_date, o.order_date) AS graduation_date, "
                "COALESCE(s.graduation_semester, o.graduation_semester) AS graduation_semester, "
                "CAST(strftime('%Y', COALESCE(s.graduation_date, o.order_date)) AS TEXT) AS graduation_year, "
                "d.name_ar AS dept_name_ar, ss.name_ar AS study_system_name_ar, ss.study_day_type AS study_type, "
                "c.name_ar AS nationality_ar, g.name_ar AS birthplace_ar "
                "FROM (SELECT id, full_name_ar, full_name_en, gender, sequence_number, postgraduation_number, date_of_birth, "
                "             birthplace_id, birthplace_other, nationality_id, department_id, study_system_id, degree_level, "
                "             order_id, CAST(admission_year AS TEXT) AS admission_year, summer_training_data, average, graduation_date, graduation_semester "
                "      FROM students "
                "      UNION ALL "
                "      SELECT id, full_name_ar, full_name_en, gender, sequence_number, postgraduation_number, date_of_birth, "
                "             birthplace_id, birthplace_other, nationality_id, department_id, study_system_id, degree_level, "
                "             order_id, CAST(admission_year AS TEXT) AS admission_year, summer_training_data, average, graduation_date, graduation_semester "
                "      FROM local_students) s "
                "LEFT JOIN graduation_orders o ON s.order_id = o.id "
                "LEFT JOIN departments d ON s.department_id = d.id "
                "LEFT JOIN study_systems ss ON s.study_system_id = ss.id "
                "LEFT JOIN countries c ON s.nationality_id = c.id "
                "LEFT JOIN governorates g ON s.birthplace_id = g.id "
                "WHERE s.id = ?", (student_id,)
            )
        else:
            try:
                resp = requests.get(f"{self.api_url}/students/{student_id}", timeout=5.0)
                if resp.status_code == 200:
                    res = resp.json()
                else:
                    res = None
            except Exception as e:
                log_system(f"API request failed: {e}", "WARNING")
                res = None
        if res:
            res = self._inject_missing_graduation_numbers([res])[0]
        return res
 
    def search(self, query: str, limit: int = 8) -> list[dict]:
        clean_query = query.strip()
        
        # 1. Performance Guard: Mirroring the SP logic, abort if less than 2 chars
        if len(clean_query) < 2:
            return []

        if not is_online():
            # 2. Offline Mode: SQLite Replica Search
            exact_match = clean_query
            prefix_match = f"{clean_query}%"
            fuzzy_match = f"%{clean_query}%"
            
            # The query unions the remote cache and local queue, matching the SP's weighted sorting
            sqlite_query = """
                SELECT 
                    s.id AS student_id, 
                    s.full_name_ar AS name_ar, 
                    s.full_name_en AS name_en, 
                    d.name_ar AS dept_name_ar,
                    CAST(strftime('%Y', s.graduation_date) AS TEXT) AS graduation_year, 
                    CAST(s.admission_year AS TEXT) AS admission_year, 
                    s.average 
                FROM (
                    SELECT id, full_name_ar, full_name_en, admission_year, graduation_date, average, department_id FROM students 
                    UNION ALL 
                    SELECT id, full_name_ar, full_name_en, admission_year, graduation_date, average, department_id FROM local_students
                ) s 
                LEFT JOIN departments d ON s.department_id = d.id 
                WHERE s.full_name_ar LIKE ? OR s.full_name_en LIKE ?
                ORDER BY 
                    CASE 
                        WHEN s.full_name_ar = ? OR s.full_name_en = ? THEN 1
                        WHEN s.full_name_ar LIKE ? OR s.full_name_en LIKE ? THEN 2
                        ELSE 3 
                    END,
                    s.full_name_ar ASC
                LIMIT ?
            """
            
            # Note the parameter order matches the ? placeholders in the query
            params = (fuzzy_match, fuzzy_match, exact_match, exact_match, prefix_match, prefix_match, limit)
            res = sqlite_read_all(sqlite_query, params)
            
        else:
            # 3. Online Mode: FastAPI Call
            try:
                resp = requests.get(
                    f"{self.api_url}/students/search/all",
                    params={"query": clean_query, "limit": limit},
                    timeout=5.0
                )
                if resp.status_code == 200:
                    res = resp.json()
                else:
                    res = []
            except Exception as e:
                log_system(f"API request failed: {e}", "WARNING")
                res = []
                
        # 4. Map back to standard dict format and inject missing numbers
        formatted_res = []
        for row in res:
            formatted_res.append({
                "id": row.get("student_id") if "student_id" in row else row.get("id"),
                "full_name_ar": row.get("name_ar") if "name_ar" in row else row.get("full_name_ar"),
                "full_name_en": row.get("name_en") if "name_en" in row else row.get("full_name_en"),
                "dept_name_ar": row.get("dept_name_ar"),
                "admission_year": row.get("admission_year"),
                "graduation_year": row.get("graduation_year"),
                "average": row.get("average")
            })
            
        return self._inject_missing_graduation_numbers(formatted_res)
        
    def count(self, name_query: str = "", dept_id: int = None, year: str | int | None = None) -> int:
        if not is_online():
            conditions = []
            params = []
            if name_query:
                pattern = f"%{name_query.strip()}%"
                conditions.append("(s.full_name_ar LIKE ? OR s.full_name_en LIKE ?)")
                params += [pattern, pattern]
            if dept_id:
                conditions.append("s.department_id = ?")
                params.append(dept_id)
            if year:
                conditions.append("s.graduation_year = ?")
                params.append(str(year))
                
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            row = sqlite_read_one(
                "SELECT COUNT(*) as total_count FROM ("
                "  SELECT id, full_name_ar, full_name_en, department_id, CAST(strftime('%Y', graduation_date) AS TEXT) AS graduation_year FROM students "
                "  UNION ALL "
                "  SELECT id, full_name_ar, full_name_en, department_id, CAST(strftime('%Y', graduation_date) AS TEXT) AS graduation_year FROM local_students"
                ") s "
                f"{where}", tuple(params)
            )
            return row['total_count'] if row else 0
        try:
            resp = requests.get(
                f"{self.api_url}/students/count/all",
                params={
                    "name_query": name_query,
                    "dept_id": dept_id,
                    "year": str(year) if year is not None else None
                },
                timeout=5.0
            )
            if resp.status_code == 200:
                row = resp.json()
            else:
                row = {"total_count": 0}
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            row = {"total_count": 0}
        return row['total_count'] if row else 0
 
    def get_by_order(self, order_id: int) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT s.id, s.full_name_ar, s.full_name_en, s.average, s.order_id, d.name_ar AS dept_name_ar "
                "FROM (SELECT id, full_name_ar, full_name_en, average, order_id, department_id FROM students "
                "      UNION ALL "
                "      SELECT id, full_name_ar, full_name_en, average, order_id, department_id FROM local_students) s "
                "LEFT JOIN departments d ON s.department_id = d.id "
                "WHERE s.order_id = ? "
                "ORDER BY s.average DESC",
                (order_id,)
            )
        try:
            resp = requests.get(f"{self.api_url}/students/by-order/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def link_to_order(self, student_id: int, order_id: int) -> None:
        if not is_online():
            sqlite_read_all("UPDATE students SET order_id = ? WHERE id = ?", (order_id, student_id))
            sqlite_read_all("UPDATE local_students SET order_id = ? WHERE id = ?", (order_id, student_id))
            log_activity(f"تم ربط الطالب ID {student_id} بالأمر الجامعي ID {order_id}")
            return
        try:
            resp = requests.put(f"{self.api_url}/students/{student_id}/link-order/{order_id}", timeout=5.0)
            if resp.status_code != 200:
                st = self.get_by_id(student_id)
                if st:
                    st["order_id"] = order_id
                    self.update(student_id, st)
            log_activity(f"تم ربط الطالب ID {student_id} بالأمر الجامعي ID {order_id}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")

    def unlink_from_order(self, student_id: int) -> None:
        if not is_online():
            sqlite_read_all("UPDATE students SET order_id = NULL WHERE id = ?", (student_id,))
            sqlite_read_all("UPDATE local_students SET order_id = NULL WHERE id = ?", (student_id,))
            log_activity(f"تم إلغاء ربط الطالب ID {student_id} من الأمر الجامعي")
            return
        try:
            resp = requests.put(f"{self.api_url}/students/{student_id}/unlink-order", timeout=5.0)
            if resp.status_code != 200:
                st = self.get_by_id(student_id)
                if st:
                    st["order_id"] = None
                    self.update(student_id, st)
            log_activity(f"تم إلغاء ربط الطالب ID {student_id} من الأمر الجامعي")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")

    def search_unlinked(self, name_query: str = "", dept_id: int | None = None, year: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if is_online():
            try:
                resp = requests.get(
                    f"{self.api_url}/students/search/unlinked",
                    params={
                        "name_query": name_query,
                        "dept_id": dept_id,
                        "year": str(year) if year is not None else None,
                        "limit": limit
                    },
                    timeout=3.0
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                log_system(f"API request failed: {e}", "WARNING")

        # Direct Database Fallback (MySQL or SQLite)
        conditions = ["(s.order_id IS NULL OR s.order_id = 0)"]
        params = []
        if name_query:
            pattern = f"%{name_query.strip()}%"
            conditions.append("(s.full_name_ar LIKE %s OR s.full_name_en LIKE %s)")
            params.extend([pattern, pattern])
        if dept_id:
            conditions.append("s.department_id = %s")
            params.append(dept_id)
        if year:
            conditions.append("(YEAR(s.graduation_date) = %s OR s.admission_year = %s)")
            params.extend([str(year), str(year)])

        where = "WHERE " + " AND ".join(conditions)
        
        # 1. Direct MySQL connection fallback
        try:
            conn = get_connection()
            cur = conn.cursor(dictionary=True)
            query = f"""
                SELECT s.id, s.full_name_ar, s.full_name_en, s.department_id, s.admission_year, 
                       YEAR(s.graduation_date) AS graduation_year, s.average, s.order_id,
                       d.name_ar AS dept_name_ar
                FROM students s
                LEFT JOIN departments d ON s.department_id = d.id
                {where}
                ORDER BY s.id DESC LIMIT %s
            """
            params.append(limit)
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            if rows:
                return cast(list[dict[str, Any]], rows)
        except Exception as err:
            log_system(f"Direct MySQL query failed, falling back to SQLite: {err}", "WARNING")

        # 2. SQLite replica fallback
        sqlite_conditions = ["(s.order_id IS NULL OR s.order_id = 0)"]
        sqlite_params = []
        if name_query:
            pattern = f"%{name_query.strip()}%"
            sqlite_conditions.append("(s.full_name_ar LIKE ? OR s.full_name_en LIKE ?)")
            sqlite_params.extend([pattern, pattern])
        if dept_id:
            sqlite_conditions.append("s.department_id = ?")
            sqlite_params.append(dept_id)
        if year:
            sqlite_conditions.append("(s.graduation_year = ? OR s.admission_year = ?)")
            sqlite_params.extend([str(year), str(year)])

        sqlite_where = "WHERE " + " AND ".join(sqlite_conditions)
        sqlite_query = f"""
            SELECT s.id, s.full_name_ar, s.full_name_en, s.department_id, s.admission_year, 
                   CAST(strftime('%Y', s.graduation_date) AS TEXT) AS graduation_year, s.average, s.order_id,
                   d.name_ar AS dept_name_ar
            FROM (
                SELECT id, full_name_ar, full_name_en, admission_year, graduation_date, average, order_id, department_id FROM students
                UNION ALL
                SELECT id, full_name_ar, full_name_en, admission_year, graduation_date, average, order_id, department_id FROM local_students
            ) s
            LEFT JOIN departments d ON s.department_id = d.id
            {sqlite_where}
            ORDER BY s.id DESC LIMIT ?
        """
        sqlite_params.append(limit)
        return sqlite_read_all(sqlite_query, tuple(sqlite_params))

    def auto_link_matching(self, order_id: int, order_data: dict) -> int:
        dept_id = order_data.get("department_id")
        grad_year = order_data.get("graduation_year")
        
        conditions = ["(s.order_id IS NULL OR s.order_id = 0)"]
        params = []
        if dept_id:
            conditions.append("s.department_id = ?")
            params.append(dept_id)
        if grad_year:
            conditions.append("(s.graduation_year = ? OR s.admission_year = ?)")
            params += [str(grad_year), str(grad_year)]

        where = "WHERE " + " AND ".join(conditions)
        matching = sqlite_read_all(f"""
            SELECT s.id FROM (
                SELECT id, department_id, order_id, CAST(strftime('%Y', graduation_date) AS TEXT) AS graduation_year, CAST(admission_year AS TEXT) AS admission_year FROM students
                UNION ALL
                SELECT id, department_id, order_id, CAST(strftime('%Y', graduation_date) AS TEXT) AS graduation_year, CAST(admission_year AS TEXT) AS admission_year FROM local_students
            ) s {where}
        """, tuple(params))

        count = 0
        for m in matching:
            sid = m["id"]
            self.link_to_order(sid, order_id)
            count += 1
        return count
 
    def unlink_from_order(self, student_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = requests.post(f"{self.api_url}/students/{student_id}/unlink-order", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم فك ارتباط الطالب ID: {student_id} بالأمر الجامعي")
            else:
                raise RuntimeError(f"API unlink failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise
 
    def link_students_to_order(self, order_id: int, order_data: dict) -> int:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = requests.post(f"{self.api_url}/students/link-order/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                row = resp.json()
                count = row.get('affected_rows', 0)
                if count > 0:
                    log_activity(f"تم ربط {count} طالب بالأمر الجامعي ID: {order_id}")
                return count
            else:
                raise RuntimeError(f"API link failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def link_to_order(self, student_id: int, order_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = requests.post(f"{self.api_url}/students/{student_id}/link-order/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم ربط الطالب ID: {student_id} بالأمر الجامعي ID: {order_id}")
            else:
                raise RuntimeError(f"API single link failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise
 
    def search_for_order(self, name_query: str = "", admission_year: str | int | None = None, department_id: int = None, limit: int = 50, offset: int = 0) -> list[dict]:
        """Legacy wrapper for OrderStudentsScreen mapping to the new paginated SP."""
        return self.get_all_paginated(limit=limit, offset=offset, name_query=name_query, dept_id=department_id, year=admission_year)
 
    def get_distinct_admission_years(self) -> list[str]:
        if not is_online():
            rows = sqlite_read_all(
                "SELECT DISTINCT strftime('%Y', graduation_date) AS admission_year FROM students WHERE graduation_date IS NOT NULL "
                "UNION "
                "SELECT DISTINCT strftime('%Y', graduation_date) AS admission_year FROM local_students WHERE graduation_date IS NOT NULL "
                "ORDER BY admission_year DESC"
            )
            # Eliminate duplicates that may arise from different SQLite data types (text vs int)
            unique_years = list(set(str(r["admission_year"]) for r in rows if r["admission_year"] is not None))
            unique_years.sort(key=lambda x: int(x) if x.isdigit() else 0, reverse=True)
            return unique_years
        try:
            resp = requests.get(f"{self.api_url}/students/distinct/years", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []
 
    def insert(self, data: dict) -> int:
        if not is_online():
            # Route to offline sync engine
            return log_offline_insert("students", dict(data))
        try:
            payload = {
                "full_name_ar": data.get('full_name_ar'),
                "full_name_en": data.get('full_name_en'),
                "gender": data.get('gender', 1),
                "sequence_number": data.get('sequence_number'),
                "postgraduation_number": data.get('postgraduation_number'),
                "date_of_birth": str(data.get('date_of_birth')) if data.get('date_of_birth') else None,
                "birthplace_id": data.get('birthplace_id', 2),
                "birthplace_other": data.get('birthplace_other'),
                "nationality_id": data.get('nationality_id', 274),
                "department_id": data.get('department_id'),
                "study_system_id": data.get('study_system_id'),
                "degree_level": data.get('degree_level', 1),
                "order_id": data.get('order_id'),
                "admission_year": str(data.get('admission_year')) if data.get('admission_year') else None,
                "summer_training_data": data.get('summer_training_data'),
                "average": float(data['average']) if data.get('average') is not None else None,
                "graduation_date": str(data.get('graduation_date')) if data.get('graduation_date') else None,
                "graduation_semester": data.get('graduation_semester')
            }
            resp = requests.post(f"{self.api_url}/students", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة طالب جديد: {data.get('full_name_ar')}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise
        
    def update(self, student_id: int, data: dict) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            payload = {
                "full_name_ar": data.get('full_name_ar'),
                "full_name_en": data.get('full_name_en'),
                "gender": data.get('gender', 1),
                "sequence_number": data.get('sequence_number'),
                "postgraduation_number": data.get('postgraduation_number'),
                "date_of_birth": str(data.get('date_of_birth')) if data.get('date_of_birth') else None,
                "birthplace_id": data.get('birthplace_id'),
                "birthplace_other": data.get('birthplace_other'),
                "nationality_id": data.get('nationality_id', 1),
                "department_id": data.get('department_id'),
                "study_system_id": data.get('study_system_id'),
                "degree_level": data.get('degree_level', 1),
                "order_id": data.get('order_id'),
                "admission_year": str(data.get('admission_year')) if data.get('admission_year') else None,
                "summer_training_data": data.get('summer_training_data'),
                "average": float(data['average']) if data.get('average') is not None else None,
                "graduation_date": str(data.get('graduation_date')) if data.get('graduation_date') else None,
                "graduation_semester": data.get('graduation_semester')
            }
            resp = requests.put(f"{self.api_url}/students/{student_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل بيانات الطالب ID: {student_id}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise
 
    def delete(self, student_id: int) -> None:
        self._call_write("DeleteStudent", (student_id,))
        log_activity(f"تم حذف الطالب ID: {student_id}")

# ---------------------------------------------------------------------------
# Module 7: Timelines & Enrollments
# ---------------------------------------------------------------------------

class AcademicPeriodRepository(BaseRepository):
    def get_by_student(self, student_id: int) -> list[dict]:
        periods = []
        if is_online():
            try:
                resp = requests.get(f"{self.api_url}/academic-periods/by-student/{student_id}", timeout=3.0)
                if resp.status_code == 200:
                    periods = resp.json()
            except Exception as e:
                log_system(f"API request failed for get_by_student academic_periods: {e}", "WARNING")

            if not periods:
                try:
                    from db import get_connection as get_mysql_conn
                    m_conn = get_mysql_conn()
                    try:
                        cur = m_conn.cursor(dictionary=True)
                        try:
                            cur.execute(
                                "SELECT id, student_id, academic_year, study_system_id, stage_number, semester_num, "
                                "COALESCE(result_status, 'PASSED') AS result_status "
                                "FROM academic_periods WHERE student_id = %s ORDER BY stage_number ASC, semester_num ASC",
                                (student_id,)
                            )
                            periods = cur.fetchall() or []
                        finally:
                            cur.close()
                    finally:
                        m_conn.close()
                except Exception as sp_err:
                    log_system(f"MySQL direct read error for academic_periods: {sp_err}", "WARNING")

        if not periods:
            periods = sqlite_read_all(
                "SELECT id, student_id, academic_year, study_system_id, stage_number, semester_num, COALESCE(result_status, 'PASSED') AS result_status FROM ("
                "  SELECT id, student_id, academic_year, study_system_id, stage_number, semester_num, result_status FROM academic_periods "
                "  UNION ALL "
                "  SELECT id, student_id, academic_year, study_system_id, stage_number, semester_num, result_status FROM local_academic_periods"
                ") WHERE student_id = ? ORDER BY stage_number, semester_num",
                (student_id,)
            )

        for r in periods:
            if not r.get("result_status"):
                r["result_status"] = "PASSED"

        return periods

    def insert(self, student_id: int, year: str, sys_id: int, stage: int, semester_num: int = 1, result_status: str = "PASSED") -> int:
        if not is_online():
            return log_offline_insert("academic_periods", {
                "student_id": student_id,
                "academic_year": year,
                "study_system_id": sys_id,
                "stage_number": stage,
                "semester_num": semester_num,
                "result_status": result_status,
            })
        try:
            payload = {
                "student_id": student_id,
                "academic_year": str(year),
                "study_system_id": sys_id,
                "stage_number": stage,
                "semester_num": semester_num,
                "result_status": result_status,
            }
            resp = requests.post(f"{self.api_url}/academic-periods", json=payload, timeout=5.0)
            if resp.status_code == 200:
                return resp.json()["new_id"]
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def update_status(self, period_id: int, result_status: str) -> None:
        conn = get_local_connection()
        try:
            if period_id < 0:
                try:
                    conn.execute("UPDATE local_academic_periods SET result_status = ? WHERE id = ?", (result_status, period_id))
                except sqlite3.OperationalError as oe:
                    if "no such column" in str(oe).lower():
                        conn.execute("ALTER TABLE local_academic_periods ADD COLUMN result_status TEXT DEFAULT 'PASSED'")
                        conn.execute("UPDATE local_academic_periods SET result_status = ? WHERE id = ?", (result_status, period_id))
                    else:
                        raise
            else:
                try:
                    conn.execute("UPDATE academic_periods SET result_status = ? WHERE id = ?", (result_status, period_id))
                except sqlite3.OperationalError as oe:
                    if "no such column" in str(oe).lower():
                        conn.execute("ALTER TABLE academic_periods ADD COLUMN result_status TEXT DEFAULT 'PASSED'")
                        conn.execute("UPDATE academic_periods SET result_status = ? WHERE id = ?", (result_status, period_id))
                    else:
                        raise
            conn.commit()
        finally:
            conn.close()

        if not is_online():
            return

        try:
            resp = requests.patch(
                f"{self.api_url}/academic-periods/{period_id}/status",
                json={"result_status": result_status},
                timeout=3.0
            )
            if resp.status_code != 200:
                from db import get_connection as get_mysql_conn
                m_conn = get_mysql_conn()
                try:
                    cur = m_conn.cursor()
                    try:
                        cur.execute("UPDATE academic_periods SET result_status = %s WHERE id = %s", (result_status, period_id))
                        m_conn.commit()
                    finally:
                        cur.close()
                finally:
                    m_conn.close()
        except Exception as e:
            log_system(f"API update_status failed: {e}", "WARNING")

    def update_stage(self, period_id: int, stage_number: int) -> None:
        conn = get_local_connection()
        try:
            if period_id < 0:
                conn.execute("UPDATE local_academic_periods SET stage_number = ? WHERE id = ?", (stage_number, period_id))
            else:
                conn.execute("UPDATE academic_periods SET stage_number = ? WHERE id = ?", (stage_number, period_id))
            conn.commit()
        finally:
            conn.close()

        if not is_online():
            return

        try:
            from db import get_connection as get_mysql_conn
            m_conn = get_mysql_conn()
            try:
                cur = m_conn.cursor()
                try:
                    cur.execute("UPDATE academic_periods SET stage_number = %s WHERE id = %s", (stage_number, period_id))
                    m_conn.commit()
                finally:
                    cur.close()
            finally:
                m_conn.close()
        except Exception as e:
            log_system(f"API update_stage failed: {e}", "WARNING")

    def delete(self, period_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = requests.delete(f"{self.api_url}/academic-periods/{period_id}", timeout=5.0)
            if resp.status_code != 200:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

class EnrollmentRepository(BaseRepository):
    def get_by_period(self, period_id: int) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT e.id, e.period_id, e.course_id, e.score, e.passed_round, "
                "       CASE WHEN e.passed_round != '1' THEN 1 ELSE 0 END AS is_second_round, "
                "       c.name_ar AS course_name_ar, c.name_en AS course_name_en, c.credit_hours "
                "FROM ("
                "  SELECT id, period_id, course_id, score, passed_round FROM enrollments "
                "  UNION ALL "
                "  SELECT id, period_id, course_id, score, passed_round FROM local_enrollments"
                ") e "
                "JOIN courses c ON e.course_id = c.id "
                "WHERE e.period_id = ? "
                "ORDER BY c.name_ar",
                (period_id,)
            )
        try:
            resp = requests.get(f"{self.api_url}/enrollments/by-period/{period_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []


    def insert(self, period_id: int, course_id: int, score: float, is_second: int) -> int:
        if not is_online():
            val = is_second
            if val == 2:
                passed_round = '2'
            elif val == 3:
                passed_round = '3'
            else:
                passed_round = '1'
            return log_offline_insert("enrollments", {
                "period_id": period_id,
                "course_id": course_id,
                "score": score,
                "passed_round": passed_round,
            })
        try:
            payload = {
                "period_id": period_id,
                "course_id": course_id,
                "score": float(score),
                "is_second": int(is_second)
            }
            resp = requests.post(f"{self.api_url}/enrollments", json=payload, timeout=5.0)
            if resp.status_code == 200:
                return resp.json()["new_id"]
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def update(self, enrollment_id: int, score: float, is_second: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = requests.put(
                f"{self.api_url}/enrollments/{enrollment_id}",
                params={"score": float(score), "is_second": int(is_second)},
                timeout=5.0
            )
            if resp.status_code != 200:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def delete(self, enrollment_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = requests.delete(f"{self.api_url}/enrollments/{enrollment_id}", timeout=5.0)
            if resp.status_code != 200:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

# ---------------------------------------------------------------------------
# Module 8: Integrated Report Engine Pipeline
# ---------------------------------------------------------------------------
class CertificateRepository(BaseRepository):
    
    def get_full_certificate_data(self, student_id: int, grouping_mode: str = "DEFAULT") -> dict | None:
        if not is_online():
            response_data = {
                "settings": [],
                "student_info": [],
                "ranking": [],
                "signers": [],
                "academic_timeline": [],
                "courses_grouped": []
            }
            
            # 0. Settings
            settings = sqlite_read_one("SELECT * FROM university_settings WHERE id = 1")
            if settings: response_data["settings"] = [settings]
            
            # 1. Student Info
            student = sqlite_read_one(
                "SELECT s.*, "
                "       d.name_ar AS dept_name_ar, d.name_en AS dept_name_en, "
                "       ss.name_ar AS study_system_name_ar, ss.name_en AS study_system_name_en, "
                "       ss.calculation_rule, ss.calculation_weights, ss.period_display, ss.study_day_type AS study_type, "
                "       c.name_ar AS nationality_ar, c.name_en AS nationality_en, "
                "       g.name_ar AS birthplace_ar, g.name_en AS birthplace_en, "
                "       o.order_number, o.order_date, o.num_students AS order_num_students "
                "FROM ("
                "  SELECT id AS student_id, full_name_ar, full_name_en, gender, sequence_number, postgraduation_number, date_of_birth, "
                "         birthplace_id, birthplace_other, nationality_id, department_id, study_system_id, degree_level, "
                "         order_id, CAST(admission_year AS TEXT) AS admission_year, summer_training_data, average, graduation_date, graduation_semester, "
                "         CAST(strftime('%Y', graduation_date) AS INTEGER) AS graduation_year "
                "  FROM students "
                "  UNION ALL "
                "  SELECT id AS student_id, full_name_ar, full_name_en, gender, sequence_number, postgraduation_number, date_of_birth, "
                "         birthplace_id, birthplace_other, nationality_id, department_id, study_system_id, degree_level, "
                "         order_id, CAST(admission_year AS TEXT) AS admission_year, summer_training_data, average, graduation_date, graduation_semester, "
                "         CAST(strftime('%Y', graduation_date) AS INTEGER) AS graduation_year "
                "  FROM local_students"
                ") s "
                "LEFT JOIN departments d    ON s.department_id   = d.id "
                "LEFT JOIN study_systems ss ON s.study_system_id = ss.id "
                "LEFT JOIN countries c      ON s.nationality_id  = c.id "
                "LEFT JOIN governorates g   ON s.birthplace_id   = g.id "
                "LEFT JOIN graduation_orders o ON s.order_id = o.id "
                "WHERE s.student_id = ?",
                (student_id,)
            )
            if not student:
                return None
            response_data["student_info"] = [student]
            
            # 2. Ranking
            dept_id = student.get("department_id")
            grad_year = student.get("graduation_year")
            avg = student.get("average") or 0.0
            
            rank_row = sqlite_read_one(
                "SELECT COUNT(*) + 1 as class_rank FROM students "
                "WHERE department_id = ? AND strftime('%Y', graduation_date) = ? AND average > ? AND average IS NOT NULL",
                (dept_id, str(grad_year), avg)
            )
            total_row = sqlite_read_one(
                "SELECT COUNT(*) as total_graduates FROM students "
                "WHERE department_id = ? AND strftime('%Y', graduation_date) = ? AND average IS NOT NULL",
                (dept_id, str(grad_year))
            )
            top_row = sqlite_read_one(
                "SELECT MAX(average) as top_average FROM students "
                "WHERE department_id = ? AND strftime('%Y', graduation_date) = ?",
                (dept_id, str(grad_year))
            )
            response_data["ranking"] = [{
                "class_rank": rank_row["class_rank"] if rank_row else 1,
                "total_graduates": total_row["total_graduates"] if total_row else 1,
                "top_average": top_row["top_average"] if top_row else 0.0
            }]
            
            # 3. Signers
            signers = sqlite_read_all(
                "SELECT id, name_ar, name_en, academic_title_ar, academic_title_en, "
                "       responsibility_ar, responsibility_en, display_order, "
                "       1 AS is_signature, display_order AS page_location, "
                "       COALESCE(personnel_role, 'signer') AS personnel_role "
                "FROM personnel WHERE is_active = 1 AND display_order > 0 ORDER BY display_order ASC, id ASC"
            )
            response_data["signers"] = signers
            
            # 4. Academic Timeline
            timeline = sqlite_read_all(
                "SELECT MIN(ap.id) AS primary_period_id, "
                "       CASE WHEN ap.academic_year IS NULL OR ap.academic_year = '' THEN '' "
                "            WHEN ap.academic_year LIKE '%-%' THEN ap.academic_year "
                "            ELSE ap.academic_year || ' - ' || CAST(CAST(ap.academic_year AS INTEGER) + 1 AS TEXT) "
                "       END AS academic_year, "
                "       MAX(ap.stage_number) AS stage_number, "
                "       COALESCE(ap.semester_num, 1) AS semester_num, "
                "       GROUP_CONCAT(COALESCE(ap.result_status, 'PASSED')) AS result_status "
                "FROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap "
                "WHERE ap.student_id = ? "
                "GROUP BY ap.academic_year, ap.semester_num "
                "ORDER BY ap.academic_year ASC, ap.semester_num ASC",
                (student_id,)
            )
            response_data["academic_timeline"] = timeline
            
            # 5. Courses (Fallback grouping logic if offline)
            courses = sqlite_read_all(
                "SELECT CASE WHEN ap.academic_year IS NULL OR ap.academic_year = '' THEN '' "
                "            WHEN ap.academic_year LIKE '%-%' THEN ap.academic_year "
                "            ELSE ap.academic_year || ' - ' || CAST(CAST(ap.academic_year AS INTEGER) + 1 AS TEXT) "
                "       END AS academic_year_formatted, "
                "       ap.academic_year, ap.stage_number, COALESCE(ap.semester_num, 1) AS semester_num, "
                "       COALESCE(c.name_ar, '') AS subject_name, COALESCE(c.credit_hours, 0) AS unit, "
                "       COALESCE(e.score, 0.0) AS mark, COALESCE(e.passed_round, 1) AS passed_round, "
                "       ap.stage_number || '_' || COALESCE(ap.semester_num, 1) AS grouping_key "
                "FROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap "
                "JOIN (SELECT * FROM enrollments UNION ALL SELECT * FROM local_enrollments) e ON e.period_id = ap.id "
                "JOIN courses c ON e.course_id = c.id "
                "WHERE ap.student_id = ? "
                "ORDER BY ap.stage_number ASC, COALESCE(ap.semester_num, 1) ASC, c.name_ar ASC",
                (student_id,)
            )
            response_data["courses_grouped"] = courses

        else:
            try:
                resp = requests.get(f"{self.api_url}/certificates/{student_id}?grouping_mode={grouping_mode}", timeout=5.0)
                if resp.status_code == 200:
                    response_data = resp.json()
                else:
                    return None
            except Exception as e:
                log_system(f"API request failed: {e}", "WARNING")
                return None
            
        if not response_data or not response_data.get("student_info"):
            return None

        data = response_data["student_info"][0] if response_data.get("student_info") else {}
        
        if response_data.get("ranking") and response_data["ranking"][0]:
            analytics = response_data["ranking"][0]
            data["rank"] = data.get("sequence_number") or analytics.get("class_rank", 1)
            order_count = data.get("order_num_students")
            if not order_count and data.get("order_id"):
                try:
                    ord_r = sqlite_read_one("SELECT num_students FROM graduation_orders WHERE id = ?", (data.get("order_id"),))
                    if ord_r and ord_r.get("num_students"):
                        order_count = ord_r.get("num_students")
                except Exception:
                    pass

            data["order_num_students"] = order_count
            data["db_total_graduates"] = analytics.get("total_graduates", 1)
            data["total_graduates"] = order_count or data.get("postgraduation_number") or analytics.get("total_graduates", 1)
            data["top_average"] = analytics.get("top_average")
            
        data["academic_timeline"] = response_data.get("academic_timeline", [])
        data["courses_grouped"] = response_data.get("courses_grouped", [])
        
        signers = response_data.get("signers", [])
        data["front_signatories"] = [p for p in signers if 1 <= p.get("display_order", 0) <= 4]
        data["back_signatories"] = [p for p in signers if p.get("display_order", 0) >= 5]
        
        if response_data.get("settings") and response_data["settings"][0]:
            settings = response_data["settings"][0]
            data["univ_name_ar"] = settings.get("univ_name_ar")
            data["univ_name_en"] = settings.get("univ_name_en")
            data["college_name_ar"] = settings.get("college_name_ar")
            data["college_name_en"] = settings.get("college_name_en")
            
        # POSTGRADUATE ISOLATION BLOCK
        data["thesis"] = None
        data["supervisors"] = []
        
        degree_level = data.get("degree_level", 1)
        if degree_level in [3, 4, "Master", "PhD"]:
            thesis_repo = ThesisRepository(self.api_url)
            supervisor_repo = StudentSupervisorRepository(self.api_url)
            
            thesis_records = thesis_repo.get_by_student(student_id)
            if thesis_records:
                data["thesis"] = thesis_records
                
            data["supervisors"] = supervisor_repo.get_by_student(student_id)
            
        return data

# ---------------------------------------------------------------------------
# Module 9: Graduation Orders
# ---------------------------------------------------------------------------

class GraduationOrderRepository(BaseRepository):
    
    def get_all(self, limit: int = 25, offset: int = 0) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT o.*, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en, "
                "(SELECT COUNT(*) FROM students s WHERE s.order_id = o.id) AS linked_count "
                "FROM graduation_orders o "
                "LEFT JOIN departments d ON o.department_id = d.id "
                "ORDER BY o.id DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
        try:
            resp = requests.get(f"{self.api_url}/graduation-orders", params={"limit": limit, "offset": offset}, timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def get_by_id(self, order_id: int) -> dict | None:
        if not is_online():
            return sqlite_read_one(
                "SELECT o.*, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en "
                "FROM graduation_orders o "
                "LEFT JOIN departments d ON o.department_id = d.id "
                "WHERE o.id = ?",
                (order_id,)
            )
        try:
            resp = requests.get(f"{self.api_url}/graduation-orders/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return None

    def insert(self, data: dict) -> int:
        if not is_online():
            args = (
                data.get('order_number'),
                data.get('order_date'),
                data.get('department_id'),
                data.get('study_type'),
                data.get('graduation_year'),
                data.get('graduation_semester'),
                data.get('num_students'),
                data.get('notes'),
                data.get('study_system_id', 1)
            )
            new_id = self._call_write("InsertGraduationOrder", args)
            log_activity(f"تم إضافة أمر جامعي جديد: {data.get('order_number')}")
            return new_id
        try:
            payload = {
                "order_number": data.get('order_number'),
                "order_date": str(data.get('order_date')),
                "department_id": int(data.get('department_id')),
                "study_type": data.get('study_type'),
                "graduation_year": int(data.get('graduation_year')),
                "graduation_semester": data.get('graduation_semester'),
                "num_students": int(data.get('num_students')),
                "notes": data.get('notes'),
                "study_system_id": int(data.get('study_system_id', 1))
            }
            resp = requests.post(f"{self.api_url}/graduation-orders", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة أمر جامعي جديد: {data.get('order_number')}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def update(self, order_id: int, data: dict) -> None:
        if not is_online():
            args = (
                order_id,
                data.get('order_number'),
                data.get('order_date'),
                data.get('department_id'),
                data.get('study_type'),
                data.get('graduation_year'),
                data.get('graduation_semester'),
                data.get('num_students'),
                data.get('notes'),
                data.get('study_system_id', 1)
            )
            self._call_write("UpdateGraduationOrder", args)
            log_activity(f"تم تعديل بيانات الأمر الجامعي: {data.get('order_number')}")
            return
        try:
            payload = {
                "order_number": data.get('order_number'),
                "order_date": str(data.get('order_date')),
                "department_id": int(data.get('department_id')),
                "study_type": data.get('study_type'),
                "graduation_year": int(data.get('graduation_year')),
                "graduation_semester": data.get('graduation_semester'),
                "num_students": int(data.get('num_students')),
                "notes": data.get('notes'),
                "study_system_id": int(data.get('study_system_id', 1))
            }
            resp = requests.put(f"{self.api_url}/graduation-orders/{order_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل بيانات الأمر الجامعي: {data.get('order_number')}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def delete(self, order_id: int) -> None:
        if not is_online():
            self._call_write("DeleteGraduationOrder", (order_id,))
            log_activity(f"تم حذف الأمر الجامعي ID: {order_id}")
            return
        try:
            resp = requests.delete(f"{self.api_url}/graduation-orders/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف الأمر الجامعي ID: {order_id}")
            else:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def get_students_for_order(self, order_id: int) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT s.id, s.full_name_ar, s.full_name_en, s.admission_year, "
                "CAST(strftime('%Y', s.graduation_date) AS TEXT) AS graduation_year, s.average, s.order_id, "
                "d.name_ar AS dept_name_ar "
                "FROM (SELECT id, full_name_ar, full_name_en, admission_year, graduation_date, average, order_id, department_id FROM students "
                "      UNION ALL "
                "      SELECT id, full_name_ar, full_name_en, admission_year, graduation_date, average, order_id, department_id FROM local_students) s "
                "LEFT JOIN departments d ON s.department_id = d.id "
                "WHERE s.order_id = ?",
                (order_id,)
            )
        try:
            resp = requests.get(f"{self.api_url}/students/by-order/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def link_students(self, order_id: int) -> int:
        if not is_online():
            row = self._call_read_one("LinkStudentsToOrder", (order_id,))
            count = row['affected_rows'] if row and 'affected_rows' in row else 0
            if count > 0:
                log_activity(f"تم ربط {count} طالب بالأمر الجامعي ID: {order_id}")
            return count
        try:
            resp = requests.post(f"{self.api_url}/students/link-order/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                row = resp.json()
                count = row.get('affected_rows', 0)
                if count > 0:
                    log_activity(f"تم ربط {count} طالب بالأمر الجامعي ID: {order_id}")
                return count
            return 0
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return 0

    def unlink_student(self, student_id: int) -> None:
        if not is_online():
            self._call_write("UnlinkStudentFromOrder", (student_id,))
            log_activity(f"تم فك ارتباط الطالب ID: {student_id} بالأمر الجامعي")
            return
        try:
            resp = requests.post(f"{self.api_url}/students/{student_id}/unlink-order", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم فك ارتباط الطالب ID: {student_id} بالأمر الجامعي")
            else:
                raise RuntimeError(f"API unlink failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

# ---------------------------------------------------------------------------
# Module 10: Thesis Records
# ---------------------------------------------------------------------------
class ThesisRepository(BaseRepository):
    def get_by_student(self, student_id: int) -> list[dict]:
        if not is_online():
            return self._call_read_all("GetThesisByStudent", (student_id,))
        try:
            resp = requests.get(f"{self.api_url}/thesis/by-student/{student_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def insert(self, student_id: int, title_ar: str, title_en: str, defense_date: str = None, committee_decision: str = None, final_grade: float = None) -> int:
        if not is_online():
            args = (student_id, title_ar, title_en, defense_date, committee_decision, final_grade)
            new_id = self._call_write("InsertThesis", args)
            log_activity(f"تم إضافة سجل أطروحة للطالب ID: {student_id}")
            return new_id
        try:
            payload = {
                "student_id": student_id,
                "title_ar": title_ar,
                "title_en": title_en,
                "defense_date": str(defense_date) if defense_date else None,
                "committee_decision": committee_decision,
                "final_grade": float(final_grade) if final_grade is not None else None
            }
            resp = requests.post(f"{self.api_url}/thesis", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة سجل أطروحة للطالب ID: {student_id}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def update(self, thesis_id: int, title_ar: str, title_en: str, defense_date: str = None, committee_decision: str = None, final_grade: float = None) -> None:
        if not is_online():
            args = (thesis_id, title_ar, title_en, defense_date, committee_decision, final_grade)
            self._call_write("UpdateThesis", args)
            log_activity(f"تم تعديل سجل الأطروحة ID: {thesis_id}")
            return
        try:
            payload = {
                "student_id": 0,
                "title_ar": title_ar,
                "title_en": title_en,
                "defense_date": str(defense_date) if defense_date else None,
                "committee_decision": committee_decision,
                "final_grade": float(final_grade) if final_grade is not None else None
            }
            resp = requests.put(f"{self.api_url}/thesis/{thesis_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل سجل الأطروحة ID: {thesis_id}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def delete(self, thesis_id: int) -> None:
        if not is_online():
            self._call_write("DeleteThesis", (thesis_id,))
            log_activity(f"تم حذف سجل الأطروحة ID: {thesis_id}")
            return
        try:
            resp = requests.delete(f"{self.api_url}/thesis/{thesis_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف سجل الأطروحة ID: {thesis_id}")
            else:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def save(self, student_id: int, title_ar: str, title_en: str, defense_date: str = None, committee_decision: str = None, final_grade: float = None) -> None:
        existing = self.get_by_student(student_id)
        if existing:
            thesis_id = existing[0]['id']
            self.update(thesis_id, title_ar, title_en, defense_date, committee_decision, final_grade)
        else:
            self.insert(student_id, title_ar, title_en, defense_date, committee_decision, final_grade)

# ---------------------------------------------------------------------------
# Module 11: Student Supervisors (Postgraduates)
# ---------------------------------------------------------------------------
class StudentSupervisorRepository(BaseRepository):
    def get_by_student(self, student_id: int) -> list[dict]:
        if not is_online():
            return self._call_read_all("GetSupervisorsByStudent", (student_id,))
        try:
            resp = requests.get(f"{self.api_url}/supervisors/by-student/{student_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def insert(self, student_id: int, personnel_id: int, supervision_role: str) -> int:
        if not is_online():
            new_id = self._call_write("InsertStudentSupervisor", (student_id, personnel_id, supervision_role))
            log_activity(f"تم إضافة مشرف جديد للطالب ID: {student_id}")
            return new_id
        try:
            payload = {
                "student_id": student_id,
                "personnel_id": personnel_id,
                "supervision_role": supervision_role
            }
            resp = requests.post(f"{self.api_url}/supervisors", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة مشرف جديد للطالب ID: {student_id}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def update(self, record_id: int, personnel_id: int, supervision_role: str) -> None:
        if not is_online():
            self._call_write("UpdateStudentSupervisor", (record_id, personnel_id, supervision_role))
            log_activity(f"تم تعديل بيانات الإشراف ID: {record_id}")
            return
        try:
            payload = {
                "student_id": 0,
                "personnel_id": personnel_id,
                "supervision_role": supervision_role
            }
            resp = requests.put(f"{self.api_url}/supervisors/{record_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل بيانات الإشراف ID: {record_id}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def delete(self, record_id: int) -> None:
        if not is_online():
            self._call_write("DeleteStudentSupervisor", (record_id,))
            log_activity(f"تم حذف سجل الإشراف ID: {record_id}")
            return
        try:
            resp = requests.delete(f"{self.api_url}/supervisors/{record_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف سجل الإشراف ID: {record_id}")
            else:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

# ---------------------------------------------------------------------------
# Compatibility wrapper for students_screen.py
# ---------------------------------------------------------------------------
class SupervisorRepository(BaseRepository):
    def get_by_student(self, student_id: int) -> list[dict]:
        return StudentSupervisorRepository(self.api_url).get_by_student(student_id)

    def add(self, student_id: int, personnel_id: int, role: str) -> None:
        StudentSupervisorRepository(self.api_url).insert(student_id, personnel_id, role)

    def delete_by_student(self, student_id: int) -> None:
        records = self.get_by_student(student_id)
        for r in records:
            if 'id' in r:
                StudentSupervisorRepository(self.api_url).delete(r['id'])

# ---------------------------------------------------------------------------
# Audit Logs (Fallback)
# ---------------------------------------------------------------------------
class AuditRepository(BaseRepository):
    def _read_activity_logs(self) -> list[dict]:
        log_path = os.path.join("logs", "activity_log.txt")
        if not os.path.exists(log_path):
            return []
        logs = []
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    parts = line.split(" [ACTIVITY] ", 1)
                    if len(parts) == 2:
                        dt = parts[0].split(",")[0]
                        msg = parts[1].strip()
                        logs.append({
                            "id": len(logs),
                            "table_name": "System",
                            "action": "INFO",
                            "summary": msg,
                            "created_at": dt,
                            "error_info": None
                        })
        except Exception:
            pass
        return list(reversed(logs))

    def count_audit_log(self, table_filter: str = "", action_filter: str = "") -> int:
        return len(self._read_activity_logs())

    def get_audit_log(self, table_filter: str = "", action_filter: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
        return self._read_activity_logs()[offset:offset+limit]

    def clear_audit_logs(self) -> None:
        try:
            log_path = os.path.join("logs", "activity_log.txt")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Module 12: Dashboard Analytics
# ---------------------------------------------------------------------------

class DashboardRepository(BaseRepository):
    def get_counts(self) -> dict:
        fallback_query = (
            "SELECT "
            "(SELECT COUNT(id) FROM students) AS total_students, "
            "(SELECT COUNT(id) FROM departments) AS total_departments, "
            "(SELECT COUNT(id) FROM courses) AS total_courses, "
            "(SELECT COUNT(id) FROM personnel) AS total_personnel"
        )
        
        # 1. Offline Mode: Read directly from SQLite
        if not is_online():
            row = sqlite_read_one(fallback_query)
            return dict(row) if row else {"total_students": 0, "total_departments": 0, "total_courses": 0, "total_personnel": 0}
        
        # 2. Online Mode: Hit the FastAPI endpoint
        try:
            resp = requests.get(f"{self.api_url}/api/dashboard/counts", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            raise RuntimeError(f"API returned status code {resp.status_code}")
            
        except Exception as e:
            # 3. Failsafe: Fall back to SQLite if the server is unreachable
            log_system(f"API request failed: {e}. Falling back to SQLite cache.", "WARNING")
            row = sqlite_read_one(fallback_query)
            return dict(row) if row else {"total_students": 0, "total_departments": 0, "total_courses": 0, "total_personnel": 0}


# ---------------------------------------------------------------------------
# Module 14: Predefined Study Routines
# ---------------------------------------------------------------------------

class StudyRoutineRepository(BaseRepository):
    def get_all(self, dept_id: int | None = None) -> list[dict]:
        """Fetch all predefined study routines with their linked courses and department info (3-Tier Failover)."""
        routines = []
        if is_online():
            try:
                resp = requests.get(f"{self.api_url}/study-routines", timeout=3.0)
                if resp.status_code == 200:
                    routines = resp.json()
            except Exception as e:
                log_system(f"API request failed for get_all study routines: {e}", "WARNING")

            if not routines:
                try:
                    routines = self._call_read_all("GetAllStudyRoutines")
                except Exception as sp_err:
                    log_system(f"SP GetAllStudyRoutines fallback error: {sp_err}", "WARNING")

        if not routines:
            where_clause = "WHERE sr.department_id = ?" if dept_id else ""
            params = (dept_id,) if dept_id else ()
            query = (
                f"SELECT sr.*, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en "
                f"FROM study_routines sr "
                f"LEFT JOIN departments d ON sr.department_id = d.id "
                f"{where_clause} ORDER BY sr.id DESC"
            )
            routines = sqlite_read_all(query, params)

        if dept_id:
            routines = [r for r in routines if r.get("department_id") == dept_id]

        for r in routines:
            rid = r.get("id")
            if rid:
                courses = []
                if is_online():
                    try:
                        c_resp = requests.get(f"{self.api_url}/study-routine-courses/{rid}", timeout=3.0)
                        if c_resp.status_code == 200:
                            courses = c_resp.json()
                    except Exception:
                        pass
                    if not courses:
                        try:
                            courses = self._call_read_all("GetStudyRoutineCourses", (rid,))
                        except Exception:
                            pass
                if not courses:
                    c_query = (
                        "SELECT c.id, c.name_ar, c.name_en, c.credit_hours, c.stage_number, c.semester_num "
                        "FROM study_routine_courses src "
                        "JOIN courses c ON src.course_id = c.id "
                        "WHERE src.routine_id = ? ORDER BY c.stage_number ASC, c.semester_num ASC, c.name_ar ASC"
                    )
                    courses = sqlite_read_all(c_query, (rid,))
                r["courses"] = courses
                r["course_ids"] = [c["id"] for c in courses if isinstance(c, dict) and "id" in c]

        return routines

    def get_by_id(self, routine_id: int) -> dict | None:
        """Fetch a single study routine with full course details."""
        routines = self.get_all()
        for r in routines:
            if r.get("id") == routine_id:
                return r
        return None

    def insert(self, data: dict) -> int:
        """Create a new study routine and link its courses (3-Tier Failover)."""
        name_ar = data.get("name_ar", "")
        name_en = data.get("name_en", "")
        dept_id = int(data.get("department_id") or 1)
        sys_id = int(data.get("study_system_id") or 1)
        stage = int(data.get("stage_number") or 1)
        sem_num = int(data.get("semester_num") or 1)
        course_ids = data.get("course_ids") or []

        # 1. Always write to local SQLite cache first for instant consistency
        local_id = None
        try:
            conn = get_local_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO study_routines (name_ar, name_en, department_id, study_system_id, stage_number, semester_num) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (name_ar, name_en, dept_id, sys_id, stage, sem_num)
                )
                local_id = cur.lastrowid
                for cid in course_ids:
                    cur.execute(
                        "INSERT OR IGNORE INTO study_routine_courses (routine_id, course_id) VALUES (?, ?)",
                        (local_id, cid)
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception as sq_err:
            log_system(f"Local study_routines write warning: {sq_err}", "WARNING")

        if not is_online():
            log_offline_insert("study_routines", {
                "name_ar": name_ar, "name_en": name_en, "department_id": dept_id,
                "study_system_id": sys_id, "stage_number": stage, "semester_num": sem_num
            })
            for cid in course_ids:
                log_offline_insert("study_routine_courses", {
                    "routine_id": local_id, "course_id": cid
                })
            log_activity(f"تم إنشاء روتين دراسي جديد (أوفلاين): {name_ar}")
            return local_id

        # 2. When online, write via API or direct Stored Procedure
        new_id = None
        try:
            payload = {
                "name_ar": name_ar,
                "name_en": name_en,
                "department_id": dept_id,
                "study_system_id": sys_id,
                "stage_number": stage,
                "semester_num": sem_num
            }
            resp = requests.post(f"{self.api_url}/study-routines", json=payload, timeout=3.0)
            if resp.status_code == 200:
                res_data = resp.json()
                new_id = res_data.get("new_id") or res_data.get("inserted_id")
        except Exception as e:
            log_system(f"API request failed for insert study routine: {e}", "WARNING")

        if not new_id:
            try:
                new_id = self._call_write("InsertStudyRoutine", (name_ar, name_en, dept_id, sys_id, stage, sem_num))
            except Exception as sp_err:
                log_system(f"SP InsertStudyRoutine error: {sp_err}", "WARNING")
                new_id = local_id

        target_id = new_id or local_id
        for cid in course_ids:
            try:
                resp = requests.post(
                    f"{self.api_url}/study-routine-courses",
                    json={"routine_id": target_id, "course_id": cid},
                    timeout=3.0
                )
                if resp.status_code != 200:
                    self._call_write("InsertStudyRoutineCourse", (target_id, cid))
            except Exception:
                try:
                    self._call_write("InsertStudyRoutineCourse", (target_id, cid))
                except Exception:
                    pass

        log_activity(f"تم إنشاء روتين دراسي جديد: {name_ar}")
        return target_id

    def update(self, routine_id: int, data: dict) -> None:
        """Update an existing study routine and sync its course associations (3-Tier Failover)."""
        name_ar = data.get("name_ar", "")
        name_en = data.get("name_en", "")
        dept_id = int(data.get("department_id") or 1)
        sys_id = int(data.get("study_system_id") or 1)
        stage = int(data.get("stage_number") or 1)
        sem_num = int(data.get("semester_num") or 1)
        course_ids = data.get("course_ids") or []

        # Local SQLite update
        try:
            conn = get_local_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE study_routines SET name_ar = ?, name_en = ?, department_id = ?, study_system_id = ?, stage_number = ?, semester_num = ? WHERE id = ?",
                    (name_ar, name_en, dept_id, sys_id, stage, sem_num, routine_id)
                )
                cur.execute("DELETE FROM study_routine_courses WHERE routine_id = ?", (routine_id,))
                for cid in course_ids:
                    cur.execute(
                        "INSERT OR IGNORE INTO study_routine_courses (routine_id, course_id) VALUES (?, ?)",
                        (routine_id, cid)
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception as sq_err:
            log_system(f"Local study_routines update warning: {sq_err}", "WARNING")

        if not is_online():
            log_activity(f"تم تعديل الروتين الدراسي (أوفلاين) ID: {routine_id}")
            return

        try:
            payload = {
                "name_ar": name_ar,
                "name_en": name_en,
                "department_id": dept_id,
                "study_system_id": sys_id,
                "stage_number": stage,
                "semester_num": sem_num
            }
            resp = requests.put(f"{self.api_url}/study-routines/{routine_id}", json=payload, timeout=3.0)
            if resp.status_code != 200:
                self._call_write("UpdateStudyRoutine", (routine_id, name_ar, name_en, dept_id, sys_id, stage, sem_num))
        except Exception as e:
            try:
                self._call_write("UpdateStudyRoutine", (routine_id, name_ar, name_en, dept_id, sys_id, stage, sem_num))
            except Exception as sp_err:
                log_system(f"SP UpdateStudyRoutine error: {sp_err}", "WARNING")

        # Sync courses
        for cid in course_ids:
            try:
                requests.post(
                    f"{self.api_url}/study-routine-courses",
                    json={"routine_id": routine_id, "course_id": cid},
                    timeout=3.0
                )
            except Exception:
                try:
                    self._call_write("InsertStudyRoutineCourse", (routine_id, cid))
                except Exception:
                    pass

        log_activity(f"تم تعديل بيانات الروتين الدراسي ID: {routine_id}")

    def delete(self, routine_id: int) -> None:
        """Delete a study routine and its linked course entries (3-Tier Failover)."""
        try:
            conn = get_local_connection()
            try:
                cur = conn.cursor()
                cur.execute("DELETE FROM study_routine_courses WHERE routine_id = ?", (routine_id,))
                cur.execute("DELETE FROM study_routines WHERE id = ?", (routine_id,))
                conn.commit()
            finally:
                conn.close()
        except Exception as sq_err:
            log_system(f"Local study_routines delete warning: {sq_err}", "WARNING")

        if not is_online():
            log_activity(f"تم حذف الروتين الدراسي (أوفلاين) ID: {routine_id}")
            return

        try:
            resp = requests.delete(f"{self.api_url}/study-routines/{routine_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف الروتين الدراسي ID: {routine_id} عبر SP")
            else:
                log_system(f"API delete study routine warning: {resp.text}", "WARNING")
        except Exception as e:
            log_system(f"API request failed for delete study routine: {e}", "WARNING")

    def apply_routine_to_student(self, student_id: int, routine_id: int, academic_year: str = "") -> dict:
        """
        Applies a comprehensive 4-Year Routine to a student:
        1. Reads the routine & courses across all 4 stages and semesters.
        2. Groups courses by (stage_number, semester_num).
        3. For each stage/semester group:
           - Calculates academic year relative to student's admission year.
           - Creates/finds matching academic_period for the student.
           - Inserts all routine courses into enrollments (score=0.0, passed_round='1').
        """
        routine = self.get_by_id(routine_id)
        if not routine:
            raise ValueError(f"Routine {routine_id} not found")

        sys_id = routine.get("study_system_id", 1)
        courses = routine.get("courses", [])
        if not courses:
            return {"periods_affected": 0, "added_courses": 0}

        student_repo = StudentRepository()
        st = student_repo.get_by_id(student_id) or {}
        adm_yr_raw = str(st.get("admission_year") or "2024").strip()
        adm_yr = int(adm_yr_raw) if adm_yr_raw.isdigit() else 2024

        period_repo = AcademicPeriodRepository()
        enroll_repo = EnrollmentRepository()
        existing_periods = period_repo.get_by_student(student_id) or []

        # Map existing periods by (stage_number, semester_num)
        period_map = {}
        for p in existing_periods:
            stg_num = p.get("stage_number")
            sem_n = p.get("semester_num")
            if stg_num and sem_n:
                period_map[(stg_num, sem_n)] = p

        # Group routine courses by (stage_number, semester_num)
        courses_by_stage_sem = {}
        for c in courses:
            c_stg = int(c.get("stage_number") or 1)
            c_sem = int(c.get("semester_num") or 1)
            key = (c_stg, c_sem)
            if key not in courses_by_stage_sem:
                courses_by_stage_sem[key] = []
            courses_by_stage_sem[key].append(c)

        total_added_courses = 0

        for (stg, sem), c_list in courses_by_stage_sem.items():
            start_yr = adm_yr + (stg - 1)
            calc_year = f"{start_yr}-{start_yr+1}"

            target_period = period_map.get((stg, sem))
            if not target_period:
                try:
                    period_id = period_repo.insert(
                        student_id=student_id,
                        year=calc_year,
                        sys_id=sys_id,
                        stage=stg,
                        semester_num=sem
                    )
                    target_period = {"id": period_id, "stage_number": stg, "semester_num": sem}
                    period_map[(stg, sem)] = target_period
                except Exception as p_err:
                    log_system(f"Failed to create academic period for Stage {stg} Sem {sem}: {p_err}", "WARNING")
                    continue

            pid = target_period["id"]
            existing_enrs = enroll_repo.get_by_period(pid) or []
            existing_cids = {e["course_id"] for e in existing_enrs if "course_id" in e}

            for c in c_list:
                cid = c["id"]
                if cid not in existing_cids:
                    try:
                        enroll_repo.insert(period_id=pid, course_id=cid, score=0.0, is_second=1)
                        total_added_courses += 1
                    except Exception as err:
                        log_system(f"Failed to add routine course {cid} to period {pid}: {err}", "WARNING")

        log_activity(f"تم تطبيق الروتين الشامل ({routine.get('name_ar')}) على الطالب ID: {student_id} — تم إضافة {total_added_courses} مادة عبر {len(courses_by_stage_sem)} فترة دراسية")
        return {"periods_affected": len(courses_by_stage_sem), "added_courses": total_added_courses}


class IssuedCertificateRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT ic.id, ic.student_id, ic.to_title, ic.template_type, ic.issue_date, "
                "s.full_name_ar, s.full_name_en, d.name_ar AS dept_name_ar "
                "FROM issued_certificates ic "
                "JOIN students s ON ic.student_id = s.id "
                "LEFT JOIN departments d ON s.department_id = d.id "
                "ORDER BY ic.issue_date DESC, ic.id DESC"
            )
        try:
            resp = requests.get(f"{self.api_url}/issued-certificates", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def get_by_student(self, student_id: int) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT ic.id, ic.student_id, ic.to_title, ic.template_type, ic.issue_date, "
                "s.full_name_ar, s.full_name_en "
                "FROM issued_certificates ic "
                "JOIN students s ON ic.student_id = s.id "
                "WHERE ic.student_id = ? "
                "ORDER BY ic.issue_date DESC, ic.id DESC",
                (student_id,)
            )
        try:
            resp = requests.get(f"{self.api_url}/issued-certificates/by-student/{student_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def insert(self, student_id: int, to_title: str = "من يهمه الأمر", template_type: str = "graduation", issue_date: str = None) -> int:
        if not issue_date:
            from datetime import datetime
            issue_date = datetime.now().strftime("%Y-%m-%d")

        payload = {
            "student_id": int(student_id),
            "to_title": str(to_title or "من يهمه الأمر"),
            "template_type": str(template_type or "graduation"),
            "issue_date": str(issue_date)
        }

        # Local SQLite insertion for instant availability & offline support
        local_id = -1
        try:
            conn = get_local_connection()
            try:
                cur = conn.execute(
                    "INSERT INTO issued_certificates (student_id, to_title, template_type, issue_date) VALUES (?, ?, ?, ?)",
                    (payload["student_id"], payload["to_title"], payload["template_type"], payload["issue_date"])
                )
                conn.commit()
                local_id = cur.lastrowid
            finally:
                conn.close()
        except Exception as sq_err:
            log_system(f"Local issued_certificates write warning: {sq_err}", "WARNING")

        if not is_online():
            log_offline_insert("issued_certificates", payload)
            return local_id

        try:
            resp = requests.post(f"{self.api_url}/issued-certificates", json=payload, timeout=5.0)
            if resp.status_code == 200:
                res_data = resp.json()
                new_id = res_data.get("new_id") or res_data.get("inserted_id")
                log_activity(f"تم تسجيل الوثيقة الصادرة بالطالب ID: {student_id} (الجهة: {to_title}) عبر SP")
                return new_id or local_id
            else:
                log_system(f"API insert issued certificate warning: {resp.text}", "WARNING")
                return local_id
        except Exception as e:
            log_system(f"API request failed for insert issued certificate: {e}", "WARNING")
            return local_id

    def delete(self, cert_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = requests.delete(f"{self.api_url}/issued-certificates/{cert_id}", timeout=5.0)
            if resp.status_code != 200:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise


from repositories.auth_repository import AuthRepository