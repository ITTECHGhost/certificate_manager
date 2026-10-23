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
import requests
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


class SettingsScreen:
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

    def _apply_initial_theme(self) -> None:
        """Applies saved theme preference on screen load."""
        self.session.apply_theme_mode()

    def _build_ui(self) -> None:
        """
        Build the settings screen layout using clean tabbed panels.
        Granular RBAC enforcement:
        - Hardware & Printer setup is accessible to all users authorized to access Settings.
        - Other tabs (institution, appearance, roles, templates, logs) require specific permissions.
        """
        is_admin = (self.session.role == "admin")
        user_perms = set()
        try:
            user_perms = set(self.perm_repo.get_user_permissions(self.emp_id) or [])
        except Exception:
            pass

        role_actions = set()
        try:
            role_def = self.role_repo.get_by_id(self.session.role) or {}
            role_actions = set(role_def.get("allowed_actions") or [])
        except Exception:
            pass

        effective_perms = user_perms | role_actions

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

    def _section_institution_info(self) -> None:
        with UI.card():
            UI.card_header("معلومات المؤسسة — Institution Info", "domain", icon_css="stat-text-blue")

            with ui.grid(columns=2).classes("w-full gap-4"):
                self.univ_ar_input = UI.text_input(
                    "اسم الجامعة بالعربية / Univ. Name (AR)",
                    value=self.settings_data.get("univ_name_ar") or ""
                )
                self.univ_en_input = UI.text_input(
                    "اسم الجامعة بالإنكليزية / Univ. Name (EN)",
                    value=self.settings_data.get("univ_name_en") or ""
                )
                self.college_ar_input = UI.text_input(
                    "اسم الكلية بالعربية / College Name (AR)",
                    value=self.settings_data.get("college_name_ar") or ""
                )
                self.college_en_input = UI.text_input(
                    "اسم الكلية بالإنجليزية / College Name (EN)",
                    value=self.settings_data.get("college_name_en") or ""
                )

            # ── LOGO UPLOAD & PREVIEW SECTION ─────────────────────────────────
            with ui.column().classes("w-full gap-3 pt-3 border-t border-[var(--border-default)] mt-2"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("image", size="sm").classes("text-blue-400")
                    ui.label("شعارات المؤسسة والكلية — Official Logos").classes("font-bold text-sm app-text-primary")
                    ui.label("(يدعم ملفات الصور بصيغ PNG, JPG, WebP, SVG)").classes("text-xs app-text-muted")

                with ui.grid(columns=2).classes("w-full gap-4"):
                    # 1. University Logo Tile
                    with ui.column().classes("p-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-main)] gap-3"):
                        with ui.row().classes("items-center justify-between w-full"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("account_balance", size="xs").classes("text-blue-400")
                                ui.label("شعار الجامعة / University Logo").classes("font-semibold text-xs app-text-primary")
                            self.univ_logo_status = ui.label(os.path.basename(self.univ_logo_path) if self.univ_logo_path else "").classes("text-[10px] app-text-muted font-mono truncate max-w-[150px]")

                        with ui.row().classes("w-full items-center justify-center p-3 rounded-xl border border-dashed border-[var(--border-default)] min-h-[110px] bg-[var(--surface-card)]"):
                            univ_src = self.univ_logo_path if (self.univ_logo_path and os.path.exists(self.univ_logo_path)) else None
                            if univ_src:
                                self.univ_logo_img = ui.image(f"{univ_src}?t={datetime.now().timestamp()}").classes("max-h-24 max-w-[140px] object-contain")
                                self.univ_placeholder_col = ui.column().classes("items-center justify-center gap-1 hidden")
                            else:
                                self.univ_logo_img = ui.image("").classes("max-h-24 max-w-[140px] object-contain hidden")
                                self.univ_placeholder_col = ui.column().classes("items-center justify-center gap-1")
                                with self.univ_placeholder_col:
                                    ui.icon("account_balance", size="md").classes("app-text-muted opacity-40")
                                    ui.label("لا يوجد شعار محدد").classes("text-[11px] app-text-muted")

                        def _handle_univ_logo_upload(e):
                            try:
                                content = e.content.read() if hasattr(e, "content") else None
                                if not content:
                                    ui.notify("تعذر قراءة الصورة!", type="warning")
                                    return
                                ext = os.path.splitext(getattr(e, "name", "logo.png"))[1].lower()
                                if ext not in [".png", ".jpg", ".jpeg", ".webp", ".svg"]:
                                    ext = ".png"
                                os.makedirs("assets", exist_ok=True)
                                saved_path = f"assets/univ_logo{ext}"
                                with open(saved_path, "wb") as f_out:
                                    f_out.write(content)
                                self.univ_logo_path = saved_path
                                self.univ_logo_img.set_source(f"{saved_path}?t={datetime.now().timestamp()}")
                                self.univ_logo_img.classes(remove="hidden")
                                self.univ_placeholder_col.classes(add="hidden")
                                self.univ_logo_status.set_text(os.path.basename(saved_path))
                                ui.notify("تم استلام شعار الجامعة! اضغط على زر الحفظ بالأسفل لاعتماده.", type="positive")
                            except Exception as err:
                                ui.notify(f"خطأ في رفع الشعار: {err}", type="negative")

                        ui.upload(
                            label="اختر أو اسحب شعار الجامعة هنا",
                            auto_upload=True,
                            on_upload=_handle_univ_logo_upload
                        ).props("accept='image/png,image/jpeg,image/webp,image/svg+xml' max-files=1 flat dense").classes("w-full text-xs")

                    # 2. College Logo Tile
                    with ui.column().classes("p-4 rounded-xl border border-[var(--border-default)] bg-[var(--bg-main)] gap-3"):
                        with ui.row().classes("items-center justify-between w-full"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("school", size="xs").classes("text-emerald-400")
                                ui.label("شعار الكلية / College Logo").classes("font-semibold text-xs app-text-primary")
                            self.college_logo_status = ui.label(os.path.basename(self.college_logo_path) if self.college_logo_path else "").classes("text-[10px] app-text-muted font-mono truncate max-w-[150px]")

                        with ui.row().classes("w-full items-center justify-center p-3 rounded-xl border border-dashed border-[var(--border-default)] min-h-[110px] bg-[var(--surface-card)]"):
                            col_src = None
                            if self.college_logo_path and os.path.exists(self.college_logo_path):
                                col_src = self.college_logo_path
                            elif os.path.exists("csit.png"):
                                col_src = "csit.png"

                            if col_src:
                                self.college_logo_img = ui.image(f"{col_src}?t={datetime.now().timestamp()}").classes("max-h-24 max-w-[140px] object-contain")
                                self.college_placeholder_col = ui.column().classes("items-center justify-center gap-1 hidden")
                            else:
                                self.college_logo_img = ui.image("").classes("max-h-24 max-w-[140px] object-contain hidden")
                                self.college_placeholder_col = ui.column().classes("items-center justify-center gap-1")
                                with self.college_placeholder_col:
                                    ui.icon("school", size="md").classes("app-text-muted opacity-40")
                                    ui.label("لا يوجد شعار محدد").classes("text-[11px] app-text-muted")

                        def _handle_college_logo_upload(e):
                            try:
                                content = e.content.read() if hasattr(e, "content") else None
                                if not content:
                                    ui.notify("تعذر قراءة الصورة!", type="warning")
                                    return
                                ext = os.path.splitext(getattr(e, "name", "logo.png"))[1].lower()
                                if ext not in [".png", ".jpg", ".jpeg", ".webp", ".svg"]:
                                    ext = ".png"
                                os.makedirs("assets", exist_ok=True)
                                saved_path = f"assets/college_logo{ext}"
                                with open(saved_path, "wb") as f_out:
                                    f_out.write(content)
                                self.college_logo_path = saved_path
                                self.college_logo_img.set_source(f"{saved_path}?t={datetime.now().timestamp()}")
                                self.college_logo_img.classes(remove="hidden")
                                self.college_placeholder_col.classes(add="hidden")
                                self.college_logo_status.set_text(os.path.basename(saved_path))
                                ui.notify("تم استلام شعار الكلية! اضغط على زر الحفظ بالأسفل لاعتماده.", type="positive")
                            except Exception as err:
                                ui.notify(f"خطأ في رفع الشعار: {err}", type="negative")

                        ui.upload(
                            label="اختر أو اسحب شعار الكلية هنا",
                            auto_upload=True,
                            on_upload=_handle_college_logo_upload
                        ).props("accept='image/png,image/jpeg,image/webp,image/svg+xml' max-files=1 flat dense").classes("w-full text-xs")

            with ui.row().classes("w-full justify-end items-center pt-3 border-t border-[var(--border-default)] mt-2"):
                UI.success_button(
                    "حفظ معلومات المؤسسة والشعارات / Save Info & Logos",
                    icon="save",
                    on_click=self._save_institution_info
                ).classes("px-5 py-2 text-xs font-bold")

    def _section_study_systems(self) -> None:
        with UI.card():
            with ui.row().classes("w-full justify-between items-center pb-3 app-card-header"):
                UI.section_label("أنظمة الدراسة — Study Systems")
                ui.button("+ إضافة نظام", color=None, on_click=self._add_study_system).classes(
                    "app-btn-primary text-sm px-4 py-2 rounded-lg normal-case font-medium"
                )

            self._systems_container = ui.column().classes("w-full")
            self._render_systems_list()

    def _render_systems_list(self) -> None:
        """Renders a clean, minimal flat table for study systems — no decorative colors."""
        self._systems_container.clear()
        with self._systems_container:
            if not self.systems:
                ui.label("لا توجد أنظمة دراسية معرفة. / No study systems defined.").classes(
                    "app-text-muted text-sm italic py-4 px-2"
                )
                return

            cols = [
                {"name": "name",    "label": "System / النظام",         "field": "name",    "align": "left"},
                {"name": "rule",    "label": "Calc Rule",                "field": "rule",    "align": "center"},
                {"name": "display", "label": "Period",                   "field": "display", "align": "center"},
                {"name": "weights", "label": "Weights",                  "field": "weights", "align": "center"},
                {"name": "active",  "label": "Active",                   "field": "active",  "align": "center"},
                {"name": "actions", "label": "حذف / Delete",                     "field": "actions", "align": "right"},
            ]
            rows = [
                {
                    "id": s.get("id"),
                    "name": f"{s.get('name_ar', '')} / {s.get('name_en', '')}",
                    "rule": s.get("calculation_rule", "annual"),
                    "display": s.get("period_display", "year"),
                    "weights": s.get("calculation_weights", "—"),
                    "is_active": bool(s.get("is_active", 1)),
                }
                for s in self.systems
            ]

            table = (
                ui.table(columns=cols, rows=rows, row_key="id")
                .classes("w-full app-table")
                .props("flat dense separator='horizontal' hide-bottom")
            )

            table.add_slot('body-cell-active', '''
                <q-td :props="props" class="text-center">
                    <q-toggle
                        :model-value="props.row.is_active"
                        @update:model-value="(val) => $parent.$emit('toggle-active', {id: props.row.id, val: val})"
                        dense color="primary"
                    />
                </q-td>
            ''')
            table.add_slot('body-cell-actions', '''
                <q-td :props="props" class="text-right">
                    <q-btn
                        icon="delete"
                        flat round dense size="sm" color="negative"
                        @click="$parent.$emit('delete-system', props.row.id)"
                    />
                </q-td>
            ''')

            table.on('toggle-active', lambda e: self._toggle_system_active(e.args['id'], e.args['val']))
            table.on('delete-system', lambda e: self._delete_study_system(e.args))

    def _section_appearance(self) -> None:
        with UI.card():
            UI.card_header("المظهر والسمات — Appearance & Theme", "palette", icon_css="stat-text-purple")

            # Always read from session.preferences — it IS the source of truth after login.
            # The DB load in _load_data() already synced into session.preferences.
            pref = self.session.preferences
            saved_theme = str(pref.get("theme", "Dark")).strip().capitalize()
            if saved_theme not in ("System", "Light", "Dark"):
                saved_theme = "Dark"
            saved_accent = str(pref.get("accent_color", "blue")).lower().replace("_", "-")
            if saved_accent == "dark-blue":
                saved_accent = "blue"
            valid_accents = ["blue", "green", "orange", "purple", "red"]
            if saved_accent not in valid_accents:
                saved_accent = "blue"
            saved_font  = str(pref.get("font_family", "Segoe UI"))
            saved_size  = int(pref.get("font_size_base") or 14)
            saved_rtl   = int(pref.get("is_arabic_rtl", 1))

            with ui.grid(columns=2).classes("w-full gap-4"):
                self.theme_select = UI.select(
                    "الوضع (فاتح/داكن) / Theme Mode",
                    options=["System", "Light", "Dark"],
                    value=saved_theme,
                    on_change=self._on_theme_select_change
                )

                self.accent_select = UI.select(
                    "اللون الأساسي / Accent Color",
                    options=valid_accents,
                    value=saved_accent,
                    on_change=self._on_accent_select_change
                )

                self.font_select = UI.select(
                    "نوع الخط / Font Family",
                    options=["Arial", "Segoe UI", "Roboto", "Cairo", "Tahoma", "Noto Sans Arabic", "times new roman"],
                    value=saved_font,
                    on_change=self._on_font_select_change
                )

                self.font_size_input = UI.number_input(
                    "حجم الخط الأساسي / Base Font Size",
                    value=saved_size, min=10, max=24,
                    on_change=self._on_font_size_change
                )

            with ui.row().classes("app-tile w-full items-center justify-between p-3 rounded-xl border"):
                UI.standard_label("اتجاه الواجهة من اليمين إلى اليسار / Arabic RTL Layout")
                self.rtl_switch = UI.switch("تفعيل RTL / Enable RTL", value=bool(saved_rtl), on_change=self._on_rtl_switch_change)

            UI.success_button(
                "حفظ وتطبيق المظهر / Save Appearance",
                icon="brush",
                on_click=self._save_appearance
            ).classes("self-end")

    # ─────────────────────────────────────────────────────────────────────────
    # Printers & Hardware Setup Section (Replaces legacy Profile & Account tab)
    # ─────────────────────────────────────────────────────────────────────────

    def _load_printer_config(self) -> dict:
        """Loads persistent printer setup from config/printer_config.json."""
        from nicegui_screens.certificate_screen import get_default_printer
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "printer_config.json")
        def_p = get_default_printer()
        default_cfg = {
            "cert_printer": def_p,
            "report_printer": def_p,
            "paper_size": "A4",
            "orientation": "Portrait",
            "auto_print": False,
            "copies": 1
        }
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        default_cfg.update(data)
            except Exception:
                pass
        return default_cfg

    def _save_printer_config_file(self, cfg: dict) -> bool:
        """Saves printer setup to config/printer_config.json."""
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "printer_config.json")
        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            log.error(f"Error saving printer config: {e}")
            return False

    def _send_printer_test_page(self, printer_name: str) -> tuple[bool, str]:
        """Sends a formatted Windows GDI test page directly to the specified printer."""
        try:
            import win32ui
            import win32con
            from datetime import datetime

            dc = win32ui.CreateDC()
            dc.CreatePrinterDC(printer_name)
            dc.StartDoc("Certificate Manager Test Page")
            dc.StartPage()

            font_title = win32ui.CreateFont({
                "name": "Segoe UI",
                "height": 55,
                "weight": win32con.FW_BOLD
            })
            dc.SelectObject(font_title)
            dc.TextOut(120, 120, "Certificate Manager — Printer Test Page")

            font_body = win32ui.CreateFont({
                "name": "Segoe UI",
                "height": 35,
                "weight": win32con.FW_NORMAL
            })
            dc.SelectObject(font_body)
            dc.TextOut(120, 220, f"Target Printer: {printer_name}")
            dc.TextOut(120, 280, f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            dc.TextOut(120, 340, "Status: Printer communication test PASSED successfully.")
            dc.TextOut(120, 400, "Institution: College of Computer Science & Information Technology")
            dc.TextOut(120, 460, "System: Certificate Manager (NiceGUI Enterprise Suite)")

            dc.EndPage()
            dc.EndDoc()
            dc.DeleteDC()
            return True, "Success"
        except Exception as exc:
            return False, str(exc)

    def _section_printer_settings(self) -> None:
        """
        Renders the dedicated Printer Setup & Hardware Configuration View.
        Configures certificate printer, reports printer, page size, orientation,
        and provides direct test printing and setting Windows default printer.
        """
        from nicegui_screens.certificate_screen import get_installed_printers, get_default_printer

        installed_printers = get_installed_printers()
        default_win_printer = get_default_printer()
        cfg = self._load_printer_config()

        cur_cert_printer = cfg.get("cert_printer") or default_win_printer
        if cur_cert_printer not in installed_printers and installed_printers:
            cur_cert_printer = default_win_printer if default_win_printer in installed_printers else installed_printers[0]

        cur_report_printer = cfg.get("report_printer") or default_win_printer
        if cur_report_printer not in installed_printers and installed_printers:
            cur_report_printer = default_win_printer if default_win_printer in installed_printers else installed_printers[0]

        cur_paper = cfg.get("paper_size", "A4")
        if cur_paper not in ["A4", "Letter", "A3", "Legal"]:
            cur_paper = "A4"

        cur_orientation = cfg.get("orientation", "Portrait")
        if cur_orientation not in ["Portrait", "Landscape"]:
            cur_orientation = "Portrait"

        cur_auto_print = bool(cfg.get("auto_print", False))
        cur_copies = int(cfg.get("copies", 1))

        with UI.card().classes("w-full p-6 gap-6"):
            UI.card_header("إعداد وتهيئة الطابعات — Printer & Hardware Setup", "print", icon_css="stat-text-blue")

            # Status Banner & Current Default
            with ui.row().classes("w-full items-center justify-between p-4 bg-[var(--bg-main)] rounded-2xl border border-[var(--border-default)] flex-wrap gap-4"):
                with ui.row().classes("items-center gap-3"):
                    with ui.element("div").classes("w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-center shrink-0"):
                        ui.icon("print", size="md").classes("text-blue-400")
                    with ui.column().classes("gap-0"):
                        ui.label("إدارة وتوجيه الطابعات المادية والافتراضية").classes("font-bold text-sm app-text-primary")
                        ui.label(f"الطابعة الافتراضية في Windows حالياً: {default_win_printer}").classes("text-xs app-text-muted font-mono")

                with ui.row().classes("items-center gap-2"):
                    ui.label(f"عدد الطابعات المكتشفة: {len(installed_printers)}").classes("text-xs font-semibold px-2.5 py-1 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20")

            # Form Fields Grid
            with ui.grid(columns=2).classes("w-full gap-5"):
                # 1. Certificate Printer
                cert_printer_select = UI.select(
                    "طابعة الوثائق والشهادات / Certificate Printer",
                    options={p: p for p in installed_printers},
                    value=cur_cert_printer
                ).classes("w-full")

                # 2. Report Printer
                report_printer_select = UI.select(
                    "طابعة التقارير والجداول / Reports & Lists Printer",
                    options={p: p for p in installed_printers},
                    value=cur_report_printer
                ).classes("w-full")

                # 3. Paper Size
                paper_size_select = UI.select(
                    "حجم الورق الافتراضي / Default Paper Size",
                    options=["A4", "Letter", "A3", "Legal"],
                    value=cur_paper
                ).classes("w-full")

                # 4. Orientation
                orientation_select = UI.select(
                    "اتجاه الطباعة / Print Orientation",
                    options=["Portrait", "Landscape"],
                    value=cur_orientation
                ).classes("w-full")

                # 5. Default Copies
                copies_input = UI.number_input(
                    "عدد النسخ الافتراضي / Default Copies",
                    value=cur_copies, min=1, max=10
                ).classes("w-full")

            # Automation & Options
            with ui.row().classes("app-tile w-full items-center justify-between p-4 rounded-xl border border-[var(--border-default)] mt-2"):
                with ui.column().classes("gap-0.5"):
                    ui.label("طباعة فورية تلقائية / Auto-print immediately").classes("text-sm font-bold app-text-primary")
                    ui.label("إرسال الوثيقة للطباعة فور اكتمال توليدها دون طلب تأكيد يدوي").classes("text-xs app-text-muted")
                auto_print_switch = UI.switch("", value=cur_auto_print)

            # Action Buttons Row
            with ui.row().classes("w-full items-center justify-between pt-4 border-t border-[var(--border-default)] flex-wrap gap-3"):
                with ui.row().classes("items-center gap-2 flex-wrap"):
                    # Test Print Button
                    def do_test_print():
                        target_p = cert_printer_select.value
                        if not target_p:
                            UI.notify("الرجاء اختيار طابعة للفحص أولاً", type="warning")
                            return
                        success, msg = self._send_printer_test_page(target_p)
                        if success:
                            UI.notify(f"تم إرسال صفحة الفحص بنجاح إلى ({target_p})", type="positive")
                        else:
                            UI.notify(f"تعذر إرسال صفحة الفحص: {msg}", type="negative")

                    UI.secondary_button(
                        "طباعة صفحة فحص / Test Print",
                        icon="receipt_long",
                        on_click=do_test_print
                    ).classes("text-xs")

                    # Set Windows Default
                    def do_set_win_default():
                        target_p = cert_printer_select.value
                        if not target_p:
                            UI.notify("الرجاء اختيار طابعة أولاً", type="warning")
                            return
                        try:
                            import win32print
                            win32print.SetDefaultPrinter(target_p)
                            UI.notify(f"تم تعيين ({target_p}) كطابعة افتراضية للنظام بنجاح!", type="positive")
                        except Exception as ex:
                            UI.notify(f"فشل تعيين الطابعة الافتراضية: {ex}", type="negative")

                    UI.secondary_button(
                        "تعيين كافتراضية في النظام / Set as Windows Default",
                        icon="star",
                        on_click=do_set_win_default
                    ).classes("text-xs")

                # Save Configuration Button
                def do_save_printer_cfg():
                    new_cfg = {
                        "cert_printer": cert_printer_select.value or "",
                        "report_printer": report_printer_select.value or "",
                        "paper_size": paper_size_select.value or "A4",
                        "orientation": orientation_select.value or "Portrait",
                        "auto_print": bool(auto_print_switch.value),
                        "copies": int(copies_input.value or 1)
                    }
                    if self._save_printer_config_file(new_cfg):
                        UI.notify("تم حفظ إعدادات الطابعات بنجاح!", type="positive")
                    else:
                        UI.notify("فشل حفظ إعدادات الطابعات!", type="negative")

                UI.success_button(
                    "حفظ إعدادات الطابعات / Save Printer Settings",
                    icon="save",
                    on_click=do_save_printer_cfg
                ).classes("text-sm px-6 py-2.5 font-bold shadow-md")

    def _section_roles_and_permissions(self) -> None:
        """
        Renders the comprehensive Role-Based Access Control (RBAC) / Responsibility Management View.
        Uses full-page sub-view transitions (overview, edit_role, user_matrix) with NO popups!
        """
        @ui.refreshable
        def render_roles_container():
            if self.roles_subview_mode == "edit_role":
                self._render_full_page_role_editor()
            elif self.roles_subview_mode == "user_matrix":
                self._render_full_page_user_matrix()
            else:
                self._render_roles_overview()

        render_roles_container()
        self._render_roles_container = render_roles_container

    def _refresh_roles_section(self) -> None:
        """Refreshes the dynamic roles subview container."""
        if hasattr(self, '_render_roles_container') and self._render_roles_container:
            self._render_roles_container.refresh()

    def _open_role_editor_view(self, role_data=None) -> None:
        """Switches to the full-page Role Editor sub-view."""
        self.editing_role_data = role_data
        self.roles_subview_mode = "edit_role"
        self._refresh_roles_section()

    def _open_user_matrix_view(self, target_user_id=None) -> None:
        """Switches to the full-page User Permissions Matrix sub-view."""
        self.target_matrix_user_id = target_user_id
        self.roles_subview_mode = "user_matrix"
        self._refresh_roles_section()

    def _return_to_roles_overview(self) -> None:
        """Returns to the overview list of roles."""
        self.roles_subview_mode = "overview"
        self.editing_role_data = None
        self.target_matrix_user_id = None
        self._refresh_roles_section()

    # ─────────────────────────────────────────────────────────────────────────
    # Sub-View 1: Roles Overview Grid
    # ─────────────────────────────────────────────────────────────────────────

    def _render_roles_overview(self) -> None:
        with UI.card().classes("w-full p-6 gap-6"):
            UI.card_header("إدارة الأدوار والمسؤوليات والصلاحيات — Roles & Permissions Matrix", "admin_panel_settings", icon_css="stat-text-emerald")

            # Header Banner & Action Buttons
            with ui.row().classes("w-full items-center justify-between p-4 bg-[var(--bg-main)] rounded-2xl border border-[var(--border-default)] flex-wrap gap-4"):
                with ui.row().classes("items-center gap-3"):
                    with ui.element("div").classes("w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center shrink-0"):
                        ui.icon("shield", size="md").classes("text-emerald-400")
                    with ui.column().classes("gap-0"):
                        ui.label("لوحة التحكم بالمسؤوليات والصلاحيات (RBAC Profiles)").classes("font-bold text-sm app-text-primary")
                        ui.label("تحديد المسؤوليات والأدوار في الكلية وضبط إمكانية الوصول إلى الشاشات والإجراءات والأقسام لكل دور.").classes("text-xs app-text-muted")

                with ui.row().classes("items-center gap-2 flex-wrap"):
                    if self.on_navigate:
                        UI.secondary_button(
                            "شاشة الكوادر / Personnel Screen",
                            icon="group",
                            on_click=lambda: self.on_navigate("personnel")
                        ).classes("text-xs")

                    UI.secondary_button(
                        "تخصيص مستخدم / User Matrix",
                        icon="tune",
                        on_click=lambda: self._open_user_matrix_view()
                    ).classes("text-xs px-3 py-1.5")

                    UI.success_button(
                        "+ إضافة دور / مسؤولية جديدة",
                        icon="add_moderator",
                        on_click=lambda: self._open_role_editor_view(None)
                    ).classes("text-xs px-4 py-2 font-bold")

            # Roles Grid Display
            roles_list = []
            try:
                roles_list = self.role_repo.get_all() or []
            except Exception as e:
                log.warning(f"Failed to fetch roles: {e}")

            personnel_list = []
            try:
                personnel_list = self.p_repo.get_all() or []
            except Exception:
                pass

            page_names = {
                "home": "الرئيسية",
                "students": "الطلاب",
                "orders": "أوامر التخرج",
                "departments": "الأقسام",
                "courses": "المقررات",
                "personnel": "الكوادر",
                "certificate": "الوثائق",
                "issued_certs": "السجل",
                "settings": "الإعدادات",
                "history": "التغييرات"
            }

            all_perms_count = 29

            if not roles_list:
                with ui.column().classes("w-full items-center py-8 text-center bg-[var(--bg-main)] rounded-2xl border border-[var(--border-default)]"):
                    ui.icon("shield_off", size="lg").classes("app-text-muted mb-2")
                    ui.label("لا توجد أدوار مسجلة حالياً").classes("text-sm font-bold app-text-muted")
                return

            # Pre-compute personnel role mappings once to eliminate loop queries and HTTP hits
            personnel_role_map = {}
            for p in personnel_list:
                p_id = p.get("id")
                if p_id:
                    personnel_role_map[p_id] = self.role_repo.get_user_role_id(p_id, user_dict=p)

            with ui.grid(columns=2).classes("w-full gap-4 mt-2"):
                for role in roles_list:
                    role_id = role.get("id")
                    r_name_ar = role.get("name_ar") or role_id
                    r_name_en = role.get("name_en") or role_id
                    desc_ar = role.get("description_ar") or ""
                    allowed_pages = role.get("allowed_pages") or []
                    allowed_actions = role.get("allowed_actions") or []
                    dept_scope = role.get("department_scope") or "all"
                    is_sys = bool(role.get("is_system"))

                    matched_users = [
                        p for p in personnel_list
                        if (personnel_role_map.get(p.get("id")) == role_id or p.get("responsibility_ar") == r_name_ar or p.get("personnel_role") == role_id)
                    ]
                    user_count = len(matched_users)

                    with ui.column().classes(
                        "w-full p-4 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-main)] "
                        "hover:border-emerald-500/40 transition-all gap-3 shadow-sm"
                    ):
                        # Card Top Row: Name + Badges + Edit/Delete
                        with ui.row().classes("w-full items-start justify-between gap-2"):
                            with ui.row().classes("items-center gap-2.5 min-w-0 flex-1"):
                                with ui.element("div").classes("w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center shrink-0"):
                                    ui.icon("verified_user" if is_sys else "shield", size="sm").classes("text-blue-400")
                                with ui.column().classes("gap-0 min-w-0 flex-1"):
                                    with ui.row().classes("items-center gap-2 flex-wrap"):
                                        ui.label(r_name_ar).classes("text-sm font-bold app-text-primary")
                                        if is_sys:
                                            ui.label("افتراضي / Built-in").classes("text-[10px] px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400 font-semibold border border-blue-500/30")
                                        else:
                                            ui.label("مخصص / Custom").classes("text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 font-semibold border border-emerald-500/30")
                                    ui.label(r_name_en).classes("text-xs app-text-muted font-mono")

                            with ui.row().classes("items-center gap-1 shrink-0"):
                                ui.button(
                                    icon="edit",
                                    on_click=lambda r=role: self._open_role_editor_view(r)
                                ).props("flat round dense size=sm color=primary").tooltip("تعديل هذا الدور والصلاحيات / Edit Role (Full Page)")

                                if not is_sys:
                                    def _confirm_delete_role(rid=role_id, rname=r_name_ar):
                                        del_dlg = ui.dialog()
                                        with del_dlg, UI.card().classes("p-6 gap-4 w-96 rounded-2xl bg-[var(--surface-card)] border border-[var(--border-default)] shadow-2xl"):
                                            ui.label("تأكيد حذف الدور — Confirm Delete").classes("text-base font-bold text-red-400")
                                            ui.label(f"هل أنت متأكد من حذف الدور المخصص ({rname}) نهائياً؟").classes("text-xs app-text-muted leading-relaxed")
                                            with ui.row().classes("w-full justify-end gap-2 pt-2"):
                                                UI.ghost_button("إلغاء / Cancel", on_click=del_dlg.close).classes("text-xs")
                                                def _do_del():
                                                    try:
                                                        self.role_repo.delete_role(rid)
                                                        ui.notify(f"تم حذف الدور ({rname}) بنجاح", type="positive")
                                                        del_dlg.close()
                                                        self._refresh_roles_section()
                                                    except Exception as exc:
                                                        ui.notify(f"خطأ أثناء حذف الدور: {exc}", type="negative")
                                                UI.danger_button("تأكيد الحذف", icon="delete", on_click=_do_del).classes("text-xs")
                                        del_dlg.open()

                                    ui.button(
                                        icon="delete",
                                        on_click=_confirm_delete_role
                                    ).props("flat round dense size=sm color=negative").tooltip("حذف هذا الدور المخصص / Delete Role")

                        if desc_ar:
                            ui.label(desc_ar).classes("text-xs app-text-muted leading-relaxed")

                        # Details Stats & Badges Grid
                        with ui.column().classes("w-full gap-2 pt-2 border-t border-[var(--border-default)]"):
                            # 1. Allowed Pages Badges
                            with ui.row().classes("w-full items-center gap-1.5 flex-wrap"):
                                ui.label("الشاشات:").classes("text-[11px] font-bold app-text-muted shrink-0")
                                if len(allowed_pages) >= 9:
                                    ui.label("كافة الشاشات (Full Page Access)").classes("text-[10px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-semibold")
                                elif not allowed_pages:
                                    ui.label("لا توجد شاشات").classes("text-[10px] px-2 py-0.5 rounded bg-red-500/10 text-red-400")
                                else:
                                    for pkey in allowed_pages[:5]:
                                        ui.label(page_names.get(pkey, pkey)).classes("text-[10px] px-2 py-0.5 rounded bg-[var(--surface-card)] border border-[var(--border-default)] app-text-primary")
                                    if len(allowed_pages) > 5:
                                        ui.label(f"+{len(allowed_pages)-5} أخرى").classes("text-[10px] px-1.5 py-0.5 rounded bg-slate-500/10 text-slate-400")

                            # 2. Allowed Permissions & Departments Row
                            with ui.row().classes("w-full items-center justify-between text-xs pt-1"):
                                with ui.row().classes("items-center gap-1"):
                                    ui.icon("check_circle", size="xs").classes("text-emerald-400")
                                    ui.label(f"الصلاحيات: {len(allowed_actions)} من {all_perms_count}").classes("font-semibold app-text-primary text-[11px]")

                                with ui.row().classes("items-center gap-1"):
                                    ui.icon("domain", size="xs").classes("text-purple-400")
                                    dept_label = "كافة الأقسام" if (dept_scope == "all" or not dept_scope) else "أقسام مخصصة"
                                    ui.label(f"الأقسام: {dept_label}").classes("font-semibold app-text-muted text-[11px]")

                                with ui.row().classes("items-center gap-1"):
                                    ui.icon("people", size="xs").classes("text-blue-400")
                                    ui.label(f"الكوادر: {user_count}").classes("font-semibold app-text-muted text-[11px]")

    # ─────────────────────────────────────────────────────────────────────────
    # Sub-View 2: Dedicated Full-Page Role Editor (NO POPUP MODAL)
    # ─────────────────────────────────────────────────────────────────────────

    def _render_full_page_role_editor(self) -> None:
        import json
        is_edit = self.editing_role_data is not None
        initial_data = self.editing_role_data or {}
        r_id = initial_data.get("id") or ""
        is_sys = bool(initial_data.get("is_system", 0))

        all_perms = []
        try:
            all_perms = self.perm_repo.get_all() or []
        except Exception:
            pass

        all_depts = []
        try:
            all_depts = self.dept_repo.get_all() or []
        except Exception:
            pass

        with UI.card().classes("w-full p-6 gap-6"):
            # Sticky/Prominent Top Navigation Bar
            with ui.row().classes("w-full items-center justify-between pb-4 border-b border-[var(--border-default)] shrink-0 gap-4 flex-wrap"):
                with ui.row().classes("items-center gap-3"):
                    UI.secondary_button(
                        "← العودة لقائمة الأدوار / Back to Roles",
                        icon="arrow_forward",
                        on_click=self._return_to_roles_overview
                    ).classes("text-xs px-4 py-2 font-bold shadow-sm")

                    with ui.element("div").classes("w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-center"):
                        ui.icon("admin_panel_settings", size="sm").classes("text-blue-400")

                    with ui.column().classes("gap-0"):
                        title_lbl = f"تعديل الدور: {initial_data.get('name_ar', '')}" if is_edit else "إنشاء دور / مسؤولية جديدة — Create Role Profile"
                        ui.label(title_lbl).classes("text-base font-bold app-text-primary")
                        ui.label("تحديد صلاحيات الوصول إلى الشاشات والإجراءات والأقسام لهذا الدور بالتفصيل.").classes("text-xs app-text-muted")

                with ui.row().classes("items-center gap-2"):
                    UI.ghost_button("إلغاء / Cancel", on_click=self._return_to_roles_overview).classes("text-xs px-3 py-2")
                    save_btn_top = UI.success_button(
                        "حفظ الدور والصلاحيات / Save Role",
                        icon="check_circle",
                        on_click=lambda: _save_role()
                    ).classes("text-xs px-5 py-2 font-bold shadow-md")

            # Form Body: Full-Width Structured Cards
            with ui.column().classes("w-full gap-6"):

                # ── 1. Basic Role Information ─────────────────────────────────
                with UI.card().classes("p-5 gap-4 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-main)]"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("badge", size="sm").classes("text-blue-400")
                        ui.label("المعلومات الأساسية للدور — Role Details").classes("text-sm font-bold text-blue-400")

                    with ui.grid(columns=2).classes("w-full gap-4"):
                        name_ar_input = UI.text_input("اسم الدور / المسؤولية (بالعربية) *", value=initial_data.get("name_ar", ""))
                        name_en_input = UI.text_input("اسم الدور / المسؤولية (بالإنكليزية) *", value=initial_data.get("name_en", ""))

                    desc_ar_input = UI.text_input("وصف الدور والمهام / Description", value=initial_data.get("description_ar", "")).classes("w-full")

                # ── 2. Department Accessibility Scope (Granular Catalog Access) ─
                with UI.card().classes("p-5 gap-4 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-main)]"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("domain", size="sm").classes("text-amber-400")
                            ui.label("نطاق الأقسام المسموح بالوصول إليها — Department Accessibility Scope").classes("text-sm font-bold text-amber-400")
                        ui.label("تحكم بالأقسام التي يستطيع هذا الدور الاطلاع على طلبتها ومقرراتها").classes("text-xs app-text-muted")

                    init_scope = initial_data.get("department_scope") or "all"
                    is_all_depts = (init_scope == "all" or not init_scope)

                    dept_radio = ui.radio(
                        {"all": "كافة الأقسام العلمية (All Departments)", "specific": "أقسام محددة فقط (Specific Departments Only)"},
                        value="all" if is_all_depts else "specific"
                    ).props("inline dense").classes("text-xs font-bold app-text-primary")

                    dept_checkboxes = {}
                    dept_boxes_wrapper = ui.column().classes("w-full gap-3 pt-2")
                    with dept_boxes_wrapper:
                        parsed_scope = []
                        if not is_all_depts and isinstance(init_scope, str):
                            try:
                                parsed_scope = json.loads(init_scope)
                            except Exception:
                                parsed_scope = [int(x) for x in init_scope.split(",") if x.strip().isdigit()]
                        elif isinstance(init_scope, list):
                            parsed_scope = init_scope

                        with ui.row().classes("w-full justify-between items-center pb-1 border-b border-[var(--border-default)]"):
                            ui.label("حدد الأقسام المتاحة لهذا الدور:").classes("text-xs font-bold app-text-primary")
                            with ui.row().classes("gap-2"):
                                def _sel_all_depts():
                                    for dcb in dept_checkboxes.values():
                                        dcb.value = True
                                def _clr_all_depts():
                                    for dcb in dept_checkboxes.values():
                                        dcb.value = False
                                UI.ghost_button("تحديد كافة الأقسام", icon="select_all", on_click=_sel_all_depts).classes("text-xs px-2 py-1")
                                UI.ghost_button("إلغاء الكل", icon="clear_all", on_click=_clr_all_depts).classes("text-xs px-2 py-1")

                        with ui.grid(columns=3).classes("w-full gap-3"):
                            for d in all_depts:
                                did = d["id"]
                                dname = d.get("name_ar") or d.get("name_en") or f"قسم {did}"
                                dcode = d.get("code") or ""
                                label_text = f"{dname} ({dcode})" if dcode else dname
                                dcb = ui.checkbox(label_text, value=(did in parsed_scope or str(did) in parsed_scope)).classes("text-xs")
                                dept_checkboxes[did] = dcb

                    def _on_scope_toggle(val):
                        v = val.value if hasattr(val, "value") else val
                        dept_boxes_wrapper.set_visibility(v == "specific")

                    dept_radio.on_value_change(_on_scope_toggle)
                    dept_boxes_wrapper.set_visibility(not is_all_depts)

                # ── 3. Page Accessibility ─────────────────────────────────────
                with UI.card().classes("p-5 gap-4 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-main)]"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("layers", size="sm").classes("text-purple-400")
                            ui.label("الشاشات والصفحات المتاح الوصول إليها — Accessible Pages").classes("text-sm font-bold text-purple-400")
                        with ui.row().classes("gap-2"):
                            def _select_all_pages():
                                for cb in page_checkboxes.values():
                                    cb.value = True
                            def _clear_all_pages():
                                for cb in page_checkboxes.values():
                                    cb.value = False
                            UI.ghost_button("تحديد كافة الشاشات", icon="select_all", on_click=_select_all_pages).classes("text-xs px-2.5 py-1")
                            UI.ghost_button("إلغاء الكل", icon="clear_all", on_click=_clear_all_pages).classes("text-xs px-2.5 py-1")

                    all_pages_map = {
                        "home": ("الرئيسية / Dashboard", "home"),
                        "students": ("إدارة الطلاب والدرجات / Students", "school"),
                        "orders": ("أوامر التخرج / Orders", "history_edu"),
                        "departments": ("إدارة الأقسام / Departments", "domain"),
                        "courses": ("المواد الدراسية / Courses", "menu_book"),
                        "personnel": ("إدارة الكوادر / Personnel", "group"),
                        "certificate": ("إصدار الوثيقة / Certificates", "print"),
                        "issued_certs": ("سجل الوثائق الصادرة / Log", "list_alt"),
                        "settings": ("إعدادات النظام / Settings", "settings"),
                        "history": ("سجل النشاط والتغييرات / History", "history"),
                    }

                    current_pages = set(initial_data.get("allowed_pages") or [])
                    if not is_edit and not current_pages:
                        current_pages = {"home", "students", "orders", "certificate", "issued_certs"}

                    page_checkboxes = {}
                    with ui.grid(columns=3).classes("w-full gap-3"):
                        for p_key, (p_title, p_icon) in all_pages_map.items():
                            with ui.row().classes("items-center justify-between p-3 rounded-xl border border-[var(--border-default)] bg-[var(--surface-card)] hover:border-purple-500/30 transition-all"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon(p_icon, size="xs").classes("text-purple-400")
                                    ui.label(p_title).classes("text-xs font-semibold app-text-primary")
                                cb = ui.checkbox(value=(p_key in current_pages))
                                page_checkboxes[p_key] = cb

                # ── 4. Granular Action Permissions (The Complete Catalog) ─────
                with UI.card().classes("p-5 gap-4 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-main)]"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("verified_user", size="sm").classes("text-emerald-400")
                            ui.label("صلاحيات الإجراءات والعمليات المفصلة — Granular Action Permissions").classes("text-sm font-bold text-emerald-400")
                        with ui.row().classes("gap-2"):
                            def _grant_all_acts():
                                for sw in action_switches.values():
                                    sw.value = True
                            def _clear_all_acts():
                                for sw in action_switches.values():
                                    sw.value = False
                            UI.ghost_button("تحديد كافة الصلاحيات", icon="select_all", on_click=_grant_all_acts).classes("text-xs px-2.5 py-1")
                            UI.ghost_button("إلغاء الكل", icon="clear_all", on_click=_clear_all_acts).classes("text-xs px-2.5 py-1")

                    # 8 Distinct, Comprehensive Categories
                    categories = {
                        "students": {
                            "title": "🎓 شؤون الطلاب والدرجات — Students & Grades",
                            "color": "text-blue-400",
                            "desc": "صلاحيات الاطلاع والإضافة والتعديل والحذف وإدارة درجات الطلبة"
                        },
                        "orders": {
                            "title": "📜 أوامر التخرج — Graduation Orders",
                            "color": "text-purple-400",
                            "desc": "صلاحيات استعراض وإنشاء وتعديل وحذف أوامر التخرج وربط الطلبة"
                        },
                        "certificates": {
                            "title": "🖨️ إصدار الوثائق الرسمية — Issue Certificates",
                            "color": "text-emerald-400",
                            "desc": "صلاحية توليد وتعيين أرقام وثائق التخرج الرسمية وطباعتها"
                        },
                        "issued_certs": {
                            "title": "📋 سجل الوثائق الصادرة — Issued Records & Logs",
                            "color": "text-teal-400",
                            "desc": "صلاحيات البحث في الأرشيف وتصدير السجلات وحذف القيود الصادرة"
                        },
                        "departments": {
                            "title": "🏢 إدارة الأقسام العلمية — Departments Management",
                            "color": "text-amber-400",
                            "desc": "صلاحيات استعراض وإضافة وتعديل وحذف الأقسام العلمية والتخصصات"
                        },
                        "courses": {
                            "title": "📚 المقررات والمناهج الدراسية — Courses Catalog",
                            "color": "text-indigo-400",
                            "desc": "صلاحيات عرض وإضافة وتعديل وحذف المواد الدراسية وتعيين ساعاتها ووحداتها"
                        },
                        "personnel": {
                            "title": "👥 الكوادر والمستخدمين — Personnel & Accounts",
                            "color": "text-orange-400",
                            "desc": "صلاحيات عرض ملفات الكوادر وإدارة الحسابات وتعيين الأدوار"
                        },
                        "settings": {
                            "title": "⚙️ إعدادات النظام — System Settings Views & Alter",
                            "color": "text-cyan-400",
                            "desc": "صلاحيات الوصول وتعديل كل شاشة من شاشات إعدادات النظام بشكل منفصل"
                        },
                    }

                    action_switches = {}
                    current_actions = set(initial_data.get("allowed_actions") or [])

                    # Backward compatibility mapping for legacy catalog:manage ONLY if no granular permissions exist
                    has_granular_catalog = any(k.startswith("departments:") or k.startswith("courses:") for k in current_actions)
                    if "catalog:manage" in current_actions and not has_granular_catalog:
                        for k in ["departments:view", "departments:create", "departments:edit", "departments:delete",
                                  "courses:view", "courses:create", "courses:edit", "courses:delete"]:
                            current_actions.add(k)

                    has_granular_settings = any(k.startswith("settings:") and k not in ("settings:manage", "settings:view") for k in current_actions)
                    if "settings:manage" in current_actions and not has_granular_settings:
                        for k in ["settings:institution", "settings:study_systems", "settings:appearance",
                                  "settings:templates", "settings:logs"]:
                            current_actions.add(k)

                    with ui.column().classes("w-full gap-5 pt-1"):
                        for cat_key, cat_meta in categories.items():
                            cat_perms = [p for p in all_perms if p.get("category") == cat_key and p.get("permission_key") in ALL_PERMISSION_KEYS]
                            if not cat_perms:
                                continue

                            with ui.column().classes("w-full p-4 rounded-xl border border-[var(--border-default)] bg-[var(--surface-card)] gap-3"):
                                with ui.row().classes("w-full justify-between items-center"):
                                    with ui.column().classes("gap-0"):
                                        ui.label(cat_meta["title"]).classes(f"font-bold text-xs {cat_meta['color']}")
                                        ui.label(cat_meta["desc"]).classes("text-[10px] app-text-muted")

                                    # Category quick select/clear
                                    def _make_cat_toggles(cp_list=cat_perms):
                                        def _sel():
                                            for p in cp_list:
                                                if p["permission_key"] in action_switches:
                                                    action_switches[p["permission_key"]].value = True
                                        def _clr():
                                            for p in cp_list:
                                                if p["permission_key"] in action_switches:
                                                    action_switches[p["permission_key"]].value = False
                                        return _sel, _clr

                                    sel_fn, clr_fn = _make_cat_toggles(cat_perms)
                                    with ui.row().classes("gap-1"):
                                        UI.ghost_button("الكل", icon="done_all", on_click=sel_fn).classes("text-[10px] px-1.5 py-0.5")
                                        UI.ghost_button("مسح", icon="remove_done", on_click=clr_fn).classes("text-[10px] px-1.5 py-0.5")

                                with ui.grid(columns=2).classes("w-full gap-3 pt-1"):
                                    for perm in cat_perms:
                                        pkey = perm["permission_key"]
                                        pname_ar = perm.get("name_ar") or pkey
                                        pname_en = perm.get("name_en") or pkey
                                        pdesc = perm.get("description_ar") or ""

                                        with ui.row().classes("items-center justify-between p-2.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-main)] hover:border-emerald-500/30 transition-all"):
                                            with ui.column().classes("gap-0 min-w-0 flex-1"):
                                                ui.label(f"{pname_ar} / {pname_en}").classes("text-xs font-bold app-text-primary truncate")
                                                if pdesc:
                                                    ui.label(pdesc).classes("text-[10px] app-text-muted line-clamp-1")
                                            sw = ui.switch(value=(pkey in current_actions)).props("dense size=sm color=positive")
                                            action_switches[pkey] = sw

            # Sticky / Bottom Action Bar
            with ui.row().classes("w-full items-center justify-between pt-6 border-t border-[var(--border-default)] mt-4"):
                UI.secondary_button("← إلغاء والعودة لقائمة الأدوار", on_click=self._return_to_roles_overview).classes("text-xs px-4 py-2")

                def _save_role():
                    nar = (name_ar_input.value or "").strip()
                    nen = (name_en_input.value or "").strip()
                    if not nar:
                        ui.notify("يرجى إدخال اسم الدور / المسؤولية بالعربية!", type="warning")
                        return
                    if not nen:
                        nen = nar

                    sel_pages = [pk for pk, cb in page_checkboxes.items() if cb.value]
                    sel_actions = [ak for ak, sw in action_switches.items() if sw.value and ak in ALL_PERMISSION_KEYS]

                    scope_val = "all"
                    if dept_radio.value == "specific":
                        chosen_depts = [did for did, dcb in dept_checkboxes.items() if dcb.value]
                        scope_val = json.dumps(chosen_depts) if chosen_depts else "all"

                    # Determine assigned slug ID
                    assigned_id = r_id
                    if not assigned_id:
                        import re
                        slug_base = re.sub(r'[^a-zA-Z0-9_]', '_', nen.strip().lower()).strip('_')
                        if not slug_base:
                            slug_base = f"role_{int(datetime.now().timestamp()) % 100000}"
                        # Check collision if adding a new role
                        existing = self.role_repo.get_by_id(slug_base)
                        if existing:
                            slug_base = f"{slug_base}_{int(datetime.now().timestamp()) % 10000}"
                        assigned_id = slug_base

                    existing_base = initial_data.get("base_role") if is_edit else None
                    base_role_val = existing_base or ("admin" if assigned_id == "admin" else "user")

                    payload = {
                        "id": assigned_id,
                        "name_ar": nar,
                        "name_en": nen,
                        "description_ar": (desc_ar_input.value or "").strip(),
                        "base_role": base_role_val,
                        "allowed_pages": sel_pages,
                        "allowed_actions": sel_actions,
                        "department_scope": scope_val,
                        "is_system": 1 if is_sys else 0
                    }

                    try:
                        self.role_repo.save_role(payload)
                        ui.notify(f"تم حفظ الدور ({nar}) بنجاح!", type="positive")
                        self._return_to_roles_overview()
                    except Exception as exc:
                        ui.notify(f"خطأ أثناء حفظ الدور: {exc}", type="negative")

                UI.success_button(
                    "حفظ الدور والصلاحيات / Save Role Profile",
                    icon="check_circle",
                    on_click=_save_role
                ).classes("text-xs px-6 py-2.5 font-bold shadow-md")

    # ─────────────────────────────────────────────────────────────────────────
    # Sub-View 3: Dedicated Full-Page User Permissions Matrix (NO POPUP MODAL)
    # ─────────────────────────────────────────────────────────────────────────

    def _render_full_page_user_matrix(self) -> None:
        all_perms = []
        try:
            all_perms = self.perm_repo.get_all() or []
        except Exception as e:
            log.warning(f"Failed to fetch permissions catalog: {e}")

        personnel_list = []
        try:
            personnel_list = self.p_repo.get_all() or []
        except Exception as e:
            log.warning(f"Failed to fetch personnel for matrix: {e}")

        if not personnel_list:
            with UI.card().classes("w-full p-6 gap-4"):
                ui.label("لا توجد حسابات كوادر مسجلة! / No personnel accounts found").classes("text-sm text-red-400 font-bold")
                UI.secondary_button("← العودة لقائمة الأدوار", on_click=self._return_to_roles_overview)
            return

        initial_id = self.target_matrix_user_id or self.emp_id
        if not any(p.get("id") == initial_id for p in personnel_list):
            initial_id = personnel_list[0].get("id")

        with UI.card().classes("w-full p-6 gap-6"):
            # Header Navigation Bar
            with ui.row().classes("w-full items-center justify-between pb-4 border-b border-[var(--border-default)] shrink-0 gap-4 flex-wrap"):
                with ui.row().classes("items-center gap-3"):
                    UI.secondary_button(
                        "← العودة لقائمة الأدوار / Back to Roles",
                        icon="arrow_forward",
                        on_click=self._return_to_roles_overview
                    ).classes("text-xs px-4 py-2 font-bold shadow-sm")

                    with ui.element("div").classes("w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center"):
                        ui.icon("shield", size="sm").classes("text-emerald-400")

                    with ui.column().classes("gap-0"):
                        ui.label("لوحة التحكم بصلاحيات المستخدمين — User Permissions Matrix").classes("text-base font-bold app-text-primary")
                        ui.label("تخصيص الصلاحيات الفردية الممنوحة لكل حساب كادر في النظام بشكل مباشر ومفصل.").classes("text-xs app-text-muted")

                with ui.row().classes("items-center gap-2"):
                    UI.ghost_button("إلغاء / Cancel", on_click=self._return_to_roles_overview).classes("text-xs px-3 py-2")
                    save_btn_top = UI.success_button(
                        "حفظ الصلاحيات / Save Permissions",
                        icon="check_circle",
                        on_click=lambda: _save_user_permissions()
                    ).classes("text-xs px-5 py-2 font-bold shadow-md")

            user_options = {
                p["id"]: f"{p.get('name_ar', '')} (@{p.get('username', '')}) — [{p.get('personnel_role', 'user')}]"
                for p in personnel_list
            }

            all_pages_map = {
                "home": ("الرئيسية / Dashboard", "home"),
                "students": ("إدارة الطلاب والدرجات / Students", "school"),
                "orders": ("أوامر التخرج / Orders", "history_edu"),
                "departments": ("إدارة الأقسام / Departments", "domain"),
                "courses": ("المواد الدراسية / Courses", "menu_book"),
                "personnel": ("إدارة الكوادر / Personnel", "group"),
                "certificate": ("إصدار الوثيقة / Certificates", "print"),
                "issued_certs": ("سجل الوثائق الصادرة / Log", "list_alt"),
                "settings": ("إعدادات النظام / Settings", "settings"),
                "history": ("سجل النشاط والتغييرات / History", "history"),
            }

            state = {
                "selected_user_id": initial_id,
                "switches": {},
                "page_checkboxes": {},
                "granted_keys": set()
            }

            def load_user_perms(uid):
                state["selected_user_id"] = uid
                try:
                    granted = set(self.perm_repo.get_user_permissions(uid) or [])
                except Exception:
                    granted = set()
                state["granted_keys"] = granted

                # Action switches
                for k, sw in state["switches"].items():
                    sw.value = (k in granted)

                # Page accessibility checkboxes
                user_pages = {k.replace("page:", "") for k in granted if k.startswith("page:")}
                if not user_pages:
                    # Inherit from assigned role
                    user_rec = next((p for p in personnel_list if p.get("id") == uid), None)
                    if user_rec:
                        r_key = user_rec.get("personnel_role") or "user"
                        role_rec = self.role_repo.get_by_id(r_key)
                        if role_rec and role_rec.get("allowed_pages"):
                            user_pages = set(role_rec.get("allowed_pages"))
                        elif r_key == "admin":
                            user_pages = set(all_pages_map.keys())
                        else:
                            user_pages = {"home", "students", "orders", "certificate", "issued_certs"}
                    else:
                        user_pages = {"home", "students", "orders", "certificate", "issued_certs"}

                for pkey, cb in state["page_checkboxes"].items():
                    cb.value = (pkey in user_pages)

            # Controls Toolbar: User Selection & Quick Presets
            with ui.row().classes("w-full items-center justify-between gap-3 p-4 bg-[var(--bg-main)] rounded-2xl border border-[var(--border-default)] flex-wrap"):
                with ui.row().classes("items-center gap-2 flex-1 min-w-[320px]"):
                    ui.label("المستخدم المحدد / User:").classes("text-xs font-bold app-text-primary shrink-0")
                    user_select = UI.select(
                        "",
                        options=user_options,
                        value=initial_id,
                        on_change=lambda e: load_user_perms(e.value)
                    ).classes("flex-1 text-xs")

                with ui.row().classes("items-center gap-2 flex-wrap shrink-0"):
                    def _grant_all():
                        for k, sw in state["switches"].items():
                            sw.value = True
                        for cb in state["page_checkboxes"].values():
                            cb.value = True
                        ui.notify("تم تحديد جميع الصلاحيات والشاشات", type="info")

                    def _revoke_all():
                        for k, sw in state["switches"].items():
                            sw.value = False
                        for cb in state["page_checkboxes"].values():
                            cb.value = False
                        ui.notify("تم إلغاء جميع الصلاحيات والشاشات", type="info")

                    def _default_user():
                        default_keys = {
                            "students:view", "orders:view", "certificates:issue",
                            "issued_certs:view", "departments:view", "courses:view", "personnel:view"
                        }
                        for k, sw in state["switches"].items():
                            sw.value = (k in default_keys)
                        def_pages = {"home", "students", "orders", "certificate", "issued_certs"}
                        for pkey, cb in state["page_checkboxes"].items():
                            cb.value = (pkey in def_pages)
                        ui.notify("تم تطبيق النمط الافتراضي للمستخدم", type="info")

                    def _registrar_preset():
                        reg_keys = {
                            "students:view", "students:create", "students:edit", "students:grades",
                            "orders:view", "orders:create", "orders:edit",
                            "certificates:issue", "issued_certs:view", "issued_certs:export",
                            "departments:view", "courses:view"
                        }
                        for k, sw in state["switches"].items():
                            sw.value = (k in reg_keys)
                        reg_pages = {"home", "students", "orders", "departments", "courses", "certificate", "issued_certs"}
                        for pkey, cb in state["page_checkboxes"].items():
                            cb.value = (pkey in reg_pages)
                        ui.notify("تم تطبيق نمط شؤون الطلاب والتسجيل", type="info")

                    UI.ghost_button("تحديد الكل", icon="select_all", on_click=_grant_all).classes("text-xs px-2.5 py-1.5")
                    UI.ghost_button("إلغاء الكل", icon="clear_all", on_click=_revoke_all).classes("text-xs px-2.5 py-1.5")
                    UI.secondary_button("نمط مستخدم", icon="tune", on_click=_default_user).classes("text-xs px-2.5 py-1.5")
                    UI.secondary_button("نمط تسجيل", icon="school", on_click=_registrar_preset).classes("text-xs px-2.5 py-1.5")

            # ── Accessible Pages for User Card ───────────────────────────────
            with UI.card().classes("p-5 gap-4 rounded-2xl border border-[var(--border-default)] bg-[var(--bg-main)]"):
                with ui.row().classes("w-full items-center justify-between pb-2 border-b border-[var(--border-default)]"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("layers", size="sm").classes("text-purple-400")
                        ui.label("الشاشات والصفحات المتاح الوصول إليها للمستخدم — Accessible Pages").classes("text-sm font-bold text-purple-400")
                    with ui.row().classes("gap-2"):
                        def _sel_all_p():
                            for cb in state["page_checkboxes"].values():
                                cb.value = True
                        def _clr_all_p():
                            for cb in state["page_checkboxes"].values():
                                cb.value = False
                        UI.ghost_button("تحديد كافة الشاشات", icon="select_all", on_click=_sel_all_p).classes("text-xs px-2.5 py-1")
                        UI.ghost_button("إلغاء الكل", icon="clear_all", on_click=_clr_all_p).classes("text-xs px-2.5 py-1")

                with ui.grid(columns=3).classes("w-full gap-3"):
                    for p_key, (p_title, p_icon) in all_pages_map.items():
                        with ui.row().classes("items-center justify-between p-3 rounded-xl border border-[var(--border-default)] bg-[var(--surface-card)] hover:border-purple-500/30 transition-all"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon(p_icon, size="xs").classes("text-purple-400")
                                ui.label(p_title).classes("text-xs font-semibold app-text-primary")
                            cb = ui.checkbox(value=False)
                            state["page_checkboxes"][p_key] = cb

            # 8 Categories Cards
            categories = {
                "students": {"title": "🎓 شؤون الطلاب والدرجات — Students & Grades", "color": "text-blue-400"},
                "orders": {"title": "📜 أوامر التخرج — Graduation Orders", "color": "text-purple-400"},
                "certificates": {"title": "🖨️ إصدار الوثائق الرسمية — Issue Certificates", "color": "text-emerald-400"},
                "issued_certs": {"title": "📋 سجل الوثائق الصادرة — Issued Records & Logs", "color": "text-teal-400"},
                "departments": {"title": "🏢 إدارة الأقسام العلمية — Departments Management", "color": "text-amber-400"},
                "courses": {"title": "📚 المقررات والمناهج الدراسية — Courses Catalog", "color": "text-indigo-400"},
                "personnel": {"title": "👥 الكوادر والمستخدمين — Personnel & Accounts", "color": "text-orange-400"},
                "settings": {"title": "⚙️ إعدادات النظام — System Settings Views & Alter", "color": "text-cyan-400"},
            }

            with ui.column().classes("w-full gap-5"):
                for cat_key, cat_meta in categories.items():
                    cat_perms = [p for p in all_perms if p.get("category") == cat_key and p.get("permission_key") in ALL_PERMISSION_KEYS]
                    if not cat_perms:
                        continue

                    with ui.column().classes("w-full p-4 rounded-xl border border-[var(--border-default)] bg-[var(--surface-card)] gap-3"):
                        ui.label(cat_meta["title"]).classes(f"font-bold text-xs {cat_meta['color']}")

                        with ui.grid(columns=2).classes("w-full gap-3"):
                            for perm in cat_perms:
                                pkey = perm["permission_key"]
                                pname_ar = perm.get("name_ar") or pkey
                                pname_en = perm.get("name_en") or pkey
                                pdesc = perm.get("description_ar") or ""

                                with ui.row().classes("items-center justify-between p-2.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-main)] hover:border-emerald-500/30 transition-all"):
                                    with ui.column().classes("gap-0 min-w-0 flex-1"):
                                        ui.label(f"{pname_ar} / {pname_en}").classes("text-xs font-bold app-text-primary truncate")
                                        if pdesc:
                                             ui.label(pdesc).classes("text-[10px] app-text-muted truncate")
                                    sw = ui.switch().props("dense size=sm color=positive")
                                    state["switches"][pkey] = sw

            load_user_perms(initial_id)

            # Bottom Actions Bar
            with ui.row().classes("w-full items-center justify-between pt-6 border-t border-[var(--border-default)] mt-4"):
                UI.secondary_button("← إلغاء والعودة لقائمة الأدوار", on_click=self._return_to_roles_overview).classes("text-xs px-4 py-2")

                def _save_user_permissions():
                    try:
                        uid = state["selected_user_id"]
                        granted_actions = [k for k, sw in state["switches"].items() if sw.value and k in ALL_PERMISSION_KEYS]
                        granted_pages = [f"page:{p_key}" for p_key, cb in state["page_checkboxes"].items() if cb.value]
                        all_to_save = granted_actions + granted_pages
                        self.perm_repo.set_user_permissions(uid, all_to_save)
                        ui.notify(
                            f"تم حفظ الصلاحيات والشاشات للمستخدم بنجاح! ({len(granted_actions)} إجراء + {len(granted_pages)} شاشة)",
                            type="positive"
                        )
                    except Exception as err:
                        ui.notify(f"خطأ أثناء حفظ الصلاحيات: {err}", type="negative")

                UI.success_button(
                    "حفظ صلاحيات وشاشات المستخدم / Save Permissions",
                    icon="check_circle",
                    on_click=_save_user_permissions
                ).classes("text-xs px-6 py-2.5 font-bold shadow-md")


    def _section_system_logs(self) -> None:
        with UI.card():
            UI.card_header("سجلات حركة النظام — System Activity Logs", "terminal", icon_css="stat-text-amber")
            log_file = Path("logs/system_log.txt")
            log_content = ""
            if log_file.exists():
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        log_content = "".join(lines[-100:])
                except Exception:
                    log_content = "تعذر قراءة ملف السجلات / Could not read log file"
            else:
                log_content = "لا يوجد سجل نشاطات حالياً / No activity log file found"

            ui.textarea(value=log_content).classes("w-full h-48 font-mono text-xs bg-[var(--bg-main)] rounded-xl p-3").props("readonly")

    def _section_analytics(self) -> None:
        with UI.card():
            UI.card_header("تحليلات وإحصائيات النظام — Analytics Summary", "analytics", icon_css="stat-text-purple")
            with ui.grid(columns=4).classes("w-full gap-4"):
                UI.stat_card("إجمالي السجلات", "Total DB Records", "1,250+", "storage", variant="blue")
                UI.stat_card("الوثائق المصدرة", "Issued Certificates", "340+", "description", variant="emerald")
                UI.stat_card("المستخدمين النشطين", "Active System Users", "12", "people", variant="amber")
                UI.stat_card("حالة مزامنة SQLite", "Sync Engine Status", "100%", "cloud_done", variant="purple")

    def _section_server_config(self) -> None:
        """Section for configuring Server API Host, Port, Secret Key, and Auto Reconnect settings."""
        with UI.card():
            UI.card_header("إعدادات السيرفر والشبكة — Server & API Settings", "dns", icon_css="stat-text-blue")

            from api_config import load_server_config
            cfg = load_server_config()

            api_host = f"http://{cfg.get('host', '127.0.0.1')}"
            api_port = str(cfg.get('port', 2030))
            api_secret = cfg.get('secret', 'certificate_manager_secret_key')
            api_timeout = int(cfg.get('timeout', 5))
            auto_sync = bool(cfg.get('auto_sync', True))

            with ui.grid(columns=2).classes("w-full gap-4"):
                self.server_host_input = UI.text_input(
                    "عنوان السيرفر / Server Host (IP/Domain)",
                    value=api_host,
                    placeholder="http://127.0.0.1"
                )
                self.server_port_input = UI.text_input(
                    "منفذ السيرفر / Server Port",
                    value=api_port,
                    placeholder="2030"
                )
                self.api_secret_input = UI.text_input(
                    "مفتاح التطبيق السرّي / App Secret Key",
                    value=api_secret,
                    placeholder="Secret Key..."
                )
                self.api_timeout_input = UI.number_input(
                    "مهلة الاتصال (بالثواني) / Request Timeout (s)",
                    value=api_timeout, min=1, max=60
                )

            with ui.row().classes("app-tile w-full items-center justify-between p-3.5 rounded-xl border mt-2"):
                with ui.column().classes("gap-0"):
                    UI.standard_label("المزامنة التلقائية عند الاتصال / Auto Online Reconnection Sync")
                    UI.muted_label("تفعيل المزامنة الفورية للبيانات المحفوظة أوفلاين بمجرد توفر الاتصال بالسيرفر.")
                self.auto_sync_switch = UI.switch("تفعيل / Enable", value=auto_sync)

            with ui.row().classes("w-full justify-between items-center pt-2 border-t mt-3"):
                UI.secondary_button(
                    "فحص الاتصال بالسيرفر / Test Connection",
                    icon="wifi_tethering",
                    on_click=self._test_server_connection
                )
                UI.success_button(
                    "حفظ إعدادات السيرفر / Save Server Config",
                    icon="save",
                    on_click=self._save_server_config
                )

    def _section_database_maintenance(self) -> None:
        """Section for Database Management, SQLite Replica Info, Offline Queue Sync, and Backups."""
        with UI.card():
            UI.card_header("إدارة وقواعد البيانات والمزامنة — Database Management & Sync", "storage", icon_css="stat-text-amber")

            # 1. Live Offline Queue & Database Replicas Overview
            with ui.row().classes("w-full items-center justify-between p-4 bg-[var(--bg-main)] rounded-xl border border-[var(--border-default)] mb-2"):
                with ui.column().classes("gap-1"):
                    ui.label("حالة قاعدة البيانات والمزامنة الأوفلاين / Database & Sync Status").classes("text-sm font-bold app-text-primary")
                    
                    # Fetch metrics from SQLite
                    queue_count = 0
                    cache_count = 0
                    try:
                        from sync_engine import sqlite_read_one
                        q_res = sqlite_read_one("SELECT COUNT(*) AS cnt FROM sync_queue")
                        queue_count = q_res.get("cnt", 0) if q_res else 0
                        c_res = sqlite_read_one("SELECT COUNT(*) AS cnt FROM read_cache")
                        cache_count = c_res.get("cnt", 0) if c_res else 0
                    except Exception:
                        pass
                    
                    ui.label(
                        f"سجلات معلقة للمزامنة: {queue_count}  |  عناصر الذاكرة المؤقتة: {cache_count}"
                    ).classes("text-xs app-text-muted font-mono")
                
                from sync_engine import is_online
                UI.status_badge(online=is_online())

            # 2. Database Action Tiles Grid
            with ui.grid(columns=2).classes("w-full gap-4 mt-2"):
                UI.action_tile(
                    "مزامنة البيانات المعلقة / Sync Offline Queue",
                    "رفع السجلات التي تمت إضافتها أوفلاين إلى قاعدة بيانات MySQL",
                    "مزامنة السجلات / Sync Queue",
                    "cloud_upload", btn_variant="success", on_click_fn=self._do_sync_offline_queue
                )
                UI.action_tile(
                    "تنزيل نسخ الجداول / Download Fresh Replicas",
                    "سحب تحديثات الجداول الحالية من MySQL وحفظها في SQLite",
                    "تحديث الجداول / Pull Replicas",
                    "cloud_download", btn_variant="primary", on_click_fn=self._do_pull_mysql_replicas
                )
                UI.action_tile(
                    "مسح الذاكرة المؤقتة / Clear Read Cache",
                    "تفريغ ذاكرة الاستعلامات المحفوظة محلياً",
                    "تفريغ الذاكرة / Clear Cache",
                    "cleaning_services", btn_variant="warning", on_click_fn=self._do_clear_read_cache
                )
                UI.action_tile(
                    "فحص اتصال قاعدة البيانات / DB Diagnostics",
                    "اختبار سرعة وصحة الاتصال بقاعدة البيانات والسيرفر",
                    "فحص الاتصال / Run Test",
                    "find_in_page", btn_variant="info", on_click_fn=self._do_check_db_diagnostics
                )
                UI.action_tile(
                    "نسخ احتياطي لقاعدة البيانات / Backup Database",
                    "إنشاء نسخة SQL احتياطية حفظاً للبيانات",
                    "إنشاء نسخة / Create Backup",
                    "backup", btn_variant="success", on_click_fn=self._do_backup
                )
                UI.action_tile(
                    "استعادة نسخة احتياطية / Restore Database",
                    "استرجاع البيانات من ملف .sql سابق",
                    "استعادة النسخة / Restore Backup",
                    "restore", btn_variant="warning", on_click_fn=self._do_restore
                )
                UI.action_tile(
                    "مسح سجل التغييرات / Clear Audit Logs",
                    "تفريغ ملف سجل النشاطات الحالية",
                    "مسح السجل / Clear Logs",
                    "delete_forever", btn_variant="danger", on_click_fn=self._do_clear_logs
                )

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

    def _on_theme_select_change(self, e=None) -> None:
        """Live theme switch when Theme Mode dropdown option changes."""
        from nicegui_ui.ui_theme import is_windows_dark_mode, set_dark_mode
        from nicegui_ui.state import log_state
        raw_val = self._get_event_value(e, self.theme_select, "Dark")
        val = str(raw_val or "Dark")
        if val == "Dark":
            set_dark_mode(True)
        elif val == "Light":
            set_dark_mode(False)
        else:
            set_dark_mode(is_windows_dark_mode())

        # Update session memory
        self.session.update_preferences(theme=val)

        # Update database and track result
        mysql_result = "success"
        try:
            self.s_repo.update_user_appearance(
                emp_id=self.emp_id,
                theme=val,
                accent=self.session.accent_color,
                font=str(self.session.preferences.get("font_family") or "Segoe UI"),
                size=int(self.session.preferences.get("font_size_base") or 13),
                rtl=int(self.session.preferences.get("is_arabic_rtl") or 1)
            )
        except Exception as exc:
            mysql_result = f"error: {exc}"

        dark_val = None
        try:
            dark_val = getattr(ui.dark_mode(), 'value', None)
        except Exception:
            pass

        log_state("THEME_TOGGLE", {
            "target_value": val,
            "app_session_preferences": dict(self.session.preferences),
            "ui_dark_mode_value": dark_val,
            "mysql_update_result": mysql_result
        })

        ui.notify(
            f"تم تغيير المظهر إلى {'الداكن' if val == 'Dark' else ('الفاتح' if val == 'Light' else 'النظام')} / Theme set to {val}!",
            type="info"
        )

    def _on_accent_select_change(self, e=None) -> None:
        """Live accent palette switch when Accent Color dropdown option changes."""
        from nicegui_ui.ui_theme import set_accent
        raw_val = self._get_event_value(e, self.accent_select, "blue")
        val = str(raw_val or "blue")
        set_accent(val)
        self.session.update_preferences(accent_color=val)
        ui.notify(f"تم تغيير اللون الأساسي / Accent set to {val}!", type="info")

    def _on_font_select_change(self, e=None) -> None:
        """Live font family switch when Font Family dropdown option changes."""
        from nicegui_ui.ui_theme import set_font_family
        raw_val = self._get_event_value(e, self.font_select, "Segoe UI")
        val = str(raw_val or "Segoe UI")
        set_font_family(val)
        self.session.update_preferences(font_family=val)
        ui.notify(f"تم تغيير نوع الخط إلى {val} / Font family set to {val}!", type="info")

    def _on_font_size_change(self, e=None) -> None:
        """Live base font size scale when Base Font Size number input changes."""
        from nicegui_ui.ui_theme import set_font_size
        try:
            raw_val = self._get_event_value(e, self.font_size_input, 13)
            val = int(raw_val or 13)
            set_font_size(val)
            self.session.update_preferences(font_size_base=val)
        except Exception:
            pass

    def _on_rtl_switch_change(self, e=None) -> None:
        """Live RTL / LTR layout direction switch when RTL toggle is changed."""
        from nicegui_ui.ui_theme import set_rtl
        try:
            raw_val = self._get_event_value(e, self.rtl_switch, True)
            val = bool(raw_val)
            set_rtl(val)
            self.session.update_preferences(is_arabic_rtl=1 if val else 0)
            ui.notify(f"تم تغيير اتجاه الواجهة إلى {'اليمين (RTL)' if val else 'اليسار (LTR)'} / Layout set to {'RTL' if val else 'LTR'}!", type="info")
        except Exception:
            pass

    def _save_institution_info(self) -> None:
        try:
            self.s_repo.update_settings(
                univ_ar=(self.univ_ar_input.value if self.univ_ar_input else "") or "",
                univ_en=(self.univ_en_input.value if self.univ_en_input else "") or "",
                college_ar=(self.college_ar_input.value if self.college_ar_input else "") or "",
                college_en=(self.college_en_input.value if self.college_en_input else "") or "",
                univ_logo=self.univ_logo_path,
                college_logo=self.college_logo_path
            )
            ui.notify("تم حفظ معلومات المؤسسة والشعارات بنجاح / Institution info & logos saved!", type="positive")
        except Exception as exc:
            ui.notify(f"Error saving settings: {exc}", type="negative")

    def _add_study_system(self) -> None:
        try:
            self.sys_repo.insert(
                name_ar="نظام جديد",
                name_en="New System",
                calc_rule="annual",
                period_display="year",
                calculation_weights="10:20:30:40"
            )
            ui.notify("تمت إضافة نظام الدراسة بنجاح / Study system added!", type="positive")
            self._load_data()
            self._render_systems_list()
        except Exception as exc:
            ui.notify(f"Error adding study system: {exc}", type="negative")

    def _toggle_system_active(self, sys_id: int, active: bool) -> None:
        try:
            self.sys_repo.toggle(sys_id, 1 if active else 0)
            ui.notify("System status updated!", type="positive")
        except Exception as exc:
            ui.notify(f"Error updating status: {exc}", type="negative")

    def _delete_study_system(self, sys_id: int) -> None:
        try:
            self.sys_repo.delete(sys_id)
            ui.notify("تم حذف نظام الدراسة / System deleted!", type="info")
            self._load_data()
            self._render_systems_list()
        except Exception as exc:
            ui.notify(f"Error deleting system: {exc}", type="negative")

    def _save_appearance(self) -> None:
        from nicegui_ui.state import log_state
        try:
            theme_val = str((self.theme_select.value if self.theme_select else None) or "Dark")
            accent_val = str((self.accent_select.value if self.accent_select else None) or "blue")
            font_val = str((self.font_select.value if self.font_select else None) or "Arial")
            size_val = int((self.font_size_input.value if self.font_size_input else None) or 14)
            rtl_val = 1 if (self.rtl_switch.value if self.rtl_switch else True) else 0

            from nicegui_ui.ui_theme import set_rtl
            set_rtl(bool(rtl_val))

            mysql_result = "success"
            try:
                self.s_repo.update_user_appearance(
                    emp_id=self.emp_id,
                    theme=theme_val,
                    accent=accent_val,
                    font=font_val,
                    size=size_val,
                    rtl=rtl_val
                )
            except Exception as exc:
                mysql_result = f"error: {exc}"

            self.session.update_preferences(
                theme=theme_val,
                accent_color=accent_val,
                font_family=font_val,
                font_size_base=size_val,
                is_arabic_rtl=rtl_val
            )

            log_state("THEME_SAVE", {
                "target_value": theme_val,
                "accent_color": accent_val,
                "font_family": font_val,
                "font_size_base": size_val,
                "app_session_preferences": dict(self.session.preferences),
                "mysql_update_result": mysql_result
            })

            ui.notify("تم حفظ وتطبيق تفضيلات المظهر بنجاح / Appearance saved & applied!", type="positive")
        except Exception as exc:
            ui.notify(f"Error saving appearance: {exc}", type="negative")

    async def _do_backup(self) -> None:
        """Ask the server to dump the database (mysqldump runs on the server) and save the .sql to Downloads."""
        from nicegui import run
        from sync_engine import is_online
        if not is_online():
            ui.notify("النسخ الاحتياطي يتطلب الاتصال بالسيرفر / Backup requires a server connection.", type="warning")
            return
        ui.notify("جاري إنشاء النسخة الاحتياطية... / Creating backup...", type="info")
        try:
            resp = await run.io_bound(
                requests.get, f"{get_api_url()}/admin/backup",
                params={"personnel_id": self.emp_id}, timeout=300.0
            )
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            filename = f"certificate_manager_backup_{datetime.now():%Y%m%d_%H%M%S}.sql"
            deliver_file(resp.content, filename, title="تم إنشاء النسخة الاحتياطية بنجاح / Backup created", auto_open=False)
        except Exception as exc:
            ui.notify(f"Backup failed: {exc}", type="negative")

    def _do_restore(self) -> None:
        """Pick a .sql backup, confirm, then upload it to the server, which restores it (admin only)."""
        from sync_engine import is_online
        if not is_online():
            ui.notify("الاستعادة تتطلب الاتصال بالسيرفر / Restore requires a server connection.", type="warning")
            return

        picked: dict = {}
        with ui.dialog() as dialog, UI.card():
            UI.card_header("استعادة نسخة احتياطية / Restore Database", "restore", icon_css="stat-text-amber")
            ui.label(
                "تحذير: الاستعادة تستبدل جميع البيانات الحالية في قاعدة البيانات. "
                "Warning: restoring replaces ALL current data in the database."
            ).classes("text-sm font-bold text-red-500")
            status_label = ui.label("لم يتم اختيار ملف بعد / No file selected").classes("text-xs app-text-muted")

            async def _on_pick(e):
                name = e.file.name or ""
                if not name.lower().endswith(".sql"):
                    ui.notify("يجب اختيار ملف .sql / Please choose a .sql file.", type="warning")
                    return
                picked["name"] = name
                picked["content"] = await e.file.read()
                status_label.set_text(f"{name} ({round(len(picked['content']) / 1024, 1)} KB)")

            ui.upload(label="اختر ملف النسخة الاحتياطية (.sql)", auto_upload=True, on_upload=_on_pick) \
                .props("accept=.sql max-files=1").classes("w-full")

            async def _confirm_restore():
                from nicegui import run
                if not picked.get("content"):
                    ui.notify("يرجى اختيار ملف أولاً / Please choose a file first.", type="warning")
                    return
                dialog.close()
                ui.notify("جاري الاستعادة... / Restoring...", type="info")
                try:
                    resp = await run.io_bound(
                        requests.post, f"{get_api_url()}/admin/restore",
                        params={"personnel_id": self.emp_id},
                        files={"file": (picked["name"], picked["content"], "application/sql")},
                        timeout=600.0,
                    )
                    if resp.status_code != 200:
                        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                    ui.notify("تمت استعادة قاعدة البيانات / Database restored!", type="positive")
                except Exception as exc:
                    ui.notify(f"Restore failed: {exc}", type="negative")

            with ui.row().classes("w-full justify-end gap-2 pt-2"):
                ui.button("إلغاء / Cancel", on_click=dialog.close).props("flat")
                ui.button("استعادة / Restore", icon="restore", on_click=_confirm_restore).props("color=negative")
        dialog.open()

    def _do_clear_logs(self) -> None:
        try:
            self.s_repo.clear_audit_logs()
            ui.notify("تم مسح سجل التغييرات / Audit logs cleared!", type="info")
        except Exception as exc:
            ui.notify(f"Clear logs failed: {exc}", type="negative")

    def _test_server_connection(self) -> None:
        """Tests live reachability of the configured Server API host & port."""
        from sync_engine import check_network_status
        host = (self.server_host_input.value if hasattr(self, 'server_host_input') and self.server_host_input else "127.0.0.1")
        port = (self.server_port_input.value if hasattr(self, 'server_port_input') and self.server_port_input else "2030")
        clean_host = str(host).replace("http://", "").replace("https://", "").strip().rstrip("/")
        full_url = f"http://{clean_host}:{port}"

        try:
            online = check_network_status(target_url=full_url)
            if online:
                ui.notify(f"الاتصال بالسيرفر {full_url} يعمل بنجاح! / Server connected successfully!", type="positive")
            else:
                ui.notify(f"السيرفر {full_url} غير متصل حالياً. يعمل التطبيق في الوضع المحتجز (Offline Mode).", type="warning")
        except Exception as exc:
            ui.notify(f"فحص الاتصال فشل: {exc}", type="negative")

    def _save_server_config(self) -> None:
        """Saves Server API settings locally to server_config.json."""
        from api_config import save_server_config
        from sync_engine import check_network_status, set_online
        host = (self.server_host_input.value if hasattr(self, 'server_host_input') and self.server_host_input else "127.0.0.1")
        port = (self.server_port_input.value if hasattr(self, 'server_port_input') and self.server_port_input else "2030")
        secret = (self.api_secret_input.value if hasattr(self, 'api_secret_input') and self.api_secret_input else "certificate_manager_secret_key")
        timeout = (self.api_timeout_input.value if hasattr(self, 'api_timeout_input') and self.api_timeout_input else 5)
        auto_sync = (self.auto_sync_switch.value if hasattr(self, 'auto_sync_switch') and self.auto_sync_switch else True)

        try:
            cfg = save_server_config(host=host, port=port, secret=secret, timeout=timeout, auto_sync=auto_sync)
            # Update active repository instances with the new URL
            if hasattr(self, 's_repo') and self.s_repo:
                self.s_repo.api_url = cfg["api_url"]
            if hasattr(self, 'student_repo') and self.student_repo:
                self.student_repo.api_url = cfg["api_url"]
                self.student_repo.api_base_url = cfg["api_url"]

            # Re-evaluate network status for the new URL immediately
            set_online(check_network_status(target_url=cfg["api_url"]))

            ui.notify(f"تم حفظ إعدادات السيرفر والمنفذ ({cfg['api_url']}) محلياً في server_config.json بنجاح!", type="positive")
            self._test_server_connection()
        except Exception as exc:
            ui.notify(f"خطأ أثناء حفظ إعدادات السيرفر: {exc}", type="negative")

    def _do_sync_offline_queue(self) -> None:
        """Triggers manual sync of queued offline INSERTs to MySQL."""
        from sync_engine import is_online, sync_offline_queue_to_mysql
        if not is_online():
            ui.notify("لا يوجد اتصال بالسيرفر حالياً للمزامنة. يرجى الاتصال أولاً.", type="warning")
            return
        try:
            sync_offline_queue_to_mysql()
            ui.notify("تمت مزامنة البيانات المعلقة مع قاعدة البيانات بنجاح! / Offline queue synced!", type="positive")
        except Exception as exc:
            ui.notify(f"خطأ أثناء المزامنة: {exc}", type="negative")

    def _do_pull_mysql_replicas(self) -> None:
        """Triggers manual download of fresh table replicas from MySQL to SQLite."""
        from sync_engine import is_online, pull_mysql_to_sqlite
        if not is_online():
            ui.notify("لا يوجد اتصال بالسيرفر حالياً لتنزيل الجداول.", type="warning")
            return
        try:
            pull_mysql_to_sqlite()
            ui.notify("تم تحديث وتنزيل نسخ الجداول الحديثة بنجاح! / Fresh table replicas downloaded!", type="positive")
        except Exception as exc:
            ui.notify(f"خطأ أثناء تنزيل الجداول: {exc}", type="negative")

    def _do_clear_read_cache(self) -> None:
        """Clears SQLite read_cache entries."""
        try:
            from sync_engine import get_local_connection
            conn = get_local_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM read_cache")
            conn.commit()
            cursor.close()
            conn.close()
            ui.notify("تم تفريغ الذاكرة المؤقتة بنجاح! / Read cache cleared!", type="positive")
        except Exception as exc:
            ui.notify(f"خطأ أثناء مسح الذاكرة: {exc}", type="negative")

    def _do_check_db_diagnostics(self) -> None:
        """Performs live database diagnostic checks."""
        from sync_engine import is_online
        try:
            from sync_engine import sqlite_read_one
            status = "Online (MySQL + SQLite)" if is_online() else "Offline (SQLite Replica)"
            q_res = sqlite_read_one("SELECT COUNT(*) AS cnt FROM sync_queue")
            q_cnt = q_res.get("cnt", 0) if q_res else 0
            ui.notify(
                f"فحص قاعدة البيانات:\n• الحالة: {status}\n• المعلق للمزامنة: {q_cnt} عنصر",
                type="info"
            )
        except Exception as exc:
            ui.notify(f"فحص قاعدة البيانات فشل: {exc}", type="negative")

    def _section_templates_management(self) -> None:
        """Dedicated settings tab to inspect, manage, upload, and understand certificate Word templates."""
        templates_dir = "templets"
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

                def _handle_upload(e):
                    try:
                        fname = getattr(e, "name", None) or getattr(e, "filename", "")
                        if not fname.lower().endswith(".docx"):
                            ui.notify("الملف غير مدعوم! يجب أن يكون ملف Word بتنسيق docx.", type="warning")
                            return

                        content = e.content.read() if hasattr(e, "content") else None
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
