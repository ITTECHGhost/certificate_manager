import sys
import os

# Set console encoding to UTF-8 to prevent Arabic character encoding crashes on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Add the parent directory to the path so we can import from data and api
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from data.repositories import (
    DepartmentRepository,
    CourseRepository,
    StudySystemRepository,
    PersonnelRepository,
    GraduationOrderRepository,
    AcademicPeriodRepository,
    EnrollmentRepository,
    StudentRepository,
)
from sync_engine import set_online

def test_api_ping():
    print("Testing ping...")
    resp = requests.get("http://127.0.0.1:2030/ping")
    print(f"Ping response: {resp.status_code} - {resp.json()}")

def test_departments():
    print("\n--- Testing Departments Repository ---")
    repo = DepartmentRepository()
    
    # 1. Get all departments
    depts = repo.get_all()
    print(f"All departments (count={len(depts)}):")
    for d in depts[:2]:
        print(f"  - ID: {d.get('id')}, Name (AR): {d.get('name_ar')}")
        
    # 2. Insert department
    print("Inserting department...")
    new_id = repo.insert(name_ar="قسم التجربة", name_en="Test Dept")
    print(f"Inserted department ID: {new_id}")
    
    # 3. Get department by ID
    dept = repo.get_by_id(new_id)
    print(f"Retrieved department: {dept}")
    
    # 4. Update department
    print("Updating department...")
    repo.update(new_id, name_ar="قسم التجربة المعدل", name_en="Updated Test Dept")
    dept_updated = repo.get_by_id(new_id)
    print(f"Updated department: {dept_updated}")
    
    # 5. Delete department
    print("Deleting department...")
    repo.delete(new_id)
    dept_deleted = repo.get_by_id(new_id)
    print(f"Retrieved after deletion: {dept_deleted}")

def test_courses():
    print("\n--- Testing Courses Repository ---")
    repo = CourseRepository()
    
    # 1. Get all courses
    courses = repo.get_all()
    print(f"All courses (count={len(courses)}):")
    for c in courses[:2]:
        print(f"  - ID: {c.get('id')}, Name (AR): {c.get('name_ar')}")

def test_personnel():
    print("\n--- Testing Personnel Repository ---")
    repo = PersonnelRepository()
    
    # 1. Get active personnel
    personnel = repo.get_active()
    print(f"Active personnel (count={len(personnel)}):")
    for p in personnel[:2]:
        print(f"  - ID: {p.get('id')}, Name: {p.get('name_ar')}")

if __name__ == "__main__":
    # Force online mode to test API endpoints
    set_online(True)
    
    try:
        test_api_ping()
        test_departments()
        test_courses()
        test_personnel()
        print("\nAll integration checks passed successfully!")
    except Exception as e:
        print(f"\nTest failed with exception: {e}")
        import traceback
        traceback.print_exc()
