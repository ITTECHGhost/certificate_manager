# =============================================================================
# data/queries.py — Data Access Layer
# =============================================================================
#
# PURPOSE:
#   Every SQL query in the application is written ONCE here as a typed
#   Python function. Screens and widgets call these functions; they never
#   write SQL directly.
#
# BENEFITS FOR OTHER PROGRAMMERS:
#   • Find any query in one file — not scattered across screens
#   • Change a query in one place — all callers automatically updated
#   • Type hints show exactly what each function takes and returns
#   • Easy to unit-test independently of the UI
#
# RETURN TYPES:
#   Functions that return rows use list[dict] — each row is a plain
#   dictionary, so callers access fields by name: row["full_name_ar"].
#   Functions that return a single value return that value directly.
#   Functions that write data return the new row's integer ID or None.
#
# ERROR HANDLING:
#   All functions let sqlite3 exceptions propagate to the caller.
#   The UI layer (screens) catches and displays them to the user.
#   This keeps data logic and display logic cleanly separated.
#
# =============================================================================

import sqlite3
from db import get_connection, insert_audit_log


# =============================================================================
# TYPE ALIAS
# =============================================================================

# A database row as a plain dictionary (column_name → value)
Row = dict


# =============================================================================
# UTILITY
# =============================================================================

def _row_to_dict(row: sqlite3.Row) -> Row:
    """Convert a sqlite3.Row to a plain dict for easy access and testing."""
    return dict(row)


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[Row]:
    """Convert a list of sqlite3.Row objects to a list of plain dicts."""
    return [_row_to_dict(r) for r in rows]


# =============================================================================
# DASHBOARD / HOME
# =============================================================================

def count_table_rows(table: str, extra_filter: str = "") -> int:
    """
    Return the number of rows in any table, with an optional WHERE clause.

    Args:
        table:        Table name (e.g. "students")
        extra_filter: Optional SQL fragment (e.g. "WHERE is_active = 1")

    Returns:
        Integer row count.

    Example:
        count_table_rows("personal", "WHERE is_active = 1")  → 6
    """
    query = f"SELECT COUNT(*) FROM {table} {extra_filter}".strip()
    with get_connection() as conn:
        return conn.execute(query).fetchone()[0]


# =============================================================================
# SETTINGS
# =============================================================================

def get_settings() -> Row:
    """Return the single row from the settings table."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    return _row_to_dict(row)

def update_settings(
    univ_ar: str, univ_en: str, 
    college_ar: str, college_en: str,
    theme: str, accent: str,
    font: str, size: int
) -> None:
    """Update global application settings."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE settings SET "
            "univ_name_ar=?, univ_name_en=?, "
            "college_name_ar=?, college_name_en=?, "
            "theme=?, accent_color=?, "
            "font_family=?, font_size_base=? "
            "WHERE id=1",
            (univ_ar, univ_en, college_ar, college_en, theme, accent, font, size)
        )
        conn.commit()
    insert_audit_log("settings", "UPDATE", "تم تحديث إعدادات النظام والمظهر")

def clear_audit_logs() -> None:
    """Permanently delete all rows from audit_log."""
    with get_connection() as conn:
        conn.execute("DELETE FROM audit_log")
        conn.commit()
    insert_audit_log("audit_log", "DELETE", "تم مسح سجل التغييرات بالكامل")


# =============================================================================
# STUDY SYSTEMS
# =============================================================================

def get_all_study_systems() -> list[Row]:
    """Return all study systems ordered by id."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name_ar, name_en, calculation_rule, calculation_weights, "
            "is_active, created_at, "
            "COALESCE(prefix, '') as prefix, "
            "COALESCE(period_display, 'semester') as period_display "
            "FROM study_systems ORDER BY id"
        ).fetchall()
    return _rows_to_dicts(rows)


def get_active_study_systems() -> list[Row]:
    """Return only active study systems."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name_ar, name_en, calculation_rule, calculation_weights, "
            "COALESCE(prefix, '') as prefix, "
            "COALESCE(period_display, 'semester') as period_display "
            "FROM study_systems WHERE is_active = 1 ORDER BY id"
        ).fetchall()
    return _rows_to_dicts(rows)


def get_study_system_by_id(ss_id: int) -> Row | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name_ar, name_en, calculation_rule, is_active, "
            "COALESCE(prefix, '') as prefix, "
            "COALESCE(period_display, 'semester') as period_display "
            "FROM study_systems WHERE id = ?", (ss_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def insert_study_system(name_ar: str, name_en: str, calculation_rule: str,
                        calculation_weights: str = "10:20:30:40",
                        prefix: str = "", period_display: str = "semester") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO study_systems (name_ar, name_en, calculation_rule, calculation_weights, prefix, period_display) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name_ar, name_en, calculation_rule, calculation_weights, prefix, period_display)
        )
        conn.commit()
        new_id = cur.lastrowid
    insert_audit_log("study_systems", "INSERT", f"تم إضافة نظام دراسة: {name_ar}")
    return new_id


def update_study_system(ss_id: int, name_ar: str, name_en: str, calculation_rule: str,
                        calculation_weights: str, is_active: int,
                        prefix: str = "", period_display: str = "semester") -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE study_systems SET name_ar=?, name_en=?, calculation_rule=?, "
            "calculation_weights=?, is_active=?, prefix=?, period_display=? WHERE id=?",
            (name_ar, name_en, calculation_rule, calculation_weights, is_active,
             prefix, period_display, ss_id)
        )
        conn.commit()
    insert_audit_log("study_systems", "UPDATE", f"تم تعديل نظام الدراسة: {name_ar}")


