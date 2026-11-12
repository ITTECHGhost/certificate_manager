"""Management lists share one shape: read-only rows, quiet confirmed delete, one paginator."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCREENS = ROOT / "nicegui_screens"

LIST_SCREENS = [
    "students_screen.py",
    "graduation_orders_screen.py",
    "courses_screen.py",
    "personnel_screen.py",
    "departments_screen.py",
]


def _src(name: str) -> str:
    return (SCREENS / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", LIST_SCREENS)
def test_one_paginator_and_no_old_prev_next(name):
    src = _src(name)
    assert src.count("UI.paginator(") == 1
    assert "def go_prev" not in src and "def go_next" not in src
    assert "السابق" not in src


@pytest.mark.parametrize("name", LIST_SCREENS)
def test_rows_open_on_click_and_delete_is_quiet_and_confirmed(name):
    src = _src(name)
    assert 'on("rowClick"' in src
    assert "app-btn-danger-icon" in src
    assert "UI.confirm_dialog(" in src


@pytest.mark.parametrize("name", LIST_SCREENS)
def test_search_and_empty_state(name):
    src = _src(name)
    assert "UI.search_input(" in src
    assert "UI.empty_state(" in src


def test_course_rows_are_read_only_and_edit_in_a_dialog():
    src = _src("courses_screen.py")
    assert "make_quick_saver" not in src          # no inline editing in the rows
    body = src[src.index("def show_edit_view"):src.index("def confirm_delete(self, row")]
    assert "ui.dialog()" in body and "self.container.clear()" not in body


def test_signature_chip_only_for_signers():
    src = _src("personnel_screen.py")
    assert '<span v-if="props.value" class="app-chip app-chip--accent">' in src
    assert "بدون توقيع" not in src


def test_order_number_and_date_stand_out():
    src = _src("graduation_orders_screen.py")
    assert "body-cell-order_number" in src and "body-cell-order_date" in src
