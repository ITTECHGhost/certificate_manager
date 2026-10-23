import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import mysql.connector
from config import DBConfig

def check_tables():
    conn = mysql.connector.connect(
        host=DBConfig.DB_HOST,
        user=DBConfig.DB_USER,
        password=DBConfig.DB_PASSWORD,
        database=DBConfig.DB_NAME
    )
    cur = conn.cursor()
    
    for table in ["settings", "university_settings"]:
        print(f"--- Table: {table} ---")
        try:
            cur.execute(f"DESCRIBE {table}")
            for row in cur.fetchall():
                print(row)
            
            cur.execute(f"SELECT * FROM {table}")
            print("Rows:")
            for row in cur.fetchall():
                print(row)
        except Exception as e:
            print(f"Error describing {table}: {e}")
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_tables()
