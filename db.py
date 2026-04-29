# =============================================================================
# db.py — Certificate Manager: Database Initialization & Utilities
# =============================================================================
# Tables (10): study_systems, countries, governorates, departments,
#              personal, courses, students, graduation_orders,
#              academic_periods, enrollments, course_departments,
#              personal_log, audit_log, settings
# =============================================================================

import sqlite3
import logging
from pathlib import Path

DB_PATH = Path("certificate_manager.db")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA encoding = 'UTF-8'")
    return conn


def insert_study_system(name_ar: str, name_en: str, calculation_rule: str, calculation_weights: str = "10:20:30:40") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO study_systems (name_ar, name_en, calculation_rule, calculation_weights) VALUES (?, ?, ?, ?)",
            (name_ar, name_en, calculation_rule, calculation_weights)
        )
        conn.commit()
        return cur.lastrowid


def insert_audit_log(table_name: str, action: str, summary: str, error_info: str = "") -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO audit_log (table_name, action, summary, error_info) VALUES (?, ?, ?, ?)",
            (table_name, action, summary, error_info or None)
        )
        conn.commit()


def init_db() -> None:
    log.info("Initializing database at: %s", DB_PATH.resolve())
    try:
        with get_connection() as conn:
            _create_tables(conn)
            _migrate_db(conn)
            _create_indexes(conn)
            _seed_study_systems(conn)
            _seed_governorates(conn)
            _seed_countries(conn)
            conn.commit()
        log.info("Database initialization complete.")
    except sqlite3.Error as e:
        log.error("Database initialization failed: %s", e)
        raise


def backup_db(dest_path: Path) -> None:
    import shutil
    shutil.copy2(DB_PATH, dest_path)
    log.info("Database backup created at: %s", dest_path)


def restore_db(src_path: Path) -> None:
    import shutil
    shutil.copy2(src_path, DB_PATH)
    log.info("Database restored from: %s", src_path)


