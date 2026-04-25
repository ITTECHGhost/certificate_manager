# =============================================================================
# tools/migrate_mysql.py — MySQL SQL Dump → SQLite Migration Script
# =============================================================================
#
# PURPOSE:
#   Reads the phpMyAdmin SQL dump from the old PHP system and imports all
#   data into the new certificate_manager.db SQLite database.
#
# HOW TO RUN:
#   python tools/migrate_mysql.py "path\to\localhost.sql"
#   (run from inside the certificate_manager\ folder)
#
# WHAT IT IMPORTS:
#   MySQL table          → SQLite table
#   ─────────────────────────────────────────────────────────
#   department           → departments  (2 depts + college from info_system)
#   signatures           → personal     (5 signatories from 1 flat row)
#   subjects_140         → courses      (year-based courses)
#   subjects_q           → courses      (semester-based courses)
#   students_140         → students     (year-based students, 118 rows)
#   students_q           → students     (semester-based students, 1474 rows)
#   subjects_students_140→ academic_periods + enrollments
#   subjects_students_q  → academic_periods + enrollments
#   order_university     → enriches students with graduation_date/semester
#
# WHAT IS NOT IMPORTED:
#   admin, statistics    → app users and certificate log (not needed)
#
# REQUIREMENTS:
#   - Python 3.10+  (no third-party packages needed for this script)
#   - db.py must be importable (run from project root)
#   - The destination certificate_manager.db must already exist
#     (run db.py first if it doesn't)
#
# SAFE TO RE-RUN:
#   The script checks for existing data before inserting. Running it twice
#   will not create duplicates — it skips already-imported records.
#
# =============================================================================

import sys
import re
import sqlite3
import logging
from pathlib import Path
from collections import defaultdict

# ── path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from db import get_connection, init_db

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# =============================================================================
# STEP 1 — SQL PARSER
# Extracts table data from a MySQL/phpMyAdmin .sql dump without needing MySQL.
# =============================================================================

def parse_sql_dump(sql_path: str) -> dict[str, list[dict]]:
    """
    Parse a phpMyAdmin SQL dump file and return all table data as dicts.

    Returns:
        { table_name: [ {col: val, ...}, ... ], ... }
    """
    log.info("Reading SQL file: %s", sql_path)
    with open(sql_path, encoding="utf-8", errors="replace") as fh:
        sql = fh.read()

    tables: dict[str, list[dict]] = {}

    # Find every INSERT INTO block
    # Pattern: INSERT INTO `table_name` (`col1`,`col2`,...) VALUES (...),(...),...;
    insert_pattern = re.compile(
        r"INSERT INTO `(\w+)` \(([^)]+)\) VALUES\s*(.*?);",
        re.DOTALL,
    )

    for match in insert_pattern.finditer(sql):
        table_name  = match.group(1)
        cols_raw    = match.group(2)
        values_raw  = match.group(3)

        # Parse column names (strip backticks)
        columns = [c.strip().strip("`") for c in cols_raw.split(",")]

        # Parse value rows — each row is (...) possibly spanning multiple lines
        rows = _parse_value_rows(values_raw)

        # Convert each row tuple to a dict
        table_rows = []
        for row_values in rows:
            if len(row_values) != len(columns):
                continue                    # malformed row — skip
            table_rows.append(dict(zip(columns, row_values)))

        if table_name not in tables:
            tables[table_name] = []
        tables[table_name].extend(table_rows)

    for name, rows in tables.items():
        log.info("  Parsed %-35s → %d rows", f"`{name}`", len(rows))

    return tables


def _parse_value_rows(values_block: str) -> list[list]:
    """
    Extract individual value tuples from the VALUES block of an INSERT.
    Handles:
        - Multi-line values
        - Quoted strings with escaped quotes (\' and '')
        - NULL values
        - Numeric values
        - Embedded commas inside quoted strings
    """
    rows = []
    i = 0
    text = values_block.strip()
    n = len(text)

    while i < n:
        # Skip whitespace and commas between rows
        while i < n and text[i] in (" ", "\n", "\r", "\t", ","):
            i += 1

        if i >= n:
            break

        if text[i] != "(":
            i += 1
            continue

        # Read one (...)  row
        i += 1          # skip opening (
        row_values = []
        while i < n and text[i] != ")":
            # Skip whitespace
            while i < n and text[i] in (" ", "\n", "\r", "\t"):
                i += 1

            if i >= n:
                break

            if text[i] == ",":
                i += 1
                continue

            if text[i] == "'":
                # Quoted string — handle escaped quotes
                i += 1
                buf = []
                while i < n:
                    if text[i] == "\\" and i + 1 < n and text[i + 1] == "'":
                        buf.append("'")
                        i += 2
                    elif text[i] == "'" and i + 1 < n and text[i + 1] == "'":
                        buf.append("'")
                        i += 2
                    elif text[i] == "'":
                        i += 1
                        break
                    else:
                        buf.append(text[i])
                        i += 1
                row_values.append("".join(buf))

            elif text[i:i+4].upper() == "NULL":
                row_values.append(None)
                i += 4

            else:
                # Numeric or unquoted value — read until comma or )
                buf = []
                while i < n and text[i] not in (",", ")"):
                    buf.append(text[i])
                    i += 1
                val = "".join(buf).strip()
                row_values.append(val if val else None)

        rows.append(row_values)
        if i < n and text[i] == ")":
            i += 1          # skip closing )

    return rows


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _str(val) -> str:
    """Return val as a stripped string, or empty string if None."""
    return str(val).strip() if val is not None else ""


