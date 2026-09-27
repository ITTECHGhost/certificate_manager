import os
import sys

sys.path.insert(0, os.path.abspath("."))
from cert_repository import _execute_mysql_stored_procedures
from data.query import get_offline_academic_courses
from nicegui_screens.certificate_screen import consolidate_courses_for_certificate

def get_online_courses(student_id):
    res = _execute_mysql_stored_procedures(student_id, "DEFAULT")
    if len(res) >= 6:
        return res[5]
    return []

def get_offline_courses(student_id):
    return get_offline_academic_courses(student_id, "DEFAULT")

def main():
    student_id = 2017
    print(f"Comparing for student {student_id}")

    online_raw = get_online_courses(student_id)
    offline_raw = get_offline_courses(student_id)
    
    online_cons = consolidate_courses_for_certificate(online_raw, is_annual=True)
    offline_cons = consolidate_courses_for_certificate(offline_raw, is_annual=True)

    def to_dict(lst):
        d = {}
        for c in lst:
            key = str(c.get("course_name_ar") or c.get("course_id"))
            d[key] = {
                "year": str(c.get("academic_year")),
                "stage": str(c.get("stage_number")),
                "sem": str(c.get("semester_num")),
                "gkey": str(c.get("grouping_key")),
                "mark": float(c.get("mark") or 0)
            }
        return d

    on_dict = to_dict(online_cons)
    off_dict = to_dict(offline_cons)

    diffs = 0
    all_keys = set(on_dict.keys()).union(set(off_dict.keys()))
    for k in sorted(all_keys):
        on_val = on_dict.get(k)
        off_val = off_dict.get(k)
        
        if on_val != off_val:
            diffs += 1
            print(f"DIFF in course '{k}':")
            print(f"  Online : {on_val}")
            print(f"  Offline: {off_val}")

    if diffs == 0:
        print("SUCCESS! Online and Offline groupings are identical!")
    else:
        print(f"Found {diffs} differences.")

if __name__ == '__main__':
    main()
