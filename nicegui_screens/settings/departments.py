# =============================================================================
# nicegui_screens/settings/departments.py — Departments tab (part of SettingsScreen)
#
# The departments list and editor are the same screen as before; it is now
# embedded in the Settings tab panel instead of being a sidebar page.
# =============================================================================

from nicegui_screens.departments_screen import DepartmentsScreen


class DepartmentsMixin:
    """Departments list and editor, shown in the Settings tab panel."""

    def _section_departments(self) -> None:
        DepartmentsScreen()
