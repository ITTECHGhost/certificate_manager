# =============================================================================
# nicegui_screens/student_bulk_import_view.py — Two-Stage Excel Bulk Import View
# =============================================================================

import os
import json
import logging
from typing import List, Dict, Any, Optional

from nicegui import ui, app
from nicegui_ui.ui_components import UI
from nicegui_ui.ui_theme import Styles
from data.repositories import (
    StudentRepository,
    AcademicPeriodRepository,
    EnrollmentRepository,
    DepartmentRepository,
    StudySystemRepository,
    CourseRepository,
    GovernorateRepository,
    CountryRepository,
    RoleRepository,
    PersonnelRepository,
    OfflineModeError,
)
from services.excel_import_service import (
    generate_students_template,
    parse_students_file,
    generate_grades_matrix_template,
    parse_grades_file,
)
from utils.file_delivery import deliver_file
from nicegui_ui.upload_utils import read_upload
from sync_engine import sqlite_read_one, sqlite_read_all, is_online

def safe_cast(val: Any, target_type: type = int, default_val: Any = 0) -> Any:
    """Safely cast a value to target_type with default_val fallback on None or cast failure."""
    if val is None:
        return default_val
    try:
        return target_type(val)
    except (ValueError, TypeError):
        return default_val

log = logging.getLogger(__name__)


