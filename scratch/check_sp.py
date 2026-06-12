import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import mysql.connector
from config import DBConfig

def show_proc_definition(proc_name):
    conn = mysql.connector.connect(
        host=DBConfig.DB_HOST,
        user=DBConfig.DB_USER,
        password=DBConfig.DB_PASSWORD,
        database=DBConfig.DB_NAME
    )
    cur = conn.cursor()
    cur.execute(f"SHOW CREATE PROCEDURE {proc_name}")
    res = cur.fetchone()
    if res:
        print(f"--- {proc_name} ---")
        print(res[2])
    cur.close()
    conn.close()

if __name__ == "__main__":
    show_proc_definition("InsertStudySystem")
    show_proc_definition("UpdateStudySystem")
