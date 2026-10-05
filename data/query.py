# =============================================================================
# data/query.py — Offline SQLite Local Query Engine for Certificates
# =============================================================================

from typing import Dict, List, Any, Optional
from sync_engine import sqlite_read_one, sqlite_read_all


def safe_cast(val: Any, target_type: type = int, default_val: Any = 0) -> Any:
    """Safely cast a value to target_type with default_val fallback on None or cast failure."""
    if val is None:
        return default_val
    try:
        return target_type(val)
    except (ValueError, TypeError):
        return default_val



Q_COURSES_SEMESTER_BY_STAGE = '''
SELECT
    ap.academic_year,
    ap.stage_number AS period_stage,
    COALESCE(c.stage_number, ap.stage_number) AS course_curriculum_stage,
    COALESCE(ap.semester_num, 1) AS semester_num,
    c.id AS course_id,
    COALESCE(c.name_ar, '') AS subject_name,
    COALESCE(c.name_en, c.name_ar, '') AS subject_name_en,
    COALESCE(c.name_ar, '') AS subject_name_ar,
    COALESCE(c.name_en, c.name_ar, '') AS course_name_en,
    COALESCE(c.name_ar, '') AS course_name_ar,
    COALESCE(c.credit_hours, 0) AS unit,
    MAX(COALESCE(e.score, 0.0)) AS mark,
    MAX(COALESCE(e.passed_round, 1)) AS passed_round,
    CAST(ap.stage_number AS TEXT) AS grouping_key,
    1 AS result_status_code,
    'PASSED' AS result_status_label
FROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap
JOIN (SELECT * FROM enrollments UNION ALL SELECT * FROM local_enrollments) e ON e.period_id = ap.id
JOIN courses c ON e.course_id = c.id
WHERE ap.student_id = ?
  AND COALESCE(e.score, 0.0) >= 50
GROUP BY ap.academic_year, ap.stage_number, c.id
ORDER BY ap.academic_year ASC, COALESCE(ap.semester_num, 1) ASC, c.name_ar ASC;
'''

Q_COURSES_SEMESTER_BY_YEAR = '''
SELECT
    ap.academic_year,
    ap.stage_number AS period_stage,
    COALESCE(c.stage_number, ap.stage_number) AS course_curriculum_stage,
    COALESCE(ap.semester_num, 1) AS semester_num,
    c.id AS course_id,
    COALESCE(c.name_ar, '') AS subject_name,
    COALESCE(c.name_en, c.name_ar, '') AS subject_name_en,
    COALESCE(c.name_ar, '') AS subject_name_ar,
    COALESCE(c.name_en, c.name_ar, '') AS course_name_en,
    COALESCE(c.name_ar, '') AS course_name_ar,
    COALESCE(c.credit_hours, 0) AS unit,
    MAX(COALESCE(e.score, 0.0)) AS mark,
    MAX(COALESCE(e.passed_round, 1)) AS passed_round,
    ap.academic_year || '_' || CAST(COALESCE(ap.semester_num, 1) AS TEXT) AS grouping_key,
    1 AS result_status_code,
    'PASSED' AS result_status_label
FROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap
JOIN (SELECT * FROM enrollments UNION ALL SELECT * FROM local_enrollments) e ON e.period_id = ap.id
JOIN courses c ON e.course_id = c.id
WHERE ap.student_id = ?
  AND COALESCE(e.score, 0.0) >= 50
GROUP BY ap.academic_year, ap.semester_num, c.id
ORDER BY ap.academic_year ASC, COALESCE(ap.semester_num, 1) ASC, c.name_ar ASC;
'''

Q_COURSES_YEARLY_BY_PERIOD_STAGE = '''
SELECT
    CASE 
        WHEN ap.academic_year IS NULL OR ap.academic_year = '' THEN '' 
        WHEN ap.academic_year LIKE '%-%' THEN ap.academic_year 
        ELSE ap.academic_year || ' - ' || CAST(CAST(ap.academic_year AS INTEGER) + 1 AS TEXT) 
    END AS academic_year_formatted,
    ap.academic_year,
    ap.stage_number AS period_stage,
    COALESCE(c.stage_number, ap.stage_number) AS course_curriculum_stage,
    COALESCE(ap.semester_num, 1) AS semester_num,
    c.id AS course_id,
    COALESCE(c.name_ar, '') AS subject_name,
    COALESCE(c.name_en, c.name_ar, '') AS course_name_en,
    COALESCE(c.name_ar, '') AS course_name_ar,
    COALESCE(c.credit_hours, 0) AS unit,
    MAX(COALESCE(e.score, 0.0)) AS mark,
    MAX(COALESCE(e.passed_round, 1)) AS passed_round,
    CASE WHEN COALESCE(c.stage_number, ap.stage_number) < ap.stage_number THEN 'عبور' ELSE 'أساسي' END AS course_type,
    CAST(ap.stage_number AS TEXT) AS grouping_key,
    1 AS result_status_code,
    'PASSED' AS result_status_label
FROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap
JOIN (SELECT * FROM enrollments UNION ALL SELECT * FROM local_enrollments) e ON e.period_id = ap.id
JOIN courses c ON e.course_id = c.id
WHERE ap.student_id = ?
  AND COALESCE(e.score, 0.0) >= 50
GROUP BY ap.academic_year, ap.stage_number, c.id
ORDER BY ap.academic_year ASC, COALESCE(ap.semester_num, 1) ASC, c.name_ar ASC;
'''

