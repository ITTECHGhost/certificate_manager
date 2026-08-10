import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import mysql.connector
from config import DBConfig

def search_sp_content():
    conn = mysql.connector.connect(
        host=DBConfig.DB_HOST,
        user=DBConfig.DB_USER,
        password=DBConfig.DB_PASSWORD,
        database=DBConfig.DB_NAME
    )
    cur = conn.cursor()
    cur.execute("SHOW PROCEDURE STATUS WHERE Db = 'certificate_manager'")
    procedures = [row[1] for row in cur.fetchall()]
    
    for proc in procedures:
        cur.execute(f"SHOW CREATE PROCEDURE {proc}")
        res = cur.fetchone()
        if res:
            definition = res[2]
            if "academic_periods" in definition:
                print(f"Procedure '{proc}' references academic_periods:")
                # Print lines containing academic_periods
                for line in definition.split("\n"):
                    if "academic_periods" in line or "FROM ap" in line or "JOIN ap" in line:
                        print("  ", line.strip())
    cur.close()
    conn.close()

if __name__ == "__main__":
    search_sp_content()