def toggle_study_system(ss_id: int, is_active: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE study_systems SET is_active=? WHERE id=?", (is_active, ss_id))
        conn.commit()
    insert_audit_log("study_systems", "UPDATE", f"تم تغيير حالة نظام الدراسة ID: {ss_id}")


def delete_study_system(ss_id: int) -> bool:
    """Delete a study system if no students or courses are linked to it."""
    with get_connection() as conn:
        # Check usage
        s_count = conn.execute("SELECT COUNT(*) FROM students WHERE study_system_id = ?", (ss_id,)).fetchone()[0]
        c_count = conn.execute("SELECT COUNT(*) FROM courses WHERE study_system_id = ?", (ss_id,)).fetchone()[0]
        
        if s_count > 0 or c_count > 0:
            return False
            
        conn.execute("DELETE FROM study_systems WHERE id = ?", (ss_id,))
        conn.commit()
    insert_audit_log("study_systems", "DELETE", f"تم حذف نظام الدراسة ID: {ss_id}")
    return True

# =============================================================================
# COUNTRIES
# =============================================================================

def get_all_countries() -> list[Row]:
    """
    Return all countries ordered alphabetically by English name.

    Returns:
        List of dicts with keys: id, name_ar, name_en, iso_code
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name_ar, name_en, iso_code "
            "FROM countries "
            "ORDER BY name_en"
        ).fetchall()
    return _rows_to_dicts(rows)


def get_country_by_id(country_id: int) -> Row | None:
    """Return a single country row by its primary key, or None if not found."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name_ar, name_en, iso_code "
            "FROM countries WHERE id = ?",
            (country_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


# =============================================================================
# GOVERNORATES
# =============================================================================

def get_all_governorates() -> list[Row]:
    """
    Return all 18 Iraqi governorates ordered by their database ID.

    Returns:
        List of dicts with keys: id, name_ar, name_en
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name_ar, name_en "
            "FROM governorates "
            "ORDER BY id"
        ).fetchall()
    return _rows_to_dicts(rows)


# =============================================================================
# DEPARTMENTS
# =============================================================================

def get_all_departments() -> list[Row]:
    """
    Return all departments ordered by Arabic name.

    Returns:
        List of dicts with keys: id, name_ar, name_en, college_ar, college_en, study_years
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name_ar, name_en, college_ar, college_en, study_years "
            "FROM departments ORDER BY name_ar"
        ).fetchall()
    return _rows_to_dicts(rows)


def get_department_by_id(dept_id: int) -> Row | None:
    """Return a single department row by its primary key, or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name_ar, name_en, college_ar, college_en, study_years "
            "FROM departments WHERE id = ?",
            (dept_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def insert_department(
    name_ar: str,
    name_en: str,
    college_ar: str,
    college_en: str,
    study_years: int = 4,
) -> int:
    """Insert a new department and return its new ID."""
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO departments (name_ar, name_en, college_ar, college_en, study_years) "
            "VALUES (?, ?, ?, ?, ?)",
            (name_ar, name_en, college_ar, college_en, study_years)
        )
        conn.commit()
        new_id = cursor.lastrowid
    insert_audit_log("departments", "INSERT", f"تم إضافة قسم جديد: {name_ar}")
    return new_id


def update_department(
    dept_id: int,
    name_ar: str,
    name_en: str,
    college_ar: str,
    college_en: str,
    study_years: int = 4,
) -> None:
    """Update all fields of an existing department row."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE departments "
            "SET name_ar=?, name_en=?, college_ar=?, college_en=?, study_years=? "
            "WHERE id=?",
            (name_ar, name_en, college_ar, college_en, study_years, dept_id)
        )
        conn.commit()
    insert_audit_log("departments", "UPDATE", f"تم تعديل بيانات القسم: {name_ar}")


def delete_department(dept_id: int) -> None:
    """
    Delete a department by ID.
    Raises sqlite3.IntegrityError if students or courses depend on it.
    """
    with get_connection() as conn:
        # 1. Grab the name before we delete it so we can log it
        dept = conn.execute("SELECT name_ar FROM departments WHERE id = ?", (dept_id,)).fetchone()
        dept_name = dept["name_ar"] if dept else f"ID: {dept_id}"
        
        conn.execute("DELETE FROM departments WHERE id = ?", (dept_id,))
        conn.commit()
    insert_audit_log("departments", "DELETE", f"تم حذف القسم: {dept_name}")


# =============================================================================
# PERSONAL (Signatories)
# =============================================================================

def _log_personal_snapshot(conn, action: str, person_id: int) -> None:
    """
    Write a snapshot of the current personal row into personal_log BEFORE
    any change is applied.  Also writes one row to audit_log.
    """
    row = conn.execute(
        "SELECT name_ar, name_en, academic_title_ar, academic_title_en, "
        "       responsibility_ar, responsibility_en, display_order, "
        "       page_location, is_active "
        "FROM personal WHERE id = ?",
        (person_id,)
    ).fetchone()
    if row:
        conn.execute(
            "INSERT INTO personal_log "
            "(action, personal_id, name_ar, name_en, academic_title_ar, academic_title_en, "
            " responsibility_ar, responsibility_en, display_order, page_location, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (action, person_id,
             row["name_ar"], row["name_en"],
             row["academic_title_ar"], row["academic_title_en"],
             row["responsibility_ar"], row["responsibility_en"],
             row["display_order"], row["page_location"], row["is_active"])
        )
    # audit_log only accepts: INSERT, UPDATE, DELETE, ERROR
    audit_action = "UPDATE" if action in ("deactivate", "activate") else action.upper()

    conn.execute(
        "INSERT INTO audit_log (table_name, record_id, action, summary) "
        "VALUES ('personal', ?, ?, ?)",
        (person_id, audit_action,
         f"{action} signatory id={person_id} ({row['name_ar'] if row else '?'})")
    )


def get_active_personal(page_location: str) -> list[Row]:
    """
    Return all currently active signatories for a given page.

    Args:
        page_location: 'front' or 'back'

    Returns:
        List of dicts ordered by display_order, with keys:
            id, name_ar, name_en, academic_title_ar, academic_title_en,
            responsibility_ar, responsibility_en, display_order,
            page_location, is_active
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name_ar, name_en, academic_title_ar, academic_title_en, "
            "       responsibility_ar, responsibility_en, "
            "       display_order, page_location, is_active "
            "FROM personal "
            "WHERE is_active = 1 AND page_location = ? "
            "ORDER BY display_order",
            (page_location,)
        ).fetchall()
    return _rows_to_dicts(rows)


def get_all_personal() -> list[Row]:
    """
    Return all personal records (active and inactive), ordered by
    page_location then display_order. Used in the management screen.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name_ar, name_en, academic_title_ar, academic_title_en, "
            "       responsibility_ar, responsibility_en, "
            "       display_order, page_location, is_active "
            "FROM personal "
            "ORDER BY page_location, display_order"
        ).fetchall()
    return _rows_to_dicts(rows)