Q_COURSES_YEARLY_BY_CURRICULUM_STAGE = '''
SELECT
    CASE 
        WHEN ap.academic_year IS NULL OR ap.academic_year = '' THEN '' 
        WHEN ap.academic_year LIKE '%-%' THEN ap.academic_year 
        ELSE ap.academic_year || ' - ' || CAST(CAST(ap.academic_year AS INTEGER) + 1 AS TEXT) 
    END AS academic_year_formatted,
    ap.academic_year,
    ap.stage_number AS period_stage,
    COALESCE(c.stage_number, ap.stage_number) AS course_curriculum_stage,
    COALESCE(ap.semester_num, 1) AS semester_num,
    c.id AS course_id,
    COALESCE(c.name_ar, '') AS subject_name,
    COALESCE(c.name_en, c.name_ar, '') AS course_name_en,
    COALESCE(c.name_ar, '') AS course_name_ar,
    COALESCE(c.credit_hours, 0) AS unit,
    MAX(COALESCE(e.score, 0.0)) AS mark,
    MAX(COALESCE(e.passed_round, 1)) AS passed_round,
    CASE WHEN COALESCE(c.stage_number, ap.stage_number) < ap.stage_number THEN 'عبور' ELSE 'أساسي' END AS course_type,
    CAST(COALESCE(c.stage_number, ap.stage_number) AS TEXT) AS grouping_key,
    1 AS result_status_code,
    'PASSED' AS result_status_label
FROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap
JOIN (SELECT * FROM enrollments UNION ALL SELECT * FROM local_enrollments) e ON e.period_id = ap.id
JOIN courses c ON e.course_id = c.id
WHERE ap.student_id = ?
  AND COALESCE(e.score, 0.0) >= 50
GROUP BY ap.academic_year, COALESCE(c.stage_number, ap.stage_number), c.id
ORDER BY ap.academic_year ASC, COALESCE(ap.semester_num, 1) ASC, c.name_ar ASC;
'''

Q_COURSES_YEARLY_BY_ACADEMIC_YEAR = '''
SELECT
    CASE 
        WHEN ap.academic_year IS NULL OR ap.academic_year = '' THEN '' 
        WHEN ap.academic_year LIKE '%-%' THEN ap.academic_year 
        ELSE ap.academic_year || ' - ' || CAST(CAST(ap.academic_year AS INTEGER) + 1 AS TEXT) 
    END AS academic_year_formatted,
    ap.academic_year,
    ap.stage_number AS period_stage,
    COALESCE(c.stage_number, ap.stage_number) AS course_curriculum_stage,
    COALESCE(ap.semester_num, 1) AS semester_num,
    c.id AS course_id,
    COALESCE(c.name_ar, '') AS subject_name,
    COALESCE(c.name_en, c.name_ar, '') AS course_name_en,
    COALESCE(c.name_ar, '') AS course_name_ar,
    COALESCE(c.credit_hours, 0) AS unit,
    MAX(COALESCE(e.score, 0.0)) AS mark,
    MAX(COALESCE(e.passed_round, 1)) AS passed_round,
    CASE WHEN COALESCE(c.stage_number, ap.stage_number) < ap.stage_number THEN 'عبور' ELSE 'أساسي' END AS course_type,
    ap.academic_year AS grouping_key,
    1 AS result_status_code,
    'PASSED' AS result_status_label
FROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap
JOIN (SELECT * FROM enrollments UNION ALL SELECT * FROM local_enrollments) e ON e.period_id = ap.id
JOIN courses c ON e.course_id = c.id
WHERE ap.student_id = ?
  AND COALESCE(e.score, 0.0) >= 50
GROUP BY ap.academic_year, c.id
ORDER BY ap.academic_year ASC, COALESCE(ap.semester_num, 1) ASC, c.name_ar ASC;
'''



def get_offline_academic_courses(student_id: int, grouping_mode: str) -> List[Dict[str, Any]]:
    st_id = int(student_id)
    ss_info = sqlite_read_one(
        "SELECT LOWER(IFNULL(ss.period_display, 'year')) AS period_display "
        "FROM (SELECT id, study_system_id FROM students UNION ALL SELECT id, study_system_id FROM local_students) s "
        "LEFT JOIN study_systems ss ON s.study_system_id = ss.id "
        "WHERE s.id = ?",
        (st_id,)
    )
    period_display = str(ss_info.get("period_display", "year")).lower() if ss_info else "year"
    
    if period_display == "semester":
        if grouping_mode == "BY_SEMESTER_stage":
            return sqlite_read_all(Q_COURSES_SEMESTER_BY_STAGE, (st_id,)) or []
        else:
            return sqlite_read_all(Q_COURSES_SEMESTER_BY_YEAR, (st_id,)) or []
    else:
        if grouping_mode == "BY_PERIOD_STAGE":
            return sqlite_read_all(Q_COURSES_YEARLY_BY_PERIOD_STAGE, (st_id,)) or []
        elif grouping_mode == "BY_CURRICULUM_STAGE":
            return sqlite_read_all(Q_COURSES_YEARLY_BY_CURRICULUM_STAGE, (st_id,)) or []
        else:
            # BY_ByAcademicYear or DEFAULT
            return sqlite_read_all(Q_COURSES_YEARLY_BY_ACADEMIC_YEAR, (st_id,)) or []


