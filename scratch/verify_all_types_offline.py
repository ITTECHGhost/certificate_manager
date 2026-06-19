import sqlite3
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))

from sync_engine import _LOCAL_DB_PATH, set_online
from data.repositories import AcademicPeriodRepository, EnrollmentRepository

def safe_cast(val):
    if val is None: return None
    try:
        if "." in str(val):
            return float(val)
        return int(val)
    except ValueError:
        return str(val)

def offline_retype_all():
    db_path = str(_LOCAL_DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all table names in local_cache.db
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall() if not r[0].startswith("sqlite_")]
    
    for table in tables:
        # Don't retype sync queue, temp_id_counter, read_cache, local_* tables
        if table in ('sync_queue', 'temp_id_counter', 'read_cache') or table.startswith("local_"):
            continue
            
        print(f"Retyping table {table}...")
        cursor.execute(f"SELECT * FROM {table}")
        rows = [dict(row) for row in cursor.fetchall()]
        if not rows:
            continue
            
        columns = list(rows[0].keys())
        
        cursor.execute(f"DROP TABLE IF EXISTS {table}_new")
        cols_def = ", ".join([f"{col}" for col in columns])
        cursor.execute(f"CREATE TABLE {table}_new ({cols_def})")
        
        placeholders = ", ".join(["?"] * len(columns))
        sql_insert = f"INSERT INTO {table}_new ({', '.join(columns)}) VALUES ({placeholders})"
        
        insert_data = [tuple(safe_cast(row[col]) for col in columns) for row in rows]
        cursor.executemany(sql_insert, insert_data)
        
        cursor.execute(f"DROP TABLE {table}")
        cursor.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
        
    conn.commit()
    conn.close()
    
    print("\n--- Verifying offline repositories query with all tables type-cast ---")
    set_online(False)
    
    # Verify AcademicPeriodRepository
    student_id = 4
    periods = AcademicPeriodRepository().get_by_student(student_id)
    print(f"Academic periods for student {student_id} offline: {len(periods)}")
    for p in periods:
        print(f"  Period ID: {p['id']} (Type: {type(p['id'])}), Stage: {p['stage_number']}")
        
        # Verify EnrollmentRepository
        enrollments = EnrollmentRepository().get_by_period(p["id"])
        print(f"    Enrollments: {len(enrollments)}")
        for e in enrollments:
            print(f"      Course ID: {e['course_id']} (Type: {type(e['course_id'])}), Course Name: {e['course_name_en']}, Score: {e['score']}")

if __name__ == "__main__":
    offline_retype_all()
