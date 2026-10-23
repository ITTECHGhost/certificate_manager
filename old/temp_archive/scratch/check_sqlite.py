import sqlite3

try:
    conn = sqlite3.connect("certificate_manager.db")
    cursor = conn.cursor()
    
    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print("Tables in SQLite:")
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
        count = cursor.fetchone()[0]
        print(f"- {t}: {count} rows")
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
