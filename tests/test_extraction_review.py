"""Extraction review: pure logic behind the «مراجعة الاستخراج» dialog."""
from services.extraction_review import (
    flag_rows, set_score, set_meta, order_number_problem, REASON_AVG, REASON_SCORE,
    REASON_MISSING, REASON_DUP, REASON_NAME,
)

COURSES = [
    {"id": 1, "name_ar": "أ", "credit_hours": 2},
    {"id": 2, "name_ar": "ب", "credit_hours": 4},
]


def _row(nid="1", name="علي حسن", scores=((1, 80.0), (2, 70.0)), avg=73.333):
    return {
        "national_id": nid, "student_name": name, "passed_round": 1,
        "result_status": "PASSED", "average": avg,
        "scores": [{"course_id": c, "score": s, "credit_hours": 2 if c == 1 else 4,
                    "course_name_ar": "x", "passed_round": 1, "stage_number": 1}
                   for c, s in scores],
        "scores_count": len(scores),
    }


def test_clean_row_has_no_flags():
    assert flag_rows([_row()], COURSES) == [[]]


def test_average_outside_50_100_flagged():
    r = _row(scores=((1, 30.0), (2, 40.0)), avg=36.667)
    assert REASON_AVG in flag_rows([r], COURSES)[0]


def test_score_out_of_range_flagged():
    r = _row(scores=((1, 120.0), (2, 70.0)))
    assert REASON_SCORE in flag_rows([r], COURSES)[0]


def test_missing_courses_flagged():
    r = _row(scores=((1, 80.0),), avg=80.0)
    assert REASON_MISSING in flag_rows([r], COURSES)[0]


def test_duplicate_national_id_flagged_on_both():
    flags = flag_rows([_row(nid="7"), _row(nid="7", name="سعد")], COURSES)
    assert REASON_DUP in flags[0] and REASON_DUP in flags[1]


def test_generated_ids_are_not_duplicates():
    flags = flag_rows([_row(nid="GEN_1"), _row(nid="GEN_1")], COURSES)
    assert REASON_DUP not in flags[0]


def test_name_not_in_known_students_flagged():
    flags = flag_rows([_row()], COURSES, known_names=["سعد كريم"])
    assert REASON_NAME in flags[0]
    assert REASON_NAME not in flag_rows([_row()], COURSES, known_names=["علي  حسن"])[0]


def test_no_known_names_means_no_name_check():
    assert REASON_NAME not in flag_rows([_row()], COURSES)[0]


def test_set_score_recomputes_weighted_average_and_does_not_mutate():
    r = _row()
    new = set_score(r, 1, 90.0, COURSES)
    assert new["average"] == round((90 * 2 + 70 * 4) / 6, 3)
    assert r["scores"][0]["score"] == 80.0


def test_set_score_adds_missing_course_and_removes_on_blank():
    r = _row(scores=((1, 80.0),), avg=80.0)
    new = set_score(r, 2, 60.0, COURSES)
    assert new["scores_count"] == 2 and new["average"] == round((80 * 2 + 60 * 4) / 6, 3)
    gone = set_score(new, 1, None, COURSES)
    assert gone["scores_count"] == 1 and gone["average"] == 60.0


def test_set_score_keeps_out_of_range_value_so_it_stays_flagged():
    new = set_score(_row(), 1, 150.0, COURSES)
    assert REASON_SCORE in flag_rows([new], COURSES)[0]


def test_set_meta_changes_name_round_status():
    new = set_meta(_row(), student_name=" سعد   كريم ", passed_round=2, result_status="DEFERRED")
    assert new["student_name"] == "سعد كريم" and new["student_name_norm"] == "سعد كريم"
    assert new["passed_round"] == 2 and new["result_status"] == "DEFERRED"
    assert all(s["passed_round"] == 2 for s in new["scores"])


def test_order_number_problem():
    assert order_number_problem("") is None
    assert order_number_problem("20707/12/3") is None
    assert order_number_problem("3/12/20707") is None   # normalised, not a problem
    assert order_number_problem("12/3") is not None
