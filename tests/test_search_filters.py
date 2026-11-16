"""Search filters on the Students page and the Graduation Orders page."""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "certificate_manager_api"))


def test_api_and_program_filter_rules_match():
    from data.query import student_filter_where as local
    from routers.students import student_filter_where as api
    cases = [
        {},
        {"query": "علي", "dept_id": 3, "study_system_id": 2, "study_type": "evening",
         "status": "graduated", "admission_year": "2021/2022"},
        {"query": "x", "status": "not_graduated", "study_type": "bad", "admission_year": "abc"},
    ]
    for c in cases:
        assert local(**c) == api(**c, ph="?"), c


def test_filter_where_whitelists_values():
    from data.query import student_filter_where
    assert student_filter_where(query="a", study_type="x; DROP", status="any", admission_year="12a") == ("", [])
    where, params = student_filter_where(dept_id=3, study_type="parallel", status="not_graduated")
    assert where.count("?") == len(params) == 2
    assert "order_id, 0) = 0" in where


def test_filters_run_on_sqlite():
    """The local copy runs the same WHERE (SQLite has SUBSTR and COALESCE)."""
    from data.query import student_filter_where
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE students (id, full_name_ar, full_name_en, national_id, department_id, "
               "study_system_id, study_type, order_id, admission_year)")
    db.executemany("INSERT INTO students VALUES (?,?,?,?,?,?,?,?,?)", [
        (1, "علي حسن", "", "", 3, 1, "morning", 7, "2021/2022"),
        (2, "علي كاظم", "", "", 3, 1, "evening", None, "2021"),
        (3, "سارة", "", "", 4, 2, None, 0, "2020"),
    ])

    def ids(**f):
        where, params = student_filter_where(**f)
        return [r[0] for r in db.execute(f"SELECT id FROM students s {where} ORDER BY id", params)]

    assert ids() == [1, 2, 3]
    assert ids(query="علي") == [1, 2]
    assert ids(study_type="evening") == [2]
    assert ids(study_type="morning") == [1, 3]          # empty type counts as morning
    assert ids(status="graduated") == [1]
    assert ids(status="not_graduated") == [2, 3]
    assert ids(admission_year="2021") == [1, 2]
    assert ids(dept_id=3, study_type="evening") == [2]


def test_students_screen_drops_empty_filters_and_keeps_dept_scope():
    from nicegui_screens.students_screen import active_filters
    assert active_filters({"dept_id": None, "study_type": "", "status": "graduated"}) == {"status": "graduated"}
    assert active_filters({"dept_id": 9}, user_dept_id=3) == {"dept_id": 3}


ORDERS = [
    {"id": 1, "order_number": "100", "department_id": 3, "study_type": "morning",
     "graduation_year": 2024, "graduation_semester": "first", "dept_name_ar": "الحاسبات"},
    {"id": 2, "order_number": "200", "department_id": 3, "study_type": "Evening",
     "graduation_year": 2025, "graduation_semester": "second", "dept_name_ar": "الحاسبات"},
    {"id": 3, "order_number": "300", "department_id": 4, "study_type": None,
     "graduation_year": 2025, "graduation_semester": "first", "dept_name_ar": "المدني"},
]


def test_filter_orders():
    from nicegui_screens.graduation_orders_screen import filter_orders

    def ids(search="", **f):
        return [r["id"] for r in filter_orders(ORDERS, search, f)]

    assert ids() == [1, 2, 3]
    assert ids("200") == [2]
    assert ids(department_id=3) == [1, 2]
    assert ids(study_type="evening") == [2]
    assert ids(study_type="morning") == [1, 3]
    assert ids(graduation_year=2025) == [2, 3]
    assert ids(graduation_semester="first", graduation_year="2025") == [3]
    assert ids(department_id=None, study_type="") == [1, 2, 3]
