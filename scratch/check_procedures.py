import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import mysql.connector
from config import DBConfig

try:
    conn = mysql.connector.connect(
        host=DBConfig.DB_HOST,
        user=DBConfig.DB_USER,
        password=DBConfig.DB_PASSWORD,
        database=DBConfig.DB_NAME
    )
    cur = conn.cursor()
    
    print("--- Stored Procedures ---")
    cur.execute("SHOW PROCEDURE STATUS WHERE Db = 'certificate_manager'")
    for row in cur.fetchall():
        print(row[1])
        
    print("\n--- Tables ---")
    cur.execute("SHOW TABLES")
    for row in cur.fetchall():
        print(row[0])
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
