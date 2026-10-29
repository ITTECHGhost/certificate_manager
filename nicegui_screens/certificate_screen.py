# =============================================================================
# nicegui_screens/certificate_screen.py — Certificate Issuance & Generation Screen
# =============================================================================

import os
import re
import logging
import asyncio
import urllib.parse
from itertools import zip_longest
from docxtpl import DocxTemplate
from nicegui import ui

import app_paths

from nicegui_ui.ui_components import UI
from nicegui_ui.template_constants import get_friendly_template_name
from data.repositories import StudentRepository, CertificateRepository, PersonnelRepository, IssuedCertificateRepository
from data.repositories.certificates import CertificateRejected
from nicegui_screens.graduation_orders_screen import extract_event_value

from services.certificate_context import (
    parse_stage_num, safe_int_val, consolidate_courses_for_certificate, consolidate_course_history,
    to_arabic_num, format_date_rtl, format_academic_year_ltr, get_subj_display, build_certificate_context,
)
from services.office_automation import (
    generate_pdf_from_docx, warm_up_word, get_installed_printers, get_default_printer,
    print_file_to_printer,
)

log = logging.getLogger(__name__)


# Register static path for certificates preview in NiceGUI
_cert_dir = str(app_paths.data_path("certificates"))
os.makedirs(_cert_dir, exist_ok=True)
try:
    from nicegui import app
    app.add_static_files('/certificates_files', _cert_dir)
except Exception:
    pass


