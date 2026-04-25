# =============================================================================
# db.py — Certificate Manager: Database Initialization & Utilities
# =============================================================================
# Responsibilities:
#   1. Open / create the SQLite database file
#   2. Create all 8 tables + indexes (idempotent — safe to call repeatedly)
#   3. Seed reference data: 18 Iraqi governorates + 195 countries
#   4. Provide a reusable get_connection() helper for all other modules
#
# Usage:
#   from db import init_db, get_connection
#   init_db()                          # call once at app startup
#   with get_connection() as conn: ... # use anywhere
#
# Requirements: Python 3.10+, no third-party packages (sqlite3 is built-in)
# =============================================================================

import sqlite3
import logging
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = Path("certificate_manager.db")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection Helper
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """
    Open and return a connection to the SQLite database.

    - Row factory set to sqlite3.Row so columns are accessible by name.
    - Foreign key enforcement enabled on every connection.
    - Use as a context manager:  with get_connection() as conn: ...
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA encoding = 'UTF-8'")
    return conn


# ---------------------------------------------------------------------------
# Public Entry Point
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Initialize the database: create all tables, indexes, and seed data.
    Safe to call on every application startup — all statements are idempotent.
    """
    log.info("Initializing database at: %s", DB_PATH.resolve())
    try:
        with get_connection() as conn:
            _create_tables(conn)
            _create_indexes(conn)
            _migrate_db(conn)
            _seed_governorates(conn)
            _seed_countries(conn)
            conn.commit()
        log.info("Database initialization complete.")
    except sqlite3.Error as e:
        log.error("Database initialization failed: %s", e)
        raise


