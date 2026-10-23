import sys
import os
sys.path.append(r"f:\CR_PY\certificate_manager")

from data.repositories import EnrollmentRepository, AcademicPeriodRepository
from sync_engine import is_online

print(f"Is online: {is_online()}")

enroll_repo = EnrollmentRepository()
period_repo = AcademicPeriodRepository()

# Find an enrollment to test with
periods = period_repo.get_by_student(1)
if periods:
    p_id = periods[0]["id"]
    print(f"Testing period_id={p_id}")
    enrs = enroll_repo.get_by_period(p_id)
    print(f"Initial enrollments for period {p_id}:")
    for e in enrs:
        print(e)
    
    if enrs:
        e_id = enrs[0]["id"]
        old_score = enrs[0].get("score")
        print(f"Testing update on enrollment {e_id}, old_score={old_score}")
        
        # Update score to 88.0 and passed_round to 2
        enroll_repo.update(e_id, 88.0, 2)
        print("Updated enrollment score to 88.0, round 2")
        
        # Check get_by_period again immediately
        enrs_after = enroll_repo.get_by_period(p_id)
        print(f"Enrollments after update:")
        for e in enrs_after:
            print(e)
            
        # Restore old score
        if old_score is not None:
            old_round = int(enrs[0].get("passed_round", 1))
            enroll_repo.update(e_id, float(old_score), old_round)
            print(f"Restored score to {old_score}, round {old_round}")
else:
    print("No periods found for student_id=1")
