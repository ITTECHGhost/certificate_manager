import logging
log = logging.getLogger(__name__)

# =============================================================================
# nicegui_screens/settings/screen.py — NiceGUI Settings Screen (wiring only;
# each tab's sections live in a mixin module next to this file)
#
# Visual styling: CSS hook classes (app-*) from theme.css
# This file contains ONLY structural layout classes (w-*, h-*, p-*, gap-*, flex, etc.)
# =============================================================================

import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from nicegui import ui
from data.repositories import (
    SettingsRepository, StudySystemRepository, PersonnelRepository,
    PermissionRepository, RoleRepository, DepartmentRepository,
    ALL_PERMISSION_KEYS
)
import api_client
import app_paths
from api_config import get_api_url
from nicegui_ui.ui_components import UI
from nicegui_ui.state import get_user_session
from nicegui_ui.template_constants import (
    TEMPLATE_REGISTRY,
    TEMPLATE_ABBREVIATIONS,
    get_template_info,
    get_friendly_template_name,
    get_short_template_badge,
    load_templates_config,
    register_template,
    delete_template_config,
)
from utils.file_delivery import deliver_file
from nicegui_ui.upload_utils import read_upload
from nicegui_screens.settings.institution import InstitutionMixin
from nicegui_screens.settings.study_systems import StudySystemsMixin
from nicegui_screens.settings.appearance import AppearanceMixin
from nicegui_screens.settings.printers import PrintersMixin
from nicegui_screens.settings.roles import RolesMixin
from nicegui_screens.settings.logs_analytics import LogsAnalyticsMixin
from nicegui_screens.settings.server import ServerMixin
from nicegui_screens.settings.maintenance import MaintenanceMixin
from nicegui_screens.settings.templates import TemplatesMixin
from nicegui_screens.settings.departments import DepartmentsMixin