def _int_or(val, default: int) -> int:
    """Parse val as int, return default on failure."""
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return default


def _float_or(val, default: float | None) -> float | None:
    """Parse val as float, return default on failure."""
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return default


def _study_type(arabic: str) -> str:
    """Map Arabic study type label to 'morning' or 'evening'."""
    return "evening" if "مسائي" in arabic else "morning"


def _grad_semester(arabic: str) -> str | None:
    """Map Arabic semester label to 'first' or 'second'."""
    a = arabic.strip()
    if "اول" in a or "الأول" in a:
        return "first"
    if "ثاني" in a or "الثاني" in a:
        return "second"
    return None


def _passed_round(arabic: str) -> str:
    """Map Arabic دور label ('اولى'/'ثانية') to 'first'/'second'."""
    a = arabic.strip()
    if "اولى" in a or "أولى" in a or "اول" in a:
        return "first"
    return "second"


def _requirment_to_stage(req: str) -> int:
    """
    Map the `requirment` field from subjects_q / subjects_students_q to
    a stage_number (1–8) for the semester-based system.

    Encoding:
        مرحلة اولى-كورس اول   → 1    (Year 1, Semester 1)
        مرحلة اولى-كورس ثاني  → 2    (Year 1, Semester 2)
        مرحلة ثانية-كورس اول  → 3    (Year 2, Semester 1)
        مرحلة ثانية-كورس ثاني → 4    (Year 2, Semester 2)
        مرحلة ثالثة-كورس اول  → 5    (Year 3, Semester 1)
        مرحلة ثالثة-كورس ثاني → 6    (Year 3, Semester 2)
        مرحلة رابعة-كورس اول  → 7    (Year 4, Semester 1)
        مرحلة رابعة-كورس ثاني → 8    (Year 4, Semester 2)
    """
    YEAR_MAP  = {"اولى": 1, "ثانية": 2, "ثالثة": 3, "رابعة": 4}
    SEM_MAP   = {"اول": 0, "ثاني": 1}      # 0=first, 1=second
    year_num  = 1
    sem_num   = 0

    for key, val in YEAR_MAP.items():
        if key in req:
            year_num = val
            break

    if "ثاني" in req.split("-")[-1]:
        sem_num = 1

    return (year_num - 1) * 2 + sem_num + 1


def _code_to_stage(code: str) -> int:
    """
    Derive stage number from a course code for year-based system.
    CS101–CS199 → stage 1, CS201–CS299 → stage 2, etc.
    """
    m = re.search(r"[A-Za-z]+(\d)", code)
    if m:
        return int(m.group(1))
    return 1


# =============================================================================
# STEP 2 — DEPARTMENTS
# =============================================================================

def migrate_departments(
    tables: dict,
    conn: sqlite3.Connection,
) -> dict[str, int]:
    """
    Insert departments using college info from info_system.

    Returns:
        dept_name_map: { arabic_department_name → new_sqlite_id }
    """
    log.info("── Migrating departments ──")

    # Get college info from info_system
    college_ar = "كلية علوم الحاسوب وتكنولوجيا المعلومات"
    college_en = "College of Computer Science and Information Technology"
    if "info_system" in tables and tables["info_system"]:
        info = tables["info_system"][0]
        college_ar = _str(info.get("collage_ar", college_ar))
        college_en = _str(info.get("collage_en", college_en))

    dept_name_map: dict[str, int] = {}

    for row in tables.get("department", []):
        name_ar = _str(row["name_ar"])
        name_en = _str(row["name_en"])

        # Check if already exists
        existing = conn.execute(
            "SELECT id FROM departments WHERE name_ar = ?", (name_ar,)
        ).fetchone()

        if existing:
            log.info("  SKIP (exists): %s", name_ar)
            dept_name_map[name_ar] = existing["id"]
        else:
            cursor = conn.execute(
                "INSERT INTO departments "
                "(name_ar, name_en, college_ar, college_en, study_years, period_type) "
                "VALUES (?, ?, ?, ?, 4, 'year')",
                (name_ar, name_en, college_ar, college_en),
            )
            dept_name_map[name_ar] = cursor.lastrowid
            log.info("  INSERTED dept: %s", name_ar)

    conn.commit()
    return dept_name_map


