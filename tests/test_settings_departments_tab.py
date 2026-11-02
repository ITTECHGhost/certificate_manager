"""Departments moved from the sidebar into the Settings screen, right after the institution tab."""
from pathlib import Path

from nicegui_screens.settings.departments import DepartmentsMixin
from nicegui_screens.settings_screen import SettingsScreen
from nicegui_ui.ui_theme import NAV_ITEMS

SCREEN_SOURCE = (Path(__file__).resolve().parent.parent / "nicegui_screens" / "settings" / "screen.py").read_text(encoding="utf-8")


def test_settings_screen_embeds_departments_section():
    assert issubclass(SettingsScreen, DepartmentsMixin)
    assert callable(getattr(SettingsScreen, "_section_departments"))


def test_departments_tab_follows_institution_tab():
    institution = SCREEN_SOURCE.index('ui.tab(name="institution"')
    departments = SCREEN_SOURCE.index('ui.tab(name="departments"')
    appearance = SCREEN_SOURCE.index('ui.tab(name="appearance"')
    assert institution < departments < appearance


def test_departments_no_longer_a_sidebar_screen():
    assert all(item["key"] != "departments" for item in NAV_ITEMS)
