import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from db import get_connection

def find_student_with_periods():
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT DISTINCT student_id FROM academic_periods LIMIT 5")
        for row in cur.fetchall():
            print("Student with period:", row['student_id'])
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    find_student_with_periods()