def get_offline_certificate_data(student_id: int, grouping_mode: str = "DEFAULT") -> Dict[str, List[Dict[str, Any]]]:
    """
    Executes local SQLite queries to fetch full certificate payload offline.
    Returns a dictionary with 6 keys: settings, student_info, ranking, signers, academic_timeline, courses_grouped.
    """
    st_id = int(student_id)
    response_data: Dict[str, List[Dict[str, Any]]] = {
        "settings": [],
        "student_info": [],
        "ranking": [],
        "signers": [],
        "academic_timeline": [],
        "courses_grouped": []
    }

    # 0. Settings
    settings = sqlite_read_one("SELECT * FROM university_settings ORDER BY id ASC LIMIT 1")
    if settings:
        response_data["settings"] = [settings]

    
    # 1. Student Info
    student = sqlite_read_one(
        "SELECT "
        "s.student_id, "
        "NULL AS department_id, "
        "IFNULL(s.full_name_ar, '') AS full_name_ar, "
        "IFNULL(s.full_name_en, '') AS full_name_en, "
        "ROUND(IFNULL(s.average, 0.0), 3) AS average, "
        "IFNULL(CAST(strftime('%Y', s.graduation_date) AS INTEGER), 0) AS graduation_year, "
        "IFNULL(s.graduation_date, '1970-01-01') AS graduation_date, "
        "IFNULL(s.graduation_semester, 1) AS graduation_semester, "
        "IFNULL(s.date_of_birth, '1970-01-01') AS date_of_birth, "
        "IFNULL(s.sequence_number, 0) AS sequence_number, "
        "CAST(CASE "
        "  WHEN s.postgraduation_number = 0 OR s.postgraduation_number IS NULL THEN IFNULL(o.num_students, '') "
        "  ELSE IFNULL(s.postgraduation_number, '') "
        "END AS TEXT) AS postgraduation_number, "
        "IFNULL(s.admission_year, 0) AS admission_year, "
        "IFNULL(s.summer_training_data, '') AS summer_training_data, "
        "IFNULL(s.order_id, 0) AS order_id, "
        "IFNULL(d.name_ar, '') AS dept_name_ar, "
        "IFNULL(d.name_en, '') AS dept_name_en, "
        "IFNULL(ss.name_ar, '') AS study_system_name_ar, "
        "IFNULL(ss.name_en, '') AS study_system_name_en, "
        "IFNULL(ss.calculation_rule, '') AS calculation_rule, "
        "IFNULL(ss.calculation_weights, '') AS calculation_weights, "
        "IFNULL(ss.period_display, '') AS period_display, "
        "IFNULL(ss.study_day_type, '') AS study_type, "
        "IFNULL(c.name_ar, '') AS nationality_ar, "
        "IFNULL(c.name_en, '') AS nationality_en, "
        "IFNULL(g.name_ar, '') AS birthplace_ar, "
        "IFNULL(g.name_en, '') AS birthplace_en, "
        "IFNULL(o.order_number, '') AS order_number, "
        "IFNULL(o.order_date, '1970-01-01') AS order_date, "
        "us.univ_name_ar, "
        "us.univ_name_en, "
        "us.college_name_ar, "
        "us.college_name_en, "
        "1 AS university_settings_id "
        "FROM ("
        "  SELECT id AS student_id, full_name_ar, full_name_en, sequence_number, postgraduation_number, date_of_birth, "
        "         birthplace_id, birthplace_other, nationality_id, department_id, study_system_id, "
        "         order_id, admission_year, summer_training_data, average, graduation_date, graduation_semester "
        "  FROM students "
        "  UNION ALL "
        "  SELECT id AS student_id, full_name_ar, full_name_en, sequence_number, postgraduation_number, date_of_birth, "
        "         birthplace_id, birthplace_other, nationality_id, department_id, study_system_id, "
        "         order_id, admission_year, summer_training_data, average, graduation_date, graduation_semester "
        "  FROM local_students "
        ") s "
        "LEFT JOIN departments d    ON s.department_id   = d.id "
        "LEFT JOIN study_systems ss ON s.study_system_id = ss.id "
        "LEFT JOIN countries c      ON s.nationality_id  = c.id "
        "LEFT JOIN governorates g   ON s.birthplace_id   = g.id "
        "LEFT JOIN graduation_orders o ON s.order_id = o.id "
        "LEFT JOIN university_settings us ON us.id = 1 "
        "WHERE s.student_id = ?",
        (st_id,)
    )

    if not student:
        return response_data

    response_data["student_info"] = [student]


    # 2. Ranking
    dept_info = sqlite_read_one("SELECT department_id FROM students WHERE id = ?", (st_id,))
    dept_id = dept_info["department_id"] if dept_info else None
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
    response_data["signers"] = signers or []

    # 4. Academic Timeline
    timeline = sqlite_read_all(
        "SELECT MIN(ap.id) AS primary_period_id, "
        "       CASE WHEN ap.academic_year IS NULL OR ap.academic_year = '' THEN '' "
        "            WHEN ap.academic_year LIKE '%-%' THEN ap.academic_year "
        "            ELSE ap.academic_year || ' - ' || CAST(CAST(ap.academic_year AS INTEGER) + 1 AS TEXT) "
        "       END AS academic_year, "
        "       MAX(ap.stage_number) AS stage_number, "
        "       COALESCE(ap.semester_num, 1) AS semester_num, "
        "       REPLACE(GROUP_CONCAT(COALESCE(ap.result_status, 'PASSED')), ',', ' / ') AS result_status "
        "FROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap "
        "WHERE ap.student_id = ? "
        "GROUP BY ap.academic_year, ap.semester_num "
        "ORDER BY ap.academic_year ASC, ap.semester_num ASC",
        (st_id,)
    )
    response_data["academic_timeline"] = timeline or []

    
    # 5. Courses
    courses = get_offline_academic_courses(st_id, grouping_mode)
    response_data["courses_grouped"] = courses or []

    return response_data


def get_offline_flat_yearly_courses(student_id: int) -> List[Dict[str, Any]]:
    """
    Fetches flat 14-column transcript courses using DEFAULT_QUERY in offline mode.
    """
    st_id = int(student_id)
    raw_rows = get_offline_academic_courses(st_id, "BY_ByAcademicYear") or []

    st_info = sqlite_read_one(
        "SELECT s.full_name_ar, ss.name_ar AS study_system_ar "
        "FROM (SELECT id, full_name_ar, study_system_id FROM students UNION ALL SELECT id, full_name_ar, study_system_id FROM local_students) s "
        "LEFT JOIN study_systems ss ON s.study_system_id = ss.id "
        "WHERE s.id = ?",
        (st_id,)
    ) or {}

    student_name_ar = str(st_info.get("full_name_ar") or "")
    study_system_ar = str(st_info.get("study_system_ar") or "")

    flat_records: List[Dict[str, Any]] = []
    for r in raw_rows:
        if isinstance(r, dict):
            stg_num = safe_cast(r.get("period_stage"), int, 1)
            flat_records.append({
                "student_id": st_id,
                "student_name_ar": student_name_ar,
                "study_system_ar": study_system_ar,
                "academic_year": str(r.get("academic_year_formatted") or r.get("academic_year") or ""),
                "stage_number": stg_num,
                "stage_name_ar": f"المرحلة {stg_num}",
                "course_id": safe_cast(r.get("course_id"), int, 0),
                "course_code": str(r.get("course_code") or ""),
                "course_name_ar": str(r.get("course_name_ar") or ""),
                "course_name_en": str(r.get("course_name_en") or ""),
                "units": safe_cast(r.get("unit"), int, 0),
                "mark": safe_cast(r.get("mark"), float, 0.0),
                "result_status_code": safe_cast(r.get("result_status_code"), int, 1),
                "result_status_label": "PASSED" if safe_cast(r.get("mark"), float, 0) >= 50 else "FAILED",
            })

    return flat_records