def _migrate_db(conn: sqlite3.Connection) -> None:
    """
    Additive schema migrations. Each ALTER TABLE is wrapped in try/except
    to skip silently if the column already exists.
    """
    migrations = [
        # Legacy migration kept for old DBs
        "ALTER TABLE courses ADD COLUMN is_shared INTEGER NOT NULL DEFAULT 0",
        # New: study_system_id on students (nullable for legacy rows)
        "ALTER TABLE students ADD COLUMN study_system_id INTEGER REFERENCES study_systems(id) ON UPDATE CASCADE ON DELETE RESTRICT",
        # New: study_system_id on courses (nullable for legacy rows)
        "ALTER TABLE courses ADD COLUMN study_system_id INTEGER REFERENCES study_systems(id) ON UPDATE CASCADE ON DELETE RESTRICT",
        # New: study_system_id on academic_periods (nullable for legacy rows)
        "ALTER TABLE academic_periods ADD COLUMN study_system_id INTEGER REFERENCES study_systems(id) ON UPDATE CASCADE ON DELETE RESTRICT",
        "ALTER TABLE study_systems ADD COLUMN calculation_weights TEXT DEFAULT '10:20:30:40'",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
            log.info("Migration applied: %s", sql[:70])
        except sqlite3.OperationalError:
            pass


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    -- -------------------------------------------------------------------------
    -- study_systems: Dynamic study system definitions (Annual / Semester)
    -- calculation_rule: 'annual' or 'semester' — machine-readable key
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS study_systems (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        name_ar          TEXT    NOT NULL CHECK(length(name_ar) <= 60),
        name_en          TEXT    NOT NULL CHECK(length(name_en) <= 60),
        calculation_rule    TEXT    NOT NULL CHECK(calculation_rule IN ('annual','semester')),
        calculation_weights TEXT    DEFAULT '10:20:30:40',
        is_active        INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
        created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
    );

    -- -------------------------------------------------------------------------
    -- countries
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS countries (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        name_ar  TEXT    NOT NULL CHECK(length(name_ar)  <= 80),
        name_en  TEXT    NOT NULL CHECK(length(name_en)  <= 80),
        iso_code TEXT    NOT NULL UNIQUE CHECK(length(iso_code) <= 3)
    );

    -- -------------------------------------------------------------------------
    -- governorates
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS governorates (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        name_ar TEXT    NOT NULL UNIQUE CHECK(length(name_ar) <= 40),
        name_en TEXT    NOT NULL UNIQUE CHECK(length(name_en) <= 40)
    );

    -- -------------------------------------------------------------------------
    -- departments: No period_type — study system is per-student now.
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS departments (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name_ar     TEXT    NOT NULL CHECK(length(name_ar)    <= 100),
        name_en     TEXT    NOT NULL CHECK(length(name_en)    <= 100),
        college_ar  TEXT    NOT NULL CHECK(length(college_ar) <= 120),
        college_en  TEXT    NOT NULL CHECK(length(college_en) <= 120),
        study_years INTEGER NOT NULL DEFAULT 4 CHECK(study_years BETWEEN 2 AND 6)
    );

    -- -------------------------------------------------------------------------
    -- personal
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
        is_active         INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1))
    );

    -- -------------------------------------------------------------------------
    -- courses: period_type replaced by study_system_id FK.
    -- stage_number: for semester system 1-8 (sem1..sem8),
    --               for annual system 1-4 (year1..year4).
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS courses (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name_ar         TEXT    NOT NULL CHECK(length(name_ar)  <= 100),
        name_en         TEXT    NOT NULL CHECK(length(name_en)  <= 100),
        credit_hours    INTEGER NOT NULL CHECK(credit_hours BETWEEN 1 AND 6),
        department_id   INTEGER          REFERENCES departments(id)
                                         ON UPDATE CASCADE ON DELETE RESTRICT,
        stage_number    INTEGER NOT NULL,
        study_system_id INTEGER NOT NULL REFERENCES study_systems(id)
                                         ON UPDATE CASCADE ON DELETE RESTRICT,
        is_shared       INTEGER NOT NULL DEFAULT 0 CHECK(is_shared IN (0,1))
    );

    -- -------------------------------------------------------------------------
    -- students: study_system_id is NOT NULL — every student must belong to a system.
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS students (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name_ar         TEXT    NOT NULL CHECK(length(full_name_ar)     <= 150),
        full_name_en         TEXT    NOT NULL CHECK(length(full_name_en)     <= 150),
        date_of_birth        TEXT    NOT NULL CHECK(length(date_of_birth)    =  10),
        birthplace_id        INTEGER          REFERENCES governorates(id)
                                              ON UPDATE CASCADE ON DELETE RESTRICT,
        birthplace_other     TEXT             CHECK(birthplace_other IS NULL
                                               OR length(birthplace_other)   <= 100),
        nationality_id       INTEGER NOT NULL REFERENCES countries(id)
                                              ON UPDATE CASCADE ON DELETE RESTRICT,
        department_id        INTEGER NOT NULL REFERENCES departments(id)
                                              ON UPDATE CASCADE ON DELETE RESTRICT,
        study_system_id      INTEGER NOT NULL REFERENCES study_systems(id)
                                              ON UPDATE CASCADE ON DELETE RESTRICT,
        order_id             INTEGER          REFERENCES graduation_orders(id)
                                              ON UPDATE CASCADE ON DELETE SET NULL,
        admission_year       INTEGER NOT NULL CHECK(admission_year BETWEEN 1950 AND 2100),
        study_type           TEXT    NOT NULL CHECK(study_type IN ('morning', 'evening')),
        graduation_date      TEXT             CHECK(graduation_date IS NULL
                                               OR length(graduation_date)    =  10),
        graduation_semester  TEXT             CHECK(graduation_semester IS NULL
                                               OR graduation_semester IN ('first', 'second')),
        average              INTEGER          CHECK(average IS NULL
                                               OR average BETWEEN 50 AND 100),
        CHECK (
            (birthplace_id IS NOT NULL AND birthplace_other IS NULL)
            OR
            (birthplace_id IS NULL     AND birthplace_other IS NOT NULL)
        )
    );

    -- -------------------------------------------------------------------------
    -- graduation_orders
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS graduation_orders (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number        TEXT    NOT NULL CHECK(length(order_number)  <= 60),
        order_date          TEXT    NOT NULL CHECK(length(order_date)    =  10),
        department_id       INTEGER NOT NULL REFERENCES departments(id)
                                             ON UPDATE CASCADE ON DELETE RESTRICT,
        study_type          TEXT    NOT NULL DEFAULT 'morning'
                                             CHECK(study_type IN ('morning','evening')),
        admission_year      INTEGER NOT NULL CHECK(admission_year BETWEEN 1950 AND 2100),
        graduation_semester TEXT    NOT NULL CHECK(graduation_semester IN ('first','second')),
        num_students        INTEGER          CHECK(num_students IS NULL OR num_students > 0),
        notes               TEXT             CHECK(notes IS NULL OR length(notes) <= 500)
    );

    -- -------------------------------------------------------------------------
    -- academic_periods: period_type replaced by study_system_id FK.
    -- UNIQUE: one period per student per stage (system determines meaning).
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS academic_periods (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id      INTEGER NOT NULL REFERENCES students(id)
                                         ON UPDATE CASCADE ON DELETE CASCADE,
        academic_year   TEXT    NOT NULL CHECK(length(academic_year) = 9),
        study_system_id INTEGER NOT NULL REFERENCES study_systems(id)
                                         ON UPDATE CASCADE ON DELETE RESTRICT,
        stage_number    INTEGER NOT NULL,
        passed_round    TEXT    NOT NULL CHECK(passed_round IN ('first', 'second')),
        UNIQUE(student_id, stage_number, academic_year)
    );

    -- -------------------------------------------------------------------------
    -- enrollments
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS enrollments (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        period_id       INTEGER NOT NULL REFERENCES academic_periods(id)
                                         ON UPDATE CASCADE ON DELETE CASCADE,
        course_id       INTEGER NOT NULL REFERENCES courses(id)
                                         ON UPDATE CASCADE ON DELETE RESTRICT,
        score           REAL    NOT NULL CHECK(score BETWEEN 0 AND 100),
        is_second_round INTEGER NOT NULL DEFAULT 0 CHECK(is_second_round IN (0, 1)),
        UNIQUE(period_id, course_id)
    );

    -- -------------------------------------------------------------------------
    -- course_departments: Junction for shared courses.
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS course_departments (
        course_id     INTEGER NOT NULL REFERENCES courses(id)
                                       ON UPDATE CASCADE ON DELETE CASCADE,
        department_id INTEGER NOT NULL REFERENCES departments(id)
                                       ON UPDATE CASCADE ON DELETE CASCADE,
        PRIMARY KEY (course_id, department_id)
    );

    -- -------------------------------------------------------------------------
    -- personal_log
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
    -- audit_log
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

    -- -------------------------------------------------------------------------
    -- settings
    -- -------------------------------------------------------------------------
    CREATE TABLE IF NOT EXISTS settings (
        id                INTEGER PRIMARY KEY CHECK (id = 1),
        univ_name_ar      TEXT    NOT NULL DEFAULT 'جامعة واسط',
        univ_name_en      TEXT    NOT NULL DEFAULT 'Wasit University',
        college_name_ar   TEXT    NOT NULL DEFAULT 'كلية الهندسة',
        college_name_en   TEXT    NOT NULL DEFAULT 'College of Engineering',
        theme             TEXT    NOT NULL DEFAULT 'System',
        accent_color      TEXT    NOT NULL DEFAULT 'blue',
        font_family       TEXT    NOT NULL DEFAULT 'Arial',
        font_size_base    INTEGER NOT NULL DEFAULT 13
    );

    INSERT OR IGNORE INTO settings (id) VALUES (1);
    """)
    log.info("All tables created (or already exist).")


def _create_indexes(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE INDEX IF NOT EXISTS idx_students_name_ar
        ON students(full_name_ar);
    CREATE INDEX IF NOT EXISTS idx_students_name_en
        ON students(full_name_en);
    CREATE INDEX IF NOT EXISTS idx_students_dept_admission
        ON students(department_id, admission_year);
    CREATE INDEX IF NOT EXISTS idx_students_study_system
        ON students(study_system_id);
    CREATE INDEX IF NOT EXISTS idx_periods_student
        ON academic_periods(student_id);
    CREATE INDEX IF NOT EXISTS idx_periods_student_stage
        ON academic_periods(student_id, stage_number);
    CREATE INDEX IF NOT EXISTS idx_enrollments_period
        ON enrollments(period_id);
    CREATE INDEX IF NOT EXISTS idx_enrollments_course
        ON enrollments(course_id);
    CREATE INDEX IF NOT EXISTS idx_personal_active_page
        ON personal(is_active, page_location, display_order);
    CREATE INDEX IF NOT EXISTS idx_courses_dept_stage
        ON courses(department_id, stage_number);
    CREATE INDEX IF NOT EXISTS idx_courses_system
        ON courses(study_system_id);
    CREATE INDEX IF NOT EXISTS idx_audit_log_table_date
        ON audit_log(table_name, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_personal_log_date
        ON personal_log(changed_at DESC);
    """)
    log.info("All indexes created (or already exist).")


