from pathlib import Path

import pytest

from utils.display_format import format_average

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("value, shown", [
    (78.5, "78.50"),
    ("81.236", "81.24"),
    (90, "90.00"),
    ("0", "0.00"),
    (None, "—"),
    ("", "—"),
    ("غير متوفر", "غير متوفر"),
])
def test_average_has_two_decimals(value, shown):
    assert format_average(value) == shown


def test_students_list_and_profile_use_two_decimal_average():
    screen = (ROOT / "nicegui_screens" / "students_screen.py").read_text(encoding="utf-8")
    profile = (ROOT / "nicegui_ui" / "student_components.py").read_text(encoding="utf-8")
    assert '"average": format_average(r.get("average"))' in screen
    assert 'format_average(data.get("average"))' in profile
    assert "round(float(r.get(\"average\")), 3)" not in screen


def test_student_page_has_back_and_issue_buttons():
    profile = (ROOT / "nicegui_ui" / "student_components.py").read_text(encoding="utf-8")
    assert "UI.back_button(self.on_back)" in profile
    assert "إصدار كتاب لهذا الطالب" in profile
