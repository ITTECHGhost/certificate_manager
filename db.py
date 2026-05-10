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

log = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA encoding = 'UTF-8'")
    return conn


def insert_study_system(name_ar: str, name_en: str, calculation_rule: str, semester_weight: int = 50, year_weight: int = 25, prefix: str = "", display_type: str = "year", weight_type: str = "year_weight") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO study_systems (name_ar, name_en, calculation_rule, semester_weight, year_weight, prefix, display_type, weight_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name_ar, name_en, calculation_rule, semester_weight, year_weight, prefix, display_type, weight_type)
        )
        conn.commit()
        return cur.lastrowid


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
    # Add new columns to study_systems if missing
    try:
        conn.execute("ALTER TABLE study_systems ADD COLUMN display_type TEXT DEFAULT 'year'")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE study_systems ADD COLUMN weight_type TEXT DEFAULT 'year_weight'")
    except sqlite3.OperationalError:
        pass
        
    try:
        conn.execute("ALTER TABLE students ADD COLUMN gender TEXT NOT NULL DEFAULT 'M' CHECK(gender IN ('M', 'F'))")
    except sqlite3.OperationalError:
        pass
        
    try:
        conn.execute("ALTER TABLE students ADD COLUMN sequence_number INTEGER")
    except sqlite3.OperationalError:
        pass
        
    try:
        conn.execute("ALTER TABLE students ADD COLUMN postgraduation_no INTEGER")
    except sqlite3.OperationalError:
        pass

    # Ensure user_preferences exists for legacy setups
    conn.execute("""
    CREATE TABLE IF NOT EXISTS user_preferences (
        user_id INTEGER PRIMARY KEY,
        theme TEXT DEFAULT 'System',
        accent_color TEXT DEFAULT 'blue',
        font_family TEXT DEFAULT 'Arial',
        font_size_base INTEGER DEFAULT 13,
        FOREIGN KEY(user_id) REFERENCES personnel(id) ON DELETE CASCADE
    )
    """)
    
    # 2026-05-02: Support for signatures and template mapping in personnel
    try:
        conn.execute("ALTER TABLE personnel ADD COLUMN is_signature INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
        
    try:
        conn.execute("ALTER TABLE personnel ADD COLUMN template_appearance_id TEXT")
    except sqlite3.OperationalError:
        pass


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK (id = 1), univ_name_ar TEXT, univ_name_en TEXT, college_name_ar TEXT, college_name_en TEXT, theme TEXT, accent_color TEXT, font_family TEXT, font_size_base INTEGER);
    CREATE TABLE IF NOT EXISTS personnel (id INTEGER PRIMARY KEY AUTOINCREMENT, name_ar TEXT NOT NULL, name_en TEXT, username TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'user' CHECK(role IN ('admin', 'user')), academic_title_ar TEXT, academic_title_en TEXT, responsibility_ar TEXT, responsibility_en TEXT, display_order INTEGER, page_location TEXT CHECK(page_location IN ('front', 'back')), is_active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS user_preferences (user_id INTEGER PRIMARY KEY, theme TEXT DEFAULT 'System', accent_color TEXT DEFAULT 'blue', font_family TEXT DEFAULT 'Arial', font_size_base INTEGER DEFAULT 13, FOREIGN KEY(user_id) REFERENCES personnel(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS certificate_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, generated_by INTEGER NOT NULL, generated_at TEXT DEFAULT (datetime('now', 'localtime')));
    CREATE TABLE IF NOT EXISTS study_systems (id INTEGER PRIMARY KEY AUTOINCREMENT, name_ar TEXT NOT NULL, name_en TEXT NOT NULL, calculation_rule TEXT NOT NULL, calculation_weights TEXT DEFAULT '10:20:30:40', semester_weight INTEGER DEFAULT 50, year_weight INTEGER DEFAULT 25, is_active INTEGER DEFAULT 1, prefix TEXT DEFAULT '', display_type TEXT DEFAULT 'year' CHECK(display_type IN ('year', 'semester')), weight_type TEXT DEFAULT 'year_weight' CHECK(weight_type IN ('year_weight', 'level_weight', 'no_weight')));
    CREATE TABLE IF NOT EXISTS departments (id INTEGER PRIMARY KEY AUTOINCREMENT, name_ar TEXT NOT NULL, name_en TEXT NOT NULL, study_years INTEGER DEFAULT 4);
    CREATE TABLE IF NOT EXISTS countries (id INTEGER PRIMARY KEY AUTOINCREMENT, name_ar TEXT, name_en TEXT, iso_code TEXT UNIQUE);
    CREATE TABLE IF NOT EXISTS governorates (id INTEGER PRIMARY KEY AUTOINCREMENT, name_ar TEXT, name_en TEXT);
    CREATE TABLE IF NOT EXISTS graduation_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, order_number TEXT NOT NULL, order_date TEXT NOT NULL, department_id INTEGER NOT NULL, study_type TEXT DEFAULT 'morning', admission_year INTEGER NOT NULL, graduation_semester TEXT NOT NULL, num_students INTEGER, notes TEXT, UNIQUE(order_number, department_id, study_type, admission_year));
    CREATE TABLE IF NOT EXISTS courses (id INTEGER PRIMARY KEY AUTOINCREMENT, name_ar TEXT NOT NULL, name_en TEXT NOT NULL, credit_hours INTEGER NOT NULL, department_id INTEGER, stage_number INTEGER NOT NULL, study_system_id INTEGER NOT NULL, is_shared INTEGER DEFAULT 0, UNIQUE(name_ar, department_id, study_system_id));
    CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY AUTOINCREMENT, full_name_ar TEXT NOT NULL, full_name_en TEXT NOT NULL, gender TEXT NOT NULL DEFAULT 'M' CHECK(gender IN ('M', 'F')), sequence_number INTEGER, postgraduation_no INTEGER, date_of_birth TEXT NOT NULL, birthplace_id INTEGER, birthplace_other TEXT, nationality_id INTEGER NOT NULL, department_id INTEGER NOT NULL, study_system_id INTEGER NOT NULL, order_id INTEGER, admission_year INTEGER NOT NULL, study_type TEXT NOT NULL, graduation_date TEXT, graduation_semester TEXT, average REAL);
    CREATE TABLE IF NOT EXISTS academic_periods (id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, academic_year TEXT NOT NULL, study_system_id INTEGER NOT NULL, stage_number INTEGER NOT NULL, passed_round TEXT NOT NULL, UNIQUE(student_id, stage_number, academic_year));
    CREATE TABLE IF NOT EXISTS enrollments (id INTEGER PRIMARY KEY AUTOINCREMENT, period_id INTEGER NOT NULL, course_id INTEGER NOT NULL, score REAL NOT NULL, is_second_round INTEGER DEFAULT 0, UNIQUE(period_id, course_id));

    INSERT OR IGNORE INTO settings (id, univ_name_ar, univ_name_en, college_name_ar, college_name_en, theme, accent_color, font_family, font_size_base) 
    VALUES (1, 'جامعة واسط', 'Wasit University', 'كلية الهندسة', 'College of Engineering', 'System', 'blue', 'Arial', 13);
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
    CREATE INDEX IF NOT EXISTS idx_personnel_active_page
        ON personnel(is_active, page_location, display_order);
    CREATE INDEX IF NOT EXISTS idx_courses_dept_stage
        ON courses(department_id, stage_number);
    CREATE INDEX IF NOT EXISTS idx_courses_system
        ON courses(study_system_id);
    CREATE INDEX IF NOT EXISTS idx_personnel_username
        ON personnel(username);
    """)
    log.info("All indexes created (or already exist).")



# ---------------------------------------------------------------------------
# Seed: Study Systems (2 default rows)
# ---------------------------------------------------------------------------

def _seed_study_systems(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO study_systems (id, name_ar, name_en, calculation_rule, semester_weight, year_weight, prefix, display_type, weight_type, is_active) "
        "VALUES (1, 'النظام السنوي', 'Annual System', 'annual', 50, 25, 'A', 'year', 'year_weight', 1), "
        "       (2, 'النظام الفصلي', 'Semester System', 'semester', 50, 25, 'S', 'semester', 'year_weight', 1)"
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
        "personnel", "courses", "students", "graduation_orders",
        "academic_periods", "enrollments", "certificate_logs"
    ]
    print("\n--- Database Verification ---")
    for table in tables:
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            print(f"  {table:<22} {row[0]:>5} rows")
        except Exception:
            pass
    print()


if __name__ == "__main__":
    init_db()
    with get_connection() as conn:
        _verify(conn)
    print("db.py is working correctly.\n")
