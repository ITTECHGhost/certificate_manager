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


class SettingsScreen(
    InstitutionMixin,
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

        # Default tab selection
        default_tab_name = "institution" if can_inst else ("appearance" if can_app else "printers")

        with ui.column().classes("w-full max-w-full min-w-0 gap-6 pb-12 overflow-hidden"):
            with ui.tabs().classes("w-full max-w-full min-w-0 app-tabs border-b border-[var(--border-default)]").props("dense shrink inline-label mobile-arrows outside-arrows") as self.tabs:
                # Tab 1: Institution
                if can_inst:
                    with ui.tab(name="institution", label="", icon="domain") as self.tab_institution:
                        with ui.column().classes("gap-0 items-start justify-center text-right py-0.5"):
                            ui.label("المؤسسة").classes("font-bold text-sm leading-tight")
                            ui.label("Institution").classes("font-normal text-xs opacity-75 leading-tight")
                else:
                    self.tab_institution = None

                # Tab 2: Appearance
                if can_app:
                    with ui.tab(name="appearance", label="", icon="palette") as self.tab_app:
                        with ui.column().classes("gap-0 items-start justify-center text-right py-0.5"):
                            ui.label("المظهر والسمات").classes("font-bold text-sm leading-tight")
                            ui.label("Appearance").classes("font-normal text-xs opacity-75 leading-tight")
                else:
                    self.tab_app = None

                # Tab 3: Hardware & Printer Setup (Replaces account view)
                with ui.tab(name="printers", label="", icon="print") as self.tab_printers:
                    with ui.column().classes("gap-0 items-start justify-center text-right py-0.5"):
                        ui.label("إعداد الطابعات").classes("font-bold text-sm leading-tight")
                        ui.label("Printers Setup").classes("font-normal text-xs opacity-75 leading-tight")

                # Tab 4: Roles & Permissions (Access Control)
                if can_roles:
                    with ui.tab(name="roles", label="", icon="admin_panel_settings") as self.tab_roles:
                        with ui.column().classes("gap-0 items-start justify-center text-right py-0.5"):
                            ui.label("الأدوار والصلاحيات").classes("font-bold text-sm leading-tight")
                            ui.label("Roles & Permissions").classes("font-normal text-xs opacity-75 leading-tight")
                else:
                    self.tab_roles = None

                # Tab 5: Templates Management
                if can_templates:
                    with ui.tab(name="templates", label="", icon="description") as self.tab_templates:
                        with ui.column().classes("gap-0 items-start justify-center text-right py-0.5"):
                            ui.label("قوالب الوثائق").classes("font-bold text-sm leading-tight")
                            ui.label("Templates").classes("font-normal text-xs opacity-75 leading-tight")
                else:
                    self.tab_templates = None

                # Tab 6: Server, Maintenance & Logs
                if can_logs:
                    with ui.tab(name="logs", label="", icon="dns") as self.tab_logs:
                        with ui.column().classes("gap-0 items-start justify-center text-right py-0.5"):
                            ui.label("السيرفر والصيانة والسجلات").classes("font-bold text-sm leading-tight")
                            ui.label("Server, Maintenance & Logs").classes("font-normal text-xs opacity-75 leading-tight")
                else:
                    self.tab_logs = None

            initial_tab = getattr(self, f"tab_{default_tab_name}", self.tab_printers)
            with ui.tab_panels(self.tabs, value=initial_tab).classes("w-full bg-transparent p-0 gap-6"):
                if can_inst and self.tab_institution:
                    with ui.tab_panel(self.tab_institution).classes("w-full gap-6 p-0 flex flex-col"):
                        self._section_institution_info()
                        self._section_study_systems()

                if can_app and self.tab_app:
                    with ui.tab_panel(self.tab_app).classes("w-full gap-6 p-0 flex flex-col"):
                        self._section_appearance()

                with ui.tab_panel(self.tab_printers).classes("w-full gap-6 p-0 flex flex-col"):
                    self._section_printer_settings()

                if can_roles and self.tab_roles:
                    with ui.tab_panel(self.tab_roles).classes("w-full gap-6 p-0 flex flex-col"):
                        self._section_roles_and_permissions()

                if can_templates and self.tab_templates:
                    with ui.tab_panel(self.tab_templates).classes("w-full gap-6 p-0 flex flex-col"):
                        self._section_templates_management()

                if can_logs and self.tab_logs:
                    with ui.tab_panel(self.tab_logs).classes("w-full gap-6 p-0 flex flex-col"):
                        self._section_server_config()
                        self._section_database_maintenance()
                        self._section_system_logs()

    def _section_about(self) -> None:
        with UI.card():
            UI.card_header("حول البرنامج — About", "info", icon_css="app-text-faint")

            with ui.column().classes("w-full items-center text-center gap-2 p-4"):
                UI.section_label("نظام إدارة الشهادات - الإصدار 2.0 (NiceGUI Native UI)")
                UI.muted_label("Certificate Manager - v2.0")
                UI.muted_label("تم التطوير لأتمتة عمليات إصدار الوثائق والشهادات الجامعية.").classes("mt-2")
                ui.label("Developed by M. Hussein / تم التطوير بواسطة م. حسين").classes(
                    "app-text-success text-xs font-semibold mt-1"
                )

                async def _check_updates_dialog():
                    from sync_engine import is_online
                    if not is_online():
                        ui.notify("لا يمكن التحقق من التحديثات في الوضع غير المتصل / Offline mode", type="warning")
                        return
                    n = ui.notification("جاري التحقق من وجود تحديثات جديدة... / Checking for updates...", timeout=None, spinner=True)
                    try:
                        import asyncio
                        from nicegui import run
                        import services.updater as upd
                        res = await run.io_bound(upd.check_for_updates)
                        n.dismiss()
                        if not res or not res.get("has_update"):
                            ui.notify("البرنامج محدث إلى آخر إصدار متاح / Application is up to date", type="positive")
                            return

                        with ui.dialog() as dlg, ui.card().classes("w-[500px] p-6 gap-4"):
                            UI.card_header(f"تحديث جديد متاح / Update Available: v{res['latest_version']}", "system_update")
                            ui.label(f"الإصدار الحالي: v{res['current_version']} ➔ الجديد: v{res['latest_version']}").classes("text-sm font-bold text-sky-500")
                            if res.get("changelog_ar"):
                                ui.label(f"سجل التغييرات: {res['changelog_ar']}").classes("text-xs text-slate-400")
                            if res.get("changelog_en"):
                                ui.label(f"Changelog: {res['changelog_en']}").classes("text-xs text-slate-400")

                            async def _start_ota():
                                dlg.close()
                                prog_notif = ui.notification("جاري تنزيل التحديث... / Downloading patch...", timeout=None, spinner=True)
                                zip_p = await run.io_bound(upd.download_patch, res)
                                prog_notif.dismiss()
                                if not zip_p:
                                    ui.notify("فشل تنزيل ملف التحديث / Failed to download patch", type="negative")
                                    return
                                ui.notify("تم تنزيل التحديث. جاري إعادة تشغيل التطبيق... / Restarting...", type="positive")
                                await asyncio.sleep(1.0)
                                upd.apply_patch_and_restart(zip_p)
                                import os
                                os._exit(0)

                            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                                ui.button("إلغاء / Cancel", on_click=dlg.close).classes("app-btn-secondary px-4 py-1.5 text-xs rounded-xl")
                                ui.button("تحديث الآن / Update Now", icon="system_update", on_click=_start_ota).classes("app-btn-primary px-4 py-1.5 text-xs rounded-xl")
                        dlg.open()
                    except Exception as e:
                        n.dismiss()
                        ui.notify(f"خطأ أثناء التحقق: {e}", type="negative")

                ui.button("التحقق من التحديثات / Check for Updates", icon="system_update_alt", on_click=_check_updates_dialog).classes("app-btn-secondary px-4 py-2 text-xs rounded-xl mt-3")

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
