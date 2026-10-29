from services.certificate_context import build_certificate_context


def _course(name, year, stage, sem):
    return {"grouping_key": f"{year}-{stage}-{sem}", "academic_year": year, "stage_number": stage,
            "period_stage": stage, "semester_num": sem, "course_name_ar": name, "course_name_en": name,
            "mark": 70, "unit": 3, "passed_round": 1, "course_id": hash(name) % 1000}


DATA = {"courses_grouped": [
    _course("A1", "2017-2018", 3, 1), _course("A2", "2017-2018", 3, 2),
    _course("B1", "2018-2019", 4, 1),                                   # semester 2 missing
    _course("C1", "2019-2020", 4, 1), _course("C2", "2019-2020", 4, 2),
], "grouping_mode": "SEMESTER"}


def _rows(is_english):
    ctx = build_certificate_context(dict(DATA), {"grouping_mode": "SEMESTER", "is_english": is_english})
    return ctx["paired_semesters"]


def test_semester_one_always_in_first_column_arabic():
    rows = _rows(False)
    assert len(rows) == 3
    firsts = [r["rows"][0]["right_name"] for r in rows]
    seconds = [r["rows"][0]["left_name"] for r in rows]
    assert [n[:2] for n in firsts] == ["A1", "B1", "C1"]
    assert [n[:2] for n in seconds] == ["A2", "", "C2"]
    assert rows[1]["semester_right_label"] == "الفصل الأول"


def test_semester_one_always_in_first_column_english():
    rows = _rows(True)
    assert [r["rows"][0]["left_name"][:2] for r in rows] == ["A1", "B1", "C1"]
    assert rows[0]["semester_left_label"] == "First Semester"
