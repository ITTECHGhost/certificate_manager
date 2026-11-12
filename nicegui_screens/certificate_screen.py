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
from nicegui_ui.template_constants import get_friendly_template_name, get_template_label_ar
from nicegui_ui.issue_helpers import (
    GRADUATES_SOURCES, filter_templates_for_system, graduates_count, group_transcript, template_option_label,
)
from utils.display_format import format_average
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

        self.container = ui.column().classes("w-full gap-4")
        self.build_ui()

        if initial_student:
            self.select_student(initial_student)

    def _format_template_options(self, template_files: list[str]) -> dict:
        """Template picker options: an Arabic display name, never the file name."""
        return {
            t: (template_option_label(t) if t and not t.startswith("لا توجد") else t)
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

    def _ensure_gender(self, student_id, student_row: dict | None = None):
        """The certificate data may lack the gender (older server procedure): take it from the student record."""
        data = self.student_full_data
        if not isinstance(data, dict):
            return
        info = data.get("student_info")
        if not isinstance(info, dict):
            info = {}
            data["student_info"] = info
        if info.get("gender") not in (None, ""):
            return
        gender = (student_row or {}).get("gender")
        if gender in (None, ""):
            try:
                gender = (self.student_repo.get_by_id(student_id) or {}).get("gender")
            except Exception:
                gender = None
        if gender not in (None, ""):
            info["gender"] = gender

    def get_templates(self, data: dict = None) -> list[str]:
        """
        Returns docx templates filtered by the student's study system (semester vs year/annual).
        If the student is semester-based ('semester'), returns templates matching 'semester' or 'sem'.
        If the student is annual/year-based ('year' / 'annual'), returns templates matching 'year' or 'annual'.
        """
        try:
            files = [f for f in os.listdir(self.templates_dir) if f.endswith(".docx") and not f.startswith("~")]
            if not files:
                return ["لا توجد قوالب"]

            return filter_templates_for_system(files, data or self.student_full_data or {})
        except Exception:
            return ["لا توجد قوالب"]

    # ── Wizard: 1 Student → 2 Document → 3 Review and issue ─────────────────
    STEPS = ["الطالب", "الوثيقة", "المراجعة والإصدار"]

    def build_ui(self):
        self.container.clear()
        self.step = 1
        with self.container:
            with UI.card().classes("gap-5"):
                @ui.refreshable
                def stepper_view():
                    UI.stepper(self.STEPS, self.step, on_step=self._go_step)

                stepper_view()
                self._stepper_view = stepper_view

                # The chosen student, shown on steps 2 and 3
                self.student_bar = ui.row().classes("w-full items-center gap-3 no-wrap")
                self.student_bar.set_visibility(False)

                # ── STEP 1: pick the student ───────────────────────────────
                self.view_student_info = ui.column().classes("w-full gap-3")
                with self.view_student_info:
                    self.search_input = UI.search_input(
                        placeholder="ابحث باسم الطالب بالعربية أو الإنكليزية",
                        on_change=lambda e: self.perform_search(),
                    ).props("autofocus")
                    self.search_input.on("keydown.enter", lambda: self.perform_search())
                    self.search_caption = ui.label("أحدث الطلاب").classes("app-caption")
                    self.search_results_container = ui.column().classes("w-full gap-2")
                    # kept for older callers; the results list is always visible now
                    self.search_results_card = self.search_results_container
                    self.student_info_container = self.search_results_container

                # ── STEP 2: document and options ───────────────────────────
                self.view_print_options = ui.column().classes("w-full gap-4")
                self.view_print_options.set_visibility(False)
                with self.view_print_options:
                    # Shown when an issued certificate is opened again: issuing updates that record
                    self.edit_mode_banner = ui.row().classes("app-chip--warning w-full items-center gap-2 no-wrap rounded-lg p-3")
                    self.edit_mode_banner.set_visibility(False)
                    with self.edit_mode_banner:
                        ui.icon("edit_document", size="20px").classes("shrink-0")
                        self.edit_mode_label = ui.label("تعديل قيد الوثيقة").classes("text-sm font-semibold")

                    with ui.element("div").classes("app-two-col"):
                        with ui.column().classes("gap-3 min-w-0"):
                            initial_templates = self.get_templates()
                            self.template_sel = UI.select(
                                "القالب",
                                options=self._format_template_options(initial_templates),
                                value=initial_templates[0] if initial_templates else None
                            ).classes("w-full app-template-select")
                            # Two lines: the template name, then its variant (language • marks)
                            self.template_sel.add_slot("option", r"""
                                <q-item v-bind="props.itemProps">
                                  <q-item-section>
                                    <q-item-label>{{ String(props.opt.label).split('\n')[0] }}</q-item-label>
                                    <q-item-label caption>{{ String(props.opt.label).split('\n')[1] || '' }}</q-item-label>
                                  </q-item-section>
                                </q-item>""")
                            self.template_sel.add_slot("selected-item", r"""
                                <div class="app-template-value">
                                  <div>{{ String(props.opt.label).split('\n')[0] }}</div>
                                  <div class="app-caption">{{ String(props.opt.label).split('\n')[1] || '' }}</div>
                                </div>""")

                            self.to_input = UI.text_input(
                                "إلى (الجهة المعنية)",
                                value="من يهمه الأمر",
                            ).classes("w-full")

                        with ui.column().classes("gap-3 min-w-0"):
                            with ui.row().classes("w-full items-center gap-1 no-wrap"):
                                init_cert_num = self.issued_cert_repo.get_next_number()
                                self.cert_number_input = UI.text_input(
                                    "رقم الوثيقة",
                                    value=init_cert_num,
                                    placeholder="مثال: 420/44"
                                ).classes("flex-1 min-w-0")

                                def _refresh_cert_number():
                                    next_num = self.issued_cert_repo.get_next_number()
                                    self.cert_number_input.value = next_num
                                    UI.notify(f"الرقم المقترح: {next_num}", type="info")

                                UI.icon_button("autorenew", "الرقم التالي المتاح", on_click=_refresh_cert_number)

                            from datetime import datetime
                            today_str = datetime.now().strftime("%Y-%m-%d")
                            self.issue_date_input = UI.text_input(
                                "تاريخ الإصدار",
                                value=today_str
                            ).classes("w-full").props("readonly")

                    # What the document includes: one clear switch per item; its fields show when on
                    ui.label("محتوى الوثيقة").classes("app-section-title")
                    with ui.column().classes("w-full gap-2"):
                        def option_row(label: str):
                            row = ui.row().classes("app-option-row w-full items-center gap-3")
                            with row:
                                sw = UI.switch(label, value=False).classes("w-48 shrink-0")
                                fields = ui.row().classes("flex-1 min-w-[220px] gap-3 items-center")
                            fields.bind_visibility_from(sw, "value")
                            return sw, fields

                        self.sw_order, f = option_row("الأمر الجامعي")
                        with f:
                            self.inp_order_num = UI.text_input("رقم الأمر الجامعي", value="").classes("flex-1 min-w-[160px]")
                            self.inp_order_date = UI.date_input("تاريخ الأمر", value="").classes("flex-1 min-w-[160px]")

                        self.sw_rank, f = option_row("تسلسل التخرج")
                        with f:
                            self.inp_rank_val = UI.text_input("تسلسل الطالب", value="").classes("flex-1 min-w-[160px]")
                        self._build_ranks_panel()

                        self.sw_summer, f = option_row("التدريب الصيفي")
                        with f:
                            self.inp_summer_year = UI.text_input("سنة التدريب", value="").classes("flex-1 min-w-[160px]")

                        self.sw_postpone, f = option_row("سنوات التأجيل")
                        with f:
                            self.inp_postpone_years = UI.text_input("سنوات التأجيل", value="").classes("w-full")

                        self.sw_second, f = option_row("الدور الثاني")
                        with f:
                            self.inp_second_subjects = UI.text_input("مواد الدور الثاني", value="").classes("w-full")

                    with ui.expansion("خيارات متقدمة", icon="tune").classes("w-full"):
                        with ui.column().classes("w-full gap-3 pt-2"):
                            def on_grouping_change(e):
                                if not hasattr(self, 'student_full_data') or not self.student_full_data: return
                                student_id = self.student_full_data.get('student_id') or self.student_full_data.get('id')
                                if not student_id: return
                                new_mode = getattr(e, 'value', e) or "DEFAULT"
                                self.current_grouping_mode = new_mode
                                self.student_full_data = self.cert_repo.get_full_certificate_data(student_id, grouping_mode=new_mode)
                                self._ensure_gender(student_id, getattr(self, "selected_student", None))
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
                                "ترتيب المواد في الجدول",
                                options=grouping_options,
                                value="DEFAULT",
                                on_change=on_grouping_change
                            ).classes("w-full")

                            def on_rank_source_change(e):
                                if not getattr(self, "student_full_data", None):
                                    return
                                src = e.value
                                if src == "manual":
                                    self.inp_rank_total.props(remove="readonly")
                                    val = graduates_count("manual", self.student_full_data, self.inp_rank_total.value or "")
                                else:
                                    self.inp_rank_total.props("readonly")
                                    val = graduates_count(src, self.student_full_data)
                                self.inp_rank_total.value = val
                                self.student_full_data["total_graduates"] = val

                            with ui.row().classes("w-full gap-3"):
                                self.rank_source_sel = UI.select(
                                    "مصدر عدد الخريجين",
                                    options=dict(GRADUATES_SOURCES),
                                    value="order",
                                    on_change=on_rank_source_change
                                ).classes("flex-1 min-w-[200px]")
                                self.inp_rank_total = UI.text_input("إجمالي الخريجين", value="").classes("flex-1 min-w-[160px]").props("readonly")

                                def _manual_total(e):
                                    if self.rank_source_sel.value == "manual" and getattr(self, "student_full_data", None):
                                        self.student_full_data["total_graduates"] = (e.value or "").strip()
                                self.inp_rank_total.on_value_change(_manual_total)
                                self.inp_rank_avg = UI.text_input("معدل الطالب الأول", value="").classes("flex-1 min-w-[160px]")

                            UI.ghost_button("تعديل بيانات الطالب", icon="edit", on_click=self.handle_edit_student)

                    with ui.row().classes("app-dialog-actions"):
                        UI.back_button(lambda: self._go_step(1))
                        ui.space()
                        UI.primary_button("التالي", icon="arrow_back", on_click=lambda: self._go_step(3))

                # ── STEP 3: review and issue ──────────────────────────────
                self.view_review = ui.column().classes("w-full gap-4")
                self.view_review.set_visibility(False)
                with self.view_review:
                    self.review_container = ui.column().classes("w-full gap-4")
                    with ui.row().classes("app-dialog-actions"):
                        UI.back_button(lambda: self._go_step(2))
                        ui.space()
                        UI.secondary_button("حفظ وفتح في Word", icon="description", on_click=self.generate_and_open_word)
                        self.btn_generate = UI.primary_button("إصدار وطباعة", icon="print", on_click=self.print_certificate)

        self._show_recent_students()

    def _go_step(self, n: int) -> None:
        """Show wizard step n (1-3). Steps 2 and 3 need a student."""
        if n >= 2 and not self.student_full_data:
            UI.notify("اختر الطالب أولاً", type="warning")
            n = 1
        self.step = n
        self.view_student_info.set_visibility(n == 1)
        self.view_print_options.set_visibility(n == 2)
        self.view_review.set_visibility(n == 3)
        self.student_bar.set_visibility(n >= 2 and bool(self.student_full_data))
        if n == 3:
            self._render_review()
        self._stepper_view.refresh()

    def show_info_view(self):
        """Older name: after a student is loaded the next thing to do is the document step."""
        self._go_step(2 if self.student_full_data else 1)

    def show_options_view(self):
        self._go_step(2)

    def _student_table(self, rows: list[dict]):
        """Clickable list of students for step 1."""
        table_rows = [{
            "id": r.get("student_id") or r.get("id"),
            "name": r.get("full_name_ar") or r.get("name_ar") or "—",
            "name_en": r.get("full_name_en") or r.get("name_en") or "",
            "dept": r.get("dept_name_ar") or r.get("department_name_ar") or "—",
            "year": str(r.get("graduation_year") or "").replace("N/A", "") or "—",
            "raw": r,
        } for r in rows]
        table = UI.data_table([
            {"name": "name", "label": "الاسم", "field": "name", "align": "right"},
            {"name": "dept", "label": "القسم", "field": "dept"},
            {"name": "year", "label": "سنة التخرج", "field": "year"},
        ], table_rows, clickable=True)
        table.add_slot("body-cell-name", """
            <q-td :props="props">
                <div class="flex flex-col text-right leading-tight">
                    <span class="font-semibold app-text-primary">{{ props.row.name }}</span>
                    <span class="app-caption" dir="ltr">{{ props.row.name_en }}</span>
                </div>
            </q-td>
        """)
        table.on("rowClick", lambda e: self.select_student(e.args[1].get("raw") or e.args[1]))
        return table

    def _show_recent_students(self) -> None:
        """Step 1 opens on the most recently added students, so the usual case is one click."""
        self.search_caption.set_text("أحدث الطلاب")
        self.search_results_container.clear()
        with self.search_results_container:
            try:
                from nicegui_ui.state import app_session
                scope = app_session.get_access().get("dept_scope")
                rows = self.student_repo.search_students_paginated(
                    query="", limit=8, offset=0, dept_id=scope[0] if scope else None
                ) or []
            except Exception as e:
                log.warning(f"Recent students failed: {e}")
                rows = []
            if rows:
                self._student_table(rows)
            else:
                UI.empty_state("لا يوجد طلاب بعد", "أضف الطالب من شاشة الطلاب ثم عد إلى هنا.", icon="people")

    def perform_search(self):
        term = ""
        if hasattr(self, "search_input") and self.search_input and self.search_input.value:
            term = str(self.search_input.value).strip()
        elif hasattr(self, "search_term") and self.search_term:
            term = str(self.search_term).strip()

        if len(term) < 2:
            self._show_recent_students()
            return

        try:
            results = self.student_repo.search(term, limit=12)
            self.search_caption.set_text(f"نتائج البحث عن «{term}»")
            self.search_results_container.clear()
            with self.search_results_container:
                if not results:
                    UI.empty_state("لا يوجد طالب بهذا الاسم", "تحقق من الاسم أو جرّب جزءًا منه.", icon="search_off")
                else:
                    self._student_table(results)
        except Exception as e:
            log.error(f"Search failed: {e}")
            UI.notify(f"تعذر البحث: {e}. تحقق من الاتصال وأعد المحاولة.", type="negative")

    def render_preview_grid(self):
        pass

    def render_empty_student_info(self):
        self._show_recent_students()

    def select_student(self, student_row):
        self.selected_student = student_row
        student_id = student_row.get("student_id") or student_row.get("id")

        # A new student starts clean: no edit mode and no document from the previous one.
        self.reissue_cert_id = None
        self.generated_file_path = None
        if hasattr(self, "edit_mode_banner") and self.edit_mode_banner:
            self.edit_mode_banner.set_visibility(False)
        if hasattr(self, "btn_generate") and self.btn_generate:
            self.btn_generate.text = "إصدار وطباعة"
        self.current_grouping_mode = getattr(self, "current_grouping_mode", "DEFAULT")

        try:
            self.student_full_data = self.cert_repo.get_full_certificate_data(
                student_id, grouping_mode="DEFAULT"
            )
            if not self.student_full_data:
                UI.notify("لا توجد بيانات دراسية لهذا الطالب. أضف مراحله ودرجاته من شاشة الطلاب.", type="warning")
                return
            self._ensure_gender(student_id, student_row)

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

            # Arriving with an existing certificate record (Issued Certificates → edit)
            if self.initial_cert_record:
                student_display_name = student_row.get("full_name_ar") or self.student_full_data.get("full_name_ar", "")
                self._enter_edit_mode(self.initial_cert_record, student_display_name)
                self.initial_cert_record = None  # used once; selecting another student must not re-enter it

            # Picking the student completes step 1; the defaults are ready on step 2
            self._go_step(2)
        except Exception as e:
            log.error(f"Error loading student: {e}")
            UI.notify(f"تعذر تحميل بيانات الطالب: {e}", type="negative")

    def _render_student_bar(self) -> None:
        """Who the document is for, with a way back to step 1."""
        data = self.student_full_data or {}
        self.student_bar.clear()
        with self.student_bar:
            ui.icon("person", size="24px").classes("app-text-accent shrink-0")
            with ui.column().classes("gap-0 min-w-0"):
                ui.label(data.get("full_name_ar", "")).classes("app-text-primary font-semibold")
                sub = " • ".join(x for x in (data.get("dept_name_ar") or "", f"المعدل {format_average(data.get('average'))}") if x)
                ui.label(sub).classes("app-caption")
            ui.space()
            UI.ghost_button("تغيير الطالب", icon="swap_horiz", on_click=lambda: self._go_step(1))

    def _render_review(self) -> None:
        """Step 3: what will be issued, any number clash inline, and the transcript as flat rows."""
        data = self.student_full_data or {}
        self.review_container.clear()
        tpl = self.template_sel.value if self.template_sel else ""
        cert_num = (self.cert_number_input.value or "").strip()
        student_id = data.get("id") or data.get("student_id")
        included = [name for sw, name in (
            (self.sw_order, "الأمر الجامعي"), (self.sw_rank, "تسلسل التخرج"), (self.sw_summer, "التدريب الصيفي"),
            (self.sw_postpone, "سنوات التأجيل"), (self.sw_second, "الدور الثاني"),
        ) if sw.value]

        with self.review_container:
            UI.dl([
                ("الطالب", data.get("full_name_ar")),
                ("القسم", data.get("dept_name_ar")),
                ("الوثيقة", self._format_template_options([tpl]).get(tpl) if tpl else ""),
                ("رقم الوثيقة", cert_num),
                ("إلى", (self.to_input.value or "").strip() or "من يهمه الأمر"),
                ("تاريخ الإصدار", self.issue_date_input.value),
                ("يتضمن", "، ".join(included) or "لا شيء إضافي"),
                ("المعدل", format_average(data.get("average"))),
            ])

            # Number clash, shown here instead of after pressing issue
            self.btn_generate.enable()
            dup = {}
            if cert_num and student_id:
                try:
                    dup = self.issued_cert_repo.check_duplicate(cert_num, student_id) or {}
                except Exception as exc:
                    log.warning(f"Duplicate check failed: {exc}")
            if dup.get("exists"):
                reissue_id = getattr(self, "reissue_cert_id", None)
                if reissue_id and dup.get("certificate_id") == reissue_id:
                    msg, variant = f"سيُحدَّث قيد الوثيقة رقم ({cert_num}) نفسه.", "accent"
                elif not dup.get("same_student"):
                    owner = dup.get("owner_name") or "طالب آخر"
                    msg, variant = f"الرقم ({cert_num}) مستخدم للطالب ({owner}). ارجع إلى الخطوة السابقة واختر رقمًا آخر.", "danger"
                    self.btn_generate.disable()
                else:
                    msg, variant = (f"الرقم ({cert_num}) صدر سابقًا لهذا الطالب. الإصدار يحدّث القيد؛ "
                                    "أتلف النسخة الورقية القديمة."), "warning"
                with ui.row().classes(f"app-chip--{variant} w-full items-start gap-2 no-wrap rounded-lg p-3"):
                    ui.icon("warning" if variant != "accent" else "info", size="20px").classes("shrink-0")
                    ui.label(msg).classes("text-sm")

            courses = data.get("courses_grouped") or []
            with ui.expansion(f"السجل الأكاديمي ({len(courses)} مادة)", icon="list_alt").classes("w-full"):
                self._transcript_table(courses, data)

    def _transcript_table(self, courses: list[dict], data: dict) -> None:
        """The transcript as flat rows: stage/year, course, mark, units, round."""
        if not courses:
            UI.empty_state("لا توجد درجات مسجلة", "أضف المراحل والدرجات من صفحة الطالب.", icon="list_alt")
            return
        st_info = data.get("student_info") or {}
        if isinstance(st_info, list) and st_info:
            st_info = st_info[0]
        is_sem = "semester" in str(st_info.get("period_display") or data.get("period_display") or "").lower()
        for gi, group in enumerate(group_transcript(courses, is_sem)):
            with ui.column().classes("app-transcript-group w-full gap-2"):
                with ui.row().classes("app-transcript-group-head w-full items-center no-wrap"):
                    ui.label(group["header"]).classes("font-semibold")
                    ui.space()
                    ui.label(f"{len(group['courses'])} مادة").classes("app-caption")
                rows = []
                for i, c in enumerate(group["courses"]):
                    pr = str(c.get("passed_round") or "1")
                    rows.append({
                        "id": f"{gi}-{i}",
                        "course": c.get("subject_name") or c.get("course_name_ar") or c.get("course_name_en") or "—",
                        "mark": c.get("mark", "—"),
                        "unit": c.get("unit", "—"),
                        "round": "الدور الثاني" if (pr in ("2", "3") or c.get("is_second_round")) else "",
                    })
                table = UI.data_table([
                    {"name": "course", "label": "المادة", "field": "course", "align": "right"},
                    {"name": "mark", "label": "الدرجة", "field": "mark"},
                    {"name": "unit", "label": "الوحدات", "field": "unit"},
                    {"name": "round", "label": "", "field": "round"},
                ], rows)
                table.add_slot("body-cell-round", """
                    <q-td :props="props"><span v-if="props.value" class="app-chip app-chip--warning">{{ props.value }}</span></q-td>
                """)

    def handle_edit_student(self):
        """Triggers navigation to Students Management screen to edit selected student."""
        if not self.selected_student:
            return

        if self.on_edit_student:
            self.on_edit_student(self.selected_student)
        else:
            UI.notify("الانتقال لصفحة تعديل الطالب...", type="info")

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

        # Graduates count: the graduation order first, else the student's own information
        src = "order" if graduates_count("order", data) else "student"
        total_grad_def = graduates_count(src, data)
        if hasattr(self, "rank_source_sel") and self.rank_source_sel:
            self.rank_source_sel.set_value(src)
            self.inp_rank_total.props("readonly")
        data["total_graduates"] = total_grad_def

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

        self._fill_ranks(data)

        # Steps 2 and 3 show who the document is for; the review follows any change
        self._render_student_bar()
        if getattr(self, "step", 1) == 3:
            self._render_review()

    # ── Graduation sequences: calculated from the averages, editable before printing ──
    RANK_ROWS = [
        ("dept_term_system", "القسم: نفس الفصل ونفس نظام الدراسة"),
        ("dept_term", "القسم: نفس الفصل، كل الأنظمة"),
        ("dept_system", "القسم: نفس النظام، كل الفصول"),
        ("dept_year", "القسم: السنة كاملة"),
        ("college_term_system", "الكلية: نفس الفصل ونفس نظام الدراسة"),
        ("college_term", "الكلية: نفس الفصل، كل الأنظمة"),
        ("college_system", "الكلية: نفس النظام، كل الفصول"),
        ("college_year", "الكلية: السنة كاملة"),
        ("first_student_college_seq", "تسلسل الخريج الأول للقسم في قائمة الكلية"),
    ]

    def _build_ranks_panel(self) -> None:
        self.rank_inputs = {}
        with ui.expansion("التسلسلات المحسوبة (قابلة للتعديل)", icon="format_list_numbered").classes("w-full") \
                .bind_visibility_from(self.sw_rank, "value"):
            self.ranks_note = ui.label("").classes("app-caption")
            with ui.grid(columns=3).classes("w-full gap-2 items-center"):
                for key, label in self.RANK_ROWS:
                    ui.label(label).classes("text-sm app-text-primary")
                    seq = UI.text_input("التسلسل", value="").classes("w-full")
                    of = UI.text_input("من أصل", value="").classes("w-full")
                    self.rank_inputs[key] = (seq, of)
            UI.ghost_button("إعادة الحساب", icon="refresh", on_click=lambda: self._fill_ranks(
                getattr(self, "student_full_data", None) or {}, force=True))

    def _fill_ranks(self, data: dict, force: bool = False) -> None:
        if not getattr(self, "rank_inputs", None):
            return
        student_id = data.get("student_id") or data.get("id")
        from utils.display_format import average_is_valid
        if not average_is_valid(data.get("average")):
            ui.notify(f"معدل الطالب ({data.get('average')}) أكبر من 100: صحّحه من تعديل بيانات الطالب قبل الإصدار",
                      type="warning", timeout=10000)
        from data.repositories.students import get_graduation_ranks
        ranks = get_graduation_ranks(student_id) if student_id else {}
        for key, (seq, of) in self.rank_inputs.items():
            r = ranks.get(key) or {}
            seq.value = str(r.get("seq") or "")
            of.value = str(r.get("of") or "")
        if not ranks:
            self.ranks_note.set_text("لا توجد تسلسلات محسوبة: الطالب غير مرتبط بأمر تخرج، أو البرنامج غير متصل بالخادم. "
                                     "اكتبها يدوياً.")
            return
        self.ranks_note.set_text(f"محسوبة من معدلات خريجي سنة {ranks.get('year')} المرتبطين بأوامر التخرج. "
                                 "إذا لم يكن كل الخريجين مدخلين، صحّح الأرقام يدوياً.")
        mine = (ranks.get("dept_system") or {}).get("seq")
        if mine and (force or not (self.inp_rank_val.value or "").strip()):
            self.inp_rank_val.value = str(mine)
            self.sw_rank.value = True

    def _ranks_from_inputs(self) -> dict:
        return {key: {"seq": (seq.value or "").strip(), "of": (of.value or "").strip()}
                for key, (seq, of) in (getattr(self, "rank_inputs", None) or {}).items()}

    def _enter_edit_mode(self, rec: dict, student_display_name: str = "") -> None:
        """Loads an issued certificate record into the form; generating then updates that record."""
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
        if hasattr(self, "edit_mode_banner") and self.edit_mode_banner:
            if hasattr(self, "edit_mode_label") and self.edit_mode_label:
                self.edit_mode_label.text = f"تعديل قيد الوثيقة رقم ({cert_num or self.reissue_cert_id}) للطالب ({student_display_name}). الإصدار يحدّث هذا القيد."
            self.edit_mode_banner.set_visibility(True)

        if hasattr(self, "btn_generate") and self.btn_generate:
            self.btn_generate.text = "تحديث وطباعة"

    def _show_reissue_warning_modal(self, cert_num: str, tpl_name: str, options: dict, reissue_cert_id: Optional[int] = None) -> None:
        """Opens a confirmation modal warning the user to destroy the old physical paper copy before re-issuing."""
        with ui.dialog() as dialog, UI.card().classes("w-full max-w-lg p-6 gap-4 bg-[var(--bg-card)] rounded-2xl border border-[var(--border-default)] shadow-2xl"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("warning", size="lg").classes("text-amber-500")
                with ui.column().classes("gap-0"):
                    ui.label("تنبيه: إعادة إصدار وثيقة برقم مسجل مسبقاً").classes("text-base font-bold app-text-primary")

            ui.separator().classes("my-1")

            with ui.column().classes("gap-2 text-sm app-text-primary leading-relaxed bg-amber-50 dark:bg-amber-950/30 p-4 rounded-xl border border-amber-200 dark:border-amber-800"):
                ui.label(f"⚠️ إن رقم الوثيقة ({cert_num}) مسجل مسبقاً لهذا الطالب في السجل الرسمي.").classes("font-bold text-amber-800 dark:text-amber-300")
                ui.label("وفقاً لتعليمات السجل والوثائق، فإن إعادة إصدار الوثيقة بنفس الرقم تتطلب أولاً إتلاف النسخة الورقية السابقة منعاً للازدواجية.").classes("text-xs leading-normal")
                ui.label("هل ترغب في متابعة التوليد وتحديث بيانات القيد في السجل؟").classes("text-xs font-semibold")

            with ui.row().classes("w-full justify-end gap-3 mt-2"):
                UI.secondary_button("إلغاء", icon="close", on_click=dialog.close).classes("text-xs px-4 py-2")
                
                def _confirm_reissue():
                    dialog.close()
                    if reissue_cert_id:
                        options["reissue_cert_id"] = reissue_cert_id
                    self.generate_docx(tpl_name, options)

                UI.danger_button("تأكيد وإتلاف القديمة", icon="done", on_click=_confirm_reissue).classes("text-xs px-4 py-2 font-bold")

        dialog.open()

    def _find_issued_record(self, student_id, issue_date: str, to_title: str, tpl_type: str) -> dict | None:
        """The issued record matching the database's unique key (student, date, recipient, template)."""
        for rec in self.issued_cert_repo.get_by_student(student_id) or []:
            if (str(rec.get("issue_date") or "")[:10] == (issue_date or "")[:10]
                    and (rec.get("to_title") or "").strip() == to_title
                    and (rec.get("template_type") or "").strip() == tpl_type):
                return rec
        return None

    def _show_already_issued_modal(self, rec: dict) -> None:
        """The student already has this certificate: offer to open it in edit mode instead of a new record."""
        with ui.dialog() as dialog, UI.card().classes("w-full max-w-lg p-6 gap-4 bg-[var(--bg-card)] rounded-2xl border border-[var(--border-default)] shadow-2xl"):
            with ui.row().classes("items-center gap-3"):
                ui.icon("edit_document", size="lg").classes("text-amber-500")
                with ui.column().classes("gap-0"):
                    ui.label("الوثيقة صادرة مسبقاً لهذا الطالب").classes("text-base font-bold app-text-primary")
            ui.label(
                f"صدرت هذه الوثيقة بالرقم ({rec.get('certificate_number') or '-'}) بتاريخ {str(rec.get('issue_date') or '')[:10]} "
                "لنفس الجهة ونفس القالب. افتحها في وضع التعديل لإعادة إصدارها (Word أو PDF) وتحديث قيدها."
            ).classes("text-sm app-text-primary leading-relaxed")
            with ui.row().classes("w-full justify-end gap-3 mt-2"):
                UI.secondary_button("إلغاء", icon="close", on_click=dialog.close).classes("text-xs px-4 py-2")

                def _open_edit():
                    dialog.close()
                    self._enter_edit_mode(rec, self.student_full_data.get("full_name_ar", ""))
                    UI.notify("تم فتح الوثيقة في وضع التعديل. اضغط زر الإصدار مرة أخرى.", type="info")

                UI.primary_button("فتح في وضع التعديل", icon="edit", on_click=_open_edit).classes("text-xs px-4 py-2 font-bold")
        dialog.open()

    def generate_certificate(self, bypass_duplicate_check: bool = False) -> bool:
        if not self.student_full_data:
            UI.notify("الرجاء اختيار طالب أولاً", type="warning")
            return False

        tpl_name = self.template_sel.value
        if not tpl_name or "لا توجد" in tpl_name:
            UI.notify("الرجاء اختيار قالب وثيقة صالح", type="warning")
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
            "ranks": self._ranks_from_inputs(),
            "opt_summer": self.sw_summer.value,
            "summer_year": (self.inp_summer_year.value or "").strip(),
            "opt_postpone": self.sw_postpone.value,
            "postpone_years": (self.inp_postpone_years.value or "").strip(),
            "opt_second_trial": self.sw_second.value,
            "second_trial_subjects": (self.inp_second_subjects.value or "").strip(),
            "national_id": (self.student_full_data.get("national_id") if self.student_full_data else None) or (self.selected_student.get("national_id") if hasattr(self, "selected_student") and self.selected_student else None) or "",
            "reissue_cert_id": getattr(self, "reissue_cert_id", None),
        }

        # Already issued (same student, date, recipient, template)? Offer edit mode instead of a refused insert.
        if not getattr(self, "reissue_cert_id", None) and student_id:
            existing = self._find_issued_record(
                student_id,
                (self.issue_date_input.value or "").strip() if hasattr(self, "issue_date_input") else "",
                (self.to_input.value or "").strip() or "من يهمه الأمر",
                os.path.splitext(tpl_name)[0],
            )
            if existing:
                self._show_already_issued_modal(existing)
                return False

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
            # The certificate number leads the file name, so each issued certificate is easy to find.
            safe_num = re.sub(r'[\\/*?:"<>|]', "-", str(options.get("certificate_number") or "")).strip()
            name_parts = [p for p in (safe_num, safe_tpl, safe_student, safe_grouping) if p]
            out_file = os.path.join(out_dir, " - ".join(name_parts) + ".docx")
    
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
                    # Stay on the record just issued, so the Word and PDF buttons re-issue it
                    # (update) instead of trying to insert a second record.
                    if not reissue_id:
                        new_rec = self._find_issued_record(student_id, issue_dt or "", to_title, tpl_type)
                        if new_rec:
                            self._enter_edit_mode(new_rec, self.student_full_data.get("full_name_ar", ""))
            except CertificateRejected as rej:
                log.warning(f"Server refused to record the issued certificate: {rej}")
                UI.notify(
                    f"لم يتم تسجيل الوثيقة في قاعدة البيانات ({rej.status_code}):\n{rej.detail}",
                    type="warning"
                )
                # A certificate the server refused has no record and no valid number: never print it.
                try:
                    os.remove(out_file)
                except OSError:
                    pass
                self.generated_file_path = None
                return False
            except Exception as sp_err:
                log.error(f"Failed to record issued certificate into database via SP: {sp_err}")

            UI.notify(f"تم إصدار وتوليد الوثيقة بنجاح: {os.path.basename(out_file)}", type="positive")
            return True
        except PermissionError as pe:
            log.error(f"Permission denied while saving certificate file {out_file}: {pe}")
            UI.notify(
                "الملف مفتوح حالياً في برنامج Word! يرجى إغلاق ملف الوثيقة المفتوح وإعادة التوليد.\n"
                "تعذر الحفظ: ملف الوثيقة مفتوح في Microsoft Word. أغلق البرنامج وأعد المحاولة.",
                type="warning"
            )
            return False
        except Exception as err:
            err_str = str(err)
            if "Permission denied" in err_str or "[Errno 13]" in err_str or ("13" in err_str and "Permission" in err_str):
                log.error(f"Permission denied saving document: {err}")
                UI.notify(
                    "الملف مفتوح حالياً في برنامج Word! يرجى إغلاق ملف الوثيقة المفتوح وإعادة المحاولة.\n"
                    "ملف الوثيقة مفتوح في Word. أغلق البرنامج وأعد المحاولة.",
                    type="warning"
                )
            else:
                log.error(f"Error generating certificate: {err}")
                UI.notify(f"خطأ أثناء توليد الوثيقة: {err}", type="negative")
            return False
    @classmethod
    def show_in_app_print_dialog(cls, pdf_path: str | None, docx_path: str):
        """The issued document: its PDF preview beside the printer, copies and one print button."""
        rel_doc_name = os.path.basename(docx_path)

        pdf_url = ""
        if pdf_path:
            quoted_pdf = urllib.parse.quote(os.path.basename(pdf_path))
            # The query string stops the viewer showing a cached PDF of the same name.
            pdf_url = f"/certificates_files/{quoted_pdf}?v={int(os.path.getmtime(pdf_path))}"

        with ui.dialog() as print_dialog, UI.card().classes(
            "app-print-dialog w-[94vw] max-w-6xl h-[90vh] gap-4"
        ):
            with ui.row().classes("w-full items-center gap-3 no-wrap"):
                ui.icon("print", size="24px").classes("app-text-accent shrink-0")
                ui.label("معاينة الوثيقة وطباعتها").classes("app-section-title")
                ui.space()
                UI.icon_button("close", "إغلاق", on_click=print_dialog.close)

            # Preview and printer panel side by side; the panel drops under the preview on narrow windows
            with ui.row().classes("w-full flex-1 gap-4 items-stretch min-h-0"):
                with ui.column().classes("flex-1 min-w-[300px] h-full rounded-lg overflow-hidden p-0 border border-[var(--border-default)]"):
                    if pdf_url:
                        # The PDF itself is the preview: what you see is exactly what prints.
                        # A real element: ui.html sanitizes its content and strips iframes.
                        ui.element("iframe").props(f'src="{pdf_url}#view=FitH"').classes(
                            "w-full h-full min-h-[360px] border-0 bg-white"
                        )
                    else:
                        with ui.column().classes("w-full h-full justify-center items-center gap-2 app-text-muted"):
                            ui.icon("description", size="xl")
                            ui.label("لا توجد معاينة PDF؛ الوثيقة جاهزة للطباعة.").classes("text-sm")

                with ui.column().classes("w-[340px] max-w-full gap-4 justify-between"):
                    with ui.column().classes("w-full gap-4"):
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
                            "الطابعة",
                            options={p: p for p in printers},
                            value=def_p if def_p in printers else (printers[0] if printers else None)
                        ).classes("w-full app-select-wrap")

                        copies_input = UI.text_input("عدد النسخ", value="1").classes("w-full")
                        copies_input.props('type=number min=1')

                        with ui.column().classes("w-full gap-1"):
                            ui.label("الملف").classes("app-caption")
                            ui.label(rel_doc_name).classes("app-text-primary text-sm break-all").props('dir=ltr')

                    with ui.column().classes("w-full gap-2"):
                        async def do_print_now():
                            sel_printer = printer_select.value
                            if not sel_printer:
                                UI.notify("اختر الطابعة من القائمة أولاً", type="warning")
                                return
                            cps = int(copies_input.value) if copies_input.value and str(copies_input.value).isdigit() else 1
                            UI.notify(f"جارٍ إرسال الوثيقة إلى الطابعة ({sel_printer})", type="info")

                            ok = await asyncio.to_thread(print_file_to_printer, docx_path, sel_printer, cps)
                            if ok:
                                UI.notify(f"أُرسلت الوثيقة إلى الطابعة ({sel_printer})", type="positive")
                                print_dialog.close()
                            else:
                                UI.notify(f"تعذرت الطباعة على ({sel_printer}). تأكد أن الطابعة متصلة أو اختر غيرها.", type="negative")

                        UI.primary_button("طباعة الآن", icon="print", on_click=do_print_now).classes("w-full")
                        if pdf_path:
                            UI.secondary_button("عرض ملف PDF في المجلد", icon="folder_open",
                                                on_click=lambda: cls._show_in_folder(pdf_path)).classes("w-full")
                        UI.ghost_button("إغلاق", on_click=print_dialog.close).classes("w-full")

        print_dialog.open()

    @staticmethod
    def _show_in_folder(pdf_path: str):
        """Opens the certificates folder in Explorer with the PDF selected (it is saved there already)."""
        import subprocess
        try:
            subprocess.Popen(["explorer", "/select,", os.path.abspath(pdf_path)])
        except Exception as err:
            log.error(f"Error opening the certificates folder: {err}")
            UI.notify(f"تعذر فتح مجلد الوثائق: {err}", type="negative")

    def generate_and_open_word(self):
        """Generates the certificate and opens the Word document directly in Microsoft Word."""
        success = self.generate_certificate()
        if success and self.generated_file_path and os.path.exists(self.generated_file_path):
            try:
                os.startfile(self.generated_file_path)
                UI.notify("تم فتح وثيقة Word في البرنامج", type="positive")
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
                    UI.notify("تعذر تحويل الوثيقة: يتطلب برنامج Microsoft Word", type="warning")

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
                UI.notify("تم فتح الوثيقة في المستعرض", type="info")
            except Exception as err:
                log.error(f"Error opening generated doc: {err}")
                UI.notify(f"تعذر فتح الملف: {err}", type="warning")
