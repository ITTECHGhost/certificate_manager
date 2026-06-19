import sys
import sqlite3
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from db import get_connection
from sync_engine import download_mysql_snapshot, init_local_db, set_online, _LOCAL_DB_PATH
from data.repositories import StudentRepository, AcademicPeriodRepository, EnrollmentRepository

def test_offline_student_data():
    print("1. Running fresh snapshot sync...")
    init_local_db()
    my_conn = get_connection()
    sqlite_conn = sqlite3.connect(str(_LOCAL_DB_PATH))
    try:
        download_mysql_snapshot(my_conn, sqlite_conn)
    finally:
        my_conn.close()
        sqlite_conn.close()
    
    print("\n2. Switching to Offline Mode...")
    set_online(False)
    
    print("\n3. Querying students offline...")
    students = StudentRepository().get_all_paginated(limit=5)
    print(f"Total students found offline: {len(students)}")
    if not students:
        print("No students found in replica cache!")
        return
        
    student = students[0]
    student_id = student["id"]
    print(f"First student offline details: ID: {student_id} (Type: {type(student_id)}), Name: {student['full_name_ar']}")
    
    print("\n4. Querying academic periods offline for student...")
    periods = AcademicPeriodRepository().get_by_student(student_id)
    print(f"Total periods found offline: {len(periods)}")
    for p in periods:
        print(f"  Period ID: {p['id']} (Type: {type(p['id'])}), Stage: {p['stage_number']}, Year: {p['academic_year']}")
        
        print("  Querying enrollments for this period...")
        enrollments = EnrollmentRepository().get_by_period(p["id"])
        print(f"    Total enrollments: {len(enrollments)}")
        for e in enrollments:
            print(f"      Course: {e['course_name_ar']}, Score: {e['score']}, Grade: {e['score']}")

if __name__ == "__main__":
    test_offline_student_data()