# ---------------------------------------------------------------------------
# Seed: Study Systems (2 default rows)
# ---------------------------------------------------------------------------

def _seed_study_systems(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO study_systems (id, name_ar, name_en, calculation_rule, calculation_weights, is_active) "
        "VALUES (1, 'النظام السنوي', 'Annual System', 'annual', '10:20:30:40', 1), "
        "       (2, 'النظام الفصلي', 'Semester System', 'semester', '10:20:30:40', 1)"
    )
    log.info("Study systems seeded (or already exist).")


# ---------------------------------------------------------------------------
# Seed: 18 Iraqi Governorates
# ---------------------------------------------------------------------------

_GOVERNORATES = [
    ("بغداد", "Baghdad"), ("البصرة", "Basra"), ("نينوى", "Nineveh"),
    ("أربيل", "Erbil"), ("النجف", "Najaf"), ("كربلاء", "Karbala"),
    ("الأنبار", "Anbar"), ("ذي قار", "Dhi Qar"), ("ميسان", "Maysan"),
    ("واسط", "Wasit"), ("بابل", "Babylon"), ("ديالى", "Diyala"),
    ("صلاح الدين", "Saladin"), ("كركوك", "Kirkuk"), ("المثنى", "Muthanna"),
    ("القادسية", "Al-Qadisiyyah"), ("السليمانية", "Sulaymaniyah"), ("دهوك", "Dohuk"),
]


def _seed_governorates(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM governorates").fetchone()[0]
    if count > 0:
        log.info("Governorates already seeded (%d rows). Skipping.", count)
        return
    conn.executemany("INSERT INTO governorates (name_ar, name_en) VALUES (?, ?)", _GOVERNORATES)
    log.info("Seeded %d governorates.", len(_GOVERNORATES))


# ---------------------------------------------------------------------------
# Seed: 195 Countries
# ---------------------------------------------------------------------------

_COUNTRIES = [
    ("AF","أفغانستان","Afghanistan"),("AL","ألبانيا","Albania"),("DZ","الجزائر","Algeria"),
    ("AD","أندورا","Andorra"),("AO","أنغولا","Angola"),("AG","أنتيغوا وباربودا","Antigua and Barbuda"),
    ("AR","الأرجنتين","Argentina"),("AM","أرمينيا","Armenia"),("AU","أستراليا","Australia"),
    ("AT","النمسا","Austria"),("AZ","أذربيجان","Azerbaijan"),("BS","جزر البهاما","Bahamas"),
    ("BH","البحرين","Bahrain"),("BD","بنغلاديش","Bangladesh"),("BB","بربادوس","Barbados"),
    ("BY","بيلاروسيا","Belarus"),("BE","بلجيكا","Belgium"),("BZ","بليز","Belize"),
    ("BJ","بنين","Benin"),("BT","بوتان","Bhutan"),("BO","بوليفيا","Bolivia"),
    ("BA","البوسنة والهرسك","Bosnia and Herzegovina"),("BW","بوتسوانا","Botswana"),
    ("BR","البرازيل","Brazil"),("BN","بروناي","Brunei"),("BG","بلغاريا","Bulgaria"),
    ("BF","بوركينا فاسو","Burkina Faso"),("BI","بوروندي","Burundi"),("CV","الرأس الأخضر","Cape Verde"),
    ("KH","كمبوديا","Cambodia"),("CM","الكاميرون","Cameroon"),("CA","كندا","Canada"),
    ("CF","جمهورية أفريقيا الوسطى","Central African Republic"),("TD","تشاد","Chad"),
    ("CL","تشيلي","Chile"),("CN","الصين","China"),("CO","كولومبيا","Colombia"),
    ("KM","جزر القمر","Comoros"),("CG","جمهورية الكونغو","Republic of the Congo"),
    ("CD","جمهورية الكونغو الديمقراطية","Democratic Republic of the Congo"),
    ("CR","كوستاريكا","Costa Rica"),("HR","كرواتيا","Croatia"),("CU","كوبا","Cuba"),
    ("CY","قبرص","Cyprus"),("CZ","جمهورية التشيك","Czech Republic"),("DK","الدنمارك","Denmark"),
    ("DJ","جيبوتي","Djibouti"),("DM","دومينيكا","Dominica"),("DO","جمهورية الدومينيكان","Dominican Republic"),
    ("EC","الإكوادور","Ecuador"),("EG","مصر","Egypt"),("SV","السلفادور","El Salvador"),
    ("GQ","غينيا الاستوائية","Equatorial Guinea"),("ER","إريتريا","Eritrea"),("EE","إستونيا","Estonia"),
    ("SZ","إسواتيني","Eswatini"),("ET","إثيوبيا","Ethiopia"),("FJ","فيجي","Fiji"),
    ("FI","فنلندا","Finland"),("FR","فرنسا","France"),("GA","الغابون","Gabon"),
    ("GM","غامبيا","Gambia"),("GE","جورجيا","Georgia"),("DE","ألمانيا","Germany"),
    ("GH","غانا","Ghana"),("GR","اليونان","Greece"),("GD","غرينادا","Grenada"),
    ("GT","غواتيمالا","Guatemala"),("GN","غينيا","Guinea"),("GW","غينيا بيساو","Guinea-Bissau"),
    ("GY","غيانا","Guyana"),("HT","هايتي","Haiti"),("HN","هندوراس","Honduras"),
    ("HU","هنغاريا","Hungary"),("IS","آيسلندا","Iceland"),("IN","الهند","India"),
    ("ID","إندونيسيا","Indonesia"),("IR","إيران","Iran"),("IQ","العراق","Iraq"),
    ("IE","أيرلندا","Ireland"),("IL","إسرائيل","Israel"),("IT","إيطاليا","Italy"),
    ("JM","جامايكا","Jamaica"),("JP","اليابان","Japan"),("JO","الأردن","Jordan"),
    ("KZ","كازاخستان","Kazakhstan"),("KE","كينيا","Kenya"),("KI","كيريباتي","Kiribati"),
    ("KP","كوريا الشمالية","North Korea"),("KR","كوريا الجنوبية","South Korea"),("KW","الكويت","Kuwait"),
    ("KG","قيرغيزستان","Kyrgyzstan"),("LA","لاوس","Laos"),("LV","لاتفيا","Latvia"),
    ("LB","لبنان","Lebanon"),("LS","ليسوتو","Lesotho"),("LR","ليبيريا","Liberia"),
    ("LY","ليبيا","Libya"),("LI","ليختنشتاين","Liechtenstein"),("LT","ليتوانيا","Lithuania"),
    ("LU","لوكسمبورغ","Luxembourg"),("MG","مدغشقر","Madagascar"),("MW","مالاوي","Malawi"),
    ("MY","ماليزيا","Malaysia"),("MV","جزر المالديف","Maldives"),("ML","مالي","Mali"),
    ("MT","مالطا","Malta"),("MH","جزر مارشال","Marshall Islands"),("MR","موريتانيا","Mauritania"),
    ("MU","موريشيوس","Mauritius"),("MX","المكسيك","Mexico"),("FM","ميكرونيزيا","Micronesia"),
    ("MD","مولدوفا","Moldova"),("MC","موناكو","Monaco"),("MN","منغوليا","Mongolia"),
    ("ME","الجبل الأسود","Montenegro"),("MA","المغرب","Morocco"),("MZ","موزمبيق","Mozambique"),
    ("MM","ميانمار","Myanmar"),("NA","ناميبيا","Namibia"),("NR","ناورو","Nauru"),
    ("NP","نيبال","Nepal"),("NL","هولندا","Netherlands"),("NZ","نيوزيلندا","New Zealand"),
    ("NI","نيكاراغوا","Nicaragua"),("NE","النيجر","Niger"),("NG","نيجيريا","Nigeria"),
    ("MK","مقدونيا الشمالية","North Macedonia"),("NO","النرويج","Norway"),("OM","عُمان","Oman"),
    ("PK","باكستان","Pakistan"),("PW","بالاو","Palau"),("PS","فلسطين","Palestine"),
    ("PA","بنما","Panama"),("PG","بابوا غينيا الجديدة","Papua New Guinea"),("PY","باراغواي","Paraguay"),
    ("PE","بيرو","Peru"),("PH","الفلبين","Philippines"),("PL","بولندا","Poland"),
    ("PT","البرتغال","Portugal"),("QA","قطر","Qatar"),("RO","رومانيا","Romania"),
    ("RU","روسيا","Russia"),("RW","رواندا","Rwanda"),("KN","سانت كيتس ونيفيس","Saint Kitts and Nevis"),
    ("LC","سانت لوسيا","Saint Lucia"),("VC","سانت فنسنت وجزر غرينادين","Saint Vincent and the Grenadines"),
    ("WS","ساموا","Samoa"),("SM","سان مارينو","San Marino"),("ST","ساو تومي وبرينسيبي","Sao Tome and Principe"),
    ("SA","المملكة العربية السعودية","Saudi Arabia"),("SN","السنغال","Senegal"),("RS","صربيا","Serbia"),
    ("SC","سيشل","Seychelles"),("SL","سيراليون","Sierra Leone"),("SG","سنغافورة","Singapore"),
    ("SK","سلوفاكيا","Slovakia"),("SI","سلوفينيا","Slovenia"),("SB","جزر سليمان","Solomon Islands"),
    ("SO","الصومال","Somalia"),("ZA","جنوب أفريقيا","South Africa"),("SS","جنوب السودان","South Sudan"),
    ("ES","إسبانيا","Spain"),("LK","سريلانكا","Sri Lanka"),("SD","السودان","Sudan"),
    ("SR","سورينام","Suriname"),("SE","السويد","Sweden"),("CH","سويسرا","Switzerland"),
    ("SY","سوريا","Syria"),("TJ","طاجيكستان","Tajikistan"),("TZ","تنزانيا","Tanzania"),
    ("TH","تايلاند","Thailand"),("TL","تيمور الشرقية","Timor-Leste"),("TG","توغو","Togo"),
    ("TO","تونغا","Tonga"),("TT","ترينيداد وتوباغو","Trinidad and Tobago"),("TN","تونس","Tunisia"),
    ("TR","تركيا","Turkey"),("TM","تركمانستان","Turkmenistan"),("TV","توفالو","Tuvalu"),
    ("UG","أوغندا","Uganda"),("UA","أوكرانيا","Ukraine"),("AE","الإمارات العربية المتحدة","United Arab Emirates"),
    ("GB","المملكة المتحدة","United Kingdom"),("US","الولايات المتحدة الأمريكية","United States"),
    ("UY","أوروغواي","Uruguay"),("UZ","أوزبكستان","Uzbekistan"),("VU","فانواتو","Vanuatu"),
    ("VA","الفاتيكان","Vatican City"),("VE","فنزويلا","Venezuela"),("VN","فيتنام","Vietnam"),
    ("YE","اليمن","Yemen"),("ZM","زامبيا","Zambia"),("ZW","زيمبابوي","Zimbabwe"),("XK","كوسوفو","Kosovo"),
]


def _seed_countries(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM countries").fetchone()[0]
    if count > 0:
        log.info("Countries already seeded (%d rows). Skipping.", count)
        return
    conn.executemany("INSERT INTO countries (iso_code, name_ar, name_en) VALUES (?, ?, ?)", _COUNTRIES)
    log.info("Seeded %d countries.", len(_COUNTRIES))


# ---------------------------------------------------------------------------
# Grade Helper
# ---------------------------------------------------------------------------

def get_grade(average: int) -> tuple[str, str]:
    if average >= 90:
        return ("امتياز",   "Excellent")
    elif average >= 80:
        return ("جيد جداً", "Very Good")
    elif average >= 70:
        return ("جيد",      "Good")
    elif average >= 60:
        return ("متوسط",    "Medium")
    else:
        return ("مقبول",    "Accepted")


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def _verify(conn: sqlite3.Connection) -> None:
    tables = [
        "study_systems", "countries", "governorates", "departments",
        "personal", "courses", "students", "graduation_orders",
        "academic_periods", "enrollments",
    ]
    print("\n--- Database Verification ---")
    for table in tables:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        print(f"  {table:<22} {row[0]:>5} rows")
    print()


if __name__ == "__main__":
    init_db()
    with get_connection() as conn:
        _verify(conn)
    print("db.py is working correctly.\n")
