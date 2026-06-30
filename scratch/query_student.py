import sys
sys.stdout.reconfigure(encoding='utf-8')
from data.repositories import StudentRepository
import mysql.connector
from config import DBConfig

def main():
    conn = mysql.connector.connect(
        host=DBConfig.DB_HOST, user=DBConfig.DB_USER,
        password=DBConfig.DB_PASSWORD, database=DBConfig.DB_NAME
    )
    cursor = conn.cursor(dictionary=True)
    
    # 1. Print columns returned by GetStudentDossierByID
    cursor.execute("SELECT student_id FROM academic_periods LIMIT 1")
    row = cursor.fetchone()
    if row:
        sid = row['student_id']
        repo = StudentRepository()
        student = repo.get_by_id(sid)
        print("Student fields:")
        for k, v in student.items():
            print(f"  {k}: {type(v)} = {v}")
            
    # 2. Print columns from graduation_orders table
    cursor.execute("DESCRIBE graduation_orders")
    print("\ngraduation_orders columns:")
    for col in cursor.fetchall():
        print(f"  {col['Field']}: {col['Type']}")
        
    # 3. Print columns from students table
    cursor.execute("DESCRIBE students")
    print("\nstudents columns:")
    for col in cursor.fetchall():
        print(f"  {col['Field']}: {col['Type']}")
        
    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()