# =============================================================================
# Offline Issued Certificates Query Functions
# =============================================================================

def get_offline_issued_certificates_by_student(student_id: int) -> List[Dict[str, Any]]:
    st_id = safe_cast(student_id, int, 0)
    return sqlite_read_all(
        "SELECT ic.id, ic.student_id, ic.to_title, ic.template_type, ic.issue_date, "
        "s.full_name_ar, s.full_name_en "
        "FROM ("
        "  SELECT id, student_id, to_title, template_type, issue_date FROM issued_certificates "
        "  UNION ALL "
        "  SELECT id, student_id, to_title, template_type, issue_date FROM local_issued_certificates "
        ") ic "
        "LEFT JOIN ("
        "  SELECT id, full_name_ar, full_name_en FROM students "
        "  UNION ALL "
        "  SELECT id, full_name_ar, full_name_en FROM local_students "
        ") s ON ic.student_id = s.id "
        "WHERE ic.student_id = ? "
        "ORDER BY ic.issue_date DESC, ic.id DESC",
        (st_id,)
    ) or []


def get_offline_issued_certificate_by_id(cert_id: int) -> Optional[Dict[str, Any]]:
    c_id = safe_cast(cert_id, int, 0)
    return sqlite_read_one(
        "SELECT ic.id, ic.student_id, ic.to_title, ic.template_type, ic.issue_date, "
        "s.full_name_ar, s.full_name_en "
        "FROM ("
        "  SELECT id, student_id, to_title, template_type, issue_date FROM issued_certificates "
        "  UNION ALL "
        "  SELECT id, student_id, to_title, template_type, issue_date FROM local_issued_certificates "
        ") ic "
        "LEFT JOIN ("
        "  SELECT id, full_name_ar, full_name_en FROM students "
        "  UNION ALL "
        "  SELECT id, full_name_ar, full_name_en FROM local_students "
        ") s ON ic.student_id = s.id "
        "WHERE ic.id = ?",
        (c_id,)
    )


def get_offline_issued_certificates_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    dept_id: Optional[int] = None,
    template_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    query = (
        "SELECT ic.id AS certificate_id, ic.id, ic.student_id, ic.to_title, ic.template_type, ic.issue_date, "
        "s.full_name_ar, s.full_name_en, d.name_ar AS department_name, d.name_ar AS dept_name_ar "
        "FROM ("
        "  SELECT id, student_id, to_title, template_type, issue_date FROM issued_certificates "
        "  UNION ALL "
        "  SELECT id, student_id, to_title, template_type, issue_date FROM local_issued_certificates "
        ") ic "
        "LEFT JOIN ("
        "  SELECT id, full_name_ar, full_name_en, department_id FROM students "
        "  UNION ALL "
        "  SELECT id, full_name_ar, full_name_en, department_id FROM local_students "
        ") s ON ic.student_id = s.id "
        "LEFT JOIN departments d ON s.department_id = d.id "
        "WHERE 1=1"
    )
    params = []
    if start_date:
        query += " AND ic.issue_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND ic.issue_date <= ?"
        params.append(end_date)
    if dept_id is not None:
        query += " AND s.department_id = ?"
        params.append(safe_cast(dept_id, int, 0))
    if template_type:
        query += " AND ic.template_type = ?"
        params.append(template_type)

    query += " ORDER BY ic.issue_date DESC, ic.id DESC"
    return sqlite_read_all(query, tuple(params)) or []


def insert_offline_issued_certificate(
    student_id: int,
    to_title: str,
    template_type: str,
    issue_date: str
) -> int:
    from sync_engine import log_offline_insert, get_local_connection
    payload = {
        "student_id": safe_cast(student_id, int, 0),
        "to_title": str(to_title or "من يهمه الأمر"),
        "template_type": str(template_type or "ARABIC"),
        "issue_date": str(issue_date or "")
    }

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
    except Exception:
        pass

    temp_id = log_offline_insert("issued_certificates", payload)
    if temp_id is not None:
        return temp_id
    return local_id


def update_offline_issued_certificate(
    cert_id: int,
    to_title: Optional[str] = None,
    template_type: Optional[str] = None,
    issue_date: Optional[str] = None
) -> None:
    from sync_engine import get_local_connection
    c_id = safe_cast(cert_id, int, 0)
    conn = get_local_connection()
    try:
        conn.execute(
            "UPDATE issued_certificates SET "
            "to_title = COALESCE(?, to_title), "
            "template_type = COALESCE(?, template_type), "
            "issue_date = COALESCE(?, issue_date) "
            "WHERE id = ?",
            (to_title, template_type, issue_date, c_id)
        )
        conn.commit()
    finally:
        conn.close()


def delete_offline_issued_certificate(cert_id: int) -> None:
    from sync_engine import get_local_connection
    c_id = safe_cast(cert_id, int, 0)
    conn = get_local_connection()
    try:
        conn.execute("DELETE FROM issued_certificates WHERE id = ?", (c_id,))
        conn.commit()
    finally:
        conn.close()


# =============================================================================
# Additional Offline Query Functions for Entity Repositories
# =============================================================================

import sqlite3
from sync_engine import get_local_connection, DB_PATH, _json_dumps

def get_offline_count_table_rows(table: str, filter_clause: str = "") -> int:
    allowed_tables = ["students", "departments", "courses", "personnel", "graduation_orders", "study_systems"]
    if table not in allowed_tables:
        return 0
    try:
        row = sqlite_read_one(f"SELECT COUNT(*) as cnt FROM {table} {filter_clause}")
        return row["cnt"] if row else 0
    except Exception:
        return 0

def get_offline_settings() -> dict:
    row = sqlite_read_one("SELECT * FROM university_settings WHERE id = 1")
    return row if row else {}