# =============================================================================
# STEP 3 — PERSONAL (SIGNATORIES)
# =============================================================================

def migrate_signatures(tables: dict, conn: sqlite3.Connection) -> None:
    """
    The `signatures` table has 5 people in one flat row.
    Split them into individual rows in the `personal` table.

    Mapping:
        associate_dean    → front page, order 1   (معاون العميد)
        assist_university → front page, order 2   (مساعد رئيس الجامعة)
        dean              → front page, order 3   (العميد)
        doc_unit          → front page, order 4   (مسؤول وحدة الوثائق)
        doc_organize      → back page,  order 5   (منظم الوثيقة)
    """
    log.info("── Migrating signatures → personal ──")

    if not tables.get("signatures"):
        log.info("  No signatures found — skipping.")
        return

    sig = tables["signatures"][0]   # only 1 row

    # Each person: (name_ar_col, title_ar_col, resp_ar_col,
    #               name_en_col, title_en_col, resp_en_col,
    #               display_order, page_location)
    people = [
        (
            "associate_dean", "sin_asst_dean", "pos_associate_dean",
            "associate_dean_en", "sin_asst_dean_en", "pos_associate_dean_en",
            1, "front",
        ),
        (
            "assist_university", "sin_assist_university", "pos_assist_university",
            "assist_university_en", "sin_assist_university_en", "pos_assist_university_en",
            2, "front",
        ),
        (
            "dean", "sin_dean", "pos_dean",
            "dean_en", "sin_dean_en", "pos_dean_en",
            3, "front",
        ),
        (
            "doc_unit", "sin_doc_unit", "pos_doc_unit",
            "doc_unit_en", "sin_doc_unit_en", "pos_doc_unit_en",
            4, "front",
        ),
        (
            "doc_organize", "sin_doc_organize", "pos_doc_organize",
            "doc_organize_en", "sin_doc_organize_en", "pos_doc_organize_en",
            5, "back",
        ),
    ]

    for (name_ar_col, title_ar_col, resp_ar_col,
         name_en_col, title_en_col, resp_en_col,
         order, page) in people:

        name_ar = _str(sig.get(name_ar_col, ""))
        if not name_ar:
            continue

        existing = conn.execute(
            "SELECT id FROM personal WHERE name_ar = ? AND display_order = ?",
            (name_ar, order)
        ).fetchone()

        if existing:
            log.info("  SKIP (exists): %s", name_ar)
            continue

        conn.execute(
            "INSERT INTO personal "
            "(name_ar, name_en, academic_title_ar, academic_title_en, "
            " responsibility_ar, responsibility_en, display_order, page_location, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (
                name_ar,
                _str(sig.get(name_en_col, "")),
                _str(sig.get(title_ar_col, "")),
                _str(sig.get(title_en_col, "")),
                _str(sig.get(resp_ar_col, "")),
                _str(sig.get(resp_en_col, "")),
                order,
                page,
            )
        )
        log.info("  INSERTED: %s (order %d, %s)", name_ar, order, page)

    conn.commit()


# =============================================================================
# STEP 4 — COURSES
# =============================================================================

def migrate_courses(
    tables: dict,
    dept_name_map: dict[str, int],
    conn: sqlite3.Connection,
) -> tuple[dict[str, int], dict[str, int]]:
    """
    Import courses from subjects_140 (year-based) and subjects_q (semester-based).

    Returns:
        courses_140_map: { code → course_id }  for year-based
        courses_q_map:   { name_ar → course_id } for semester-based
    """
    log.info("── Migrating courses ──")
    courses_140_map: dict[str, int] = {}
    courses_q_map:   dict[str, int] = {}

    # ── Year-based courses (subjects_140) ────────────────────────────────────
    for row in tables.get("subjects_140", []):
        code    = _str(row.get("code",    ""))
        name_ar = _str(row.get("name_ar", ""))
        name_en = _str(row.get("name_en", ""))
        units   = _int_or(row.get("units"), 3)
        dep_ar  = _str(row.get("dep",     ""))
        dept_id = dept_name_map.get(dep_ar, list(dept_name_map.values())[0] if dept_name_map else 1)
        stage   = _code_to_stage(code)

        existing = conn.execute(
            "SELECT id FROM courses WHERE name_ar = ? AND department_id = ? AND period_type='year'",
            (name_ar, dept_id)
        ).fetchone()

        if existing:
            courses_140_map[code] = existing["id"]
        else:
            cur = conn.execute(
                "INSERT INTO courses (name_ar, name_en, credit_hours, department_id, stage_number, period_type) "
                "VALUES (?, ?, ?, ?, ?, 'year')",
                (name_ar, name_en, units, dept_id, stage)
            )
            courses_140_map[code] = cur.lastrowid

    log.info("  subjects_140: %d courses", len(courses_140_map))

    # ── Semester-based courses (subjects_q) ──────────────────────────────────
    for row in tables.get("subjects_q", []):
        name_ar = _str(row.get("name_ar", ""))
        name_en = _str(row.get("name_en", ""))
        units   = _int_or(row.get("units"), 3)
        dep_ar  = _str(row.get("dep",     ""))
        req     = _str(row.get("requirment", ""))
        dept_id = dept_name_map.get(dep_ar, list(dept_name_map.values())[0] if dept_name_map else 1)
        stage   = _requirment_to_stage(req) if req else 1

        existing = conn.execute(
            "SELECT id FROM courses WHERE name_ar = ? AND department_id = ? AND period_type='semester'",
            (name_ar, dept_id)
        ).fetchone()

        if existing:
            courses_q_map[name_ar] = existing["id"]
        else:
            cur = conn.execute(
                "INSERT INTO courses (name_ar, name_en, credit_hours, department_id, stage_number, period_type) "
                "VALUES (?, ?, ?, ?, ?, 'semester')",
                (name_ar, name_en, units, dept_id, stage)
            )
            courses_q_map[name_ar] = cur.lastrowid

    log.info("  subjects_q:   %d courses", len(courses_q_map))
    conn.commit()
    return courses_140_map, courses_q_map


