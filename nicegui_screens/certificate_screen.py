# =============================================================================
# nicegui_screens/certificate_screen.py — Certificate Issuance & Generation Screen
# =============================================================================

import os
import re
import logging
from itertools import zip_longest
from docxtpl import DocxTemplate
from nicegui import ui

from nicegui_ui.ui_components import UI
from data.repositories import StudentRepository, CertificateRepository, PersonnelRepository
from nicegui_screens.graduation_orders_screen import extract_event_value

log = logging.getLogger(__name__)


def build_certificate_context(data: dict, options: dict) -> dict:
    """
    Builds the template context dictionary for docxtpl rendering.
    Supports both annual and semester study systems, attempt tracking,
    bilingual fields, and signatories.
    """
    period_disp = str(data.get("period_display") or "year").lower()
    is_english = options.get("is_english", False)

    periods = data.get("periods", [])
    all_enrs = []
    for p in periods:
        for enr in p.get("enrollments", []):
            enr["_period_ref"] = p
            all_enrs.append(enr)

    from collections import defaultdict
    course_groups = defaultdict(list)
    for enr in all_enrs:
        course_groups[enr.get("course_id")].append(enr)

    for course_id, group in course_groups.items():
        total_attempts = 0
        for e in group:
            pr = str(e.get("passed_round", "1"))
            isr = e.get("is_second_round", 0)
            if pr == '3':
                total_attempts += 3
            elif pr == '2' or isr == 1:
                total_attempts += 2
            else:
                total_attempts += 1

        passing_candidates = [e for e in group if e.get("score") is not None and float(e.get("score") or 0) >= 50.0]
        if passing_candidates:
            passing_candidates.sort(key=lambda x: x.get("_period_ref", {}).get("stage_number", 0), reverse=True)
            passing_enr = passing_candidates[0]
            score_val = passing_enr.get("score")
            if score_val is not None:
                score_float = float(score_val)
                score_str = f"{int(score_float)}" if score_float.is_integer() else f"{score_float:.1f}"
                if total_attempts > 1:
                    passing_enr["score"] = f"{score_str} ({total_attempts})"
                else:
                    passing_enr["score"] = score_str

    for p in periods:
        p["enrollments"] = []

    for course_id, group in course_groups.items():
        passing_candidates = [e for e in group if e.get("score") is not None and (
            isinstance(e["score"], str) or (isinstance(e["score"], (int, float)) and float(e["score"]) >= 50.0)
        )]
        if passing_candidates:
            passing_candidates.sort(key=lambda x: x.get("_period_ref", {}).get("stage_number", 0), reverse=True)
            passing_enr = passing_candidates[0]
            passing_enr["_period_ref"]["enrollments"].append(passing_enr)

    paired_semesters = []
    is_annual = (period_disp == "year")
    num_periods = len(periods)

    if is_annual:
        half = (num_periods + 1) // 2
        for i in range(half):
            left_period = periods[i]
            right_period = periods[i + half] if i + half < num_periods else None

            left_stage_num = i + 1
            right_stage_num = i + half + 1

            left_label = f"{left_period.get('academic_year', '')} ({left_stage_num})" if left_period else ""
            right_label = f"{right_period.get('academic_year', '')}" if right_period else ""

            left_courses = left_period.get("enrollments", []) if left_period else []
            right_courses = right_period.get("enrollments", []) if right_period else []

            doc_rows = []
            for left, right in zip_longest(left_courses, right_courses, fillvalue={}):
                lname = left.get("course_name_en" if is_english else "course_name_ar", "")
                rname = right.get("course_name_en" if is_english else "course_name_ar", "")
                doc_rows.append({
                    "left_name": lname, "left_subj": lname,
                    "left_mark": str(left.get("score", "")), "left_unit": str(left.get("credit_hours", "")),
                    "right_name": rname, "right_subj": rname,
                    "right_mark": str(right.get("score", "")), "right_unit": str(right.get("credit_hours", "")),
                })

            paired_semesters.append({
                "left_label": left_label, "right_label": right_label, "year_label": "",
                "rows": doc_rows, "year_s_l": str(left_stage_num), "year_s_r": str(right_stage_num)
            })
    else:
        for i in range(0, num_periods, 2):
            left_period = periods[i]
            right_period = periods[i + 1] if i + 1 < num_periods else None
            stage_num = (i // 2) + 1
            row_year_display = f"{left_period.get('academic_year', '')} - Stage {stage_num}" if left_period else ""
            left_label = "First Semester" if is_english else "الفصل الأول"
            right_label = "Second Semester" if is_english else "الفصل الثاني"

            left_courses = left_period.get("enrollments", []) if left_period else []
            right_courses = right_period.get("enrollments", []) if right_period else []

            doc_rows = []
            for left, right in zip_longest(left_courses, right_courses, fillvalue={}):
                lname = left.get("course_name_en" if is_english else "course_name_ar", "")
                rname = right.get("course_name_en" if is_english else "course_name_ar", "")
                doc_rows.append({
                    "left_name": lname, "left_subj": lname,
                    "left_mark": str(left.get("score", "")), "left_unit": str(left.get("credit_hours", "")),
                    "right_name": rname, "right_subj": rname,
                    "right_mark": str(right.get("score", "")), "right_unit": str(right.get("credit_hours", "")),
                })

            paired_semesters.append({
                "left_label": left_label, "right_label": right_label, "year_label": row_year_display,
                "rows": doc_rows, "year_s_l": str(stage_num), "year_s_r": str(stage_num)
            })

    # Academic Grade Calculation
    avg = data.get("average")
    avg_float = float(avg) if avg is not None else 0.0
    if avg_float >= 90:
        grade = "ممتاز" if not is_english else "Excellent"
    elif avg_float >= 80:
        grade = "جيد جداً" if not is_english else "Very Good"
    elif avg_float >= 70:
        grade = "جيد" if not is_english else "Good"
    elif avg_float >= 60:
        grade = "متوسط" if not is_english else "Medium"
    elif avg_float >= 50:
        grade = "مقبول" if not is_english else "Pass"
    else:
        grade = "—"

    ctx = {
        "Title": options.get("to_title") or ("Whom it May Concern" if is_english else "من يهمه الأمر"),
        "student_name": data.get("full_name_en" if is_english else "full_name_ar", ""),
        "Birthday": str(data.get("date_of_birth") or ""),
        "Birthplace": data.get("birthplace_en" if is_english else "birthplace_ar") or data.get("birthplace_other", ""),
        "Nationality": data.get("nationality_en" if is_english else "nationality_ar", ""),
        "admission_year": str(data.get("admission_year") or ""),
        "graduation_year": str(data.get("graduation_year") or ""),
        "department_id": data.get("dept_name_en" if is_english else "dept_name_ar", ""),
        "study_type": data.get("study_type", "صباحي"),
        "graduation_date": str(data.get("graduation_date") or ""),
        "graduation_semester": str(data.get("graduation_semester") or ""),
        "average": str(avg) if avg else "—",
        "Grade": grade,
        "sequence_ON": bool(options.get("opt_rank")),
        "Failure_ON": bool(options.get("opt_postpone")),
        "Passed_ON": bool(options.get("opt_second_trial")),
        "Summer_ON": bool(options.get("opt_summer")),
        "Sequence_of_Graduation": str(options.get("rank_val") or data.get("rank") or ""),
        "num_students": str(options.get("rank_total") or data.get("total_graduates") or ""),
        "Average_of_First_Student": str(options.get("rank_avg") or data.get("top_average") or ""),
        "Summer_Training_year": str(options.get("summer_year") or ""),
        "Postponement_and_Failure_Years": str(options.get("postpone_years") or ""),
        "Subjects_Passed_with_Second_Trial": str(options.get("second_trial_subjects") or ""),
        "order_number": str(options.get("order_num") or data.get("order_number") or "") if options.get("opt_order") else "",
        "order_date": str(options.get("order_date") or data.get("order_date") or "") if options.get("opt_order") else "",
        "paired_semesters": paired_semesters,
        "paired_years": paired_semesters,
        "semesters": paired_semesters,
    }

    # Signatories
    front_sigs = data.get("front_signatories", [])
    for i, sig in enumerate(front_sigs):
        idx = i + 1
        ctx[f"sig{idx}_name"] = sig.get("name_en" if is_english else "name_ar", "")
        ctx[f"sig{idx}_title"] = sig.get("academic_title_en" if is_english else "academic_title_ar", "")
        ctx[f"sig{idx}_resp"] = sig.get("responsibility_en" if is_english else "responsibility_ar", "")

    back_sigs = data.get("back_signatories", [])
    for i, sig in enumerate(back_sigs):
        idx = i + 5
        ctx[f"sig{idx}_name"] = sig.get("name_en" if is_english else "name_ar", "")
        ctx[f"sig{idx}_title"] = sig.get("academic_title_en" if is_english else "academic_title_ar", "")
        ctx[f"sig{idx}_resp"] = sig.get("responsibility_en" if is_english else "responsibility_ar", "")

    return ctx


class CertificateScreen:
    """
    Certificate Generation & Issuance Screen (NiceGUI version).
    Uses separated full-width sub-views for Student Profile/Transcript and Certificate Print Options.
    """

    def __init__(self, on_edit_student=None, initial_student=None):
        self.on_edit_student = on_edit_student
        self.student_repo = StudentRepository()
        self.cert_repo = CertificateRepository()
        self.personnel_repo = PersonnelRepository()

        self.selected_student = None
        self.student_full_data = None
        self.generated_file_path = None

        self.templates_dir = "templets"
        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir, exist_ok=True)

        self.container = ui.column().classes("w-full h-full p-6 gap-6 overflow-y-auto")
        self.build_ui()

        if initial_student:
            self.select_student(initial_student)

    def render_screen(self):
        """Re-renders the screen container while preserving the currently selected student data."""
        self.build_ui()
        if self.student_full_data:
            self.update_student_ui()
            self.show_info_view()

    def get_templates(self) -> list[str]:
        try:
            files = [f for f in os.listdir(self.templates_dir) if f.endswith(".docx") and not f.startswith("~")]
            return files if files else ["لا توجد قوالب / No templates found"]
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

                        UI.secondary_button("⬅️ العودة لبيانات الطالب", icon="arrow_forward", on_click=self.show_info_view).classes("text-xs px-4 py-2 font-bold")

                    # Row 1: Template Selector + Issued To + Edit Student (3 Components in 1 Row)
                    with ui.row().classes("w-full gap-4 items-center"):
                        self.template_sel = UI.select(
                            "قالب الوثيقة / Certificate Template",
                            options={t: t for t in self.get_templates()},
                            value=self.get_templates()[0] if self.get_templates() else None
                        ).classes("flex-1 text-sm")

                        self.to_input = UI.text_input(
                            "إلى (الجهة المعنية) / Issued To",
                            value="من يهمه الأمر",
                            placeholder="اسم الجهة الموجه إليها..."
                        ).classes("flex-1 text-sm")

                        UI.secondary_button("تعديل الطالب / Edit Student", icon="edit", on_click=self.handle_edit_student).classes("text-sm px-4 py-3.5 mt-2")

                    ui.separator().classes("my-1")

                    # Row 2: University Order Section (3 Components in 1 Row)
                    with UI.card().classes("w-full p-4 gap-3 bg-[var(--bg-main)] rounded-xl border border-[var(--border-default)]"):
                        ui.label("بيانات الأمر الجامعي — University Order").classes("text-xs font-bold app-text-accent")
                        with ui.row().classes("w-full gap-4 items-center"):
                            self.sw_order = UI.switch("تفعيل الأمر الجامعي / Enable Order", value=False).classes("w-64")
                            self.inp_order_num = UI.text_input("رقم الأمر الجامعي / Order No", value="").classes("flex-1 text-sm")
                            self.inp_order_date = UI.text_input("تاريخ الأمر / Order Date", value="").classes("flex-1 text-sm")

                    # Row 3: Graduation Rank Section (4 Components in 1 Row)
                    with UI.card().classes("w-full p-4 gap-3 bg-[var(--bg-main)] rounded-xl border border-[var(--border-default)]"):
                        ui.label("بيانات تسلسل التخرج والترتيب — Graduation Rank").classes("text-xs font-bold app-text-accent")
                        with ui.row().classes("w-full gap-4 items-center"):
                            self.sw_rank = UI.switch("تفعيل تسلسل التخرج / Enable Rank", value=False).classes("w-64")
                            self.inp_rank_val = UI.text_input("تسلسل الطالب / Rank", value="").classes("flex-1 text-sm")
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

                        self.btn_open = UI.secondary_button(
                            "فتح المعاينة والطباعة",
                            icon="print",
                            on_click=self.print_certificate
                        ).classes("flex-1 py-3 text-base")

                        UI.secondary_button("العودة لبيانات الطالب", icon="arrow_forward", on_click=self.show_info_view).classes("px-6 py-3 text-sm")

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
        student_id = student_row["id"]

        try:
            self.student_full_data = self.cert_repo.get_full_certificate_data(student_id)
            if not self.student_full_data:
                UI.notify("لا توجد بيانات دراسية للطالب المحدد / No academic data found", type="warning")
                return

            self.update_student_ui()
            # Auto preselect template matching study system calculation rule
            calc_rule = str(self.student_full_data.get("calculation_rule") or "annual").lower()
            templates = self.get_templates()
            matched_tpl = next((t for t in templates if calc_rule in t.lower()), templates[0] if templates else None)
            if matched_tpl:
                self.template_sel.value = matched_tpl

            self.show_info_view()
        except Exception as e:
            log.error(f"Error loading student: {e}")
            UI.notify(e, type="negative")

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
        if not data:
            return

        # ── 1. Auto Extract Second Trial Courses & Calculate Default Summer Training Year ──
        second_courses = []
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

        # Default summer training year
        summer_val = data.get("summer_training_data")
        grad_year = data.get("graduation_year")
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

        if data.get("rank"):
            self.sw_rank.value = True
            self.inp_rank_val.value = str(data.get("rank") or "")
            self.inp_rank_total.value = str(data.get("total_graduates") or "")
            self.inp_rank_avg.value = str(round(float(data.get("top_average") or 0), 2) if data.get("top_average") else "")

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
                        UI.secondary_button("تعديل الطالب / Edit Student", icon="edit", on_click=self.handle_edit_student).classes("text-xs px-4 py-2.5")

            # 4 Unified Non-Duplicated Key Metric Cards
            avg = data.get("average")
            avg_str = f"{float(avg):.2f}%" if avg is not None else "—"
            rank_val = data.get("rank")
            total_grad = data.get("total_graduates")
            rank_str = f"المرتبة {rank_val} من {total_grad} خريج" if rank_val and total_grad else "—"
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

            # Academic Transcript Table Section (Spacious Cards for Each Stage)
            ui.label("السجل الأكاديمي والدرجات — Academic Transcript").classes("text-lg font-extrabold app-text-primary mt-2 tracking-wide")
            with ui.column().classes("w-full border border-[var(--border-default)] rounded-2xl p-5 bg-[var(--bg-main)] gap-5 max-h-[540px] overflow-y-auto"):
                periods = data.get("periods", [])
                if not periods:
                    ui.label("لا توجد سجلات دراسية / No course records").classes("text-sm app-text-muted italic p-4")
                for p in periods:
                    stg = p.get("stage_number", "")
                    year = p.get("academic_year", "")
                    enrs = p.get("enrollments", [])

                    with ui.column().classes("w-full gap-3 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)]"):
                        with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)]"):
                            ui.label(f"المرحلة {stg} — العام الدراسي ({year})").classes("text-sm font-extrabold app-text-accent tracking-wide")
                            ui.label(f"عدد المواد: {len(enrs)}").classes("text-xs app-text-muted font-medium")

                        with ui.column().classes("w-full gap-2.5"):
                            for enr in enrs:
                                cname = enr.get("course_name_ar") or enr.get("course_name_en") or ""
                                score = enr.get("score", "—")
                                units = enr.get("credit_hours", 0)
                                pr = str(enr.get("passed_round", "1"))
                                is_2nd = (pr in ('2', '3') or enr.get("is_second_round"))

                                with ui.row().classes("w-full justify-between items-center text-sm py-2.5 px-4 rounded-xl bg-[var(--bg-main)] transition-all border border-[var(--border-default)] hover:border-amber-500/30"):
                                    with ui.row().classes("items-center gap-3"):
                                        ui.label(cname).classes("app-text-primary font-bold text-sm")
                                        if is_2nd:
                                            ui.label("الدور الثاني").classes("px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-amber-500/20 text-amber-400 border border-amber-500/30")

                                    with ui.row().classes("items-center gap-4"):
                                        ui.label(f"الدرجة: {score}").classes("font-extrabold text-emerald-400 font-mono text-sm")
                                        ui.label(f"{units} وحدات").classes("text-xs font-bold px-3 py-1 bg-[var(--bg-card)] rounded-lg text-slate-300 font-mono border border-[var(--border-default)]")

    def generate_certificate(self) -> bool:
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

        # Prepare options dictionary
        is_en = "en" in tpl_name.lower() or "eng" in tpl_name.lower()
        options = {
            "is_english": is_en,
            "to_title": self.to_input.value.strip(),
            "opt_order": self.sw_order.value,
            "order_num": self.inp_order_num.value.strip(),
            "order_date": self.inp_order_date.value.strip(),
            "opt_rank": self.sw_rank.value,
            "rank_val": self.inp_rank_val.value.strip(),
            "rank_total": self.inp_rank_total.value.strip(),
            "rank_avg": self.inp_rank_avg.value.strip(),
            "opt_summer": self.sw_summer.value,
            "summer_year": self.inp_summer_year.value.strip(),
            "opt_postpone": self.sw_postpone.value,
            "postpone_years": self.inp_postpone_years.value.strip(),
            "opt_second_trial": self.sw_second.value,
            "second_trial_subjects": self.inp_second_subjects.value.strip(),
        }

        try:
            ctx = build_certificate_context(self.student_full_data, options)

            # Ensure output directory exists
            out_dir = os.path.abspath("certificates")
            os.makedirs(out_dir, exist_ok=True)

            student_name = ctx.get("student_name", "Student")
            safe_student = re.sub(r'[\\/*?:"<>|]', "", student_name).strip() or "Student"
            safe_tpl = re.sub(r'[\\/*?:"<>|]', "", os.path.splitext(tpl_name)[0]).strip()
            out_file = os.path.join(out_dir, f"{safe_tpl} - {safe_student}.docx")

            doc = DocxTemplate(tpl_path)
            doc.render(ctx)
            doc.save(out_file)

            self.generated_file_path = out_file
            UI.notify(f"تم إصدار وتوليد الوثيقة بنجاح: {os.path.basename(out_file)}", type="positive")

            # Trigger automatic browser download
            ui.download(out_file, filename=os.path.basename(out_file))
            return True
        except Exception as err:
            log.error(f"Error generating certificate: {err}")
            UI.notify(err, type="negative")
            return False

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

    def print_certificate(self):
        """Generates the certificate and opens the Windows print dialog ready to print."""
        if not self.generated_file_path or not os.path.exists(self.generated_file_path):
            success = self.generate_certificate()
            if not success:
                return

        if self.generated_file_path and os.path.exists(self.generated_file_path):
            try:
                # Triggers default Windows print dialog for the generated .docx file
                os.startfile(self.generated_file_path, "print")
                UI.notify("تم تجهيز وثيقة الطالب وإرسالها للطباعة / Document sent to printer", type="positive")
            except Exception as err:
                log.warning(f"Direct print command error: {err}, opening for printing...")
                try:
                    os.startfile(self.generated_file_path)
                    UI.notify("تم فتح الوثيقة (يرجى الضغط على Ctrl+P للطباعة) / Document opened for printing", type="info")
                except Exception as e2:
                    UI.notify(f"تعذر فتح الوثيقة للطباعة: {e2}", type="negative")

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
