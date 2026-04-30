# =============================================================================
# screens/settings_screen.py — Application Configuration Screen
# =============================================================================

import os
import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog
from config import AppFonts, AppColors, AppSizes
from ui.base_screen import BaseScreen
from ui.widgets import (
    make_section_header, make_labeled_entry, make_primary_button, 
    make_danger_button, make_divider
)
import threading
from data.queries import (
    get_settings, update_settings, clear_audit_logs,
    get_all_study_systems, update_study_system, 
    insert_study_system, delete_study_system
)
from db import backup_db, restore_db
from tools.migrate_mysql import run_migration

class SettingsScreen(BaseScreen):
    """
    Settings screen for global application control.
    Allows changing university names, database maintenance, and about info.
    """

    def __init__(self, parent, switch_callback):
        super().__init__(parent, switch_callback)

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        
        # Scrollable content area
        self._scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self._scroll_frame.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Section 1: General Info ---
        make_section_header(self._scroll_frame, "معلومات المؤسسة", "Institution Info").grid(row=0, column=0, sticky="e", pady=(10, 20))
        
        info_card = ctk.CTkFrame(self._scroll_frame, corner_radius=AppSizes.CORNER_RADIUS_CARD, border_width=1, border_color=AppColors.BORDER)
        info_card.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 30))
        info_card.grid_columnconfigure((0, 1), weight=1)

        self._univ_ar = make_labeled_entry(info_card, "اسم الجامعة بالعربية", "Univ. Name (AR)")
        self._univ_ar.container.grid(row=0, column=1, padx=20, pady=20, sticky="ew")

        self._univ_en = make_labeled_entry(info_card, "اسم الجامعة بالإنكليزية", "Univ. Name (EN)")
        self._univ_en.container.grid(row=0, column=0, padx=20, pady=20, sticky="ew")

        self._college_ar = make_labeled_entry(info_card, "اسم الكلية بالعربية", "College Name (AR)")
        self._college_ar.container.grid(row=1, column=1, padx=20, pady=(0, 20), sticky="ew")

        self._college_en = make_labeled_entry(info_card, "اسم الكلية بالإنكليزية", "College Name (EN)")
        self._college_en.container.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")

        make_primary_button(info_card, "حفظ الإعدادات", "Save Settings", command=self._save_info).grid(row=2, column=0, columnspan=2, pady=(0, 20))

        # --- Section 2: Study Systems ---
        make_section_header(self._scroll_frame, "أنظمة الدراسة", "Study Systems").grid(row=2, column=0, sticky="e", pady=(10, 20))
        
        self._systems_card = ctk.CTkFrame(self._scroll_frame, corner_radius=AppSizes.CORNER_RADIUS_CARD, border_width=1, border_color=AppColors.BORDER)
        self._systems_card.grid(row=3, column=0, sticky="ew", padx=5, pady=(0, 30))
        self._systems_card.grid_columnconfigure((1, 2), weight=1)

        # Headers
        ctk.CTkLabel(self._systems_card, text="القاعدة\nRule", font=ctk.CTkFont(family=AppFonts.FAMILY, size=11, weight="bold")).grid(row=0, column=0, padx=10, pady=10)
        ctk.CTkLabel(self._systems_card, text="الأوزان (%)\nWeights", font=ctk.CTkFont(family=AppFonts.FAMILY, size=11, weight="bold")).grid(row=0, column=1, padx=10, pady=10)
        ctk.CTkLabel(self._systems_card, text="العرض\nDisplay", font=ctk.CTkFont(family=AppFonts.FAMILY, size=11, weight="bold")).grid(row=0, column=2, padx=10, pady=10)
        ctk.CTkLabel(self._systems_card, text="البادئة\nPrefix", font=ctk.CTkFont(family=AppFonts.FAMILY, size=11, weight="bold")).grid(row=0, column=3, padx=10, pady=10)
        ctk.CTkLabel(self._systems_card, text="الاسم بالإنكليزية\nEnglish Name", font=ctk.CTkFont(family=AppFonts.FAMILY, size=11, weight="bold")).grid(row=0, column=4, padx=10, pady=10)
        ctk.CTkLabel(self._systems_card, text="الاسم بالعربية\nArabic Name", font=ctk.CTkFont(family=AppFonts.FAMILY, size=11, weight="bold")).grid(row=0, column=5, padx=10, pady=10)
        ctk.CTkLabel(self._systems_card, text="تفعيل\nActive", font=ctk.CTkFont(family=AppFonts.FAMILY, size=11, weight="bold")).grid(row=0, column=6, padx=10, pady=10)
        
        # Add Button in Header row
        ctk.CTkButton(self._systems_card, text="+", width=40, font=ctk.CTkFont(family=AppFonts.FAMILY, size=16, weight="bold"), 
                     fg_color=AppColors.COLOR_INFO, command=self._add_system).grid(row=0, column=5, padx=10, pady=10)

        self._system_rows = [] # list of (id, entry_ar, entry_en, rule_label, switch_active)
        
        # --- Section 3: Appearance & Theme ---
        make_section_header(self._scroll_frame, "المظهر والسمات", "Appearance & Theme").grid(row=4, column=0, sticky="e", pady=(10, 20))
        
        theme_card = ctk.CTkFrame(self._scroll_frame, corner_radius=AppSizes.CORNER_RADIUS_CARD, border_width=1, border_color=AppColors.BORDER)
        theme_card.grid(row=5, column=0, sticky="ew", padx=5, pady=(0, 30))
        theme_card.grid_columnconfigure((0, 1), weight=1)

        from ui.widgets import make_labeled_dropdown
        
        self._theme = make_labeled_dropdown(theme_card, "الوضع (فاتح/داكن)", "Theme Mode", values=["System", "Light", "Dark"])
        self._theme.container.grid(row=0, column=1, padx=20, pady=20, sticky="ew")

        self._accent = make_labeled_dropdown(theme_card, "اللون الأساسي", "Accent Color", values=["blue", "green", "dark-blue", "orange", "purple", "red"])
        self._accent.container.grid(row=0, column=0, padx=20, pady=20, sticky="ew")

        self._font = make_labeled_dropdown(theme_card, "نوع الخط", "Font Family", values=["Arial", "Segoe UI", "Roboto", "Cairo", "Tahoma"])
        self._font.container.grid(row=1, column=1, padx=20, pady=(0, 20), sticky="ew")

        self._font_size = make_labeled_entry(theme_card, "حجم الخط الأساسي", "Base Font Size")
        self._font_size.container.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")

        make_primary_button(theme_card, "حفظ وتطبيق المظهر", "Save & Apply Theme", command=self._save_visuals).grid(row=2, column=0, columnspan=2, pady=(0, 20))

        # --- Section 4: Database Maintenance ---
        make_section_header(self._scroll_frame, "صيانة قاعدة البيانات", "Database Maintenance").grid(row=6, column=0, sticky="e", pady=(10, 20))
        
        db_card = ctk.CTkFrame(self._scroll_frame, corner_radius=AppSizes.CORNER_RADIUS_CARD, border_width=1, border_color=AppColors.BORDER)
        db_card.grid(row=7, column=0, sticky="ew", padx=5, pady=(0, 30))
        db_card.grid_columnconfigure((0, 1), weight=1)

        # Backup
        ctk.CTkLabel(db_card, text="نسخ احتياطي لقاعدة البيانات\nBackup Database", font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY)).grid(row=0, column=1, padx=20, pady=20, sticky="e")
        make_primary_button(db_card, "إنشاء نسخة احتياطية", "Create Backup", command=self._handle_backup).grid(row=0, column=0, padx=20, pady=20, sticky="w")

        # Restore
        ctk.CTkLabel(db_card, text="استعادة نسخة احتياطية\nRestore Database", font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY)).grid(row=2, column=1, padx=20, pady=(20, 10), sticky="e")
        make_primary_button(db_card, "استعادة النسخة", "Restore Backup", command=self._handle_restore).grid(row=2, column=0, padx=20, pady=(20, 10), sticky="w")

        # Import Legacy
        ctk.CTkLabel(db_card, text="استيراد من النظام القديم\nImport Legacy MySQL (.sql)", font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY)).grid(row=3, column=1, padx=20, pady=(0, 20), sticky="e")
        make_primary_button(db_card, "استيراد البيانات", "Import Data", command=self._handle_import).grid(row=3, column=0, padx=20, pady=(0, 20), sticky="w")

        make_divider(db_card).grid(row=4, column=0, columnspan=2, sticky="ew", padx=20)

        # Clear Logs
        ctk.CTkLabel(db_card, text="مسح سجل التغييرات\nClear Audit Logs", font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY)).grid(row=5, column=1, padx=20, pady=20, sticky="e")
        make_danger_button(db_card, "مسح السجل", "Clear Logs", command=self._handle_clear_logs).grid(row=5, column=0, padx=20, pady=20, sticky="w")

        # --- Section 5: About ---
        make_section_header(self._scroll_frame, "حول البرنامج", "About").grid(row=8, column=0, sticky="e", pady=(10, 20))
        
        about_card = ctk.CTkFrame(self._scroll_frame, corner_radius=AppSizes.CORNER_RADIUS_CARD, border_width=1, border_color=AppColors.BORDER)
        about_card.grid(row=9, column=0, sticky="ew", padx=5, pady=(0, 30))
        
        about_text = (
            "نظام إدارة الشهادات - الإصدار 1.0\n"
            "Certificate Manager - v1.0\n\n"
            "تم التطوير لأتمتة عمليات إصدار الوثائق والشهادات الجامعية.\n"
            "Developed to automate university document and certificate issuance.\n\n"
            "تم تطوير البرنامج بواسطة المبرمج م. حسين \n"
            "Developed by the programmer M. Hussein"
        )
        ctk.CTkLabel(about_card, text=about_text, font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY), justify="center").pack(pady=30, padx=20)

    def refresh(self) -> None:
        """Load settings from the database."""
        settings = get_settings()
        self._univ_ar.delete(0, "end")
        self._univ_ar.insert(0, settings["univ_name_ar"])
        
        self._univ_en.delete(0, "end")
        self._univ_en.insert(0, settings["univ_name_en"])
        
        self._college_ar.delete(0, "end")
        self._college_ar.insert(0, settings["college_name_ar"])
        
        self._college_en.delete(0, "end")
        self._college_en.insert(0, settings["college_name_en"])

        self._theme.set(settings.get("theme", "System"))
        self._accent.set(settings.get("accent_color", "blue"))
        self._font.set(settings.get("font_family", "Arial"))
        self._font_size.delete(0, "end")
        self._font_size.insert(0, str(settings.get("font_size_base", 13)))

        # Load Study Systems — destroy all non-header children safely
        for widget in list(self._systems_card.winfo_children()):
            try:
                info = widget.grid_info()
                if info and int(info.get("row", 0)) > 0:
                    widget.destroy()
            except Exception:
                pass
        
        self._system_rows = []
        systems = get_all_study_systems()
        for i, s in enumerate(systems):
            row_idx = i + 1
            
            ent_ar = ctk.CTkEntry(self._systems_card, font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY), justify="right")
            ent_ar.insert(0, s["name_ar"])
            ent_ar.grid(row=row_idx, column=5, padx=10, pady=5, sticky="ew")
            
            ent_en = ctk.CTkEntry(self._systems_card, font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY), justify="left")
            ent_en.insert(0, s["name_en"])
            ent_en.grid(row=row_idx, column=4, padx=10, pady=5, sticky="ew")

            ent_prefix = ctk.CTkEntry(self._systems_card, font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY), width=70, placeholder_text="e.g. S")
            ent_prefix.insert(0, s.get("prefix", "") or "")
            ent_prefix.grid(row=row_idx, column=3, padx=10, pady=5, sticky="ew")

            period_menu = ctk.CTkOptionMenu(self._systems_card, values=["year", "semester"], width=90,
                                            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL))
            period_menu.set(s.get("period_display", "semester") or "semester")
            period_menu.grid(row=row_idx, column=2, padx=10, pady=5)

            ent_weights = ctk.CTkEntry(self._systems_card, font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY), width=100, placeholder_text="10:20:30:40")
            ent_weights.insert(0, s.get("calculation_weights", "10:20:30:40"))
            ent_weights.grid(row=row_idx, column=1, padx=10, pady=5, sticky="ew")
            
            rule_menu = ctk.CTkOptionMenu(self._systems_card, values=["annual", "semester"], width=100, font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL))
            rule_menu.set(s["calculation_rule"])
            rule_menu.grid(row=row_idx, column=0, padx=10, pady=5)
            
            sw_active = ctk.CTkSwitch(self._systems_card, text="", width=50)
            if s["is_active"]: sw_active.select()
            else: sw_active.deselect()
            sw_active.grid(row=row_idx, column=6, padx=10, pady=5)
            
            # Delete button
            del_btn = ctk.CTkButton(self._systems_card, text="X", width=30, fg_color="transparent", text_color=AppColors.COLOR_ERROR, 
                                   command=lambda sid=s["id"]: self._delete_system(sid))
            del_btn.grid(row=row_idx, column=7, padx=5, pady=5)

            self._system_rows.append({
                "id": s["id"],
                "ent_ar": ent_ar,
                "ent_en": ent_en,
                "ent_prefix": ent_prefix,
                "ent_weights": ent_weights,
                "rule_menu": rule_menu,
                "period_menu": period_menu,
                "sw": sw_active
            })
            
        make_primary_button(self._systems_card, "حفظ التعديلات", "Save Changes", command=self._save_systems).grid(row=len(systems)+1, column=0, columnspan=8, pady=20)

    def _save_info(self) -> None:
        self._do_save("تم حفظ معلومات المؤسسة بنجاح\nInstitution info saved successfully")

    def _save_visuals(self) -> None:
        self._do_save("تم تطبيق المظهر الجديد بنجاح (قد يتطلب إعادة تشغيل لبعض العناصر)\nTheme applied successfully (some elements may need restart)")
        from config import refresh_config
        refresh_config()

    def _save_systems(self) -> None:
        try:
            for row in self._system_rows:
                update_study_system(
                    ss_id=row["id"],
                    name_ar=row["ent_ar"].get().strip(),
                    name_en=row["ent_en"].get().strip(),
                    calculation_rule=row["rule_menu"].get(),
                    calculation_weights=row["ent_weights"].get().strip(),
                    is_active=1 if row["sw"].get() else 0,
                    prefix=row["ent_prefix"].get().strip(),
                    period_display=row["period_menu"].get(),
                )
            self.show_success("تم حفظ أنظمة الدراسة بنجاح\nStudy systems saved successfully")
            self.refresh()
        except Exception as e:
            self.show_error(f"Error saving study systems: {e}")

    def _add_system(self) -> None:
        """Adds a new study system via a dialog."""
        name_ar = ctk.CTkInputDialog(text="أدخل اسم النظام الجديد (عربي):\nEnter new system name (Arabic):", title="نظام جديد").get_input()
        if not name_ar: return
        
        name_en = ctk.CTkInputDialog(text="أدخل اسم النظام الجديد (English):\nEnter new system name (English):", title="New System").get_input()
        if not name_en: return
        
        rule = ctk.CTkInputDialog(text="أدخل قاعدة الحساب (annual / semester):\nEnter calculation rule (annual / semester):", title="Rule").get_input()
        if not rule or rule.lower() not in ["annual", "semester"]:
            self.show_error("القاعدة يجب أن تكون annual أو semester\nRule must be 'annual' or 'semester'")
            return

        period = ctk.CTkInputDialog(text="كيف يعرض جدول الدرجات؟ (year / semester):\nHow is the degree table displayed? (year / semester):", title="Period Display").get_input() or "semester"
        if period.lower() not in ["year", "semester"]:
            period = "semester"

        prefix = ctk.CTkInputDialog(text="أدخل البادئة (اختياري، مثال: S أو A):\nEnter prefix (optional, e.g. S or A):", title="Prefix").get_input() or ""
            
        weights = ctk.CTkInputDialog(text="أدخل الأوزان (مثال 10:20:30:40):\nEnter weights (e.g. 10:20:30:40):", title="Weights").get_input() or "10:20:30:40"

        try:
            insert_study_system(name_ar, name_en, rule.lower(), weights)
            self.show_success("تمت الإضافة بنجاح\nAdded successfully")
            self.refresh()
        except Exception as e:
            self.show_error(f"Failed to add system: {e}")

    def _delete_system(self, ss_id: int) -> None:
        """Deletes a study system if not in use."""
        self.show_confirm(
            message="هل أنت متأكد من حذف هذا النظام؟ لا يمكن الحذف إذا كان مرتبطاً بطلاب أو مواد.\nAre you sure? Cannot delete if linked to students or courses.",
            on_confirm=lambda: self._do_delete_system(ss_id)
        )

    def _do_delete_system(self, ss_id: int) -> None:
        try:
            success = delete_study_system(ss_id)
            if success:
                self.show_success("تم الحذف بنجاح\nDeleted successfully")
                self.refresh()
            else:
                self.show_error("لا يمكن حذف النظام لأنه مستخدم حالياً\nCannot delete: system is in use")
        except Exception as e:
            self.show_error(f"Error deleting system: {e}")

    def _do_save(self, success_msg: str) -> None:
        try:
            update_settings(
                univ_ar=self._univ_ar.get(),
                univ_en=self._univ_en.get(),
                college_ar=self._college_ar.get(),
                college_en=self._college_en.get(),
                theme=self._theme.get(),
                accent=self._accent.get(),
                font=self._font.get(),
                size=int(self._font_size.get() or 13)
            )
            self.show_success(success_msg)
        except Exception as e:
            self.show_error(f"Error saving settings: {e}")

    def _handle_backup(self) -> None:
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".db",
                filetypes=[("SQLite Database", "*.db")],
                initialfile="certificate_manager_backup.db"
            )
            if file_path:
                backup_db(Path(file_path))
                self.show_success("تم إنشاء النسخة الاحتياطية بنجاح\nBackup created successfully")
        except Exception as e:
            self.show_error(f"Backup failed: {e}")

    def _handle_restore(self) -> None:
        try:
            file_path = filedialog.askopenfilename(
                title="اختر ملف نسخة احتياطية  /  Select Backup File",
                defaultextension=".db",
                filetypes=[("SQLite Database", "*.db")]
            )
            if file_path:
                self.show_confirm(
                    message=f"هل أنت متأكد من استعادة قاعدة البيانات من الملف:\n{os.path.basename(file_path)}؟\nسيتم استبدال جميع البيانات الحالية.",
                    on_confirm=lambda: self._do_restore(file_path)
                )
        except Exception as e:
            self.show_error(f"Error opening file picker: {e}")

    def _do_restore(self, file_path: str) -> None:
        try:
            restore_db(Path(file_path))
            self.show_success("تم استعادة قاعدة البيانات بنجاح. يرجى إعادة تشغيل البرنامج لتطبيق التغييرات.\nDatabase restored successfully. Please restart the app to apply changes.")
        except Exception as e:
            self.show_error(f"Restore failed: {e}\n(تأكد من إغلاق أي نوافذ أخرى قد تستخدم قاعدة البيانات)")

    def _handle_clear_logs(self) -> None:
        self.show_confirm(
            message="هل أنت متأكد من مسح جميع سجلات التغييرات؟ لا يمكن التراجع عن هذا الإجراء.\nAre you sure you want to clear all audit logs? This cannot be undone.",
            on_confirm=self._do_clear_logs
        )

    def _do_clear_logs(self) -> None:
        try:
            clear_audit_logs()
            self.show_success("تم مسح السجل بنجاح\nLogs cleared successfully")
        except Exception as e:
            self.show_error(f"Error clearing logs: {e}")
    def _handle_import(self) -> None:
        """Opens a file picker and starts the migration."""
        file_path = filedialog.askopenfilename(
            title="اختر ملف SQL للنظام القديم  /  Select Legacy SQL File",
            filetypes=[("SQL Dump", "*.sql")]
        )
        if file_path:
            self.show_confirm(
                message=f"هل أنت متأكد من استيراد البيانات من الملف:\n{os.path.basename(file_path)}؟\nسيتم إضافة البيانات الجديدة إلى قاعدة البيانات الحالية.",
                on_confirm=lambda: self._start_import_thread(file_path)
            )

    def _start_import_thread(self, sql_path: str) -> None:
        """Runs the migration in a background thread."""
        self.show_info("جاري استيراد البيانات، يرجى الانتظار...\nImporting data, please wait...")
        threading.Thread(target=self._run_migration_task, args=(sql_path,), daemon=True).start()

    def _run_migration_task(self, sql_path: str) -> None:
        try:
            run_migration(sql_path)
            # Use after() to show success on main thread
            self.after(0, lambda: self.show_success("تم استيراد البيانات بنجاح!\nData imported successfully!"))
            self.after(0, self.refresh)
        except Exception as e:
            self.after(0, lambda err=e: self.show_error(f"فشل الاستيراد:\n{err}\nImport failed."))