# # =============================================================================
# # STEP 5 — ORDER UNIVERSITY INDEX
# # Builds a lookup from (dep_ar, year_study, graduation_semester) → graduation info
# # =============================================================================

# def build_order_index(tables: dict) -> dict[tuple, dict]:
#     """
#     Index the order_university table for fast lookup when enriching students.

#     Key: (dep_ar, year_study, graduation_semester_ar)
#     Value: { graduation_date, order_number }
#     """
#     index: dict[tuple, dict] = {}
#     for row in tables.get("order_university", []):
#         key = (
#             _str(row.get("dep",                 "")),
#             _str(row.get("year_study",          "")),
#             _str(row.get("graduation_semester", "")),
#         )
#         index[key] = {
#             "graduation_date":  _str(row.get("date",             "")),
#             "order_number":     _str(row.get("order_university", "")),
#         }
#     return index

# =============================================================================
# STEP 5 — GRADUATION ORDERS
# Imports order_university as real graduation_orders records.
# Also builds a lookup index used when linking students.
# =============================================================================

def migrate_orders(
    tables: dict,
    dept_name_map: dict[str, int],
    conn: sqlite3.Connection,
) -> dict[tuple, dict]:
    """
    Import order_university rows into the graduation_orders table.
    Returns an index: (dep_ar, year_study, grad_sem_ar) → { order_id, graduation_date }
    used when assigning students to orders.
    """
    log.info("── Migrating order_university → graduation_orders ──")

    index: dict[tuple, dict] = {}
    inserted = 0

    for row in tables.get("order_university", []):
        dep_ar   = _str(row.get("dep",                 ""))
        year_str = _str(row.get("year_study",          ""))
        sem_ar   = _str(row.get("graduation_semester", ""))
        role_ar  = _str(row.get("role",                ""))
        order_num = _str(row.get("order_university",   ""))
        date_str  = _str(row.get("date",               ""))
        num_str   = _str(row.get("num_students",       ""))
        study_ar  = _str(row.get("study",              "الدراسة الصباحية"))

        dept_id  = dept_name_map.get(dep_ar)
        if not dept_id:
            continue

        # grad_semester: prefer graduation_semester, fall back to role
        sem_display = sem_ar or role_ar
        grad_sem = _grad_semester(sem_display)
        if not grad_sem:
            continue

        study_type  = _study_type(study_ar)
        adm_year    = _int_or(year_str, 2020)
        num_students = _int_or(num_str, None) if num_str.isdigit() else None

        # Validate date format
        if len(date_str) != 10:
            date_str = f"{adm_year + 4}-06-01"   # fallback: 4 years after admission

        # Check if already imported
        existing = conn.execute(
            "SELECT id FROM graduation_orders "
            "WHERE order_number=? AND department_id=? AND admission_year=? AND graduation_semester=?",
            (order_num, dept_id, adm_year, grad_sem)
        ).fetchone()

        if existing:
            order_id = existing["id"]
        else:
            cur = conn.execute(
                "INSERT INTO graduation_orders "
                "(order_number, order_date, department_id, study_type, "
                " admission_year, graduation_semester, num_students) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (order_num, date_str, dept_id, study_type,
                 adm_year, grad_sem, num_students)
            )
            order_id = cur.lastrowid
            inserted += 1

        # Build index for student linking
        key = (dep_ar, year_str, sem_display)
        index[key] = {
            "order_id":       order_id,
            "graduation_date": date_str,
            "order_number":   order_num,
        }

    conn.commit()
    log.info("  graduation_orders: %d inserted", inserted)
    return index


