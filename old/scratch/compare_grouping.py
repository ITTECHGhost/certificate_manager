import os
import sys
import json

sys.path.insert(0, os.path.abspath("."))
from cert_repository import _execute_mysql_stored_procedures
from data.query import get_offline_academic_courses
from nicegui_screens.certificate_screen import consolidate_courses_for_certificate

def get_online_courses(student_id):
    # Online mode runs sp_GetFullCertificateData which returns multiple result sets.
    # We want the courses_grouped which is the 6th result set.
    res = _execute_mysql_stored_procedures(student_id, "DEFAULT")
    if len(res) >= 6:
        return res[5]
    return []

def get_offline_courses(student_id):
    # Offline mode fetches from Q_COURSES_YEARLY_BY_ACADEMIC_YEAR
    return get_offline_academic_courses(student_id, "DEFAULT")

def main():
    student_id = 2137
    print(f"Comparing for student {student_id}")

    online_raw = get_online_courses(student_id)
    offline_raw = get_offline_courses(student_id)
    
    print(f"Raw Online rows: {len(online_raw)}")
    print(f"Raw Offline rows: {len(offline_raw)}")

    # Consolidate them using certificate_screen.py logic
    # Assume is_annual = True for this student
    online_cons = consolidate_courses_for_certificate(online_raw, is_annual=True)
    offline_cons = consolidate_courses_for_certificate(offline_raw, is_annual=True)

    print(f"Consolidated Online rows: {len(online_cons)}")
    print(f"Consolidated Offline rows: {len(offline_cons)}")

    # Sort them consistently for comparison
    def sort_key(c):
        return (str(c.get("academic_year") or ""), str(c.get("course_name_ar") or ""))

    online_cons.sort(key=sort_key)
    offline_cons.sort(key=sort_key)

    print("\n--- Online ---")
    for c in online_cons:
        print(f"Year: {c.get('academic_year')}, Stage: {c.get('stage_number')}, Sem: {c.get('semester_num')}, Key: {c.get('grouping_key')}, Mark: {c.get('mark')}, Name: {c.get('course_name_ar')}")

    print("\n--- Offline ---")
    for c in offline_cons:
        print(f"Year: {c.get('academic_year')}, Stage: {c.get('stage_number')}, Sem: {c.get('semester_num')}, Key: {c.get('grouping_key')}, Mark: {c.get('mark')}, Name: {c.get('course_name_ar')}")

if __name__ == '__main__':
    main()
