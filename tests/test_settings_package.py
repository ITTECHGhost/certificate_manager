"""The Settings screen is assembled from one mixin per section (nicegui_screens/settings/).

Every method SettingsScreen had before the split must still resolve on it, and come
from the mixin module the plan assigns it to.
"""
import importlib

import pytest

from nicegui_screens.settings_screen import SettingsScreen

SECTIONS = {
    "institution": ("InstitutionMixin", [
        "_section_institution_info", "_save_institution_info",
    ]),
    "study_systems": ("StudySystemsMixin", [
        "_section_study_systems", "_render_systems_list", "_add_study_system",
        "_toggle_system_active", "_delete_study_system",
    ]),
    "appearance": ("AppearanceMixin", [
        "_apply_initial_theme", "_section_appearance", "_on_theme_select_change", "_on_accent_select_change",
        "_on_font_select_change", "_on_font_size_change", "_on_rtl_switch_change", "_save_appearance",
    ]),
    "printers": ("PrintersMixin", [
        "_load_printer_config", "_save_printer_config_file", "_send_printer_test_page", "_section_printer_settings",
    ]),
    "roles": ("RolesMixin", [
        "_section_roles_and_permissions", "_refresh_roles_section", "_open_role_editor_view",
        "_open_user_matrix_view", "_return_to_roles_overview", "_render_roles_overview",
        "_render_full_page_role_editor", "_render_full_page_user_matrix",
    ]),
    "logs_analytics": ("LogsAnalyticsMixin", [
        "_section_system_logs", "_section_analytics", "_do_clear_logs",
    ]),
    "server": ("ServerMixin", [
        "_section_server_config", "_test_server_connection", "_save_server_config",
        "_do_sync_offline_queue", "_refresh_sync_status", "_show_failed_sync_rows",
    ]),
    "maintenance": ("MaintenanceMixin", [
        "_section_database_maintenance", "_do_backup", "_do_restore", "_do_pull_mysql_replicas",
        "_do_clear_read_cache", "_do_check_db_diagnostics",
    ]),
    "templates": ("TemplatesMixin", [
        "_section_templates_management",
    ]),
    "screen": ("SettingsScreen", [
        "__init__", "_load_data", "_build_ui", "_section_about", "_get_event_value",
    ]),
}


@pytest.mark.parametrize("module, cls_name, method", [
    (m, c, name) for m, (c, names) in SECTIONS.items() for name in names
])
def test_method_comes_from_its_section_module(module, cls_name, method):
    owner = getattr(importlib.import_module(f"nicegui_screens.settings.{module}"), cls_name)
    assert method in vars(owner), f"{method} is not defined in nicegui_screens.settings.{module}.{cls_name}"
    assert getattr(SettingsScreen, method) is vars(owner)[method]


def test_no_method_defined_twice():
    seen = {}
    for module, (cls_name, _) in SECTIONS.items():
        owner = getattr(importlib.import_module(f"nicegui_screens.settings.{module}"), cls_name)
        for name, val in vars(owner).items():
            if callable(val) and not name.startswith("__") or name == "__init__":
                assert name not in seen, f"{name} defined in both {seen[name]} and {module}"
                seen[name] = module