def build_order_index(tables: dict) -> dict[tuple, dict]:
    """
    Legacy fallback index for student migration before orders are inserted.
    This is now used only when migrate_orders is not available.
    """
    index: dict[tuple, dict] = {}
    for row in tables.get("order_university", []):
        key = (
            _str(row.get("dep",                 "")),
            _str(row.get("year_study",          "")),
            _str(row.get("graduation_semester", "")),
        )
        index[key] = {
            "graduation_date": _str(row.get("date",             "")),
            "order_number":    _str(row.get("order_university", "")),
        }
    return index

# =============================================================================
# STEP 6 — STUDENTS
# =============================================================================

def migrate_students(
    tables: dict,
    dept_name_map: dict[str, int],
    order_index: dict[tuple, dict],
    conn: sqlite3.Connection,
) -> tuple[dict[int, int], dict[int, int]]:
    """
    Import students_140 (year-based) and students_q (semester-based).

    Returns:
        map_140: { old_mysql_id → new_sqlite_id }
        map_q:   { old_mysql_id → new_sqlite_id }
    """
    log.info("── Migrating students ──")

    # Iraq country id
    iraq_id = conn.execute(
        "SELECT id FROM countries WHERE iso_code='IQ'"
    ).fetchone()["id"]

    map_140: dict[int, int] = {}
    map_q:   dict[int, int] = {}

    def _insert_student(
        old_id: int,
        name_ar: str,
        name_en: str,
        study: str,
        dep_ar: str,
        grad_year: str,
        grad_sem_ar: str,
        average_str: str,
        order_index: dict,
        period_type: str,
    ) -> int | None:
        """Insert one student and return their new SQLite ID, or None on error."""
        dept_id = dept_name_map.get(dep_ar)
        if not dept_id:
            log.warning("    Unknown dept '%s' for student %s — skipping.", dep_ar, name_ar)
            return None

        # # Lookup graduation date from order_university
        # order_info  = order_index.get((dep_ar, grad_year, grad_sem_ar), {})
        # grad_date   = order_info.get("graduation_date") or None
        # grad_sem    = _grad_semester(grad_sem_ar)

        # # average: MySQL stores as float string e.g. "85.172"
        # avg_float   = _float_or(average_str, None)
        # avg_int     = int(round(avg_float)) if avg_float is not None else None
        # if avg_int is not None and not (50 <= avg_int <= 100):
        #     avg_int = None

        # admission_year = _int_or(grad_year, 2020)

        # # cur = conn.execute(
        # #     "INSERT INTO students "
        # #     "(full_name_ar, full_name_en, date_of_birth, "
        # #     " birthplace_id, birthplace_other, nationality_id, "
        # #     " department_id, admission_year, study_type, "
        # #     " graduation_date, graduation_semester, average) "
        # #     "VALUES (?, ?, '2000-01-01', NULL, 'غير محدد', ?, ?, ?, ?, ?, ?, ?)",
        # #     (
        # #         name_ar,
        # #         name_en or name_ar,
        # #         iraq_id,
        # #         dept_id,
        # #         admission_year,
        # #         _study_type(study),
        # #         grad_date,
        # #         grad_sem,
        # #         avg_int,
        # #     )
        # # )
        # # return cur.lastrowid

        #     # Find matching order_id from the order index
        # order_id = None
        # for key, val in order_index.items():
        #     if (key[0] == dep_ar and key[1] == grad_year
        #             and _grad_semester(key[2]) == grad_sem):
        #         order_id = val.get("order_id")
        #         if not grad_date:
        #             grad_date = val.get("graduation_date")
        #         break

        # cur = conn.execute(
        #     "INSERT INTO students "
        #     "(full_name_ar, full_name_en, date_of_birth, birthplace_id, "
        #     " birthplace_other, nationality_id, department_id, admission_year, "
        #     " study_type, graduation_date, graduation_semester, average, order_id) "
        #     "VALUES (?, ?, \'2000-01-01\', NULL, \'غير محدد\', ?, ?, ?, ?, ?, ?, ?, ?)",
        #     (
        #         name_ar,
        #         name_en or name_ar,
        #         iraq_id,
        #         dept_id,
        #         admission_year,
        #         _study_type(study),
        #         grad_date,
        #         grad_sem,
        #         avg_int,
        #         order_id,
        #     )
        # )
        # return cur.lastrowid

    # Lookup order from the index built by migrate_orders()
        order_info  = order_index.get((dep_ar, grad_year, grad_sem_ar), {})
        grad_date   = order_info.get("graduation_date") or None
        order_id    = order_info.get("order_id")        # FK to graduation_orders
        grad_sem    = _grad_semester(grad_sem_ar)

        # average: MySQL stores as float string e.g. "85.172"
        avg_float   = _float_or(average_str, None)
        avg_int     = int(round(avg_float)) if avg_float is not None else None
        if avg_int is not None and not (50 <= avg_int <= 100):
            avg_int = None

        admission_year = _int_or(grad_year, 2020)

        cur = conn.execute(
            "INSERT INTO students "
            "(full_name_ar, full_name_en, date_of_birth, "
            " birthplace_id, birthplace_other, nationality_id, "
            " department_id, admission_year, study_type, "
            " graduation_date, graduation_semester, average, order_id) "
            "VALUES (?, ?, '2000-01-01', NULL, 'غير محدد', ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                name_ar,
                name_en or name_ar,
                iraq_id,
                dept_id,
                admission_year,
                _study_type(study),
                grad_date,
                grad_sem,
                avg_int,
                order_id,
            )
        )
        return cur.lastrowid

    # ── students_140 (year-based) ─────────────────────────────────────────────
    inserted_140 = 0
    for row in tables.get("students_140", []):
        old_id  = _int_or(row.get("id"), 0)
        name_ar = _str(row.get("name",  ""))

        # Skip if already imported (idempotency check on name)
        existing = conn.execute(
            "SELECT id FROM students WHERE full_name_ar = ?", (name_ar,)
        ).fetchone()
        if existing:
            map_140[old_id] = existing["id"]
            continue

        new_id = _insert_student(
            old_id,
            name_ar,
            _str(row.get("name_en",            "")),
            _str(row.get("study",               "")),
            _str(row.get("department",           "")),
            _str(row.get("graduation_year",      "")),
            _str(row.get("graduation_semester",  "")),
            _str(row.get("average",              "")),
            order_index,
            "year",
        )
        if new_id:
            map_140[old_id] = new_id
            inserted_140 += 1

    log.info("  students_140: %d inserted, %d total", inserted_140, len(map_140))

    # ── students_q (semester-based) ───────────────────────────────────────────
    inserted_q = 0
    for row in tables.get("students_q", []):
        old_id  = _int_or(row.get("id"), 0)
        name_ar = _str(row.get("name",  ""))

        existing = conn.execute(
            "SELECT id FROM students WHERE full_name_ar = ?", (name_ar,)
        ).fetchone()
        if existing:
            map_q[old_id] = existing["id"]
            continue

        # students_q uses 'role' instead of 'graduation_semester'
        grad_sem_ar = _str(row.get("role", ""))

        new_id = _insert_student(
            old_id,
            name_ar,
            _str(row.get("name_en",           "")),
            _str(row.get("study",              "")),
            _str(row.get("department",         "")),
            _str(row.get("graduation_year",    "")),
            grad_sem_ar,
            _str(row.get("average",            "")),
            order_index,
            "semester",
        )
        if new_id:
            map_q[old_id] = new_id
            inserted_q += 1

    log.info("  students_q:   %d inserted, %d total", inserted_q, len(map_q))
    conn.commit()
    return map_140, map_q