def _migrate_db(conn: sqlite3.Connection) -> None:
    """
    Apply additive schema migrations that are safe on existing databases.
    Each ALTER TABLE is wrapped in a try/except so it skips silently if the
    column already exists (sqlite3 raises OperationalError in that case).
    """
    migrations = [
        "ALTER TABLE courses ADD COLUMN is_shared INTEGER NOT NULL DEFAULT 0",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
            log.info("Migration applied: %s", sql[:60])
        except sqlite3.OperationalError:
            pass   # column already exists


# ---------------------------------------------------------------------------
# Table Creation
# ---------------------------------------------------------------------------

def _create_tables(conn: sqlite3.Connection) -> None:
    """Create all 8 tables. Skips silently if they already exist."""

    conn.executescript("""
    -- -------------------------------------------------------------------------
    -- countries: 195 rows pre-seeded. ISO 3166-1 alpha-2 codes.
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS countries (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        name_ar  TEXT    NOT NULL CHECK(length(name_ar)  <= 80),
        name_en  TEXT    NOT NULL CHECK(length(name_en)  <= 80),
        iso_code TEXT    NOT NULL UNIQUE
                                 CHECK(length(iso_code)  <= 3)
    );

    -- -------------------------------------------------------------------------
    -- governorates: 18 Iraqi rows pre-seeded.
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS governorates (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        name_ar TEXT    NOT NULL UNIQUE CHECK(length(name_ar) <= 40),
        name_en TEXT    NOT NULL UNIQUE CHECK(length(name_en) <= 40)
    );

    -- -------------------------------------------------------------------------
    -- departments
    -- period_type: 'year' or 'semester' — determines certificate format.
    -- study_years: 2–6 covers all Iraqi university programs.
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS departments (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name_ar     TEXT    NOT NULL CHECK(length(name_ar)    <= 100),
        name_en     TEXT    NOT NULL CHECK(length(name_en)    <= 100),
        college_ar  TEXT    NOT NULL CHECK(length(college_ar) <= 120),
        college_en  TEXT    NOT NULL CHECK(length(college_en) <= 120),
        study_years INTEGER NOT NULL CHECK(study_years BETWEEN 2 AND 6),
        period_type TEXT    NOT NULL CHECK(period_type IN ('year', 'semester'))
    );

    -- -------------------------------------------------------------------------
    -- personal: Signatories for front (positions 1–4) and back (5–6) pages.
    -- is_active 1 = current signatory, 0 = historical record.
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS personal (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        name_ar           TEXT    NOT NULL CHECK(length(name_ar)           <= 80),
        name_en           TEXT    NOT NULL CHECK(length(name_en)           <= 80),
        academic_title_ar TEXT    NOT NULL CHECK(length(academic_title_ar) <= 50),
        academic_title_en TEXT    NOT NULL CHECK(length(academic_title_en) <= 50),
        responsibility_ar TEXT    NOT NULL CHECK(length(responsibility_ar) <= 120),
        responsibility_en TEXT    NOT NULL CHECK(length(responsibility_en) <= 120),
        display_order     INTEGER NOT NULL CHECK(display_order BETWEEN 1 AND 6),
        page_location     TEXT    NOT NULL CHECK(page_location IN ('front', 'back')),
        is_active         INTEGER NOT NULL DEFAULT 1
                                           CHECK(is_active IN (0, 1))
    );

    -- -------------------------------------------------------------------------
    -- courses: Catalog of all courses, organized by dept + stage.
    -- stage_number 1–8 covers up to 4-year semester programs (8 semesters).
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS courses (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        name_ar       TEXT    NOT NULL CHECK(length(name_ar)  <= 100),
        name_en       TEXT    NOT NULL CHECK(length(name_en)  <= 100),
        credit_hours  INTEGER NOT NULL CHECK(credit_hours BETWEEN 1 AND 6),
        department_id INTEGER NOT NULL REFERENCES departments(id)
                                       ON UPDATE CASCADE
                                       ON DELETE RESTRICT,
        stage_number  INTEGER NOT NULL ,
        period_type   TEXT    NOT NULL CHECK(period_type IN ('year', 'semester'))
    );

    -- -------------------------------------------------------------------------
    -- students: Core record. One row per student.
    -- average: user-entered integer 50–100. Grade derived at display time.
    -- birthplace: either birthplace_id (Iraqi) OR birthplace_other (foreign).
    -- CHECK guarantees exactly one is populated, never both, never neither.
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS students (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name_ar         TEXT    NOT NULL CHECK(length(full_name_ar)     <= 150),
        full_name_en         TEXT    NOT NULL CHECK(length(full_name_en)     <= 150),
        date_of_birth        TEXT    NOT NULL CHECK(length(date_of_birth)    =  10),
        birthplace_id        INTEGER          REFERENCES governorates(id)
                                              ON UPDATE CASCADE
                                              ON DELETE RESTRICT,
        birthplace_other     TEXT             CHECK(birthplace_other IS NULL
                                               OR length(birthplace_other)  <= 100),
        nationality_id       INTEGER NOT NULL REFERENCES countries(id)
                                              ON UPDATE CASCADE
                                              ON DELETE RESTRICT,
        department_id        INTEGER NOT NULL REFERENCES departments(id)
                                              ON UPDATE CASCADE
                                              ON DELETE RESTRICT,
        order_id             INTEGER          REFERENCES graduation_orders(id) ON UPDATE CASCADE ON DELETE SET NULL,
        admission_year       INTEGER NOT NULL CHECK(admission_year BETWEEN 1950 AND 2100),
        study_type           TEXT    NOT NULL CHECK(study_type IN ('morning', 'evening')),
        graduation_date      TEXT             CHECK(graduation_date IS NULL
                                               OR length(graduation_date)   =  10),
        graduation_semester  TEXT             CHECK(graduation_semester IS NULL
                                               OR graduation_semester
                                               IN ('first', 'second')),
        average              INTEGER          CHECK(average IS NULL
                                               OR average BETWEEN 50 AND 100),

        CHECK (
            (birthplace_id IS NOT NULL AND birthplace_other IS NULL)
            OR
            (birthplace_id IS NULL     AND birthplace_other IS NOT NULL)
        )
    );
    

    -- graduation_orders: Official university orders (أوامر جامعية).
    -- Each order approves a batch of students for graduation.
    -- order_number: e.g. "18515/13/2"  (رقم الأمر الجامعي)
    -- order_date:   YYYY-MM-DD
    -- admission_year: the batch/دفعة year, e.g. 2018
    -- num_students: expected count from the official document
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS graduation_orders (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number        TEXT    NOT NULL CHECK(length(order_number)  <= 60),
        order_date          TEXT    NOT NULL CHECK(length(order_date)    =  10),
        department_id       INTEGER NOT NULL REFERENCES departments(id)
                                             ON UPDATE CASCADE
                                             ON DELETE RESTRICT,
        study_type          TEXT    NOT NULL DEFAULT \'morning\'
                                             CHECK(study_type IN (\'morning\',\'evening\')),
        admission_year      INTEGER NOT NULL CHECK(admission_year BETWEEN 1950 AND 2100),
        graduation_semester TEXT    NOT NULL CHECK(graduation_semester IN (\'first\',\'second\')),
        num_students        INTEGER          CHECK(num_students IS NULL OR num_students > 0),
        notes               TEXT             CHECK(notes IS NULL OR length(notes) <= 500)
    );


    -- -------------------------------------------------------------------------
    -- academic_periods: One row per stage per student.
    -- UNIQUE prevents duplicate stages for the same student.
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS academic_periods (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id    INTEGER NOT NULL REFERENCES students(id)
                                       ON UPDATE CASCADE
                                       ON DELETE CASCADE,
        academic_year TEXT    NOT NULL CHECK(length(academic_year) = 9),
        period_type   TEXT    NOT NULL CHECK(period_type IN ('year', 'semester')),
        stage_number  INTEGER NOT NULL ,
        passed_round  TEXT    NOT NULL CHECK(passed_round IN ('first', 'second')),

        UNIQUE(student_id, stage_number, period_type)
    );

    -- -------------------------------------------------------------------------
    -- enrollments: One row per course per period (Approach B — individual).
    -- UNIQUE prevents the same course appearing twice in one period.
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS enrollments (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        period_id       INTEGER NOT NULL REFERENCES academic_periods(id)
                                         ON UPDATE CASCADE
                                         ON DELETE CASCADE,
        course_id       INTEGER NOT NULL REFERENCES courses(id)
                                         ON UPDATE CASCADE
                                         ON DELETE RESTRICT,
        score           REAL    NOT NULL CHECK(score BETWEEN 0 AND 100),
        is_second_round INTEGER NOT NULL DEFAULT 0
                                         CHECK(is_second_round IN (0, 1)),

        UNIQUE(period_id, course_id)
    );

    -- -------------------------------------------------------------------------
    -- course_departments: Junction table for shared courses.
    -- A course with department_id IS NULL in courses table is "shared".
    -- This table lists which departments share it.
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS course_departments (
        course_id     INTEGER NOT NULL REFERENCES courses(id)
                                       ON UPDATE CASCADE ON DELETE CASCADE,
        department_id INTEGER NOT NULL REFERENCES departments(id)
                                       ON UPDATE CASCADE ON DELETE CASCADE,
        PRIMARY KEY (course_id, department_id)
    );

    -- -------------------------------------------------------------------------
    -- personal_log: Full row snapshot BEFORE any edit/deactivate on personal.
    -- action: 'insert', 'update', 'deactivate'
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS personal_log (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        action            TEXT    NOT NULL,
        changed_at        TEXT    NOT NULL DEFAULT (datetime('now')),
        personal_id       INTEGER NOT NULL,
        name_ar           TEXT,
        name_en           TEXT,
        academic_title_ar TEXT,
        academic_title_en TEXT,
        responsibility_ar TEXT,
        responsibility_en TEXT,
        display_order     INTEGER,
        page_location     TEXT,
        is_active         INTEGER
    );

    -- -------------------------------------------------------------------------
    -- audit_log: Universal change log for ALL tables.
    -- table_name: which table was modified
    -- record_id:  PK of the affected row
    -- action:     'INSERT', 'UPDATE', 'DELETE'
    -- summary:    human-readable description of what changed
    -- error_info: if the operation raised an exception, store it here
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS audit_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name  TEXT    NOT NULL,
        record_id   INTEGER,
        action      TEXT    NOT NULL CHECK(action IN ('INSERT','UPDATE','DELETE','ERROR')),
        summary     TEXT,
        error_info  TEXT,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    );
    """)
    log.info("All tables created (or already exist).")


# ---------------------------------------------------------------------------
# Index Creation
# ---------------------------------------------------------------------------

def _create_indexes(conn: sqlite3.Connection) -> None:
    """Create all performance indexes. Skips silently if they already exist."""

    conn.executescript("""
    -- Fast student name search (supports fuzzy matching in Python)
    CREATE INDEX IF NOT EXISTS idx_students_name_ar
        ON students(full_name_ar);

    CREATE INDEX IF NOT EXISTS idx_students_name_en
        ON students(full_name_en);

    -- Ranking: all graduates in same department + admission year
    CREATE INDEX IF NOT EXISTS idx_students_dept_admission
        ON students(department_id, admission_year);

    -- All academic periods for one student
    CREATE INDEX IF NOT EXISTS idx_periods_student
        ON academic_periods(student_id);

    -- Student periods filtered by stage
    CREATE INDEX IF NOT EXISTS idx_periods_student_stage
        ON academic_periods(student_id, stage_number);

    -- All enrollments for one period
    CREATE INDEX IF NOT EXISTS idx_enrollments_period
        ON enrollments(period_id);

    -- Where a course appears across all enrollments
    CREATE INDEX IF NOT EXISTS idx_enrollments_course
        ON enrollments(course_id);

    -- Active signatories by page (certificate generation queries this every time)
    CREATE INDEX IF NOT EXISTS idx_personal_active_page
        ON personal(is_active, page_location, display_order);

    -- Course catalog filtered by department + stage
    CREATE INDEX IF NOT EXISTS idx_courses_dept_stage
        ON courses(department_id, stage_number);

    -- Audit log — fast retrieval newest-first per table
    CREATE INDEX IF NOT EXISTS idx_audit_log_table_date
        ON audit_log(table_name, created_at DESC);

    -- Personal log — newest changes first
    CREATE INDEX IF NOT EXISTS idx_personal_log_date
        ON personal_log(changed_at DESC);
    """)
    log.info("All indexes created (or already exist).")


# ---------------------------------------------------------------------------
# Seed: 18 Iraqi Governorates
# ---------------------------------------------------------------------------

_GOVERNORATES: list[tuple[str, str]] = [
    ("بغداد",        "Baghdad"),
    ("البصرة",       "Basra"),
    ("نينوى",        "Nineveh"),
    ("أربيل",        "Erbil"),
    ("النجف",        "Najaf"),
    ("كربلاء",       "Karbala"),
    ("الأنبار",      "Anbar"),
    ("ذي قار",       "Dhi Qar"),
    ("ميسان",        "Maysan"),
    ("واسط",         "Wasit"),
    ("بابل",         "Babylon"),
    ("ديالى",        "Diyala"),
    ("صلاح الدين",   "Saladin"),
    ("كركوك",        "Kirkuk"),
    ("المثنى",       "Muthanna"),
    ("القادسية",     "Al-Qadisiyyah"),
    ("السليمانية",   "Sulaymaniyah"),
    ("دهوك",         "Dohuk"),
]


def _seed_governorates(conn: sqlite3.Connection) -> None:
    """Insert the 18 Iraqi governorates if the table is empty."""
    count = conn.execute("SELECT COUNT(*) FROM governorates").fetchone()[0]
    if count > 0:
        log.info("Governorates already seeded (%d rows). Skipping.", count)
        return

    conn.executemany(
        "INSERT INTO governorates (name_ar, name_en) VALUES (?, ?)",
        _GOVERNORATES
    )
    log.info("Seeded %d governorates.", len(_GOVERNORATES))


# ---------------------------------------------------------------------------
# Seed: 195 Countries
# Format: (iso_code, name_ar, name_en)
# ---------------------------------------------------------------------------

_COUNTRIES: list[tuple[str, str, str]] = [
    ("AF", "أفغانستان",                          "Afghanistan"),
    ("AL", "ألبانيا",                             "Albania"),
    ("DZ", "الجزائر",                             "Algeria"),
    ("AD", "أندورا",                              "Andorra"),
    ("AO", "أنغولا",                              "Angola"),
    ("AG", "أنتيغوا وباربودا",                    "Antigua and Barbuda"),
    ("AR", "الأرجنتين",                           "Argentina"),
    ("AM", "أرمينيا",                             "Armenia"),
    ("AU", "أستراليا",                            "Australia"),
    ("AT", "النمسا",                              "Austria"),
    ("AZ", "أذربيجان",                            "Azerbaijan"),
    ("BS", "جزر البهاما",                         "Bahamas"),
    ("BH", "البحرين",                             "Bahrain"),
    ("BD", "بنغلاديش",                            "Bangladesh"),
    ("BB", "بربادوس",                             "Barbados"),
    ("BY", "بيلاروسيا",                           "Belarus"),
    ("BE", "بلجيكا",                              "Belgium"),
    ("BZ", "بليز",                                "Belize"),
    ("BJ", "بنين",                                "Benin"),
    ("BT", "بوتان",                               "Bhutan"),
    ("BO", "بوليفيا",                             "Bolivia"),
    ("BA", "البوسنة والهرسك",                     "Bosnia and Herzegovina"),
    ("BW", "بوتسوانا",                            "Botswana"),
    ("BR", "البرازيل",                            "Brazil"),
    ("BN", "بروناي",                              "Brunei"),
    ("BG", "بلغاريا",                             "Bulgaria"),
    ("BF", "بوركينا فاسو",                        "Burkina Faso"),
    ("BI", "بوروندي",                             "Burundi"),
    ("CV", "الرأس الأخضر",                        "Cape Verde"),
    ("KH", "كمبوديا",                             "Cambodia"),
    ("CM", "الكاميرون",                           "Cameroon"),
    ("CA", "كندا",                                "Canada"),
    ("CF", "جمهورية أفريقيا الوسطى",              "Central African Republic"),
    ("TD", "تشاد",                                "Chad"),
    ("CL", "تشيلي",                               "Chile"),
    ("CN", "الصين",                               "China"),
    ("CO", "كولومبيا",                            "Colombia"),
    ("KM", "جزر القمر",                           "Comoros"),
    ("CG", "جمهورية الكونغو",                     "Republic of the Congo"),
    ("CD", "جمهورية الكونغو الديمقراطية",         "Democratic Republic of the Congo"),
    ("CR", "كوستاريكا",                           "Costa Rica"),
    ("HR", "كرواتيا",                             "Croatia"),
    ("CU", "كوبا",                                "Cuba"),
    ("CY", "قبرص",                                "Cyprus"),
    ("CZ", "جمهورية التشيك",                      "Czech Republic"),
    ("DK", "الدنمارك",                            "Denmark"),
    ("DJ", "جيبوتي",                              "Djibouti"),
    ("DM", "دومينيكا",                            "Dominica"),
    ("DO", "جمهورية الدومينيكان",                 "Dominican Republic"),
    ("EC", "الإكوادور",                           "Ecuador"),
    ("EG", "مصر",                                 "Egypt"),
    ("SV", "السلفادور",                           "El Salvador"),
    ("GQ", "غينيا الاستوائية",                    "Equatorial Guinea"),
    ("ER", "إريتريا",                             "Eritrea"),
    ("EE", "إستونيا",                             "Estonia"),
    ("SZ", "إسواتيني",                            "Eswatini"),
    ("ET", "إثيوبيا",                             "Ethiopia"),
    ("FJ", "فيجي",                                "Fiji"),
    ("FI", "فنلندا",                              "Finland"),
    ("FR", "فرنسا",                               "France"),
    ("GA", "الغابون",                             "Gabon"),
    ("GM", "غامبيا",                              "Gambia"),
    ("GE", "جورجيا",                              "Georgia"),
    ("DE", "ألمانيا",                             "Germany"),
    ("GH", "غانا",                                "Ghana"),
    ("GR", "اليونان",                             "Greece"),
    ("GD", "غرينادا",                             "Grenada"),
    ("GT", "غواتيمالا",                           "Guatemala"),
    ("GN", "غينيا",                               "Guinea"),
    ("GW", "غينيا بيساو",                         "Guinea-Bissau"),
    ("GY", "غيانا",                               "Guyana"),
    ("HT", "هايتي",                               "Haiti"),
    ("HN", "هندوراس",                             "Honduras"),
    ("HU", "هنغاريا",                             "Hungary"),
    ("IS", "آيسلندا",                             "Iceland"),
    ("IN", "الهند",                               "India"),
    ("ID", "إندونيسيا",                           "Indonesia"),
    ("IR", "إيران",                               "Iran"),
    ("IQ", "العراق",                              "Iraq"),
    ("IE", "أيرلندا",                             "Ireland"),
    ("IL", "إسرائيل",                             "Israel"),
    ("IT", "إيطاليا",                             "Italy"),
    ("JM", "جامايكا",                             "Jamaica"),
    ("JP", "اليابان",                             "Japan"),
    ("JO", "الأردن",                              "Jordan"),
    ("KZ", "كازاخستان",                           "Kazakhstan"),
    ("KE", "كينيا",                               "Kenya"),
    ("KI", "كيريباتي",                            "Kiribati"),
    ("KP", "كوريا الشمالية",                      "North Korea"),
    ("KR", "كوريا الجنوبية",                      "South Korea"),
    ("KW", "الكويت",                              "Kuwait"),
    ("KG", "قيرغيزستان",                          "Kyrgyzstan"),
    ("LA", "لاوس",                                "Laos"),
    ("LV", "لاتفيا",                              "Latvia"),
    ("LB", "لبنان",                               "Lebanon"),
    ("LS", "ليسوتو",                              "Lesotho"),
    ("LR", "ليبيريا",                             "Liberia"),
    ("LY", "ليبيا",                               "Libya"),
    ("LI", "ليختنشتاين",                          "Liechtenstein"),
    ("LT", "ليتوانيا",                            "Lithuania"),
    ("LU", "لوكسمبورغ",                           "Luxembourg"),
    ("MG", "مدغشقر",                              "Madagascar"),
    ("MW", "مالاوي",                              "Malawi"),
    ("MY", "ماليزيا",                             "Malaysia"),
    ("MV", "جزر المالديف",                        "Maldives"),
    ("ML", "مالي",                                "Mali"),
    ("MT", "مالطا",                               "Malta"),
    ("MH", "جزر مارشال",                          "Marshall Islands"),
    ("MR", "موريتانيا",                           "Mauritania"),
    ("MU", "موريشيوس",                            "Mauritius"),
    ("MX", "المكسيك",                             "Mexico"),
    ("FM", "ميكرونيزيا",                          "Micronesia"),
    ("MD", "مولدوفا",                             "Moldova"),
    ("MC", "موناكو",                              "Monaco"),
    ("MN", "منغوليا",                             "Mongolia"),
    ("ME", "الجبل الأسود",                        "Montenegro"),
    ("MA", "المغرب",                              "Morocco"),
    ("MZ", "موزمبيق",                             "Mozambique"),
    ("MM", "ميانمار",                             "Myanmar"),
    ("NA", "ناميبيا",                             "Namibia"),
    ("NR", "ناورو",                               "Nauru"),
    ("NP", "نيبال",                               "Nepal"),
    ("NL", "هولندا",                              "Netherlands"),
    ("NZ", "نيوزيلندا",                           "New Zealand"),
    ("NI", "نيكاراغوا",                           "Nicaragua"),
    ("NE", "النيجر",                              "Niger"),
    ("NG", "نيجيريا",                             "Nigeria"),
    ("MK", "مقدونيا الشمالية",                    "North Macedonia"),
    ("NO", "النرويج",                             "Norway"),
    ("OM", "عُمان",                               "Oman"),
    ("PK", "باكستان",                             "Pakistan"),
    ("PW", "بالاو",                               "Palau"),
    ("PS", "فلسطين",                              "Palestine"),
    ("PA", "بنما",                                "Panama"),
    ("PG", "بابوا غينيا الجديدة",                 "Papua New Guinea"),
    ("PY", "باراغواي",                            "Paraguay"),
    ("PE", "بيرو",                                "Peru"),
    ("PH", "الفلبين",                             "Philippines"),
    ("PL", "بولندا",                              "Poland"),
    ("PT", "البرتغال",                            "Portugal"),
    ("QA", "قطر",                                 "Qatar"),
    ("RO", "رومانيا",                             "Romania"),
    ("RU", "روسيا",                               "Russia"),
    ("RW", "رواندا",                              "Rwanda"),
    ("KN", "سانت كيتس ونيفيس",                   "Saint Kitts and Nevis"),
    ("LC", "سانت لوسيا",                          "Saint Lucia"),
    ("VC", "سانت فنسنت وجزر غرينادين",            "Saint Vincent and the Grenadines"),
    ("WS", "ساموا",                               "Samoa"),
    ("SM", "سان مارينو",                          "San Marino"),
    ("ST", "ساو تومي وبرينسيبي",                  "Sao Tome and Principe"),
    ("SA", "المملكة العربية السعودية",             "Saudi Arabia"),
    ("SN", "السنغال",                             "Senegal"),
    ("RS", "صربيا",                               "Serbia"),
    ("SC", "سيشل",                                "Seychelles"),
    ("SL", "سيراليون",                            "Sierra Leone"),
    ("SG", "سنغافورة",                            "Singapore"),
    ("SK", "سلوفاكيا",                            "Slovakia"),
    ("SI", "سلوفينيا",                            "Slovenia"),
    ("SB", "جزر سليمان",                          "Solomon Islands"),
    ("SO", "الصومال",                             "Somalia"),
    ("ZA", "جنوب أفريقيا",                        "South Africa"),
    ("SS", "جنوب السودان",                        "South Sudan"),
    ("ES", "إسبانيا",                             "Spain"),
    ("LK", "سريلانكا",                            "Sri Lanka"),
    ("SD", "السودان",                             "Sudan"),
    ("SR", "سورينام",                             "Suriname"),
    ("SE", "السويد",                              "Sweden"),
    ("CH", "سويسرا",                              "Switzerland"),
    ("SY", "سوريا",                               "Syria"),
    ("TJ", "طاجيكستان",                           "Tajikistan"),
    ("TZ", "تنزانيا",                             "Tanzania"),
    ("TH", "تايلاند",                             "Thailand"),
    ("TL", "تيمور الشرقية",                       "Timor-Leste"),
    ("TG", "توغو",                                "Togo"),
    ("TO", "تونغا",                               "Tonga"),
    ("TT", "ترينيداد وتوباغو",                    "Trinidad and Tobago"),
    ("TN", "تونس",                                "Tunisia"),
    ("TR", "تركيا",                               "Turkey"),
    ("TM", "تركمانستان",                          "Turkmenistan"),
    ("TV", "توفالو",                              "Tuvalu"),
    ("UG", "أوغندا",                              "Uganda"),
    ("UA", "أوكرانيا",                            "Ukraine"),
    ("AE", "الإمارات العربية المتحدة",             "United Arab Emirates"),
    ("GB", "المملكة المتحدة",                     "United Kingdom"),
    ("US", "الولايات المتحدة الأمريكية",           "United States"),
    ("UY", "أوروغواي",                            "Uruguay"),
    ("UZ", "أوزبكستان",                           "Uzbekistan"),
    ("VU", "فانواتو",                             "Vanuatu"),
    ("VA", "الفاتيكان",                           "Vatican City"),
    ("VE", "فنزويلا",                             "Venezuela"),
    ("VN", "فيتنام",                              "Vietnam"),
    ("YE", "اليمن",                               "Yemen"),
    ("ZM", "زامبيا",                              "Zambia"),
    ("ZW", "زيمبابوي",                            "Zimbabwe"),
    ("XK", "كوسوفو",                              "Kosovo"),
]


def _seed_countries(conn: sqlite3.Connection) -> None:
    """Insert all countries if the table is empty."""
    count = conn.execute("SELECT COUNT(*) FROM countries").fetchone()[0]
    if count > 0:
        log.info("Countries already seeded (%d rows). Skipping.", count)
        return

    conn.executemany(
        "INSERT INTO countries (iso_code, name_ar, name_en) VALUES (?, ?, ?)",
        _COUNTRIES
    )
    log.info("Seeded %d countries.", len(_COUNTRIES))


# ---------------------------------------------------------------------------
# Grade Helper (used by all modules — defined once here)
# ---------------------------------------------------------------------------

def get_grade(average: int) -> tuple[str, str]:
    """
    Derive the Arabic and English grade label from a numeric average.

    Returns a tuple: (grade_ar, grade_en)

    Grade scale (Iraqi Ministry of Higher Education standard):
        90 – 100  →  امتياز      / Excellent
        80 –  89  →  جيد جداً   / Very Good
        70 –  79  →  جيد         / Good
        60 –  69  →  متوسط       / Medium
        50 –  59  →  مقبول       / Accepted
    """
    if average >= 90:
        return ("امتياز",    "Excellent")
    elif average >= 80:
        return ("جيد جداً",  "Very Good")
    elif average >= 70:
        return ("جيد",       "Good")
    elif average >= 60:
        return ("متوسط",     "Medium")
    else:
        return ("مقبول",     "Accepted")


# ---------------------------------------------------------------------------
# Quick Verification (run this file directly to test)
# ---------------------------------------------------------------------------

def _verify(conn: sqlite3.Connection) -> None:
    """Print row counts for all tables to confirm seeding worked."""
    tables = [
        "countries", "governorates", "departments",
        "personal", "courses", "students",
        "academic_periods", "enrollments"
    ]
    print("\n--- Database Verification ---")
    for table in tables:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        print(f"  {table:<20} {row[0]:>5} rows")

    print("\n--- Sample: First 5 Countries ---")
    for row in conn.execute("SELECT iso_code, name_ar, name_en FROM countries LIMIT 5"):
        print(f"  {row['iso_code']}  {row['name_ar']:<30} {row['name_en']}")

    print("\n--- Sample: All Governorates ---")
    for row in conn.execute("SELECT name_ar, name_en FROM governorates ORDER BY id"):
        print(f"  {row['name_ar']:<20} {row['name_en']}")

    print("\n--- Grade Scale Verification ---")
    for score in [95, 85, 75, 65, 55]:
        ar, en = get_grade(score)
        print(f"  {score}  →  {ar:<12} / {en}")
    print()


if __name__ == "__main__":
    init_db()
    with get_connection() as conn:
        _verify(conn)
    print("db.py is working correctly.\n")