def insert_personal(
    name_ar: str,
    name_en: str,
    academic_title_ar: str,
    academic_title_en: str,
    responsibility_ar: str,
    responsibility_en: str,
    display_order: int,
    page_location: str,
) -> int:
    """
    Insert a new signatory and return their new ID.
    New records are always inserted as active (is_active = 1).
    Writes an INSERT row to audit_log.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO personal "
            "(name_ar, name_en, academic_title_ar, academic_title_en, "
            " responsibility_ar, responsibility_en, "
            " display_order, page_location, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (name_ar, name_en, academic_title_ar, academic_title_en,
             responsibility_ar, responsibility_en, display_order, page_location)
        )
        new_id = cursor.lastrowid
        conn.commit()
    insert_audit_log("personal", "INSERT", f"تم إضافة كادر جديد: {name_ar}")
    return new_id


def update_personal(
    person_id: int,
    name_ar: str,
    name_en: str,
    academic_title_ar: str,
    academic_title_en: str,
    responsibility_ar: str,
    responsibility_en: str,
    display_order: int,
    page_location: str,
) -> None:
    """
    Update an existing signatory row IN PLACE.
    Snapshots the old values into personal_log before changing.
    """
    with get_connection() as conn:
        _log_personal_snapshot(conn, "update", person_id)
        conn.execute(
            "UPDATE personal "
            "SET name_ar=?, name_en=?, academic_title_ar=?, academic_title_en=?, "
            "    responsibility_ar=?, responsibility_en=?, "
            "    display_order=?, page_location=? "
            "WHERE id=?",
            (name_ar, name_en, academic_title_ar, academic_title_en,
             responsibility_ar, responsibility_en,
             display_order, page_location, person_id)
        )
        conn.commit()
    insert_audit_log("personal", "UPDATE", f"تم تعديل بيانات الكادر: {name_ar}")


def deactivate_personal(person_id: int) -> None:
    """
    Mark a signatory as inactive (is_active = 0).
    The record is kept for historical audit — not deleted.
    Snapshots the row into personal_log before deactivating.
    """
    with get_connection() as conn:
        _log_personal_snapshot(conn, "deactivate", person_id)
        # 1. Grab the name before we update them so we can log it
        personal = conn.execute("SELECT name_ar FROM personal WHERE id = ?", (person_id,)).fetchone()
        personal_name = personal["name_ar"] if personal else f"ID: {person_id}"
        conn.execute(
            "UPDATE personal SET is_active = 0 WHERE id = ?",
            (person_id,)
        )
        conn.commit()
    insert_audit_log("personal", "UPDATE", f"تم إلغاء تفعيل الكادر: {personal_name}")


def activate_personal(person_id: int) -> None:
    """
    Restore a signatory to active status (is_active = 1).
    """
    with get_connection() as conn:
        _log_personal_snapshot(conn, "activate", person_id)
        personal = conn.execute("SELECT name_ar FROM personal WHERE id = ?", (person_id,)).fetchone()
        personal_name = personal["name_ar"] if personal else f"ID: {person_id}"
        conn.execute(
            "UPDATE personal SET is_active = 1 WHERE id = ?",
            (person_id,)
        )
        conn.commit()
    insert_audit_log("personal", "UPDATE", f"تم إعادة تفعيل الكادر: {personal_name}")


def delete_personal(person_id: int) -> None:
    """Permanently deletes a signatory from the database."""
    with get_connection() as conn:
        # 1. Grab the name before we delete them so we can log it
        personal = conn.execute("SELECT name_ar FROM personal WHERE id = ?", (person_id,)).fetchone()
        personal_name = personal["name_ar"] if personal else f"ID: {person_id}"
        # 2. Delete the personal
        conn.execute("DELETE FROM personal WHERE id = ?", (person_id,))
        conn.commit()
    insert_audit_log("personal", "DELETE", f"تم حذف الكادر: {personal_name}")

# =============================================================================
# AUDIT LOG
# =============================================================================



def get_audit_log(
    table_filter: str = "",
    action_filter: str = "",
    limit: int = 100,
    offset: int = 0,
) -> list[Row]:
    """
    Return audit log rows, newest first.

    Args:
        table_filter:  If non-empty, only rows where table_name = this value.
        action_filter: If non-empty, only rows where action = this value.
        limit:         Max rows to return.
        offset:        Pagination offset.

    Returns:
        List of dicts: id, table_name, record_id, action, summary,
                       error_info, created_at.
    """
    conditions = []
    params: list = []
    if table_filter:
        conditions.append("table_name = ?")
        params.append(table_filter)
    if action_filter:
        conditions.append("action = ?")
        params.append(action_filter)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params += [limit, offset]
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT id, table_name, record_id, action, summary, error_info, created_at "
            f"FROM audit_log {where} "
            f"ORDER BY created_at DESC "
            f"LIMIT ? OFFSET ?",
            params
        ).fetchall()
    return _rows_to_dicts(rows)


def count_audit_log(table_filter: str = "", action_filter: str = "") -> int:
    """Return total matching rows in audit_log (for pagination)."""
    conditions = []
    params: list = []
    if table_filter:
        conditions.append("table_name = ?")
        params.append(table_filter)
    if action_filter:
        conditions.append("action = ?")
        params.append(action_filter)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    with get_connection() as conn:
        return conn.execute(
            f"SELECT COUNT(*) FROM audit_log {where}", params
        ).fetchone()[0]


# =============================================================================
# COURSES
# =============================================================================

def get_courses_by_department(dept_id: int) -> list[Row]:
    """
    Return all courses for a given department, ordered by stage then name.

    Returns:
        List of dicts with keys:
            id, name_ar, name_en, credit_hours,
            department_id, stage_number, study_system_id
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name_ar, name_en, credit_hours, "
            "       department_id, stage_number, study_system_id, is_shared "
            "FROM courses "
            "WHERE department_id = ? "
            "ORDER BY stage_number, name_ar",
            (dept_id,)
        ).fetchall()
    return _rows_to_dicts(rows)


def get_all_courses() -> list[Row]:
    """
    Return all courses across all departments.
    For shared courses (department_id IS NULL), the dept_name_ar column
    shows 'مشتركة (Dept1، Dept2, ...)' listing all linked departments.
    Ordered by dept label then stage then name.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT c.id, c.name_ar, c.name_en, c.credit_hours, "
            "       c.department_id, c.stage_number, c.study_system_id, "
            "       ss.name_ar AS study_system_name_ar, "
            "       ss.calculation_rule, "
            "       CASE WHEN c.department_id IS NOT NULL "
            "            THEN d.name_ar "
            "            ELSE NULL END AS dept_name_ar, "
            "       c.is_shared "
            "FROM courses c "
            "LEFT JOIN departments d ON c.department_id = d.id "
            "LEFT JOIN study_systems ss ON c.study_system_id = ss.id "
            "ORDER BY COALESCE(d.name_ar, 'ي'), c.stage_number, c.name_ar"
        ).fetchall()
        result = []
        for row in rows:
            r = _row_to_dict(row)
            if r.get("is_shared"):
                depts = conn.execute(
                    "SELECT d.name_ar FROM course_departments cd "
                    "JOIN departments d ON cd.department_id = d.id "
                    "WHERE cd.course_id = ? ORDER BY d.name_ar",
                    (r["id"],)
                ).fetchall()
                names = "، ".join(d["name_ar"] for d in depts)
                r["dept_name_ar"] = f"مشتركة ({names})" if names else "مشتركة"
            result.append(r)
    return result


def get_shared_dept_ids(course_id: int) -> list[int]:
    """Return list of department IDs linked to a shared course."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT department_id FROM course_departments WHERE course_id = ?",
            (course_id,)
        ).fetchall()
    return [r["department_id"] for r in rows]


