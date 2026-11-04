import json

import pytest

import nicegui_ui.template_constants as tc
from nicegui_ui.issue_helpers import filter_templates_for_system, template_lines


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """A private templates_config.json, so the real one is never read or written."""
    monkeypatch.setattr(tc, "TEMPLATES_DIR", str(tmp_path))
    monkeypatch.setattr(tc, "CONFIG_FILE", str(tmp_path / "templates_config.json"))
    return tmp_path / "templates_config.json"


def test_save_round_trip(cfg):
    assert tc.save_template_tags("year - Temp - Ar.docx", "تأييد عربي فصلي", "Ar", "Annual", False)
    t = tc.template_tags("year - Temp - Ar.docx")
    assert (t["lang"], t["system"], t["sbs"]) == ("Ar", "Annual", False)
    assert tc.get_template_info("year - Temp - Ar")["display_name"] == "تأييد عربي فصلي"

    # Editing changes name and tags; the file name stays
    assert tc.save_template_tags("year - Temp - Ar.docx", "وثيقة بولونيا", "En", "Bologna", True)
    saved = json.loads(cfg.read_text(encoding="utf-8"))["year - Temp - Ar"]
    assert saved["file"] == "year - Temp - Ar.docx"
    assert (saved["lang"], saved["system"], saved["sbs"], saved["system_ar"]) == ("En", "Bologna", True, "مسار بولونيا")


def test_save_refuses_empty_name_and_normalises_tags(cfg):
    assert not tc.save_template_tags("x.docx", "  ", "Ar", "Annual", False)
    assert tc.save_template_tags("x.docx", "س", "zz", "nope", 0)
    t = tc.template_tags("x.docx")
    assert (t["lang"], t["system"], t["sbs"]) == ("Ar", "Annual", False)


def test_conflicts():
    tags = {"lang": "Ar", "system": "Annual", "sbs": False}
    assert tc.template_tag_conflicts("تأييد عربي فصلي", tags) == []
    msgs = tc.template_tag_conflicts("وثيقة انجليزي بالدرجات مقررات", tags)
    assert len(msgs) == 3


def test_issue_label_uses_user_name(cfg):
    tc.save_template_tags("year - Temp - En.docx", "تأييد انجليزي فصلي", "En", "Annual", False)
    assert template_lines("year - Temp - En.docx") == ("تأييد انجليزي فصلي", "إنكليزي • بدون درجات")


def test_filter_follows_system_tag_not_file_name(cfg):
    # File name says "year" but the user tagged it semester
    tc.save_template_tags("year - Temp - Ar.docx", "تأييد", "Ar", "Semester", False)
    tc.save_template_tags("semester - Temp - Ar.docx", "تأييد", "Ar", "Annual", False)
    files = ["year - Temp - Ar.docx", "semester - Temp - Ar.docx"]
    assert filter_templates_for_system(files, {"period_display": "semester"}) == ["year - Temp - Ar.docx"]
    assert filter_templates_for_system(files, {"period_display": "year"}) == ["semester - Temp - Ar.docx"]


SYSTEMS = [
    {"id": 1, "name_ar": "النظام الفصلي", "calculation_rule": "annual", "study_day_type": "Morning"},
    {"id": 3, "name_ar": "النظام الفصلي", "calculation_rule": "annual", "study_day_type": "Evening"},
    {"id": 2, "name_ar": "نظام المقررات", "calculation_rule": "semester", "study_day_type": "Morning"},
]


def test_system_options_come_from_study_systems():
    assert tc.system_tag_options(SYSTEMS) == {"النظام الفصلي": "Annual", "نظام المقررات": "Semester"}
    # a name no longer in the list is kept for the template that has it
    assert "ماجستير" in tc.system_tag_options(SYSTEMS, current="ماجستير")


def test_named_system_tag_saved_and_used_for_filter(cfg):
    tc.save_template_tags("year - Temp - Ar.docx", "تأييد", "Ar", "Annual", False, system_name="النظام الفصلي")
    tc.save_template_tags("semester - Temp - Ar.docx", "تأييد", "Ar", "Semester", False, system_name="نظام المقررات")
    t = tc.template_tags("year - Temp - Ar.docx")
    assert (t["system_name"], t["system_ar"]) == ("النظام الفصلي", "النظام الفصلي")
    files = ["year - Temp - Ar.docx", "semester - Temp - Ar.docx"]
    assert filter_templates_for_system(files, {"study_system_name_ar": "نظام المقررات"}) == ["semester - Temp - Ar.docx"]
