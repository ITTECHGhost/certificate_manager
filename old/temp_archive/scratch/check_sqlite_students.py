import sqlite3
import sys

def check_sqlite():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    conn = sqlite3.connect("local_cache.db")
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]
    print("SQLite tables:", tables)
    
    if "students" in tables:
        # Check columns
        cursor.execute("PRAGMA table_info(students)")
        cols = cursor.fetchall()
        print("\nColumns in SQLite students table:")
        for c in cols:
            print(c)
            
        # Check first 5 rows
        cursor.execute("SELECT id, full_name_ar, admission_year, graduation_year, department_id, average FROM students LIMIT 5")
        rows = cursor.fetchall()
        print("\nFirst 5 students in SQLite replica:")
        for r in rows:
            print(r)
            
    conn.close()

if __name__ == "__main__":
    check_sqlite()