def get_shared_dept_labels(course_id: int) -> list[str]:
    """Return list of 'name_ar / name_en' labels for depts linked to a shared course."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT d.name_ar, d.name_en FROM course_departments cd "
            "JOIN departments d ON cd.department_id = d.id "
            "WHERE cd.course_id = ? ORDER BY d.name_ar",
            (course_id,)
        ).fetchall()
    return [f"{r['name_ar']}  /  {r['name_en']}" for r in rows]


def insert_course(
    name_ar: str,
    name_en: str,
    credit_hours: int,
    department_id: int | None,
    stage_number: int,
    study_system_id: int,
    shared_dept_ids: list[int] | None = None,
) -> int:
    """
    Insert a new course.
    If department_id is None, the course is shared.
    Returns new course ID.
    """
    is_shared = 1 if department_id is None else 0
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO courses "
            "(name_ar, name_en, credit_hours, department_id, stage_number, study_system_id, is_shared) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name_ar, name_en, credit_hours, department_id, stage_number, study_system_id, is_shared)
        )
        new_id = cursor.lastrowid
        if is_shared and shared_dept_ids:
            conn.executemany(
                "INSERT OR IGNORE INTO course_departments (course_id, department_id) VALUES (?, ?)",
                [(new_id, did) for did in shared_dept_ids]
            )
        conn.commit()
    insert_audit_log("courses", "INSERT", f"تم إضافة مادة جديدة: {name_ar}")
    return new_id


def update_course(
    course_id: int,
    name_ar: str,
    name_en: str,
    credit_hours: int,
    department_id: int | None,
    stage_number: int,
    study_system_id: int,
    shared_dept_ids: list[int] | None = None,
) -> None:
    """Update an existing course. Handles shared <-> dedicated transitions."""
    is_shared = 1 if department_id is None else 0
    with get_connection() as conn:
        conn.execute(
            "UPDATE courses "
            "SET name_ar=?, name_en=?, credit_hours=?, "
            "    department_id=?, stage_number=?, study_system_id=?, is_shared=? "
            "WHERE id=?",
            (name_ar, name_en, credit_hours,
             department_id, stage_number, study_system_id, is_shared, course_id)
        )
        conn.execute("DELETE FROM course_departments WHERE course_id=?", (course_id,))
        if is_shared and shared_dept_ids:
            conn.executemany(
                "INSERT OR IGNORE INTO course_departments (course_id, department_id) VALUES (?, ?)",
                [(course_id, did) for did in shared_dept_ids]
            )
        conn.commit()
    insert_audit_log("courses", "UPDATE", f"تم تعديل بيانات المادة: {name_ar}")


def delete_course(course_id: int) -> None:
    """
    Delete a course by ID.
    Raises sqlite3.IntegrityError if enrollments depend on it.
    """
    with get_connection() as conn:
        course = conn.execute("SELECT name_ar FROM courses WHERE id=?", (course_id,)).fetchone()
        course_name = course["name_ar"] if course else f"ID: {course_id}"
        
        conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
        conn.commit()
    insert_audit_log("courses", "DELETE", f"تم حذف المادة: {course_name}")


# =============================================================================
# STUDENTS
# =============================================================================

def search_students(query: str) -> list[Row]:
    """
    Search students by Arabic or English name using a LIKE query.
    Returns up to 50 matches ordered by Arabic name.

    Args:
        query: Partial name string. e.g. "حسين" or "Hussein"

    Returns:
        List of dicts with keys:
            id, full_name_ar, full_name_en, admission_year,
            department_id, dept_name_ar, graduation_date, average
    """
    pattern = f"%{query}%"
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT s.id, s.full_name_ar, s.full_name_en, "
            "       s.admission_year, s.department_id, "
            "       d.name_ar AS dept_name_ar, "
            "       s.graduation_date, s.average "
            "FROM students s "
            "LEFT JOIN departments d ON s.department_id = d.id "
            "WHERE s.full_name_ar LIKE ? OR s.full_name_en LIKE ? "
            "ORDER BY s.full_name_ar "
            "LIMIT 50",
            (pattern, pattern)
        ).fetchall()
    return _rows_to_dicts(rows)


def get_student_by_id(student_id: int) -> Row | None:
    """
    Return a full student record joined with department, study system,
    and location names. Returns None if not found.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT s.*, "
            "       d.name_ar  AS dept_name_ar, "
            "       d.name_en  AS dept_name_en, "
            "       ss.name_ar AS study_system_name_ar, "
            "       ss.name_en AS study_system_name_en, "
            "       ss.calculation_rule, "
            "       g.name_ar  AS birthplace_ar, "
            "       g.name_en  AS birthplace_en, "
            "       c.name_ar  AS nationality_ar, "
            "       c.name_en  AS nationality_en "
            "FROM students s "
            "LEFT JOIN departments d   ON s.department_id   = d.id "
            "LEFT JOIN study_systems ss ON s.study_system_id = ss.id "
            "LEFT JOIN governorates g  ON s.birthplace_id   = g.id "
            "LEFT JOIN countries    c  ON s.nationality_id  = c.id "
            "WHERE s.id = ?",
            (student_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def insert_student(
    full_name_ar: str,
    full_name_en: str,
    date_of_birth: str,
    birthplace_id: int | None,
    birthplace_other: str | None,
    nationality_id: int,
    department_id: int,
    study_system_id: int,
    admission_year: int,
    study_type: str,
    graduation_date: str | None = None,
    graduation_semester: str | None = None,
    average: int | None = None,
) -> int:
    """Insert a new student and return the new student ID."""
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO students "
            "(full_name_ar, full_name_en, date_of_birth, birthplace_id, "
            " birthplace_other, nationality_id, department_id, study_system_id, "
            " admission_year, study_type, graduation_date, graduation_semester, average) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (full_name_ar, full_name_en, date_of_birth, birthplace_id,
             birthplace_other, nationality_id, department_id, study_system_id,
             admission_year, study_type, graduation_date, graduation_semester, average)
        )
        conn.commit()
        new_id = cursor.lastrowid
    insert_audit_log("students", "INSERT", f"تم إضافة طالب جديد: {full_name_ar}")
    return new_id


def update_student(student_id: int, **fields) -> None:
    """
    Update one or more fields on a student record.
    """
    if not fields:
        return

    set_clause = ", ".join(f"{col} = ?" for col in fields)
    values = list(fields.values()) + [student_id]

    with get_connection() as conn:
        conn.execute(
            f"UPDATE students SET {set_clause} WHERE id = ?",
            values
        )
        conn.commit()
    # ---> Log student update (FIXED BUG: changed kwargs to fields) <---     
    insert_audit_log("students", "UPDATE", f"تم تعديل بيانات الطالب: {fields.get('full_name_ar', 'ID: ' + str(student_id))}")


