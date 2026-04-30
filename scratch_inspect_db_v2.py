import sqlite3

def inspect():
    conn = sqlite3.connect('certificate_manager.db')
    conn.row_factory = sqlite3.Row
    
    print("--- study_systems table ---")
    rows = conn.execute("SELECT * FROM study_systems").fetchall()
    for r in rows:
        print(dict(r))
        
    print("\n--- students table sample ---")
    rows = conn.execute("SELECT id, study_type, study_system_id FROM students LIMIT 5").fetchall()
    for r in rows:
        print(dict(r))
    
    conn.close()

if __name__ == "__main__":
    inspect()
