import sqlite3
import re
import os
import logging
from typing import List, Dict, Any, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("migration.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SQLParser:
    """A robust line-by-line SQL dump parser for MySQL exports."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        
    def parse(self):
        """Generates (table_name, list_of_rows) from the SQL file."""
        if not os.path.exists(self.file_path):
            logger.error(f"SQL file not found: {self.file_path}")
            return

        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            buffer = []
            in_insert = False
            current_table = None
            
            for line in f:
                line = line.strip()
                if not line or line.startswith('--') or line.startswith('/*'):
                    continue
                
                insert_match = re.match(r"INSERT INTO\s+[`]?(\w+)[`]?\s*(?:\((.*?)\))?\s*VALUES", line, re.IGNORECASE)
                if insert_match:
                    current_table = insert_match.group(1)
                    in_insert = True
                    start_pos = line.upper().find("VALUES") + 6
                    buffer.append(line[start_pos:])
                elif in_insert:
                    buffer.append(line)
                
                if in_insert and line.endswith(';'):
                    full_insert = " ".join(buffer)
                    rows = self._extract_rows(full_insert)
                    yield current_table, rows
                    buffer = []
                    in_insert = False

    def _extract_rows(self, content: str) -> List[List[Optional[str]]]:
        rows = []
        current_row = ""
        in_string = False
        quote_char = None
        parens_level = 0
        
        content = content.strip().rstrip(';')
        
        i = 0
        while i < len(content):
            c = content[i]
            if not in_string:
                if c == "(":
                    if parens_level == 0: current_row = ""
                    else: current_row += c
                    parens_level += 1
                elif c == ")":
                    parens_level -= 1
                    if parens_level == 0:
                        rows.append(self._parse_row_values(current_row))
                        current_row = ""
                    else: current_row += c
                elif c in ("'", '"'):
                    in_string = True
                    quote_char = c
                    current_row += c
                elif c != "," or parens_level > 0:
                    current_row += c
            else:
                current_row += c
                if c == quote_char:
                    if i > 0 and content[i-1] == "\\": pass
                    else: in_string = False
            i += 1
        return rows

    def _parse_row_values(self, row_str: str) -> List[Optional[str]]:
        values = []
        current_val = ""
        in_string = False
        quote_char = None
        
        i = 0
        while i < len(row_str):
            c = row_str[i]
            if not in_string:
                if c in ("'", '"'):
                    in_string = True
                    quote_char = c
                elif c == ",":
                    values.append(self._clean_val(current_val))
                    current_val = ""
                else:
                    current_val += c
            else:
                if c == quote_char:
                    if i > 0 and row_str[i-1] == "\\": current_val += c
                    else: in_string = False
                else:
                    current_val += c
            i += 1
        values.append(self._clean_val(current_val))
        return values

    def _clean_val(self, val: str) -> Optional[str]:
        val = val.strip()
        if val.upper() == 'NULL': return None
        if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
            val = val[1:-1]
        return val.replace("\\'", "'").replace('\\"', '"')

class MigrationManager:
    def __init__(self, sql_dump_path: str, db_path: str):
        self.sql_dump_path = sql_dump_path
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.dept_map = {}
        self.country_map = {}
        self.gov_map = {}
        self._load_mappings()

    def _load_mappings(self):
        self.cursor.execute("SELECT id, name_en FROM countries")
        self.country_map = {row[1].lower(): row[0] for row in self.cursor.fetchall()}
        self.cursor.execute("SELECT id, name_en FROM governorates")
        self.gov_map = {row[1].lower(): row[0] for row in self.cursor.fetchall()}
        
    def get_or_create_dept(self, name_ar, period_type='semester'):
        if name_ar in self.dept_map: return self.dept_map[name_ar]
        self.cursor.execute("SELECT id FROM departments WHERE name_ar = ?", (name_ar,))
        row = self.cursor.fetchone()
        if row:
            self.dept_map[name_ar] = row[0]
            return row[0]
        name_en = "Information Systems" if "نظم" in name_ar else "Computer Science"
        self.cursor.execute(
            "INSERT INTO departments (name_ar, name_en, college_ar, college_en, study_years) VALUES (?, ?, ?, ?, ?)",
            (name_ar, name_en, "كلية علوم الحاسوب وتكنولوجيا المعلومات", "College of Computer Science and IT", 4)
        )
        dept_id = self.cursor.lastrowid
        self.dept_map[name_ar] = dept_id
        return dept_id

    def run(self):
        logger.info("Starting migration...")
        
        # Clear existing data to ensure a clean import and avoid IntegrityErrors
        logger.info("Clearing existing database tables...")
        self.cursor.executescript("""
            DELETE FROM enrollments;
            DELETE FROM academic_periods;
            DELETE FROM courses;
            DELETE FROM students;
            DELETE FROM graduation_orders;
            DELETE FROM departments;
        """)
        
        parser = SQLParser(self.sql_dump_path)
        
        for table_name, rows in parser.parse():
            logger.info(f"Processing table: {table_name} ({len(rows)} rows)")
            if table_name == 'admin':
                self.migrate_users(rows)
            elif table_name == 'info_system':
                self.migrate_info_system(rows)
            elif table_name == 'order_university':
                self.migrate_orders(rows)
            elif table_name in ('students_140', 'students_q'):
                system_id = 2 if '140' in table_name else 1
                period_type = 'semester' if '140' in table_name else 'year'
                self.migrate_students(rows, system_id, period_type)
            elif table_name in ('subjects_students_140', 'subjects_students_q'):
                period_type = 'semester' if '140' in table_name else 'year'
                self.migrate_enrollments(rows, period_type)
            elif table_name == 'signatures':
                self.migrate_personal(rows)
                
        self.conn.commit()
        logger.info("Migration complete.")

    def migrate_users(self, rows):
        self.cursor.execute("DELETE FROM users")
        for row in rows:
            if len(row) < 5: continue
            role = 'admin' if 'مسؤول' in row[4] else 'user'
            try:
                self.cursor.execute(
                    "INSERT INTO users (id, name, username, password, role) VALUES (?, ?, ?, ?, ?)",
                    (row[0], row[1], row[2], row[3], role)
                )
            except sqlite3.IntegrityError:
                pass

    def migrate_info_system(self, rows):
        if not rows: return
        row = rows[0]
        if len(row) < 5: return
        try:
            self.cursor.execute(
                "UPDATE settings SET univ_name_ar = ?, college_name_ar = ?, univ_name_en = ?, college_name_en = ? WHERE id = 1",
                (row[1], row[2], row[3], row[4])
            )
        except sqlite3.Error:
            pass

    def migrate_orders(self, rows):
        for row in rows:
            if len(row) < 9: continue
            dept_id = self.get_or_create_dept(row[1])
            study_type = 'evening' if 'مسائي' in row[2] else 'morning'
            admission_year = int(row[3]) if row[3].isdigit() else 2018
            sem_val = (row[4] if row[4] else '') + ' ' + (row[5] if len(row)>5 and row[5] else '')
            sem = 'second' if 'ثاني' in sem_val else 'first'
            num_st = int(row[8]) if row[8] and row[8].isdigit() else None
            
            try:
                self.cursor.execute(
                    "INSERT INTO graduation_orders (order_number, order_date, department_id, study_type, admission_year, graduation_semester, num_students) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (row[6], row[7], dept_id, study_type, admission_year, sem, num_st)
                )
            except sqlite3.IntegrityError:
                pass

    def migrate_personal(self, rows):
        for row in rows:
            if len(row) < 37: continue
            self.cursor.execute("DELETE FROM personal")
            sigs = [
                (row[31], row[34], row[32], row[35], row[33], row[36], 1, "front"),
                (row[13], row[14], row[15], row[16], row[17], row[18], 2, "front"),
                (row[7], row[8], row[9], row[10], row[11], row[12], 3, "back"),
                (row[1], row[2], row[3], row[4], row[5], row[6], 4, "back"),
                (row[25], row[26], row[27], row[28], row[29], row[30], 5, "back"),
                (row[19], row[20], row[21], row[22], row[23], row[24], 6, "back")
            ]
            for s in sigs:
                try:
                    self.cursor.execute(
                        "INSERT INTO personal (name_ar, name_en, academic_title_ar, academic_title_en, responsibility_ar, responsibility_en, display_order, page_location, is_active) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
                        s
                    )
                except sqlite3.Error:
                    pass

    def migrate_students(self, rows, system_id, period_type):
        for row in rows:
            if len(row) < 13: continue
            dept_id = self.get_or_create_dept(row[5], period_type)
            gov_id = self.gov_map.get(row[14].lower(), 2)
            country_id = self.country_map.get(row[13].lower(), 111)
            study_type = 'evening' if 'مسائية' in row[4] else 'morning'
            sem = row[15].lower() if len(row) > 15 and row[15] else 'first'
            if sem not in ('first', 'second'): sem = 'first'
            
            avg_str = row[8]
            avg = None
            if avg_str:
                try: avg = round(float(avg_str))
                except: pass

            admission_year = int(row[6]) if row[6].isdigit() else 2018

            order_number = row[11] if len(row) > 11 else None
            order_id = None
            if order_number:
                self.cursor.execute(
                    "SELECT id FROM graduation_orders WHERE order_number = ? AND department_id = ? AND study_type = ?", 
                    (order_number, dept_id, study_type)
                )
                orow = self.cursor.fetchone()
                if orow: 
                    order_id = orow[0]
                else:
                    self.cursor.execute("SELECT id FROM graduation_orders WHERE order_number = ?", (order_number,))
                    orow = self.cursor.fetchone()
                    if orow: order_id = orow[0]

            try:
                self.cursor.execute(
                    "INSERT INTO students (id, full_name_ar, full_name_en, date_of_birth, birthplace_id, nationality_id, department_id, study_system_id, order_id, admission_year, study_type, graduation_semester, average) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row[0], row[1], row[2], '2000-01-01', gov_id, country_id, dept_id, 
                        system_id, order_id, admission_year, 
                        study_type, sem, avg
                    )
                )
            except sqlite3.IntegrityError:
                pass

    def migrate_enrollments(self, rows, period_type):
        for row in rows:
            if len(row) == 11:
                sid, code, n_ar, n_en, units, grade, year, sem_ar, attempt = row[1], row[2], row[3], row[4], row[6], row[7], row[8], row[9], row[10]
            else:
                sid, code, n_ar, n_en, grade, units, year, sem_ar = row[1], "", row[2], row[3], row[5], row[6], row[7], row[8]
                attempt = "First"

            # 1. Get/Create Course
            self.cursor.execute("SELECT id FROM courses WHERE name_ar = ?", (n_ar,))
            crow = self.cursor.fetchone()
            if crow: cid = crow[0]
            else:
                self.cursor.execute(
                    "INSERT INTO courses (name_ar, name_en, credit_hours, department_id, stage_number, study_system_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (n_ar, n_en, int(units) if units and units.isdigit() else 3, 1, 1, 1 if period_type == 'year' else 2)
                )
                cid = self.cursor.lastrowid
            
            if len(year) == 4: year_str = f"{int(year)-1}-{year}"
            else: year_str = year if len(year) == 9 else "2020-2021"
            
            # 2. Get/Create Academic Period
            self.cursor.execute(
                "SELECT id FROM academic_periods WHERE student_id = ? AND academic_year = ? AND study_system_id = ?", 
                (sid, year_str, 1 if period_type == 'year' else 2)
            )
            prow = self.cursor.fetchone()
            if prow: pid = prow[0]
            else:
                try:
                    self.cursor.execute(
                        "INSERT INTO academic_periods (student_id, academic_year, study_system_id, stage_number, passed_round) VALUES (?, ?, ?, ?, ?)",
                        (sid, year_str, 1 if period_type == 'year' else 2, 1, 'first')
                    )
                    pid = self.cursor.lastrowid
                except sqlite3.IntegrityError:
                    self.cursor.execute("SELECT id FROM academic_periods WHERE student_id = ? AND academic_year = ?", (sid, year_str))
                    res = self.cursor.fetchone()
                    if res: pid = res[0]
                    else: continue

            # 3. Create Enrollment
            try:
                self.cursor.execute(
                    "INSERT INTO enrollments (period_id, course_id, score, is_second_round) VALUES (?, ?, ?, ?)",
                    (pid, cid, float(grade) if grade and grade.replace('.','',1).isdigit() else 0, 1 if 'ثاني' in sem_ar or 'ثانية' in attempt else 0)
                )
            except sqlite3.IntegrityError:
                pass

def run_migration(sql_dump_path: str):
    from db import DB_PATH
    manager = MigrationManager(sql_dump_path, str(DB_PATH))
    manager.run()

if __name__ == "__main__":
    SQL_FILE = r"f:\CR_PY\certificate_manager\project2 (2).sql"
    DB_FILE = r"f:\CR_PY\certificate_manager\certificate_manager1.db"
    manager = MigrationManager(SQL_FILE, DB_FILE)
    manager.run()
