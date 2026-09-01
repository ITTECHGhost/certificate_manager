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


DEFAULT_QUERY = """
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
    COALESCE(ap.result_status, 'PASSED') AS result_status_code,
    COALESCE(c.name_en, '') AS course_name_en, 
    COALESCE(c.name_ar, '') AS course_name_ar,
    COALESCE(c.credit_hours, 0) AS unit, 
    MAX(COALESCE(e.score, 0.0)) AS mark,
    MAX(COALESCE(e.passed_round, 1)) AS passed_round,
    CASE WHEN COALESCE(c.stage_number, ap.stage_number) < ap.stage_number THEN 'عبور' ELSE 'أساسي' END AS course_type,
    c.id AS course_id, 
    '' AS course_code
FROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap
JOIN (SELECT * FROM enrollments UNION ALL SELECT * FROM local_enrollments) e ON e.period_id = ap.id
JOIN courses c ON e.course_id = c.id
WHERE ap.student_id = ? AND e.score >= 50
GROUP BY e.course_id
ORDER BY ap.stage_number ASC, COALESCE(ap.semester_num, 1) ASC, c.name_ar ASC
"""


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
    settings = sqlite_read_one("SELECT * FROM university_settings WHERE id = 1")
    if settings:
        response_data["settings"] = [settings]

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
        "  FROM local_students "
        ") s "
        "LEFT JOIN departments d    ON s.department_id   = d.id "
        "LEFT JOIN study_systems ss ON s.study_system_id = ss.id "
        "LEFT JOIN countries c      ON s.nationality_id  = c.id "
        "LEFT JOIN governorates g   ON s.birthplace_id   = g.id "
        "LEFT JOIN graduation_orders o ON s.order_id = o.id "
        "WHERE s.student_id = ?",
        (st_id,)
    )
    if not student:
        return response_data
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
        "       GROUP_CONCAT(COALESCE(ap.result_status, 'PASSED')) AS result_status "
        "FROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap "
        "WHERE ap.student_id = ? "
        "GROUP BY ap.academic_year, ap.semester_num "
        "ORDER BY ap.academic_year ASC, ap.semester_num ASC",
        (st_id,)
    )
    response_data["academic_timeline"] = timeline or []

    # 5. Courses
    courses = sqlite_read_all(DEFAULT_QUERY, (st_id,))
    response_data["courses_grouped"] = courses or []

    return response_data


def get_offline_flat_yearly_courses(student_id: int) -> List[Dict[str, Any]]:
    """
    Fetches flat 14-column transcript courses using DEFAULT_QUERY in offline mode.
    """
    st_id = int(student_id)
    raw_rows = sqlite_read_all(DEFAULT_QUERY, (st_id,)) or []

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
