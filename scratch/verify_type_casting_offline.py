import sqlite3
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

from sync_engine import _LOCAL_DB_PATH, set_online
from data.repositories import AcademicPeriodRepository, EnrollmentRepository

def safe_cast(val):
    if val is None: return None
    # If the value can be parsed as int/float, return it as int/float
    try:
        if "." in str(val):
            return float(val)
        return int(val)
    except ValueError:
        return str(val)

def offline_retype_and_verify():
    db_path = str(_LOCAL_DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Let's inspect academic_periods and enrollments
    tables_to_retype = ['academic_periods', 'enrollments']
    
    for table in tables_to_retype:
        print(f"\n--- Retyping table {table} ---")
        cursor.execute(f"SELECT * FROM {table}")
        rows = [dict(row) for row in cursor.fetchall()]
        if not rows:
            print(f"No rows in table {table}!")
            continue
            
        columns = list(rows[0].keys())
        
        # Recreate type-free table
        cursor.execute(f"DROP TABLE IF EXISTS {table}_new")
        cols_def = ", ".join([f"{col}" for col in columns])
        cursor.execute(f"CREATE TABLE {table}_new ({cols_def})")
        
        # Insert casted data
        placeholders = ", ".join(["?"] * len(columns))
        sql_insert = f"INSERT INTO {table}_new ({', '.join(columns)}) VALUES ({placeholders})"
        
        insert_data = [tuple(safe_cast(row[col]) for col in columns) for row in rows]
        cursor.executemany(sql_insert, insert_data)
        
        # Replace original table with the new typed table
        cursor.execute(f"DROP TABLE {table}")
        cursor.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
        print(f"Table {table} updated and type-cast successfully.")
        
    conn.commit()
    conn.close()
    
    print("\n--- Verifying offline repositories query with type-cast SQLite ---")
    set_online(False)
    
    # Verify AcademicPeriodRepository
    # Let's query student 4 again
    student_id = 4
    periods = AcademicPeriodRepository().get_by_student(student_id)
    print(f"Academic periods for student {student_id} offline: {len(periods)}")
    for p in periods:
        print(f"  Period ID: {p['id']} (Type: {type(p['id'])}), Student ID: {p['student_id']} (Type: {type(p['student_id'])}), Stage: {p['stage_number']}")
        
        # Verify EnrollmentRepository
        enrollments = EnrollmentRepository().get_by_period(p["id"])
        print(f"    Enrollments: {len(enrollments)}")
        for e in enrollments:
            print(f"      Course: {e['course_name_ar']}, Score: {e['score']} (Type: {type(e['score'])}), Period ID: {e['period_id']} (Type: {type(e['period_id'])})")

if __name__ == "__main__":
    offline_retype_and_verify()
