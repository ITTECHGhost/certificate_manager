import sqlite3
import requests
import json
from pathlib import Path

# Paths
DB_PATH = Path(__file__).resolve().parent.parent / "local_cache.db"

def test_ping():
    print("--- Testing GET /ping ---")
    try:
        response = requests.get("http://127.0.0.1:2030/ping", timeout=2.0)
        print("Status Code:", response.status_code)
        print("Response JSON:", response.json())
        return response.status_code == 200
    except Exception as e:
        print("Error pinging FastAPI server:", e)
        return False

def test_batch_sync():
    print("--- Testing POST /sync Batch Insertion ---")
    
    # Define a batch containing a student and their academic period referencing the student's temp_id
    payload = {
        "actions": [
            {
                "id": 1,
                "table_name": "students",
                "operation": "INSERT",
                "temp_id": -101,
                "payload": {
                    "id": -101,
                    "full_name_ar": "طالب تجريبي من الاختبار",
                    "full_name_en": "Test Student from API Sync Test",
                    "gender": "M",
                    "sequence_number": 999,
                    "postgraduation_no": 888,
                    "date_of_birth": "2000-01-01",
                    "birthplace_id": 1,
                    "birthplace_other": "",
                    "nationality_id": 274,  # Iraq nationality
                    "department_id": 1,
                    "study_system_id": 1,
                    "degree_level": "Bachelor",
                    "order_id": None,
                    "admission_year": "2022",
                    "summer_training_data": None,
                    "average": 82.5,
                    "graduation_date": "2026-06-01",
                    "graduation_semester": "First"
                }
            },
            {
                "id": 2,
                "table_name": "academic_periods",
                "operation": "INSERT",
                "temp_id": -102,
                "payload": {
                    "id": -102,
                    "student_id": -101,  # References temp_id -101
                    "academic_year": "2022-2023",
                    "study_system_id": 1,
                    "stage_number": 1,
                    "semester_num": 1
                }
            }
        ]
    }
    
    try:
        response = requests.post("http://127.0.0.1:2030/sync", json=payload, timeout=5.0)
        print("Sync Status Code:", response.status_code)
        print("Sync Response JSON:", response.json())
        return response.status_code == 200
    except Exception as e:
        print("Error during sync request:", e)
        return False

def inspect_sync_queue():
    print("--- Inspecting SQLite sync_queue ---")
    if not DB_PATH.exists():
        print(f"No local database found at {DB_PATH}")
        return []
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM sync_queue").fetchall()
        print(f"Found {len(rows)} entries in sync_queue:")
        for r in rows:
            print(dict(r))
        return [dict(r) for r in rows]
    finally:
        conn.close()

if __name__ == "__main__":
    ping_ok = test_ping()
    if ping_ok:
        test_batch_sync()
    inspect_sync_queue()
