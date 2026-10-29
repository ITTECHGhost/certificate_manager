import logging
log = logging.getLogger(__name__)

# =============================================================================
# nicegui_screens/settings_screen.py — NiceGUI Settings Screen
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


class SettingsScreen(
    InstitutionMixin,
    StudySystemsMixin,
    AppearanceMixin,
    PrintersMixin,
    RolesMixin,
    LogsAnalyticsMixin,
    ServerMixin,
    MaintenanceMixin,
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

    def _section_templates_management(self) -> None:
        """Dedicated settings tab to inspect, manage, upload, and understand certificate Word templates."""
        templates_dir = str(app_paths.data_path("templets"))
        if not os.path.exists(templates_dir):
            os.makedirs(templates_dir, exist_ok=True)

        # ── 1. Guide & Abbreviations Legend Card ──────────────────────────────
        with UI.card():
            with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)]"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("menu_book", size="md").classes("stat-text-blue")
                    with ui.column().classes("gap-0"):
                        ui.label("دليل معاني واختصارات أسماء القوالب — Template Legend & Code Guide").classes("text-base font-bold app-text-primary")
                        ui.label("توضيح معايير التسمية المعتمدة لقوالب الوثائق: [اللغة]، [النظام / الدرجة]، [SBS إن وجد]، cr").classes("text-xs app-text-muted")

            with ui.grid(columns=4).classes("w-full gap-3 pt-2"):
                legends = [
                    ("En", "اللغة الإنكليزية", "English Language", "text-cyan-400", "language"),
                    ("Ar", "اللغة العربية", "Arabic Language", "text-emerald-400", "translate"),
                    ("Semester", "نظام المقررات (فصلي)", "Semester Course System", "text-teal-400", "view_timeline"),
                    ("Annual", "النظام السنوي", "Annual / Yearly System", "text-indigo-400", "calendar_today"),
                    ("Master", "الماجستير (دراسات عليا)", "Master's Degree Program", "text-purple-400", "school"),
                    ("SBS", "درجات مقترنة جنباً إلى جنب", "Side-By-Side Courses", "text-amber-400", "view_column"),
                    ("cr", "وثيقة تخرج رسمية", "Official Certificate", "text-blue-400", "verified"),
                    ("Temp", "ملف قالب Word رسمي", "Word Template File (.docx)", "text-slate-400", "description"),
                ]
                for code, ar_label, en_label, color, icon in legends:
                    with ui.row().classes("items-center gap-2.5 p-3 rounded-xl border border-[var(--border-default)] bg-[var(--bg-main)]"):
                        ui.icon(icon, size="sm").classes(color)
                        with ui.column().classes("gap-0"):
                            with ui.row().classes("items-center gap-1.5"):
                                ui.label(code).classes(f"font-bold font-mono text-xs {color}")
                                ui.label(f"— {ar_label}").classes("text-xs font-semibold app-text-primary")
                            ui.label(en_label).classes("text-[10px] app-text-muted")

        # ── 2. Templates Management & File Catalog Card ──────────────────────
        with UI.card():
            with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)] flex-wrap gap-2"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("article", size="md").classes("stat-text-purple")
                    with ui.column().classes("gap-0"):
                        ui.label("قوالب الوثائق الرسمية المتوفرة — Certificate Word Templates").classes("text-base font-bold app-text-primary")
                        ui.label("إدارة ملفات نماذج Word، تعديل مسمياتها المعتمدة، وفتحها مباشرة في Microsoft Word").classes("text-xs app-text-muted")

                with ui.row().classes("items-center gap-2"):
                    def _open_templates_dir():
                        folder_path = os.path.abspath(templates_dir)
                        if os.path.exists(folder_path):
                            try:
                                os.startfile(folder_path)
                                ui.notify(f"تم فتح مجلد القوالب: {folder_path}", type="positive")
                            except Exception as e:
                                ui.notify(f"تعذر فتح المجلد: {e}", type="warning")

                    async def _sync_templates_from_server():
                        from sync_engine import is_online
                        if not is_online():
                            ui.notify("لا يمكن المزامنة في الوضع غير المتصل / Offline mode", type="warning")
                            return
                        n = ui.notification("جاري مزامنة نماذج الوثائق مع الخادم المركزي... / Syncing...", timeout=None, spinner=True)
                        try:
                            from nicegui import run
                            import services.template_sync as t_sync
                            res = await run.io_bound(t_sync.sync_templates_if_online)
                            n.dismiss()
                            if res.get("synced_files"):
                                ui.notify(f"تم تحديث {len(res['synced_files'])} ملف بنجاح / Synced successfully", type="positive")
                                _render_templates_table.refresh()
                            elif res.get("up_to_date"):
                                ui.notify("جميع القوالب محدثة ومطابقة للخادم المركزي / Up to date", type="info")
                            else:
                                ui.notify(f"فشلت مزامنة بعض الملفات: {res.get('errors')}", type="negative")
                        except Exception as e:
                            n.dismiss()
                            ui.notify(f"خطأ أثناء المزامنة: {e}", type="negative")

                    ui.button("مزامنة مع الخادم / Sync from Server", icon="cloud_sync", on_click=_sync_templates_from_server).classes("app-btn-secondary px-3 py-1.5 text-xs rounded-xl")
                    ui.button("فتح مجلد القوالب / Open Folder", icon="folder_open", on_click=_open_templates_dir).classes("app-btn-secondary px-3 py-1.5 text-xs rounded-xl")
                    ui.button("تحديث / Refresh", icon="refresh", on_click=lambda: _render_templates_table.refresh()).classes("app-btn-secondary px-3 py-1.5 text-xs rounded-xl")

            @ui.refreshable
            def _render_templates_table():
                files = []
                if os.path.exists(templates_dir):
                    files = [f for f in sorted(os.listdir(templates_dir)) if f.endswith(".docx") and not f.startswith("~")]

                if not files:
                    with ui.column().classes("w-full py-8 items-center justify-center gap-2 text-center"):
                        ui.icon("folder_off", size="xl").classes("app-text-muted")
                        ui.label("لم يتم العثور على أية قوالب Word في مجلد templets/").classes("text-sm font-semibold app-text-primary")
                        ui.label("يمكنك إضافة ورفع القوالب أدناه مع تحديد مسمياتها الرسمية").classes("text-xs app-text-muted")
                    return

                with ui.column().classes("w-full gap-2 pt-2"):
                    for f in files:
                        filepath = os.path.join(templates_dir, f)
                        info = get_template_info(f)
                        display_name = info.get("display_name") or f
                        size_kb = round(os.path.getsize(filepath) / 1024, 1)
                        mtime = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d %H:%M")

                        with ui.row().classes("w-full justify-between items-center p-3 rounded-xl border border-[var(--border-default)] bg-[var(--bg-main)] hover:border-blue-500/50 transition-all gap-3 flex-wrap"):
                            # Left info: Icon + Title + Filename
                            with ui.row().classes("items-center gap-3 flex-1 min-w-[280px]"):
                                ui.icon("description", size="sm").classes("text-blue-400 shrink-0")
                                with ui.column().classes("gap-0"):
                                    ui.label(display_name).classes("text-xs font-bold text-blue-400")
                                    with ui.row().classes("items-center gap-2 text-[10px] text-slate-400"):
                                        ui.label(f).classes("font-mono text-slate-300 font-semibold")
                                        ui.label("•")
                                        ui.label(f"{size_kb} KB")
                                        ui.label("•")
                                        ui.label(f"آخر تعديل: {mtime}")

                            # Middle Badges: System + Language + Type
                            with ui.row().classes("items-center gap-2 shrink-0"):
                                sys_name = info.get("system_ar") or "النظام السنوي"
                                sys_color = "bg-blue-500/20 text-blue-300 border-blue-500/30" if "سنوي" in sys_name else ("bg-purple-500/20 text-purple-300 border-purple-500/30" if "ماجستير" in sys_name else "bg-teal-500/20 text-teal-300 border-teal-500/30")
                                ui.label(sys_name).classes(f"text-[10px] px-2 py-0.5 rounded-lg border font-semibold {sys_color}")

                                lang_name = info.get("lang_ar") or "عربي"
                                lang_color = "bg-emerald-500/20 text-emerald-300 border-emerald-500/30" if "عربي" in lang_name else "bg-cyan-500/20 text-cyan-300 border-cyan-500/30"
                                ui.label(lang_name).classes(f"text-[10px] px-2 py-0.5 rounded-lg border font-semibold {lang_color}")

                                type_name = info.get("type_ar") or "بدون درجات"
                                type_color = "bg-amber-500/20 text-amber-300 border-amber-500/30" if "درجات" in type_name or "SBS" in type_name else "bg-slate-500/20 text-slate-300 border-slate-500/30"
                                ui.label(type_name).classes(f"text-[10px] px-2 py-0.5 rounded-lg border font-semibold {type_color}")

                            # Actions: Edit Name, Download, Open in Word
                            with ui.row().classes("items-center gap-1.5 shrink-0"):
                                def _open_rename_dialog(filename=f, current_title=display_name):
                                    with ui.dialog() as rename_dlg, UI.card().classes(
                                        "p-5 gap-4 w-[420px] max-w-full rounded-2xl border border-blue-500/30 shadow-2xl bg-[var(--surface-card)]"
                                    ):
                                        with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)]"):
                                            ui.label("تعديل اسم القالب / Edit Template Name").classes("text-sm font-bold app-text-primary")
                                            ui.button(icon="close", on_click=rename_dlg.close).classes("app-btn-secondary p-1 rounded-lg text-xs")

                                        ui.label(f"الملف: {filename}").classes("text-xs font-mono app-text-muted")

                                        new_name_input = ui.input(
                                            label="الاسم المعتمد في القوائم والسجلات",
                                            value=current_title
                                        ).classes("w-full app-input text-xs").props("outlined dense")

                                        with ui.row().classes("w-full justify-end gap-2 mt-2"):
                                            UI.secondary_button("إلغاء", on_click=rename_dlg.close).classes("text-xs px-3 py-1.5")

                                            def _do_rename():
                                                val = (new_name_input.value or "").strip()
                                                if val:
                                                    register_template(filename, val)
                                                    rename_dlg.close()
                                                    ui.notify("تم تعديل اسم القالب بنجاح", type="positive")
                                                    _render_templates_table.refresh()

                                            UI.primary_button("حفظ", icon="save", on_click=_do_rename).classes("text-xs px-3 py-1.5")
                                    rename_dlg.open()

                                ui.button(icon="edit", on_click=_open_rename_dialog).classes("app-btn-secondary p-1.5 rounded-lg text-xs").tooltip("تعديل اسم القالب / Edit Display Name")

                                def _open_word(fp=filepath):
                                    try:
                                        os.startfile(os.path.abspath(fp))
                                        ui.notify(f"تم فتح القالب في Microsoft Word: {os.path.basename(fp)}", type="positive")
                                    except Exception as exc:
                                        ui.notify(f"تعذر فتح الملف: {exc}", type="warning")

                                ui.button(icon="launch", on_click=_open_word).classes("app-btn-secondary p-1.5 rounded-lg text-xs").tooltip("فتح القالب في Word / Open in Word")
                                ui.button(icon="download", on_click=lambda fp=filepath: deliver_file(fp, filename=os.path.basename(fp), title=f"تم حفظ القالب ({os.path.basename(fp)}) بنجاح", auto_open=False)).classes("app-btn-secondary p-1.5 rounded-lg text-xs").tooltip("تنزيل القالب / Download Document")

            _render_templates_table()

        # ── 3. Add New Template & Choose Name Card ───────────────────────────
        with UI.card():
            with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)]"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("add_circle", size="md").classes("stat-text-emerald")
                    with ui.column().classes("gap-0"):
                        ui.label("إضافة قالب وثيقة جديد وتحديد اسمه — Add New Template & Set Name").classes("text-base font-bold app-text-primary")
                        ui.label("رفع ملف Word (.docx) وتحديد الاسم المعتمد للقالب (مثال: Ar, Master, cr أو En, Master, cr)").classes("text-xs app-text-muted")

            new_template_state = {
                "file_name": "",
                "file_content": None,
                "display_name": "Ar, Master, cr",
                "lang": "Ar",
                "system": "Master",
                "sbs": False,
            }

            with ui.column().classes("w-full gap-4 pt-2"):
                # Quick generator / helper row
                with ui.row().classes("w-full items-center gap-3 flex-wrap"):
                    def _update_suggested_name():
                        l = new_template_state["lang"]
                        s = new_template_state["system"]
                        is_sbs = new_template_state["sbs"]
                        parts = [l, s]
                        if is_sbs:
                            parts.append("SBS")
                        parts.append("cr")
                        sug = ", ".join(parts)
                        new_template_state["display_name"] = sug
                        name_input.value = sug

                    def _on_lang_change(e):
                        val = getattr(e, "value", None) or (e if isinstance(e, str) else "Ar")
                        new_template_state["lang"] = str(val or "Ar")
                        _update_suggested_name()

                    def _on_system_change(e):
                        val = getattr(e, "value", None) or (e if isinstance(e, str) else "Master")
                        new_template_state["system"] = str(val or "Master")
                        _update_suggested_name()

                    def _on_sbs_toggle(e):
                        val = getattr(e, "value", None) or (e if isinstance(e, bool) else False)
                        new_template_state["sbs"] = bool(val)
                        _update_suggested_name()

                    ui.select(
                        options={"Ar": "عربي (Ar)", "En": "إنكليزي (En)"},
                        value="Ar",
                        label="اللغة",
                        on_change=_on_lang_change
                    ).classes("app-input text-xs w-36").props("outlined dense options-dense")

                    ui.select(
                        options={
                            "Master": "ماجستير (Master)",
                            "Semester": "نظام المقررات (Semester)",
                            "Annual": "النظام السنوي (Annual)",
                            "PhD": "دكتوراه (PhD)",
                            "Diploma": "دبلوم عالي (Diploma)",
                        },
                        value="Master",
                        label="النظام / الدرجة",
                        on_change=_on_system_change
                    ).classes("app-input text-xs w-48").props("outlined dense options-dense")

                    ui.checkbox(
                        "مقترن جنباً إلى جنب (SBS)",
                        value=False,
                        on_change=_on_sbs_toggle
                    ).classes("text-xs font-semibold app-text-primary")

                # Name input row
                with ui.row().classes("w-full items-center gap-3"):
                    name_input = ui.input(
                        label="الاسم المعتمد للقالب / Template Name",
                        value=new_template_state["display_name"],
                        placeholder="مثال: Ar, Master, cr أو En, Master, cr"
                    ).classes("flex-1 app-input text-xs").props("outlined dense")

                    def _on_name_typed(e):
                        new_template_state["display_name"] = (name_input.value or "").strip()

                    name_input.on("change", _on_name_typed)

                # Selected file status indicator
                file_status_label = ui.label("لم يتم اختيار ملف Word بعد").classes("text-xs app-text-muted italic")

                async def _handle_upload(e):
                    try:
                        fname, content = await read_upload(e)
                        if not fname.lower().endswith(".docx"):
                            ui.notify("الملف غير مدعوم! يجب أن يكون ملف Word بتنسيق docx.", type="warning")
                            return

                        if not content:
                            ui.notify("تعذر قراءة محتوى الملف المرفوع", type="warning")
                            return

                        new_template_state["file_name"] = fname
                        new_template_state["file_content"] = content
                        file_status_label.set_text(f"تم اختيار الملف: {fname} ({round(len(content)/1024, 1)} KB)")
                        file_status_label.classes(remove="italic app-text-muted", add="font-bold text-emerald-400")
                        ui.notify(f"تم استلام ملف القالب: {fname}، اضغط على زر الحفظ أدناه لتسجيله", type="positive")
                    except Exception as up_err:
                        log.error(f"Failed to handle upload: {up_err}")
                        ui.notify(f"خطأ أثناء قراءة الملف: {up_err}", type="negative")

                ui.upload(
                    label="اختر أو اسحب ملف قالب Word (.docx) هنا",
                    auto_upload=True,
                    on_upload=_handle_upload
                ).props("accept=.docx max-files=1").classes("w-full border-2 border-dashed border-[var(--border-default)] rounded-2xl p-3 bg-[var(--bg-main)]")

                # Save Button Row
                with ui.row().classes("w-full justify-end items-center gap-2 pt-2"):
                    def _save_new_template():
                        fname = new_template_state.get("file_name")
                        content = new_template_state.get("file_content")
                        chosen_name = (name_input.value or new_template_state.get("display_name") or "").strip()

                        if not fname or not content:
                            ui.notify("يرجى اختيار ملف Word (.docx) أولاً قبل الحفظ!", type="warning")
                            return

                        if not chosen_name:
                            ui.notify("يرجى إدخال اسم للقالب!", type="warning")
                            return

                        dest_path = os.path.join(templates_dir, fname)
                        try:
                            with open(dest_path, "wb") as f_out:
                                f_out.write(content)

                            register_template(
                                key_or_filename=fname,
                                display_name=chosen_name,
                                file=fname,
                                lang=new_template_state["lang"],
                                system=new_template_state["system"],
                                sbs=new_template_state["sbs"]
                            )

                            ui.notify(f"تم حفظ وتسجيل القالب بنجاح باسم: ({chosen_name})", type="positive")
                            new_template_state["file_name"] = ""
                            new_template_state["file_content"] = None
                            file_status_label.set_text("لم يتم اختيار ملف Word بعد")
                            file_status_label.classes(remove="font-bold text-emerald-400", add="italic app-text-muted")
                            _render_templates_table.refresh()
                        except Exception as err:
                            log.error(f"Failed to save new template: {err}")
                            ui.notify(f"خطأ أثناء حفظ القالب: {err}", type="negative")

                    UI.primary_button(
                        "حفظ وتسجيل القالب / Save & Register Template",
                        icon="save",
                        on_click=_save_new_template
                    ).classes("text-xs px-4 py-2")
