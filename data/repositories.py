# =============================================================================
# data/repositories.py — Data Access Layer (MySQL + OOP)
# =============================================================================

import logging
from db import get_connection

activity_logger = logging.getLogger("activity")

def log_activity(summary: str) -> None:
    activity_logger.info(summary)


class BaseRepository:
    """Base repository with shared utilities for MySQL execution."""
    
    def __init__(self):
        # We don't hold a persistent connection; we fetch one per operation 
        # to avoid timeouts and thread issues.
        pass
        
    def _execute(self, query: str, params: tuple = None, commit: bool = False):
        """Execute a query that does not return rows (INSERT, UPDATE, DELETE)."""
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, params or ())
            if commit:
                conn.commit()
                return cur.lastrowid
            return cur.rowcount
        finally:
            if 'cur' in locals():
                cur.close()
            conn.close()

    def _fetch_all(self, query: str, params: tuple = None) -> list[dict]:
        """Execute a SELECT query and return a list of dictionaries."""
        conn = get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute(query, params or ())
            return cur.fetchall()
        finally:
            if 'cur' in locals():
                cur.close()
            conn.close()

    def _fetch_one(self, query: str, params: tuple = None) -> dict | None:
        """Execute a SELECT query and return a single dictionary or None."""
        conn = get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute(query, params or ())
            return cur.fetchone()
        finally:
            if 'cur' in locals():
                cur.close()
            conn.close()

    def _fetch_scalar(self, query: str, params: tuple = None):
        """Execute a SELECT query and return a single scalar value."""
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, params or ())
            row = cur.fetchone()
            return row[0] if row else None
        finally:
            if 'cur' in locals():
                cur.close()
            conn.close()

    def count_table_rows(self, table: str, filter_clause: str = "") -> int:
        """Count rows in a table securely."""
        # Simple validation for table name
        allowed_tables = [
            "students", "departments", "courses", "personnel", 
            "graduation_orders", "study_systems"
        ]
        if table not in allowed_tables:
            return 0
        query = f"SELECT COUNT(*) FROM {table} {filter_clause}"
        return self._fetch_scalar(query) or 0

# ---------------------------------------------------------------------------
# Settings Repository
# ---------------------------------------------------------------------------

class SettingsRepository(BaseRepository):
    def get_settings(self) -> dict:
        return self._fetch_one("SELECT * FROM settings WHERE id = 1") or {}

    def update_settings(self, univ_ar: str, univ_en: str, college_ar: str, college_en: str) -> None:
        self._execute(
            "UPDATE settings SET univ_name_ar=%s, univ_name_en=%s, college_name_ar=%s, college_name_en=%s WHERE id=1",
            (univ_ar, univ_en, college_ar, college_en), commit=True
        )
        log_activity("تم تحديث إعدادات النظام")

    def get_user_appearance(self, user_id: int) -> dict:
        row = self._fetch_one("SELECT * FROM user_preferences WHERE user_id = %s", (user_id,))
        if not row:
            return {"theme": "System", "accent_color": "blue", "font_family": "Arial", "font_size_base": 13}
        return row

    def update_user_appearance(self, user_id: int, theme: str, accent: str, font: str, size: int) -> None:
        # MySQL equivalent for UPSERT
        query = """
            INSERT INTO user_preferences (user_id, theme, accent_color, font_family, font_size_base)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                theme=VALUES(theme), accent_color=VALUES(accent_color), 
                font_family=VALUES(font_family), font_size_base=VALUES(font_size_base)
        """
        self._execute(query, (user_id, theme, accent, font, size), commit=True)
        log_activity(f"تم تحديث المظهر للمستخدم ID: {user_id}")

    def clear_audit_logs(self) -> None:
        self._execute("DELETE FROM audit_log", commit=True)
        log_activity("تم مسح سجل التغييرات بالكامل")


# ---------------------------------------------------------------------------
# Lookups Repositories (Countries, Governorates)
# ---------------------------------------------------------------------------

class CountryRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        return self._fetch_all("SELECT id, name_ar, name_en, iso_code FROM countries ORDER BY name_en")

class GovernorateRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        return self._fetch_all("SELECT id, name_ar, name_en FROM governorates ORDER BY id")

class DepartmentRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        return self._fetch_all("SELECT id, name_ar, name_en, college_ar, college_en, study_years FROM departments ORDER BY name_ar")
        
    def get_by_id(self, dept_id: int) -> dict | None:
        return self._fetch_one("SELECT * FROM departments WHERE id = %s", (dept_id,))

    def insert(self, name_ar: str, name_en: str, study_years: int) -> int:
        new_id = self._execute("INSERT INTO departments (name_ar, name_en, study_years) VALUES (%s, %s, %s)", (name_ar, name_en, study_years), commit=True)
        log_activity(f"تم إضافة قسم جديد: {name_ar}")
        return new_id

    def update(self, dept_id: int, name_ar: str, name_en: str, study_years: int) -> None:
        self._execute("UPDATE departments SET name_ar=%s, name_en=%s, study_years=%s WHERE id=%s", (name_ar, name_en, study_years, dept_id), commit=True)
        log_activity(f"تم تعديل القسم: {name_ar}")

    def delete(self, dept_id: int) -> None:
        self._execute("DELETE FROM departments WHERE id=%s", (dept_id,), commit=True)
        log_activity(f"تم حذف القسم ID: {dept_id}")

# ---------------------------------------------------------------------------
# Core Repositories
# ---------------------------------------------------------------------------

class StudySystemRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        return self._fetch_all(
            "SELECT id, name_ar, name_en, calculation_rule, calculation_weights, "
            "period_display, is_active, created_at "
            "FROM study_systems ORDER BY id"
        )
        
    def get_active(self) -> list[dict]:
        return self._fetch_all(
            "SELECT id, name_ar, name_en, calculation_rule, calculation_weights, "
            "period_display "
            "FROM study_systems WHERE is_active = 1 ORDER BY id"
        )
        
    def get_by_id(self, system_id: int) -> dict | None:
        return self._fetch_one("SELECT * FROM study_systems WHERE id = %s", (system_id,))

    def insert(self, name_ar: str, name_en: str, calc_rule: str, period_display: str = 'year', calculation_weights: str = None) -> int:
        new_id = self._execute(
            "INSERT INTO study_systems (name_ar, name_en, calculation_rule, period_display, calculation_weights) "
            "VALUES (%s, %s, %s, %s, %s)",
            (name_ar, name_en, calc_rule, period_display, calculation_weights), commit=True
        )
        log_activity(f"تم إضافة نظام دراسي جديد: {name_ar}")
        return new_id

    def update(self, sys_id: int, name_ar: str, name_en: str, calc_rule: str, period_display: str = 'year', calculation_weights: str = None, **_ignored) -> None:
        self._execute(
            "UPDATE study_systems SET name_ar=%s, name_en=%s, calculation_rule=%s, period_display=%s, calculation_weights=%s WHERE id=%s",
            (name_ar, name_en, calc_rule, period_display, calculation_weights, sys_id), commit=True
        )
        log_activity(f"تم تعديل النظام الدراسي: {name_ar}")

    def toggle(self, sys_id: int, new_status: int) -> None:
        self._execute("UPDATE study_systems SET is_active = %s WHERE id = %s", (new_status, sys_id), commit=True)

    def delete(self, sys_id: int) -> None:
        self._execute("DELETE FROM study_systems WHERE id = %s", (sys_id,), commit=True)
        log_activity(f"تم حذف النظام الدراسي ID: {sys_id}")

class PersonnelRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        return self._fetch_all("SELECT * FROM personnel ORDER BY display_order, name_ar")
        
    def get_active(self) -> list[dict]:
        return self._fetch_all("SELECT * FROM personnel WHERE is_active = 1 ORDER BY display_order, name_ar")

    def authenticate(self, username: str, password: str) -> dict | None:
        user = self._fetch_one("SELECT * FROM personnel WHERE username = %s AND is_active = 1", (username,))
        if user and user.get("password") == password:
            return user
        return None
        
    def insert(self, data: dict) -> int:
        fields = list(data.keys())
        placeholders = ", ".join(["%s"] * len(fields))
        columns = ", ".join(fields)
        values = tuple(data[f] for f in fields)
        new_id = self._execute(f"INSERT INTO personnel ({columns}) VALUES ({placeholders})", values, commit=True)
        log_activity(f"تم إضافة كادر جديد: {data.get('name_ar')}")
        return new_id
        
    def update(self, person_id: int, data: dict) -> None:
        fields = list(data.keys())
        set_clause = ", ".join([f"{f}=%s" for f in fields])
        values = tuple(data[f] for f in fields) + (person_id,)
        self._execute(f"UPDATE personnel SET {set_clause} WHERE id=%s", values, commit=True)
        log_activity(f"تم تعديل بيانات الكادر ID: {person_id}")

    def toggle_active(self, person_id: int, is_active: int) -> None:
        self._execute("UPDATE personnel SET is_active = %s WHERE id = %s", (is_active, person_id), commit=True)
        
    def delete(self, person_id: int) -> None:
        self._execute("DELETE FROM personnel WHERE id = %s", (person_id,), commit=True)
        log_activity(f"تم حذف الكادر ID: {person_id}")

class CourseRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        return self._fetch_all(
            "SELECT c.*, "
            "       IF(c.is_shared, "
            "          (SELECT GROUP_CONCAT(d2.name_ar SEPARATOR '، ') "
            "           FROM course_departments cd "
            "           JOIN departments d2 ON cd.department_id = d2.id "
            "           WHERE cd.course_id = c.id), "
            "          d.name_ar) AS dept_name_ar, "
            "       ss.name_ar AS study_system_name_ar "
            "FROM courses c "
            "LEFT JOIN departments d ON c.department_id = d.id "
            "LEFT JOIN study_systems ss ON c.study_system_id = ss.id "
            "ORDER BY c.name_ar"
        )
        
    def get_by_department(self, dept_id: int) -> list[dict]:
        return self._fetch_all("SELECT * FROM courses WHERE department_id = %s ORDER BY name_ar", (dept_id,))

    def get_by_dept_stage_system(self, dept_id: int, stage: int, system_id: int) -> list[dict]:
        return self._fetch_all(
            "SELECT id, name_ar, name_en, credit_hours FROM courses "
            "WHERE department_id=%s AND stage_number=%s AND study_system_id=%s ORDER BY name_ar",
            (dept_id, stage, system_id)
        )

    def get_shared_dept_ids(self, course_id: int) -> list[int]:
        rows = self._fetch_all("SELECT department_id FROM course_departments WHERE course_id = %s", (course_id,))
        return [r["department_id"] for r in rows]

    def insert(self, data: dict) -> int:
        shared_ids = data.pop("shared_dept_ids", None)
        
        fields = list(data.keys())
        placeholders = ", ".join(["%s"] * len(fields))
        columns = ", ".join(fields)
        values = tuple(data[f] for f in fields)
        new_id = self._execute(f"INSERT INTO courses ({columns}) VALUES ({placeholders})", values, commit=True)
        log_activity(f"تم إضافة مادة دراسية جديدة: {data.get('name_ar')}")
        
        if shared_ids:
            self._execute("UPDATE courses SET is_shared=1 WHERE id=%s", (new_id,), commit=True)
            for did in shared_ids:
                self._execute("INSERT INTO course_departments (course_id, department_id) VALUES (%s, %s)", (new_id, did), commit=True)
                
        return new_id

    def update(self, course_id: int, data: dict) -> None:
        shared_ids = data.pop("shared_dept_ids", None)
        
        fields = list(data.keys())
        set_clause = ", ".join([f"{f}=%s" for f in fields])
        values = tuple(data[f] for f in fields) + (course_id,)
        self._execute(f"UPDATE courses SET {set_clause} WHERE id=%s", values, commit=True)
        log_activity(f"تم تعديل بيانات المادة الدراسية ID: {course_id}")
        
        self._execute("DELETE FROM course_departments WHERE course_id=%s", (course_id,), commit=True)
        if shared_ids:
            self._execute("UPDATE courses SET is_shared=1, department_id=NULL WHERE id=%s", (course_id,), commit=True)
            for did in shared_ids:
                self._execute("INSERT INTO course_departments (course_id, department_id) VALUES (%s, %s)", (course_id, did), commit=True)
        else:
            self._execute("UPDATE courses SET is_shared=0 WHERE id=%s", (course_id,), commit=True)

    def delete(self, course_id: int) -> None:
        self._execute("DELETE FROM courses WHERE id=%s", (course_id,), commit=True)
        log_activity(f"تم حذف المادة الدراسية ID: {course_id}")

class ThesisRepository(BaseRepository):
    def get_by_student(self, student_id: int) -> dict | None:
        return self._fetch_one("SELECT * FROM thesis_records WHERE student_id = %s", (student_id,))

    def save(self, student_id: int, title_ar: str, title_en: str, defense_date: str, committee_decision: str, final_grade: float) -> None:
        query = """
            INSERT INTO thesis_records (student_id, title_ar, title_en, defense_date, committee_decision, final_grade)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                title_ar=VALUES(title_ar), title_en=VALUES(title_en),
                defense_date=VALUES(defense_date), committee_decision=VALUES(committee_decision),
                final_grade=VALUES(final_grade)
        """
        self._execute(query, (student_id, title_ar, title_en, defense_date, committee_decision, final_grade), commit=True)

class SupervisorRepository(BaseRepository):
    def get_by_student(self, student_id: int) -> list[dict]:
        return self._fetch_all(
            "SELECT ss.*, p.name_ar as personnel_name_ar, p.name_en as personnel_name_en "
            "FROM student_supervisors ss "
            "JOIN personnel p ON ss.personnel_id = p.id "
            "WHERE ss.student_id = %s", (student_id,)
        )
        
    def add(self, student_id: int, personnel_id: int, role: str) -> None:
        self._execute(
            "INSERT INTO student_supervisors (student_id, personnel_id, supervision_role) VALUES (%s, %s, %s)",
            (student_id, personnel_id, role), commit=True
        )

    def remove(self, record_id: int) -> None:
        self._execute("DELETE FROM student_supervisors WHERE id = %s", (record_id,), commit=True)
        
    def delete_by_student(self, student_id: int) -> None:
        self._execute("DELETE FROM student_supervisors WHERE student_id = %s", (student_id,), commit=True)

class GraduationOrderRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        return self._fetch_all(
            "SELECT o.*, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en, "
            "(SELECT COUNT(*) FROM students s WHERE s.order_id = o.id) AS linked_count "
            "FROM graduation_orders o "
            "JOIN departments d ON o.department_id = d.id "
            "ORDER BY o.order_date DESC, o.id DESC"
        )
        
    def get_by_id(self, order_id: int) -> dict | None:
        return self._fetch_one(
            "SELECT o.*, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en "
            "FROM graduation_orders o "
            "JOIN departments d ON o.department_id = d.id "
            "WHERE o.id = %s", (order_id,)
        )

    def insert(self, data: dict) -> int:
        fields = list(data.keys())
        placeholders = ", ".join(["%s"] * len(fields))
        columns = ", ".join(fields)
        values = tuple(data[f] for f in fields)
        new_id = self._execute(f"INSERT INTO graduation_orders ({columns}) VALUES ({placeholders})", values, commit=True)
        log_activity(f"تم إضافة أمر تخرج جديد: {data.get('order_number')}")
        return new_id

    def update(self, order_id: int, data: dict) -> None:
        fields = list(data.keys())
        set_clause = ", ".join([f"{f}=%s" for f in fields])
        values = tuple(data[f] for f in fields) + (order_id,)
        self._execute(f"UPDATE graduation_orders SET {set_clause} WHERE id=%s", values, commit=True)
        log_activity(f"تم تعديل أمر التخرج ID: {order_id}")

    def delete(self, order_id: int) -> None:
        self._execute("UPDATE students SET order_id = NULL WHERE order_id = %s", (order_id,), commit=True)
        self._execute("DELETE FROM graduation_orders WHERE id = %s", (order_id,), commit=True)
        log_activity(f"تم حذف أمر التخرج ID: {order_id}")