class StudentBulkImportView:
    """
    Dedicated Two-Stage Excel Bulk Ingestion View for Students and Grades:
    1. Department & Stage setup (entered once, auto-locked if user is department-restricted).
    2. Upload students demographic info via Excel (with downloadable template).
    3. Upload course grades matrix via Excel (with downloadable dynamic template pre-populated with students & courses).
    4. Verification, review, and batch database commitment.
    """

    def __init__(self, container, on_back_callback=None, on_success_callback=None):
        self.container = container
        self.on_back_callback = on_back_callback
        self.on_success_callback = on_success_callback

        # Repositories
        self.student_repo = StudentRepository()
        self.period_repo = AcademicPeriodRepository()
        self.enroll_repo = EnrollmentRepository()
        self.dept_repo = DepartmentRepository()
        self.sys_repo = StudySystemRepository()
        self.course_repo = CourseRepository()
        self.gov_repo = GovernorateRepository()
        self.country_repo = CountryRepository()
        self.role_repo = RoleRepository()
        self.personnel_repo = PersonnelRepository()

        # State Variables
        self.selected_dept_id: Optional[int] = None
        self.selected_stage: int = 1
        self.selected_system_id: Optional[int] = None

        # Dynamic Default Academic Year (e.g. 2024-2025 or 2023-2024)
        from datetime import datetime
        now = datetime.now()
        curr_yr = now.year
        if now.month >= 8:
            self.academic_year: str = f"{curr_yr}-{curr_yr+1}"
        else:
            self.academic_year: str = f"{curr_yr-1}-{curr_yr}"

        self.semester_num: int = 1
        self.is_dept_locked: bool = False
        self.lock_reason: str = ""

        # Catalogs
        self.departments: List[Dict[str, Any]] = []
        self.study_systems: List[Dict[str, Any]] = []
        self.courses_for_stage: List[Dict[str, Any]] = []
        self.gov_map: Dict[str, int] = {}
        self.country_map: Dict[str, int] = {}

        # Parsed Data
        self.parsed_students: List[Dict[str, Any]] = []
        self.parsed_grades: List[Dict[str, Any]] = []
        self.merged_records: List[Dict[str, Any]] = []

        # UI Element References
        self.dept_select = None
        self.system_select = None
        self.year_input = None
        self.dl_grades_btn = None
        self.courses_container = None
        self.students_table_container = None
        self.grades_table_container = None
        self.summary_container = None

    def render(self):
        """Construct the entire Two-Stage Bulk Import View layout."""
        self.container.clear()
        self._load_reference_data()
        self._detect_user_department_scope()

        with self.container:
            with UI.card().classes("w-full flex-1 gap-6 p-6"):

                # Header Row: Title & Return Button
                with ui.row().classes("w-full items-center justify-between gap-4 pb-4 border-b border-[var(--border-default)]"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("group_add", size="md").classes("app-text-accent")
                        with ui.column().classes("gap-0.5"):
                            ui.label("إضافة مجموعة طلاب ودرجاتهم (استيراد Excel) — Bulk Import Students & Grades").classes(
                                "text-xl font-bold app-text-primary"
                            )
                            ui.label(
                                "الخطوة 1: تحديد القسم والنظام الدراسي ◀ الخطوة 2: رفع بيانات الطلاب ◀ الخطوة 3: رفع درجات المواد ◀ الخطوة 4: الحفظ"
                            ).classes("text-xs app-text-muted")

                    UI.secondary_button(
                        "← العودة لقائمة الطلاب / Back to Students",
                        on_click=self._handle_back
                    ).classes("text-xs px-4 py-2 font-bold shadow-sm")

                # =============================================================
                # Zone 1: Department & Academic Context (Entered Once)
                # =============================================================
                with UI.card().classes("w-full p-5 gap-4 bg-[var(--surface-ground)] rounded-2xl border border-[var(--border-default)]"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.row().classes("items-center gap-2"):
                            ui.badge("1", color="primary").classes("text-sm font-bold px-2.5 py-1 rounded-full")
                            ui.label("تحديد بيانات القسم والنظام الدراسي / Academic Context Setup").classes(
                                "text-base font-bold app-text-primary"
                            )
                        if self.is_dept_locked:
                            with ui.row().classes("items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 text-amber-500 text-xs font-bold border border-amber-500/30"):
                                ui.icon("lock", size="xs")
                                ui.label(f"مقيد بصلاحيات حسابك: {self.lock_reason}")

                    # Selection Inputs Row (Department, Study System, Academic Year in one row)
                    with ui.row().classes("w-full gap-4 items-center flex-wrap"):
                        # Department
                        dept_opts = {d["id"]: f"{d.get('name_ar')} ({d.get('name_en', '')})" for d in self.departments}
                        self.dept_select = ui.select(
                            options=dept_opts,
                            value=self.selected_dept_id,
                            label="القسم العلمي / Department *",
                            on_change=self._on_dept_changed
                        ).props("outlined dense options-dense").classes("flex-1 min-w-[260px]")
                        if self.is_dept_locked:
                            self.dept_select.disable()

                        # Study System with clear Annual / Semester & Morning / Evening labels
                        sys_opts = {}
                        for s in self.study_systems:
                            s_name = s.get("name_ar") or ""
                            day_type = (s.get("study_day_type") or "Morning").capitalize()
                            day_ar = "صباحي" if day_type == "Morning" else "مسائي"
                            sys_type_name = "سنوي / مقررات" if ("سنوي" in s_name or "مقررات" in s_name) else "فصلي"
                            sys_opts[s["id"]] = f"نظام {sys_type_name} ({day_ar}) — {s_name}"

                        self.system_select = ui.select(
                            options=sys_opts,
                            value=self.selected_system_id,
                            label="النظام الدراسي / Study System *",
                            on_change=self._on_system_changed
                        ).props("outlined dense options-dense").classes("flex-1 min-w-[260px]")

                        # Academic Year
                        self.year_input = UI.text_input(
                            label="العام الدراسي / Academic Year *",
                            value=self.academic_year,
                            on_change=self._on_year_changed
                        ).classes("w-52").props("dense outlined")

                    # Live Courses Chip Preview Container
                    self.courses_container = ui.column().classes("w-full gap-2 mt-2")
                    self._refresh_courses_display()

                # =============================================================
                # Zone 2: Students Information (File 1)
                # =============================================================
                with UI.card().classes("w-full p-5 gap-4 bg-[var(--surface-ground)] rounded-2xl border border-[var(--border-default)]"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.row().classes("items-center gap-2"):
                            ui.badge("2", color="secondary").classes("text-sm font-bold px-2.5 py-1 rounded-full")
                            ui.label("بيانات الطلاب الديموغرافية (الملف الأول) / Students Demographics (File 1)").classes(
                                "text-base font-bold app-text-primary"
                            )
                        with ui.row().classes("items-center gap-2"):
                            UI.primary_button(
                                "تحميل نموذج بيانات الطلاب (Excel)",
                                icon="download",
                                on_click=self._download_students_template
                            ).classes("text-xs px-3.5 py-1.5 font-bold shadow-sm")

                    ui.label(
                        "قم بتحميل النموذج أعلاه وتعبئة بيانات الطلاب (الاسم، الرقم الوطني، الجنس، تاريخ الميلاد، إلخ) ثم ارفع الملف هنا:"
                    ).classes("text-xs app-text-muted")

                    # File Upload Widget
                    with ui.row().classes("w-full items-center gap-4 p-4 rounded-xl border border-dashed border-[var(--border-default)] bg-[var(--surface-card)]"):
                        ui.upload(
                            label="اسحب أو اختر ملف بيانات الطلاب (.xlsx)",
                            auto_upload=True,
                            max_files=1,
                            on_upload=self._on_students_file_uploaded
                        ).props('accept=".xlsx" flat bordered').classes("w-full max-w-md")

                        with ui.column().classes("gap-1 flex-1 text-xs text-[var(--text-secondary)] leading-relaxed"):
                            ui.label("• يدعم الملف الأرقام العربية والإنكليزية وتنسيقات التواريخ المختلفة.")
                            ui.label("• يتم التحقق تلقائياً من تكرار الأرقام الوطنية وسلامة الأسماء.")

                    # Parsed Students Table Preview Container
                    self.students_table_container = ui.column().classes("w-full gap-2")
                    self._render_students_table()

                # =============================================================
                # Zone 3: Courses & Grades Matrix (File 2)
                # =============================================================
                with UI.card().classes("w-full p-5 gap-4 bg-[var(--surface-ground)] rounded-2xl border border-[var(--border-default)]"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.row().classes("items-center gap-2"):
                            ui.badge("3", color="accent").classes("text-sm font-bold px-2.5 py-1 rounded-full")
                            ui.label("درجات ومواد الطلاب (الملف الثاني) / Courses & Grades Matrix (File 2)").classes(
                                "text-base font-bold app-text-primary"
                            )
                        with ui.row().classes("items-center gap-2"):
                            self.dl_grades_btn = UI.primary_button(
                                "تحميل كشف درجات المواد (Excel)",
                                icon="download",
                                on_click=self._download_grades_template
                            ).classes("text-xs px-3.5 py-1.5 font-bold shadow-sm")
                            if not self.parsed_students:
                                self.dl_grades_btn.disable()

                    ui.label(
                        "يحتوي كشف الدرجات تلقائياً على أسماء الطلاب المرفوعين من الخطوة 2 مع أعمدة لكافة مواد القسم والمواد المشتركة للمرحلة المحددة:"
                    ).classes("text-xs app-text-muted")

                    # File Upload Widget
                    with ui.row().classes("w-full items-center gap-4 p-4 rounded-xl border border-dashed border-[var(--border-default)] bg-[var(--surface-card)]"):
                        ui.upload(
                            label="اسحب أو اختر ملف كشف الدرجات المكتمل (.xlsx)",
                            auto_upload=True,
                            max_files=1,
                            on_upload=self._on_grades_file_uploaded
                        ).props('accept=".xlsx" flat bordered').classes("w-full max-w-md")

                        with ui.column().classes("gap-1 flex-1 text-xs text-[var(--text-secondary)] leading-relaxed"):
                            ui.label("• يتم احتساب معدل الطالب الموزون تلقائياً بناءً على عدد وحدات كل مادة.")
                            ui.label("• يتم تعيين الدور (الأول/الثاني) وحالة النتيجة (ناجح/إكمال/راسب) لكل طالب.")

                    # Combined Grades Preview Table Container
                    self.grades_table_container = ui.column().classes("w-full gap-2")
                    self._render_grades_table()

                # =============================================================
                # Zone 4: Verification Summary & Commitment Action
                # =============================================================
                self.summary_container = ui.column().classes("w-full gap-4 mt-2")
                self._render_summary_zone()

    # -------------------------------------------------------------------------
    # Helper: Reference Data & User Department Scope
    # -------------------------------------------------------------------------

    def _load_reference_data(self):
        """Fetch departments, study systems, governorates, and countries."""
        try:
            self.departments = self.dept_repo.get_all() or []
            if self.departments and not self.selected_dept_id:
                self.selected_dept_id = self.departments[0]["id"]
        except Exception as e:
            log.warning(f"Failed to fetch departments: {e}")

        try:
            self.study_systems = self.sys_repo.get_active() or self.sys_repo.get_all() or []
            if self.study_systems and not self.selected_system_id:
                self.selected_system_id = self.study_systems[0]["id"]
        except Exception as e:
            log.warning(f"Failed to fetch study systems: {e}")

        try:
            govs = self.gov_repo.get_all() or []
            self.gov_map = {str(g.get("name_ar", "")).strip(): g["id"] for g in govs}
            self.gov_map["بغداد"] = 2  # standard default
        except Exception:
            pass

        try:
            countries = self.country_repo.get_all() or []
            self.country_map = {str(c.get("name_ar", "")).strip(): c["id"] for c in countries}
            self.country_map["عراقي"] = 274
            self.country_map["العراق"] = 274
        except Exception:
            pass

        self._resolve_courses()

    def _detect_user_department_scope(self):
        """Check if logged-in user is restricted to a specific department."""
        try:
            # Department scope cached at login (no network call here)
            from nicegui_ui.state import app_session
            allowed_ids = app_session.get_access().get("dept_scope")

            if allowed_ids:
                # Filter self.departments so user only sees departments they have access to
                self.departments = [d for d in self.departments if d["id"] in allowed_ids]
                first_dept_id = allowed_ids[0]
                self.selected_dept_id = first_dept_id
                if len(allowed_ids) == 1:
                    self.is_dept_locked = True
                dept_name = next((d.get("name_ar") for d in self.departments if d["id"] == first_dept_id), str(first_dept_id))
                self.lock_reason = f"قسم {dept_name}"
                self._resolve_courses()
        except Exception as e:
            log.debug(f"Department scope detection notice: {e}")

    def _resolve_courses(self):
        """
        Fetch courses belonging to selected department,
        PLUS shared courses (college & university requirements).
        """
        if not self.selected_dept_id:
            self.courses_for_stage = []
            return

        try:
            dept_courses = self.course_repo.get_by_department(self.selected_dept_id) or []

            # Fetch all courses to identify shared courses across departments
            all_courses = self.course_repo.get_all() or []
            seen_ids = {c["id"] for c in dept_courses}
            dept_course_names = {str(c.get("name_en") or c.get("name_ar") or "").strip().lower() for c in dept_courses}

            shared_courses = []
            for c in all_courses:
                if c["id"] in seen_ids:
                    continue

                c_dept = c.get("department_id")
                c_name = str(c.get("name_en") or c.get("name_ar") or "").strip().lower()

                if c_dept is None or c_dept == 0:
                    c_copy = dict(c)
                    c_copy["is_shared"] = True
                    shared_courses.append(c_copy)
                    seen_ids.add(c["id"])
                elif c_name in dept_course_names:
                    c_copy = dict(c)
                    c_copy["is_shared"] = True
                    if not any(sc.get("name_ar") == c.get("name_ar") for sc in dept_courses):
                        shared_courses.append(c_copy)
                        seen_ids.add(c["id"])

            for c in dept_courses:
                c["is_shared"] = False

            all_resolved = dept_courses + shared_courses
            all_resolved.sort(key=lambda x: (int(x.get("stage_number") or 1), x.get("id") or 0))
            self.courses_for_stage = all_resolved
        except Exception as err:
            log.error(f"Error resolving courses: {err}")
            self.courses_for_stage = []

    # -------------------------------------------------------------------------
    # Change Handlers
    # -------------------------------------------------------------------------

    def _on_dept_changed(self, e):
        if e and hasattr(e, "value") and e.value:
            self.selected_dept_id = int(e.value)
            self._resolve_courses()
            self._refresh_courses_display()

    def _on_system_changed(self, e):
        if e and hasattr(e, "value") and e.value:
            self.selected_system_id = int(e.value)

    def _on_year_changed(self, e):
        val = e.value if hasattr(e, "value") else str(e or "")
        self.academic_year = str(val).strip()

    def _refresh_courses_display(self):
        """Update live course chips preview."""
        if not self.courses_container:
            return
        self.courses_container.clear()
        with self.courses_container:
            dept_name = next((d.get("name_ar") for d in self.departments if d["id"] == self.selected_dept_id), "القسم")
            dept_courses = [c for c in self.courses_for_stage if not c.get("is_shared")]
            shared_courses = [c for c in self.courses_for_stage if c.get("is_shared")]

            with ui.row().classes("w-full items-center justify-between text-xs"):
                ui.label(
                    f"📚 المواد المشمولة في كشف درجات قسم {dept_name} ({len(self.courses_for_stage)} مادة):"
                ).classes("font-bold app-text-primary")
                with ui.row().classes("items-center gap-3"):
                    ui.label(f"• تخصصية: {len(dept_courses)}").classes("text-blue-500 font-semibold")
                    ui.label(f"• مشتركة ومتطلبات كلية: {len(shared_courses)}").classes("text-teal-500 font-semibold")

            with ui.row().classes("w-full flex-wrap gap-2 pt-1"):
                if not self.courses_for_stage:
                    ui.label("⚠️ لا توجد مواد مسجلة لهذا القسم حالياً.").classes("text-xs text-amber-500 italic")
                for c in self.courses_for_stage:
                    is_sh = c.get("is_shared", False)
                    c_stg = int(c.get("stage_number") or 1)
                    bg_color = "bg-teal-500/10 text-teal-400 border border-teal-500/30" if is_sh else "bg-blue-500/10 text-blue-400 border border-blue-500/30"
                    tag_text = "مشترك" if is_sh else "تخصصي"
                    with ui.row().classes(f"items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs {bg_color}"):
                        ui.icon("layers" if is_sh else "menu_book", size="xs")
                        ui.label(f"{c.get('name_ar')} (م{c_stg} | {c.get('credit_hours', 3)} و)").classes("font-medium")
                        ui.badge(tag_text, color="transparent").classes("text-[10px] p-0 font-mono opacity-80")

    # -------------------------------------------------------------------------
    # Zone 2: Students File Upload & Table
    # -------------------------------------------------------------------------

    def _download_students_template(self):
        """Generate and deliver Students Roster Excel template directly to Downloads and Excel."""
        try:
            file_bytes = generate_students_template()
            deliver_file(
                content=file_bytes,
                filename="نموذج_بيانات_الطلاب.xlsx",
                title="تم تجهيز وحفظ نموذج بيانات الطلاب (Excel) بنجاح",
                auto_open=False,
                show_modal=True
            )
        except Exception as exc:
            log.error(f"Error generating students template: {exc}")
            ui.notify(f"خطأ في توليد النموذج: {exc}", type="negative")

    async def _on_students_file_uploaded(self, event):
        """Handle uploaded Students Roster Excel."""
        try:
            _name, content = await read_upload(event)
            students, errors = parse_students_file(content)
            if errors:
                for err in errors[:3]:
                    ui.notify(err, type="warning")
            if not students:
                ui.notify("لم يتم العثور على بيانات طلاب صالحة في الملف المرفوع.", type="negative")
                return

            self.parsed_students = students
            ui.notify(f"تم قراءة وتدقيق بيانات {len(students)} طالب بنجاح!", type="positive")
            self._render_students_table()
            self._sync_merged_records()
            self._render_summary_zone()
        except Exception as exc:
            log.error(f"Error reading students file: {exc}")
            ui.notify(f"فشل قراءة ملف الطلاب: {exc}", type="negative")

    def _render_students_table(self):
        """Render staging table for parsed students."""
        if self.dl_grades_btn:
            if self.parsed_students:
                self.dl_grades_btn.enable()
            else:
                self.dl_grades_btn.disable()

        if not self.students_table_container:
            return
        self.students_table_container.clear()
        if not self.parsed_students:
            return

        with self.students_table_container:
            with ui.row().classes("w-full items-center justify-between mt-3 px-2"):
                ui.label(f"قائمة الطلاب المرفوعين ({len(self.parsed_students)} طالب):").classes("text-sm font-bold text-emerald-500")
                UI.secondary_button("مسح القائمة / Clear", on_click=self._clear_students).classes("text-xs px-2.5 py-1")

            cols = [
                {"name": "index", "label": "#", "field": "index", "align": "center", "classes": "w-12"},
                {"name": "full_name_ar", "label": "اسم الطالب (رباعي)", "field": "full_name_ar", "align": "right", "sortable": True},
                {"name": "national_id", "label": "الرقم الوطني / الهوية", "field": "national_id", "align": "center"},
                {"name": "gender_label", "label": "الجنس", "field": "gender_label", "align": "center"},
                {"name": "date_of_birth", "label": "تاريخ الميلاد", "field": "date_of_birth", "align": "center"},
                {"name": "birthplace", "label": "المحافظة", "field": "birthplace", "align": "center"},
                {"name": "admission_year", "label": "سنة القبول", "field": "admission_year", "align": "center"},
                {"name": "study_type_ar", "label": "نوع الدراسة", "field": "study_type_ar", "align": "center"},
                {"name": "actions", "label": "حذف", "field": "actions", "align": "center", "classes": "w-16"},
            ]

            rows_data = []
            for idx, st in enumerate(self.parsed_students, start=1):
                item = dict(st)
                item["index"] = idx
                rows_data.append(item)

            table = ui.table(columns=cols, rows=rows_data, row_key="national_id").classes(Styles.TABLE_CLASSES).props("dense flat bordered")

            table.add_slot("body-cell-actions", """
                <q-td :props="props">
                    <q-btn flat dense round size="sm" color="negative" icon="delete" @click="$parent.$emit('remove_student', props.row)" />
                </q-td>
            """)

            def on_remove(e):
                row_data = getattr(e, "args", {}) or {}
                nid = row_data.get("national_id")
                self.parsed_students = [s for s in self.parsed_students if s.get("national_id") != nid]
                self._render_students_table()
                self._sync_merged_records()
                self._render_summary_zone()

            table.on("remove_student", on_remove)

    def _clear_students(self):
        self.parsed_students = []
        self._render_students_table()
        self._sync_merged_records()
        self._render_summary_zone()

    # -------------------------------------------------------------------------
    # Zone 3: Grades Matrix File Upload & Table
    # -------------------------------------------------------------------------

    def _download_grades_template(self):
        """Generate and deliver dynamic Grades Matrix Excel template directly to Downloads and Excel."""
        if not self.parsed_students:
            ui.notify("يرجى رفع ملف بيانات الطلاب (الملف الأول) أولاً قبل تحميل كشف الدرجات.", type="warning")
            return

        if not self.courses_for_stage:
            ui.notify("يرجى تحديد قسم يحتوي على مواد دراسية أولاً.", type="warning")
            return

        try:
            dept_name = next((d.get("name_ar") for d in self.departments if d["id"] == self.selected_dept_id), "")
            file_bytes = generate_grades_matrix_template(
                students=self.parsed_students,
                courses=self.courses_for_stage,
                dept_name=dept_name,
                stage_num=None,
                academic_year=self.academic_year
            )
            clean_dept = (dept_name or "").replace(" ", "_")
            filename = f"كشف_درجات_قسم_{clean_dept}.xlsx"
            deliver_file(
                content=file_bytes,
                filename=filename,
                title=f"تم تجهيز وحفظ كشف درجات المواد ({dept_name}) بنجاح",
                auto_open=False,
                show_modal=True
            )
        except Exception as exc:
            log.error(f"Error generating grades template: {exc}")
            ui.notify(f"خطأ في توليد كشف الدرجات: {exc}", type="negative")

    async def _on_grades_file_uploaded(self, event):
        """Handle uploaded Grades Matrix Excel."""
        if not self.parsed_students:
            ui.notify("يرجى رفع ملف بيانات الطلاب أولاً (الخطوة 2) قبل رفع ملف الدرجات.", type="warning")
            return

        if not self.courses_for_stage:
            ui.notify("يرجى تحديد قسم ومرحلة دراسية أولاً.", type="warning")
            return

        try:
            _name, content = await read_upload(event)
            grades, errors = parse_grades_file(content, self.courses_for_stage)
            if errors:
                for err in errors[:3]:
                    ui.notify(err, type="warning")
            if not grades:
                ui.notify("لم يتم العثور على درجات صالحة في الملف المرفوع.", type="negative")
                return

            self.parsed_grades = grades
            ui.notify(f"تم قراءة درجات {len(grades)} طالب بنجاح!", type="positive")
            self._sync_merged_records()
            self._render_grades_table()
            self._render_summary_zone()
        except Exception as exc:
            log.error(f"Error reading grades file: {exc}")
            ui.notify(f"فشل قراءة كشف الدرجات: {exc}", type="negative")

    def _sync_merged_records(self):
        """Correlate students from Step 2 with grades from Step 3."""
        grades_by_nid = {
            str(g.get("national_id")).strip(): g
            for g in self.parsed_grades
            if g.get("national_id") and not str(g.get("national_id")).startswith("GEN_")
        }
        grades_by_name = {
            " ".join(str(g.get("student_name", "")).split()): g
            for g in self.parsed_grades
            if g.get("student_name")
        }

        self.merged_records = []
        for idx, st in enumerate(self.parsed_students, start=1):
            nid = str(st.get("national_id", "")).strip()
            name = str(st.get("full_name_ar", "")).strip()
            name_norm = " ".join(name.split())

            grade_info = (
                (grades_by_nid.get(nid) if (nid and not nid.startswith("GEN_")) else None)
                or grades_by_name.get(name_norm)
                or {}
            )
            scores = grade_info.get("scores", [])
            avg = grade_info.get("average", 0.0)
            res_st = grade_info.get("result_status", "PASSED")
            p_round = grade_info.get("passed_round", 1)

            self.merged_records.append({
                "index": idx,
                "student_info": st,
                "national_id": nid,
                "full_name_ar": name,
                "full_name_en": st.get("full_name_en", ""),
                "scores": scores,
                "scores_count": len(scores),
                "total_required_courses": len(self.courses_for_stage),
                "average": avg,
                "result_status": res_st,
                "passed_round": p_round,
                "has_grades": len(scores) > 0,
            })

    def _render_grades_table(self):
        """Render staging table for parsed grades."""
        if not self.grades_table_container:
            return
        self.grades_table_container.clear()
        if not self.parsed_grades:
            return

        with self.grades_table_container:
            with ui.row().classes("w-full items-center justify-between mt-3 px-2"):
                ui.label(f"معاينة كشف الدرجات والنتائج المحسوبة ({len(self.parsed_grades)} طالب):").classes("text-sm font-bold text-blue-500")
                UI.secondary_button("مسح الدرجات / Clear", on_click=self._clear_grades).classes("text-xs px-2.5 py-1")

            cols = [
                {"name": "index", "label": "#", "field": "index", "align": "center", "classes": "w-12"},
                {"name": "full_name_ar", "label": "اسم الطالب", "field": "full_name_ar", "align": "right", "sortable": True},
                {"name": "national_id", "label": "الرقم الوطني", "field": "national_id", "align": "center"},
                {"name": "scores_count_display", "label": "المواد المرصودة", "field": "scores_count_display", "align": "center"},
                {"name": "average", "label": "المعدل المحسوب", "field": "average", "align": "center", "sortable": True},
                {"name": "passed_round_display", "label": "الدور", "field": "passed_round_display", "align": "center"},
                {"name": "result_status_display", "label": "النتيجة", "field": "result_status_display", "align": "center"},
                {"name": "actions", "label": "تفاصيل المواد", "field": "actions", "align": "center"},
            ]

            rows_data = []
            for rec in self.merged_records:
                r_item = dict(rec)
                r_item["scores_count_display"] = f"{rec['scores_count']} من {rec['total_required_courses']} مادة"
                r_item["passed_round_display"] = "الدور الثاني" if rec["passed_round"] == 2 else ("الدور الثالث" if rec["passed_round"] == 3 else "الدور الأول")
                st_map = {
                    "PASSED": "ناجح",
                    "FAILED_REPEAT": "راسب (إعادة)",
                    "CARRIED_OVER": "إكمال / عبور",
                    "DEFERRED": "تأجيل",
                }
                r_item["result_status_display"] = st_map.get(rec["result_status"], "ناجح")
                rows_data.append(r_item)

            table = ui.table(columns=cols, rows=rows_data, row_key="national_id").classes(Styles.TABLE_CLASSES).props("dense flat bordered")

            table.add_slot("body-cell-average", """
                <q-td :props="props">
                    <span class="font-bold text-sm" :class="props.row.average >= 50 ? 'text-emerald-500' : 'text-rose-500'">
                        {{ props.row.average.toFixed(3) }}
                    </span>
                </q-td>
            """)

            table.add_slot("body-cell-actions", """
                <q-td :props="props">
                    <q-btn dense size="sm" color="primary" flat icon="list_alt" label="عرض المواد" @click="$parent.$emit('show_scores_dialog', props.row)" />
                </q-td>
            """)

            def on_show_dialog(e):
                row_data = getattr(e, "args", {}) or {}
                self._show_student_scores_dialog(row_data)

            table.on("show_scores_dialog", on_show_dialog)

    def _clear_grades(self):
        self.parsed_grades = []
        self._sync_merged_records()
        self._render_grades_table()
        self._render_summary_zone()

    def _show_student_scores_dialog(self, row_data: Dict[str, Any]):
        """Open modal dialog showing detailed subject breakdown for a student."""
        name = row_data.get("full_name_ar", "")
        scores = row_data.get("scores", [])

        with ui.dialog() as dlg, UI.card().classes("p-6 gap-4 w-[520px] max-w-full bg-[var(--surface-card)] rounded-2xl border border-[var(--border-default)] shadow-2xl"):
            with ui.row().classes("w-full items-center justify-between pb-2 border-b border-[var(--border-default)]"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("school", size="sm").classes("app-text-accent")
                    ui.label(f"درجات المواد — {name}").classes("text-base font-bold app-text-primary")
                ui.button(icon="close", on_click=dlg.close).props("flat dense round")

            if not scores:
                ui.label("لا توجد درجات مرصودة لهذا الطالب في الملف.").classes("text-sm text-amber-500")
            else:
                with ui.column().classes("w-full gap-2 max-h-96 overflow-y-auto"):
                    for sc in scores:
                        score_val = sc.get("score", 0.0)
                        is_pass = score_val >= 50.0
                        with ui.row().classes("w-full items-center justify-between p-2.5 rounded-xl border border-[var(--border-default)] bg-[var(--surface-ground)]"):
                            with ui.column().classes("gap-0.5"):
                                ui.label(sc.get("course_name_ar") or sc.get("course_name_en")).classes("text-sm font-semibold app-text-primary")
                                ui.label(f"الوحدات: {sc.get('credit_hours', 3)}").classes("text-xs app-text-muted")

                            with ui.row().classes("items-center gap-3"):
                                ui.label(f"{score_val:.1f}").classes(f"font-bold text-base {'text-emerald-500' if is_pass else 'text-rose-500'}")
                                ui.badge("ناجح" if is_pass else "راسب", color="positive" if is_pass else "negative").classes("text-xs font-bold")

            with ui.row().classes("w-full justify-between items-center pt-3 border-t border-[var(--border-default)]"):
                ui.label(f"المعدل النهائي: {row_data.get('average', 0.0):.3f}").classes("font-bold text-sm app-text-accent")
                UI.secondary_button("إغلاق / Close", on_click=dlg.close).classes("text-xs px-4 py-1.5")

        dlg.open()

    # -------------------------------------------------------------------------
    # Zone 4: Verification Summary & Commitment
    # -------------------------------------------------------------------------

    def _render_summary_zone(self):
        """Render final summary stats and commitment button."""
        if not self.summary_container:
            return
        self.summary_container.clear()

        st_count = len(self.parsed_students)
        gr_count = len(self.parsed_grades)
        has_data = st_count > 0

        with self.summary_container:
            with UI.card().classes("w-full p-6 gap-5 bg-gradient-to-r from-slate-900 to-slate-800 rounded-2xl border border-slate-700 shadow-xl text-white"):
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.row().classes("items-center gap-3"):
                        ui.icon("verified", size="md").classes("text-emerald-400")
                        with ui.column().classes("gap-0.5"):
                            ui.label("ملخص الاستيراد والتأكيد النهائي / Ingestion Summary & Confirmation").classes("text-lg font-bold")
                            dept_name = next((d.get("name_ar") for d in self.departments if d["id"] == self.selected_dept_id), "القسم")
                            ui.label(f"القسم: {dept_name} | السنة: {self.academic_year}").classes("text-xs text-slate-300")

                with ui.row().classes("w-full gap-4 items-center"):
                    with ui.column().classes("p-3 rounded-xl bg-slate-800/80 border border-slate-700 flex-1 items-center"):
                        ui.label(str(st_count)).classes("text-2xl font-bold text-emerald-400")
                        ui.label("إجمالي الطلاب المرفوعين").classes("text-xs text-slate-300")

                    with ui.column().classes("p-3 rounded-xl bg-slate-800/80 border border-slate-700 flex-1 items-center"):
                        ui.label(str(len(self.courses_for_stage))).classes("text-2xl font-bold text-blue-400")
                        ui.label("المواد المشمولة في الكشف").classes("text-xs text-slate-300")

                    with ui.column().classes("p-3 rounded-xl bg-slate-800/80 border border-slate-700 flex-1 items-center"):
                        total_scores = sum(len(g.get("scores", [])) for g in self.parsed_grades)
                        ui.label(str(total_scores)).classes("text-2xl font-bold text-amber-400")
                        ui.label("إجمالي الدرجات المرصودة").classes("text-xs text-slate-300")

                with ui.row().classes("w-full justify-end items-center gap-4 pt-2"):
                    UI.secondary_button("إلغاء ومسح الكل / Reset All", on_click=self._reset_all).classes("text-xs px-4 py-2 text-slate-300")

                    commit_btn = UI.success_button(
                        f"💾 تأكيد واستيراد {st_count} طالب وحفظ درجاتهم في قاعدة البيانات",
                        icon="cloud_upload",
                        on_click=self._execute_batch_import
                    ).classes("text-sm px-6 py-3 font-bold shadow-lg")
                    if not has_data:
                        commit_btn.disable()

    def _reset_all(self):
        self.parsed_students = []
        self.parsed_grades = []
        self.merged_records = []
        self._render_students_table()
        self._render_grades_table()
        self._render_summary_zone()
        ui.notify("تم مسح البيانات بنجاح.", type="info")

    # -------------------------------------------------------------------------
    # Batch Execution & Existence Resolution
    # -------------------------------------------------------------------------

    def _find_existing_student(self, national_id: Optional[str], full_name_ar: str, dept_id: int) -> Optional[int]:
        """
        Check if student already exists in the database by national_id or (full_name_ar + department_id).
        Checks SQLite replicas (synced + offline) and online API.
        """
        clean_nat = str(national_id).strip() if national_id else ""
        clean_name = str(full_name_ar).strip() if full_name_ar else ""

        # 1. Check by national_id in SQLite
        if clean_nat:
            r = sqlite_read_one("SELECT id FROM students WHERE TRIM(national_id) = ?", (clean_nat,))
            if r and r.get("id"):
                return int(r["id"])
            r_loc = sqlite_read_one("SELECT id FROM local_students WHERE TRIM(national_id) = ?", (clean_nat,))
            if r_loc and r_loc.get("id"):
                return int(r_loc["id"])

        # 2. Check by full_name_ar in same department in SQLite
        if clean_name and dept_id:
            r = sqlite_read_one(
                "SELECT id FROM students WHERE TRIM(full_name_ar) = ? AND department_id = ?",
                (clean_name, dept_id)
            )
            if r and r.get("id"):
                return int(r["id"])
            r_loc = sqlite_read_one(
                "SELECT id FROM local_students WHERE TRIM(full_name_ar) = ? AND department_id = ?",
                (clean_name, dept_id)
            )
            if r_loc and r_loc.get("id"):
                return int(r_loc["id"])

        # 3. Check online API if online
        if is_online() and clean_name and dept_id:
            try:
                candidates = self.student_repo.get_all_paginated(limit=10, name_query=clean_name, dept_id=dept_id) or []
                for c in candidates:
                    c_name = str(c.get("full_name_ar") or "").strip()
                    c_dept = safe_cast(c.get("department_id"), int, 0)
                    c_nat = str(c.get("national_id") or "").strip()
                    if clean_nat and c_nat == clean_nat:
                        return int(c["id"])
                    if c_name == clean_name and (c_dept == dept_id or c_dept == 0):
                        return int(c["id"])
            except Exception as e:
                log.debug(f"Online candidate search notice: {e}")

        return None

    def _execute_batch_import(self):
        """Perform atomic insertion/updating of students, academic periods, and enrollments."""
        if not self.parsed_students:
            ui.notify("لا توجد بيانات طلاب للاستيراد.", type="warning")
            return

        with ui.dialog() as progress_dlg, UI.card().classes("p-6 gap-4 w-96 bg-[var(--surface-card)] text-[var(--text-primary)] rounded-2xl border border-[var(--border-default)] shadow-2xl"):
            ui.label("جاري استيراد مجموعة الطلاب...").classes("text-base font-bold text-emerald-500")
            status_lbl = ui.label("بدء المعالجة...").classes("text-xs text-[var(--text-secondary)]")
            progress_bar = ui.linear_progress(value=0.0).props("instant-feedback stripe rounded").classes("w-full")

        progress_dlg.open()

        created_students = 0
        updated_students = 0
        created_periods = 0
        reused_periods = 0
        created_enrollments = 0
        updated_enrollments = 0
        total_students = len(self.parsed_students)

        try:
            if is_online():
                status_lbl.text = "جاري إرسال حزمة البيانات المجمعة إلى الخادم..."
                progress_bar.value = 0.5
                payload_students = []
                for rec in self.merged_records:
                    st = rec["student_info"]
                    bp_name = st.get("birthplace", "بغداد")
                    bp_id = self.gov_map.get(bp_name, 2)
                    nat_id = self.country_map.get(st.get("nationality", "عراقي"), 274)

                    scores_list = []
                    for sc in rec.get("scores", []):
                        try:
                            scores_list.append({
                                "course_id": int(sc["course_id"]),
                                "score": float(sc["score"]),
                                "passed_round": int(sc.get("passed_round", 1)),
                                "stage_number": safe_cast(sc.get("stage_number"), int, 1)
                            })
                        except (ValueError, TypeError):
                            pass

                    payload_students.append({
                        "full_name_ar": st.get("full_name_ar"),
                        "full_name_en": st.get("full_name_en") or "",
                        "gender": int(st.get("gender") or 1),
                        "date_of_birth": st.get("date_of_birth") or None,
                        "birthplace_id": bp_id,
                        "nationality_id": nat_id,
                        "national_id": st.get("national_id") or None,
                        "department_id": self.selected_dept_id,
                        "study_system_id": self.selected_system_id or 1,
                        "degree_level": 1,
                        "admission_year": st.get("admission_year") or self.academic_year,
                        "average": rec.get("average") if rec.get("has_grades") else None,
                        "academic_year": str(self.academic_year).strip(),
                        "stage_number": 1,
                        "semester_num": 1,
                        "result_status": rec.get("result_status", "PASSED"),
                        "scores": scores_list
                    })

                res = self.student_repo.bulk_import(payload_students)
                created_students = res.get("created_students", 0)
                updated_students = res.get("updated_students", 0)
                created_periods = res.get("created_periods", 0)
                reused_periods = res.get("reused_periods", 0)
                created_enrollments = res.get("saved_enrollments", 0)
                progress_bar.value = 1.0
            else:
                for idx, rec in enumerate(self.merged_records, start=1):
                    st = rec["student_info"]
                    name_ar = st.get("full_name_ar")
                    status_lbl.text = f"معالجة الطالب ({idx}/{total_students}): {name_ar}"
                    progress_bar.value = float(idx) / float(total_students)

                    # Resolve birthplace
                    bp_name = st.get("birthplace", "بغداد")
                    bp_id = self.gov_map.get(bp_name, 2)

                    # Resolve nationality
                    nat_id = self.country_map.get(st.get("nationality", "عراقي"), 274)

                    # Student Payload
                    st_payload = {
                        "full_name_ar": name_ar,
                        "full_name_en": st.get("full_name_en") or "",
                        "gender": int(st.get("gender") or 1),
                        "date_of_birth": st.get("date_of_birth") or None,
                        "birthplace_id": bp_id,
                        "nationality_id": nat_id,
                        "national_id": st.get("national_id") or None,
                        "department_id": self.selected_dept_id,
                        "study_system_id": self.selected_system_id or 1,
                        "degree_level": 1,
                        "admission_year": st.get("admission_year") or self.academic_year,
                        "average": rec.get("average") if rec.get("has_grades") else None,
                    }

                    # 1. Check if student already exists -> update vs insert
                    existing_st_id = self._find_existing_student(
                        national_id=st_payload.get("national_id"),
                        full_name_ar=name_ar,
                        dept_id=self.selected_dept_id
                    )

                    if existing_st_id is not None:
                        target_student_id = existing_st_id
                        try:
                            self.student_repo.update(target_student_id, st_payload)
                            updated_students += 1
                        except Exception as st_up_err:
                            log.warning(f"Standard update failed, attempting direct SQLite update: {st_up_err}")
                            try:
                                from sync_engine import _get_local_conn
                                conn_loc = _get_local_conn()
                                tbl = "local_students" if target_student_id < 0 else "students"
                                conn_loc.execute(f"""
                                    UPDATE {tbl} SET
                                        full_name_en = CASE WHEN ? != '' THEN ? ELSE full_name_en END,
                                        gender = COALESCE(?, gender),
                                        date_of_birth = COALESCE(?, date_of_birth),
                                        birthplace_id = COALESCE(?, birthplace_id),
                                        nationality_id = COALESCE(?, nationality_id),
                                        study_system_id = COALESCE(?, study_system_id),
                                        average = CASE WHEN ? IS NOT NULL THEN ? ELSE average END
                                    WHERE id = ?
                                """, (
                                    st_payload.get("full_name_en") or "", st_payload.get("full_name_en") or "",
                                    st_payload.get("gender"),
                                    st_payload.get("date_of_birth"),
                                    st_payload.get("birthplace_id"),
                                    st_payload.get("nationality_id"),
                                    st_payload.get("study_system_id"),
                                    st_payload.get("average"), st_payload.get("average"),
                                    target_student_id
                                ))
                                conn_loc.commit()
                                conn_loc.close()
                                updated_students += 1
                            except Exception as direct_err:
                                log.error(f"Failed direct offline update for student {target_student_id}: {direct_err}")
                    else:
                        try:
                            target_student_id = self.student_repo.insert(st_payload)
                            created_students += 1
                        except Exception as st_err:
                            log.error(f"Failed to insert student {name_ar}: {st_err}")
                            continue

                    # 2. Check or create academic periods & enrollments offline
                    res_status = rec.get("result_status", "PASSED")
                    scores = rec.get("scores", [])

                    if scores:
                        scores_by_stage = {}
                        for sc in scores:
                            stg = safe_cast(sc.get("stage_number"), int, 1)
                            scores_by_stage.setdefault(stg, []).append(sc)

                        for stg, sc_list in scores_by_stage.items():
                            target_period_id = None
                            try:
                                existing_periods = self.period_repo.get_by_student(target_student_id) or []
                                for p in existing_periods:
                                    p_yr = str(p.get("academic_year") or "").strip()
                                    p_stg = safe_cast(p.get("stage_number"), int, 0)
                                    if p_yr == str(self.academic_year).strip() and p_stg == stg:
                                        target_period_id = p.get("id")
                                        break

                                if target_period_id is not None:
                                    self.period_repo.update_status(target_period_id, res_status)
                                    reused_periods += 1
                                else:
                                    target_period_id = self.period_repo.insert(
                                        student_id=target_student_id,
                                        year=self.academic_year,
                                        sys_id=self.selected_system_id or 1,
                                        stage=stg,
                                        semester_num=1,
                                        result_status=res_status
                                    )
                                    created_periods += 1
                            except Exception as p_err:
                                log.error(f"Failed to process academic period for student {target_student_id}: {p_err}")
                                continue

                            # 3. Check existing enrollments for period -> update vs insert
                            existing_enroll_map = {}
                            try:
                                existing_enrolls = self.enroll_repo.get_by_period(target_period_id) or []
                                for e in existing_enrolls:
                                    cid = safe_cast(e.get("course_id"), int, 0)
                                    if cid and e.get("id"):
                                        existing_enroll_map[cid] = e["id"]
                            except Exception as e_chk_err:
                                log.warning(f"Failed to check existing enrollments: {e_chk_err}")

                            for sc in sc_list:
                                try:
                                    cid = int(sc["course_id"])
                                    score_val = float(sc["score"])
                                    p_round = int(sc.get("passed_round", 1))

                                    if cid in existing_enroll_map:
                                        enroll_id = existing_enroll_map[cid]
                                        try:
                                            self.enroll_repo.update(enroll_id, score=score_val, is_second=p_round)
                                            updated_enrollments += 1
                                        except Exception as e_up_err:
                                            log.warning(f"Standard enroll update failed, trying direct SQLite update: {e_up_err}")
                                            try:
                                                from sync_engine import _get_local_conn
                                                conn_loc = _get_local_conn()
                                                tbl = "local_enrollments" if enroll_id < 0 else "enrollments"
                                                conn_loc.execute(
                                                    f"UPDATE {tbl} SET score = ?, passed_round = ? WHERE id = ?",
                                                    (score_val, str(p_round), enroll_id)
                                                )
                                                conn_loc.commit()
                                                conn_loc.close()
                                                updated_enrollments += 1
                                            except Exception as d_e_err:
                                                log.error(f"Direct offline enrollment update failed: {d_e_err}")
                                    else:
                                        self.enroll_repo.insert(
                                            period_id=target_period_id,
                                            course_id=cid,
                                            score=score_val,
                                            is_second=p_round
                                        )
                                        created_enrollments += 1
                                except Exception as e_err:
                                    log.error(f"Failed to save enrollment {sc}: {e_err}")
                    else:
                        # Default period when no scores are provided
                        try:
                            existing_periods = self.period_repo.get_by_student(target_student_id) or []
                            found_p = any(str(p.get("academic_year") or "").strip() == str(self.academic_year).strip() for p in existing_periods)
                            if not found_p:
                                self.period_repo.insert(
                                    student_id=target_student_id,
                                    year=self.academic_year,
                                    sys_id=self.selected_system_id or 1,
                                    stage=1,
                                    semester_num=1,
                                    result_status=res_status
                                )
                                created_periods += 1
                            else:
                                reused_periods += 1
                        except Exception as p_err:
                            log.error(f"Failed to process default academic period: {p_err}")

            progress_dlg.close()

            # Success Celebration Dialog
            with ui.dialog() as success_dlg, UI.card().classes("p-6 gap-4 w-[460px] bg-[var(--surface-card)] text-[var(--text-primary)] rounded-2xl border border-emerald-500/40 shadow-2xl"):
                with ui.row().classes("items-center gap-3"):
                    ui.icon("check_circle", size="lg").classes("text-emerald-500")
                    with ui.column().classes("gap-0.5"):
                        ui.label("اكتمل الاستيراد بنجاح! / Import Successful").classes("text-lg font-bold text-emerald-500")
                        ui.label("تمت معالجة كافة السجلات وتحديث قاعدة البيانات بنجاح").classes("text-xs text-[var(--text-secondary)]")

                with ui.column().classes("w-full p-3.5 rounded-xl bg-[var(--surface-ground)] border border-[var(--border-default)] gap-2 text-xs"):
                    if created_students > 0 or updated_students > 0:
                        parts = []
                        if created_students:
                            parts.append(f"إضافة {created_students} طالب جديد")
                        if updated_students:
                            parts.append(f"تحديث بيانات {updated_students} طالب سابق")
                        ui.label(f"• تم {' و'.join(parts)} بنجاح.")

                    if created_periods > 0 or reused_periods > 0:
                        p_parts = []
                        if created_periods:
                            p_parts.append(f"إنشاء {created_periods} مرحلة دراسية جديدة")
                        if reused_periods:
                            p_parts.append(f"تحديث {reused_periods} مرحلة دراسية سابقة")
                        ui.label(f"• تم {' و'.join(p_parts)} للعام {self.academic_year}.")

                    if created_enrollments > 0 or updated_enrollments > 0:
                        e_parts = []
                        if created_enrollments:
                            e_parts.append(f"حفظ {created_enrollments} درجة دراسية جديدة")
                        if updated_enrollments:
                            e_parts.append(f"تحديث {updated_enrollments} درجة مادة معتمدة")
                        ui.label(f"• تم {' و'.join(e_parts)} بنجاح.")

                with ui.row().classes("w-full justify-end gap-3 mt-2"):
                    def on_finish():
                        success_dlg.close()
                        if callable(self.on_success_callback):
                            self.on_success_callback()
                        else:
                            self._handle_back()

                    UI.success_button("الانتقال إلى قائمة الطلاب / View Students", icon="people", on_click=on_finish).classes("text-xs px-4 py-2 font-bold")

            success_dlg.open()

        except Exception as batch_err:
            progress_dlg.close()
            log.error(f"Fatal error during bulk import: {batch_err}")
            ui.notify(f"خطأ غير متوقع أثناء الاستيراد: {batch_err}", type="negative")

    def _handle_back(self):
        """Navigate back to standard students screen."""
        if callable(self.on_back_callback):
            self.on_back_callback()
