"""normalize_order_numbers.plan: a reversed number whose fixed form already exists (same
department, system, semester) is listed as a duplicate, not changed (the run used to fail)."""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "certificate_manager_api"))
sys.modules.setdefault("mysql", types.ModuleType("mysql"))
sys.modules.setdefault("mysql.connector", types.ModuleType("mysql.connector"))

import normalize_order_numbers as n  # noqa: E402


def _r(i, num, dept=1, sem="first"):
    return {"id": i, "order_number": num, "department_id": dept, "study_system_id": 1, "graduation_semester": sem}


def test_duplicate_listed_not_fixed():
    fix, review, clash = n.plan([_r(113, "3/13/17862"), _r(138, "3/13/15710"), _r(140, "15710/13/3")])
    assert fix == [(113, "3/13/17862", "17862/13/3")]
    assert clash == [(138, "3/13/15710", "15710/13/3", 140)] and review == []


def test_same_number_other_department_is_fine():
    fix, _r2, clash = n.plan([_r(1, "3/13/15710", dept=2), _r(2, "15710/13/3", dept=1)])
    assert [f[0] for f in fix] == [1] and clash == []
