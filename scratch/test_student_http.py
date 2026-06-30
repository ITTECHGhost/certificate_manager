import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Reconfigure console output encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import requests
import json

API_URL = "http://127.0.0.1:8000"

def test_endpoints():
    # 1. Test /ping
    print("--- Test /ping ---")
    r = requests.get(f"{API_URL}/ping")
    print(r.status_code, r.json())
    
    # 2. Test distinct years
    print("\n--- Test GET /students/distinct/years ---")
    r = requests.get(f"{API_URL}/students/distinct/years")
    print(r.status_code, r.json()[:5] if isinstance(r.json(), list) else r.json())
    
    # 3. Test count
    print("\n--- Test GET /students/count/all ---")
    r = requests.get(f"{API_URL}/students/count/all")
    print(r.status_code, r.json())
    
    # 4. Test paginated
    print("\n--- Test GET /students/paginated ---")
    r = requests.get(f"{API_URL}/students/paginated", params={"limit": 5})
    print(r.status_code)
    students = r.json()
    print(f"Fetched {len(students)} students.")
    if students:
        print("First student:", students[0]["full_name_ar"])
        first_id = students[0]["id"]
        
        # 5. Test detail
        print(f"\n--- Test GET /students/{{student_id}} for id={first_id} ---")
        r = requests.get(f"{API_URL}/students/{first_id}")
        print(r.status_code, r.json().get("full_name_ar"))
        
    # 6. Test search
    print("\n--- Test GET /students/search/all ---")
    r = requests.get(f"{API_URL}/students/search/all", params={"query": "طالب", "limit": 3})
    print(r.status_code, [s.get("full_name_ar") for s in r.json()])

    # 7. Test Student CRUD cycle (POST -> PUT -> DELETE)
    print("\n--- Test Student CRUD Cycle ---")
    student_payload = {
        "full_name_ar": "طالب اختبار كرود",
        "full_name_en": "CRUD Test Student",
        "gender": "M",
        "sequence_number": 1234,
        "postgraduation_no": 5678,
        "date_of_birth": "1999-12-31",
        "birthplace_id": 1,
        "birthplace_other": "",
        "nationality_id": 274,
        "department_id": 1,
        "study_system_id": 1,
        "degree_level": "Bachelor",
        "order_id": None,
        "admission_year": "2021",
        "summer_training_data": None,
        "average": 89.2,
        "graduation_date": "2025-06-01",
        "graduation_semester": "Second"
    }
    
    # POST
    r = requests.post(f"{API_URL}/students", json=student_payload)
    print("POST /students:", r.status_code, r.json())
    new_id = r.json().get("new_id")
    
    if new_id:
        # PUT
        student_payload["full_name_ar"] = "طالب اختبار كرود معدل"
        r = requests.put(f"{API_URL}/students/{new_id}", json=student_payload)
        print(f"PUT /students/{new_id}:", r.status_code, r.json())
        
        # Verify PUT change via detail
        r = requests.get(f"{API_URL}/students/{new_id}")
        print(f"Verified GET /students/{new_id}:", r.json().get("full_name_ar"))
        
        # DELETE
        r = requests.delete(f"{API_URL}/students/{new_id}")
        print(f"DELETE /students/{new_id}:", r.status_code, r.json())
        
        # Verify DELETE
        r = requests.get(f"{API_URL}/students/{new_id}")
        print(f"Verified deletion (should be 404):", r.status_code)

if __name__ == "__main__":
    test_endpoints()