# =============================================================================
# ACADEMIC PERIODS
# =============================================================================

def get_periods_for_student(student_id: int) -> list[Row]:
    """
    Return all academic periods for a student, ordered by stage number.

    Returns:
        List of dicts with keys:
            id, student_id, academic_year, study_system_id,
            stage_number, passed_round
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, student_id, academic_year, "
            "       study_system_id, stage_number, passed_round "
            "FROM academic_periods "
            "WHERE student_id = ? "
            "ORDER BY stage_number",
            (student_id,)
        ).fetchall()
    return _rows_to_dicts(rows)


def insert_period(
    student_id: int,
    academic_year: str,
    study_system_id: int,
    stage_number: int,
    passed_round: str,
) -> int:
    """Insert one academic period and return its new ID."""
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO academic_periods "
            "(student_id, academic_year, study_system_id, stage_number, passed_round) "
            "VALUES (?, ?, ?, ?, ?)",
            (student_id, academic_year, study_system_id, stage_number, passed_round)
        )
        conn.commit()
        new_id = cursor.lastrowid
    insert_audit_log("academic_periods", "INSERT", f"تم إضافة مرحلة دراسية جديدة للطالب ID: {student_id}")
    return new_id


# =============================================================================
# ENROLLMENTS
# =============================================================================

def get_enrollments_for_period(period_id: int) -> list[Row]:
    """
    Return all course enrollments for one academic period,
    joined with course details.

    Returns:
        List of dicts with keys:
            id, period_id, course_id, score, is_second_round,
            course_name_ar, course_name_en, credit_hours
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT e.id, e.period_id, e.course_id, e.score, e.is_second_round, "
            "       c.name_ar AS course_name_ar, "
            "       c.name_en AS course_name_en, "
            "       c.credit_hours "
            "FROM enrollments e "
            "JOIN courses c ON e.course_id = c.id "
            "WHERE e.period_id = ? "
            "ORDER BY c.name_ar",
            (period_id,)
        ).fetchall()
    return _rows_to_dicts(rows)


def insert_enrollment(
    period_id: int,
    course_id: int,
    score: float,
    is_second_round: int = 0,
) -> int:
    """
    Insert a single course enrollment and return its new ID.

    Args:
        period_id:       FK to academic_periods.id
        course_id:       FK to courses.id
        score:           Numeric score 0–100
        is_second_round: 1 if passed via resit exam, 0 otherwise
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO enrollments (period_id, course_id, score, is_second_round) "
            "VALUES (?, ?, ?, ?)",
            (period_id, course_id, score, is_second_round)
        )
        conn.commit()
        new_id = cursor.lastrowid
    insert_audit_log("enrollments", "INSERT", f"تم إضافة درجة مادة جديدة للمرحلة ID: {period_id}")
    return new_id


def delete_enrollment(enrollment_id: int) -> None:
    """Delete a single enrollment row by its primary key."""
    with get_connection() as conn:
        conn.execute("DELETE FROM enrollments WHERE id = ?", (enrollment_id,))
        conn.commit()
    insert_audit_log("enrollments", "DELETE", f"تم حذف درجة مادة ID: {enrollment_id}")


# =============================================================================
# CERTIFICATE COMPUTATION QUERIES
# =============================================================================

def get_graduate_rank(student_id: int) -> tuple[int, int]:
    """
    Compute a student's rank among graduates from the same department
    and admission year, sorted by average descending.

    Returns:
        Tuple (rank, total_graduates)
        e.g. (3, 45) means 3rd out of 45 graduates.
        Returns (0, 0) if the student has no average set.
    """
    with get_connection() as conn:
        # Get the student's department and admission year
        student = conn.execute(
            "SELECT department_id, admission_year, average "
            "FROM students WHERE id = ?",
            (student_id,)
        ).fetchone()

        if not student or student["average"] is None:
            return (0, 0)

        # Count graduates with a higher average in the same group
        rank = conn.execute(
            "SELECT COUNT(*) FROM students "
            "WHERE department_id = ? "
            "  AND admission_year = ? "
            "  AND graduation_date IS NOT NULL "
            "  AND average > ?",
            (student["department_id"],
             student["admission_year"],
             student["average"])
        ).fetchone()[0] + 1  # +1 because rank starts at 1

        # Count total graduates in the same group
        total = conn.execute(
            "SELECT COUNT(*) FROM students "
            "WHERE department_id = ? "
            "  AND admission_year = ? "
            "  AND graduation_date IS NOT NULL",
            (student["department_id"], student["admission_year"])
        ).fetchone()[0]

    return (rank, total)


def get_top_graduate_average(department_id: int, admission_year: int) -> float | None:
    """
    Return the highest average among graduates in the same
    department and admission year.
    Returns None if no graduates exist in that group.
    """
    with get_connection() as conn:
        result = conn.execute(
            "SELECT MAX(average) FROM students "
            "WHERE department_id = ? "
            "  AND admission_year = ? "
            "  AND graduation_date IS NOT NULL",
            (department_id, admission_year)
        ).fetchone()[0]
    return result


# =============================================================================
# GRADUATION ORDERS  (أوامر التخرج الجامعية)
# =============================================================================

def get_all_orders() -> list[Row]:
    """
    Return all graduation orders joined with their department name,
    ordered by most recent first.

    Returns:
        List of dicts with keys:
            id, order_number, order_date, department_id, dept_name_ar,
            dept_name_en, study_type, admission_year, graduation_semester,
            num_students, notes, linked_count
        Where linked_count = number of students currently linked to this order.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT o.id, o.order_number, o.order_date, "
            "       o.department_id, d.name_ar AS dept_name_ar, "
            "       d.name_en AS dept_name_en, "
            "       o.study_type, o.admission_year, o.graduation_semester, "
            "       o.num_students, o.notes, "
            "       COUNT(s.id) AS linked_count "
            "FROM graduation_orders o "
            "JOIN departments d ON o.department_id = d.id "
            "LEFT JOIN students s ON s.order_id = o.id "
            "GROUP BY o.id "
            "ORDER BY o.order_date DESC, o.id DESC"
        ).fetchall()
    return _rows_to_dicts(rows)


