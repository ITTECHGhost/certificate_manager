# =============================================================================
# nicegui_screens/settings_screen.py — NiceGUI Settings Screen
#
# Visual styling: CSS hook classes (app-*) from theme.css
# This file contains ONLY structural layout classes (w-*, h-*, p-*, gap-*, flex, etc.)
# =============================================================================

from pathlib import Path
from nicegui import ui
from data.repositories import SettingsRepository, StudySystemRepository
from db import backup_db, restore_db
from tools.migrate_mysql import trigger_migration
from nicegui_ui.ui_components import UI
from nicegui_ui.state import get_user_session


class SettingsScreen:
    """
    NiceGUI Settings Screen.
    Renders inside the MainAppShell scroll content area.
    """

    def __init__(self, on_notify=None) -> None:
        self.s_repo = SettingsRepository()
        self.sys_repo = StudySystemRepository()
        self.on_notify = on_notify or (lambda msg, typ="positive": ui.notify(msg, type=typ))

        self.session = get_user_session()
        self.emp_id = self.session.emp_id

        self.settings_data: dict = {}
        self.appearance_data: dict = {}
        self.systems: list = []

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

    def _load_data(self) -> None:
        """Fetch current settings and study systems. Appearance comes from session preferences."""
        try:
            self.settings_data = self.s_repo.get_settings() or {}
            self.systems = self.sys_repo.get_all() or []
            # Appearance_data is not used for defaults — session.preferences is the source of truth.
            # We load it only to sync it back if the DB has fresher values than the session.
            db_appearance = self.s_repo.get_user_appearance(self.emp_id) or {}
            if db_appearance:
                # Only update session if DB returned real non-default values
                pref = self.session.preferences
                for key in ("theme", "accent_color", "font_family", "font_size_base", "is_arabic_rtl"):
                    db_val = db_appearance.get(key)
                    if db_val is not None:
                        pref[key] = db_val
        except Exception as exc:
            print(f"[SettingsScreen] Error loading settings data: {exc}")

    def _apply_initial_theme(self) -> None:
        """Applies saved theme preference on screen load."""
        self.session.apply_theme_mode()

    def _build_ui(self) -> None:
        """Build the settings screen layout using the UI factory."""
        with ui.column().classes("w-full gap-6 pb-12"):
            self._section_institution_info()
            self._section_study_systems()
            self._section_appearance()
            self._section_database_maintenance()
            self._section_about()

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
                    "اسم الكلية بالإنكليزية / College Name (EN)",
                    value=self.settings_data.get("college_name_en") or ""
                )

            UI.primary_button(
                "حفظ معلومات المؤسسة / Save Info",
                icon="save",
                on_click=self._save_institution_info
            ).classes("self-end")

    def _section_study_systems(self) -> None:
        with UI.card():
            with ui.row().classes("w-full justify-between items-center pb-3 app-card-header"):
                UI.section_label("أنظمة الدراسة — Study Systems")
                ui.button("+ إضافة نظام", on_click=self._add_study_system).classes(
                    "app-btn-secondary text-sm px-4 py-2 rounded-lg normal-case font-medium"
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
                {"name": "actions", "label": "",                         "field": "actions", "align": "right"},
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
                        dense
                    />
                </q-td>
            ''')
            table.add_slot('body-cell-actions', '''
                <q-td :props="props" class="text-right">
                    <q-btn
                        icon="delete"
                        flat round dense size="xs"
                        class="app-text-error"
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
            saved_theme  = str(pref.get("theme", "Dark"))
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
                    value=saved_theme
                )
                self.theme_select.on("update:model-value", self._on_theme_select_change)

                self.accent_select = UI.select(
                    "اللون الأساسي / Accent Color",
                    options=valid_accents,
                    value=saved_accent
                )
                self.accent_select.on("update:model-value", self._on_accent_select_change)

                self.font_select = UI.select(
                    "نوع الخط / Font Family",
                    options=["Arial", "Segoe UI", "Roboto", "Cairo", "Tahoma"],
                    value=saved_font
                )
                self.font_select.on("update:model-value", self._on_font_select_change)

                self.font_size_input = UI.number_input(
                    "حجم الخط الأساسي / Base Font Size",
                    value=saved_size, min=10, max=24
                )
                self.font_size_input.on("update:model-value", self._on_font_size_change)

            with ui.row().classes("app-tile w-full items-center justify-between p-3 rounded-xl border"):
                UI.standard_label("اتجاه الواجهة من اليمين إلى اليسار / Arabic RTL Layout")
                self.rtl_switch = UI.switch("تفعيل RTL / Enable RTL", value=bool(saved_rtl))

            UI.primary_button(
                "حفظ وتطبيق المظهر / Save Appearance",
                icon="brush",
                on_click=self._save_appearance
            ).classes("self-end")

    def _section_database_maintenance(self) -> None:
        with UI.card():
            UI.card_header("صيانة قاعدة البيانات — Database Maintenance", "storage", icon_css="stat-text-amber")

            with ui.grid(columns=2).classes("w-full gap-4"):
                UI.action_tile(
                    "نسخ احتياطي لقاعدة البيانات / Backup Database",
                    "إنشاء نسخة SQL احتياطية حفظاً للبيانات",
                    "إنشاء نسخة احتياطية / Create Backup",
                    "backup", btn_variant="primary", on_click_fn=self._do_backup
                )
                UI.action_tile(
                    "استعادة نسخة احتياطية / Restore Database",
                    "استرجاع البيانات من ملف .sql سابق",
                    "استعادة النسخة / Restore Backup",
                    "restore", btn_variant="warning", on_click_fn=self._do_restore
                )
                UI.action_tile(
                    "استيراد من النظام القديم / Import Legacy MySQL",
                    "نقل وسحب البيانات القديمة تلقائياً",
                    "استيراد البيانات / Import Data",
                    "upload_file", btn_variant="success", on_click_fn=self._do_import
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

    def _on_theme_select_change(self, e=None) -> None:
        """Live theme switch when Theme Mode dropdown option changes."""
        from nicegui_ui.ui_theme import is_windows_dark_mode, set_dark_mode
        val = str((self.theme_select.value if self.theme_select else None) or "Dark")
        if val == "Dark":
            set_dark_mode(True)
        elif val == "Light":
            set_dark_mode(False)
        else:
            set_dark_mode(is_windows_dark_mode())

        ui.notify(
            f"تم تغيير المظهر إلى {'الداكن' if val == 'Dark' else ('الفاتح' if val == 'Light' else 'النظام')} / Theme set to {val}!",
            type="info"
        )

    def _on_accent_select_change(self, e=None) -> None:
        """Live accent palette switch when Accent Color dropdown option changes."""
        from nicegui_ui.ui_theme import set_accent
        val = str((self.accent_select.value if self.accent_select else None) or "blue")
        set_accent(val)
        ui.notify(f"تم تغيير اللون الأساسي / Accent set to {val}!", type="info")

    def _on_font_select_change(self, e=None) -> None:
        """Live font family switch when Font Family dropdown option changes."""
        from nicegui_ui.ui_theme import set_font_family
        val = str((self.font_select.value if self.font_select else None) or "Segoe UI")
        set_font_family(val)
        ui.notify(f"تم تغيير نوع الخط إلى {val} / Font family set to {val}!", type="info")

    def _on_font_size_change(self, e=None) -> None:
        """Live base font size scale when Base Font Size number input changes."""
        from nicegui_ui.ui_theme import set_font_size
        try:
            val = int((self.font_size_input.value if self.font_size_input else None) or 13)
            set_font_size(val)
        except Exception:
            pass

    def _save_institution_info(self) -> None:
        try:
            self.s_repo.update_settings(
                univ_ar=(self.univ_ar_input.value if self.univ_ar_input else "") or "",
                univ_en=(self.univ_en_input.value if self.univ_en_input else "") or "",
                college_ar=(self.college_ar_input.value if self.college_ar_input else "") or "",
                college_en=(self.college_en_input.value if self.college_en_input else "") or ""
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
        try:
            theme_val = str((self.theme_select.value if self.theme_select else None) or "Dark")
            accent_val = str((self.accent_select.value if self.accent_select else None) or "blue")
            font_val = str((self.font_select.value if self.font_select else None) or "Arial")
            size_val = int((self.font_size_input.value if self.font_size_input else None) or 14)
            rtl_val = 1 if (self.rtl_switch.value if self.rtl_switch else True) else 0

            dark_mode = ui.dark_mode()
            if theme_val == "Dark":
                dark_mode.enable()
            elif theme_val == "Light":
                dark_mode.disable()
            else:
                dark_mode.auto()


            self.s_repo.update_user_appearance(
                emp_id=self.emp_id,
                theme=theme_val,
                accent=accent_val,
                font=font_val,
                size=size_val,
                rtl=rtl_val
            )

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
