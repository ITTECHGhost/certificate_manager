import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from sync_engine import set_online
from data.repositories import DepartmentRepository

set_online(False)
depts = DepartmentRepository().get_all()
print(f"Total departments retrieved offline: {len(depts)}")
if depts:
    print(f"First department details: {depts[0]}")
    # Check what keys are present
    keys = list(depts[0].keys())
    print(f"Keys present: {keys}")
    has_college_ar = "college_ar" in depts[0]
    has_college_name_ar = "college_name_ar" in depts[0]
    print(f"Has 'college_ar': {has_college_ar}")
    print(f"Has 'college_name_ar': {has_college_name_ar}")
