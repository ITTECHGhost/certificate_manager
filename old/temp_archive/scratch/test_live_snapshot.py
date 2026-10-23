import sys
import sqlite3
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from db import get_connection
from sync_engine import download_mysql_snapshot, init_local_db, _LOCAL_DB_PATH

def test_live_snapshot():
    print("Initializing local SQLite cache...")
    init_local_db()
    
    print("Connecting to MySQL...")
    my_conn = get_connection()
    
    # Open SQLite connection
    sqlite_conn = sqlite3.connect(str(_LOCAL_DB_PATH))
    sqlite_conn.row_factory = sqlite3.Row
    
    try:
        print("Running download_mysql_snapshot...")
        download_mysql_snapshot(my_conn, sqlite_conn)
        print("Snapshot complete!")
        
        # Verify columns of local departments table
        cursor = sqlite_conn.cursor()
        cursor.execute("PRAGMA table_info(departments)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Columns in SQLite 'departments' table: {columns}")
        
        # Verify rows in local departments
        cursor.execute("SELECT * FROM departments LIMIT 2")
        rows = [dict(row) for row in cursor.fetchall()]
        print(f"Departments in SQLite: {rows}")
        
    finally:
        my_conn.close()
        sqlite_conn.close()

if __name__ == "__main__":
    test_live_snapshot()