def get_offline_user_appearance(emp_id: int) -> dict:
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
    except Exception:
        return {
            "EMP_ID": emp_id,
            "theme": "Dark",
            "accent_color": "blue",
            "font_family": "Segoe UI",
            "font_size_base": 13,
            "is_arabic_rtl": 1
        }

def update_offline_user_appearance(emp_id: int, theme: str, accent: str, font: str, size: int, rtl: int = 1) -> None:
    conn = get_local_connection()
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
        
        payload = {
            "emp_id": emp_id,
            "theme": theme,
            "accent_color": accent,
            "font_family": font,
            "font_size_base": size,
            "rtl": rtl
        }
        cur.execute(
            "INSERT INTO sync_queue (table_name, operation, temp_id, payload) VALUES (?, 'UPDATE', ?, ?)",
            ("settings", emp_id, _json_dumps(payload))
        )
        conn.commit()
    finally:
        conn.close()

def get_offline_countries() -> list[dict]:
    return sqlite_read_all("SELECT id, name_ar, name_en, iso_code FROM countries ORDER BY name_en")

def get_offline_governorates() -> list[dict]:
    return sqlite_read_all("SELECT id, name_ar, name_en FROM governorates ORDER BY id")

def get_offline_departments() -> list[dict]:
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

def get_offline_department_by_id(dept_id: int) -> dict | None:
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

def get_offline_study_systems() -> list[dict]:
    return sqlite_read_all("SELECT * FROM study_systems ORDER BY id")

def get_offline_active_study_systems() -> list[dict]:
    return sqlite_read_all("SELECT * FROM study_systems WHERE is_active = 1 ORDER BY id")

def get_offline_study_system_by_id(system_id: int) -> dict | None:
    return sqlite_read_one("SELECT * FROM study_systems WHERE id = ?", (system_id,))

def get_offline_personnel() -> list[dict]:
    return sqlite_read_all("SELECT * FROM personnel")

def get_offline_active_personnel() -> list[dict]:
    return sqlite_read_all("SELECT * FROM personnel WHERE is_active = 1")

def get_offline_personnel_by_id(person_id: int) -> dict | None:
    return sqlite_read_one("SELECT * FROM personnel WHERE id = ?", (person_id,))

def get_offline_personnel_by_username(username: str) -> dict | None:
    return sqlite_read_one("SELECT * FROM personnel WHERE username = ?", (username,))

def get_offline_courses() -> list[dict]:
    return sqlite_read_all(
        "SELECT c.*, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en "
        "FROM courses c "
        "LEFT JOIN departments d ON c.department_id = d.id "
        "ORDER BY c.name_ar ASC"
    )

def get_offline_courses_by_department(dept_id: int) -> list[dict]:
    return sqlite_read_all(
        "SELECT c.id, c.name_ar, c.name_en, c.credit_hours, c.department_id, c.stage_number "
        "FROM courses c "
        "WHERE c.department_id = ? "
        "ORDER BY c.stage_number ASC, c.name_ar ASC",
        (dept_id,)
    )

def get_offline_courses_by_dept_stage_system(dept_id: int, stage: int, system_id: int) -> list[dict]:
    return sqlite_read_all(
        "SELECT id, name_ar, name_en, credit_hours, stage_number FROM courses "
        "WHERE department_id = ? AND stage_number <= ? "
        "ORDER BY stage_number, name_ar",
        (dept_id, stage),
    )

def update_offline_course(course_id: int, name_ar: str, name_en: str, credit_hours: int, dept_id: int, stage_number: int) -> None:
    sq_conn = get_local_connection()
    try:
        sq_conn.execute(
            "UPDATE courses SET name_ar=?, name_en=?, credit_hours=?, department_id=?, stage_number=? WHERE id=?",
            (name_ar, name_en, credit_hours, dept_id, stage_number, course_id)
        )
        sq_conn.commit()
    finally:
        sq_conn.close()

def search_offline_students_paginated(db_path: str, search_term: str, limit: int = 25, offset: int = 0) -> list[dict]:
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
            ORDER BY CASE WHEN s.id < 0 THEN 1 ELSE 0 END DESC, ABS(s.id) DESC
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
        fallback_query = query.replace(
            "( SELECT id, full_name_ar, full_name_en, graduation_date, average, department_id FROM students UNION ALL SELECT id, full_name_ar, full_name_en, graduation_date, average, department_id FROM local_students ) s",
            "students s"
        ).replace(
            "(\n                SELECT id, full_name_ar, full_name_en, graduation_date, average, department_id FROM students\n                UNION ALL\n                SELECT id, full_name_ar, full_name_en, graduation_date, average, department_id FROM local_students\n            ) s",
            "students s"
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

def get_offline_last_added_students(limit: int = 5) -> list[dict]:
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
        "ORDER BY CASE WHEN s.id < 0 THEN 1 ELSE 0 END DESC, ABS(s.id) DESC LIMIT ?"
    )
    return sqlite_read_all(query, (limit,)) or []

def get_offline_student_supplemental_graduation(student_ids: list[int]) -> dict[int, dict]:
    if not student_ids:
        return {}
    conn = get_local_connection()
    try:
        cursor = conn.cursor()
        format_strings = ','.join(['?'] * len(student_ids))
        query = f"SELECT id, sequence_number, postgraduation_number FROM students WHERE id IN ({format_strings})"
        cursor.execute(query, tuple(student_ids))
        supp_data = {row["id"]: dict(row) for row in cursor.fetchall()}
        return supp_data
    finally:
        conn.close()

def get_offline_students_paginated(limit: int = 25, offset: int = 0, name_query: str = "", dept_id: int = None, year: str | int | None = None) -> list[dict]:
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
    
    return sqlite_read_all(
        "SELECT s.id, s.full_name_ar, s.full_name_en, s.admission_year, s.graduation_year, s.average, s.order_id, "
        "d.name_ar AS dept_name_ar "
        "FROM (SELECT id, full_name_ar, full_name_en, CAST(admission_year AS TEXT) AS admission_year, CAST(strftime('%Y', graduation_date) AS TEXT) AS graduation_year, average, order_id, department_id FROM students "
        "      UNION ALL "
        "      SELECT id, full_name_ar, full_name_en, CAST(admission_year AS TEXT) AS admission_year, CAST(strftime('%Y', graduation_date) AS TEXT) AS graduation_year, average, order_id, department_id FROM local_students) s "
        "LEFT JOIN departments d ON s.department_id = d.id "
        f"{where} ORDER BY CASE WHEN s.id < 0 THEN 1 ELSE 0 END DESC, ABS(s.id) DESC LIMIT ? OFFSET ?", tuple(params)
    ) or []