def get_order_by_id(order_id: int) -> Row | None:
    """Return a single graduation order with department details, or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT o.*, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en "
            "FROM graduation_orders o "
            "JOIN departments d ON o.department_id = d.id "
            "WHERE o.id = ?",
            (order_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def insert_order(
    order_number: str,
    order_date: str,
    department_id: int,
    study_type: str,
    admission_year: int,
    graduation_semester: str,
    num_students: int | None = None,
    notes: str | None = None,
) -> int:
    """
    Insert a new graduation order and return its new ID.

    Args:
        order_number:        Official order number, e.g. "18515/13/2"
        order_date:          Date in YYYY-MM-DD format
        department_id:       FK → departments.id
        study_type:          'morning' or 'evening'
        admission_year:      The batch/دفعة year, e.g. 2018
        graduation_semester: 'first' or 'second'
        num_students:        Expected student count from the document (optional)
        notes:               Any extra remarks (optional)
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO graduation_orders "
            "(order_number, order_date, department_id, study_type, "
            " admission_year, graduation_semester, num_students, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (order_number, order_date, department_id, study_type,
             admission_year, graduation_semester, num_students, notes)
        )
        conn.commit()
        new_id = cursor.lastrowid
    insert_audit_log("graduation_orders", "INSERT", f"تم إضافة أمر جامعي جديد: {order_number}")
    return new_id


def update_order(
    order_id: int,
    order_number: str,
    order_date: str,
    department_id: int,
    study_type: str,
    admission_year: int,
    graduation_semester: str,
    num_students: int | None = None,
    notes: str | None = None,
) -> None:
    """Update all fields of an existing graduation order row."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE graduation_orders "
            "SET order_number=?, order_date=?, department_id=?, study_type=?, "
            "    admission_year=?, graduation_semester=?, num_students=?, notes=? "
            "WHERE id=?",
            (order_number, order_date, department_id, study_type,
             admission_year, graduation_semester, num_students, notes, order_id)
        )
        conn.commit()
    insert_audit_log("graduation_orders", "UPDATE", f"تم تعديل بيانات الأمر الجامعي: {order_number}")


def delete_order(order_id: int) -> None:
    """
    Delete a graduation order.
    First unlinks all students that reference it (sets their order_id to NULL)
    so no orphaned FK references remain.
    """
    with get_connection() as conn:
        # 1. Grab order number for logging
        order = conn.execute("SELECT order_number FROM graduation_orders WHERE id = ?", (order_id,)).fetchone()
        order_num = order["order_number"] if order else f"ID: {order_id}"
        
        conn.execute(
            "UPDATE students SET order_id = NULL WHERE order_id = ?",
            (order_id,)
        )
        conn.execute("DELETE FROM graduation_orders WHERE id = ?", (order_id,))
        conn.commit()
    insert_audit_log("graduation_orders", "DELETE", f"تم حذف الأمر الجامعي: {order_num}")


def get_students_for_order(order_id: int) -> list[Row]:
    """
    Return all students currently linked to a graduation order.

    Returns:
        List of dicts with keys:
            id, full_name_ar, full_name_en, average, graduation_date,
            graduation_semester, dept_name_ar
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT s.id, s.full_name_ar, s.full_name_en, s.average, "
            "       s.graduation_date, s.graduation_semester, "
            "       d.name_ar AS dept_name_ar "
            "FROM students s "
            "JOIN departments d ON s.department_id = d.id "
            "WHERE s.order_id = ? "
            "ORDER BY s.average DESC NULLS LAST",
            (order_id,)
        ).fetchall()
    return _rows_to_dicts(rows)


def link_students_to_order(order_id: int) -> int:
    """
    Automatically link all students that match the order's
    department + admission_year + graduation_semester to this order.

    Only links students that do NOT already have an order assigned.
    Also sets graduation_date and graduation_semester on matched students
    from the order record.

    Returns:
        Number of students linked.
    """
    order = get_order_by_id(order_id)
    if not order:
        return 0

    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE students "
            "SET order_id = ?, "
            "    graduation_date = ?, "
            "    graduation_semester = ? "
            "WHERE department_id = ? "
            "  AND admission_year = ? "
            "  AND study_type = ? "
            "  AND order_id IS NULL",
            (
                order_id,
                order["order_date"],
                order["graduation_semester"],
                order["department_id"],
                order["admission_year"],
                order["study_type"],
            )
        )
        conn.commit()
        count = cursor.rowcount
    if count > 0:
        insert_audit_log("students", "UPDATE", f"تم ربط {count} طالب بالأمر الجامعي ID: {order_id}")
    return count


def unlink_student_from_order(student_id: int) -> None:
    """Remove the order assignment from a single student."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE students SET order_id = NULL WHERE id = ?",
            (student_id,)
        )
        conn.commit()
    insert_audit_log("students", "UPDATE", f"تم فك ارتباط الطالب ID: {student_id} بالأمر الجامعي")


def import_students_from_order_excel(
    order_id: int,
    student_rows: list[dict],
    department_id: int,
    default_nationality_id: int,
) -> tuple[int, int]:
    """
    Bulk-import students from an Excel file that came with the graduation order.

    For each row in student_rows, the function:
        1. Checks if a student with the same Arabic name already exists
        2. If yes: links them to this order and updates their graduation info
        3. If no:  creates a new student record and links them

    Args:
        order_id:                 The graduation order to link students to.
        student_rows:             List of dicts. Expected keys:
                                      full_name_ar  (required)
                                      full_name_en  (optional)
                                      average       (optional int 50-100)
                                      sequence      (optional — rank)
        department_id:            Department FK for new student records.
        default_nationality_id:   Country FK (usually Iraq) for new records.

    Returns:
        (linked_count, created_count)
    """
    order = get_order_by_id(order_id)
    if not order:
        return (0, 0)

    linked  = 0
    created = 0

    with get_connection() as conn:
        for row in student_rows:
            name_ar = str(row.get("full_name_ar", "") or "").strip()
            if not name_ar:
                continue

            name_en  = str(row.get("full_name_en", "") or "").strip()
            avg_raw  = row.get("average")
            try:
                avg = int(round(float(str(avg_raw)))) if avg_raw is not None else None
                if avg is not None and not (50 <= avg <= 100):
                    avg = None
            except (ValueError, TypeError):
                avg = None

            # Try to match existing student by Arabic name
            existing = conn.execute(
                "SELECT id FROM students "
                "WHERE full_name_ar = ? AND department_id = ?",
                (name_ar, department_id)
            ).fetchone()

            if existing:
                # Update graduation info and link to order
                conn.execute(
                    "UPDATE students "
                    "SET order_id=?, graduation_date=?, graduation_semester=?"
                    "    , average=COALESCE(?, average) "
                    "WHERE id=?",
                    (order_id, order["order_date"],
                     order["graduation_semester"], avg, existing["id"])
                )
                linked += 1
            else:
                # Create a new student record
                conn.execute(
                    "INSERT INTO students "
                    "(full_name_ar, full_name_en, date_of_birth, "
                    " birthplace_id, birthplace_other, nationality_id, "
                    " department_id, admission_year, study_type, "
                    " graduation_date, graduation_semester, average, order_id) "
                    "VALUES (?, ?, '2000-01-01', NULL, 'غير محدد', ?, "
                    "        ?, ?, ?, ?, ?, ?, ?)",
                    (
                        name_ar,
                        name_en or name_ar,
                        default_nationality_id,
                        department_id,
                        order["admission_year"],
                        order["study_type"],
                        order["order_date"],
                        order["graduation_semester"],
                        avg,
                        order_id,
                    )
                )
                created += 1

        conn.commit()
    insert_audit_log("students", "INSERT", f"تم استيراد {created} طالب جديد وربط {linked} طالب بالأمر الجامعي ID: {order_id}")
    return (linked, created)


# =============================================================================
# ADDITIONAL STUDENT / PERIOD QUERIES  (used by students_screen)
# =============================================================================

def delete_student(student_id: int) -> None:
    """
    Delete a student and all their academic_periods + enrollments.
    Cascade rules in the schema handle periods and enrollments automatically.
    """
    with get_connection() as conn:
        # 1. Grab the name before we delete them so we can log it
        student = conn.execute("SELECT full_name_ar FROM students WHERE id = ?", (student_id,)).fetchone()
        student_name = student["full_name_ar"] if student else f"ID: {student_id}"

        # 2. Delete the student
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()

    # 3. Log the deletion
    insert_audit_log("students", "DELETE", f"تم حذف الطالب: {student_name}")


def update_period(period_id: int, academic_year: str, passed_round: str) -> None:
    """Update the academic_year and passed_round of an existing period."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE academic_periods SET academic_year=?, passed_round=? WHERE id=?",
            (academic_year, passed_round, period_id)
        )
        conn.commit()
    insert_audit_log("academic_periods", "UPDATE", f"تم تعديل بيانات المرحلة الدراسية ID: {period_id}")