# =============================================================================
# STEP 7 — ACADEMIC PERIODS + ENROLLMENTS
# =============================================================================

def migrate_enrollments_140(
    tables: dict,
    student_map: dict[int, int],
    courses_map: dict[str, int],
    conn: sqlite3.Connection,
) -> None:
    """
    Import year-based enrollment data from subjects_students_140.

    Grouping logic:
        Each (student_id, yearr, semester) combination = one academic_period.
        academic_year is constructed as "yearr-(yearr+1)".
        stage_number = derived from course code (CS1xx=1, CS2xx=2, etc.)
        passed_round = from `failed` column ('اولى'→first, 'ثانية'→second)
    """
    log.info("── Migrating subjects_students_140 → periods + enrollments ──")

    # Group rows by (old_student_id, yearr, semester)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in tables.get("subjects_students_140", []):
        old_sid = _int_or(row.get("id_student"), 0)
        yearr   = _str(row.get("yearr",    "0"))
        sem     = _str(row.get("semester", ""))
        groups[(old_sid, yearr, sem)].append(row)

    periods_inserted  = 0
    enrolls_inserted  = 0
    skipped_students  = 0

    # Map each chronological semester to a stage number (1 to N)
    student_sems = {}
    for (old_sid, yearr, sem_ar) in groups.keys():
        if old_sid not in student_sems:
            student_sems[old_sid] = set()
        year_int = _int_or(yearr, 2020)
        # map semester to int for sorting
        sem_int = 1 if 'اول' in sem_ar else (2 if 'ثان' in sem_ar else 3)
        student_sems[old_sid].add((year_int, sem_int, sem_ar))
        
    student_stage_map = {}
    for old_sid, sems in student_sems.items():
        # Sort by year then by sem_int
        for idx, s in enumerate(sorted(list(sems), key=lambda x: (x[0], x[1]))):
            student_stage_map[(old_sid, s[0], s[2])] = idx + 1

    for (old_sid, yearr, sem_ar), rows in groups.items():
        new_sid = student_map.get(old_sid)
        if not new_sid:
            skipped_students += 1
            continue

        year_int    = _int_or(yearr, 2020)
        acad_year   = f"{year_int}-{year_int + 1}"

        # Stage is strictly the chronological semester (1 to N)
        stage = student_stage_map[(old_sid, year_int, sem_ar)]

        # passed_round: if any course in this period was failed then resit (ثانية)
        rounds = [_passed_round(_str(r.get("failed", "اولى"))) for r in rows]
        passed_round = "second" if "second" in rounds else "first"

        # Check if period already exists
        existing_period = conn.execute(
            "SELECT id FROM academic_periods "
            "WHERE student_id=? AND stage_number=? AND period_type='year'",
            (new_sid, stage)
        ).fetchone()

        if existing_period:
            period_id = existing_period["id"]
        else:
            cur = conn.execute(
                "INSERT INTO academic_periods "
                "(student_id, academic_year, period_type, stage_number, passed_round) "
                "VALUES (?, ?, 'year', ?, ?)",
                (new_sid, acad_year, stage, passed_round)
            )
            period_id = cur.lastrowid
            periods_inserted += 1

        # Insert enrollments for each course in this period
        for row in rows:
            code    = _str(row.get("code",    ""))
            score   = _float_or(row.get("degree"), 0.0)
            is_2nd  = 1 if _passed_round(_str(row.get("failed", ""))) == "second" else 0

            course_id = courses_map.get(code)
            if not course_id:
                # Course not in catalog — insert it on the fly
                name_ar = _str(row.get("name_ar", code))
                name_en = _str(row.get("name_en", code))
                units   = _int_or(row.get("units"), 3)
                # Get dept from student record
                student = conn.execute(
                    "SELECT department_id FROM students WHERE id=?", (new_sid,)
                ).fetchone()
                dept_id = student["department_id"] if student else 1

                existing_c = conn.execute(
                    "SELECT id FROM courses WHERE name_ar=? AND department_id=? AND period_type='year'",
                    (name_ar, dept_id)
                ).fetchone()
                if existing_c:
                    course_id = existing_c["id"]
                else:
                    c = conn.execute(
                        "INSERT INTO courses (name_ar, name_en, credit_hours, department_id, stage_number, period_type) "
                        "VALUES (?, ?, ?, ?, ?, 'year')",
                        (name_ar, name_en, units, dept_id, _code_to_stage(code))
                    )
                    course_id = c.lastrowid
                    courses_map[code] = course_id

            # Check enrollment doesn't already exist
            existing_e = conn.execute(
                "SELECT id FROM enrollments WHERE period_id=? AND course_id=?",
                (period_id, course_id)
            ).fetchone()
            if not existing_e and score is not None:
                conn.execute(
                    "INSERT INTO enrollments (period_id, course_id, score, is_second_round) "
                    "VALUES (?, ?, ?, ?)",
                    (period_id, course_id, score, is_2nd)
                )
                enrolls_inserted += 1

    conn.commit()
    log.info(
        "  subjects_students_140: %d periods, %d enrollments, %d students skipped",
        periods_inserted, enrolls_inserted, skipped_students
    )


