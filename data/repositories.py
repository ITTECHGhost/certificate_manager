# =============================================================================
# data/repositories.py — Data Access Layer (MySQL SP Architecture)
# =============================================================================

import os
import logging
import requests
from db import get_connection
from sync_engine import (
    is_online, log_offline_insert,
    cache_read_result, get_cached_read,
    sqlite_read_all, sqlite_read_one,
    pull_mysql_to_sqlite_background,
    get_local_connection,
)

activity_logger = logging.getLogger("activity")

def log_activity(summary: str) -> None:
    activity_logger.info(summary)


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
    
    def __init__(self):
        pass
        
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
                if row and 'new_id' in row:
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
        conn = get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM university_settings WHERE id = 1")
            row = cur.fetchone()
            return row or {}
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

    def update_settings(self, univ_ar: str, univ_en: str, college_ar: str, college_en: str) -> None:
        if not is_online():
            raise OfflineModeError()
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE university_settings SET univ_name_ar=%s, univ_name_en=%s, college_name_ar=%s, college_name_en=%s WHERE id=1",
                (univ_ar, univ_en, college_ar, college_en)
            )
            conn.commit()
            log_activity("\u062a\u0645 \u062a\u062d\u062f\u064a\u062b \u0625\u0639\u062f\u0627\u062f\u0627\u062a \u0627\u0644\u0646\u0638\u0627\u0645")
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

    def get_user_appearance(self, user_id: int) -> dict:
        row = self._call_read_one("GetUserPreferences", (user_id,))
        return row if row else {"theme": "System", "accent_color": "blue", "font_family": "Arial", "font_size_base": 13}

    def update_user_appearance(self, user_id: int, theme: str, accent: str, font: str, size: int, rtl: int = 1) -> None:
        self._call_write("UpdateUserPreferences", (user_id, theme, accent, font, size, rtl))
        log_activity(f"تم تحديث المظهر للمستخدم ID: {user_id}")

    def clear_audit_logs(self) -> None:
        self._call_write("ClearAuditLogs")
        log_activity("تم مسح سجل التغييرات بالكامل")

# ---------------------------------------------------------------------------
# Module 2: Relational Lookups
# ---------------------------------------------------------------------------

class CountryRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all("SELECT id, name_ar, name_en, iso_code FROM countries ORDER BY name_en")
        return self._call_read_all("GetAllCountries")

class GovernorateRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all("SELECT id, name_ar, name_en FROM governorates ORDER BY id")
        return self._call_read_all("GetAllGovernorates")

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
        return self._call_read_all("GetAllDepartments")
        
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
        return self._call_read_one("GetDepartmentByID", (dept_id,))

    def insert(self, name_ar: str, name_en: str, uni_settings_id: int = 1, **_ignored) -> int:
        new_id = self._call_write("InsertDepartment", (name_ar, name_en, uni_settings_id))
        log_activity(f"تم إضافة قسم جديد: {name_ar}")
        return new_id

    def update(self, dept_id: int, name_ar: str, name_en: str, uni_settings_id: int = 1, **_ignored) -> None:
        self._call_write("UpdateDepartment", (dept_id, name_ar, name_en, uni_settings_id))
        log_activity(f"تم تعديل القسم: {name_ar}")

    def delete(self, dept_id: int) -> None:
        self._call_write("DeleteDepartment", (dept_id,))
        log_activity(f"تم حذف القسم ID: {dept_id}")

# ---------------------------------------------------------------------------
# Module 3: Study Systems
# ---------------------------------------------------------------------------

class StudySystemRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all("SELECT * FROM study_systems ORDER BY id")
        return self._call_read_all("GetAllStudySystems")
        
    def get_active(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all("SELECT * FROM study_systems WHERE is_active = 1 ORDER BY id")
        return self._call_read_all("GetActiveStudySystems")
        
    def get_by_id(self, system_id: int) -> dict | None:
        if not is_online():
            return sqlite_read_one("SELECT * FROM study_systems WHERE id = ?", (system_id,))
        return self._call_read_one("GetStudySystemByID", (system_id,))

    def insert(self, name_ar: str, name_en: str, calc_rule: str, period_display: str = 'year', calculation_weights: str = None) -> int:
        new_id = self._call_write("InsertStudySystem", (name_ar, name_en, "Morning", calc_rule, calculation_weights, period_display, 1))
        log_activity(f"تم إضافة نظام دراسي جديد: {name_ar}")
        return new_id

    def update(self, sys_id: int, name_ar: str, name_en: str, calc_rule: str, period_display: str = 'year', calculation_weights: str = None, **_ignored) -> None:
        existing = self.get_by_id(sys_id)
        day_type = existing.get("study_day_type", "Morning") if existing else "Morning"
        is_active = existing.get("is_active", 1) if existing else 1
        self._call_write("UpdateStudySystem", (sys_id, name_ar, name_en, day_type, calc_rule, calculation_weights, period_display, is_active))
        log_activity(f"تم تعديل النظام الدراسي: {name_ar}")

    def toggle(self, sys_id: int, new_status: int) -> None:
        if not is_online():
            raise OfflineModeError()
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE study_systems SET is_active = %s WHERE id = %s", (new_status, sys_id))
            conn.commit()
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

    def delete(self, sys_id: int) -> None:
        self._call_write("DeleteStudySystem", (sys_id,))
        log_activity(f"تم حذف النظام الدراسي ID: {sys_id}")

# ---------------------------------------------------------------------------
# Module 4: Personnel Management & Authentication
# ---------------------------------------------------------------------------

class PersonnelRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all("SELECT * FROM personnel")
        return self._call_read_all("GetAllPersonnel")
        
    def get_active(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all("SELECT * FROM personnel WHERE is_active = 1")
        return self._call_read_all("GetActivePersonnel")

    def authenticate(self, username: str, password_hash: str) -> dict | None:
        """Authenticate a user. Online: check MySQL + trigger background pull.
        Offline: check local SQLite replica."""
        if not is_online():
            # Offline authentication against local SQLite replica
            return sqlite_read_one(
                "SELECT * FROM personnel WHERE username = ? AND password_hash = ? AND is_active = 1",
                (username, password_hash),
            )
        # Online: use MySQL SP
        result = self._call_read_one("AuthenticateUser", (username, password_hash))
        if result:
            # Successful login — refresh local cache in background
            pull_mysql_to_sqlite_background()
        return result

    def insert(self, data: dict) -> int:
        if not is_online():
            raise OfflineModeError()
        conn = get_connection()
        try:
            fields = list(data.keys())
            placeholders = ", ".join(["%s"] * len(fields))
            columns = ", ".join(fields)
            values = tuple(data[f] for f in fields)
            cur = conn.cursor()
            cur.execute(f"INSERT INTO personnel ({columns}) VALUES ({placeholders})", values)
            conn.commit()
            new_id = cur.lastrowid
            log_activity(f"تم إضافة كادر جديد: {data.get('name_ar')}")
            return new_id
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()
        
    def update(self, person_id: int, data: dict) -> None:
        if not is_online():
            raise OfflineModeError()
        conn = get_connection()
        try:
            fields = list(data.keys())
            set_clause = ", ".join([f"{f}=%s" for f in fields])
            values = tuple(data[f] for f in fields) + (person_id,)
            cur = conn.cursor()
            cur.execute(f"UPDATE personnel SET {set_clause} WHERE id=%s", values)
            conn.commit()
            log_activity(f"تم تعديل بيانات الكادر ID: {person_id}")
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()


    def toggle_active(self, person_id: int, is_active: int) -> None:
        if not is_online():
            raise OfflineModeError()
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE personnel SET is_active = %s WHERE id = %s", (is_active, person_id))
            conn.commit()
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()
        
    def delete(self, person_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM personnel WHERE id = %s", (person_id,))
            conn.commit()
            log_activity(f"\u062a\u0645 \u062d\u0630\u0641 \u0627\u0644\u0643\u0627\u062f\u0631 ID: {person_id}")
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

# ---------------------------------------------------------------------------
# Module 5: Course Catalog
# ---------------------------------------------------------------------------

class CourseRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT c.*, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en, "
                "       s.name_ar AS study_system_name_ar, s.name_en AS study_system_name_en "
                "FROM courses c "
                "LEFT JOIN departments d ON c.department_id = d.id "
                "LEFT JOIN study_systems s ON c.study_system_id = s.id "
                "ORDER BY c.name_ar ASC"
            )
        return self._call_read_all("GetAllCourses")
        
    def get_by_department(self, dept_id: int) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT c.id, c.name_ar, c.name_en, c.credit_hours, c.study_system_id, c.is_shared "
                "FROM courses c "
                "WHERE c.department_id = ? "
                "   OR (c.is_shared = 1 AND c.id IN (SELECT course_id FROM course_departments WHERE department_id = ?)) "
                "ORDER BY c.name_ar ASC",
                (dept_id, dept_id)
            )
        return self._call_read_all("GetCoursesByDepartment", (dept_id,))

    def get_by_dept_stage_system(self, dept_id: int, stage: int, system_id: int) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT id, name_ar, name_en, credit_hours, stage_number FROM courses "
                "WHERE (department_id = ? OR (is_shared = 1 AND id IN (SELECT course_id FROM course_departments WHERE department_id = ?))) "
                "AND stage_number <= ? AND study_system_id = ? "
                "ORDER BY stage_number, name_ar",
                (dept_id, dept_id, stage, system_id),
            )
        conn = get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT id, name_ar, name_en, credit_hours, stage_number FROM courses "
                "WHERE (department_id = %s OR (is_shared = 1 AND id IN (SELECT course_id FROM course_departments WHERE department_id = %s))) "
                "AND stage_number <= %s AND study_system_id = %s "
                "ORDER BY stage_number, name_ar",
                (dept_id, dept_id, stage, system_id)
            )
            return cur.fetchall()
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

    def get_shared_dept_ids(self, course_id: int) -> list[int]:
        if not is_online():
            rows = sqlite_read_all(
                "SELECT department_id FROM course_departments WHERE course_id = ?",
                (course_id,),
            )
            return [r["department_id"] for r in rows]
        conn = get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT department_id FROM course_departments WHERE course_id = %s", (course_id,))
            rows = cur.fetchall()
            return [r["department_id"] for r in rows]
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

    def insert(self, data: dict) -> int:
        if not is_online():
            raise OfflineModeError()
        shared_ids = data.pop("shared_dept_ids", None)
        
        conn = get_connection()
        try:
            fields = list(data.keys())
            placeholders = ", ".join(["%s"] * len(fields))
            columns = ", ".join(fields)
            values = tuple(data[f] for f in fields)
            cur = conn.cursor()
            cur.execute(f"INSERT INTO courses ({columns}) VALUES ({placeholders})", values)
            conn.commit()
            new_id = cur.lastrowid
            log_activity(f"تم إضافة مادة دراسية جديدة: {data.get('name_ar')}")
            
            if shared_ids:
                cur.execute("UPDATE courses SET is_shared=1 WHERE id=%s", (new_id,))
                for did in shared_ids:
                    cur.execute("INSERT INTO course_departments (course_id, department_id) VALUES (%s, %s)", (new_id, did))
                conn.commit()
                
            return new_id
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

    def update(self, course_id: int, data: dict) -> None:
        if not is_online():
            raise OfflineModeError()
        shared_ids = data.pop("shared_dept_ids", None)
        
        conn = get_connection()
        try:
            fields = list(data.keys())
            set_clause = ", ".join([f"{f}=%s" for f in fields])
            values = tuple(data[f] for f in fields) + (course_id,)
            cur = conn.cursor()
            cur.execute(f"UPDATE courses SET {set_clause} WHERE id=%s", values)
            
            cur.execute("DELETE FROM course_departments WHERE course_id=%s", (course_id,))
            if shared_ids:
                cur.execute("UPDATE courses SET is_shared=1, department_id=NULL WHERE id=%s", (course_id,))
                for did in shared_ids:
                    cur.execute("INSERT INTO course_departments (course_id, department_id) VALUES (%s, %s)", (course_id, did))
            else:
                cur.execute("UPDATE courses SET is_shared=0 WHERE id=%s", (course_id,))
            conn.commit()
            log_activity(f"تم تعديل بيانات المادة الدراسية ID: {course_id}")
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

    def delete(self, course_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM courses WHERE id=%s", (course_id,))
            conn.commit()
            log_activity(f"تم حذف المادة الدراسية ID: {course_id}")
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()


class StudentRepository(BaseRepository):
    def __init__(self, api_url: str = "http://127.0.0.1:8000"):
        super().__init__()
        self.api_url = api_url

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
                                    "postgraduation_number": sdata.get("postgraduation_no")
                                }
                        except Exception as e:
                            print(f"API supplemental fetch failed for {sid}: {e}")
                else:
                    conn = get_local_connection()
                    cursor = conn.cursor()
                    format_strings = ','.join(['?'] * len(student_ids))
                    query = f"SELECT id, sequence_number, postgraduation_no AS postgraduation_number FROM students WHERE id IN ({format_strings})"
                    cursor.execute(query, tuple(student_ids))
                    supp_data = {row["id"]: dict(row) for row in cursor.fetchall()}
                    cursor.close()
                    conn.close()
                
                # Inject back into the original list (set both keys for robust compatibility)
                for s in students_list:
                    sid = s.get("id")
                    if sid in supp_data:
                        s["sequence_number"] = supp_data[sid].get("sequence_number")
                        s["postgraduation_no"] = supp_data[sid].get("postgraduation_number")
                        s["postgraduation_number"] = supp_data[sid].get("postgraduation_number")
                        
            except Exception as e:
                print(f"Supplemental fetch failed: {e}")
                
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
                conditions.append("s.admission_year = ?")
                params.append(str(year))
                
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            params += [limit, offset]
            
            res = sqlite_read_all(
                "SELECT s.id, s.full_name_ar, s.full_name_en, s.admission_year, s.average, s.order_id, "
                "d.name_ar AS dept_name_ar "
                "FROM (SELECT id, full_name_ar, full_name_en, CAST(admission_year AS TEXT) AS admission_year, average, order_id, department_id FROM students "
                "      UNION ALL "
                "      SELECT id, full_name_ar, full_name_en, CAST(admission_year AS TEXT) AS admission_year, average, order_id, department_id FROM local_students) s "
                "LEFT JOIN departments d ON s.department_id = d.id "
                f"{where} ORDER BY s.full_name_ar LIMIT ? OFFSET ?", tuple(params)
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
                else:
                    res = []
            except Exception as e:
                print(f"API request failed: {e}")
                res = []
        return self._inject_missing_graduation_numbers(res)
        
    def get_by_id(self, student_id: int) -> dict | None:
        if not is_online():
            res = sqlite_read_one(
                "SELECT s.*, o.order_number, "
                "COALESCE(s.graduation_date, o.order_date) AS graduation_date, "
                "COALESCE(s.graduation_semester, o.graduation_semester) AS graduation_semester, "
                "d.name_ar AS dept_name_ar, ss.name_ar AS study_system_name_ar, "
                "c.name_ar AS nationality_ar, g.name_ar AS birthplace_ar "
                "FROM (SELECT id, full_name_ar, full_name_en, gender, sequence_number, postgraduation_no, date_of_birth, "
                "             birthplace_id, birthplace_other, nationality_id, department_id, study_system_id, degree_level, "
                "             order_id, CAST(admission_year AS TEXT) AS admission_year, summer_training_data, average, graduation_date, graduation_semester "
                "      FROM students "
                "      UNION ALL "
                "      SELECT id, full_name_ar, full_name_en, gender, sequence_number, postgraduation_no, date_of_birth, "
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
                print(f"API request failed: {e}")
                res = None
        if res:
            res = self._inject_missing_graduation_numbers([res])[0]
        return res
 
    def search(self, query: str, limit: int = 8) -> list[dict]:
        if not is_online():
            pattern = f"%{query.strip()}%"
            res = sqlite_read_all(
                "SELECT s.id, s.full_name_ar, s.full_name_en, s.admission_year, s.average, "
                "d.name_ar AS dept_name_ar "
                "FROM (SELECT id, full_name_ar, full_name_en, CAST(admission_year AS TEXT) AS admission_year, average, department_id FROM students "
                "      UNION ALL "
                "      SELECT id, full_name_ar, full_name_en, CAST(admission_year AS TEXT) AS admission_year, average, department_id FROM local_students) s "
                "LEFT JOIN departments d ON s.department_id = d.id "
                "WHERE s.full_name_ar LIKE ? OR s.full_name_en LIKE ? "
                "ORDER BY s.full_name_ar LIMIT ?", (pattern, pattern, limit)
            )
        else:
            try:
                resp = requests.get(
                    f"{self.api_url}/students/search/all",
                    params={"query": query, "limit": limit},
                    timeout=5.0
                )
                if resp.status_code == 200:
                    res = resp.json()
                else:
                    res = []
            except Exception as e:
                print(f"API request failed: {e}")
                res = []
        return self._inject_missing_graduation_numbers(res)
        
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
                conditions.append("s.admission_year = ?")
                params.append(str(year))
                
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            row = sqlite_read_one(
                "SELECT COUNT(*) as total_count FROM ("
                "  SELECT id, full_name_ar, full_name_en, department_id, CAST(admission_year AS TEXT) AS admission_year FROM students "
                "  UNION ALL "
                "  SELECT id, full_name_ar, full_name_en, department_id, CAST(admission_year AS TEXT) AS admission_year FROM local_students"
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
            print(f"API request failed: {e}")
            row = {"total_count": 0}
        return row['total_count'] if row else 0
 
    def get_by_order(self, order_id: int) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT id, full_name_ar, average, order_id FROM students WHERE order_id = ? "
                "UNION ALL "
                "SELECT id, full_name_ar, average, order_id FROM local_students WHERE order_id = ? "
                "ORDER BY average DESC",
                (order_id, order_id)
            )
        try:
            resp = requests.get(f"{self.api_url}/students/by-order/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            print(f"API request failed: {e}")
            return []
 
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
            print(f"API request failed: {e}")
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
            print(f"API request failed: {e}")
            raise
 
    def search_for_order(self, name_query: str = "", admission_year: str | int | None = None, department_id: int = None, limit: int = 50, offset: int = 0) -> list[dict]:
        """Legacy wrapper for OrderStudentsScreen mapping to the new paginated SP."""
        return self.get_all_paginated(limit=limit, offset=offset, name_query=name_query, dept_id=department_id, year=admission_year)
 
    def get_distinct_admission_years(self) -> list[str]:
        if not is_online():
            rows = sqlite_read_all(
                "SELECT DISTINCT admission_year FROM students "
                "UNION "
                "SELECT DISTINCT admission_year FROM local_students "
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
            print(f"API request failed: {e}")
            return []
 
    def insert(self, data: dict) -> int:
        if not is_online():
            # Route to offline sync engine
            return log_offline_insert("students", dict(data))
        try:
            payload = {
                "full_name_ar": data.get('full_name_ar'),
                "full_name_en": data.get('full_name_en'),
                "gender": data.get('gender', 'M'),
                "sequence_number": data.get('sequence_number'),
                "postgraduation_no": data.get('postgraduation_no'),
                "date_of_birth": str(data.get('date_of_birth')) if data.get('date_of_birth') else None,
                "birthplace_id": data.get('birthplace_id'),
                "birthplace_other": data.get('birthplace_other'),
                "nationality_id": data.get('nationality_id', 1),
                "department_id": data.get('department_id'),
                "study_system_id": data.get('study_system_id'),
                "degree_level": data.get('degree_level', 'Bachelor'),
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
            print(f"API request failed: {e}")
            raise
        
    def update(self, student_id: int, data: dict) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            payload = {
                "full_name_ar": data.get('full_name_ar'),
                "full_name_en": data.get('full_name_en'),
                "gender": data.get('gender', 'M'),
                "sequence_number": data.get('sequence_number'),
                "postgraduation_no": data.get('postgraduation_no'),
                "date_of_birth": str(data.get('date_of_birth')) if data.get('date_of_birth') else None,
                "birthplace_id": data.get('birthplace_id'),
                "birthplace_other": data.get('birthplace_other'),
                "nationality_id": data.get('nationality_id', 1),
                "department_id": data.get('department_id'),
                "study_system_id": data.get('study_system_id'),
                "degree_level": data.get('degree_level', 'Bachelor'),
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
            print(f"API request failed: {e}")
            raise
 
    def delete(self, student_id: int) -> None:
        self._call_write("DeleteStudent", (student_id,))
        log_activity(f"تم حذف الطالب ID: {student_id}")

# ---------------------------------------------------------------------------
# Module 7: Timelines & Enrollments
# ---------------------------------------------------------------------------

class AcademicPeriodRepository(BaseRepository):
    def get_by_student(self, student_id: int) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT id, student_id, academic_year, study_system_id, stage_number, semester_num FROM ("
                "  SELECT id, student_id, academic_year, study_system_id, stage_number, semester_num FROM academic_periods "
                "  UNION ALL "
                "  SELECT id, student_id, academic_year, study_system_id, stage_number, semester_num FROM local_academic_periods"
                ") WHERE student_id = ? ORDER BY stage_number",
                (student_id,)
            )
        return self._call_read_all("GetAcademicPeriodsByStudent", (student_id,))

    def insert(self, student_id: int, year: str, sys_id: int, stage: int, semester_num: int = 1) -> int:
        if not is_online():
            return log_offline_insert("academic_periods", {
                "student_id": student_id,
                "academic_year": year,
                "study_system_id": sys_id,
                "stage_number": stage,
                "semester_num": semester_num,
            })
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO academic_periods (student_id, academic_year, study_system_id, stage_number, semester_num) "
                "VALUES (%s, %s, %s, %s, %s)", (student_id, year, sys_id, stage, semester_num)
            )
            conn.commit()
            return cur.lastrowid
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

            
    def delete(self, period_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM academic_periods WHERE id=%s", (period_id,))
            conn.commit()
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

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
        return self._call_read_all("GetEnrollmentsByPeriod", (period_id,))


    def insert(self, period_id: int, course_id: int, score: float, is_second: int) -> int:
        if not is_online():
            passed_round = '2' if is_second else '1'
            return log_offline_insert("enrollments", {
                "period_id": period_id,
                "course_id": course_id,
                "score": score,
                "passed_round": passed_round,
            })
        passed_round = '2' if is_second else '1'
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO enrollments (period_id, course_id, score, passed_round) VALUES (%s, %s, %s, %s)",
                (period_id, course_id, score, passed_round)
            )
            conn.commit()
            return cur.lastrowid
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

    def update(self, enrollment_id: int, score: float, is_second: int) -> None:
        if not is_online():
            raise OfflineModeError()
        passed_round = '2' if is_second else '1'
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE enrollments SET score=%s, passed_round=%s WHERE id=%s",
                (score, passed_round, enrollment_id)
            )
            conn.commit()
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

    def delete(self, enrollment_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM enrollments WHERE id=%s", (enrollment_id,))
            conn.commit()
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

# ---------------------------------------------------------------------------
# Module 8: Integrated Report Engine Pipeline
# ---------------------------------------------------------------------------
class CertificateRepository(BaseRepository):
    
    def get_full_certificate_data(self, student_id: int) -> dict | None:
        if not is_online():
            student = sqlite_read_one(
                "SELECT s.*, "
                "       d.name_ar AS dept_name_ar, d.name_en AS dept_name_en, "
                "       ss.name_ar AS study_system_name_ar, ss.name_en AS study_system_name_en, "
                "       ss.calculation_rule, ss.calculation_weights, ss.period_display, "
                "       c.name_ar AS nationality_ar, c.name_en AS nationality_en, "
                "       g.name_ar AS birthplace_ar, g.name_en AS birthplace_en, "
                "       o.order_number, o.order_date "
                "FROM ("
                "  SELECT id, full_name_ar, full_name_en, gender, sequence_number, postgraduation_no, date_of_birth, "
                "         birthplace_id, birthplace_other, nationality_id, department_id, study_system_id, degree_level, "
                "         order_id, CAST(admission_year AS TEXT) AS admission_year, summer_training_data, average, graduation_date, graduation_semester "
                "  FROM students "
                "  UNION ALL "
                "  SELECT id, full_name_ar, full_name_en, gender, sequence_number, postgraduation_no, date_of_birth, "
                "         birthplace_id, birthplace_other, nationality_id, department_id, study_system_id, degree_level, "
                "         order_id, CAST(admission_year AS TEXT) AS admission_year, summer_training_data, average, graduation_date, graduation_semester "
                "  FROM local_students"
                ") s "
                "LEFT JOIN departments d    ON s.department_id   = d.id "
                "LEFT JOIN study_systems ss ON s.study_system_id = ss.id "
                "LEFT JOIN countries c      ON s.nationality_id  = c.id "
                "LEFT JOIN governorates g   ON s.birthplace_id   = g.id "
                "LEFT JOIN graduation_orders o ON s.order_id = o.id "
                "WHERE s.id = ?",
                (student_id,)
            )
            if not student:
                return None
            
            data = student
            
            # Class Rank
            rank_row = sqlite_read_one(
                "SELECT COUNT(*) + 1 as rank FROM students "
                "WHERE department_id = ? AND admission_year = ? AND average > ? AND average IS NOT NULL",
                (data.get("department_id"), data.get("admission_year"), data.get("average", 0) or 0)
            )
            # Total Graduates
            total_row = sqlite_read_one(
                "SELECT COUNT(*) as total FROM students "
                "WHERE department_id = ? AND admission_year = ? AND average IS NOT NULL",
                (data.get("department_id"), data.get("admission_year"))
            )
            data["rank"] = data.get("sequence_number") or (rank_row["rank"] if rank_row else 1)
            data["total_graduates"] = data.get("postgraduation_no") or (total_row["total"] if total_row else 1)
            
            # Top Average
            top_row = sqlite_read_one(
                "SELECT MAX(average) as top_avg FROM students "
                "WHERE department_id = ? AND admission_year = ?",
                (data.get("department_id"), data.get("admission_year"))
            )
            data["top_average"] = top_row["top_avg"] if top_row else None
            
            # Fetch Academic Periods and Enrollments
            periods = sqlite_read_all(
                "SELECT id, student_id, academic_year, study_system_id, stage_number FROM ("
                "  SELECT id, student_id, academic_year, study_system_id, stage_number FROM academic_periods "
                "  UNION ALL "
                "  SELECT id, student_id, academic_year, study_system_id, stage_number FROM local_academic_periods"
                ") WHERE student_id = ? ORDER BY stage_number",
                (student_id,)
            )
            data["periods"] = []
            for p in periods:
                enrollments = sqlite_read_all(
                    "SELECT e.score, "
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
                    (p["id"],)
                )
                p["enrollments"] = enrollments
                data["periods"].append(p)
                
            # Signatories
            data["front_signatories"] = sqlite_read_all(
                "SELECT * FROM personnel WHERE is_active = 1 AND display_order BETWEEN 1 AND 4 ORDER BY display_order"
            )
            data["back_signatories"] = sqlite_read_all(
                "SELECT * FROM personnel WHERE is_active = 1 AND display_order >= 5 ORDER BY display_order"
            )
            
            # Settings
            settings = sqlite_read_one("SELECT * FROM university_settings WHERE id = 1")
            if settings:
                data["univ_name_ar"] = settings.get("univ_name_ar")
                data["univ_name_en"] = settings.get("univ_name_en")
                data["college_name_ar"] = settings.get("college_name_ar")
                data["college_name_en"] = settings.get("college_name_en")
                
            # Postgraduate isolation
            data["thesis"] = None
            data["supervisors"] = []
            degree_level = data.get("degree_level", "Bachelor")
            if degree_level in ["Master", "PhD"]:
                try:
                    data["thesis"] = sqlite_read_all("SELECT * FROM thesis_records WHERE student_id = ?", (student_id,))
                except Exception:
                    data["thesis"] = []
                try:
                    data["supervisors"] = sqlite_read_all(
                        "SELECT ss.*, p.name_ar as personnel_name_ar, p.name_en as personnel_name_en "
                        "FROM student_supervisors ss "
                        "JOIN personnel p ON ss.personnel_id = p.id "
                        "WHERE ss.student_id = ?",
                        (student_id,)
                    )
                except Exception:
                    data["supervisors"] = []
            return data

        rowsets = self._call_read_multi("GetFullCertificateData", (student_id,))
        
        if not rowsets or not rowsets[0]:
            return None
            
        data = rowsets[0][0]
        
        if len(rowsets) > 1 and rowsets[1]:
            analytics = rowsets[1][0]
            data["rank"] = data.get("sequence_number") or analytics.get("class_rank", 1)
            data["total_graduates"] = data.get("postgraduation_no") or analytics.get("total_graduates", 1)
            data["top_average"] = analytics.get("top_average")
            
        data["periods"] = []
        if len(rowsets) > 3:
            periods = rowsets[2]
            enrollments = rowsets[3]
            for p in periods:
                p["enrollments"] = [e for e in enrollments if e["period_id"] == p["id"]]
                data["periods"].append(p)
                
        if len(rowsets) > 4: data["front_signatories"] = rowsets[4]
        if len(rowsets) > 5: data["back_signatories"] = rowsets[5]
            
        if len(rowsets) > 6 and rowsets[6]:
            settings = rowsets[6][0]
            data["univ_name_ar"] = settings.get("univ_name_ar")
            data["univ_name_en"] = settings.get("univ_name_en")
            data["college_name_ar"] = settings.get("college_name_ar")
            data["college_name_en"] = settings.get("college_name_en")

        # POSTGRADUATE ISOLATION BLOCK
        data["thesis"] = None
        data["supervisors"] = []
        
        degree_level = data.get("degree_level", "Bachelor")
        if degree_level in ["Master", "PhD"]:
            thesis_repo = ThesisRepository()
            supervisor_repo = StudentSupervisorRepository()
            
            thesis_records = thesis_repo.get_by_student(student_id)
            if thesis_records:
                data["thesis"] = thesis_records
                
            data["supervisors"] = supervisor_repo.get_by_student(student_id)
            
        return data

# ---------------------------------------------------------------------------
# Module 9: Graduation Orders
# ---------------------------------------------------------------------------

class GraduationOrderRepository(BaseRepository):
    
    def get_all(self) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT o.*, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en, "
                "(SELECT COUNT(*) FROM students s WHERE s.order_id = o.id) AS linked_count "
                "FROM graduation_orders o "
                "LEFT JOIN departments d ON o.department_id = d.id "
                "ORDER BY o.order_date DESC, o.id DESC"
            )
        return self._call_read_all("GetAllGraduationOrders")

    def get_by_id(self, order_id: int) -> dict | None:
        if not is_online():
            return sqlite_read_one(
                "SELECT o.*, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en "
                "FROM graduation_orders o "
                "LEFT JOIN departments d ON o.department_id = d.id "
                "WHERE o.id = ?",
                (order_id,)
            )
        return self._call_read_one("GetGraduationOrderByID", (order_id,))

    def insert(self, data: dict) -> int:
        args = (
            data.get('order_number'),
            data.get('order_date'),
            data.get('department_id'),
            data.get('study_type'),
            data.get('admission_year'),
            data.get('graduation_semester'),
            data.get('num_students'),
            data.get('notes'),
            data.get('study_system_id', 1)
        )
        new_id = self._call_write("InsertGraduationOrder", args)
        log_activity(f"تم إضافة أمر جامعي جديد: {data.get('order_number')}")
        return new_id

    def update(self, order_id: int, data: dict) -> None:
        args = (
            order_id,
            data.get('order_number'),
            data.get('order_date'),
            data.get('department_id'),
            data.get('study_type'),
            data.get('admission_year'),
            data.get('graduation_semester'),
            data.get('num_students'),
            data.get('notes'),
            data.get('study_system_id', 1)
        )
        self._call_write("UpdateGraduationOrder", args)
        log_activity(f"تم تعديل بيانات الأمر الجامعي: {data.get('order_number')}")

    def delete(self, order_id: int) -> None:
        self._call_write("DeleteGraduationOrder", (order_id,))
        log_activity(f"تم حذف الأمر الجامعي ID: {order_id}")

    def get_students_for_order(self, order_id: int) -> list[dict]:
        if not is_online():
            return sqlite_read_all(
                "SELECT s.id, s.full_name_ar, s.full_name_en, s.admission_year, s.average, s.order_id, "
                "d.name_ar AS dept_name_ar "
                "FROM (SELECT * FROM students UNION ALL SELECT * FROM local_students) s "
                "LEFT JOIN departments d ON s.department_id = d.id "
                "WHERE s.order_id = ?",
                (order_id,)
            )
        return self._call_read_all("GetStudentsByOrder", (order_id,))

    def link_students(self, order_id: int) -> int:
        row = self._call_read_one("LinkStudentsToOrder", (order_id,))
        count = row['affected_rows'] if row and 'affected_rows' in row else 0
        if count > 0:
            log_activity(f"تم ربط {count} طالب بالأمر الجامعي ID: {order_id}")
        return count

    def unlink_student(self, student_id: int) -> None:
        self._call_write("UnlinkStudentFromOrder", (student_id,))
        log_activity(f"تم فك ارتباط الطالب ID: {student_id} بالأمر الجامعي")

# ---------------------------------------------------------------------------
# Module 10: Thesis Records
# ---------------------------------------------------------------------------
class ThesisRepository(BaseRepository):
    def get_by_student(self, student_id: int) -> list[dict]:
        return self._call_read_all("GetThesisByStudent", (student_id,))

    def insert(self, student_id: int, title_ar: str, title_en: str, defense_date: str = None, committee_decision: str = None, final_grade: float = None) -> int:
        args = (student_id, title_ar, title_en, defense_date, committee_decision, final_grade)
        new_id = self._call_write("InsertThesis", args)
        log_activity(f"تم إضافة سجل أطروحة للطالب ID: {student_id}")
        return new_id

    def update(self, thesis_id: int, title_ar: str, title_en: str, defense_date: str = None, committee_decision: str = None, final_grade: float = None) -> None:
        args = (thesis_id, title_ar, title_en, defense_date, committee_decision, final_grade)
        self._call_write("UpdateThesis", args)
        log_activity(f"تم تعديل سجل الأطروحة ID: {thesis_id}")

    def delete(self, thesis_id: int) -> None:
        self._call_write("DeleteThesis", (thesis_id,))
        log_activity(f"تم حذف سجل الأطروحة ID: {thesis_id}")

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
        return self._call_read_all("GetSupervisorsByStudent", (student_id,))

    def insert(self, student_id: int, personnel_id: int, supervision_role: str) -> int:
        new_id = self._call_write("InsertStudentSupervisor", (student_id, personnel_id, supervision_role))
        log_activity(f"تم إضافة مشرف جديد للطالب ID: {student_id}")
        return new_id

    def update(self, record_id: int, personnel_id: int, supervision_role: str) -> None:
        self._call_write("UpdateStudentSupervisor", (record_id, personnel_id, supervision_role))
        log_activity(f"تم تعديل بيانات الإشراف ID: {record_id}")

    def delete(self, record_id: int) -> None:
        self._call_write("DeleteStudentSupervisor", (record_id,))
        log_activity(f"تم حذف سجل الإشراف ID: {record_id}")

# ---------------------------------------------------------------------------
# Compatibility wrapper for students_screen.py
# ---------------------------------------------------------------------------
class SupervisorRepository(BaseRepository):
    def get_by_student(self, student_id: int) -> list[dict]:
        return StudentSupervisorRepository().get_by_student(student_id)

    def add(self, student_id: int, personnel_id: int, role: str) -> None:
        StudentSupervisorRepository().insert(student_id, personnel_id, role)

    def delete_by_student(self, student_id: int) -> None:
        records = self.get_by_student(student_id)
        for r in records:
            if 'id' in r:
                StudentSupervisorRepository().delete(r['id'])

# ---------------------------------------------------------------------------
# Audit Logs (Fallback)
# ---------------------------------------------------------------------------
class AuditRepository(BaseRepository):
    def _read_activity_logs(self) -> list[dict]:
        log_path = "activity_log.txt"
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
            with open("activity_log.txt", "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass

