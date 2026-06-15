# =============================================================================
# data/repositories.py — Data Access Layer (MySQL SP Architecture)
# =============================================================================

import logging
from db import get_connection
from sync_engine import (
    is_online, log_offline_insert,
    cache_read_result, get_cached_read,
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
        if not is_online():
            return 0
        allowed_tables = ["students", "departments", "courses", "personnel", "graduation_orders", "study_systems"]
        if table not in allowed_tables:
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
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE university_settings SET univ_name_ar=%s, univ_name_en=%s, college_name_ar=%s, college_name_en=%s WHERE id=1",
                (univ_ar, univ_en, college_ar, college_en)
            )
            conn.commit()
            log_activity("تم تحديث إعدادات النظام")
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
        return self._call_read_all("GetAllCountries")

class GovernorateRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        return self._call_read_all("GetAllGovernorates")

class DepartmentRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        return self._call_read_all("GetAllDepartments")
        
    def get_by_id(self, dept_id: int) -> dict | None:
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
        return self._call_read_all("GetAllStudySystems")
        
    def get_active(self) -> list[dict]:
        return self._call_read_all("GetActiveStudySystems")
        
    def get_by_id(self, system_id: int) -> dict | None:
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
        return self._call_read_all("GetAllPersonnel")
        
    def get_active(self) -> list[dict]:
        return self._call_read_all("GetActivePersonnel")

    def authenticate(self, username: str, password_hash: str) -> dict | None:
        return self._call_read_one("AuthenticateUser", (username, password_hash))

    def insert(self, data: dict) -> int:
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
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE personnel SET is_active = %s WHERE id = %s", (is_active, person_id))
            conn.commit()
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()
        
    def delete(self, person_id: int) -> None:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM personnel WHERE id = %s", (person_id,))
            conn.commit()
            log_activity(f"تم حذف الكادر ID: {person_id}")
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

# ---------------------------------------------------------------------------
# Module 5: Course Catalog
# ---------------------------------------------------------------------------

class CourseRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        return self._call_read_all("GetAllCourses")
        
    def get_by_department(self, dept_id: int) -> list[dict]:
        return self._call_read_all("GetCoursesByDepartment", (dept_id,))

    def get_by_dept_stage_system(self, dept_id: int, stage: int, system_id: int) -> list[dict]:
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
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM courses WHERE id=%s", (course_id,))
            conn.commit()
            log_activity(f"تم حذف المادة الدراسية ID: {course_id}")
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()

# ---------------------------------------------------------------------------
# Module 6: Student Record Access Layer
# ---------------------------------------------------------------------------

class StudentRepository(BaseRepository):
    def get_all_paginated(self, limit: int = 25, offset: int = 0, name_query: str = "", dept_id: int = None, year: str = None) -> list[dict]:
        return self._call_read_all("GetStudentsPaginated", (limit, offset, name_query, dept_id, year))
        
    def get_by_id(self, student_id: int) -> dict | None:
        return self._call_read_one("GetStudentDossierByID", (student_id,))

    def search(self, query: str, limit: int = 8) -> list[dict]:
        return self._call_read_all("SearchStudentsBasic", (query, limit))
        
    def count(self, name_query: str = "", dept_id: int = None, year: str = None) -> int:
        row = self._call_read_one("CountStudentsFiltered", (name_query, dept_id, year))
        return row['total_count'] if row else 0

    def insert(self, data: dict) -> int:
        if not is_online():
            # Route to offline sync engine
            return log_offline_insert("students", dict(data))
        # Schema-aligned payload mapping
        args = (
            data.get('full_name_ar'), data.get('full_name_en'), data.get('gender', 'M'),
            data.get('sequence_number'), data.get('postgraduation_no'), data.get('date_of_birth'),
            data.get('birthplace_id'), data.get('birthplace_other'), data.get('nationality_id'),
            data.get('department_id'), data.get('study_system_id'), data.get('degree_level', 'Bachelor'),
            data.get('order_id'), data.get('admission_year'), data.get('summer_training_data'),
            data.get('average'), data.get('graduation_date'), data.get('graduation_semester')
        )
        new_id = self._call_write("InsertStudent", args)
        log_activity(f"\u062a\u0645 \u0625\u0636\u0627\u0641\u0629 \u0637\u0627\u0644\u0628 \u062c\u062f\u064a\u062f: {data.get('full_name_ar')}")
        return new_id
        
    def update(self, student_id: int, data: dict) -> None:
        args = (
            student_id,
            data.get('full_name_ar'), data.get('full_name_en'), data.get('gender', 'M'),
            data.get('sequence_number'), data.get('postgraduation_no'), data.get('date_of_birth'),
            data.get('birthplace_id'), data.get('birthplace_other'), data.get('nationality_id'),
            data.get('department_id'), data.get('study_system_id'), data.get('degree_level', 'Bachelor'),
            data.get('order_id'), data.get('admission_year'), data.get('summer_training_data'),
            data.get('average'), data.get('graduation_date'), data.get('graduation_semester')
        )
        self._call_write("UpdateStudent", args)
        log_activity(f"\u062a\u0645 \u062a\u0639\u062f\u064a\u0644 \u0628\u064a\u0627\u0646\u0627\u062a \u0627\u0644\u0637\u0627\u0644\u0628 ID: {student_id}")

    def delete(self, student_id: int) -> None:
        self._call_write("DeleteStudent", (student_id,))
        log_activity(f"\u062a\u0645 \u062d\u0630\u0641 \u0627\u0644\u0637\u0627\u0644\u0628 ID: {student_id}")

# ---------------------------------------------------------------------------
# Module 7: Timelines & Enrollments
# ---------------------------------------------------------------------------

class AcademicPeriodRepository(BaseRepository):
    def get_by_student(self, student_id: int) -> list[dict]:
        return self._call_read_all("GetAcademicPeriodsByStudent", (student_id,))

    def insert(self, student_id: int, year: str, sys_id: int, stage: int, round_val: str = None) -> int:
        if not is_online():
            return log_offline_insert("academic_periods", {
                "student_id": student_id,
                "academic_year": year,
                "study_system_id": sys_id,
                "stage_number": stage,
                "semester_num": 1,
            })
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO academic_periods (student_id, academic_year, study_system_id, stage_number) "
                "VALUES (%s, %s, %s, %s)", (student_id, year, sys_id, stage)
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
        return self._call_read_all("GetAllGraduationOrders")

    def get_by_id(self, order_id: int) -> dict | None:
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
        
        conn = get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute(f"SELECT * FROM audit_log {where} ORDER BY created_at DESC LIMIT %s OFFSET %s", tuple(params))
            return cur.fetchall()
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()
        
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
        
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM audit_log {where}", tuple(params))
            row = cur.fetchone()
            return row[0] if row else 0
        finally:
            if 'cur' in locals(): cur.close()
            conn.close()
