import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Reconfigure console output to support unicode characters like Arabic
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import sqlite3
import json
from sync_engine import (
    log_offline_insert,
    sync_offline_queue_to_mysql,
    get_queue_status,
)

DB_PATH = Path(__file__).resolve().parent.parent / "local_cache.db"

def clear_local_data():
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("DELETE FROM sync_queue")
        conn.execute("DELETE FROM local_students")
        conn.execute("DELETE FROM local_academic_periods")
        conn.commit()
    finally:
        conn.close()

def inspect_local_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        students = conn.execute("SELECT * FROM local_students").fetchall()
        periods = conn.execute("SELECT * FROM local_academic_periods").fetchall()
        print("Local Students in SQLite:")
        for s in students:
            print(dict(s))
        print("Local Academic Periods in SQLite:")
        for p in periods:
            print(dict(p))
    finally:
        conn.close()

def run_test():
    print("--- Clearing local data ---")
    clear_local_data()
    
    print("--- Logging offline student insert ---")
    student_payload = {
        "full_name_ar": "طالب أوفلاين تجريبي",
        "full_name_en": "Offline Test Student",
        "gender": "M",
        "sequence_number": 777,
        "postgraduation_no": 777,
        "date_of_birth": "2001-02-02",
        "birthplace_id": 2,
        "birthplace_other": "",
        "nationality_id": 274,
        "department_id": 1,
        "study_system_id": 1,
        "degree_level": "Bachelor",
        "order_id": None,
        "admission_year": "2023",
        "summer_training_data": None,
        "average": 78.4,
        "graduation_date": "2027-06-01",
        "graduation_semester": "First"
    }
    temp_student_id = log_offline_insert("students", student_payload)
    print(f"Logged student with temp_id: {temp_student_id}")

    print("--- Logging offline academic period insert ---")
    period_payload = {
        "student_id": temp_student_id,  # references the student's negative temp_id
        "academic_year": "2023-2024",
        "study_system_id": 1,
        "stage_number": 1,
        "semester_num": 1
    }
    temp_period_id = log_offline_insert("academic_periods", period_payload)
    print(f"Logged academic period with temp_id: {temp_period_id}")

    print("\n--- Local DB State Before Sync ---")
    inspect_local_db()
    status_before = get_queue_status()
    print("Queue count before sync:", status_before["pending"])

    print("\n--- Triggering Sync to FastAPI Server ---")
    summary = sync_offline_queue_to_mysql()
    print("Sync Summary:", summary)

    print("\n--- Local DB State After Sync ---")
    inspect_local_db()
    status_after = get_queue_status()
    print("Queue count after sync:", status_after["pending"])
    
    if status_after["pending"] == 0 and summary["synced"] == 2:
        print("\n🎉 SUCCESS: All local temporary IDs successfully mapped and resolved! offline sync is 100% working.")
    else:
        print("\n❌ FAILURE: Verification failed.")

if __name__ == "__main__":
    run_test()
