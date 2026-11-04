from nicegui_ui.issue_helpers import (
    filter_templates_for_system, graduates_count, group_transcript, student_system,
    template_lines, template_option_label, GRADUATES_SOURCES,
)

FILES = ["semester - Temp - Ar.docx", "semester - Temp - En - D - SBS.docx",
         "year - Temp - Ar.docx", "year - Temp - En - D - SBS.docx"]


def test_template_lines(monkeypatch, tmp_path):
    import nicegui_ui.template_constants as tc
    monkeypatch.setattr(tc, "CONFIG_FILE", str(tmp_path / "none.json"))
    assert template_lines("year - Temp - Ar - D - SBS") == ("وثيقة تخرج — النظام الفصلي", "عربي • بالدرجات")
    assert template_lines("semester - Temp - En.docx") == ("وثيقة تخرج — نظام المقررات", "إنكليزي • بدون درجات")
    assert "\n" in template_option_label("year - Temp - Ar")
    assert "جدولان" not in template_option_label("year - Temp - Ar - D - SBS")


def test_filter_by_system(monkeypatch, tmp_path):
    import nicegui_ui.template_constants as tc
    monkeypatch.setattr(tc, "CONFIG_FILE", str(tmp_path / "none.json"))
    assert student_system({"period_display": "Semester"}) == "semester"
    assert student_system({"period_display": "year"}) == "annual"
    assert student_system({}) == ""
    assert filter_templates_for_system(FILES, {"period_display": "semester"}) == FILES[:2]
    assert filter_templates_for_system(FILES, {"calculation_rule": "annual"}) == FILES[2:]
    assert filter_templates_for_system(FILES, {}) == FILES


def test_graduates_three_sources():
    assert list(GRADUATES_SOURCES) == ["order", "student", "manual"]
    d = {"order_num_students": 120, "postgraduation_number": "95"}
    assert graduates_count("order", d) == "120"
    assert graduates_count("student", d) == "95"
    assert graduates_count("manual", d, " 7 ") == "7"
    assert graduates_count("order", {}) == ""


def test_group_transcript():
    courses = [
        {"period_stage": 1, "academic_year": "2020-2021", "subject_name": "a"},
        {"period_stage": 1, "academic_year": "2020-2021", "subject_name": "b"},
        {"period_stage": 2, "academic_year": "2021-2022", "subject_name": "c", "semester_num": 1},
    ]
    g = group_transcript(courses, is_semester=False)
    assert [x["header"] for x in g] == ["المرحلة 1 • 2020-2021", "المرحلة 2 • 2021-2022"]
    assert [len(x["courses"]) for x in g] == [2, 1]
    g = group_transcript(courses, is_semester=True)
    assert g[1]["header"] == "المرحلة 2 • 2021-2022 • الفصل 1"
    assert group_transcript([], False) == []