def delete_period(period_id: int) -> None:
    """
    Delete one academic period and all its enrollments.
    Cascade rules handle enrollments automatically.
    """
    with get_connection() as conn:
        conn.execute("DELETE FROM academic_periods WHERE id = ?", (period_id,))
        conn.commit()
    insert_audit_log("academic_periods", "DELETE", f"تم حذف المرحلة الدراسية ID: {period_id}")


def update_enrollment(enrollment_id: int, score: float, is_second_round: int) -> None:
    """Update the score and round flag of an existing enrollment."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE enrollments SET score=?, is_second_round=? WHERE id=?",
            (score, is_second_round, enrollment_id)
        )
        conn.commit()
    insert_audit_log("enrollments", "UPDATE", f"تم تعديل درجة المادة ID: {enrollment_id}")


def get_courses_for_dept_stage(
    department_id: int, stage_number: int, study_system_id: int
) -> list[Row]:
    """
    Return all courses defined for a specific department + stage + study system.
    Used to populate the course picker when adding enrollments.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name_ar, name_en, credit_hours "
            "FROM courses "
            "WHERE department_id=? AND stage_number=? AND study_system_id=? "
            "ORDER BY name_ar",
            (department_id, stage_number, study_system_id)
        ).fetchall()
    return _rows_to_dicts(rows)


def fuzzy_search_students(query: str, limit: int = 8) -> list[Row]:
    """
    Search students by Arabic or English name.
    Returns exact + partial matches ordered by relevance.
    The caller (students_screen) can further rank using difflib.

    Args:
        query: Search string — Arabic or English partial name.
        limit: Maximum rows to return.

    Returns:
        List of student summary dicts (id, full_name_ar, full_name_en,
        dept_name_ar, admission_year, average, graduation_date).
    """
    pattern = f"%{query.strip()}%"
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT s.id, s.full_name_ar, s.full_name_en, "
            "       s.admission_year, s.average, s.graduation_date, "
            "       d.name_ar AS dept_name_ar "
            "FROM students s "
            "LEFT JOIN departments d ON s.department_id = d.id "
            "WHERE s.full_name_ar LIKE ? OR s.full_name_en LIKE ? "
            "ORDER BY s.full_name_ar "
            "LIMIT ?",
            (pattern, pattern, limit)
        ).fetchall()
    return _rows_to_dicts(rows)


def search_students_for_order(
    name_query: str = "",
    admission_year: int | None = None,
    department_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Row]:
    """
    Search students for the order-students sub-screen.
    Supports filtering by name, admission year, and department.

    Returns:
        List of dicts: id, full_name_ar, full_name_en, admission_year,
        dept_name_ar, average, order_id (None = unlinked).
    """
    conditions = []
    params: list = []
    if name_query.strip():
        pattern = f"%{name_query.strip()}%"
        conditions.append("(s.full_name_ar LIKE ? OR s.full_name_en LIKE ?)")
        params += [pattern, pattern]
    if admission_year is not None:
        conditions.append("s.admission_year = ?")
        params.append(admission_year)
    if department_id is not None:
        conditions.append("s.department_id = ?")
        params.append(department_id)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params += [limit, offset]
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT s.id, s.full_name_ar, s.full_name_en, "
            "       s.admission_year, s.average, s.order_id, "
            "       d.name_ar AS dept_name_ar "
            "FROM students s "
            "LEFT JOIN departments d ON s.department_id = d.id "
            f"{where} "
            "ORDER BY s.full_name_ar "
            "LIMIT ? OFFSET ?",
            params
        ).fetchall()
    return _rows_to_dicts(rows)


def count_students_for_order(
    name_query: str = "",
    admission_year: int | None = None,
    department_id: int | None = None,
) -> int:
    """Count matching students (for pagination in order-students sub-screen)."""
    conditions = []
    params: list = []
    if name_query.strip():
        pattern = f"%{name_query.strip()}%"
        conditions.append("(s.full_name_ar LIKE ? OR s.full_name_en LIKE ?)")
        params += [pattern, pattern]
    if admission_year is not None:
        conditions.append("s.admission_year = ?")
        params.append(admission_year)
    if department_id is not None:
        conditions.append("s.department_id = ?")
        params.append(department_id)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    with get_connection() as conn:
        return conn.execute(
            f"SELECT COUNT(*) FROM students s {where}", params
        ).fetchone()[0]


# =============================================================================
# GRADUATION ORDERS - LINKING STUDENTS
# =============================================================================

def get_students_for_order(order_id: int) -> list[Row]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, full_name_ar, average, order_id "
            "FROM students WHERE order_id = ? ORDER BY full_name_ar",
            (order_id,)
        ).fetchall()
    return _rows_to_dicts(rows)