class AcademicPeriodRepository(BaseRepository):
    def get_by_student(self, student_id: int) -> list[dict]:
        return self._fetch_all(
            "SELECT id, student_id, academic_year, study_system_id, stage_number "
            "FROM academic_periods WHERE student_id = %s ORDER BY stage_number", (student_id,)
        )
        
    def insert(self, student_id: int, year: str, sys_id: int, stage: int, round_val: str = None) -> int:
        new_id = self._execute(
            "INSERT INTO academic_periods (student_id, academic_year, study_system_id, stage_number) "
            "VALUES (%s, %s, %s, %s)", (student_id, year, sys_id, stage), commit=True
        )
        return new_id
        
    def update(self, period_id: int, year: str, round_val: str = None) -> None:
        self._execute(
            "UPDATE academic_periods SET academic_year=%s WHERE id=%s",
            (year, period_id), commit=True
        )
        
    def delete(self, period_id: int) -> None:
        self._execute("DELETE FROM academic_periods WHERE id=%s", (period_id,), commit=True)

class EnrollmentRepository(BaseRepository):
    def get_by_period(self, period_id: int) -> list[dict]:
        return self._fetch_all(
            "SELECT e.id, e.period_id, e.course_id, e.score, e.is_second_round, "
            "c.name_ar AS course_name_ar, c.name_en AS course_name_en, c.credit_hours "
            "FROM enrollments e JOIN courses c ON e.course_id = c.id "
            "WHERE e.period_id = %s ORDER BY c.name_ar", (period_id,)
        )

    def insert(self, period_id: int, course_id: int, score: float, is_second: int) -> int:
        return self._execute(
            "INSERT INTO enrollments (period_id, course_id, score, is_second_round) VALUES (%s, %s, %s, %s)",
            (period_id, course_id, score, is_second), commit=True
        )

    def update(self, enrollment_id: int, score: float, is_second: int) -> None:
        self._execute(
            "UPDATE enrollments SET score=%s, is_second_round=%s WHERE id=%s",
            (score, is_second, enrollment_id), commit=True
        )
        
    def delete(self, enrollment_id: int) -> None:
        self._execute("DELETE FROM enrollments WHERE id=%s", (enrollment_id,), commit=True)

