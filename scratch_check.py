# pyrefly: ignore [missing-import]
import sys
sys.stdout.reconfigure(encoding='utf-8')
import mysql.connector
from config import DBConfig

def main():
    conn = mysql.connector.connect(
        host=DBConfig.DB_HOST, user=DBConfig.DB_USER,
        password=DBConfig.DB_PASSWORD, database=DBConfig.DB_NAME
    )
    cursor = conn.cursor(dictionary=True)
    
    # Row counts
    for t in ['students', 'academic_periods', 'enrollments', 'courses']:
        cursor.execute(f"SELECT COUNT(*) as cnt FROM {t}")
        print(f"{t}: {cursor.fetchone()['cnt']} rows")
    
    # Find a student with periods
    cursor.execute("SELECT DISTINCT student_id FROM academic_periods LIMIT 1")
    sid = cursor.fetchone()['student_id']
    
    # Get period
    cursor.execute("SELECT id FROM academic_periods WHERE student_id = %s LIMIT 1", (sid,))
    pid = cursor.fetchone()['id']
    
    # Get enrollments using exact repository query
    cursor.execute(
        "SELECT e.id, e.score, "
        "CASE WHEN e.passed_round != '1' THEN 1 ELSE 0 END AS is_second_round, "
        "c.name_en "
        "FROM enrollments e JOIN courses c ON e.course_id = c.id "
        "WHERE e.period_id = %s ORDER BY c.name_ar", (pid,)
    )
    rows = cursor.fetchall()
    print(f"\nStudent {sid}, Period {pid}: {len(rows)} enrollments")
    for r in rows[:5]:
        print(f"  {r['name_en']}: score={r['score']}, is_second_round={r['is_second_round']}")
    
    print("\n=== ALL QUERIES WORKING ===")
    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()