def get_offline_student_by_id(student_id: int) -> dict | None:
    return sqlite_read_one(
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

def search_offline_students(query: str, limit: int = 8) -> list[dict]:
    clean_query = query.strip()
    if len(clean_query) < 2:
        return []

    exact_match = clean_query
    prefix_match = f"{clean_query}%"
    fuzzy_match = f"%{clean_query}%"
    
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
    return sqlite_read_all(sqlite_query, params) or []

def get_offline_student_statistics_by_department() -> list[dict]:
    return sqlite_read_all(
        "SELECT d.id AS department_id, d.name_ar AS dept_name_ar, "
        "COUNT(s.id) AS total_students, "
        "SUM(CASE WHEN s.order_id IS NOT NULL THEN 1 ELSE 0 END) AS graduated_count, "
        "AVG(s.average) AS average_gpa "
        "FROM departments d "
        "LEFT JOIN (SELECT id, order_id, average, department_id FROM students UNION ALL SELECT id, order_id, average, department_id FROM local_students) s ON d.id = s.department_id "
        "GROUP BY d.id ORDER BY d.name_ar"
    ) or []

def get_offline_unlinked_students(dept_id: int, year: str | int) -> list[dict]:
    return sqlite_read_all(
        "SELECT id, full_name_ar, full_name_en, admission_year, average, sequence_number, postgraduation_number "
        "FROM (SELECT id, full_name_ar, full_name_en, admission_year, average, sequence_number, postgraduation_number, order_id, department_id, graduation_date FROM students "
        "      UNION ALL "
        "      SELECT id, full_name_ar, full_name_en, admission_year, average, sequence_number, postgraduation_number, order_id, department_id, graduation_date FROM local_students) "
        "WHERE department_id = ? AND strftime('%Y', graduation_date) = ? AND (order_id IS NULL OR order_id = 0) "
        "ORDER BY average DESC",
        (dept_id, str(year))
    ) or []

def link_offline_students_to_order(student_ids: list[int], order_id: int) -> None:
    for student_id in student_ids:
        sqlite_read_all("UPDATE students SET order_id = ? WHERE id = ?", (order_id, student_id))
        sqlite_read_all("UPDATE local_students SET order_id = ? WHERE id = ?", (order_id, student_id))

def unlink_offline_students_from_order(student_ids: list[int]) -> None:
    for student_id in student_ids:
        sqlite_read_all("UPDATE students SET order_id = NULL WHERE id = ?", (student_id,))
        sqlite_read_all("UPDATE local_students SET order_id = NULL WHERE id = ?", (student_id,))

def get_offline_students_by_order_id(order_id: int, limit: int = 25, offset: int = 0) -> list[dict]:
    sqlite_query = """
        SELECT 
            s.id AS student_id, 
            s.full_name_ar AS name_ar, 
            s.full_name_en AS name_en, 
            d.name_ar AS dept_name_ar, 
            strftime('%Y', s.graduation_date) AS graduation_year, 
            s.average
        FROM (
            SELECT id, full_name_ar, full_name_en, graduation_date, average, department_id, order_id FROM students
            UNION ALL
            SELECT id, full_name_ar, full_name_en, graduation_date, average, department_id, order_id FROM local_students
        ) s
        LEFT JOIN departments d ON s.department_id = d.id
        WHERE s.order_id = ?
        ORDER BY s.id DESC
        LIMIT ? OFFSET ?
    """
    return sqlite_read_all(sqlite_query, (order_id, limit, offset)) or []

def search_offline_students_by_order(order_id: int, query: str = "", limit: int = 25, offset: int = 0) -> list[dict]:
    clean_query = query.strip()
    if not clean_query:
        return get_offline_students_by_order_id(order_id, limit=limit, offset=offset)

    sqlite_query = """
        SELECT 
            s.id AS student_id, 
            s.full_name_ar AS name_ar, 
            s.full_name_en AS name_en, 
            d.name_ar AS dept_name_ar, 
            strftime('%Y', s.graduation_date) AS graduation_year, 
            s.average
        FROM (
            SELECT id, full_name_ar, full_name_en, graduation_date, average, department_id, order_id FROM students
            UNION ALL
            SELECT id, full_name_ar, full_name_en, graduation_date, average, department_id, order_id FROM local_students
        ) s
        LEFT JOIN departments d ON s.department_id = d.id
        WHERE s.order_id = ?
          AND (s.full_name_ar LIKE ? OR s.full_name_en LIKE ?)
        ORDER BY s.id DESC
        LIMIT ? OFFSET ?
    """
    pattern = f"%{clean_query}%"
    return sqlite_read_all(sqlite_query, (order_id, pattern, pattern, limit, offset)) or []

def get_offline_distinct_admission_years() -> list[str]:
    rows = sqlite_read_all(
        "SELECT DISTINCT strftime('%Y', graduation_date) AS admission_year FROM students WHERE graduation_date IS NOT NULL "
        "UNION "
        "SELECT DISTINCT strftime('%Y', graduation_date) AS admission_year FROM local_students WHERE graduation_date IS NOT NULL "
        "ORDER BY admission_year DESC"
    ) or []
    unique_years = list(set(str(r["admission_year"]) for r in rows if r.get("admission_year") is not None))
    unique_years.sort(key=lambda x: int(x) if x.isdigit() else 0, reverse=True)
    return unique_years

def delete_offline_student(student_id: int) -> None:
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

def get_offline_academic_periods_by_student(student_id: int | str) -> list[dict]:
    try:
        sid = int(student_id)
    except (ValueError, TypeError):
        sid = student_id
    return sqlite_read_all(
        "SELECT id, student_id, academic_year, study_system_id, stage_number, semester_num, COALESCE(result_status, 'PASSED') AS result_status FROM ("
        "  SELECT id, student_id, academic_year, study_system_id, stage_number, semester_num, result_status FROM academic_periods "
        "  UNION ALL "
        "  SELECT id, student_id, academic_year, study_system_id, stage_number, semester_num, result_status FROM local_academic_periods"
        ") WHERE CAST(student_id AS INTEGER) = CAST(? AS INTEGER) OR student_id = ? ORDER BY stage_number, semester_num",
        (sid, str(student_id))
    ) or []

def update_offline_academic_period_status(period_id: int, result_status_key: str) -> None:
    conn = get_local_connection()
    try:
        if period_id < 0:
            try:
                conn.execute("UPDATE local_academic_periods SET result_status = ? WHERE id = ?", (result_status_key, period_id))
            except sqlite3.OperationalError as oe:
                if "no such column" in str(oe).lower():
                    conn.execute("ALTER TABLE local_academic_periods ADD COLUMN result_status TEXT DEFAULT 'PASSED'")
                    conn.execute("UPDATE local_academic_periods SET result_status = ? WHERE id = ?", (result_status_key, period_id))
                else:
                    raise
        else:
            try:
                conn.execute("UPDATE academic_periods SET result_status = ? WHERE id = ?", (result_status_key, period_id))
            except sqlite3.OperationalError as oe:
                if "no such column" in str(oe).lower():
                    conn.execute("ALTER TABLE academic_periods ADD COLUMN result_status TEXT DEFAULT 'PASSED'")
                    conn.execute("UPDATE academic_periods SET result_status = ? WHERE id = ?", (result_status_key, period_id))
                else:
                    raise
        conn.commit()
    finally:
        conn.close()

def update_offline_academic_period_stage(period_id: int, stage_number: int) -> None:
    conn = get_local_connection()
    try:
        if period_id < 0:
            conn.execute("UPDATE local_academic_periods SET stage_number = ? WHERE id = ?", (stage_number, period_id))
        else:
            conn.execute("UPDATE academic_periods SET stage_number = ? WHERE id = ?", (stage_number, period_id))
        conn.commit()
    finally:
        conn.close()

def get_offline_enrollments_by_period(period_id: int | str) -> list[dict]:
    try:
        pid = int(period_id)
    except (ValueError, TypeError):
        pid = period_id
    return sqlite_read_all(
        "SELECT e.id, e.period_id, e.course_id, e.score, e.passed_round, "
        "       CASE WHEN e.passed_round != '1' THEN 1 ELSE 0 END AS is_second_round, "
        "       c.name_ar AS course_name_ar, c.name_en AS course_name_en, c.credit_hours "
        "FROM ("
        "  SELECT id, period_id, course_id, score, passed_round FROM enrollments "
        "  UNION ALL "
        "  SELECT id, period_id, course_id, score, passed_round FROM local_enrollments"
        ") e "
        "LEFT JOIN courses c ON CAST(e.course_id AS INTEGER) = CAST(c.id AS INTEGER) "
        "WHERE CAST(e.period_id AS INTEGER) = CAST(? AS INTEGER) OR e.period_id = ? "
        "ORDER BY c.name_ar",
        (pid, str(period_id))
    ) or []

def update_offline_enrollment(enrollment_id: int, score: float, passed_round: str) -> None:
    sq_conn = get_local_connection()
    try:
        sq_conn.execute("UPDATE enrollments SET score = ?, passed_round = ? WHERE id = ?", (float(score), passed_round, enrollment_id))
        sq_conn.execute("UPDATE local_enrollments SET score = ?, passed_round = ? WHERE id = ?", (float(score), passed_round, enrollment_id))
        sq_conn.commit()
    finally:
        sq_conn.close()

def get_offline_graduation_orders(limit: int = 25, offset: int = 0) -> list[dict]:
    return sqlite_read_all(
        "SELECT o.*, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en, "
        "(SELECT COUNT(*) FROM students s WHERE s.order_id = o.id) AS linked_count "
        "FROM graduation_orders o "
        "LEFT JOIN departments d ON o.department_id = d.id "
        "ORDER BY o.id DESC LIMIT ? OFFSET ?",
        (limit, offset)
    ) or []

def get_offline_graduation_order_by_id(order_id: int) -> dict | None:
    return sqlite_read_one(
        "SELECT o.*, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en "
        "FROM graduation_orders o "
        "LEFT JOIN departments d ON o.department_id = d.id "
        "WHERE o.id = ?",
        (order_id,)
    )

def get_offline_audit_logs() -> list[dict]:
    try:
        return sqlite_read_all("SELECT id, user, action, details, timestamp FROM audit_log ORDER BY id DESC LIMIT 100")
    except Exception:
        return []

def get_offline_study_routines(dept_id: int = None, sys_id: int = None) -> list[dict]:
    query = """
        SELECT sr.id, sr.name_ar, sr.name_en,
               sr.department_id, sr.study_system_id,
               d.name_ar AS dept_name_ar, d.name_en AS dept_name_en,
               ss.name_ar AS study_system_name_ar, ss.name_en AS study_system_name_en, ss.study_day_type AS study_type
        FROM study_routines sr
        LEFT JOIN departments d ON sr.department_id = d.id
        LEFT JOIN study_systems ss ON sr.study_system_id = ss.id
        WHERE (sr.department_id = ? OR ? IS NULL)
          AND (sr.study_system_id = ? OR ? IS NULL)
        ORDER BY sr.id DESC
    """
    return sqlite_read_all(query, (dept_id, dept_id, sys_id, sys_id)) or []

def get_offline_study_routine_by_id(routine_id: int) -> dict | None:
    query = """
        SELECT sr.id, sr.name_ar, sr.name_en,
               sr.department_id, sr.study_system_id,
               d.name_ar AS dept_name_ar, d.name_en AS dept_name_en,
               ss.name_ar AS study_system_name_ar, ss.name_en AS study_system_name_en, ss.study_day_type AS study_type
        FROM study_routines sr
        LEFT JOIN departments d ON sr.department_id = d.id
        LEFT JOIN study_systems ss ON sr.study_system_id = ss.id
        WHERE sr.id = ?
    """
    return sqlite_read_one(query, (routine_id,))

def get_offline_study_routine_periods(routine_id: int | str) -> list[dict]:
    try:
        rid = int(routine_id)
    except (ValueError, TypeError):
        rid = routine_id
    query = "SELECT id, routine_id, stage_number, semester_num FROM study_routine_period WHERE CAST(routine_id AS INTEGER) = CAST(? AS INTEGER) OR routine_id = ? ORDER BY stage_number, semester_num"
    return sqlite_read_all(query, (rid, str(routine_id))) or []

def get_offline_study_routine_period_courses(period_id: int | str) -> list[dict]:
    try:
        pid = int(period_id)
    except (ValueError, TypeError):
        pid = period_id
    query = """
        SELECT src.id, src.period_id, src.course_id,
               c.name_ar AS course_name_ar, c.name_en AS course_name_en, c.credit_hours, c.stage_number
        FROM study_routine_courses src
        LEFT JOIN courses c ON CAST(src.course_id AS INTEGER) = CAST(c.id AS INTEGER)
        WHERE CAST(src.period_id AS INTEGER) = CAST(? AS INTEGER) OR src.period_id = ?
        ORDER BY c.name_ar
    """
    return sqlite_read_all(query, (pid, str(period_id))) or []

def insert_offline_study_routine(name_ar: str, name_en: str, dept_id: int, sys_id: int) -> int:
    conn = get_local_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO study_routines (name_ar, name_en, department_id, study_system_id) VALUES (?, ?, ?, ?)",
            (name_ar, name_en, dept_id, sys_id)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def update_offline_study_routine(routine_id: int, name_ar: str, name_en: str, dept_id: int, sys_id: int) -> None:
    conn = get_local_connection()
    try:
        conn.execute(
            "UPDATE study_routines SET name_ar = ?, name_en = ?, department_id = ?, study_system_id = ? WHERE id = ?",
            (name_ar, name_en, dept_id, sys_id, routine_id)
        )
        conn.commit()
    finally:
        conn.close()

def delete_offline_study_routine(routine_id: int) -> None:
    conn = get_local_connection()
    try:
        conn.execute("DELETE FROM study_routine_courses WHERE period_id IN (SELECT id FROM study_routine_period WHERE routine_id = ?)", (routine_id,))
        conn.execute("DELETE FROM study_routine_period WHERE routine_id = ?", (routine_id,))
        conn.execute("DELETE FROM study_routines WHERE id = ?", (routine_id,))
        conn.commit()
    finally:
        conn.close()

def count_offline_students(name_query: str = "", dept_id: int | None = None, year: str | int | None = None) -> int:
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

def search_offline_unlinked_students(name_query: str = "", dept_id: int | None = None, year: int | None = None, limit: int = 50) -> list[dict]:
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
    return sqlite_read_all(sqlite_query, tuple(sqlite_params)) or []

def get_offline_unlinked_students_matching(dept_id: int | None = None, grad_year: str | int | None = None) -> list[dict]:
    conditions = ["(s.order_id IS NULL OR s.order_id = 0)"]
    params = []
    if dept_id:
        conditions.append("s.department_id = ?")
        params.append(dept_id)
    if grad_year:
        conditions.append("(s.graduation_year = ? OR s.admission_year = ?)")
        params += [str(grad_year), str(grad_year)]

    where = "WHERE " + " AND ".join(conditions)
    return sqlite_read_all(f"""
        SELECT s.id FROM (
            SELECT id, department_id, order_id, CAST(strftime('%Y', graduation_date) AS TEXT) AS graduation_year, CAST(admission_year AS TEXT) AS admission_year FROM students
            UNION ALL
            SELECT id, department_id, order_id, CAST(strftime('%Y', graduation_date) AS TEXT) AS graduation_year, CAST(admission_year AS TEXT) AS admission_year FROM local_students
        ) s {where}
    """, tuple(params)) or []

def get_offline_dashboard_counts() -> dict:
    fallback_query = (
        "SELECT "
        "(SELECT COUNT(id) FROM students) AS total_students, "
        "(SELECT COUNT(id) FROM departments) AS total_departments, "
        "(SELECT COUNT(id) FROM courses) AS total_courses, "
        "(SELECT COUNT(id) FROM personnel) AS total_personnel"
    )
    row = sqlite_read_one(fallback_query)
    return dict(row) if row else {"total_students": 0, "total_departments": 0, "total_courses": 0, "total_personnel": 0}

def insert_offline_study_routine_period(routine_id: int, stage: int, sem_num: int) -> int:
    conn = get_local_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO study_routine_period (routine_id, stage_number, semester_num) VALUES (?, ?, ?)",
            (routine_id, stage, sem_num)
        )
        local_id = cur.lastrowid
        conn.commit()
        return local_id
    finally:
        conn.close()

