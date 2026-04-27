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
from data.queries import get_settings, update_settings, clear_audit_logs
from db import backup_db, restore_db

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

        # --- Section 2: Appearance & Theme ---
        make_section_header(self._scroll_frame, "المظهر والسمات", "Appearance & Theme").grid(row=2, column=0, sticky="e", pady=(10, 20))
        
        theme_card = ctk.CTkFrame(self._scroll_frame, corner_radius=AppSizes.CORNER_RADIUS_CARD, border_width=1, border_color=AppColors.BORDER)
        theme_card.grid(row=3, column=0, sticky="ew", padx=5, pady=(0, 30))
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

        # --- Section 3: Database Maintenance ---
        make_section_header(self._scroll_frame, "صيانة قاعدة البيانات", "Database Maintenance").grid(row=4, column=0, sticky="e", pady=(10, 20))
        
        db_card = ctk.CTkFrame(self._scroll_frame, corner_radius=AppSizes.CORNER_RADIUS_CARD, border_width=1, border_color=AppColors.BORDER)
        db_card.grid(row=5, column=0, sticky="ew", padx=5, pady=(0, 30))
        db_card.grid_columnconfigure((0, 1), weight=1)

        # Backup
        ctk.CTkLabel(db_card, text="نسخ احتياطي لقاعدة البيانات\nBackup Database", font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY)).grid(row=0, column=1, padx=20, pady=20, sticky="e")
        make_primary_button(db_card, "إنشاء نسخة احتياطية", "Create Backup", command=self._handle_backup).grid(row=0, column=0, padx=20, pady=20, sticky="w")

        # Restore
        ctk.CTkLabel(db_card, text="استعادة نسخة احتياطية\nRestore Database", font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY)).grid(row=2, column=1, padx=20, pady=20, sticky="e")
        make_primary_button(db_card, "استعادة النسخة", "Restore Backup", command=self._handle_restore).grid(row=2, column=0, padx=20, pady=20, sticky="w")

        make_divider(db_card).grid(row=3, column=0, columnspan=2, sticky="ew", padx=20)

        # Clear Logs
        ctk.CTkLabel(db_card, text="مسح سجل التغييرات\nClear Audit Logs", font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY)).grid(row=4, column=1, padx=20, pady=20, sticky="e")
        make_danger_button(db_card, "مسح السجل", "Clear Logs", command=self._handle_clear_logs).grid(row=4, column=0, padx=20, pady=20, sticky="w")

        # --- Section 3: About ---
        make_section_header(self._scroll_frame, "حول البرنامج", "About").grid(row=6, column=0, sticky="e", pady=(10, 20))
        
        about_card = ctk.CTkFrame(self._scroll_frame, corner_radius=AppSizes.CORNER_RADIUS_CARD, border_width=1, border_color=AppColors.BORDER)
        about_card.grid(row=7, column=0, sticky="ew", padx=5, pady=(0, 30))
        
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

    def _save_info(self) -> None:
        self._do_save("تم حفظ معلومات المؤسسة بنجاح\nInstitution info saved successfully")

    def _save_visuals(self) -> None:
        self._do_save("تم تطبيق المظهر الجديد بنجاح (قد يتطلب إعادة تشغيل لبعض العناصر)\nTheme applied successfully (some elements may need restart)")
        from config import refresh_config
        refresh_config()

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
