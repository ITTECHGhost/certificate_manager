# =============================================================================
# screens/settings_screen.py — NiceGUI Settings Screen
# =============================================================================
#
# Full NiceGUI rewrite of the application settings screen.
# Built using the `UI` component factory from `ui_components.py` and `state.py`.
#
# Features:
#   1. Institution Info (Univ & College AR/EN)
#   2. Study Systems Management (CRUD list with Active toggle switches + Add/Delete)
#   3. Appearance & Theme (Theme Mode dropdown with live Light/Dark mode switching,
#      Accent, Font, Base Font Size, RTL Layout controls bound to logged-in EMP_ID session state)
#   4. Database Maintenance (Backup, Restore, Legacy MySQL Import, Clear Logs)
#   5. About Section (Version & Developer credits)
#
# =============================================================================

from pathlib import Path
from nicegui import ui
from data.repositories import SettingsRepository, StudySystemRepository
from db import backup_db, restore_db
from tools.migrate_mysql import trigger_migration
from ui_components import UI
from state import get_user_session


class SettingsScreen:
    """
    NiceGUI Settings Screen.
    Renders inside the MainAppShell scroll content area.
    """

    def __init__(self, on_notify=None) -> None:
        self.s_repo = SettingsRepository()
        self.sys_repo = StudySystemRepository()
        self.on_notify = on_notify or (lambda msg, typ="positive": ui.notify(msg, type=typ))

        # Active User Session State
        self.session = get_user_session()
        self.emp_id = self.session.emp_id

        # Data
        self.settings_data: dict = {}
        self.appearance_data: dict = {}
        self.systems: list = []

        # Form Controls
        self.univ_ar_input = None
        self.univ_en_input = None
        self.college_ar_input = None
        self.college_en_input = None
        self.theme_select = None
        self.accent_select = None
        self.font_select = None
        self.font_size_input = None
        self.rtl_switch = None

        self._load_data()
        self._build_ui()
        self._apply_initial_theme()

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    def _load_data(self) -> None:
        """Fetch current settings, user appearance (tied to EMP_ID), and study systems from repositories."""
        try:
            self.settings_data = self.s_repo.get_settings() or {}
            self.appearance_data = self.s_repo.get_user_appearance(self.emp_id) or {}
            self.systems = self.sys_repo.get_all() or []
        except Exception as exc:
            print(f"[SettingsScreen] Error loading settings data: {exc}")

    def _apply_initial_theme(self) -> None:
        """Applies saved theme preference on screen load."""
        saved_theme = str(self.appearance_data.get("theme", "Dark"))
        dark_mode = ui.dark_mode()
        if saved_theme == "Dark":
            dark_mode.enable()
        elif saved_theme == "Light":
            dark_mode.disable()
        else:
            dark_mode.auto()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the settings screen layout using the UI factory."""
        with ui.column().classes("w-full gap-6 pb-12"):
            self._section_institution_info()
            self._section_study_systems()
            self._section_appearance()
            self._section_database_maintenance()
            self._section_about()

    # ── Section 1: Institution Info ──────────────────────────────────

    def _section_institution_info(self) -> None:
        with UI.card():
            UI.card_header("معلومات المؤسسة — Institution Info", "domain", "text-blue-500 dark:text-blue-400")

            with ui.grid(columns=2).classes("w-full gap-4"):
                self.univ_ar_input = UI.text_input(
                    "اسم الجامعة بالعربية / Univ. Name (AR)",
                    value=self.settings_data.get("univ_name_ar", "")
                )
                self.univ_en_input = UI.text_input(
                    "اسم الجامعة بالإنكليزية / Univ. Name (EN)",
                    value=self.settings_data.get("univ_name_en", "")
                )
                self.college_ar_input = UI.text_input(
                    "اسم الكلية بالعربية / College Name (AR)",
                    value=self.settings_data.get("college_name_ar", "")
                )
                self.college_en_input = UI.text_input(
                    "اسم الكلية بالإنكليزية / College Name (EN)",
                    value=self.settings_data.get("college_name_en", "")
                )

            UI.primary_button(
                "حفظ معلومات المؤسسة / Save Info",
                icon="save",
                on_click=self._save_institution_info
            ).classes("self-end")

    # ── Section 2: Study Systems ─────────────────────────────────────

    def _section_study_systems(self) -> None:
        with UI.card():
            with ui.row().classes("w-full justify-between items-center border-b border-slate-200 dark:border-slate-800 pb-3"):
                UI.section_label("أنظمة الدراسة — Study Systems")
                UI.success_button(
                    "إضافة نظام جديد / Add System",
                    icon="add",
                    on_click=self._add_study_system
                )

            self._systems_container = ui.column().classes("w-full gap-3")
            self._render_systems_list()

    def _render_systems_list(self) -> None:
        """Renders/refreshes the study systems list rows."""
        self._systems_container.clear()
        with self._systems_container:
            for s in self.systems:
                with ui.row().classes(
                    "w-full items-center gap-3 p-3 bg-slate-50 dark:bg-slate-900/60 "
                    "rounded-xl border border-slate-200 dark:border-slate-800 flex-nowrap"
                ):
                    UI.standard_label(
                        f"{s.get('name_ar', '')} ({s.get('name_en', '')})"
                    ).classes("w-48 truncate")

                    UI.chip(f"Rule: {s.get('calculation_rule', 'annual')}", color="blue")
                    UI.chip(f"Display: {s.get('period_display', 'year')}", color="teal")

                    UI.muted_label(f"Weights: {s.get('calculation_weights', '—')}").classes("flex-grow")

                    sw = UI.switch("تفعيل / Active", value=bool(s.get("is_active", 1)))
                    sw.on(
                        "change",
                        lambda e, sid=s["id"]: self._toggle_system_active(sid, e.value)
                    )

                    UI.ghost_button(
                        "", icon="delete",
                        on_click=lambda sid=s["id"]: self._delete_study_system(sid)
                    ).classes("text-red-500 dark:text-red-400 hover:bg-red-500/20 p-2")

    # ── Section 3: Appearance & Theme (Bound to EMP_ID Session State) ─

    def _section_appearance(self) -> None:
        with UI.card():
            UI.card_header("المظهر والسمات — Appearance & Theme", "palette", "text-purple-500 dark:text-purple-400")

            saved_theme = str(self.appearance_data.get("theme", "Dark"))
            saved_accent = str(self.appearance_data.get("accent_color", "blue"))
            saved_font = str(self.appearance_data.get("font_family", "Segoe UI"))
            saved_size = int(self.appearance_data.get("font_size_base", 13))
            saved_rtl = int(self.appearance_data.get("is_arabic_rtl", 1))

            with ui.grid(columns=2).classes("w-full gap-4"):
                self.theme_select = UI.select(
                    "الوضع (فاتح/داكن) / Theme Mode",
                    options=["System", "Light", "Dark"],
                    value=saved_theme
                )
                self.theme_select.on("update:model-value", self._on_theme_select_change)

                self.accent_select = UI.select(
                    "اللون الأساسي / Accent Color",
                    options=["blue", "green", "dark-blue", "orange", "purple", "red"],
                    value=saved_accent
                )
                self.font_select = UI.select(
                    "نوع الخط / Font Family",
                    options=["Arial", "Segoe UI", "Roboto", "Cairo", "Tahoma"],
                    value=saved_font
                )
                self.font_size_input = UI.number_input(
                    "حجم الخط الأساسي / Base Font Size",
                    value=saved_size, min=10, max=24
                )

            with ui.row().classes("w-full items-center justify-between p-3 bg-slate-50 dark:bg-slate-900/40 rounded-xl border border-slate-200 dark:border-slate-800"):
                UI.standard_label("اتجاه الواجهة من اليمين إلى اليسار / Arabic RTL Layout")
                self.rtl_switch = UI.switch("تفعيل RTL / Enable RTL", value=bool(saved_rtl))

            UI.primary_button(
                "حفظ وتطبيق المظهر / Save Appearance",
                icon="brush",
                on_click=self._save_appearance
            ).classes("self-end bg-purple-600 hover:bg-purple-500")

    # ── Section 4: Database Maintenance ──────────────────────────────

    def _section_database_maintenance(self) -> None:
        with UI.card():
            UI.card_header("صيانة قاعدة البيانات — Database Maintenance", "storage", "text-amber-500 dark:text-amber-400")

            with ui.grid(columns=2).classes("w-full gap-4"):
                UI.action_tile(
                    "نسخ احتياطي لقاعدة البيانات / Backup Database",
                    "إنشاء نسخة SQL احتياطية حفظاً للبيانات",
                    "إنشاء نسخة احتياطية / Create Backup",
                    "backup", "bg-blue-600", self._do_backup
                )
                UI.action_tile(
                    "استعادة نسخة احتياطية / Restore Database",
                    "استرجاع البيانات من ملف .sql سابق",
                    "استعادة النسخة / Restore Backup",
                    "restore", "bg-amber-600", self._do_restore
                )
                UI.action_tile(
                    "استيراد من النظام القديم / Import Legacy MySQL",
                    "نقل وسحب البيانات القديمة تلقائياً",
                    "استيراد البيانات / Import Data",
                    "upload_file", "bg-emerald-600", self._do_import
                )
                UI.action_tile(
                    "مسح سجل التغييرات / Clear Audit Logs",
                    "تفريغ ملف سجل النشاطات الحالية",
                    "مسح السجل / Clear Logs",
                    "delete_forever", "bg-red-600", self._do_clear_logs
                )

    # ── Section 5: About ─────────────────────────────────────────────

    def _section_about(self) -> None:
        with UI.card():
            UI.card_header("حول البرنامج — About", "info", "text-slate-400")

            with ui.column().classes("w-full items-center text-center gap-2 p-4"):
                UI.section_label("نظام إدارة الشهادات - الإصدار 2.0 (NiceGUI Native UI)")
                UI.muted_label("Certificate Manager - v2.0")
                UI.muted_label("تم التطوير لأتمتة عمليات إصدار الوثائق والشهادات الجامعية.").classes("mt-2")
                ui.label("Developed by M. Hussein / تم التطوير بواسطة م. حسين").classes(
                    "text-xs text-emerald-600 dark:text-emerald-400 font-semibold mt-1"
                )

    # ------------------------------------------------------------------
    # Live Theme Change & Event Handlers
    # ------------------------------------------------------------------

    def _on_theme_select_change(self, e=None) -> None:
        """Live theme switch when Theme Mode dropdown option changes."""
        val = str(self.theme_select.value or "Dark")
        dark_mode = ui.dark_mode()
        if val == "Dark":
            dark_mode.enable()
        elif val == "Light":
            dark_mode.disable()
        else:
            dark_mode.auto()
        
        ui.notify(
            f"تم تغيير المظهر إلى {'الداكن' if val == 'Dark' else ('الفاتح' if val == 'Light' else 'النظام')} / Theme set to {val}!",
            type="info"
        )

    def _save_institution_info(self) -> None:
        try:
            self.s_repo.update_settings(
                univ_ar=self.univ_ar_input.value or "",
                univ_en=self.univ_en_input.value or "",
                college_ar=self.college_ar_input.value or "",
                college_en=self.college_en_input.value or ""
            )
            ui.notify("تم حفظ معلومات المؤسسة بنجاح / Institution info saved!", type="positive")
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
        """Saves theme and appearance preferences to database for current EMP_ID session."""
        try:
            theme_val = str(self.theme_select.value or "Dark")
            accent_val = str(self.accent_select.value or "blue")
            font_val = str(self.font_select.value or "Segoe UI")
            size_val = int(self.font_size_input.value or 13)
            rtl_val = 1 if (self.rtl_switch.value if self.rtl_switch else True) else 0

            # Apply live mode
            dark_mode = ui.dark_mode()
            if theme_val == "Dark":
                dark_mode.enable()
            elif theme_val == "Light":
                dark_mode.disable()
            else:
                dark_mode.auto()

            # Save to repository via session EMP_ID
            self.s_repo.update_user_appearance(
                emp_id=self.emp_id,
                theme=theme_val,
                accent=accent_val,
                font=font_val,
                size=size_val,
                rtl=rtl_val
            )

            # Update session state in memory
            self.session.update_preferences(
                theme=theme_val,
                accent_color=accent_val,
                font_family=font_val,
                font_size_base=size_val,
                is_arabic_rtl=rtl_val
            )

            ui.notify("تم حفظ وتطبيق تفضيلات المظهر بنجاح / Appearance saved & applied!", type="positive")
        except Exception as exc:
            ui.notify(f"Error saving appearance: {exc}", type="negative")

    def _do_backup(self) -> None:
        try:
            backup_path = Path("certificate_manager_backup.sql")
            backup_db(backup_path)
            ui.notify("تم إنشاء النسخة الاحتياطية بنجاح / Backup created!", type="positive")
        except Exception as exc:
            ui.notify(f"Backup failed: {exc}", type="negative")

    def _do_restore(self) -> None:
        try:
            backup_path = Path("certificate_manager_backup.sql")
            restore_db(backup_path)
            ui.notify("تمت استعادة قاعدة البيانات / Database restored!", type="positive")
        except Exception as exc:
            ui.notify(f"Restore failed: {exc}", type="negative")

    def _do_import(self) -> None:
        try:
            trigger_migration("certificate_manager.sql")
            ui.notify("تمت عملية الاستيراد بنجاح / Legacy import finished!", type="positive")
        except Exception as exc:
            ui.notify(f"Import failed: {exc}", type="negative")

    def _do_clear_logs(self) -> None:
        try:
            self.s_repo.clear_audit_logs()
            ui.notify("تم مسح سجل التغييرات / Audit logs cleared!", type="info")
        except Exception as exc:
            ui.notify(f"Clear logs failed: {exc}", type="negative")