def migrate_enrollments_q(
    tables: dict,
    student_map: dict[int, int],
    courses_map: dict[str, int],
    conn: sqlite3.Connection,
) -> None:
    """
    Import semester-based enrollment data from subjects_students_q.

    Grouping logic:
        Each (student_id, requirment_stage) = one academic_period.
        The `yearr` of the latest course in that stage is used for academic_year.
        passed_round = from `role` column (الاول/الثاني).
    """
    log.info("── Migrating subjects_students_q → periods + enrollments ──")

    # Group rows chronologically by (old_student_id, yearr, role)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in tables.get("subjects_students_q", []):
        old_sid = _int_or(row.get("id_student"), 0)
        yearr   = _int_or(row.get("yearr", "0"), 2020)
        role    = _str(row.get("role", "الاول"))
        groups[(old_sid, yearr, role)].append(row)

    periods_inserted = 0
    enrolls_inserted = 0
    skipped_students = 0

    # Map each chronological semester to a stage number
    student_sems = {}
    for (old_sid, yearr, role) in groups.keys():
        if old_sid not in student_sems:
            student_sems[old_sid] = set()
        # map role to int for sorting
        role_int = 1 if 'اول' in role else (2 if 'ثان' in role else 3)
        student_sems[old_sid].add((yearr, role_int, role))
        
    student_stage_map_q = {}
    for old_sid, sems in student_sems.items():
        # Sort by year then by role_int
        for idx, s in enumerate(sorted(list(sems), key=lambda x: (x[0], x[1]))):
            student_stage_map_q[(old_sid, s[0], s[2])] = idx + 1

    for (old_sid, yearr, role), rows in groups.items():
        new_sid = student_map.get(old_sid)
        if not new_sid:
            skipped_students += 1
            continue

        year_int   = yearr
        acad_year  = f"{year_int}-{year_int + 1}"
        
        # Override stage with strictly chronological stage
        stage = student_stage_map_q[(old_sid, yearr, role)]

        # passed_round
        rounds = [_passed_round(_str(r.get("role", "الاول"))) for r in rows]
        passed_round = "second" if "second" in rounds else "first"

        existing_period = conn.execute(
            "SELECT id FROM academic_periods "
            "WHERE student_id=? AND stage_number=? AND period_type='semester'",
            (new_sid, stage)
        ).fetchone()

        if existing_period:
            period_id = existing_period["id"]
        else:
            cur = conn.execute(
                "INSERT INTO academic_periods "
                "(student_id, academic_year, period_type, stage_number, passed_round) "
                "VALUES (?, ?, 'semester', ?, ?)",
                (new_sid, acad_year, stage, passed_round)
            )
            period_id = cur.lastrowid
            periods_inserted += 1

        for row in rows:
            name_ar = _str(row.get("name_ar", ""))
            score   = _float_or(row.get("degree"), 0.0)
            is_2nd  = 1 if _passed_round(_str(row.get("role", ""))) == "second" else 0

            course_id = courses_map.get(name_ar)
            if not course_id:
                # Create course on the fly
                name_en = _str(row.get("name_en", ""))
                units   = _int_or(row.get("units"), 3)
                student = conn.execute(
                    "SELECT department_id FROM students WHERE id=?", (new_sid,)
                ).fetchone()
                dept_id = student["department_id"] if student else 1

                existing_c = conn.execute(
                    "SELECT id FROM courses WHERE name_ar=? AND department_id=? AND period_type='semester'",
                    (name_ar, dept_id)
                ).fetchone()
                if existing_c:
                    course_id = existing_c["id"]
                else:
                    c = conn.execute(
                        "INSERT INTO courses (name_ar, name_en, credit_hours, department_id, stage_number, period_type) "
                        "VALUES (?, ?, ?, ?, ?, 'semester')",
                        (name_ar, name_en, units, dept_id, stage)
                    )
                    course_id = c.lastrowid
                    courses_map[name_ar] = course_id

            existing_e = conn.execute(
                "SELECT id FROM enrollments WHERE period_id=? AND course_id=?",
                (period_id, course_id)
            ).fetchone()
            if not existing_e and score is not None:
                conn.execute(
                    "INSERT INTO enrollments (period_id, course_id, score, is_second_round) "
                    "VALUES (?, ?, ?, ?)",
                    (period_id, course_id, score, is_2nd)
                )
                enrolls_inserted += 1

    conn.commit()
    log.info(
        "  subjects_students_q:   %d periods, %d enrollments, %d students skipped",
        periods_inserted, enrolls_inserted, skipped_students
    )


