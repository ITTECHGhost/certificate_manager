# =============================================================================
# data/repositories.py — Data Access Layer (MySQL SP Architecture)
# =============================================================================

import os
import hashlib
import logging
import requests
from typing import Any, List, Dict, Optional, Union, cast
from api_config import API_URL, get_api_url
from db import get_connection
from sync_engine import (
    is_online, log_offline_insert,
    cache_read_result, get_cached_read,
    pull_mysql_to_sqlite_background,
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
    get_offline_enrollments_by_period,
    update_offline_enrollment,
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
            
            # Extract LAST_INSERT_ID() if the SP returns a rowset
            for result in cur.stored_results():
                row = result.fetchone()
                if isinstance(row, dict):
                    if 'new_id' in row and row['new_id'] is not None:
                        return int(row['new_id'])
                    if 'inserted_id' in row and row['inserted_id'] is not None:
                        return int(row['inserted_id'])
                    # Fallback to first dict value if it is an integer ID
                    vals = [v for v in row.values() if isinstance(v, int)]
                    if vals:
                        return vals[0]
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
            return get_offline_count_table_rows(table, filter_clause)
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
            return get_offline_settings()
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
            return get_offline_user_appearance(emp_id)

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
            return get_offline_user_appearance(emp_id)
        except Exception as e:
            log_system(f"[ERROR][SettingsRepository.get_user_appearance] API/DB connection failure for user {emp_id}: {e}", "ERROR")
            return get_offline_user_appearance(emp_id)

    def update_user_appearance(self, emp_id: int, theme: str, accent: str, font: str, size: int, rtl: int = 1) -> None:
        """
        Update appearance preferences tied directly to personnel user via EMP_ID.
        """
        if not is_online():
            update_offline_user_appearance(emp_id, theme, accent, font, size, rtl)
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
                update_offline_user_appearance(emp_id, theme, accent, font, size, rtl)
                log_activity(f"تم تحديث المظهر للمستخدم ID: {emp_id}")
        except Exception as e:
            log_system(f"[ERROR][SettingsRepository.update_user_appearance] API/DB connection failure for user {emp_id}: {e}", "ERROR")
            update_offline_user_appearance(emp_id, theme, accent, font, size, rtl)

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

# ---------------------------------------------------------
class CountryRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            return get_offline_countries()
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
            return get_offline_governorates()
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
            return get_offline_departments()
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
            return get_offline_department_by_id(dept_id)
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
            return get_offline_study_systems()
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
            return get_offline_active_study_systems()
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
            return get_offline_study_system_by_id(system_id)
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
            return get_offline_personnel()
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
            return get_offline_active_personnel()
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
            return get_offline_personnel_by_id(person_id)
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
            return get_offline_personnel_by_username(username)
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
            return get_offline_courses()
        try:
            resp = requests.get(f"{self.api_url}/courses", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            raise RuntimeError(f"API returned status code {resp.status_code}")
        except Exception as e:
            log_system(f"API request failed: {e}. Falling back to SQLite cache.", "WARNING")
            return get_offline_courses()
        
    def get_by_department(self, dept_id: int) -> list[dict]:
        if not is_online():
            return get_offline_courses_by_department(dept_id)
        try:
            resp = requests.get(f"{self.api_url}/courses/by-dept/{dept_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            raise RuntimeError(f"API returned status code {resp.status_code}")
        except Exception as e:
            log_system(f"API request failed: {e}. Falling back to SQLite cache.", "WARNING")
            return get_offline_courses_by_department(dept_id)

    def get_by_dept_stage_system(self, dept_id: int, stage: int, system_id: int) -> list[dict]:
        if not is_online():
            return get_offline_courses_by_dept_stage_system(dept_id, stage, system_id)
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
            return get_offline_courses_by_dept_stage_system(dept_id, stage, system_id)

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
        payload = dict(data)
        payload["credit_hours"] = int(payload.get("credit_hours", 3))
        payload["stage_number"] = int(payload.get("stage_number", 1))
        if "department_id" in payload and payload["department_id"] is not None:
            payload["department_id"] = int(payload["department_id"])

        if not is_online():
            update_offline_course(
                course_id,
                payload.get("name_ar"),
                payload.get("name_en"),
                payload["credit_hours"],
                payload.get("department_id"),
                payload["stage_number"]
            )
            return

        try:
            resp = requests.put(f"{self.api_url}/courses/{course_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل بيانات المادة الدراسية ID: {course_id}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")

            # Sync local SQLite cache
            update_offline_course(
                course_id,
                payload.get("name_ar"),
                payload.get("name_en"),
                payload["credit_hours"],
                payload.get("department_id"),
                payload["stage_number"]
            )
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

        return search_offline_students_paginated(self.local_db_path, query, limit, offset)

    def get_last_added_students(self, limit: int = 5) -> list[dict]:
        """Fetch the most recently added students (ordered by id DESC)."""
        return get_offline_last_added_students(limit)

    def get_recent_issued_certificates(self, limit: int = 5) -> list[dict]:
        """Fetch recently issued certificates strictly from issued_certificates table (no graduation_orders fallback)."""
        certs = IssuedCertificateRepository().get_all()
        return certs[:limit] if certs else []

    def get_issued_certificates_report(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        department_id: int | None = None,
        template_type: str | None = None
    ) -> list[dict]:
        """Calls GetIssuedCertificatesReport SP via API or SQLite offline fallback."""
        if is_online():
            try:
                params = {}
                if start_date: params["start_date"] = start_date
                if end_date: params["end_date"] = end_date
                if department_id: params["department_id"] = department_id
                if template_type: params["template_type"] = template_type
                resp = requests.get(f"{self.api_url}/issued-certificates/report", params=params, timeout=5.0)
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                log_system(f"Failed to fetch issued certificates report via SP API: {e}", "WARNING")

        return get_offline_issued_certificates_report(start_date, end_date, department_id, template_type)

    def get_issued_certificates_by_student(self, student_id: int) -> list[dict]:
        """Calls GetIssuedCertificatesByStudent SP via API or SQLite offline fallback."""
        if is_online():
            try:
                resp = requests.get(f"{self.api_url}/issued-certificates/by-student/{student_id}", timeout=5.0)
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                log_system(f"API request failed for student issued certs: {e}", "WARNING")

        return get_offline_issued_certificates_by_student(student_id)

    def get_issued_certificate_by_id(self, cert_id: int) -> dict | None:
        """Calls GetIssuedCertificateById SP via API or SQLite offline fallback."""
        if is_online():
            try:
                resp = requests.get(f"{self.api_url}/issued-certificates/{cert_id}", timeout=5.0)
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                log_system(f"API request failed for issued cert by id: {e}", "WARNING")

        return get_offline_issued_certificate_by_id(cert_id)

    def get_recent_printed_certificates(self, limit: int = 5) -> list[dict]:
        """Fetch recently printed certificates strictly from issued_certificates table."""
        return self.get_recent_issued_certificates(limit=limit)

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
                    supp_data = get_offline_student_supplemental_graduation(student_ids)
                
                # Inject back into the original list (set both keys for robust compatibility)
                for s in students_list:
                    sid = s.get("id")
                    if sid in supp_data:
                        s["sequence_number"] = supp_data[sid].get("sequence_number")
                        s["postgraduation_number"] = supp_data[sid].get("postgraduation_number")
                        
            except Exception as e:
                log_system(f"Supplemental fetch failed: {e}", "WARNING")
                
        return students_list

    def get_all_paginated(self, limit: int = 25, offset: int = 0, name_query: str = "", dept_id: int = None, year: str | int | None = None) -> list[dict]:
        if not is_online():
            res = get_offline_students_paginated(limit=limit, offset=offset, name_query=name_query, dept_id=dept_id, year=year)
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
            res = get_offline_student_by_id(student_id)
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
            res = search_offline_students(clean_query, limit=limit)
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
            return count_offline_students(name_query=name_query, dept_id=dept_id, year=year)
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
            return get_offline_students_by_order_id(order_id)
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
            link_offline_students_to_order([student_id], order_id)
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
            unlink_offline_students_from_order([student_id])
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

        return search_offline_unlinked_students(name_query=name_query, dept_id=dept_id, year=year, limit=limit)

    def auto_link_matching(self, order_id: int, order_data: dict) -> int:
        dept_id = order_data.get("department_id")
        grad_year = order_data.get("graduation_year")
        matching = get_offline_unlinked_students_matching(dept_id, grad_year)

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
            return get_offline_distinct_admission_years()
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
        if not is_online():
            delete_offline_student(student_id)
            log_activity(f"تم حذف الطالب ID: {student_id}")
            return

        try:
            resp = requests.delete(f"{self.api_url}/students/{student_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف الطالب ID: {student_id}")
            else:
                self._call_write("DeleteStudent", (student_id,))
                log_activity(f"تم حذف الطالب ID: {student_id}")
        except Exception as e:
            log_system(f"API delete failed, using direct write: {e}", "WARNING")
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
            periods = get_offline_academic_periods_by_student(student_id)

        status_code_map = {
            1: "PASSED", "1": "PASSED", "PASSED": "PASSED",
            2: "FAILED_REPEAT", "2": "FAILED_REPEAT", "FAILED": "FAILED_REPEAT", "FAILED_REPEAT": "FAILED_REPEAT",
            3: "EXCEPTIONAL_PASS", "3": "EXCEPTIONAL_PASS", "EXCEPTIONAL_PASS": "EXCEPTIONAL_PASS",
            4: "CARRIED_OVER", "4": "CARRIED_OVER", "CARRIED_OVER": "CARRIED_OVER",
            5: "DEFERRED", "5": "DEFERRED", "DEFERRED": "DEFERRED",
            6: "DISMISSED", "6": "DISMISSED", "DISMISSED": "DISMISSED",
        }

        norm_periods = []
        for r in periods:
            if isinstance(r, dict):
                raw_st = r.get("result_status")
                r["result_status"] = status_code_map.get(raw_st, status_code_map.get(str(raw_st).strip(), "PASSED"))
                norm_periods.append(r)
            elif isinstance(r, (tuple, list)) and len(r) >= 7:
                raw_st = r[6]
                st_str = status_code_map.get(raw_st, status_code_map.get(str(raw_st).strip(), "PASSED"))
                norm_periods.append({
                    "id": r[0], "student_id": r[1], "academic_year": r[2],
                    "study_system_id": r[3], "stage_number": r[4], "semester_num": r[5],
                    "result_status": st_str
                })

        return norm_periods

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
            resp = requests.post(f"{self.api_url}/academic-periods", json=payload, timeout=3.0)
            if resp.status_code == 200:
                return resp.json()["new_id"]
        except Exception as e:
            log_system(f"API request failed for academic-periods insert: {e}", "WARNING")

        try:
            new_id = self._call_write("InsertAcademicPeriod", (student_id, str(year), sys_id, stage, semester_num, result_status))
            if new_id:
                return new_id
        except Exception as sp_err:
            log_system(f"SP InsertAcademicPeriod error: {sp_err}", "WARNING")

        return log_offline_insert("academic_periods", {
            "student_id": student_id, "academic_year": year,
            "study_system_id": sys_id, "stage_number": stage,
            "semester_num": semester_num, "result_status": result_status,
        })

    def update_status(self, period_id: int, result_status: str | int) -> None:
        status_to_code = {
            "PASSED": 1, "1": 1, 1: 1,
            "FAILED_REPEAT": 2, "FAILED": 2, "2": 2, 2: 2,
            "EXCEPTIONAL_PASS": 3, "3": 3, 3: 3,
            "CARRIED_OVER": 4, "4": 4, 4: 4,
            "DEFERRED": 5, "5": 5, 5: 5,
            "DISMISSED": 6, "6": 6, 6: 6,
        }
        st_code = status_to_code.get(result_status, status_to_code.get(str(result_status).strip().upper(), 1))
        st_key = {1: "PASSED", 2: "FAILED_REPEAT", 3: "EXCEPTIONAL_PASS", 4: "CARRIED_OVER", 5: "DEFERRED", 6: "DISMISSED"}.get(st_code, "PASSED")

        update_offline_academic_period_status(period_id, st_key)

        if not is_online():
            return

        try:
            resp = requests.patch(
                f"{self.api_url}/academic-periods/{period_id}/status",
                json={"result_status": str(st_code)},
                timeout=3.0
            )
        except Exception as e:
            log_system(f"API update_status failed: {e}", "WARNING")

    def update_stage(self, period_id: int, stage_number: int) -> None:
        update_offline_academic_period_stage(period_id, stage_number)

        if not is_online():
            return

        try:
            resp = requests.patch(
                f"{self.api_url}/academic-periods/{period_id}/stage",
                json={"stage_number": stage_number},
                timeout=3.0
            )
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
            return get_offline_enrollments_by_period(period_id)
        try:
            resp = requests.get(f"{self.api_url}/enrollments/by-period/{period_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def insert(self, period_id: int, course_id: int, score: float, is_second: int) -> int:
        val = is_second
        passed_round = '2' if val == 2 else ('3' if val == 3 else '1')
        if not is_online():
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
            resp = requests.post(f"{self.api_url}/enrollments", json=payload, timeout=3.0)
            if resp.status_code == 200:
                return resp.json()["new_id"]
        except Exception as e:
            log_system(f"API request failed for enrollment insert: {e}", "WARNING")

        try:
            new_id = self._call_write("InsertEnrollment", (period_id, course_id, float(score), passed_round))
            if new_id:
                return new_id
        except Exception as sp_err:
            log_system(f"SP InsertEnrollment error: {sp_err}", "WARNING")

        return log_offline_insert("enrollments", {
            "period_id": period_id, "course_id": course_id,
            "score": score, "passed_round": passed_round
        })

    def update(self, enrollment_id: int, score: float, is_second: int) -> None:
        val = int(is_second)
        if val == 2:
            passed_round = '2'
        elif val == 3:
            passed_round = '3'
        elif val == 0:
            passed_round = '0'
        else:
            passed_round = '1'

        update_offline_enrollment(enrollment_id, score, passed_round)

        if not is_online():
            return

        try:
            resp = requests.put(
                f"{self.api_url}/enrollments/{enrollment_id}",
                params={"score": float(score), "is_second": int(is_second)},
                timeout=3.0
            )
        except Exception as e:
            log_system(f"API request failed for enrollment update: {e}", "WARNING")

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
        """Delegates 100% of certificate data fetching & context transformation to cert_repository.py."""
        try:
            from cert_repository import get_certificate_payload
            return get_certificate_payload(student_id, grouping_mode)
        except Exception as e:
            log_system(f"cert_repository.get_certificate_payload failed: {e}", "WARNING")
            return None

    def get_flat_yearly_courses(self, student_id: int) -> list[dict]:
        """Delegates flat-yearly course transcript fetching to cert_repository.py / data.query."""
        if is_online():
            try:
                resp = requests.get(f"{self.api_url}/certificates/flat-yearly/{student_id}", timeout=5.0)
                if resp.status_code == 200:
                    rows = resp.json()
                    if isinstance(rows, list):
                        return rows
            except Exception as e:
                log_system(f"API flat-yearly courses fetch failed: {e}", "WARNING")

        try:
            from data.query import get_offline_flat_yearly_courses
            return get_offline_flat_yearly_courses(student_id)
        except Exception as e:
            log_system(f"Offline flat-yearly courses query failed: {e}", "WARNING")
            return []

# ---------------------------------------------------------------------------
# Module 9: Graduation Orders
# ---------------------------------------------------------------------------

class GraduationOrderRepository(BaseRepository):
    
    def get_all(self, limit: int = 25, offset: int = 0) -> list[dict]:
        if not is_online():
            return get_offline_graduation_orders(limit=limit, offset=offset)
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
            return get_offline_graduation_order_by_id(order_id)
        try:
            resp = requests.get(f"{self.api_url}/graduation-orders/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return None
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
            return get_offline_students_by_order_id(order_id)
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
        if not is_online():
            return get_offline_dashboard_counts()
        
        try:
            resp = requests.get(f"{self.api_url}/api/dashboard/counts", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            raise RuntimeError(f"API returned status code {resp.status_code}")
            
        except Exception as e:
            log_system(f"API request failed: {e}. Falling back to SQLite cache.", "WARNING")
            return get_offline_dashboard_counts()


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
            routines = get_offline_study_routines(dept_id)

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
                    courses = get_offline_study_routine_period_courses(rid)
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
        """Create a new study routine and link default periods/courses (3-Tier Failover)."""
        name_ar = data.get("name_ar", "")
        name_en = data.get("name_en", "")
        dept_id = int(data.get("department_id") or 1)
        sys_id = int(data.get("study_system_id") or 1)
        course_ids = data.get("course_ids") or []

        if not is_online():
            local_id = insert_offline_study_routine(name_ar, name_en, dept_id, sys_id)
            if local_id:
                for stg in range(1, 5):
                    for sem in (1, 2):
                        self.insert_period({"routine_id": local_id, "stage_number": stg, "semester_num": sem})
            log_activity(f"تم إنشاء روتين دراسي جديد (أوفلاين): {name_ar}")
            return local_id or 1

        new_id = None
        try:
            new_id = self._call_write("InsertStudyRoutine", (name_ar, name_en, dept_id, sys_id))
        except Exception as sp_err:
            log_system(f"SP InsertStudyRoutine error: {sp_err}", "WARNING")
            new_id = insert_offline_study_routine(name_ar, name_en, dept_id, sys_id)

        target_id = new_id or 1

        try:
            for stg in range(1, 5):
                for sem in (1, 2):
                    self.insert_period({"routine_id": target_id, "stage_number": stg, "semester_num": sem})
        except Exception as p_err:
            log_system(f"Error auto-creating routine periods: {p_err}", "WARNING")

        log_activity(f"تم إنشاء روتين دراسي جديد: {name_ar}")
        return target_id

    def update(self, routine_id: int, data: dict) -> None:
        """Update an existing study routine header and sync its metadata."""
        name_ar = data.get("name_ar", "")
        name_en = data.get("name_en", "")
        dept_id = int(data.get("department_id") or 1)
        sys_id = int(data.get("study_system_id") or 1)
        course_ids = data.get("course_ids") or []

        update_offline_study_routine(routine_id, name_ar, name_en, dept_id, sys_id)

        if not is_online():
            log_activity(f"تم تعديل الروتين الدراسي (أوفلاين) ID: {routine_id}")
            return

        try:
            payload = {
                "name_ar": name_ar,
                "name_en": name_en,
                "department_id": dept_id,
                "study_system_id": sys_id,
            }
            resp = requests.put(f"{self.api_url}/study-routines/{routine_id}", json=payload, timeout=3.0)
            if resp.status_code != 200:
                self._call_write("UpdateStudyRoutine", (routine_id, name_ar, name_en, dept_id, sys_id))
        except Exception as e:
            try:
                self._call_write("UpdateStudyRoutine", (routine_id, name_ar, name_en, dept_id, sys_id))
            except Exception as sp_err:
                log_system(f"SP UpdateStudyRoutine error: {sp_err}", "WARNING")

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
        """Delete a study routine and its linked period & course entries (3-Tier Failover)."""
        delete_offline_study_routine(routine_id)

        if not is_online():
            log_activity(f"تم حذف الروتين الدراسي (أوفلاين) ID: {routine_id}")
            return

        api_success = False
        try:
            resp = requests.delete(f"{self.api_url}/study-routines/{routine_id}", timeout=5.0)
            if resp.status_code == 200:
                api_success = True
                log_activity(f"تم حذف الروتين الدراسي ID: {routine_id} عبر API")
        except Exception as e:
            log_system(f"API request failed for delete study routine: {e}", "WARNING")

        if not api_success:
            try:
                self._call_write("DeleteStudyRoutine", (routine_id,))
                log_activity(f"تم حذف الروتين الدراسي ID: {routine_id} عبر SP")
            except Exception as sp_err:
                log_system(f"SP DeleteStudyRoutine error: {sp_err}", "WARNING")

    def get_periods(self, routine_id: int) -> list[dict]:
        """Fetch periods associated with a study routine (3-Tier Failover)."""
        periods = []
        if is_online():
            try:
                periods = self._call_read_all("GetStudyRoutinePeriods", (routine_id,))
            except Exception as e:
                log_system(f"SP GetStudyRoutinePeriods error: {e}", "WARNING")

        if not periods:
            periods = get_offline_study_routine_periods(routine_id)
        return periods

    def get_period_courses(self, period_id: int) -> list[dict]:
        """Fetch courses associated with a routine period (3-Tier Failover)."""
        courses = []
        if is_online():
            try:
                courses = self._call_read_all("GetStudyRoutinePeriodCourses", (period_id,))
            except Exception as e:
                log_system(f"SP GetStudyRoutinePeriodCourses error: {e}", "WARNING")

        if not courses:
            courses = get_offline_study_routine_period_courses(period_id)
        return courses

    def insert_period(self, data: dict) -> int:
        """Add a stage/semester period to a study routine."""
        routine_id = int(data.get("routine_id") or 0)
        stage = int(data.get("stage_number") or 1)
        sem_num = int(data.get("semester_num") or 1)

        local_id = insert_offline_study_routine_period(routine_id, stage, sem_num)

        if not is_online():
            return local_id or 1

        new_id = None
        try:
            new_id = self._call_write("InsertStudyRoutinePeriod", (routine_id, stage, sem_num))
        except Exception as sp_err:
            log_system(f"SP InsertStudyRoutinePeriod error: {sp_err}", "WARNING")

        return new_id or local_id or 1

    def insert_period_course(self, period_id: int, course_id: int) -> None:
        """Assign a course to a routine period."""
        insert_offline_study_routine_period_course(period_id, course_id)

        if is_online():
            try:
                self._call_write("InsertStudyRoutinePeriodCourse", (period_id, course_id))
            except Exception as sp_err:
                log_system(f"SP InsertStudyRoutinePeriodCourse error: {sp_err}", "WARNING")

    def delete_period(self, period_id: int) -> None:
        """Delete a routine period and unassign its courses."""
        delete_offline_study_routine_period(period_id)

        if is_online():
            try:
                self._call_write("DeleteStudyRoutinePeriod", (period_id,))
            except Exception as sp_err:
                log_system(f"SP DeleteStudyRoutinePeriod error: {sp_err}", "WARNING")

    def delete_period_course(self, period_id: int, course_id: int) -> None:
        """Unassign a course from a routine period."""
        delete_offline_study_routine_period_course(period_id, course_id)

        if is_online():
            try:
                self._call_write("DeleteStudyRoutinePeriodCourse", (period_id, course_id))
            except Exception as sp_err:
                log_system(f"SP DeleteStudyRoutinePeriodCourse error: {sp_err}", "WARNING")

    def apply_routine_to_student(self, student_id: int, routine_id: int, academic_year: str = "") -> dict:
        """
        Applies a comprehensive 4-Year Routine to a student:
        1. Reads routine periods and courses across all stages/semesters.
        2. Groups courses by (stage_number, semester_num).
        3. For each stage/semester group:
           - Calculates academic year relative to student's admission year.
           - Creates/finds matching academic_period for the student.
           - Inserts all routine courses into enrollments (score=0.0, passed_round='1').
        """
        routine = self.get_by_id(routine_id) or {}

        sys_id = routine.get("study_system_id", 1)

        # Build comprehensive course map grouped by (stage_number, semester_num)
        courses_by_stage_sem = {}

        # 1. Read period-based courses
        routine_periods = self.get_periods(routine_id) or []
        for p in routine_periods:
            pid = p.get("id") or p.get("period_id")
            stg = int(p.get("stage_number") or 1)
            sem = int(p.get("semester_num") or 1)
            key = (stg, sem)
            if key not in courses_by_stage_sem:
                courses_by_stage_sem[key] = []

            if pid:
                p_courses = self.get_period_courses(pid) or []
                for pc in p_courses:
                    cid = pc.get("course_id") or pc.get("id")
                    if cid and not any((c.get("id") == cid or c.get("course_id") == cid) for c in courses_by_stage_sem[key]):
                        courses_by_stage_sem[key].append({
                            "id": cid,
                            "course_id": cid,
                            "stage_number": stg,
                            "semester_num": sem
                        })

        # 2. Also check direct header courses if any
        header_courses = routine.get("courses", []) or []
        for c in header_courses:
            cid = c.get("id") or c.get("course_id")
            stg = int(c.get("stage_number") or 1)
            sem = int(c.get("semester_num") or 1)
            key = (stg, sem)
            if key not in courses_by_stage_sem:
                courses_by_stage_sem[key] = []
            if cid and not any((existing.get("id") == cid or existing.get("course_id") == cid) for existing in courses_by_stage_sem[key]):
                courses_by_stage_sem[key].append({
                    "id": cid,
                    "course_id": cid,
                    "stage_number": stg,
                    "semester_num": sem
                })

        if not courses_by_stage_sem:
            log_system(f"Apply Routine warning: Routine {routine_id} has no assigned periods or courses.", "WARNING")
            return {"periods_affected": 0, "added_courses": 0}

        student_repo = StudentRepository()
        st = student_repo.get_by_id(student_id) if hasattr(student_repo, 'get_by_id') else None
        if not st:
            st_list = student_repo.search_students_paginated("", limit=100)
            st = next((s for s in st_list if s.get("student_id") == student_id or s.get("id") == student_id), {})

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
                period_map[(int(stg_num), int(sem_n))] = p

        total_added_courses = 0
        periods_affected = 0

        for (stg, sem), c_list in courses_by_stage_sem.items():
            start_yr = adm_yr + (stg - 1)
            calc_year = f"{start_yr}-{start_yr+1}"

            target_period = period_map.get((stg, sem))
            period_created = False
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
                    period_created = True
                except Exception as p_err:
                    log_system(f"Failed to create academic period for Stage {stg} Sem {sem}: {p_err}", "WARNING")
                    continue

            pid = target_period["id"]
            existing_enrs = enroll_repo.get_by_period(pid) or []
            existing_cids = {e.get("course_id") for e in existing_enrs if "course_id" in e}

            added_in_period = 0
            for c in c_list:
                cid = c.get("id") or c.get("course_id")
                if cid and cid not in existing_cids:
                    try:
                        enroll_repo.insert(period_id=pid, course_id=cid, score=0.0, is_second=1)
                        total_added_courses += 1
                        added_in_period += 1
                        existing_cids.add(cid)
                    except Exception as err:
                        log_system(f"Failed to add routine course {cid} to period {pid}: {err}", "WARNING")

            if period_created or added_in_period > 0:
                periods_affected += 1

        log_activity(f"تم تطبيق الروتين الشامل ({routine.get('name_ar')}) على الطالب ID: {student_id} — تم إضافة {total_added_courses} مادة عبر {periods_affected} فترة دراسية")
        return {"periods_affected": periods_affected, "added_courses": total_added_courses}


class IssuedCertificateRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            from data.query import get_offline_issued_certificates_report
            return get_offline_issued_certificates_report()
        try:
            resp = requests.get(f"{self.api_url}/issued-certificates/report", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            from data.query import get_offline_issued_certificates_report
            return get_offline_issued_certificates_report()

    def get_by_student(self, student_id: int) -> list[dict]:
        if not is_online():
            from data.query import get_offline_issued_certificates_by_student
            return get_offline_issued_certificates_by_student(student_id)
        try:
            resp = requests.get(f"{self.api_url}/issued-certificates/by-student/{student_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            from data.query import get_offline_issued_certificates_by_student
            return get_offline_issued_certificates_by_student(student_id)

    def get_by_id(self, cert_id: int) -> dict | None:
        if not is_online():
            from data.query import get_offline_issued_certificate_by_id
            return get_offline_issued_certificate_by_id(cert_id)
        try:
            resp = requests.get(f"{self.api_url}/issued-certificates/{cert_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            from data.query import get_offline_issued_certificate_by_id
            return get_offline_issued_certificate_by_id(cert_id)

    def get_report(self, start_date=None, end_date=None, dept_id=None, template_type=None) -> list[dict]:
        if not is_online():
            from data.query import get_offline_issued_certificates_report
            return get_offline_issued_certificates_report(
                start_date=start_date, end_date=end_date, dept_id=dept_id, template_type=template_type
            )
        try:
            params = {}
            if start_date: params["start_date"] = start_date
            if end_date: params["end_date"] = end_date
            if dept_id is not None: params["department_id"] = dept_id
            if template_type: params["template_type"] = template_type
            resp = requests.get(f"{self.api_url}/issued-certificates/report", params=params, timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            from data.query import get_offline_issued_certificates_report
            return get_offline_issued_certificates_report(
                start_date=start_date, end_date=end_date, dept_id=dept_id, template_type=template_type
            )

    def insert(self, student_id: int, to_title: Optional[str] = "من يهمه الأمر", template_type: Optional[str] = "graduation", issue_date: Optional[str] = None) -> int:
        if not issue_date:
            from datetime import datetime
            issue_date = datetime.now().strftime("%Y-%m-%d")

        payload = {
            "student_id": int(student_id),
            "to_title": str(to_title or "من يهمه الأمر"),
            "template_type": str(template_type or "graduation"),
            "issue_date": str(issue_date)
        }

        if not is_online():
            from data.query import insert_offline_issued_certificate
            return insert_offline_issued_certificate(
                student_id=payload["student_id"],
                to_title=payload["to_title"],
                template_type=payload["template_type"],
                issue_date=payload["issue_date"]
            )

        try:
            resp = requests.post(f"{self.api_url}/issued-certificates", json=payload, timeout=5.0)
            if resp.status_code == 200:
                res_data = resp.json()
                new_id = res_data.get("new_id") or res_data.get("inserted_id")
                log_activity(f"تم تسجيل الوثيقة الصادرة بالطالب ID: {student_id} (الجهة: {to_title}) عبر SP")
                if new_id:
                    return new_id
            else:
                log_system(f"API insert issued certificate warning: {resp.text}", "WARNING")
        except Exception as e:
            log_system(f"API request failed for insert issued certificate: {e}", "WARNING")

        from data.query import insert_offline_issued_certificate
        return insert_offline_issued_certificate(
            student_id=payload["student_id"],
            to_title=payload["to_title"],
            template_type=payload["template_type"],
            issue_date=payload["issue_date"]
        )

    def update(self, cert_id: int, to_title: Optional[str] = None, template_type: Optional[str] = None, issue_date: Optional[str] = None) -> None:
        payload = {}
        if to_title is not None: payload["to_title"] = to_title
        if template_type is not None: payload["template_type"] = template_type
        if issue_date is not None: payload["issue_date"] = issue_date

        if not is_online():
            from data.query import update_offline_issued_certificate
            update_offline_issued_certificate(
                cert_id=cert_id,
                to_title=payload.get("to_title"),
                template_type=payload.get("template_type"),
                issue_date=payload.get("issue_date")
            )
            return

        try:
            resp = requests.put(f"{self.api_url}/issued-certificates/{cert_id}", json=payload, timeout=5.0)
            if resp.status_code != 200:
                log_system(f"API update issued certificate warning: {resp.text}", "WARNING")
                from data.query import update_offline_issued_certificate
                update_offline_issued_certificate(
                    cert_id=cert_id,
                    to_title=payload.get("to_title"),
                    template_type=payload.get("template_type"),
                    issue_date=payload.get("issue_date")
                )
        except Exception as e:
            log_system(f"API request failed for update issued certificate: {e}", "WARNING")
            from data.query import update_offline_issued_certificate
            update_offline_issued_certificate(
                cert_id=cert_id,
                to_title=payload.get("to_title"),
                template_type=payload.get("template_type"),
                issue_date=payload.get("issue_date")
            )

    def delete(self, cert_id: int) -> None:
        if not is_online():
            from data.query import delete_offline_issued_certificate
            delete_offline_issued_certificate(cert_id)
            return
        try:
            resp = requests.delete(f"{self.api_url}/issued-certificates/{cert_id}", timeout=5.0)
            if resp.status_code != 200:
                log_system(f"API delete failed: {resp.text}", "WARNING")
                from data.query import delete_offline_issued_certificate
                delete_offline_issued_certificate(cert_id)
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            from data.query import delete_offline_issued_certificate
            delete_offline_issued_certificate(cert_id)


from repositories.auth_repository import AuthRepository