def search_students_for_order(name_query: str, admission_year: int | None, department_id: int | None, limit: int) -> list[Row]:
    query = (
        "SELECT s.id, s.full_name_ar, s.admission_year, s.order_id, "
        "d.name_ar as dept_name_ar "
        "FROM students s "
        "LEFT JOIN departments d ON s.department_id = d.id "
        "WHERE 1=1"
    )
    params = []
    
    if name_query:
        query += " AND s.full_name_ar LIKE ?"
        params.append(f"%{name_query}%")
    
    if admission_year:
        query += " AND s.admission_year = ?"
        params.append(admission_year)
        
    if department_id:
        query += " AND s.department_id = ?"
        params.append(department_id)
        
    query += " ORDER BY s.full_name_ar LIMIT ?"
    params.append(limit)
    
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return _rows_to_dicts(rows)

def link_students_to_order(order_id: int) -> int:
    with get_connection() as conn:
        order = conn.execute(
            "SELECT department_id, admission_year, study_type, order_date, graduation_semester "
            "FROM graduation_orders WHERE id = ?",
            (order_id,)
        ).fetchone()
        
        if not order:
            return 0
            
        cur = conn.execute(
            "UPDATE students SET order_id = ?, graduation_date = ?, graduation_semester = ? "
            "WHERE department_id = ? AND admission_year = ? AND study_type = ? AND order_id IS NULL",
            (order_id, order["order_date"], order["graduation_semester"],
             order["department_id"], order["admission_year"], order["study_type"])
        )
        conn.commit()
        return cur.rowcount

def unlink_student_from_order(student_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE students SET order_id = NULL, graduation_date = NULL, graduation_semester = NULL "
            "WHERE id = ?",
            (student_id,)
        )
        conn.commit()
    insert_audit_log("students", "UPDATE", f"تم إلغاء ربط الطالب {student_id} من الأمر الجامعي")
# =============================================================================
# CERTIFICATE GENERATION
# =============================================================================

def get_full_certificate_data(student_id: int) -> dict | None:
    """
    Fetch all data needed to generate a certificate for a student in one structured dict.
    Includes:
        - Base student info + joins (dept, nationality, birthplace, order)
        - Rank and total graduates
        - Top graduate average
        - Academic periods + course enrollments
        - Active signatories (front and back)
    """
    with get_connection() as conn:
        # 1. Base student record with joins
        row = conn.execute(
            "SELECT s.*, "
            "       d.name_ar AS dept_name_ar, d.name_en AS dept_name_en, "
            "       ss.name_ar AS study_system_name_ar, ss.name_en AS study_system_name_en, "
            "       ss.calculation_rule, "
            "       c.name_ar AS nationality_ar, c.name_en AS nationality_en, "
            "       g.name_ar AS birthplace_ar, g.name_en AS birthplace_en, "
            "       o.order_number, o.order_date "
            "FROM students s "
            "LEFT JOIN departments d    ON s.department_id   = d.id "
            "LEFT JOIN study_systems ss ON s.study_system_id = ss.id "
            "LEFT JOIN countries c      ON s.nationality_id  = c.id "
            "LEFT JOIN governorates g   ON s.birthplace_id   = g.id "
            "LEFT JOIN graduation_orders o ON s.order_id = o.id "
            "WHERE s.id = ?",
            (student_id,)
        ).fetchone()

        if not row:
            return None
            
        data = _row_to_dict(row)
        
        # 2. Ranks & Top Averages
        rank, total = get_graduate_rank(student_id)
        data["rank"] = rank
        data["total_graduates"] = total
        data["top_average"] = get_top_graduate_average(data["department_id"], data["admission_year"])
        
        # 3. Academic periods & enrollments
        periods = conn.execute(
            "SELECT * FROM academic_periods WHERE student_id = ? ORDER BY stage_number",
            (student_id,)
        ).fetchall()
        
        data["periods"] = []
        for p in periods:
            p_dict = _row_to_dict(p)
            enrolls = conn.execute(
                "SELECT e.score, e.is_second_round, c.name_ar, c.name_en, c.credit_hours "
                "FROM enrollments e "
                "JOIN courses c ON e.course_id = c.id "
                "WHERE e.period_id = ? "
                "ORDER BY c.name_ar",
                (p["id"],)
            ).fetchall()
            p_dict["enrollments"] = _rows_to_dicts(enrolls)
            data["periods"].append(p_dict)
            
        # 4. Signatories
        front_sigs = conn.execute(
            "SELECT * FROM personal WHERE is_active = 1 AND page_location = 'front' ORDER BY display_order"
        ).fetchall()
        back_sigs = conn.execute(
            "SELECT * FROM personal WHERE is_active = 1 AND page_location = 'back' ORDER BY display_order"
        ).fetchall()
        
        data["front_signatories"] = _rows_to_dicts(front_sigs)
        data["back_signatories"] = _rows_to_dicts(back_sigs)
        
        # 5. Global Settings
        settings = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
        if settings:
            data["univ_name_ar"] = settings["univ_name_ar"]
            data["univ_name_en"] = settings["univ_name_en"]
            data["college_name_ar"] = settings["college_name_ar"]
            data["college_name_en"] = settings["college_name_en"]
        
        return data
def get_students_paginated(
    limit: int = 25,
    offset: int = 0,
    name_query: str = "",
    dept_id: int | None = None,
    year: int | None = None,
) -> list[Row]:
    """
    Return a paginated slice of students, with optional filters.
    Used by StudentsScreen pagination.
    """
    conditions = []
    params: list = []
    if name_query.strip():
        pattern = f"%{name_query.strip()}%"
        conditions.append("(s.full_name_ar LIKE ? OR s.full_name_en LIKE ?)")
        params += [pattern, pattern]
    if dept_id is not None:
        conditions.append("s.department_id = ?")
        params.append(dept_id)
    if year is not None:
        conditions.append("s.admission_year = ?")
        params.append(year)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params += [limit, offset]
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT s.id, s.full_name_ar, s.full_name_en, "
            "       s.admission_year, s.average, s.order_id, "
            "       d.name_ar AS dept_name_ar "
            "FROM students s "
            "LEFT JOIN departments d ON s.department_id = d.id "
            f"{where} "
            "ORDER BY s.full_name_ar "
            "LIMIT ? OFFSET ?",
            params
        ).fetchall()
    return _rows_to_dicts(rows)


def count_students(
    name_query: str = "",
    dept_id: int | None = None,
    year: int | None = None,
) -> int:
    """Return total students count matching optional filters."""
    conditions = []
    params: list = []
    if name_query.strip():
        pattern = f"%{name_query.strip()}%"
        conditions.append("(s.full_name_ar LIKE ? OR s.full_name_en LIKE ?)")
        params += [pattern, pattern]
    if dept_id is not None:
        conditions.append("s.department_id = ?")
        params.append(dept_id)
    if year is not None:
        conditions.append("s.admission_year = ?")
        params.append(year)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    with get_connection() as conn:
        return conn.execute(
            f"SELECT COUNT(*) FROM students s {where}", params
        ).fetchone()[0]

