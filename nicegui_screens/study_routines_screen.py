import logging
from nicegui import ui
from data.repositories import (
    StudyRoutineRepository,
    DepartmentRepository,
    StudySystemRepository,
    CourseRepository,
)

log = logging.getLogger(__name__)


class StudyRoutinesController:
    """
    Hierarchical Study Routines Controller with Tabbed UI & Master-Detail Split View:
    - Tab 1: Predefined Study Routines (Unified Header + 1/3 Master List & 2/3 Detail Workspace).
    - Tab 2: Course Catalog (Placeholder / Embeddable).
    """

    def __init__(self, container: ui.column | None = None, standalone: bool = True) -> None:
        self.repo = StudyRoutineRepository()
        self.dept_repo = DepartmentRepository()
        self.system_repo = StudySystemRepository()
        self.course_repo = CourseRepository()

        # Active routine state for the master-detail split view
        self.active_routine_id: int | None = None

        self.container = container or ui.column().classes("w-full p-0 gap-0")
        if standalone:
            self.build_ui()

    # =========================================================================
    # 1. Main View Setup (build_ui)
    # =========================================================================

    def build_ui(self) -> None:
        """Renders the master-detail routines workspace directly without redundant top tab headers."""
        with self.container:
            self.render_master_detail_view()

    def render_master_detail_view(self) -> None:
        """Renders the unified header card and Master-Detail split-view row."""
        with ui.card().classes("w-full shadow-sm rounded-2xl p-0 bg-[var(--bg-card)] border border-[var(--border-default)] flex-col flex-nowrap overflow-hidden"):
            # Header Row
            with ui.row().classes("w-full justify-between items-center p-5 border-b border-[var(--border-default)] flex-wrap gap-4 shrink-0"):
                # Right Side: Title & Subtitle
                with ui.row().classes("items-center gap-3"):
                    ui.icon("playlist_add_check", size="md").classes("text-teal-600 dark:text-teal-400 shrink-0")
                    with ui.column().classes("gap-0.5"):
                        ui.label("الروتينات والخطط الدراسية — Predefined Study Routines").classes(
                            "text-xl font-bold text-[var(--text-primary)]"
                        )
                        ui.label(
                            "إنشاء وتجهيز حزم المواد لكل قسم ومرحلة وفصل دراسي لربطها للطلاب تلقائياً"
                        ).classes("text-xs text-[var(--text-muted)]")

                # Left Side: Green Add Routine Button
                ui.button(
                    "+ إضافة روتين جديد / Add Routine",
                    icon="add",
                    on_click=self.open_routine_dialog
                ).classes("bg-teal-600 hover:bg-teal-700 text-white font-bold rounded-xl px-5 py-2.5 text-sm shadow-sm")

            # Master-Detail Split View (Below Header Row)
            with ui.row().classes("w-full no-wrap items-stretch p-5 gap-5 bg-[var(--bg-main)]"):
                self._render_left_column()
                self._render_right_column()

    # =========================================================================
    # 2. Left Column (Master Navigation - 30% Width)
    # =========================================================================

    @ui.refreshable_method
    def _render_left_column(self) -> None:
        """Renders the master routine list cards (30% locked width)."""
        with ui.column().style("width: 30%; flex: 0 0 30%;").classes("gap-4 h-full"):
            try:
                routines = self.repo.get_all() or []
            except Exception as exc:
                log.warning(f"Error fetching study routines: {exc}")
                routines = []

            if not routines:
                with ui.card().classes("w-full p-6 text-center rounded-xl border border-dashed border-[var(--border-default)] bg-[var(--bg-card)]"):
                    ui.icon("playlist_add_check", size="md").classes("text-[var(--text-muted)] mx-auto mb-1")
                    ui.label("لا توجد روتينات دراسية").classes("text-sm font-bold text-[var(--text-primary)]")
                    ui.label("اضغط زر الإضافة في الأعلى لإنشاء روتين جديد.").classes("text-xs text-[var(--text-muted)] mt-0.5")
                return

            # Auto-select first routine if none selected
            if self.active_routine_id is None and routines:
                self.active_routine_id = routines[0].get("id")

            # Clickable Routine Cards List
            with ui.column().classes("w-full gap-2.5 pr-1"):
                for routine in routines:
                    r_id = routine.get("id")
                    name_ar = routine.get("name_ar") or "روتين بدون اسم"
                    name_en = routine.get("name_en") or ""
                    dept_name = routine.get("dept_name_ar") or routine.get("department_name_ar") or "قسم غير محدد"
                    is_active = (self.active_routine_id == r_id)

                    card_classes = (
                        "w-full p-4 rounded-xl cursor-pointer transition-all shadow-sm "
                        + ("border-2 border-teal-600 bg-teal-500/10 ring-2 ring-teal-600/20 "
                           if is_active else
                           "border border-[var(--border-default)] bg-[var(--bg-card)] hover:border-slate-400 dark:hover:border-slate-600")
                    )

                    def make_click_handler(selected_id=r_id):
                        def on_click():
                            self.active_routine_id = selected_id
                            self._render_left_column.refresh()
                            self._render_right_column.refresh()
                        return on_click

                    with ui.card().classes(card_classes).on("click", make_click_handler()):
                        with ui.row().classes("w-full justify-between items-start gap-2"):
                            with ui.column().classes("gap-0.5 flex-1 min-w-0"):
                                ui.label(name_ar).classes(
                                    f"font-bold text-sm truncate w-full "
                                    f"{'text-teal-600 dark:text-teal-400' if is_active else 'text-[var(--text-primary)]'}"
                                )
                                if name_en:
                                    ui.label(name_en).classes("text-xs text-[var(--text-muted)] font-mono truncate w-full")

                            ui.icon(
                                "check_circle" if is_active else "chevron_left",
                                size="xs"
                            ).classes("text-teal-600" if is_active else "text-[var(--text-muted)]")

                        with ui.row().classes("w-full items-center justify-between pt-2 mt-1 border-t border-[var(--border-default)]"):
                            ui.label(dept_name).classes("text-[11px] font-semibold text-[var(--text-muted)] truncate")
                            courses_count = len(routine.get("courses") or routine.get("course_ids") or [])
                            if courses_count:
                                ui.label(f"{courses_count} مواد").classes(
                                    "text-[10px] font-bold px-1.5 py-0.5 rounded bg-[var(--bg-main)] text-[var(--text-primary)] border border-[var(--border-default)]"
                                )

    # =========================================================================
    # 3. Right Column (Detail Workspace - 70% Width)
    # =========================================================================

    @ui.refreshable_method
    def _render_right_column(self) -> None:
        """Renders the detail workspace containing the active routine, its open period cards, and assigned course chips (70% width)."""
        with ui.column().classes("flex-1 min-w-0 gap-4 bg-[var(--bg-main)] p-4 rounded-xl border border-[var(--border-default)] h-full"):
            # Empty State
            if self.active_routine_id is None:
                with ui.column().classes("w-full h-full min-h-[400px] items-center justify-center text-center gap-3 py-16"):
                    ui.icon("touch_app", size="xl").classes("text-[var(--text-muted)] mb-1")
                    ui.label("الرجاء تحديد روتين من القائمة").classes("text-base font-bold text-[var(--text-primary)]")
                    ui.label("انقر على أي روتين من القائمة لعرض وتعديل مراحله ومواده الدراسية.").classes("text-xs text-[var(--text-muted)] max-w-sm")
                return

            # Active State: Fetch routine details
            routine = None
            if hasattr(self.repo, "get_by_id"):
                routine = self.repo.get_by_id(self.active_routine_id)
            if not routine:
                all_r = self.repo.get_all() or []
                for r in all_r:
                    if r.get("id") == self.active_routine_id:
                        routine = r
                        break

            if not routine:
                self.active_routine_id = None
                with ui.column().classes("w-full py-12 items-center text-center"):
                    ui.label("لم يتم العثور على بيانات الروتين المحدد").classes("text-sm text-rose-500 font-bold")
                return

            routine_id = int(routine.get("id") or 0)
            name_ar = routine.get("name_ar") or "روتين دراسي"
            name_en = routine.get("name_en") or ""
            dept_name = routine.get("dept_name_ar") or routine.get("department_name_ar") or "قسم غير محدد"
            dept_id = routine.get("department_id")

            # Routine Info Card
            with ui.card().classes("w-full justify-between items-center p-4 rounded-xl bg-[var(--bg-card)] shadow-sm border border-[var(--border-default)] shrink-0"):
                with ui.row().classes("w-full justify-between items-center"):
                    with ui.row().classes("items-center gap-3 flex-1 min-w-0"):
                        ui.icon("school", size="md").classes("text-teal-600 shrink-0")
                        with ui.column().classes("gap-0 min-w-0"):
                            ui.label(name_ar).classes("text-lg font-bold text-[var(--text-primary)] truncate w-full")
                            with ui.row().classes("items-center gap-2"):
                                ui.label(f"القسم: {dept_name}").classes("text-xs font-semibold text-[var(--text-muted)]")
                                if name_en:
                                    ui.label(f"• {name_en}").classes("text-xs text-[var(--text-muted)] font-mono")

                    with ui.row().classes("items-center gap-1"):
                        ui.button(
                            icon="edit",
                            on_click=lambda _, r=routine: self.open_routine_dialog(r)
                        ).props("flat round dense color=primary").tooltip("تعديل الروتين / Edit Routine")

                        ui.button(
                            icon="delete",
                            on_click=lambda _, r_id=routine_id: self._delete_routine(r_id)
                        ).props("flat round dense color=negative").tooltip("حذف الروتين / Delete Routine")

            # Fetch periods for the routine
            periods = []
            if hasattr(self.repo, "get_periods"):
                try:
                    periods = self.repo.get_periods(routine_id) or []
                except Exception:
                    periods = []

            # If no discrete periods in DB yet, auto-create standard 4 stages x 2 semesters in DB
            if not periods:
                try:
                    for s_num in range(1, 5):
                        for sem_n in (1, 2):
                            self.repo.insert_period({"routine_id": routine_id, "stage_number": s_num, "semester_num": sem_n})
                    periods = self.repo.get_periods(routine_id) or []
                except Exception as p_err:
                    log.warning(f"Error auto-creating periods for routine {routine_id}: {p_err}")
                    periods = []

            # Periods Workspace (Open Period Cards Grid/Column - No Inner Scrollbar!)
            with ui.column().classes("w-full gap-4 flex-1 pr-1"):
                if not periods:
                    with ui.column().classes("w-full p-8 text-center rounded-xl bg-[var(--bg-card)] border border-dashed border-[var(--border-default)]"):
                        ui.icon("event_busy", size="md").classes("text-[var(--text-muted)] mx-auto mb-1")
                        ui.label("لا توجد مراحل أو فصول مضافة لهذا الروتين بعد.").classes("text-sm font-semibold text-[var(--text-primary)]")
                        ui.label("اضغط على زر (+ إضافة مرحلة/فصل جديد) بالأسفل للبدء.").classes("text-xs text-[var(--text-muted)] mt-0.5")
                else:
                    for period in periods:
                        p_raw_id = period.get("id") or period.get("period_id") or 0
                        period_id = int(str(p_raw_id)) if not isinstance(p_raw_id, (list, tuple, dict)) else 0
                        stg_num = int(str(period.get("stage_number") or 1))
                        sem_num = int(str(period.get("semester_num") or 1))
                        period_title = f"المرحلة {stg_num} - الفصل {sem_num}"

                        # Fetch courses for this period
                        courses = []
                        if hasattr(self.repo, "get_period_courses") and period_id:
                            try:
                                courses = self.repo.get_period_courses(period_id) or []
                            except Exception:
                                courses = []

                        if not courses:
                            courses = period.get("courses") or []

                        if not isinstance(courses, list):
                            courses = []

                        # Render Period Container (Fully Visible, Theme-Aware & Stacked)
                        with ui.column().classes("w-full shadow-sm rounded-xl border border-[var(--border-default)] bg-[var(--bg-card)] p-4 gap-3"):
                            # Header Row with Title and Delete Period Button
                            with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)] flex-wrap gap-2"):
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon("calendar_month", size="xs").classes("text-teal-600 dark:text-teal-400 shrink-0")
                                    ui.label(period_title).classes("font-bold text-sm text-[var(--text-primary)]")
                                    ui.label(f"({len(courses)} مواد)").classes("text-xs text-[var(--text-muted)] font-semibold")

                                ui.button(
                                    icon="delete",
                                    on_click=lambda _, p_id=period_id: self._delete_period(p_id)
                                ).props("flat round dense size=sm color=negative").tooltip("حذف الفترة")

                            # Courses Listing Row with single Add button
                            with ui.row().classes("w-full gap-2 flex-wrap items-center pt-1 min-h-[36px]"):
                                if not courses:
                                    with ui.row().classes("w-full p-3 rounded-lg border border-dashed border-[var(--border-default)] bg-[var(--bg-main)] items-center justify-between"):
                                        ui.label("لا توجد مواد دراسية مسندة لهذه الفترة بعد.").classes("text-xs italic text-[var(--text-muted)]")
                                        ui.button(
                                            "+ إضافة مادة الآن / Add Course",
                                            icon="add_circle",
                                            on_click=lambda _, p_id=period_id, d_id=dept_id, s_num=stg_num, sem_n=sem_num: self.open_course_assignment_dialog(p_id, d_id, s_num, sem_n)
                                        ).props("flat dense size=xs").classes("text-teal-600 font-bold")
                                else:
                                    for course in courses:
                                        c_raw_id = course.get("course_id") or course.get("id") or course.get("mapping_id")
                                        course_id = int(c_raw_id or 0)
                                        course_name = course.get("course_name_ar") or course.get("name_ar") or course.get("course_name_en") or course.get("name_en") or "مادة"
                                        credit_hrs = course.get("credit_hours") or course.get("credits")

                                        with ui.row().classes("items-center gap-2 px-3 py-1.5 rounded-xl bg-[var(--bg-main)] border border-[var(--border-default)] text-[var(--text-primary)] text-xs shadow-xs hover:border-teal-500/50 transition-all"):
                                            ui.icon("menu_book", size="xs").classes("text-teal-600 dark:text-teal-400 shrink-0")
                                            ui.label(course_name).classes("font-bold text-xs text-[var(--text-primary)]")
                                            if credit_hrs:
                                                ui.label(f"({credit_hrs} وحدات)").classes("text-[10px] font-bold px-1.5 py-0.5 rounded bg-teal-500/10 text-teal-600 dark:text-teal-400 border border-teal-500/20")
                                            ui.button(
                                                icon="close",
                                                on_click=lambda _, p_id=period_id, c_id=course_id: self._remove_course(p_id, c_id)
                                            ).props("flat round dense size=xs color=negative").tooltip("إلغاء تعيين المادة")

                                    # Add button inline with course chips
                                    ui.button(
                                        "+ إضافة مادة / Add Course",
                                        icon="add_circle",
                                        on_click=lambda _, p_id=period_id, d_id=dept_id, s_num=stg_num, sem_n=sem_num: self.open_course_assignment_dialog(p_id, d_id, s_num, sem_n)
                                    ).classes("bg-teal-600/10 hover:bg-teal-600/20 text-teal-600 dark:text-teal-400 font-bold rounded-xl px-3 py-1.5 text-xs border border-teal-600/30 shadow-none")

            # Footer: Add New Period Button
            ui.button(
                "+ إضافة مرحلة/فصل جديد / Add New Period",
                icon="add_circle",
                on_click=lambda: self.open_period_dialog(self.active_routine_id)
            ).classes("w-full py-3 bg-teal-600 hover:bg-teal-700 text-white font-bold rounded-xl shadow-md text-sm mt-auto")

    # =========================================================================
    # 4. Dialogs (Modals)
    # =========================================================================

    def open_routine_dialog(self, routine: dict | None = None) -> None:
        """Modal for creating or editing a Study Routine."""
        is_edit = routine is not None
        routine_id = routine.get("id") if is_edit else None

        try:
            depts = self.dept_repo.get_all() or []
        except Exception:
            depts = []
        dept_options = {d["id"]: f"{d.get('name_ar', '')} / {d.get('name_en', '')}" for d in depts}
        
        target_dept = routine.get("department_id") if is_edit else None
        if target_dept and target_dept in dept_options:
            init_dept = target_dept
        else:
            init_dept = list(dept_options.keys())[0] if dept_options else 1

        try:
            systems = self.system_repo.get_all() or []
        except Exception:
            systems = []

        sys_options = {}
        for s in systems:
            sys_id = s.get("id")
            if not sys_id:
                continue
            name_ar = s.get("name_ar") or "نظام دراسي"
            name_en = s.get("name_en") or ""
            day_raw = str(s.get("study_day_type") or s.get("study_type") or "").strip().lower()
            if day_raw in ["morning", "day", "صباحي", "الصباحية"]:
                type_label = "الدراسة الصباحية / Morning"
            elif day_raw in ["evening", "night", "مسائي", "المسائية"]:
                type_label = "الدراسة المسائية / Evening"
            else:
                type_label = s.get("study_day_type") or s.get("study_type") or ""

            type_suffix = f" [{type_label}]" if type_label else ""
            label = f"{name_ar}{type_suffix} — {name_en}" if name_en else f"{name_ar}{type_suffix}"
            sys_options[sys_id] = label

        if not sys_options:
            sys_options = {
                1: "نظام فصلي [الدراسة الصباحية / Morning] — Semester System",
                2: "نظام فصلي [الدراسة المسائية / Evening] — Semester System",
                3: "نظام سنوي [الدراسة الصباحية / Morning] — Annual System",
                4: "نظام سنوي [الدراسة المسائية / Evening] — Annual System",
            }
        
        target_sys = routine.get("study_system_id") if is_edit else None
        if target_sys and target_sys in sys_options:
            init_sys = target_sys
        else:
            init_sys = list(sys_options.keys())[0]

        dialog = ui.dialog()
        with dialog, ui.card().classes("w-full max-w-lg p-6 shadow-xl rounded-2xl gap-4 bg-[var(--bg-card)] border border-[var(--border-default)]"):
            with ui.row().classes("w-full items-center gap-2 pb-2 border-b border-[var(--border-default)]"):
                ui.icon("edit_note" if is_edit else "post_add", size="sm").classes("text-teal-600 dark:text-teal-400")
                ui.label("تعديل الروتين الدراسي / Edit Routine" if is_edit else "إضافة روتين دراسي جديد / Add Routine").classes("text-lg font-bold text-[var(--text-primary)]")

            name_ar_val = routine.get("name_ar", "") if is_edit else ""
            name_en_val = routine.get("name_en", "") if is_edit else ""

            name_ar_input = ui.input("اسم الروتين بالعربية / Routine Name (AR)", value=name_ar_val).classes("w-full text-sm").props("outlined dense")
            name_en_input = ui.input("اسم الروتين بالإنجليزية / Routine Name (EN)", value=name_en_val).classes("w-full text-sm").props("outlined dense")
            dept_select = ui.select(options=dept_options, value=init_dept, label="القسم التابع له / Department").classes("w-full text-sm").props("outlined dense")
            sys_select = ui.select(options=sys_options, value=init_sys, label="النظام الدراسي / Study System").classes("w-full text-sm").props("outlined dense")

            with ui.row().classes("w-full justify-end gap-2 pt-3 border-t border-slate-200 dark:border-slate-700"):
                ui.button("إلغاء / Cancel", on_click=dialog.close).props("flat").classes("text-slate-500 text-sm")

                def save_routine():
                    name_ar = (name_ar_input.value or "").strip()
                    name_en = (name_en_input.value or "").strip()
                    dept_id = dept_select.value
                    sys_id = sys_select.value

                    if not name_ar:
                        ui.notify("يرجى إدخال اسم الروتين بالعربية", type="warning")
                        return

                    payload = {
                        "name_ar": name_ar,
                        "name_en": name_en,
                        "department_id": dept_id,
                        "study_system_id": sys_id,
                    }

                    try:
                        if is_edit and routine_id:
                            self.repo.update(routine_id, payload)
                            ui.notify("تم تعديل الروتين الدراسي بنجاح!", type="positive")
                        else:
                            new_id = self.repo.insert(payload)
                            if new_id:
                                self.active_routine_id = new_id
                            ui.notify("تمت إضافة الروتين الدراسي بنجاح!", type="positive")

                        dialog.close()
                        self._render_left_column.refresh()
                        self._render_right_column.refresh()
                    except Exception as err:
                        log.error(f"Failed to save routine: {err}")
                        ui.notify(f"خطأ أثناء الحفظ: {err}", type="negative")

                ui.button("حفظ الروتين / Save", icon="save", on_click=save_routine).classes("bg-teal-600 hover:bg-teal-700 text-white text-sm px-4 py-2 rounded-lg")

        dialog.open()

    def open_period_dialog(self, routine_id: int | None) -> None:
        """Modal for adding an academic Period to a Study Routine."""
        if not routine_id:
            ui.notify("الرجاء اختيار روتين دراسي أولاً", type="warning")
            return

        dialog = ui.dialog()
        with dialog, ui.card().classes("w-full max-w-sm p-6 shadow-xl rounded-2xl gap-4 bg-[var(--bg-card)] border border-[var(--border-default)]"):
            with ui.row().classes("w-full items-center gap-2 pb-2 border-b border-[var(--border-default)]"):
                ui.icon("event", size="sm").classes("text-teal-600 dark:text-teal-400")
                ui.label("إضافة فترة دراسية / Add Period").classes("text-lg font-bold text-[var(--text-primary)]")

            stage_input = ui.number(label="رقم المرحلة / Stage Number", value=1, min=1, max=6, step=1).classes("w-full text-sm").props("outlined dense")
            sem_input = ui.number(label="رقم الفصل / Semester Number", value=1, min=1, max=3, step=1).classes("w-full text-sm").props("outlined dense")

            with ui.row().classes("w-full justify-end gap-2 pt-3 border-t border-slate-200 dark:border-slate-700"):
                ui.button("إلغاء / Cancel", on_click=dialog.close).props("flat").classes("text-slate-500 text-sm")

                def save_period():
                    stg = int(stage_input.value or 1)
                    sem = int(sem_input.value or 1)

                    payload = {
                        "routine_id": routine_id,
                        "stage_number": stg,
                        "semester_num": sem,
                    }

                    try:
                        if hasattr(self.repo, "insert_period"):
                            self.repo.insert_period(payload)
                        else:
                            self.repo.insert(payload)

                        ui.notify("تمت إضافة الفترة الدراسية بنجاح!", type="positive")
                        dialog.close()
                        self._render_right_column.refresh()
                    except Exception as err:
                        log.error(f"Failed to insert period: {err}")
                        ui.notify(f"خطأ أثناء إضافة الفترة: {err}", type="negative")

                ui.button("إضافة / Add", icon="add", on_click=save_period).classes("bg-teal-600 hover:bg-teal-700 text-white text-sm px-4 py-2 rounded-lg")

        dialog.open()

    def open_course_assignment_dialog(self, period_id: int, department_id: int | None = None, stage_number: int = 1, semester_num: int = 1) -> None:
        """Modal with autocomplete select to assign any Course from the Catalog to a Routine Period."""
        try:
            depts = self.dept_repo.get_all() or []
            dept_map = {d["id"]: (d.get("name_ar") or d.get("name_en") or "") for d in depts if d.get("id")}
        except Exception:
            dept_map = {}

        try:
            all_courses = self.course_repo.get_all() or []
            dept_courses = []
            if department_id and hasattr(self.course_repo, "get_by_department"):
                dept_courses = self.course_repo.get_by_department(department_id) or []
        except Exception as exc:
            log.warning(f"Error fetching course options for routine assignment: {exc}")
            all_courses = []
            dept_courses = []

        seen_ids = set()
        ordered_courses = []
        for c in dept_courses:
            cid = c.get("id")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                ordered_courses.append(c)

        for c in all_courses:
            cid = c.get("id")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                ordered_courses.append(c)

        course_options = {}
        for c in ordered_courses:
            cid = c.get("id")
            name_ar = c.get("name_ar") or ""
            name_en = c.get("name_en") or ""
            stage = c.get("stage_number") or 1

            # Resolve actual Department Name
            d_id = c.get("department_id")
            d_name = c.get("dept_name_ar") or c.get("department_name_ar") or (dept_map.get(d_id) if d_id else "")
            
            if d_name:
                d_str = d_name if d_name.startswith("قسم") else f"قسم {d_name}"
                badge = f" [{d_str}]"
            else:
                badge = " [مادة عامة / General]"

            label = f"{name_ar} / {name_en} (المرحلة {stage}){badge}" if name_en else f"{name_ar} (المرحلة {stage}){badge}"
            course_options[cid] = label

        init_course = list(course_options.keys())[0] if course_options else None

        dialog = ui.dialog()
        with dialog, ui.card().classes("w-full max-w-md p-6 shadow-xl rounded-2xl gap-4 bg-[var(--bg-card)] border border-[var(--border-default)]"):
            with ui.row().classes("w-full items-center gap-2 pb-2 border-b border-[var(--border-default)]"):
                ui.icon("library_add", size="sm").classes("text-teal-600 dark:text-teal-400")
                ui.label("إسناد مادة دراسية / Assign Course").classes("text-lg font-bold text-[var(--text-primary)]")

            if not course_options:
                ui.label("لا توجد مواد متاحة للقسم المحدد.").classes("text-xs text-amber-500 italic py-2")
            else:
                course_select = ui.select(
                    options=course_options,
                    value=init_course,
                    label="اختر المادة الدراسية / Select Course",
                    with_input=True
                ).classes("w-full text-sm").props("outlined dense use-input fill-input")

            with ui.row().classes("w-full justify-end gap-2 pt-3 border-t border-slate-200 dark:border-slate-700"):
                ui.button("إلغاء / Cancel", on_click=dialog.close).props("flat").classes("text-slate-500 text-sm")

                def save_course_assignment():
                    if not course_options or not course_select.value:
                        ui.notify("يرجى تحديد مادة دراسية أولاً", type="warning")
                        return

                    cid = int(course_select.value)
                    try:
                        if hasattr(self.repo, "insert_period_course"):
                            self.repo.insert_period_course(period_id, cid)
                        elif self.active_routine_id:
                            # Add to routine courses
                            cur_r = self.repo.get_by_id(self.active_routine_id) or {}
                            c_ids = set(cur_r.get("course_ids") or [])
                            c_ids.add(cid)
                            cur_r["course_ids"] = list(c_ids)
                            self.repo.update(self.active_routine_id, cur_r)

                        ui.notify("تم تعيين المادة للفترة الدراسية بنجاح!", type="positive")
                        dialog.close()
                        self._render_right_column.refresh()
                    except Exception as err:
                        log.error(f"Failed to assign course to period: {err}")
                        ui.notify(f"خطأ أثناء ربط المادة: {err}", type="negative")

                ui.button("إسناد المادة / Assign", icon="check", on_click=save_course_assignment).classes("bg-teal-600 hover:bg-teal-700 text-white text-sm px-4 py-2 rounded-lg")

        dialog.open()

    # =========================================================================
    # 5. Delete Action Handlers
    # =========================================================================

    def _delete_routine(self, routine_id: int) -> None:
        """Deletes a study routine and resets active selection if needed."""
        try:
            self.repo.delete(routine_id)
            if self.active_routine_id == routine_id:
                self.active_routine_id = None
            ui.notify("تم حذف الروتين الدراسي بنجاح", type="positive")
            self._render_left_column.refresh()
            self._render_right_column.refresh()
        except Exception as err:
            log.error(f"Error deleting routine {routine_id}: {err}")
            ui.notify(f"خطأ أثناء حذف الروتين: {err}", type="negative")

    def _delete_period(self, period_id: int) -> None:
        """Deletes an academic period and refreshes the detail workspace."""
        try:
            if hasattr(self.repo, "delete_period"):
                self.repo.delete_period(period_id)
            ui.notify("تم حذف الفترة الدراسية بنجاح", type="positive")
            self._render_right_column.refresh()
        except Exception as err:
            log.error(f"Error deleting period {period_id}: {err}")
            ui.notify(f"خطأ أثناء حذف الفترة: {err}", type="negative")

    def _remove_course(self, period_id: int, course_id: int) -> None:
        """Unassigns a course from a period and refreshes the detail workspace."""
        try:
            if hasattr(self.repo, "delete_period_course"):
                self.repo.delete_period_course(period_id, course_id)
            elif self.active_routine_id:
                cur_r = self.repo.get_by_id(self.active_routine_id) or {}
                c_ids = set(cur_r.get("course_ids") or [])
                c_ids.discard(course_id)
                cur_r["course_ids"] = list(c_ids)
                self.repo.update(self.active_routine_id, cur_r)
            ui.notify("تم إلغاء تعيين المادة من الفترة بنجاح", type="positive")
            self._render_right_column.refresh()
        except Exception as err:
            log.error(f"Error unassigning course {course_id} from period {period_id}: {err}")
            ui.notify(f"خطأ أثناء حذف المادة: {err}", type="negative")


class StudyRoutinesScreen:
    """Standalone wrapper screen for the Study Routines view."""
    def __init__(self):
        self.controller = StudyRoutinesController()
