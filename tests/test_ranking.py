import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "certificate_manager_api"))

from ranking import compute_ranks  # noqa: E402


def g(i, dept, sem, sys_id, avg):
    return {"id": i, "department_id": dept, "semester": sem, "system_id": sys_id, "average": avg}


CLASS = [
    g(1, 1, "first", 1, 90), g(2, 1, "first", 1, 85), g(3, 1, "first", 1, 85), g(4, 1, "first", 1, 80),
    g(5, 1, "first", 2, 95),            # same dept, evening
    g(6, 1, "second", 1, 88),           # same dept, second semester
    g(7, 2, "first", 1, 99),            # other department
    g(8, 1, "first", 1, None),          # no average: never counted
]


def test_ties_share_a_sequence():
    r = compute_ranks(CLASS[3], CLASS)          # average 80, after 90, 85, 85
    assert r["dept_term_system"] == {"seq": 4, "of": 4}
    assert compute_ranks(CLASS[1], CLASS)["dept_term_system"]["seq"] == 2
    assert compute_ranks(CLASS[2], CLASS)["dept_term_system"]["seq"] == 2


def test_each_group():
    r = compute_ranks(CLASS[1], CLASS)          # average 85
    assert r["dept_term"] == {"seq": 3, "of": 5}        # 95, 90 above
    assert r["dept_system"] == {"seq": 3, "of": 5}      # 90, 88 above
    assert r["dept_year"] == {"seq": 4, "of": 6}        # 95, 90, 88 above
    assert r["college_term_system"] == {"seq": 3, "of": 5}   # 99, 90 above
    assert r["college_year"] == {"seq": 5, "of": 7}


def test_first_student_place_in_college():
    r = compute_ranks(CLASS[1], CLASS)
    assert r["first_student_college_seq"]["seq"] == 2   # dept top 95, only 99 above
    assert r["first_student_college_seq"]["of"] == 7


def test_student_without_average():
    r = compute_ranks(CLASS[7], CLASS)
    assert r["dept_year"]["seq"] is None


def test_rank_fields_for_templates():
    from services.certificate_context import rank_fields
    r = rank_fields({"dept_year": {"seq": 2, "of": 131}, "first_student_college_seq": {"seq": 1, "of": 301}})
    assert r["seq_dept_year_words"] == "الثاني"
    assert r["seq_dept_year_of_words"] == "مئة وواحد وثلاثون"
    assert r["first_student_college_seq_words"] == "الأول"
    assert r["seq_college_term"] == "" and r["seq_college_term_words"] == ""


def test_impossible_average_is_ignored():
    rows = CLASS + [g(99, 1, "first", 1, 770.298)]
    assert compute_ranks(CLASS[0], rows)["dept_term_system"]["seq"] == 1


def test_average_rule():
    from utils.display_format import average_is_valid
    assert average_is_valid(85.5) and average_is_valid(None) and average_is_valid(100)
    assert not average_is_valid(770.298) and not average_is_valid(-1)
