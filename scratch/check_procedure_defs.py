import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import mysql.connector
from config import DBConfig

procedures_to_check = [
    "GetThesisByStudent",
    "InsertThesis",
    "UpdateThesis",
    "DeleteThesis",
    "GetSupervisorsByStudent",
    "InsertStudentSupervisor",
    "UpdateStudentSupervisor",
    "DeleteStudentSupervisor"
]

try:
    conn = mysql.connector.connect(
        host=DBConfig.DB_HOST,
        user=DBConfig.DB_USER,
        password=DBConfig.DB_PASSWORD,
        database=DBConfig.DB_NAME
    )
    cur = conn.cursor()
    
    for proc in procedures_to_check:
        try:
            cur.execute(f"SHOW CREATE PROCEDURE {proc}")
            row = cur.fetchone()
            if row:
                print(f"=== {proc} ===")
                print(row[2])
                print("-" * 50)
            else:
                print(f"=== {proc} NOT FOUND ===")
        except Exception as e:
            print(f"Error checking {proc}: {e}")
            
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
