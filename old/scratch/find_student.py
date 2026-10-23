import sys
import os
sys.path.append(r"f:\CR_PY\certificate_manager")

from data.repositories import StudentRepository, AcademicPeriodRepository, EnrollmentRepository

student_repo = StudentRepository()
period_repo = AcademicPeriodRepository()
enroll_repo = EnrollmentRepository()

students = student_repo.get_all(limit=10)
for s in students:
    s_id = s.get("id")
    periods = period_repo.get_by_student(s_id)
    if periods:
        print(f"Student {s_id} has {len(periods)} periods.")
        for p in periods:
            enrs = enroll_repo.get_by_period(p["id"])
            if enrs:
                print(f"  Period {p['id']} has {len(enrs)} enrollments:")
                for e in enrs:
                    print("   ", e)