class StudentRepository(BaseRepository):
    def get_all_paginated(self, limit: int = 25, offset: int = 0, name_query: str = "", dept_id: int = None, year: int = None) -> list[dict]:
        conditions = []
        params = []
        if name_query:
            pattern = f"%{name_query.strip()}%"
            conditions.append("(s.full_name_ar LIKE %s OR s.full_name_en LIKE %s)")
            params += [pattern, pattern]
        if dept_id:
            conditions.append("s.department_id = %s")
            params.append(dept_id)
        if year:
            conditions.append("s.admission_year = %s")
            params.append(year)
            
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params += [limit, offset]
        
        return self._fetch_all(
            "SELECT s.id, s.full_name_ar, s.full_name_en, s.admission_year, s.average, s.order_id, "
            "d.name_ar AS dept_name_ar "
            "FROM students s LEFT JOIN departments d ON s.department_id = d.id "
            f"{where} ORDER BY s.full_name_ar LIMIT %s OFFSET %s", tuple(params)
        )
        
    def get_by_id(self, student_id: int) -> dict | None:
        return self._fetch_one(
            "SELECT s.*, d.name_ar AS dept_name_ar, ss.name_ar AS study_system_name_ar, "
            "c.name_ar AS nationality_ar, g.name_ar AS birthplace_ar "
            "FROM students s "
            "LEFT JOIN departments d ON s.department_id = d.id "
            "LEFT JOIN study_systems ss ON s.study_system_id = ss.id "
            "LEFT JOIN countries c ON s.nationality_id = c.id "
            "LEFT JOIN governorates g ON s.birthplace_id = g.id "
            "WHERE s.id = %s", (student_id,)
        )

    def search(self, query: str, limit: int = 8) -> list[dict]:
        pattern = f"%{query.strip()}%"
        return self._fetch_all(
            "SELECT s.id, s.full_name_ar, s.full_name_en, s.admission_year, s.average, "
            "d.name_ar AS dept_name_ar "
            "FROM students s LEFT JOIN departments d ON s.department_id = d.id "
            "WHERE s.full_name_ar LIKE %s OR s.full_name_en LIKE %s "
            "ORDER BY s.full_name_ar LIMIT %s", (pattern, pattern, limit)
        )
        
    def count(self, name_query: str = "", dept_id: int = None, year: int = None) -> int:
        conditions = []
        params = []
        if name_query:
            pattern = f"%{name_query.strip()}%"
            conditions.append("(s.full_name_ar LIKE %s OR s.full_name_en LIKE %s)")
            params += [pattern, pattern]
        if dept_id:
            conditions.append("s.department_id = %s")
            params.append(dept_id)
        if year:
            conditions.append("s.admission_year = %s")
            params.append(year)
            
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        return self._fetch_scalar(f"SELECT COUNT(*) FROM students s {where}", tuple(params))

    def insert(self, data: dict) -> int:
        # data contains fields including degree_level
        fields = list(data.keys())
        placeholders = ", ".join(["%s"] * len(fields))
        columns = ", ".join(fields)
        values = tuple(data[f] for f in fields)
        
        new_id = self._execute(f"INSERT INTO students ({columns}) VALUES ({placeholders})", values, commit=True)
        log_activity(f"تم إضافة طالب جديد: {data.get('full_name_ar')}")
        return new_id
        
    def update(self, student_id: int, data: dict) -> None:
        fields = list(data.keys())
        set_clause = ", ".join([f"{f}=%s" for f in fields])
        values = tuple(data[f] for f in fields) + (student_id,)
        
        self._execute(f"UPDATE students SET {set_clause} WHERE id=%s", values, commit=True)
        log_activity(f"تم تعديل بيانات الطالب ID: {student_id}")

    def delete(self, student_id: int) -> None:
        self._execute("DELETE FROM students WHERE id=%s", (student_id,), commit=True)
        log_activity(f"تم حذف الطالب ID: {student_id}")

    def get_by_order(self, order_id: int) -> list[dict]:
        return self._fetch_all(
            "SELECT id, full_name_ar, average, order_id FROM students WHERE order_id = %s ORDER BY average DESC",
            (order_id,)
        )
        
    def search_for_order(self, name_query: str = "", admission_year: int = None, department_id: int = None, limit: int = 50) -> list[dict]:
        conditions = []
        params = []
        if name_query:
            pattern = f"%{name_query.strip()}%"
            conditions.append("(s.full_name_ar LIKE %s OR s.full_name_en LIKE %s)")
            params += [pattern, pattern]
        if admission_year:
            conditions.append("s.admission_year = %s")
            params.append(admission_year)
        if department_id:
            conditions.append("s.department_id = %s")
            params.append(department_id)
            
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)
        
        return self._fetch_all(
            "SELECT s.id, s.full_name_ar, s.admission_year, s.order_id, d.name_ar AS dept_name_ar "
            "FROM students s LEFT JOIN departments d ON s.department_id = d.id "
            f"{where} ORDER BY s.full_name_ar LIMIT %s", tuple(params)
        )
        
    def unlink_from_order(self, student_id: int) -> None:
        self._execute("UPDATE students SET order_id = NULL, graduation_date = NULL, graduation_semester = NULL WHERE id = %s", (student_id,), commit=True)
        
    def link_students_to_order(self, order_id: int, order_data: dict) -> int:
        dept_id = order_data.get("department_id")
        adm_year = order_data.get("admission_year")
        if not dept_id or not adm_year:
            return 0
            
        query = "UPDATE students SET order_id = %s, graduation_date = %s, graduation_semester = %s WHERE department_id = %s AND admission_year = %s AND order_id IS NULL"
        return self._execute(query, (order_id, order_data.get("order_date"), order_data.get("graduation_semester"), dept_id, adm_year), commit=True)

class AuditRepository(BaseRepository):
    def get_audit_log(self, table_filter: str = "", action_filter: str = "", limit: int = 25, offset: int = 0) -> list[dict]:
        conditions = []
        params = []
        if table_filter:
            conditions.append("table_name = %s")
            params.append(table_filter)
        if action_filter:
            conditions.append("action = %s")
            params.append(action_filter)
            
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params += [limit, offset]
        
        return self._fetch_all(
            f"SELECT * FROM audit_log {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            tuple(params)
        )
        
    def count_audit_log(self, table_filter: str = "", action_filter: str = "") -> int:
        conditions = []
        params = []
        if table_filter:
            conditions.append("table_name = %s")
            params.append(table_filter)
        if action_filter:
            conditions.append("action = %s")
            params.append(action_filter)
            
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        return self._fetch_scalar(f"SELECT COUNT(*) FROM audit_log {where}", tuple(params))

