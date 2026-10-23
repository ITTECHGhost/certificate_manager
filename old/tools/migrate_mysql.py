import re
import os
import logging
import sys
from typing import List, Optional

# Add root directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# =============================================================================
# LOGGING SETUP (Text Files)
# =============================================================================
system_logger = logging.getLogger("system")
system_logger.setLevel(logging.INFO)
sys_handler = logging.FileHandler("system_log.txt", encoding='utf-8')
sys_handler.setFormatter(logging.Formatter('%(asctime)s [SYSTEM] %(levelname)s: %(message)s'))
system_logger.addHandler(sys_handler)
system_logger.addHandler(logging.StreamHandler())

from db import init_db, get_connection

activity_logger = logging.getLogger("activity")
activity_logger.setLevel(logging.INFO)
act_handler = logging.FileHandler("activity_log.txt", encoding='utf-8')
act_handler.setFormatter(logging.Formatter('%(asctime)s [ACTIVITY] %(message)s'))
activity_logger.addHandler(act_handler)


# =============================================================================
# SQL PARSER
# =============================================================================
class SQLParser:
    """A robust line-by-line SQL dump parser for MySQL exports."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        
    def parse(self):
        if not os.path.exists(self.file_path):
            system_logger.error(f"SQL file not found: {self.file_path}")
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


# =============================================================================
# MIGRATION MANAGER  (MySQL target)
# =============================================================================
class MigrationManager:
    def __init__(self, sql_dump_path: str):
        self.sql_dump_path = sql_dump_path
        
        # Ensure schema is up-to-date (adds missing columns, etc.)
        init_db()
        
        self.conn = get_connection()
        self.cursor = self.conn.cursor(buffered=True)
        self.cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        self.dept_map = {}
        self.country_map = {}
        self.gov_map = {}
        
        self._load_mappings()

    def _load_mappings(self):
        self.cursor.execute("SELECT id, name_en FROM countries")
        self.country_map = {row[1].lower(): row[0] for row in self.cursor.fetchall()}
        self.cursor.execute("SELECT id, name_en FROM governorates")
        self.gov_map = {row[1].lower(): row[0] for row in self.cursor.fetchall()}
        
    def get_or_create_dept(self, name_ar):
        name_ar = str(name_ar or '').strip()
        if not name_ar: name_ar = "قسم عام"
        
        if name_ar in self.dept_map: return self.dept_map[name_ar]
        self.cursor.execute("SELECT id FROM departments WHERE name_ar = %s", (name_ar,))
        row = self.cursor.fetchone()
        if row:
            self.dept_map[name_ar] = row[0]
            return row[0]
        
        name_en = "Information Systems" if "نظم" in name_ar else "Computer Science"
        
        # Check what columns the departments table has
        self.cursor.execute("DESCRIBE departments")
        cols = [r[0] for r in self.cursor.fetchall()]
        
        if 'college_ar' in cols:
            self.cursor.execute(
                "INSERT INTO departments (name_ar, name_en, college_ar, college_en) VALUES (%s, %s, %s, %s)", 
                (name_ar, name_en, 'علوم الحاسوب وتكنولوجيا المعلومات', 'Computer Science and IT')
            )
        else:
            self.cursor.execute("INSERT INTO departments (name_ar, name_en) VALUES (%s, %s)", (name_ar, name_en))
            
        dept_id = self.cursor.lastrowid
        self.dept_map[name_ar] = dept_id
        return dept_id

    def run(self):
        system_logger.info("Starting database replacement migration (MySQL target)...")
        
        # Clear specific tables in case of re-run (order matters for FK constraints)
        for table in ['enrollments', 'academic_periods', 'courses', 'students', 'graduation_orders', 'departments']:
            try:
                self.cursor.execute(f"DELETE FROM {table}")
            except Exception as e:
                system_logger.warning(f"Could not clear {table}: {e}")
        
        parser = SQLParser(self.sql_dump_path)
        
        for table_name, rows in parser.parse():
            system_logger.info(f"Processing table: {table_name} ({len(rows)} rows)")
            
            if table_name == 'admin':
                self.migrate_users_to_personnel(rows)
            elif table_name == 'info_system':
                self.migrate_info_system(rows)
            elif table_name == 'order_university':
                self.migrate_orders(rows)
            elif table_name == 'signatures':
                self.migrate_signatures_to_personnel(rows)
            elif table_name in ('students_140', 'students_q'):
                # Handle ID conflicts by adding offsets for different systems
                # students_q is the main table (offset 0), students_140 is legacy (offset 2000)
                system_id = 2 if '140' in table_name else 1
                offset = 2000 if '140' in table_name else 0
                self.migrate_students(rows, system_id, id_offset=offset)
            elif table_name in ('subjects_students_140', 'subjects_students_q'):
                system_id = 2 if '140' in table_name else 1
                offset = 2000 if '140' in table_name else 0
                self.migrate_enrollments(rows, system_id, id_offset=offset)
                
        self.cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        self.conn.commit()
        self.cursor.close()
        self.conn.close()
        system_logger.info("Migration strictly complete.")

    def migrate_users_to_personnel(self, rows):
        """Maps legacy admin credentials into the unified personnel table."""
        for row in rows:
            if len(row) < 5: continue
            role = 'admin' if row[4] and 'مسؤول' in str(row[4]) else 'user'
            try:
                self.cursor.execute(
                    "INSERT INTO personnel (name_ar, username, password_hash, personnel_role) VALUES (%s, %s, %s, %s)",
                    (str(row[1] or 'User').strip(), str(row[2]).strip(), str(row[3]).strip(), role)
                )
            except Exception as e:
                system_logger.warning(f"Failed to import user {row[2]}: {e}")

    def migrate_signatures_to_personnel(self, rows):
        """Maps legacy signatory details into the unified personnel table."""
        for row in rows:
            if len(row) < 37: continue
            sigs = [
                (row[31], row[34], row[32], row[35], row[33], row[36], 1),
                (row[13], row[14], row[15], row[16], row[17], row[18], 2),
                (row[7], row[8], row[9], row[10], row[11], row[12], 3),
                (row[1], row[2], row[3], row[4], row[5], row[6], 4),
                (row[25], row[26], row[27], row[28], row[29], row[30], 5),
                (row[19], row[20], row[21], row[22], row[23], row[24], 6)
            ]
            for s in sigs:
                if not s[0]: continue
                try:
                    self.cursor.execute(
                        "INSERT INTO personnel (name_ar, name_en, academic_title_ar, academic_title_en, responsibility_ar, responsibility_en, display_order) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (s[0], s[1], s[2], s[3], s[4], s[5], s[6])
                    )
                except Exception as e:
                    system_logger.warning(f"Failed to import signature: {e}")

    def migrate_info_system(self, rows):
        if not rows: return
        row = rows[0]
        if len(row) < 5: return
        try:
            self.cursor.execute(
                "UPDATE settings SET univ_name_ar = %s, college_name_ar = %s, univ_name_en = %s, college_name_en = %s WHERE id = 1",
                (row[1], row[2], row[3], row[4])
            )
        except Exception as e:
            system_logger.warning(f"Failed to update info_system: {e}")

    def migrate_orders(self, rows):
        for row in rows:
            if len(row) < 9: continue
            dept_id = self.get_or_create_dept(row[1])
            study_type = 'evening' if row[2] and 'مسائي' in str(row[2]) else 'morning'
            
            # Extract graduation year robustly
            graduation_year = None
            if row[3]:
                if str(row[3]).isdigit():
                    graduation_year = int(row[3])
                else:
                    match = re.search(r'\d{4}', str(row[3]))
                    if match: graduation_year = int(match.group())

            # When importing legacy data, map year_study field directly into graduation_year if it evaluates to NULL
            if graduation_year is None:
                graduation_year = row[3]

            # Determine base study system: 2 = semester, 1 = annual
            year_val = 0
            if row[3]:
                match_yr = re.search(r'\d{4}', str(row[3]))
                if match_yr:
                    try:
                        year_val = int(match_yr.group())
                    except Exception:
                        pass
            base_system = 2 if year_val > 2020 else 1

            # study_system_id Mapping Constraints
            legacy_study = str(row[2] or '')
            if 'مسائية' in legacy_study:
                study_system_id = 3 if base_system == 1 else 4
            elif 'صباحية' in legacy_study:
                study_system_id = 1 if base_system == 1 else 2
            else:
                if 'مسائي' in legacy_study:
                    study_system_id = 3 if base_system == 1 else 4
                else:
                    study_system_id = base_system

            # Resolve Arabic semester string safely
            sem_val = str(row[4] or '') + ' ' + str(row[5] if len(row)>5 else '')
            sem = 'second' if 'ثاني' in sem_val else 'first'
            
            # Number of students
            num_st = int(row[8]) if row[8] and str(row[8]).isdigit() else None
            
            order_num = str(row[6] or '').strip()
            if not order_num: continue
            
            order_date = str(row[7] or '').strip()
            if len(order_date) != 10:
                order_date = '2000-01-01'
                
            try:
                self.cursor.execute(
                    "INSERT IGNORE INTO graduation_orders (order_number, order_date, department_id, study_type, graduation_year, graduation_semester, num_students, study_system_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (order_num, order_date, dept_id, study_type, graduation_year, sem, num_st, study_system_id)
                )
            except Exception as e:
                system_logger.warning(f"Failed to import order {order_num}: {e}")

    def migrate_students(self, rows, system_id, id_offset=0):
        for row in rows:
            if len(row) < 13: continue
            
            sid = int(row[0]) + id_offset
            full_name_ar = str(row[1] or '').strip()
            if not full_name_ar: continue # Prevent crash on NOT NULL constraint
            full_name_en = str(row[2] or '').strip()
            
            gender = 'F' if row[3] and 'انثى' in str(row[3]) else 'M'
            study_type = 'evening' if row[4] and 'مسائي' in str(row[4]) else 'morning'
            dept_id = self.get_or_create_dept(row[5])
            
            sem_val = str(row[7] or '')
            sem = 'second' if 'ثاني' in sem_val else 'first'
            
            sequence = int(row[9]) if row[9] and str(row[9]).isdigit() else None
            postgrad_no = int(row[10]) if row[10] and str(row[10]).isdigit() else None
            
            avg_str = row[8]
            avg = None
            if avg_str:
                try: avg = float(avg_str)
                except: pass

            order_number = str(row[11] or '').strip()
            
            # Safe Date Extraction
            grad_date = str(row[12] or '').strip()
            if len(grad_date) != 10: grad_date = None
            
            country_name = str(row[13] or '').strip().lower()
            country_id = self.country_map.get(country_name, 274)
            
            gov_name = str(row[14] or '').strip().lower()
            gov_id = self.gov_map.get(gov_name, 2)
            
            dob = str(row[15] or '').strip().replace('/', '-')
            if len(dob) != 10: dob = '2000-01-01'

            # Calculate Application Year Context
            admission_year = 2018
            app_year_str = str(row[16] or '') if len(row) > 16 else ''
            match = re.search(r'\d{4}', app_year_str)
            if match:
                admission_year = int(match.group())

            # Look up Order ID
            order_id = None
            if order_number:
                # 1. Strict Match
                self.cursor.execute(
                    "SELECT id FROM graduation_orders WHERE order_number = %s AND department_id = %s AND study_type = %s", 
                    (order_number, dept_id, study_type)
                )
                orow = self.cursor.fetchone()
                if orow: 
                    order_id = orow[0]
                else:
                    # 2. Flexible Match (Order Number only)
                    self.cursor.execute("SELECT id FROM graduation_orders WHERE order_number = %s", (order_number,))
                    orow = self.cursor.fetchone()
                    if orow: 
                        order_id = orow[0]
                    else:
                        # 3. Partial Match (Strip slashes/spaces)
                        clean_num = re.sub(r'[^0-9]', '', order_number)
                        if clean_num:
                            self.cursor.execute("SELECT id, order_number FROM graduation_orders")
                            all_orders = self.cursor.fetchall()
                            for oid, onum in all_orders:
                                if re.sub(r'[^0-9]', '', onum) == clean_num:
                                    order_id = oid
                                    break

            try:
                self.cursor.execute(
                    "INSERT IGNORE INTO students (id, full_name_ar, full_name_en, gender, sequence_number, "
                    "postgraduation_number, date_of_birth, birthplace_id, nationality_id, department_id, "
                    "study_system_id, order_id, admission_year, graduation_date, graduation_semester, average) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (sid, full_name_ar, full_name_en, gender, sequence, postgrad_no, dob, gov_id, country_id, dept_id, system_id, order_id, admission_year, grad_date, sem, avg)
                )
            except Exception as e:
                system_logger.warning(f"Failed to import student {sid} '{full_name_ar}': {e}")

    def migrate_enrollments(self, rows, system_id, id_offset=0):
        course_cache = {}
        period_cache = {}
        
        for row in rows:
            if len(row) >= 11:
                sid, code, n_ar, n_en, units, grade, year, sem_ar, attempt = row[1], row[2], row[3], row[4], row[6], row[7], row[8], row[9], row[10]
            else:
                sid, code, n_ar, n_en, grade, units, year, sem_ar = row[1], "", row[2], row[3], row[5], row[6], row[7], row[8]
                attempt = "First"

            sid = int(sid) + id_offset

            n_ar = str(n_ar or '').strip()
            if not n_ar: continue
            
            # 1. Quick Course Cache
            c_key = (n_ar, system_id)
            if c_key in course_cache:
                cid = course_cache[c_key]
            else:
                self.cursor.execute("SELECT id FROM courses WHERE name_ar = %s AND study_system_id = %s", (n_ar, system_id))
                crow = self.cursor.fetchone()
                if crow: 
                    cid = crow[0]
                else:
                    # Fallback: check if course exists with any study_system_id
                    self.cursor.execute("SELECT id FROM courses WHERE name_ar = %s", (n_ar,))
                    crow2 = self.cursor.fetchone()
                    if crow2:
                        cid = crow2[0]
                    else:
                        try:
                            self.cursor.execute(
                                "INSERT INTO courses (name_ar, name_en, credit_hours, department_id, stage_number, study_system_id) VALUES (%s, %s, %s, %s, %s, %s)",
                                (n_ar, str(n_en or ''), int(units) if str(units).isdigit() else 3, 1, 1, system_id)
                            )
                            cid = self.cursor.lastrowid
                        except Exception:
                            # Race condition or unique constraint — re-fetch
                            self.cursor.execute("SELECT id FROM courses WHERE name_ar = %s", (n_ar,))
                            crow3 = self.cursor.fetchone()
                            cid = crow3[0] if crow3 else None
                            if not cid:
                                continue
                course_cache[c_key] = cid
            
            # 2. Standardize Year
            year_str = str(year or '').strip()
            if len(year_str) == 4 and year_str.isdigit():
                year_str = f"{int(year_str)-1}-{year_str}"
            elif len(year_str) != 9:
                year_str = "2020-2021"
            
            # 3. Quick Period Cache
            p_key = (sid, year_str, system_id)
            if p_key in period_cache:
                pid = period_cache[p_key]
            else:
                self.cursor.execute(
                    "INSERT IGNORE INTO academic_periods (student_id, academic_year, study_system_id, stage_number) VALUES (%s, %s, %s, %s)",
                    (sid, year_str, system_id, 1)
                )
                self.cursor.execute("SELECT id FROM academic_periods WHERE student_id = %s AND academic_year = %s", (sid, year_str))
                p_fetch = self.cursor.fetchone()
                if p_fetch:
                    pid = p_fetch[0]
                    period_cache[p_key] = pid
                else:
                    continue

            # 4. Insert Enrollment
            try:
                score_val = float(grade) if grade and str(grade).replace('.','',1).isdigit() else 0.0
                passed_round = '2' if 'ثاني' in str(sem_ar or '') or 'ثانية' in str(attempt or '') else '1'
                self.cursor.execute(
                    "INSERT IGNORE INTO enrollments (period_id, course_id, score, passed_round) VALUES (%s, %s, %s, %s)",
                    (pid, cid, score_val, passed_round)
                )
            except Exception as e:
                pass


def trigger_migration(sql_dump_path: str, db_path: str = None):
    """Entry point intended to be triggered from the Settings UI button.
    
    The db_path parameter is kept for backward compatibility but is no longer
    used — the migration now targets the active MySQL database via db.get_connection().
    """
    try:
        manager = MigrationManager(sql_dump_path)
        manager.run()
        activity_logger.info(f"Database migrated successfully using {sql_dump_path}")
        return True
    except Exception as e:
        system_logger.error(f"Migration Failed: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    # Example local testing execution
    SQL_FILE = r"CSIT_SQL_DATABASE2.sql"
    trigger_migration(SQL_FILE)