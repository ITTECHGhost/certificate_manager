"""College and departments in one view; personnel is a Settings tab, not a sidebar screen."""
from pathlib import Path

from nicegui_screens.settings.departments import DepartmentsMixin, departments_newest_first
from nicegui_screens.settings_screen import SettingsScreen
from nicegui_ui.ui_theme import NAV_ITEMS

SETTINGS = Path(__file__).resolve().parent.parent / "nicegui_screens"
SCREEN_SOURCE = (SETTINGS / "settings" / "screen.py").read_text(encoding="utf-8")
DEPT_SOURCE = (SETTINGS / "settings" / "departments.py").read_text(encoding="utf-8")
PERSONNEL_SOURCE = (SETTINGS / "personnel_screen.py").read_text(encoding="utf-8")


def test_settings_screen_embeds_departments_section():
    assert issubclass(SettingsScreen, DepartmentsMixin)
    assert callable(getattr(SettingsScreen, "_section_departments"))


def test_no_separate_departments_tab_departments_follow_the_college():
    assert 'ui.tab(name="departments"' not in SCREEN_SOURCE
    line = next(l for l in SCREEN_SOURCE.splitlines() if '"institution": (self.tab_institution' in l)
    assert line.index("_section_institution_info") < line.index("_section_departments") < line.index("_section_study_systems")


def test_department_form_has_only_the_two_names():
    assert DEPT_SOURCE.count("UI.text_input(") == 4          # add: ar + en; edit: ar + en
    assert "college_ar" not in DEPT_SOURCE and "college_en" not in DEPT_SOURCE


def test_departments_newest_first():
    rows = [{"id": 2}, {"id": 10}, {"id": "7"}, {"id": None}]
    assert [r["id"] for r in departments_newest_first(rows)] == [10, "7", 2, None]


def test_departments_and_personnel_not_sidebar_screens():
    keys = {item["key"] for item in NAV_ITEMS}
    assert "departments" not in keys and "personnel" not in keys


def test_personnel_is_a_settings_tab_with_the_sidebar_permission_rule():
    assert 'ui.tab(name="personnel"' in SCREEN_SOURCE
    assert '"personnel" in access_screens' in SCREEN_SOURCE


def test_personnel_list_shows_position_and_role_under_name():
    assert '{"name": "position", "label": "المنصب"' in PERSONNEL_SOURCE
    assert '"label": "الصلاحية"' not in PERSONNEL_SOURCE
    assert "(role_name, r.get(\"username\")" in PERSONNEL_SOURCE