class CertificateRepository(BaseRepository):
    def log_certificate_generation(self, student_id: int, user_id: int) -> int:
        return self._execute(
            "INSERT INTO certificate_logs (student_id, generated_by) VALUES (%s, %s)",
            (student_id, user_id), commit=True
        )
        
    def get_full_certificate_data(self, student_id: int) -> dict | None:
        row = self._fetch_one(
            "SELECT s.*, "
            "       d.name_ar AS dept_name_ar, d.name_en AS dept_name_en, "
            "       ss.name_ar AS study_system_name_ar, ss.name_en AS study_system_name_en, "
            "       ss.calculation_rule, ss.calculation_weights, ss.period_display, "
            "       c.name_ar AS nationality_ar, c.name_en AS nationality_en, "
            "       g.name_ar AS birthplace_ar, g.name_en AS birthplace_en, "
            "       o.order_number, o.order_date "
            "FROM students s "
            "LEFT JOIN departments d    ON s.department_id   = d.id "
            "LEFT JOIN study_systems ss ON s.study_system_id = ss.id "
            "LEFT JOIN countries c      ON s.nationality_id  = c.id "
            "LEFT JOIN governorates g   ON s.birthplace_id   = g.id "
            "LEFT JOIN graduation_orders o ON s.order_id = o.id "
            "WHERE s.id = %s",
            (student_id,)
        )
        if not row:
            return None
            
        data = row
        
        # We need get_graduate_rank and get_top_graduate_average. They were in queries.py.
        # For simplicity, we can fetch them using direct scalar queries.
        # This implementation requires those queries to be translated.
        # But this function is huge. Let's just use it as it was but with MySQL syntax.
        # I'll implement rank logic.
        dept_id = data["department_id"]
        adm_year = data["admission_year"]
        
        rank_row = self._fetch_one(
            "SELECT COUNT(*) + 1 as rank FROM students "
            "WHERE department_id = %s AND admission_year = %s AND average > %s AND average IS NOT NULL",
            (dept_id, adm_year, data.get("average", 0) or 0)
        )
        total_row = self._fetch_one(
            "SELECT COUNT(*) as total FROM students "
            "WHERE department_id = %s AND admission_year = %s AND average IS NOT NULL",
            (dept_id, adm_year)
        )
        
        data["rank"] = data.get("sequence_number") if data.get("sequence_number") is not None else (rank_row["rank"] if rank_row else 1)
        data["total_graduates"] = data.get("postgraduation_no") if data.get("postgraduation_no") is not None else (total_row["total"] if total_row else 1)
        
        top_row = self._fetch_one(
            "SELECT MAX(average) as top_avg FROM students "
            "WHERE department_id = %s AND admission_year = %s",
            (dept_id, adm_year)
        )
        data["top_average"] = top_row["top_avg"] if top_row else None
        
        periods = self._fetch_all(
            "SELECT * FROM academic_periods WHERE student_id = %s "
            "ORDER BY stage_number, academic_year",
            (student_id,)
        )
        data["periods"] = []
        for p in periods:
            enrolls = self._fetch_all(
                "SELECT e.score, e.is_second_round, "
                "       c.name_ar AS course_name_ar, "
                "       c.name_en AS course_name_en, "
                "       c.credit_hours "
                "FROM enrollments e "
                "JOIN courses c ON e.course_id = c.id "
                "WHERE e.period_id = %s "
                "ORDER BY c.name_ar",
                (p["id"],)
            )
            p["enrollments"] = enrolls
            data["periods"].append(p)
            
        data["front_signatories"] = self._fetch_all("SELECT * FROM personnel WHERE is_active = 1 AND display_order BETWEEN 1 AND 4 ORDER BY display_order")
        data["back_signatories"] = self._fetch_all("SELECT * FROM personnel WHERE is_active = 1 AND display_order >= 5 ORDER BY display_order")
        
        settings = self._fetch_one("SELECT * FROM settings WHERE id = 1")
        if settings:
            data["univ_name_ar"] = settings.get("univ_name_ar")
            data["univ_name_en"] = settings.get("univ_name_en")
            data["college_name_ar"] = settings.get("college_name_ar")
            data["college_name_en"] = settings.get("college_name_en")
            
        return data