class CertificateScreen:
    """
    Certificate Generation & Issuance Screen (NiceGUI version).
    Uses separated full-width sub-views for Student Profile/Transcript and Certificate Print Options.
    """

    def __init__(self, on_edit_student=None, initial_student=None, initial_cert_record=None):
        self.on_edit_student = on_edit_student
        warm_up_word()  # start the hidden Word now so the first preview is fast
        self.initial_cert_record = initial_cert_record
        self.reissue_cert_id = (initial_cert_record.get("certificate_id") or initial_cert_record.get("id")) if initial_cert_record else None
        self.student_repo = StudentRepository()
        self.cert_repo = CertificateRepository()
        self.personnel_repo = PersonnelRepository()
        self.issued_cert_repo = IssuedCertificateRepository()

        self.selected_student = None
        self.student_full_data = None
        self.generated_file_path = None
        self.current_grouping_mode = "DEFAULT"

        self.templates_dir = str(app_paths.data_path("templets"))
        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir, exist_ok=True)

        self.container = ui.column().classes("w-full h-full p-6 gap-6 overflow-y-auto")
        self.build_ui()

        if initial_student:
            self.select_student(initial_student)

    def _format_template_options(self, template_files: list[str]) -> dict:
        """Maps raw template filenames to friendly Arabic/bilingual display labels."""
        return {
            t: (get_friendly_template_name(t, include_file=True) if t and not t.startswith("لا توجد") else t)
            for t in template_files
        }

    def render_screen(self):
        """Re-renders the screen container while preserving the currently selected student data."""
        self.build_ui()
        if self.student_full_data:
            self.update_student_ui()
            filtered_templates = self.get_templates(self.student_full_data)
            if hasattr(self, "template_sel") and self.template_sel:
                self.template_sel.options = self._format_template_options(filtered_templates)
                self.template_sel.value = filtered_templates[0] if filtered_templates else None
                self.template_sel.update()
            self.show_info_view()
            if hasattr(self, "render_preview_grid"):
                self.render_preview_grid()

    def get_templates(self, data: dict = None) -> list[str]:
        """
        Returns docx templates filtered by the student's study system (semester vs year/annual).
        If the student is semester-based ('semester'), returns templates matching 'semester' or 'sem'.
        If the student is annual/year-based ('year' / 'annual'), returns templates matching 'year' or 'annual'.
        """
        try:
            files = [f for f in os.listdir(self.templates_dir) if f.endswith(".docx") and not f.startswith("~")]
            if not files:
                return ["لا توجد قوالب / No templates found"]

            if not data:
                data = self.student_full_data or {}

            period_disp = str(data.get("period_display") or "").lower().strip()
            calc_rule = str(data.get("calculation_rule") or "").lower().strip()

            if "semester" in period_disp or "semester" in calc_rule:
                system_keys = ["semester", "sem"]
            elif "year" in period_disp or "annual" in calc_rule or "year" in calc_rule:
                system_keys = ["year", "annual"]
            else:
                system_keys = []

            if system_keys:
                matching = [f for f in files if any(k in f.lower() for k in system_keys)]
                if matching:
                    return matching

            return files
        except Exception:
            return ["لا توجد قوالب / No templates found"]

    def build_ui(self):
        self.container.clear()
        with self.container:
            # ── Top Bar: Search Field Card with Live Inline Results Dropdown ────
            with UI.card().classes("w-full p-5 gap-4 shrink-0 bg-[var(--bg-card)] border border-[var(--border-default)] rounded-2xl"):
                with ui.row().classes("w-full justify-between items-center flex-wrap gap-4"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("school", size="md").classes("app-text-accent")
                        with ui.column().classes("gap-0"):
                            ui.label("إصدار الوثيقة — Issue Certificate").classes("text-xl font-bold app-text-primary")
                            ui.label("البحث عن الطالب، عرض السجل الأكاديمي، وتخصيص إعدادات الطباعة وتوليد قوالب Word").classes("text-xs app-text-muted")

                    # Search Box Container with Live Auto-Complete Results Below
                    with ui.column().classes("flex-1 max-w-2xl min-w-[320px] gap-2"):
                        with ui.row().classes("w-full items-center gap-3"):
                            def on_search(e=None):
                                val = extract_event_value(e, default="")
                                if not val and hasattr(self, "search_input") and self.search_input:
                                    val = self.search_input.value
                                self.search_term = str(val or "").strip()
                                self.perform_search()

                            self.search_input = UI.text_input(
                                label="",
                                placeholder="ابحث باسم الطالب (عربي أو إنكليزي)...",
                                on_change=on_search
                            ).classes("flex-1 text-sm")
                            self.search_input.on("keydown.enter", lambda: self.perform_search())

                            UI.primary_button("بحث / Search", icon="search", on_click=lambda: self.perform_search()).classes("px-5 py-2.5 text-sm")

                        # Live Search Results Card right below input
                        self.search_results_card = ui.column().classes("w-full pt-2 gap-2 border-t border-[var(--border-default)] mt-2")
                        self.search_results_card.set_visibility(False)
                        with self.search_results_card:
                            self.search_results_container = ui.column().classes("w-full max-h-[300px] overflow-y-auto gap-2")

            # ── Main Content Container (Separated Sub-Views) ───────────────────
            self.main_content_card = UI.card().classes("w-full flex-1 p-6 gap-6 border border-[var(--border-default)] bg-[var(--bg-card)] rounded-2xl min-h-0")
            with self.main_content_card:
                # ── SUB-VIEW 1: Student Info & Transcript ──────────────────────
                self.view_student_info = ui.column().classes("w-full gap-6")
                with self.view_student_info:
                    self.student_info_container = ui.column().classes("w-full gap-6")
                    self.render_empty_student_info()

                # ── SUB-VIEW 2: Print Settings & Certificate Options ───────────
                self.view_print_options = ui.column().classes("w-full gap-6")
                self.view_print_options.set_visibility(False)
                with self.view_print_options:
                    # Options View Header
                    with ui.row().classes("w-full justify-between items-center pb-3 border-b border-[var(--border-default)]"):
                        with ui.column().classes("gap-0"):
                            ui.label("إعدادات طباعة وثيقة الطالب وقوالب Word").classes("text-lg font-bold app-text-primary")
                            ui.label("ضبط الخيارات المستثناة، الأمر الجامعي، الترتيب وتخصيص القالب").classes("text-xs app-text-muted")

                        UI.primary_button("العودة لبيانات الطالب / Back to Student", icon="arrow_forward", on_click=self.show_info_view).classes("text-xs px-4 py-2 font-bold")

                    # Edit Mode Banner (Visible when editing an existing certificate record)
                    self.edit_mode_banner = ui.row().classes(
                        "w-full p-3.5 rounded-xl bg-amber-500/15 border border-amber-500/40 items-center justify-between shadow-sm"
                    )
                    self.edit_mode_banner.set_visibility(False)
                    with self.edit_mode_banner:
                        with ui.row().classes("items-center gap-2.5"):
                            ui.icon("edit_document", size="sm").classes("text-amber-400 text-lg")
                            with ui.column().classes("gap-0"):
                                self.edit_mode_label = ui.label("تعديل قيد الوثيقة / Editing Certificate Record").classes(
                                    "text-sm font-bold text-amber-300"
                                )
                                ui.label("سيتم تحديث سجل الوثيقة في قاعدة البيانات مباشرة عند التوليد والحفظ").classes(
                                    "text-[11px] text-amber-200/70"
                                )
                        ui.badge("وضع التعديل / Edit Mode", color="amber-700").classes("text-xs font-bold px-2.5 py-1")

                    # Row 1: Template Selector + Issued To + Edit Student (3 Components in 1 Row)
                    with ui.row().classes("w-full gap-4 items-center"):
                        initial_templates = self.get_templates()
                        self.template_sel = UI.select(
                            "قالب الوثيقة / Certificate Template",
                            options=self._format_template_options(initial_templates),
                            value=initial_templates[0] if initial_templates else None
                        ).classes("flex-1 text-sm")

                        self.to_input = UI.text_input(
                            "إلى (الجهة المعنية) / Issued To",
                            value="من يهمه الأمر",
                            placeholder="اسم الجهة الموجه إليها..."
                        ).classes("flex-1 text-sm")
                        
                        def on_grouping_change(e):
                            if not hasattr(self, 'student_full_data') or not self.student_full_data: return
                            student_id = self.student_full_data.get('student_id') or self.student_full_data.get('id')
                            if not student_id: return
                            new_mode = getattr(e, 'value', e) or "DEFAULT"
                            self.current_grouping_mode = new_mode
                            self.student_full_data = self.cert_repo.get_full_certificate_data(student_id, grouping_mode=new_mode)
                            self.update_student_ui()

                        grouping_options = {
                            "DEFAULT": "الافتراضي - سنوي",
                            "BY_PERIOD_STAGE": "سنوي - حسب المرحلة الدراسية",
                            "BY_CURRICULUM_STAGE": "سنوي - حسب مرحلة المادة",
                            "BY_ByAcademicYear": "سنوي - حسب سنة الإنجاز",
                            "BY_SEMESTER_stage": "مقررات - حسب المرحلة",
                            "BY_SEMESTER_year": "مقررات - حسب السنة"
                        }
                        self.grouping_sel = UI.select(
                            "نمط التجميع / Grouping",
                            options=grouping_options,
                            value="DEFAULT",
                            on_change=on_grouping_change
                        ).classes("flex-1 text-sm")

                        UI.primary_button("تعديل الطالب / Edit", icon="edit", on_click=self.handle_edit_student).classes("text-sm px-4 py-3.5 mt-2")

                    # Row 1.5: Certificate Registry Info (Certificate Number & Auto Issue Date in 1 Row)
                    with ui.row().classes("w-full gap-4 items-center flex-nowrap"):
                        with ui.row().classes("flex-1 min-w-0 gap-2 items-center flex-nowrap"):
                            init_cert_num = self.issued_cert_repo.get_next_number()
                            self.cert_number_input = UI.text_input(
                                "رقم الوثيقة / Certificate Number",
                                value=init_cert_num,
                                placeholder="مثال: 420/44 أو 105"
                            ).classes("flex-1 min-w-0 text-sm")

                            def _refresh_cert_number():
                                next_num = self.issued_cert_repo.get_next_number()
                                self.cert_number_input.value = next_num
                                UI.notify(f"تم تحديث الرقم المقترح: {next_num}", type="info")

                            ui.button(icon="autorenew", on_click=_refresh_cert_number).classes(
                                "p-2.5 mt-2 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 shadow-none hover:bg-slate-300 dark:hover:bg-slate-700 shrink-0"
                            ).tooltip("توليد الرقم التالي تلقائياً / Auto-Generate Next Number")

                        from datetime import datetime
                        today_str = datetime.now().strftime("%Y-%m-%d")
                        self.issue_date_input = UI.text_input(
                            "تاريخ الإصدار / Issue Date (تلقائي اليوم)",
                            value=today_str
                        ).classes("flex-1 min-w-0 text-sm").props("readonly")

                    ui.separator().classes("my-1")

                    # Row 2: University Order Section (3 Components in 1 Row)
                    with UI.card().classes("w-full p-4 gap-3 bg-[var(--bg-main)] rounded-xl border border-[var(--border-default)]"):
                        ui.label("بيانات الأمر الجامعي — University Order").classes("text-xs font-bold app-text-accent")
                        with ui.row().classes("w-full gap-4 items-center"):
                            self.sw_order = UI.switch("تفعيل الأمر الجامعي / Enable Order", value=False).classes("w-64")
                            self.inp_order_num = UI.text_input("رقم الأمر الجامعي / Order No", value="").classes("flex-1 text-sm")
                            self.inp_order_date = UI.text_input("تاريخ الأمر / Order Date", value="").classes("flex-1 text-sm")

                    # Row 3: Graduation Rank Section (5 Components in 1 Row)
                    with UI.card().classes("w-full p-4 gap-3 bg-[var(--bg-main)] rounded-xl border border-[var(--border-default)]"):
                        ui.label("بيانات تسلسل التخرج والترتيب — Graduation Rank").classes("text-xs font-bold app-text-accent")
                        with ui.row().classes("w-full gap-4 items-center"):
                            self.sw_rank = UI.switch("تفعيل تسلسل التخرج / Enable Rank", value=False).classes("w-52")
                            self.inp_rank_val = UI.text_input("تسلسل الطالب / Rank", value="").classes("flex-1 text-sm")

                            def on_rank_source_change(e):
                                if not hasattr(self, "student_full_data") or not self.student_full_data: return
                                src = e.value
                                order_cnt = self.student_full_data.get("order_num_students")
                                custom_cnt = self.student_full_data.get("postgraduation_number")
                                db_cnt = self.student_full_data.get("db_total_graduates")

                                if src == "custom":
                                    sel_val = custom_cnt if custom_cnt is not None and str(custom_cnt).strip() != "" else ""
                                elif src == "order":
                                    sel_val = order_cnt if order_cnt is not None and str(order_cnt).strip() != "" else ""
                                elif src == "db":
                                    sel_val = db_cnt if db_cnt is not None and str(db_cnt).strip() != "" else ""
                                else:
                                    sel_val = ""

                                self.inp_rank_total.value = str(sel_val) if sel_val != "" else ""
                                self.student_full_data["total_graduates"] = sel_val
                                rank_v = self.inp_rank_val.value or self.student_full_data.get("rank")
                                if hasattr(self, "rank_str_label") and self.rank_str_label:
                                    self.rank_str_label.text = f"المرتبة {rank_v} من {sel_val} خريج" if rank_v and sel_val != "" else "—"

                            self.rank_source_sel = UI.select(
                                "مصدر العدد / Count Source",
                                options={
                                    "order": "الأمر الجامعي / Order Count",
                                    "custom": "يدوي للطالب / Total Postgrad Students",
                                    "db": "قاعدة البيانات / DB Count"
                                },
                                value="order",
                                on_change=on_rank_source_change
                            ).classes("flex-1 text-sm")

                            self.inp_rank_total = UI.text_input("إجمالي المتخرجين / Total", value="").classes("flex-1 text-sm")
                            self.inp_rank_avg = UI.text_input("معدل الطالب الأول / Top Avg", value="").classes("flex-1 text-sm")

                    # Row 4: Academic Exceptions Grid (3 Cards Grid)
                    with ui.grid(columns=3).classes("w-full gap-4"):
                        # Card 1: Summer Training
                        with UI.card().classes("p-4 gap-2 bg-[var(--bg-main)] rounded-xl border border-[var(--border-default)]"):
                            self.sw_summer = UI.switch("التدريب الصيفي / Summer Training", value=False)
                            self.inp_summer_year = UI.text_input("سنة التدريب / Training Year", value="").classes("w-full text-sm mt-1")

                        # Card 2: Postponed Years
                        with UI.card().classes("p-4 gap-2 bg-[var(--bg-main)] rounded-xl border border-[var(--border-default)]"):
                            self.sw_postpone = UI.switch("سنوات التأجيل / Postponed Years", value=False)
                            self.inp_postpone_years = UI.text_input("سنوات التأجيل / Postponed Years", value="").classes("w-full text-sm mt-1")

                        # Card 3: Second Trial Subjects
                        with UI.card().classes("p-4 gap-2 bg-[var(--bg-main)] rounded-xl border border-[var(--border-default)]"):
                            self.sw_second = UI.switch("الدور الثاني / Second Trial", value=False)
                            self.inp_second_subjects = UI.text_input("مواد الدور الثاني / Subjects", value="").classes("w-full text-sm mt-1")

                    ui.separator().classes("my-2")

                    # Row 5: Primary Action Buttons
                    with ui.row().classes("w-full gap-4 items-center pt-2"):
                        self.btn_generate = UI.success_button(
                            "إصدار وتوليد الوثيقة (Word)",
                            icon="description",
                            on_click=self.generate_and_open_word
                        ).classes("flex-1 py-3 text-base font-bold")

                        self.btn_open = UI.primary_button(
                            "إصدار ومعاينة PDF والطباعة",
                            icon="print",
                            on_click=self.print_certificate
                        ).classes("flex-1 py-3 text-base")

                        UI.primary_button("العودة لبيانات الطالب", icon="arrow_forward", on_click=self.show_info_view).classes("px-6 py-3 text-sm")

    def show_info_view(self):
        self.view_print_options.set_visibility(False)
        self.view_student_info.set_visibility(True)

    def show_options_view(self):
        self.view_student_info.set_visibility(False)
        self.view_print_options.set_visibility(True)

    def perform_search(self):
        term = ""
        if hasattr(self, "search_input") and self.search_input and self.search_input.value:
            term = str(self.search_input.value).strip()
        elif hasattr(self, "search_term") and self.search_term:
            term = str(self.search_term).strip()

        if len(term) < 2:
            if hasattr(self, "search_results_card"):
                self.search_results_card.set_visibility(False)
            return

        try:
            results = self.student_repo.search(term, limit=12)
            self.search_results_container.clear()

            if not results:
                with self.search_results_container:
                    ui.label("لم يتم العثور على طالب بهذا الاسم / No matching student found").classes(
                        "text-xs app-text-muted italic p-4 text-center w-full"
                    )
                self.search_results_card.set_visibility(True)
                return

            with self.search_results_container:
                for row in results:
                    dept = row.get("dept_name_ar", "")
                    year = str(row.get("graduation_year") or row.get("admission_year", ""))

                    item = ui.row().classes(
                        "w-full justify-between items-center p-3 rounded-xl hover:bg-[var(--bg-main)] "
                        "cursor-pointer border border-[var(--border-default)] transition-all bg-[var(--bg-card)] shadow-sm"
                    )
                    item.on("click", lambda r=row: self.select_student(r))

                    with item:
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("account_circle", size="md").classes("app-text-accent")
                            with ui.column().classes("gap-0"):
                                ui.label(row.get("full_name_ar", "")).classes("font-bold text-sm app-text-primary")
                                ui.label(row.get("full_name_en", "")).classes("text-xs app-text-muted font-mono")

                        with ui.column().classes("items-end gap-0"):
                            ui.label(dept).classes("text-xs font-bold app-text-accent")
                            ui.label(f"دفعة {year}").classes("text-xs app-text-muted")

            self.search_results_card.set_visibility(True)
        except Exception as e:
            log.error(f"Search failed: {e}")
            UI.notify(f"خطأ في البحث: {e}", type="negative")

    def render_preview_grid(self):
        pass

    def render_empty_student_info(self):
        self.student_info_container.clear()
        with self.student_info_container:
            with ui.column().classes("w-full items-center justify-center p-16 gap-3 app-text-muted"):
                ui.icon("manage_search", size="lg").classes("opacity-50 text-4xl")
                ui.label("الرجاء البحث واختيار طالب لعرض معلوماته الأكاديمية وإصدار الوثيقة.").classes("text-base font-semibold text-center")

    def select_student(self, student_row):
        if hasattr(self, "search_results_card"):
            self.search_results_card.set_visibility(False)

        self.selected_student = student_row
        student_id = student_row.get("student_id") or student_row.get("id")
        self.current_grouping_mode = getattr(self, "current_grouping_mode", "DEFAULT")

        try:
            self.student_full_data = self.cert_repo.get_full_certificate_data(
                student_id, grouping_mode="DEFAULT"
            )
            if not self.student_full_data:
                UI.notify("لا توجد بيانات دراسية للطالب المحدد / No academic data found", type="warning")
                return

            # Dynamic grouping options update based on student's study system (semester vs yearly)
            semester_options = {
                "BY_SEMESTER_stage": "مقررات - حسب المرحلة",
                "BY_SEMESTER_year": "مقررات - حسب السنة"
            }
            yearly_options = {
                "DEFAULT": "الافتراضي - سنوي",
                "BY_PERIOD_STAGE": "سنوي - حسب المرحلة الدراسية",
                "BY_CURRICULUM_STAGE": "سنوي - حسب مرحلة المادة",
                "BY_ByAcademicYear": "سنوي - حسب سنة الإنجاز"
            }

            period_disp = str(self.student_full_data.get("period_display") or "").lower().strip()
            if period_disp in ("year", "yearly"):
                is_semester = False
            elif period_disp == "semester":
                is_semester = True
            else:
                sys_name = str(self.student_full_data.get("study_system_name_ar") or "").lower()
                is_semester = "semester" in sys_name or ("فصل" in sys_name and "سنو" not in sys_name)

            if is_semester:
                target_opts = semester_options
                default_val = "BY_SEMESTER_stage"
            else:
                target_opts = yearly_options
                default_val = "DEFAULT"

            self.current_grouping_mode = default_val

            if default_val != "DEFAULT":
                self.student_full_data = self.cert_repo.get_full_certificate_data(
                    student_id, grouping_mode=default_val
                )

            self.update_student_ui()

            if hasattr(self, "grouping_sel") and self.grouping_sel:
                self.grouping_sel.options = target_opts
                self.grouping_sel.value = default_val
                self.grouping_sel.update()

            # Filter template dropdown options dynamically based on student's study system (semester vs year)
            filtered_templates = self.get_templates(self.student_full_data)
            if hasattr(self, "template_sel") and self.template_sel:
                self.template_sel.options = self._format_template_options(filtered_templates)
                self.template_sel.value = filtered_templates[0] if filtered_templates else None
                self.template_sel.update()

            # If arriving with an existing certificate record (e.g. from Issued Certificates registry Edit button)
            if self.initial_cert_record:
                rec = self.initial_cert_record
                cert_num = rec.get("certificate_number") or ""
                to_title = rec.get("to_title") or rec.get("recipient_name") or ""
                issue_date = rec.get("issue_date") or ""
                tpl_type = rec.get("template_type") or rec.get("template_file") or rec.get("template_name") or ""

                if hasattr(self, "cert_number_input") and self.cert_number_input and cert_num:
                    self.cert_number_input.value = str(cert_num)
                if hasattr(self, "to_input") and self.to_input and to_title:
                    self.to_input.value = str(to_title)
                if hasattr(self, "issue_date_input") and self.issue_date_input and issue_date:
                    self.issue_date_input.value = str(issue_date)[:10]

                # Match template in dropdown
                if hasattr(self, "template_sel") and self.template_sel and tpl_type:
                    tpl_clean = str(tpl_type).strip().lower()
                    matched = None
                    opts = self.template_sel.options
                    opt_keys = list(opts.keys()) if isinstance(opts, dict) else list(opts)
                    for opt_k in opt_keys:
                        opt_clean = os.path.splitext(opt_k)[0].strip().lower()
                        if tpl_clean == opt_clean or tpl_clean in opt_clean or opt_clean in tpl_clean:
                            matched = opt_k
                            break
                    if matched:
                        self.template_sel.value = matched
                        self.template_sel.update()

                self.reissue_cert_id = rec.get("certificate_id") or rec.get("id")
                student_display_name = student_row.get("full_name_ar") or self.student_full_data.get("full_name_ar", "")
                if hasattr(self, "edit_mode_banner") and self.edit_mode_banner:
                    if hasattr(self, "edit_mode_label") and self.edit_mode_label:
                        self.edit_mode_label.text = f"وضع التعديل: تعديل قيد الوثيقة رقم ({cert_num or self.reissue_cert_id}) للطالب ({student_display_name})"
                    self.edit_mode_banner.set_visibility(True)

                if hasattr(self, "btn_generate") and self.btn_generate:
                    self.btn_generate.text = "تحديث وتوليد الوثيقة (Word) / Update & Generate"

                # Directly show print options view as requested
                self.show_options_view()
            else:
                self.show_info_view()
        except Exception as e:
            log.error(f"Error loading student: {e}")
            UI.notify(f"خطأ أثناء تحميل بيانات الطالب: {e}", type="negative")

    def handle_edit_student(self):
        """Triggers navigation to Students Management screen to edit selected student."""
        if not self.selected_student:
            return

        if self.on_edit_student:
            self.on_edit_student(self.selected_student)
        else:
            UI.notify("الانتقال لصفحة تعديل الطالب... / Redirecting to edit student", type="info")

    def update_student_ui(self):
        data = self.student_full_data
        if not data: return

        st_info = data.get("student_info") or {}
        if isinstance(st_info, list) and len(st_info) > 0:
            st_info = st_info[0]
        
        period_disp = str(st_info.get("period_display") or "").lower().strip()
        is_annual = ("semester" not in period_disp)

        if data.get("courses_grouped"):
            data["courses_grouped"] = consolidate_courses_for_certificate(data["courses_grouped"], is_annual=is_annual)

        # ── 1. Auto Extract Second Trial Courses & Calculate Default Summer Training Year ──
        second_courses = []
        for c in data.get("courses_grouped", []):
            pr = str(c.get("passed_round") or "1").strip()
            isr = c.get("is_second_round", 0)
            if pr in ('2', '3') or isr == 1 or pr in (2, 3):
                cname = c.get("subject_name") or c.get("course_name_ar") or c.get("course_name_en")
                if cname and cname not in second_courses:
                    second_courses.append(cname)

        if not second_courses:
            for p in data.get("periods", []):
                for enr in p.get("enrollments", []):
                    pr = str(enr.get("passed_round", "1"))
                    isr = enr.get("is_second_round", 0)
                    if pr in ('2', '3') or isr == 1:
                        cname = enr.get("course_name_ar") or enr.get("course_name_en")
                        if cname and cname not in second_courses:
                            second_courses.append(cname)

        if second_courses:
            self.inp_second_subjects.value = "، ".join(second_courses)
            self.sw_second.value = True
        else:
            self.inp_second_subjects.value = ""
            self.sw_second.value = False

        # ── Auto Extract Postponed & Failed Years ──
        timeline = data.get("academic_timeline") or data.get("periods") or []
        from cert_repository import extract_failed_years
        failed_years_list = extract_failed_years(timeline, is_english=False)
        if failed_years_list:
            postpone_strs = []
            for y in failed_years_list:
                st_state = y.get("state") or "تأجيل"
                postpone_strs.append(f"السنة {y.get('year_d')} / المرحلة {y.get('stage')} (سنة {st_state})")
            self.inp_postpone_years.value = "؛ ".join(postpone_strs)
            self.sw_postpone.value = True
        else:
            self.inp_postpone_years.value = ""
            self.sw_postpone.value = False

        # Summer training year display (first checks student's saved summer_training_data, fallback to graduation_year - 1)
        summer_val = data.get("summer_training_data") or data.get("summer_training")
        if not summer_val and hasattr(self, "selected_student") and self.selected_student:
            summer_val = self.selected_student.get("summer_training_data") or self.selected_student.get("summer_training")

        if not summer_val and data.get("id"):
            try:
                st_row = self.student_repo.get_by_id(data.get("id"))
                if st_row:
                    summer_val = st_row.get("summer_training_data") or st_row.get("summer_training")
            except Exception:
                pass

        grad_year = data.get("graduation_year")
        if not grad_year and data.get("graduation_date"):
            gdate_str = str(data.get("graduation_date")).strip()
            if len(gdate_str) >= 4 and gdate_str[:4].isdigit():
                grad_year = gdate_str[:4]

        if summer_val and str(summer_val).strip():
            self.inp_summer_year.value = str(summer_val).strip()
            self.sw_summer.value = True
        elif grad_year and str(grad_year).isdigit():
            def_year = str(int(grad_year) - 1)
            self.inp_summer_year.value = def_year
            self.sw_summer.value = True
        else:
            self.inp_summer_year.value = ""
            self.sw_summer.value = False

        # Fill University Order & Rank
        if data.get("order_number"):
            self.sw_order.value = True
            self.inp_order_num.value = str(data.get("order_number") or "")
            self.inp_order_date.value = str(data.get("order_date") or "")

        rank_val_def = data.get("rank") or data.get("sequence_number")
        if not rank_val_def and hasattr(self, "selected_student") and self.selected_student:
            rank_val_def = self.selected_student.get("sequence_number") or self.selected_student.get("rank")

        total_grad_def = data.get("total_graduates") or data.get("postgraduation_number") or data.get("order_num_students") or data.get("num_students")
        if not total_grad_def and hasattr(self, "selected_student") and self.selected_student:
            total_grad_def = self.selected_student.get("postgraduation_number") or self.selected_student.get("total_graduates")

        top_avg_val_def = data.get("top_average")

        if rank_val_def or total_grad_def:
            self.sw_rank.value = True
            self.inp_rank_val.value = str(rank_val_def or "")
            self.inp_rank_total.value = str(total_grad_def or "")
            if top_avg_val_def:
                try:
                    self.inp_rank_avg.value = str(round(float(top_avg_val_def), 2))
                except (ValueError, TypeError):
                    self.inp_rank_avg.value = str(top_avg_val_def)

        # ── 2. Render Student Profile View (High Readability, No Duplication, Structured List) ──
        self.student_info_container.clear()
        with self.student_info_container:
            # Student Profile Header Card
            with UI.card().classes("w-full p-6 gap-4 bg-[var(--bg-main)] rounded-2xl border border-[var(--border-default)] shadow-sm"):
                with ui.row().classes("w-full justify-between items-center flex-wrap gap-4"):
                    with ui.row().classes("items-center gap-4"):
                        ui.icon("badge", size="lg").classes("app-text-accent text-3xl")
                        with ui.column().classes("gap-1"):
                            ui.label(data.get("full_name_ar", "")).classes("text-2xl font-black app-text-primary tracking-wide")
                            ui.label(data.get("full_name_en", "")).classes("text-sm app-text-muted font-mono font-medium")

                    with ui.row().classes("items-center gap-3"):
                        ui.label(data.get("dept_name_ar", "")).classes(
                            "px-4 py-2 text-sm font-bold rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] app-text-accent shadow-sm"
                        )
                        UI.primary_button("خيارات وتوليد الوثيقة", icon="tune", on_click=self.show_options_view).classes("text-xs px-5 py-2.5 font-bold shadow-md")
                        UI.primary_button("تعديل الطالب / Edit Student", icon="edit", on_click=self.handle_edit_student).classes("text-xs px-4 py-2.5")

            # 4 Unified Non-Duplicated Key Metric Cards
            avg = data.get("average")
            avg_str = f"{float(avg):.2f}%" if avg is not None else "—"
            rank_val = self.inp_rank_val.value or data.get("rank") or data.get("sequence_number")
            if not rank_val and hasattr(self, "selected_student") and self.selected_student:
                rank_val = self.selected_student.get("sequence_number") or self.selected_student.get("rank")

            total_grad = self.inp_rank_total.value or data.get("total_graduates") or data.get("postgraduation_number") or data.get("order_num_students") or data.get("num_students")
            if not total_grad and hasattr(self, "selected_student") and self.selected_student:
                total_grad = self.selected_student.get("postgraduation_number") or self.selected_student.get("total_graduates")

            if rank_val and total_grad:
                rank_str = f"المرتبة {rank_val} من {total_grad} خريج"
            elif rank_val:
                rank_str = f"المرتبة {rank_val}"
            else:
                rank_str = "—"
            top_avg = data.get("top_average")
            top_avg_str = f"{float(top_avg):.2f}%" if top_avg else "—"
            order_num_str = data.get('order_number')
            order_date_str = data.get('order_date')
            order_display = f"رقم {order_num_str}" if order_num_str else "غير محدد"
            order_sub = f"بتاريخ {order_date_str}" if order_date_str else ""

            with ui.grid(columns=4).classes("w-full gap-5"):
                # Card 1: المعدل العام
                with UI.card().classes("p-5 items-center justify-center text-center bg-[var(--bg-main)] rounded-2xl border border-[var(--border-default)] gap-1 shadow-sm"):
                    ui.label("المعدل العام").classes("text-s font-bold app-text-muted tracking-wider uppercase")
                    ui.label(avg_str).classes("text-2xl font-black text-emerald-400 tracking-tight")
                    ui.label(data.get("grade") or "ناجح").classes("text-s font-bold text-slate-400")

                # Card 2: الترتيب والتسلسل (Unified without duplicate!)
                with UI.card().classes("p-5 items-center justify-center text-center bg-[var(--bg-main)] rounded-2xl border border-[var(--border-default)] gap-1 shadow-sm"):
                    ui.label("تسلسل التخرج").classes("text-s font-bold app-text-muted tracking-wider uppercase")
                    ui.label(rank_str).classes("text-xl font-black text-blue-400 tracking-tight")
                    ui.label(f"الأول: {top_avg_str}").classes("text-s font-bold text-slate-400")

                # Card 3: الأمر الجامعي
                with UI.card().classes("p-5 items-center justify-center text-center bg-[var(--bg-main)] rounded-2xl border border-[var(--border-default)] gap-1 shadow-sm"):
                    ui.label("الأمر الجامعي").classes("text-s font-bold app-text-muted tracking-wider uppercase")
                    ui.label(order_display).classes("text-lg font-black text-purple-400 tracking-tight")
                    if order_sub:
                        ui.label(order_sub).classes("text-s font-bold text-slate-400")

                # Card 4: التدريب الصيفي
                with UI.card().classes("p-5 items-center justify-center text-center bg-[var(--bg-main)] rounded-2xl border border-[var(--border-default)] gap-1 shadow-sm"):
                    ui.label("التدريب الصيفي").classes("text-s font-bold app-text-muted tracking-wider uppercase")
                    ui.label(self.inp_summer_year.value or "—").classes("text-2xl font-black text-amber-400 tracking-tight")
                    ui.label("سنة التدريب").classes("text-s font-bold text-slate-400")

            # Dedicated Second Trial Subjects List Section ("Make a List" requested by user)
            with UI.card().classes("w-full p-6 gap-3 bg-[var(--bg-main)] rounded-2xl border border-[var(--border-default)] shadow-sm"):
                with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)]"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("history_edu", size="sm").classes("text-amber-400")
                        ui.label("مواد الدور الثاني — Second Trial Subjects List").classes("text-sm font-extrabold app-text-accent tracking-wide")
                    if second_courses:
                        ui.label(f"إجمالي المواد: {len(second_courses)}").classes("text-s font-bold px-3 py-1 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30")

                if second_courses:
                    with ui.row().classes("w-full flex-wrap gap-3 pt-2"):
                        for cname in second_courses:
                            with ui.row().classes("items-center gap-2 px-3.5 py-2 rounded-xl bg-[var(--bg-card)] border border-amber-500/30 text-amber-300 font-bold text-xs shadow-sm hover:border-amber-400 transition-all"):
                                ui.icon("menu_book", size="xs").classes("text-amber-400")
                                ui.label(cname).classes("text-sm font-semibold")
                else:
                    with ui.row().classes("items-center gap-2 text-xs text-emerald-400 font-bold p-2"):
                        ui.icon("check_circle", size="xs").classes("text-emerald-400")
                        ui.label("استحقاق الدور الأول — الطالب اجتاز جميع المواد الدراسية من الدور الأول.").classes("text-sm")

            # Academic Transcript Table Section (Cards Grouped by Dynamic Grouping Mode)
            semester_options = {
                "BY_SEMESTER_stage": "مقررات - حسب المرحلة",
                "BY_SEMESTER_year": "مقررات - حسب السنة"
            }
            yearly_options = {
                "DEFAULT": "الافتراضي - سنوي",
                "BY_PERIOD_STAGE": "سنوي - حسب المرحلة الدراسية",
                "BY_CURRICULUM_STAGE": "سنوي - حسب مرحلة المادة",
                "BY_ByAcademicYear": "سنوي - حسب سنة الإنجاز"
            }

            st_info_ui = data.get("student_info") or {}
            if isinstance(st_info_ui, list) and len(st_info_ui) > 0:
                st_info_ui = st_info_ui[0]
            
            period_disp = str(st_info_ui.get("period_display") or "").lower().strip()
            if period_disp in ("year", "yearly"):
                is_semester = False
            elif period_disp == "semester":
                is_semester = True
            else:
                sys_name = str(st_info_ui.get("study_system_name_ar") or "").lower()
                is_semester = "semester" in sys_name or ("فصل" in sys_name and "سنو" not in sys_name)

            group_opts = semester_options if is_semester else yearly_options

            current_mode = getattr(self, "current_grouping_mode", "DEFAULT")
            if current_mode not in group_opts:
                current_mode = "BY_SEMESTER_stage" if is_semester else "DEFAULT"

            async def on_grouping_change(e):
                new_mode = str(getattr(e, 'value', e) or "DEFAULT")
                self.current_grouping_mode = new_mode
                if self.selected_student:
                    try:
                        self.student_full_data = self.cert_repo.get_full_certificate_data(
                            self.selected_student["id"], grouping_mode=new_mode
                        )
                        self.update_student_ui()
                    except Exception as exc:
                        log.error(f"Error updating grouping: {exc}")
                        UI.notify(f"خطأ في تحديث التجميع: {exc}", type="negative")

            with ui.row().classes("w-full justify-between items-center mt-2 pb-1"):
                ui.label("السجل الأكاديمي والدرجات — Academic Transcript").classes("text-lg font-extrabold app-text-primary tracking-wide")
                
                UI.select(
                    "خيارات التجميع / Grouping Options",
                    options=group_opts,
                    value=current_mode,
                    on_change=lambda e: on_grouping_change(e)
                ).classes("w-72 text-xs")

            with ui.column().classes("w-full border border-[var(--border-default)] rounded-2xl p-5 bg-[var(--bg-main)] gap-5 h-auto"):
                courses = data.get("courses_grouped", [])
                if not courses:
                    ui.label("لا توجد سجلات دراسية / No course records").classes("text-sm app-text-muted italic p-4")
                else:
                    grouped_data = {}
                    for c in courses:
                        pstg = (
                            c.get("period_stage")
                            or c.get("stage_number")
                            or c.get("course_curriculum_stage")
                            or c.get("default_stage")
                            or c.get("stages")
                            or ""
                        )
                        raw_yr = str(c.get("academic_year") or "")
                        fmt_yr = str(c.get("academic_year_formatted") or raw_yr)
                        sem_num = c.get("semester_num", 1)
                        k = c.get("grouping_key") or f"{raw_yr}_{pstg}_{sem_num}"
                        if k not in grouped_data:
                            grouped_data[k] = {
                                "key": str(k),
                                "academic_year": fmt_yr,
                                "raw_academic_year": raw_yr,
                                "stage_number": pstg,
                                "semester_num": sem_num,
                                "enrollments": []
                            }
                        grouped_data[k]["enrollments"].append(c)

                    for k, p in grouped_data.items():
                        enrs = p.get("enrollments", [])
                        p_stages = [c.get("period_stage") or c.get("stage_number") for c in enrs if c.get("period_stage") or c.get("stage_number")]
                        if p_stages:
                            p["stage_number"] = max(p_stages, key=p_stages.count)

                    def _get_group_sort_key(p):
                        gk = str(p.get("key") or "")
                        if gk.isdigit() and len(gk) <= 2:
                            return ("", int(gk), 0)
                        if '_' in gk and gk.split('_')[0].isdigit() and len(gk.split('_')[0]) <= 2:
                            s_p, sem_p = gk.split('_')
                            return ("", int(s_p), int(sem_p) if sem_p.isdigit() else 0)
                        yr = str(p.get("raw_academic_year") or p.get("academic_year") or "")
                        try:
                            s_num = int(p.get("stage_number", 0))
                        except (ValueError, TypeError):
                            s_num = 0
                        try:
                            m_num = int(p.get("semester_num", 1))
                        except (ValueError, TypeError):
                            m_num = 1
                        return (yr, s_num, m_num)

                    sorted_groups = sorted(grouped_data.values(), key=_get_group_sort_key)

                    with ui.grid(columns=2).classes("w-full gap-5 items-start"):
                        for p in sorted_groups:
                            stg = p.get("stage_number", "")
                            year = p.get("academic_year", "")
                            sem = p.get("semester_num", 1)
                            enrs = p.get("enrollments", [])
                            gk_val = str(p.get("key") or "")

                            parts = []
                            if gk_val in ('1', '2', '3', '4', '5', '6'):
                                parts.append(f"المرحلة {gk_val}")
                            elif '_' in gk_val and gk_val.split('_')[0].isdigit() and len(gk_val.split('_')[0]) <= 2:
                                s_part, sem_part = gk_val.split('_')
                                parts.append(f"المرحلة {s_part}")
                                parts.append(f"الفصل {sem_part}")
                            else:
                                if year:
                                    parts.append(f"العام الدراسي ({year})")
                                if stg:
                                    parts.append(f"المرحلة {stg}")
                                if "semester" in period_disp and sem:
                                    parts.append(f"الفصل {sem}")
                            header_label = " — ".join(parts) if parts else f"المجموعة ({gk_val})"

                            with ui.column().classes("w-full gap-3 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-sm"):
                                with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)]"):
                                    ui.label(header_label).classes("text-sm font-extrabold app-text-accent tracking-wide")
                                    ui.label(f"عدد المواد: {len(enrs)}").classes("text-xs app-text-muted font-medium")

                                with ui.column().classes("w-full gap-2"):
                                    for enr in enrs:
                                        cname = enr.get("subject_name") or enr.get("course_name_ar") or enr.get("course_name_en") or ""
                                        score = enr.get("mark", "—")
                                        units = enr.get("unit", 0)
                                        pr = str(enr.get("passed_round", "1"))
                                        is_2nd = (pr in ('2', '3') or enr.get("is_second_round"))

                                        with ui.row().classes("w-full justify-between items-center text-sm py-2 px-3.5 rounded-xl bg-[var(--bg-main)] transition-all border border-[var(--border-default)] hover:border-amber-500/30"):
                                            with ui.row().classes("items-center gap-2"):
                                                ui.label(cname).classes("app-text-primary font-bold text-xs")
                                                if is_2nd:
                                                    ui.label("الدور الثاني").classes("px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-amber-500/20 text-amber-400 border border-amber-500/30")

                                            with ui.row().classes("items-center gap-2"):
                                                ui.label(f"الدرجة: {score}").classes("font-extrabold text-emerald-400 font-mono text-xs")
                                                ui.label(f"{units} وحدات").classes("text-[10px] font-bold px-2 py-0.5 bg-[var(--bg-card)] rounded-lg text-slate-300 font-mono border border-[var(--border-default)]")

    def _show_reissue_warning_modal(self, cert_num: str, tpl_name: str, options: dict, reissue_cert_id: Optional[int] = None) -> None:
        """Opens a confirmation modal warning the user to destroy the old physical paper copy before re-issuing."""
        with ui.dialog() as dialog, UI.card().classes("w-full max-w-lg p-6 gap-4 bg-[var(--bg-card)] rounded-2xl border border-[var(--border-default)] shadow-2xl"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("warning", size="lg").classes("text-amber-500")
                with ui.column().classes("gap-0"):
                    ui.label("تنبيه: إعادة إصدار وثيقة برقم مسجل مسبقاً").classes("text-base font-bold app-text-primary")
                    ui.label("Document Re-issuance & Invalidation Notice").classes("text-xs app-text-muted")

            ui.separator().classes("my-1")

            with ui.column().classes("gap-2 text-sm app-text-primary leading-relaxed bg-amber-50 dark:bg-amber-950/30 p-4 rounded-xl border border-amber-200 dark:border-amber-800"):
                ui.label(f"⚠️ إن رقم الوثيقة ({cert_num}) مسجل مسبقاً لهذا الطالب في السجل الرسمي.").classes("font-bold text-amber-800 dark:text-amber-300")
                ui.label("وفقاً لتعليمات السجل والوثائق، فإن إعادة إصدار الوثيقة بنفس الرقم تتطلب أولاً إتلاف النسخة الورقية السابقة منعاً للازدواجية.").classes("text-xs leading-normal")
                ui.label("هل ترغب في متابعة التوليد وتحديث بيانات القيد في السجل؟").classes("text-xs font-semibold")

            with ui.row().classes("w-full justify-end gap-3 mt-2"):
                UI.secondary_button("إلغاء / Cancel", icon="close", on_click=dialog.close).classes("text-xs px-4 py-2")
                
                def _confirm_reissue():
                    dialog.close()
                    if reissue_cert_id:
                        options["reissue_cert_id"] = reissue_cert_id
                    self.generate_docx(tpl_name, options)

                UI.danger_button("تأكيد وإتلاف القديمة / Confirm & Overwrite", icon="done", on_click=_confirm_reissue).classes("text-xs px-4 py-2 font-bold")

        dialog.open()

    def generate_certificate(self, bypass_duplicate_check: bool = False) -> bool:
        if not self.student_full_data:
            UI.notify("الرجاء اختيار طالب أولاً / Please select a student first", type="warning")
            return False

        tpl_name = self.template_sel.value
        if not tpl_name or "لا توجد" in tpl_name:
            UI.notify("الرجاء اختيار قالب وثيقة صالح / Please select a valid document template", type="warning")
            return False

        tpl_path = os.path.join(self.templates_dir, tpl_name)
        if not os.path.exists(tpl_path):
            UI.notify(f"القالب غير موجود: {tpl_path}", type="negative")
            return False

        cert_num = (self.cert_number_input.value or "").strip() if hasattr(self, "cert_number_input") else ""
        student_id = self.student_full_data.get("id") or self.student_full_data.get("student_id")

        # Prepare options dictionary
        is_en = "en" in tpl_name.lower() or "eng" in tpl_name.lower()
        options = {
            "is_english": is_en,
            "certificate_number": cert_num,
            "to_title": (self.to_input.value or "").strip(),
            "opt_order": self.sw_order.value,
            "order_num": (self.inp_order_num.value or "").strip(),
            "order_date": (self.inp_order_date.value or "").strip(),
            "opt_rank": self.sw_rank.value,
            "rank_val": (self.inp_rank_val.value or "").strip(),
            "rank_total": (self.inp_rank_total.value or "").strip(),
            "rank_avg": (self.inp_rank_avg.value or "").strip(),
            "opt_summer": self.sw_summer.value,
            "summer_year": (self.inp_summer_year.value or "").strip(),
            "opt_postpone": self.sw_postpone.value,
            "postpone_years": (self.inp_postpone_years.value or "").strip(),
            "opt_second_trial": self.sw_second.value,
            "second_trial_subjects": (self.inp_second_subjects.value or "").strip(),
            "national_id": (self.student_full_data.get("national_id") if self.student_full_data else None) or (self.selected_student.get("national_id") if hasattr(self, "selected_student") and self.selected_student else None) or "",
            "reissue_cert_id": getattr(self, "reissue_cert_id", None),
        }

        # Check duplicate certificate number
        if cert_num and not bypass_duplicate_check:
            dup_info = self.issued_cert_repo.check_duplicate(cert_num, student_id)
            if dup_info.get("exists"):
                reissue_id = getattr(self, "reissue_cert_id", None)
                if reissue_id and dup_info.get("certificate_id") == reissue_id:
                    # User is editing this exact certificate record, so reuse without duplicate warning
                    pass
                elif not dup_info.get("same_student"):
                    owner_name = dup_info.get("owner_name") or f"طالب آخر (ID: {dup_info.get('owner_id')})"
                    UI.notify(
                        f"⚠️ خطأ: رقم الوثيقة ({cert_num}) مستخدم بالفعل للطالب ({owner_name})! يرجى اختيار رقم فريد.",
                        type="negative",
                        close_button="حسناً"
                    )
                    return False
                else:
                    self._show_reissue_warning_modal(cert_num, tpl_name, options, reissue_cert_id=dup_info.get("certificate_id"))
                    return False

        return self.generate_docx(tpl_name, options)

    # Set to True to enable verbose printing of docxtpl context variables in the terminal/log
    ENABLE_CONTEXT_LOGGING: bool = False

    @staticmethod
    def print_certificate_context(ctx: dict, enabled: bool = False) -> None:
        """
        Prints every variable passed to Word (docxtpl) line by line to standard output (terminal)
        and system logs so the user can track every data field step by step.
        Set `ENABLE_CONTEXT_LOGGING = True` or pass `enabled=True` to activate in the future.
        """
        if not (enabled or CertificateScreen.ENABLE_CONTEXT_LOGGING):
            return

        banner = "=" * 80
        log_lines = [
            "",
            banner,
            "  === WORD DOCXTPL CONTEXT VARIABLES TRACKING LOG ===",
            banner,
            "\n--- [1. TOP-LEVEL SCALAR VARIABLES & METADATA] ---",
        ]

        scalars = {}
        lists_and_dicts = {}
        for k, v in ctx.items():
            if isinstance(v, (list, dict)):
                lists_and_dicts[k] = v
            else:
                scalars[k] = v
                log_lines.append(f"  • {k:<30} = {repr(v)}")

        # Signatories
        signatories = ctx.get("signatories")
        if isinstance(signatories, list):
            log_lines.append(f"\n--- [2. SIGNATORIES ({len(signatories)} Total)] ---")
            for idx, sig in enumerate(signatories):
                if isinstance(sig, dict):
                    log_lines.append(
                        f"  ► Signatory {idx+1}: name='{sig.get('name')}', title='{sig.get('title')}', order={sig.get('order')}"
                    )
                else:
                    log_lines.append(f"  ► Signatory {idx+1}: {sig}")

        # Tables & Paired Semesters / Years
        printed_table_ids = set()
        for table_key in ("paired_semesters", "paired_years", "semesters"):
            table_list = ctx.get(table_key)
            if isinstance(table_list, list) and table_list:
                if id(table_list) in printed_table_ids:
                    log_lines.append(f"\n--- [3. TABLE DATA: '{table_key}' (Same data as paired_semesters — skipped duplicate print)] ---")
                    continue
                printed_table_ids.add(id(table_list))
                log_lines.append(f"\n--- [3. TABLE DATA: '{table_key}' ({len(table_list)} Tables/Rows)] ---")
                for t_idx, table_item in enumerate(table_list):
                    log_lines.append("\n  ==========================================================================")
                    log_lines.append(f"  ► Table {t_idx+1}:")
                    log_lines.append(f"      left_label       : '{table_item.get('left_label', '')}'")
                    log_lines.append(f"      right_label      : '{table_item.get('right_label', '')}'")
                    log_lines.append(f"      year_left_label  : '{table_item.get('year_left_label', '')}'")
                    log_lines.append(f"      year_right_label : '{table_item.get('year_right_label', '')}'")
                    log_lines.append(f"      year_label       : '{table_item.get('year_label', '')}'")
                    log_lines.append(f"      academic_year    : '{table_item.get('academic_year', '')}'")
                    log_lines.append(f"      num_s_l          : '{table_item.get('num_s_l', '')}'")
                    log_lines.append(f"      num_s_r          : '{table_item.get('num_s_r', '')}'")
                    log_lines.append(f"      year_s_l         : '{table_item.get('year_s_l', '')}'")
                    log_lines.append(f"      year_s_r         : '{table_item.get('year_s_r', '')}'")
                    log_lines.append(f"      stage_s_l        : '{table_item.get('stage_s_l', '')}'")
                    log_lines.append(f"      stage_s_r        : '{table_item.get('stage_s_r', '')}'")
                    log_lines.append(f"      stage_text       : '{table_item.get('stage_text', '')}'")

                    rows = table_item.get("rows", [])
                    if isinstance(rows, list) and rows:
                        log_lines.append(f"\n      --- Courses ({len(rows)} Rows) ---")
                        log_lines.append(f"      {'#':<3} | {'RIGHT SUBJECT':<35} | {'MARK':<6} | {'UNIT':<5} || {'LEFT SUBJECT':<35} | {'MARK':<6} | {'UNIT':<5}")
                        log_lines.append("      " + "-" * 105)
                        for r_idx, r in enumerate(rows):
                            if isinstance(r, dict):
                                r_subj = str(r.get('right_name') or r.get('right_subj') or '')
                                r_mark = str(r.get('right_mark') or '')
                                r_unit = str(r.get('right_unit') or '')
                                l_subj = str(r.get('left_name') or r.get('left_subj') or '')
                                l_mark = str(r.get('left_mark') or '')
                                l_unit = str(r.get('left_unit') or '')
                                log_lines.append(
                                    f"      {r_idx+1:<3} | {r_subj:<35} | {r_mark:<6} | {r_unit:<5} || {l_subj:<35} | {l_mark:<6} | {l_unit:<5}"
                                )

        log_lines.append(banner)
        full_output = "\n".join(log_lines)

        print(full_output, flush=True)
        log.info(full_output)

    def generate_docx(self, tpl_name: str, options: dict) -> bool:
        """Generates Word document from template and returns True on success."""
        tpl_path = str(app_paths.data_path("templets", tpl_name))
        if not os.path.exists(tpl_path):
            UI.notify(f"قالب الوثيقة غير موجود: {tpl_name}", type="negative")
            return False
    
        if not self.student_full_data:
            UI.notify("لم يتم تحميل بيانات الطالب", type="warning")
            return False
    
        # options is already fully populated by generate_certificate
    
        out_file = ""
        try:
            from cert_repository import transform_raw_payload_to_context
            # The toggle values (including Summer Training) are passed directly into cert_repository.py here!
            ctx = transform_raw_payload_to_context(self.student_full_data, is_english=options.get("is_english", False), options=options)
            
            # Inject missing arrays into ctx so build_certificate_context can find them
            ctx["courses_grouped"] = self.student_full_data.get("courses_grouped", [])
            ctx["all_personnel"] = self.student_full_data.get("signers", [])
            ctx["academic_timeline"] = self.student_full_data.get("academic_timeline", [])
            
            # We also call build_certificate_context to maintain backward compatibility with any other UI-specific toggles
            ctx = build_certificate_context(ctx, options)
    
            # Inject certificate number into context
            ctx["certificate_number"] = options.get("certificate_number", "")

            # Print all context variables line-by-line to terminal & log
            self.print_certificate_context(ctx)
    
            # Ensure output directory exists
            out_dir = str(app_paths.data_path("certificates"))
            os.makedirs(out_dir, exist_ok=True)
    
            student_name = ctx.get("student_name", "Student")
            safe_student = re.sub(r'[\\/*?:"<>|]', "", student_name).strip() or "Student"
            safe_tpl = re.sub(r'[\\/*?:"<>|]', "", os.path.splitext(tpl_name)[0]).strip()
            grouping_mode = getattr(self, "current_grouping_mode", "DEFAULT")
            safe_grouping = re.sub(r'[\\/*?:"<>|]', "", str(grouping_mode)).strip()
            out_file = os.path.join(out_dir, f"{safe_tpl} - {safe_student} - {safe_grouping}.docx")
    
            doc = DocxTemplate(tpl_path)
            doc.render(ctx)
            doc.save(out_file)

            self.generated_file_path = out_file

            # Record issued certificate into database via Stored Procedure (InsertIssuedCertificate)
            try:
                student_id = self.student_full_data.get("id") or self.student_full_data.get("student_id")
                if student_id:
                    to_title = (self.to_input.value or "").strip() or "من يهمه الأمر"
                    tpl_type = os.path.splitext(tpl_name)[0]
                    cert_num = options.get("certificate_number") or ((self.cert_number_input.value or "").strip() if hasattr(self, "cert_number_input") else None)
                    from nicegui_ui.state import app_session
                    u_id = getattr(app_session, "emp_id", None)
                    u_name = getattr(app_session, "name_ar", None) or getattr(app_session, "username", "Admin")
                    reissue_id = options.get("reissue_cert_id")
                    issue_dt = (self.issue_date_input.value or "").strip() if hasattr(self, "issue_date_input") else None
                    if reissue_id:
                        self.issued_cert_repo.update(
                            cert_id=reissue_id,
                            to_title=to_title,
                            template_type=tpl_type,
                            certificate_number=cert_num,
                            issue_date=issue_dt
                        )
                        log.info(f"Successfully updated/overwritten existing issued certificate ID {reissue_id} for student ID {student_id}")
                    else:
                        self.issued_cert_repo.insert(
                            student_id=student_id,
                            to_title=to_title,
                            template_type=tpl_type,
                            certificate_number=cert_num,
                            issue_date=issue_dt,
                            user_id=u_id,
                            user_name=u_name
                        )
                        log.info(f"Successfully recorded issued certificate for student ID {student_id} via InsertIssuedCertificate SP.")
                    # Automatically prepare next sequence number in UI if not editing
                    if not reissue_id and hasattr(self, "cert_number_input") and self.cert_number_input:
                        self.cert_number_input.value = self.issued_cert_repo.get_next_number()
            except CertificateRejected as rej:
                log.warning(f"Server refused to record the issued certificate: {rej}")
                UI.notify(
                    f"لم يتم تسجيل الوثيقة في قاعدة البيانات / The server refused to record this certificate ({rej.status_code}):\n{rej.detail}",
                    type="warning"
                )
            except Exception as sp_err:
                log.error(f"Failed to record issued certificate into database via SP: {sp_err}")

            UI.notify(f"تم إصدار وتوليد الوثيقة بنجاح: {os.path.basename(out_file)}", type="positive")

            # Trigger automatic browser download
            ui.download(out_file, filename=os.path.basename(out_file))
            return True
        except PermissionError as pe:
            log.error(f"Permission denied while saving certificate file {out_file}: {pe}")
            UI.notify(
                "الملف مفتوح حالياً في برنامج Word! يرجى إغلاق ملف الوثيقة المفتوح وإعادة التوليد.\n"
                "Permission denied: The certificate document is open in Microsoft Word. Please close Word and try again.",
                type="warning"
            )
            return False
        except Exception as err:
            err_str = str(err)
            if "Permission denied" in err_str or "[Errno 13]" in err_str or ("13" in err_str and "Permission" in err_str):
                log.error(f"Permission denied saving document: {err}")
                UI.notify(
                    "الملف مفتوح حالياً في برنامج Word! يرجى إغلاق ملف الوثيقة المفتوح وإعادة المحاولة.\n"
                    "The certificate document is open in Word. Please close Word and try again.",
                    type="warning"
                )
            else:
                log.error(f"Error generating certificate: {err}")
                UI.notify(f"خطأ أثناء توليد الوثيقة: {err}", type="negative")
            return False
    def show_in_app_print_dialog(self, pdf_path: str | None, docx_path: str):
        """
        Opens a modern in-app modal dialog featuring live document preview,
        system printer selection, copies count, and one-click direct printing.
        """
        rel_doc_name = os.path.basename(docx_path)

        pdf_url = ""
        if pdf_path:
            quoted_pdf = urllib.parse.quote(os.path.basename(pdf_path))
            # The query string stops the viewer showing a cached PDF of the same name.
            pdf_url = f"/certificates_files/{quoted_pdf}?v={int(os.path.getmtime(pdf_path))}"

        with ui.dialog() as print_dialog, UI.card().classes(
            "w-[94vw] max-w-6xl h-[90vh] p-6 gap-4 flex-col bg-[var(--bg-card)] border border-[var(--border-default)] rounded-2xl shadow-2xl"
        ):
            # Modal Top Bar
            with ui.row().classes("w-full justify-between items-center pb-3 border-b border-[var(--border-default)]"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("print", size="md").classes("app-text-accent")
                    ui.label("معاينة الوثيقة والطباعة المباشرة — Certificate Preview & Print").classes("text-lg font-bold app-text-primary")

                UI.secondary_button("إغلاق / Close", icon="close", on_click=print_dialog.close).classes("text-xs px-3 py-1.5")

            # Main Body: Left Document Previewer + Right Printer Controls Panel
            with ui.row().classes("w-full flex-1 gap-6 items-stretch overflow-hidden"):
                # Left Column: In-App Document Previewer
                with ui.column().classes("flex-1 h-full rounded-xl overflow-hidden p-0 border border-[var(--border-default)] bg-slate-900 shadow-inner"):
                    if pdf_url:
                        # The PDF itself is the preview: what you see is exactly what prints.
                        ui.html(
                            f'<iframe src="{pdf_url}#view=FitH" style="width:100%;height:100%;min-height:600px;border:0;background:white"></iframe>'
                        ).classes("w-full h-full")
                    else:
                        with ui.column().classes("w-full h-full justify-center items-center gap-2 text-slate-400"):
                            ui.icon("description", size="xl")
                            ui.label("الوثيقة جاهزة للطباعة المباشرة").classes("font-bold text-sm")

                # Right Column: Printer Controls Panel
                with ui.column().classes("w-80 h-full p-5 rounded-xl border border-[var(--border-default)] bg-[var(--bg-main)] gap-4 justify-between"):
                    with ui.column().classes("w-full gap-4"):
                        ui.label("إعدادات الطابعة — Printer Selection").classes("text-sm font-extrabold app-text-accent pb-2 border-b border-[var(--border-default)]")

                        printers = get_installed_printers()
                        def_p = get_default_printer()
                        try:
                            import json
                            p_cfg_path = str(app_paths.data_path("config", "printer_config.json"))
                            if os.path.exists(p_cfg_path):
                                with open(p_cfg_path, "r", encoding="utf-8") as f:
                                    p_cfg = json.load(f)
                                    configured_cert_p = p_cfg.get("cert_printer")
                                    if configured_cert_p and configured_cert_p in printers:
                                        def_p = configured_cert_p
                        except Exception:
                            pass

                        printer_select = UI.select(
                            "اختيار الطابعة / Select Printer",
                            options={p: p for p in printers},
                            value=def_p if def_p in printers else (printers[0] if printers else None)
                        ).classes("w-full text-sm")

                        copies_input = UI.text_input("عدد النسخ / Copies", value="1").classes("w-full text-sm")

                        # Document Details Summary Box
                        with UI.card().classes("w-full p-3.5 gap-1.5 text-xs bg-[var(--bg-card)] rounded-xl border border-[var(--border-default)] app-text-muted shadow-sm"):
                            ui.label("معلومات المستند:").classes("font-bold app-text-accent")
                            ui.label(f"الملف: {rel_doc_name}").classes("font-mono text-[11px] truncate w-full")
                            ui.label("الحالة: جاهز للطباعة المباشرة").classes("text-emerald-400 font-bold mt-1")

                    # Primary Actions Group
                    with ui.column().classes("w-full gap-3 pt-4 border-t border-[var(--border-default)]"):
                        async def do_print_now():
                            sel_printer = printer_select.value
                            if not sel_printer:
                                UI.notify("الرجاء اختيار طابعة من القائمة أولاً", type="warning")
                                return
                            cps = int(copies_input.value) if copies_input.value and copies_input.value.isdigit() else 1
                            UI.notify(f"جاري إرسال الوثيقة للطباعة إلى ({sel_printer})...", type="info")

                            ok = await asyncio.to_thread(print_file_to_printer, docx_path, sel_printer, cps)
                            if ok:
                                UI.notify(f"تم إرسال الوثيقة بنجاح إلى الطابعة: {sel_printer}", type="positive")
                                print_dialog.close()
                            else:
                                UI.notify(f"تعذر إرسال الوثيقة للطباعة على {sel_printer}", type="negative")

                        UI.success_button("🖨️ طباعة الآن / Print Now", icon="print", on_click=do_print_now).classes("w-full py-3 text-sm font-bold shadow-md")
                        if pdf_path:
                            UI.secondary_button("⬇️ تحميل ملف PDF", icon="download", on_click=lambda: ui.download(pdf_path)).classes("w-full py-2.5 text-xs")
                        UI.secondary_button("إغلاق / Close", icon="cancel", on_click=print_dialog.close).classes("w-full py-2 text-xs")

        print_dialog.open()

    def generate_and_open_word(self):
        """Generates the certificate and opens the Word document directly in Microsoft Word."""
        success = self.generate_certificate()
        if success and self.generated_file_path and os.path.exists(self.generated_file_path):
            try:
                os.startfile(self.generated_file_path)
                UI.notify("تم فتح وثيقة Word في البرنامج / Word document opened", type="positive")
            except Exception as err:
                log.error(f"Error opening generated Word doc: {err}")
                UI.notify(f"تعذر فتح ملف Word: {err}", type="warning")

    async def print_certificate(self):
        """Fills Word template, converts to PDF/HTML asynchronously in background, and opens full in-app preview modal."""
        # Filling the template also records the certificate, so only do it once.
        if not self.generated_file_path or not os.path.exists(self.generated_file_path):
            if not self.generate_certificate():
                return

        if self.generated_file_path and os.path.exists(self.generated_file_path):
            try:
                UI.notify("جاري تحويل الوثيقة وتحضير المعاينة...", type="info")

                # Word runs on its own background thread, so the UI stays responsive.
                pdf_res = await asyncio.to_thread(generate_pdf_from_docx, self.generated_file_path)
                pdf_path = pdf_res if pdf_res and os.path.exists(pdf_res) else None
                if pdf_path is None:
                    UI.notify("تعذر تحويل الوثيقة: يتطلب برنامج Microsoft Word / Microsoft Word is required for preview and PDF", type="warning")

                self.show_in_app_print_dialog(pdf_path, self.generated_file_path)
            except Exception as err:
                log.error(f"Error opening in-app print dialog: {err}")
                UI.notify(f"تعذر فتح نافذة المعاينة والطباعة: {err}", type="negative")

    def open_generated_document(self):
        if not self.generated_file_path or not os.path.exists(self.generated_file_path):
            self.generate_certificate()

        if self.generated_file_path and os.path.exists(self.generated_file_path):
            try:
                os.startfile(self.generated_file_path)
                UI.notify("تم فتح الوثيقة في المستعرض / Document opened", type="info")
            except Exception as err:
                log.error(f"Error opening generated doc: {err}")
                UI.notify(f"تعذر فتح الملف: {err}", type="warning")