# =============================================================================
# STEP 8 — FINAL REPORT
# =============================================================================

def print_report(conn: sqlite3.Connection) -> None:
    """Print a summary of what is now in the destination database."""
    log.info("── Import complete — Final counts ──")
    tables = [
        "countries", "governorates", "departments", "personal",
        "courses", "students", "academic_periods", "enrollments",
    ]
    for t in tables:
        n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        log.info("  %-22s  %d rows", t, n)


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    if len(sys.argv) < 2:
        print()
        print("Usage:")
        print('  python tools/migrate_mysql.py "path\\to\\localhost.sql"')
        print()
        sys.exit(1)

    sql_path = sys.argv[1]
    if not Path(sql_path).exists():
        log.error("File not found: %s", sql_path)
        sys.exit(1)

    # Make sure destination DB exists and is initialized
    init_db()

    # Parse the entire SQL dump into memory
    tables = parse_sql_dump(sql_path)

    with get_connection() as conn:
        # Run each migration step in order
        dept_map              = migrate_departments(tables, conn)
        migrate_signatures(tables, conn)
        courses_140, courses_q = migrate_courses(tables, dept_map, conn)
        # order_idx             = build_order_index(tables)
        # map_140, map_q        = migrate_students(tables, dept_map, order_idx, conn)
        order_idx             = migrate_orders(tables, dept_map, conn)
        map_140, map_q        = migrate_students(tables, dept_map, order_idx, conn)

        migrate_enrollments_140(tables, map_140, courses_140, conn)
        migrate_enrollments_q  (tables, map_q,   courses_q,   conn)

        print_report(conn)

    log.info("Done. Open main.py to view imported data.")


if __name__ == "__main__":
    main()
