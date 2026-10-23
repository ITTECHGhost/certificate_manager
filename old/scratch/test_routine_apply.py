import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.abspath('.'))

from data.repositories import StudyRoutineRepository, StudentRepository, AcademicPeriodRepository, EnrollmentRepository

repo = StudyRoutineRepository()
routines = repo.get_all()
print(f"Total routines fetched: {len(routines)}")

for r in routines:
    r_id = r.get("id")
    name_ar = r.get("name_ar")
    courses = r.get("courses") or []
    print(f"\nRoutine ID: {r_id} | Name: {name_ar} | Total courses attached: {len(courses)}")
    for c in courses[:10]:
        print(f"   - Course: {c.get('name_ar')} | Stage: {c.get('stage_number')} | Sem: {c.get('semester_num')} | ID: {c.get('id')}")

if routines:
    for r in routines:
        r_id = r.get("id")
        print(f"\n=== Routine ID {r_id}: {r.get('name_ar')} ===")
        periods = repo.get_periods(r_id)
        print(f"Periods count: {len(periods)}")
        for p in periods:
            p_id = p.get("id")
            p_stg = p.get("stage_number")
            p_sem = p.get("semester_num")
            p_courses = repo.get_period_courses(p_id)
            print(f"  Period ID {p_id} (Stage {p_stg}, Sem {p_sem}): {len(p_courses)} courses")
            for pc in p_courses:
                print(f"     -> {pc.get('name_ar')} (ID: {pc.get('id') or pc.get('course_id')})")

