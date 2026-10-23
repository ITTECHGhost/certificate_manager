import re

with open('data/repositories.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update imports at top of data/repositories.py
content = re.sub(
    r'from sync_engine import \([\s\S]*?\)',
    '''from sync_engine import (
    is_online, log_offline_insert,
    cache_read_result, get_cached_read,
    pull_mysql_to_sqlite_background,
    generate_temp_id,
    DB_PATH,
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
)''',
    content
)

# Replace count_table_rows
content = content.replace(
    '''        if not is_online():
            # Count from SQLite replica
            try:
                row = sqlite_read_one(f"SELECT COUNT(*) as cnt FROM {table} {filter_clause}")
                return row["cnt"] if row else 0
            except Exception:
                return 0''',
    '''        if not is_online():
            return get_offline_count_table_rows(table, filter_clause)'''
)

# Replace SettingsRepository.get_settings
content = content.replace(
    '''    def get_settings(self) -> dict:
        if not is_online():
            row = sqlite_read_one("SELECT * FROM university_settings WHERE id = 1")
            return row if row else {}''',
    '''    def get_settings(self) -> dict:
        if not is_online():
            return get_offline_settings()'''
)

# Replace SettingsRepository.get_user_appearance
old_get_appearance = '''        if not is_online():
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
                }'''

content = content.replace(old_get_appearance, '''        if not is_online():
            return get_offline_user_appearance(emp_id)''')

# Replace fallback get_user_appearance SQLite reads in SettingsRepository
content = re.sub(
    r'row = sqlite_read_one\("SELECT EMP_ID, theme[\s\S]*?is_arabic_rtl": 1\n\s*\}',
    'return get_offline_user_appearance(emp_id)',
    content
)

# Replace SettingsRepository.update_user_appearance offline block
old_update_appearance = '''        if not is_online():
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
            return'''

content = content.replace(old_update_appearance, '''        if not is_online():
            update_offline_user_appearance(emp_id, theme, accent, font, size, rtl)
            log_activity(f"تم تحديث المظهر للمستخدم ID: {emp_id}")
            return''')

# Replace CountryRepository.get_all
content = content.replace('return sqlite_read_all("SELECT id, name_ar, name_en, iso_code FROM countries ORDER BY name_en")', 'return get_offline_countries()')

# Replace GovernorateRepository.get_all
content = content.replace('return sqlite_read_all("SELECT id, name_ar, name_en FROM governorates ORDER BY id")', 'return get_offline_governorates()')

# Replace DepartmentRepository get_all and get_by_id
content = content.replace('''        if not is_online():
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
            )''', '''        if not is_online():
            return get_offline_departments()''')

content = content.replace('''        if not is_online():
            return sqlite_read_one(
                "SELECT d.id, d.name_ar, d.name_en, "
                "       u.college_name_ar AS college_name_ar, "
                "       u.college_name_en AS college_en, "
                "       u.college_name_ar AS college_ar, "
                "       u.college_name_en AS college_en, "
                "       4 AS study_years "
                "FROM departments d "
                "LEFT JOIN university_settings u ON d.university_settings_id = u.id "
                "WHERE d.id = ?",
                (dept_id,)
            )''', '''        if not is_online():
            return get_offline_department_by_id(dept_id)''')

# Replace StudySystemRepository
content = content.replace('return sqlite_read_all("SELECT * FROM study_systems ORDER BY id")', 'return get_offline_study_systems()')
content = content.replace('return sqlite_read_all("SELECT * FROM study_systems WHERE is_active = 1 ORDER BY id")', 'return get_offline_active_study_systems()')
content = content.replace('return sqlite_read_one("SELECT * FROM study_systems WHERE id = ?", (system_id,))', 'return get_offline_study_system_by_id(system_id)')

# Replace PersonnelRepository
content = content.replace('return sqlite_read_all("SELECT * FROM personnel")', 'return get_offline_personnel()')
content = content.replace('return sqlite_read_all("SELECT * FROM personnel WHERE is_active = 1")', 'return get_offline_active_personnel()')
content = content.replace('return sqlite_read_one("SELECT * FROM personnel WHERE id = ?", (person_id,))', 'return get_offline_personnel_by_id(person_id)')
content = content.replace('return sqlite_read_one("SELECT * FROM personnel WHERE username = ?", (username,))', 'return get_offline_personnel_by_username(username)')

# Replace CourseRepository
content = re.sub(
    r'if not is_online\(\):\s*return sqlite_read_all\(\s*"SELECT c\.\*, d\.name_ar AS dept_name_ar[\s\S]*?ORDER BY c\.name_ar ASC"\s*\)',
    'if not is_online():\n            return get_offline_courses()',
    content
)

content = re.sub(
    r'return sqlite_read_all\(\s*"SELECT c\.id, c\.name_ar, c\.name_en, c\.credit_hours, c\.department_id, c\.stage_number[\s\S]*?\(dept_id,\)\s*\)',
    'return get_offline_courses_by_department(dept_id)',
    content
)

content = re.sub(
    r'return sqlite_read_all\(\s*"SELECT id, name_ar, name_en, credit_hours, stage_number FROM courses[\s\S]*?\(dept_id, stage\),\s*\)',
    'return get_offline_courses_by_dept_stage_system(dept_id, stage, system_id)',
    content
)

# Replace CourseRepository.update offline block
content = re.sub(
    r'if not is_online\(\):\s*sq_conn = get_local_connection\(\)[\s\S]*?sq_conn\.close\(\)\s*return',
    'if not is_online():\n            update_offline_course(course_id, payload.get("name_ar"), payload.get("name_en"), payload["credit_hours"], payload.get("department_id"), payload["stage_number"])\n            return',
    content
)

# Remove standalone search_students_sqlite function from repositories.py
content = re.sub(
    r'def search_students_sqlite\([\s\S]*?return \[\s*\{\s*"student_id"[\s\S]*?\n            \]\n',
    '',
    content
)

content = content.replace(
    'return search_students_sqlite(self.local_db_path, query, limit, offset)',
    'return search_offline_students_paginated(self.local_db_path, query, limit, offset)'
)

# Replace StudentRepository methods
content = content.replace('return sqlite_read_all(query, (limit,))', 'return get_offline_last_added_students(limit)')

# Replace _inject_missing_graduation_numbers offline block
old_supp = '''                else:
                    conn = get_local_connection()
                    cursor = conn.cursor()
                    format_strings = ','.join(['?'] * len(student_ids))
                    query = f"SELECT id, sequence_number, postgraduation_number FROM students WHERE id IN ({format_strings})"
                    cursor.execute(query, tuple(student_ids))
                    supp_data = {row["id"]: dict(row) for row in cursor.fetchall()}
                    cursor.close()
                    conn.close()'''

content = content.replace(old_supp, '''                else:
                    supp_data = get_offline_student_supplemental_graduation(student_ids)''')

# Replace get_all_paginated offline block
old_get_all_paginated = '''        if not is_online():
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
            )'''

content = content.replace(old_get_all_paginated, '''        if not is_online():
            res = get_offline_students_paginated(limit, offset, name_query, dept_id, year)''')

# Replace get_by_id offline block
old_get_by_id = '''        if not is_online():
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
            )'''

content = content.replace(old_get_by_id, '''        if not is_online():
            res = get_offline_student_by_id(student_id)''')

# Replace search offline block
old_search_offline = '''        if not is_online():
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
            params = (fuzzy_match, fuzzy_match, exact_match, exact_match, prefix_match, prefix_match, limit)
            res = sqlite_read_all(sqlite_query, params)'''

content = content.replace(old_search_offline, '''        if not is_online():
            res = search_offline_students(query, limit)''')

# Replace StudentRepository.get_statistics_by_department offline block
old_stats = '''        if not is_online():
            row = sqlite_read_one(
                "SELECT COUNT(*) AS total_students, "
                "SUM(CASE WHEN order_id IS NOT NULL THEN 1 ELSE 0 END) AS graduated_count, "
                "AVG(average) AS average_gpa FROM ("
                "  SELECT id, order_id, average FROM students "
                "  UNION ALL "
                "  SELECT id, order_id, average FROM local_students"
                ")"
            )
            return row if row else {}'''

content = content.replace(old_stats, '''        if not is_online():
            return get_offline_student_statistics_by_department()''')

# Replace get_unlinked_students offline block
content = re.sub(
    r'if not is_online\(\):\s*return sqlite_read_all\(\s*"SELECT id, full_name_ar[\s\S]*?\(dept_id, str\(year\)\)\s*\)',
    'if not is_online():\n            return get_offline_unlinked_students(dept_id, year)',
    content
)

# Replace link_to_order / unlink_from_order offline blocks
content = content.replace(
    '''        for student_id in student_ids:
            sqlite_read_all("UPDATE students SET order_id = ? WHERE id = ?", (order_id, student_id))
            sqlite_read_all("UPDATE local_students SET order_id = ? WHERE id = ?", (order_id, student_id))''',
    '''        link_offline_students_to_order(student_ids, order_id)'''
)

content = content.replace(
    '''        for student_id in student_ids:
            sqlite_read_all("UPDATE students SET order_id = NULL WHERE id = ?", (student_id,))
            sqlite_read_all("UPDATE local_students SET order_id = NULL WHERE id = ?", (student_id,))''',
    '''        unlink_offline_students_from_order(student_ids)'''
)

# Replace get_by_order_id & search_by_order
content = re.sub(
    r'if not is_online\(\):\s*sqlite_query = """\s*SELECT \s*s\.id AS student_id[\s\S]*?return sqlite_read_all\(sqlite_query, \(order_id, limit, offset\)\)',
    'if not is_online():\n            return get_offline_students_by_order_id(order_id, limit, offset)',
    content
)

content = re.sub(
    r'if not is_online\(\):\s*if not clean_query:[\s\S]*?return sqlite_read_all\(sqlite_query, \(order_id, pattern, pattern, limit, offset\)\)',
    'if not is_online():\n            return search_offline_students_by_order(order_id, query, limit, offset)',
    content
)

# Replace get_distinct_admission_years
content = re.sub(
    r'if not is_online\(\):\s*rows = sqlite_read_all\([\s\S]*?return unique_years',
    'if not is_online():\n            return get_offline_distinct_admission_years()',
    content
)

# Replace StudentRepository.delete offline block
old_delete_student = '''        if not is_online():
            sq_conn = get_local_connection()
            try:
                sq_conn.execute("DELETE FROM enrollments WHERE period_id IN (SELECT id FROM academic_periods WHERE student_id=?)", (student_id,))
                sq_conn.execute("DELETE FROM student_courses WHERE period_id IN (SELECT id FROM academic_periods WHERE student_id=?)", (student_id,))
                sq_conn.execute("DELETE FROM academic_periods WHERE student_id=?", (student_id,))
                sq_conn.execute("DELETE FROM issued_certificates WHERE student_id=?", (student_id,))
                sq_conn.execute("DELETE FROM students WHERE id=?", (student_id,))
                sq_conn.execute("DELETE FROM local_students WHERE id=?", (student_id,))
                sq_conn.commit()
            finally:
                sq_conn.close()
            log_activity(f"تم حذف الطالب ID: {student_id}")
            return'''

content = content.replace(old_delete_student, '''        if not is_online():
            delete_offline_student(student_id)
            log_activity(f"تم حذف الطالب ID: {student_id}")
            return''')

# Replace AcademicPeriodRepository get_by_student offline block
old_get_periods = '''        if not periods:
            periods = sqlite_read_all(
                "SELECT id, student_id, academic_year, study_system_id, stage_number, semester_num, COALESCE(result_status, 'PASSED') AS result_status FROM ("
                "  SELECT id, student_id, academic_year, study_system_id, stage_number, semester_num, result_status FROM academic_periods "
                "  UNION ALL "
                "  SELECT id, student_id, academic_year, study_system_id, stage_number, semester_num, result_status FROM local_academic_periods"
                ") WHERE student_id = ? ORDER BY stage_number, semester_num",
                (student_id,)
            ) or []'''

content = content.replace(old_get_periods, '''        if not periods:
            periods = get_offline_academic_periods_by_student(student_id)''')

# Replace AcademicPeriodRepository update_status & update_stage offline blocks
old_period_status = '''        conn = get_local_connection()
        try:
            if period_id < 0:
                try:
                    conn.execute("UPDATE local_academic_periods SET result_status = ? WHERE id = ?", (st_key, period_id))
                except sqlite3.OperationalError as oe:
                    if "no such column" in str(oe).lower():
                        conn.execute("ALTER TABLE local_academic_periods ADD COLUMN result_status TEXT DEFAULT 'PASSED'")
                        conn.execute("UPDATE local_academic_periods SET result_status = ? WHERE id = ?", (st_key, period_id))
                    else:
                        raise
            else:
                try:
                    conn.execute("UPDATE academic_periods SET result_status = ? WHERE id = ?", (st_key, period_id))
                except sqlite3.OperationalError as oe:
                    if "no such column" in str(oe).lower():
                        conn.execute("ALTER TABLE academic_periods ADD COLUMN result_status TEXT DEFAULT 'PASSED'")
                        conn.execute("UPDATE academic_periods SET result_status = ? WHERE id = ?", (st_key, period_id))
                    else:
                        raise
            conn.commit()
        finally:
            conn.close()'''

content = content.replace(old_period_status, '        update_offline_academic_period_status(period_id, st_key)')

old_period_stage = '''        conn = get_local_connection()
        try:
            if period_id < 0:
                conn.execute("UPDATE local_academic_periods SET stage_number = ? WHERE id = ?", (stage_number, period_id))
            else:
                conn.execute("UPDATE academic_periods SET stage_number = ? WHERE id = ?", (stage_number, period_id))
            conn.commit()
        finally:
            conn.close()'''

content = content.replace(old_period_stage, '        update_offline_academic_period_stage(period_id, stage_number)')

# Replace EnrollmentRepository get_by_period and update
content = re.sub(
    r'if not is_online\(\):\s*return sqlite_read_all\(\s*"SELECT e\.id, e\.period_id, e\.course_id[\s\S]*?\(period_id,\)\s*\)',
    'if not is_online():\n            return get_offline_enrollments_by_period(period_id)',
    content
)

old_update_enrollment = '''        # Always update local SQLite cache
        try:
            sq_conn = get_local_connection()
            try:
                sq_conn.execute("UPDATE enrollments SET score = ?, passed_round = ? WHERE id = ?", (float(score), passed_round, enrollment_id))
                sq_conn.execute("UPDATE local_enrollments SET score = ?, passed_round = ? WHERE id = ?", (float(score), passed_round, enrollment_id))
                sq_conn.commit()
            finally:
                sq_conn.close()
        except Exception as sq_err:
            log_system(f"Local enrollments update warning: {sq_err}", "WARNING")'''

content = content.replace(old_update_enrollment, '''        try:
            update_offline_enrollment(enrollment_id, score, passed_round)
        except Exception as sq_err:
            log_system(f"Local enrollments update warning: {sq_err}", "WARNING")''')

# Replace GraduationOrderRepository
content = re.sub(
    r'if not is_online\(\):\s*return sqlite_read_all\(\s*"SELECT o\.\*, d\.name_ar AS dept_name_ar[\s\S]*?\(limit, offset\)\s*\)',
    'if not is_online():\n            return get_offline_graduation_orders(limit, offset)',
    content
)

content = re.sub(
    r'if not is_online\(\):\s*return sqlite_read_one\(\s*"SELECT o\.\*, d\.name_ar AS dept_name_ar[\s\S]*?\(order_id,\)\s*\)',
    'if not is_online():\n            return get_offline_graduation_order_by_id(order_id)',
    content
)

# Replace AuditRepository.get_all
content = content.replace(
    'return sqlite_read_all("SELECT id, user, action, details, timestamp FROM audit_log ORDER BY id DESC LIMIT 100")',
    'return get_offline_audit_logs()'
)

# Replace StudyRoutineRepository offline methods
content = re.sub(
    r'if not is_online\(\):\s*query = """\s*SELECT sr\.id, sr\.routine_name_ar AS name_ar[\s\S]*?return sqlite_read_all\(query, \(dept_id, dept_id, sys_id, sys_id\)\)',
    'if not is_online():\n            return get_offline_study_routines(dept_id, sys_id)',
    content
)

content = re.sub(
    r'if not is_online\(\):\s*query = """\s*SELECT sr\.id, sr\.routine_name_ar AS name_ar[\s\S]*?return sqlite_read_one\(query, \(routine_id,\)\)',
    'if not is_online():\n            return get_offline_study_routine_by_id(routine_id)',
    content
)

content = re.sub(
    r'if not is_online\(\):\s*query = "SELECT id, routine_id, stage_number, semester_num FROM study_routine_period WHERE routine_id = \? ORDER BY stage_number, semester_num"\s*return sqlite_read_all\(query, \(routine_id,\)\)',
    'if not is_online():\n            return get_offline_study_routine_periods(routine_id)',
    content
)

content = re.sub(
    r'if not is_online\(\):\s*query = """\s*SELECT src\.id, src\.period_id, src\.course_id[\s\S]*?return sqlite_read_all\(query, \(period_id,\)\)',
    'if not is_online():\n            return get_offline_study_routine_period_courses(period_id)',
    content
)

content = re.sub(
    r'if not is_online\(\):\s*conn = get_local_connection\(\)[\s\S]*?return cur\.lastrowid',
    'if not is_online():\n            return insert_offline_study_routine(name_ar, name_en, dept_id, sys_id)',
    content
)

content = re.sub(
    r'if not is_online\(\):\s*conn = get_local_connection\(\)[\s\S]*?return',
    'if not is_online():\n            update_offline_study_routine(routine_id, name_ar, name_en, dept_id, sys_id)\n            return',
    content
)

content = re.sub(
    r'if not is_online\(\):\s*conn = get_local_connection\(\)[\s\S]*?log_activity\(f"تم حذف الروتين ID: {routine_id}"\)\s*return',
    'if not is_online():\n            delete_offline_study_routine(routine_id)\n            log_activity(f"تم حذف الروتين ID: {routine_id}")\n            return',
    content
)

with open('data/repositories.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated data/repositories.py successfully.")