def insert_offline_study_routine_period_course(period_id: int, course_id: int) -> None:
    conn = get_local_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO study_routine_courses (period_id, course_id) VALUES (?, ?)",
            (period_id, course_id)
        )
        conn.commit()
    finally:
        conn.close()

def delete_offline_study_routine_period(period_id: int) -> None:
    conn = get_local_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM study_routine_courses WHERE period_id = ?", (period_id,))
        cur.execute("DELETE FROM study_routine_period WHERE id = ?", (period_id,))
        conn.commit()
    finally:
        conn.close()

def delete_offline_study_routine_period_course(period_id: int, course_id: int) -> None:
    conn = get_local_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM study_routine_courses WHERE period_id = ? AND course_id = ?", (period_id, course_id))
        conn.commit()
    finally:
        conn.close()

def delete_offline_academic_period(period_id: int) -> None:
    """Delete academic period and its enrollments from local SQLite database replica & cache tables."""
    conn = get_local_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM enrollments WHERE period_id = ?", (period_id,))
        cur.execute("DELETE FROM local_enrollments WHERE period_id = ?", (period_id,))
        cur.execute("DELETE FROM academic_periods WHERE id = ?", (period_id,))
        cur.execute("DELETE FROM local_academic_periods WHERE id = ?", (period_id,))
        conn.commit()
    finally:
        conn.close()


