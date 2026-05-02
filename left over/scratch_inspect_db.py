import sqlite3

def inspect_db():
    conn = sqlite3.connect('certificate_manager.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("--- Study Systems ---")
    rows = cursor.execute("SELECT id, calculation_rule FROM study_systems").fetchall()
    for row in rows:
        print(f"ID: {row['id']}, Rule: {row['calculation_rule']}")
    
    print("\n--- Academic Periods Sample ---")
    rows = cursor.execute("SELECT student_id, academic_year, stage_number FROM academic_periods LIMIT 20").fetchall()
    for row in rows:
        print(f"SID: {row['student_id']}, Year: {row['academic_year']}, Stage: {row['stage_number']}")

    conn.close()

if __name__ == "__main__":
    inspect_db()
