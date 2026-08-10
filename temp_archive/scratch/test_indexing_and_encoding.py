import sqlite3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from sync_engine import download_mysql_snapshot

class MockCursor:
    def __init__(self, table_data):
        self.table_data = table_data
        self.current_table = None
        
    def execute(self, sql):
        # Infer the table name from SELECT * FROM <table>;
        import re
        m = re.search(r"SELECT \* FROM (\w+);", sql)
        if m:
            self.current_table = m.group(1)
        else:
            self.current_table = None
            
    def fetchall(self):
        if self.current_table and self.current_table in self.table_data:
            return self.table_data[self.current_table]
        return []

class MockConnection:
    def __init__(self, table_data):
        self.table_data = table_data
        
    def cursor(self, dictionary=True):
        return MockCursor(self.table_data)

def test_indexing_and_encoding():
    print("=== Testing indexing and byte decoding ===")
    
    # Mock data including bytearray and numeric FKs
    mock_data = {
        "departments": [
            {"id": 1, "name_ar": bytearray("علوم الحاسوب", "utf-8"), "name_en": "Computer Science", "university_settings_id": 1}
        ],
        "students": [
            {"id": 10, "full_name_ar": bytearray("أحمد", "utf-8"), "department_id": 1, "nationality_id": 274}
        ]
    }
    
    # Connect to local SQLite test cache
    db_path = "local_test_cache.db"
    if Path(db_path).exists():
        Path(db_path).unlink()
        
    sqlite_conn = sqlite3.connect(db_path)
    my_conn = MockConnection(mock_data)
    
    try:
        # Replicate using mock connection
        download_mysql_snapshot(my_conn, sqlite_conn)
        print("MOCK replication complete.")
        
        # Verify columns & type in departments
        cursor = sqlite_conn.cursor()
        cursor.execute("PRAGMA table_info(departments)")
        dept_cols = cursor.fetchall()
        print(f"Departments Table Schema:")
        for col in dept_cols:
            print(f"  Col: {col[1]}, Type-Affinity: {col[2]}, PK: {col[5]}")
            if col[1] == "id":
                assert col[5] == 1, "id column is not a PRIMARY KEY!"
                assert "INTEGER" in col[2], "id column type affinity is not INTEGER!"
                
        # Verify index in students
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index'")
        indexes = cursor.fetchall()
        print(f"Created Indexes:")
        idx_names = []
        for idx in indexes:
            print(f"  Index: {idx[0]}, SQL: {idx[1]}")
            idx_names.append(idx[0])
            
        assert "idx_students_department_id" in idx_names, "Missing index on department_id!"
        assert "idx_students_nationality_id" in idx_names, "Missing index on nationality_id!"
        
        # Verify byte decoding
        cursor.execute("SELECT name_ar FROM departments WHERE id = 1")
        name_ar = cursor.fetchone()[0]
        print(f"Decoded Arabic name_ar: {name_ar}")
        assert name_ar == "علوم الحاسوب", "Bytearray decoding failed!"
        
        print("\nPASS: SQLite PK injection, foreign key indexing, and UTF-8 bytearray decoding verified.")
        
    finally:
        sqlite_conn.close()
        if Path(db_path).exists():
            Path(db_path).unlink()

if __name__ == "__main__":
    test_indexing_and_encoding()