class SettingsScreen(
    InstitutionMixin,
    DepartmentsMixin,
    StudySystemsMixin,
    AppearanceMixin,
    PrintersMixin,
    RolesMixin,
    LogsAnalyticsMixin,
    ServerMixin,
    MaintenanceMixin,
    TemplatesMixin,
):
    """
    NiceGUI Settings Screen.
    Renders inside the MainAppShell scroll content area.
    """

    def __init__(self, on_notify=None, on_navigate=None) -> None:
        self.s_repo = SettingsRepository()
        self.sys_repo = StudySystemRepository()
        self.p_repo = PersonnelRepository()
        self.perm_repo = PermissionRepository()
        self.role_repo = RoleRepository()
        self.dept_repo = DepartmentRepository()
        self.on_notify = on_notify or (lambda msg, typ="positive": ui.notify(msg, type=typ))
        self.on_navigate = on_navigate

        self.session = get_user_session()
        self.emp_id = self.session.emp_id

        self.settings_data: dict = {}
        self.appearance_data: dict = {}
        self.systems: list = []

        self.univ_ar_input = None
        self.univ_en_input = None
        self.college_ar_input = None
        self.college_en_input = None
        self.univ_logo_path = None
        self.college_logo_path = None
        self.univ_logo_img = None
        self.college_logo_img = None
        self.univ_placeholder_col = None
        self.college_placeholder_col = None
        self.univ_logo_status = None
        self.college_logo_status = None
        self.theme_select = None
        self.accent_select = None
        self.font_select = None
        self.font_size_input = None
        self.rtl_switch = None

        # Full-Page Subview Routing for Roles & Permissions Matrix
        self.roles_subview_mode: str = "overview"  # "overview" | "edit_role" | "user_matrix"
        self.editing_role_data: dict | None = None
        self.target_matrix_user_id: int | None = None
        self._render_roles_container = None

        self._load_data()
        self._build_ui()
        self._apply_initial_theme()

    def _load_data(self) -> None:
        """Fetch current settings and study systems. Appearance comes from session preferences."""
        try:
            self.settings_data = self.s_repo.get_settings() or {}
            self.univ_logo_path = self.settings_data.get("univ_logo_path") or "assets/univ_logo.png"
            self.college_logo_path = self.settings_data.get("college_logo_path") or "assets/college_logo.png"
            self.systems = self.sys_repo.get_all() or []
        except Exception as exc:
            log.warning(f"[SettingsScreen] Error loading settings data: {exc}")

    def _build_ui(self) -> None:
        """
        Build the settings screen layout using clean tabbed panels.
        Granular RBAC enforcement:
        - Hardware & Printer setup is accessible to all users authorized to access Settings.
        - Other tabs (institution, appearance, roles, templates, logs) require specific permissions.
        """
        is_admin = (self.session.role == "admin")
        # User grants + role actions, cached at login (no network call here)
        effective_perms = set(self.session.get_access().get("permissions") or [])

        # Granular permissions checking - strictly governed by specific granular permission keys
        can_inst = is_admin or "settings:institution" in effective_perms or "settings:study_systems" in effective_perms
        can_app = is_admin or "settings:appearance" in effective_perms
        can_printers = True  # Always accessible to users in Settings screen
        can_roles = is_admin or "settings:roles" in effective_perms
        can_templates = is_admin or "settings:templates" in effective_perms
        can_logs = is_admin or "settings:logs" in effective_perms
        # Departments and personnel used to be sidebar screens: same rule as the sidebar
        access = self.session.get_access() or {}
        access_screens = access.get("allowed_screens")
        can_depts = is_admin or not access or access_screens is None or "departments" in access_screens
        can_personnel = is_admin or not access or access_screens is None or "personnel" in access_screens
        self._can_edit_departments = can_depts

        # Default tab selection
        default_tab_name = "institution" if can_inst else ("appearance" if can_app else "printers")

        with ui.column().classes("w-full max-w-full min-w-0 gap-6 pb-12 overflow-hidden"):
            with ui.row().classes("w-full max-w-full min-w-0 gap-6 items-start no-wrap"):
                with ui.tabs().classes("app-tabs w-60 shrink-0 max-w-full").props("vertical dense inline-label") as self.tabs:
                    self.tab_institution = ui.tab(name="institution", label="معلومات الجامعة", icon="domain") if can_inst else None
                    self.tab_app = ui.tab(name="appearance", label="المظهر والسمات", icon="palette") if can_app else None
                    self.tab_printers = ui.tab(name="printers", label="إعداد الطابعات", icon="print")
                    self.tab_personnel = ui.tab(name="personnel", label="الكوادر", icon="manage_accounts") if can_personnel else None
                    self.tab_roles = ui.tab(name="roles", label="الأدوار والصلاحيات", icon="admin_panel_settings") if can_roles else None
                    self.tab_templates = ui.tab(name="templates", label="قوالب الوثائق", icon="description") if can_templates else None
                    self.tab_logs = ui.tab(name="logs", label="السيرفر والصيانة والسجلات", icon="dns") if can_logs else None

                initial_tab = getattr(self, f"tab_{default_tab_name}", self.tab_printers)

                # Each panel is built the first time its tab opens, so the page shows at once
                builders = {
                    # College first, its departments under it, then the study systems
                    "institution": (self.tab_institution, (self._section_institution_info, self._section_departments, self._section_study_systems)),
                    "appearance": (self.tab_app, (self._section_appearance,)),
                    "printers": (self.tab_printers, (self._section_printer_settings,)),
                    "personnel": (self.tab_personnel, (self._section_personnel,)),
                    "roles": (self.tab_roles, (self._section_roles_and_permissions,)),
                    "templates": (self.tab_templates, (self._section_templates_management,)),
                    "logs": (self.tab_logs, ((self._section_server_config,)
                                             + ((self._section_server_update,) if is_admin else ())
                                             + (self._section_database_maintenance, self._section_system_logs))),
                }
                panels: dict[str, ui.tab_panel] = {}
                built: set[str] = set()

                def _build_panel(name: str) -> None:
                    if name in built or name not in panels:
                        return
                    built.add(name)
                    with panels[name]:
                        for section in builders[name][1]:
                            section()

                with ui.tab_panels(self.tabs, value=initial_tab).classes("flex-1 min-w-0 bg-transparent p-0"):
                    for name, (tab, _sections) in builders.items():
                        if tab:
                            panels[name] = ui.tab_panel(tab).classes("w-full gap-6 p-0 flex flex-col")

                _build_panel(initial_tab._props.get("name") if initial_tab else "printers")
                self.tabs.on_value_change(lambda e: _build_panel(e.value if isinstance(e.value, str) else getattr(e.value, "_props", {}).get("name")))

    def _section_about(self) -> None:
        with UI.card():
            UI.card_header("حول البرنامج", "info", icon_css="app-text-faint")

            with ui.column().classes("w-full items-center text-center gap-2 p-4"):
                UI.section_label("نظام إدارة الشهادات")
                UI.muted_label("تم التطوير لأتمتة عمليات إصدار الوثائق والشهادات الجامعية.").classes("mt-2")
                ui.label("تم التطوير بواسطة م. حسين").classes(
                    "app-text-success text-xs font-semibold mt-1"
                )

                async def _check_updates_dialog():
                    from sync_engine import is_online
                    if not is_online():
                        ui.notify("لا يمكن التحقق من التحديثات في الوضع غير المتصل", type="warning")
                        return
                    n = ui.notification("جاري التحقق من وجود تحديثات جديدة...", timeout=None, spinner=True)
                    try:
                        import asyncio
                        from nicegui import run
                        import services.updater as upd
                        res = await run.io_bound(upd.check_for_updates)
                        n.dismiss()
                        if not res or not res.get("has_update"):
                            ui.notify("البرنامج محدث إلى آخر إصدار متاح", type="positive")
                            return

                        from nicegui_ui.update_prompt import show_update_dialog
                        show_update_dialog(res)
                    except Exception as e:
                        n.dismiss()
                        ui.notify(f"خطأ أثناء التحقق: {e}", type="negative")

                ui.button("التحقق من التحديثات", icon="system_update_alt", on_click=_check_updates_dialog).classes("app-btn-secondary px-4 py-2 text-xs rounded-xl mt-3")

    def _section_personnel(self) -> None:
        from nicegui_screens.personnel_screen import PersonnelScreen
        PersonnelScreen()

    def open_tab(self, name: str) -> None:
        """Switch to a Settings tab by name (used by the roles page's personnel button)."""
        tab = getattr(self, f"tab_{name}", None)
        if tab is not None:
            self.tabs.set_value(name)

    def _get_event_value(self, e, element, default_val):
        if e is not None:
            if hasattr(e, "value") and e.value is not None:
                return e.value
            elif hasattr(e, "args"):
                args = e.args
                if isinstance(args, (str, int, float)):
                    return args
                elif isinstance(args, (list, tuple)) and len(args) > 0:
                    return args[0]
        if element is not None and element.value is not None:
            return element.value
        return default_val
