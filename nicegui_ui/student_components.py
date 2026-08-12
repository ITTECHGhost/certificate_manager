import logging
from nicegui import ui
from nicegui_ui.ui_components import UI
from nicegui_ui.ui_theme import Styles

from data.repositories import (
    AcademicPeriodRepository,
    EnrollmentRepository,
    CourseRepository,
    DepartmentRepository,
    StudySystemRepository,
    OfflineModeError,
    sqlite_read_all,
)

log = logging.getLogger(__name__)


def normalize_year(year_str: str) -> str:
    """Normalize 'YYYY' to 'YYYY-YYYY+1' so grouping keys always match."""
    year_str = str(year_str).strip()
    if len(year_str) == 4 and year_str.isdigit():
        next_year = int(year_str) + 1
        return f"{year_str}-{next_year}"
    return year_str


def calculate_stage(db_year: str, admission_year: str | int | None) -> int:
    """Automatically calculate student stage number from academic year and admission year."""
    try:
        if "-" in db_year:
            year_start = int(db_year.split("-")[0])
        else:
            year_start = int(db_year)
        if admission_year:
            adm_str = str(admission_year).strip()
            if "-" in adm_str:
                adm_year = int(adm_str.split("-")[0])
            else:
                adm_year = int(adm_str)
            diff = year_start - adm_year
            return max(1, diff + 1)
    except Exception:
        pass
    return 1


class CourseEnrollmentView:
    """
    Full dedicated view for managing course enrollments & scores for an academic period.
    All controls (course select, score, round display, save, delete) are aligned strictly in single rows with zero overflow.
    Prevents duplicate course enrollments, blocks re-enrolling in passed courses, displays non-editable Round badges,
    and enforces pass requirement (score >= 50) on 3rd attempt (Round 3).
    """
    def __init__(self, repo, parent_container, on_back):
        self.repo = repo
        self.parent = parent_container
        self.on_back = on_back
        self.period_repo = AcademicPeriodRepository()
        self.enroll_repo = EnrollmentRepository()
        self.course_repo = CourseRepository()

    def render(self, period: dict, student_data: dict):
        self.parent.clear()
        pid = period["id"]
        stage = period.get("stage_number") or calculate_stage(period.get("academic_year", ""), student_data.get("admission_year"))
        dept_id = student_data.get("department_id")
        sys_id = period.get("study_system_id") or student_data.get("study_system_id") or 1
        st_name_ar = student_data.get("full_name_ar") or student_data.get("name_ar") or "طالب"
        st_name_en = student_data.get("full_name_en") or student_data.get("name_en") or ""
        yr = period.get("academic_year", "")
        sem_num = period.get("semester_num", 1)
        sem_label = "الفصل الأول / Term 1" if sem_num == 1 else ("الفصل الثاني / Term 2" if sem_num == 2 else "الفصل الصيفي / Summer")
        student_id = student_data.get("id") or student_data.get("student_id") or period.get("student_id")

        # Fetch current period enrollments
        try:
            enrollments = self.enroll_repo.get_by_period(pid) or []
        except Exception as err:
            log.warning(f"Failed to fetch enrollments for period {pid}: {err}")
            enrollments = []

        current_period_course_ids = {e.get("course_id") for e in enrollments if e.get("course_id")}

        # Track all previous attempts & passed status for this student across all academic periods
        student_course_attempts = {}  # {course_id: count_of_previous_attempts}
        passed_courses = {}  # {course_id: float_score}
        if student_id:
            try:
                all_st_periods = self.period_repo.get_by_student(student_id) or []
                for st_p in all_st_periods:
                    st_enrs = self.enroll_repo.get_by_period(st_p["id"]) or []
                    for e in st_enrs:
                        c_id = e.get("course_id")
                        s_val = e.get("score")
                        if c_id:
                            student_course_attempts[c_id] = student_course_attempts.get(c_id, 0) + 1
                        if c_id and s_val is not None:
                            try:
                                fs = float(s_val)
                                if fs >= 50.0:
                                    passed_courses[c_id] = fs
                            except (ValueError, TypeError):
                                pass
            except Exception as err:
                log.warning(f"Failed to check student passed courses & attempts: {err}")

        def get_suggested_round(c_id: int | None) -> int:
            if not c_id:
                return 1
            attempts = student_course_attempts.get(c_id, 0)
            # 0 previous attempts -> Round 1
            # 1 previous attempt  -> Round 2
            # 2+ previous attempts -> Round 3
            return min(3, max(1, attempts + 1))

        with self.parent:
            with UI.card().classes('flex-1 gap-6 p-6 overflow-hidden'):
                # Top View Header
                with ui.row().classes('w-full justify-between items-center pb-4 border-b border-[var(--border-default)] app-card-header'):
                    with ui.row().classes('items-center gap-4'):
                        ui.button(icon='arrow_back', on_click=lambda: self.on_back(student_data)).props('flat round dense').classes('app-text-primary')
                        ui.icon('edit_note', size='md').classes('app-text-accent')
                        with ui.column().classes('gap-0'):
                            ui.label(f"إدارة المواد والدرجات — {st_name_ar}").classes('text-xl font-bold app-text-primary')
                            if st_name_en:
                                ui.label(st_name_en).classes('text-sm text-slate-400 font-mono')
                            ui.label(f"العام الدراسي: {yr}  •  المرحلة: {stage}  •  {sem_label}").classes('text-sm font-semibold app-text-accent mt-1')

                # Add Course Form Card (Strictly 1 horizontal row)
                with UI.card().classes('w-full p-5 gap-3 bg-[var(--bg-card)] rounded-xl border border-[var(--border-default)] overflow-hidden'):
                    ui.label("إضافة مادة دراسية جديدة — Add New Course").classes('text-base font-bold app-text-accent w-full')
                    
                    try:
                        available_courses = self.course_repo.get_by_department(dept_id) if dept_id else []
                        if not available_courses:
                            available_courses = sqlite_read_all(
                                "SELECT id, name_ar, name_en, credit_hours, stage_number FROM courses ORDER BY stage_number ASC, name_ar ASC"
                            )
                    except Exception as err:
                        log.warning(f"Failed to fetch course catalog: {err}")
                        try:
                            available_courses = sqlite_read_all(
                                "SELECT id, name_ar, name_en, credit_hours, stage_number FROM courses ORDER BY stage_number ASC, name_ar ASC"
                            )
                        except Exception:
                            available_courses = []

                    if available_courses:
                        available_courses.sort(key=lambda c: (int(c.get("stage_number") or 1), str(c.get("name_ar") or "")))

                    course_opts = {}
                    for c in available_courses:
                        cid = c["id"]
                        c_ar = c.get("name_ar", "مادة")
                        c_en = c.get("name_en", "")
                        units = c.get("credit_hours", 1)
                        stg = c.get("stage_number", 1)
                        att_count = student_course_attempts.get(cid, 0)
                        
                        if cid in current_period_course_ids:
                            label = f"المرحلة {stg} / Stage {stg} — {c_ar}" + (f"  /  {c_en}" if c_en else "") + f" ({units} وحدة) — [مسجلة في هذا الفصل]"
                        elif cid in passed_courses:
                            p_score = passed_courses[cid]
                            disp_p = f"{int(p_score)}" if p_score.is_integer() else f"{p_score:.1f}"
                            label = f"المرحلة {stg} / Stage {stg} — {c_ar}" + (f"  /  {c_en}" if c_en else "") + f" ({units} وحدة) — [ناجح: {disp_p}]"
                        elif att_count > 0:
                            sug_round_num = min(3, att_count + 1)
                            round_name = 'الأول' if sug_round_num == 1 else ('الثاني' if sug_round_num == 2 else 'الثالث')
                            label = f"المرحلة {stg} / Stage {stg} — {c_ar}" + (f"  /  {c_en}" if c_en else "") + f" ({units} وحدة) — [محاولة {sug_round_num}: الدور {round_name}]"
                        else:
                            label = f"المرحلة {stg} / Stage {stg} — {c_ar}" + (f"  /  {c_en}" if c_en else "") + f" ({units} وحدة)"
                        course_opts[cid] = label

                    if course_opts:
                        initial_cid = list(course_opts.keys())[0]
                        initial_round = get_suggested_round(initial_cid)

                        with ui.row().classes("w-full gap-3 items-end flex-nowrap"):
                            def format_round_text(r_num: int) -> str:
                                return "الدور الأول / Round 1" if r_num == 1 else ("الدور الثاني / Round 2" if r_num == 2 else "الدور الثالث / Round 3")

                            def on_course_change(e):
                                sel_id = e.value if hasattr(e, 'value') else e
                                if sel_id:
                                    sug_r = get_suggested_round(sel_id)
                                    round_badge.text = format_round_text(sug_r)

                            course_select = UI.select("اختيار المادة / Select Course", course_opts, value=initial_cid, with_input=True, on_change=on_course_change).classes("flex-1 min-w-0 text-sm")
                            score_input = UI.text_input("الدرجة / Score", value="").classes("text-sm").style("width: 110px; min-width: 110px; max-width: 110px;")

                            # Display Round as non-editable badge label
                            with ui.column().classes("gap-1 shrink-0").style("width: 160px; min-width: 160px; max-width: 160px;"):
                                ui.label("الدور / Attempt").classes("text-xs font-semibold app-text-muted")
                                round_badge = ui.label(format_round_text(initial_round)).classes(
                                    "text-sm font-bold px-3 py-2 rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] app-text-accent text-center w-full shadow-sm"
                                )

                            def submit_add_course():
                                cid = course_select.value
                                if not cid:
                                    ui.notify("يرجى اختيار مادة من القائمة", type="warning")
                                    return

                                if cid in current_period_course_ids:
                                    ui.notify(
                                        "المادة مسجلة بالفعل في هذا الفصل! يمكنك تعديل الدرجة مباشرة من القائمة أدناه / Course is already enrolled in this period",
                                        type="warning"
                                    )
                                    return

                                if cid in passed_courses:
                                    p_score = passed_courses[cid]
                                    disp_p = f"{int(p_score)}" if p_score.is_integer() else f"{p_score:.1f}"
                                    ui.notify(
                                        f"لا يمكن تسجيل المادة: الطالب قد نجح فيها سابقاً بمعدل ({disp_p}) / Student already passed this course",
                                        type="warning"
                                    )
                                    return

                                s_str = score_input.value.strip() if score_input.value else ""
                                try:
                                    s_val = float(s_str)
                                    if not (0 <= s_val <= 100):
                                        ui.notify("الدرجة يجب أن تكون بين 0 و100", type="warning")
                                        return
                                except ValueError:
                                    ui.notify("يرجى إدخال درجة صالحة (0-100)", type="warning")
                                    return

                                r_val = get_suggested_round(cid)
                                # Validate 3rd attempt: MUST be >= 50
                                if r_val == 3 and s_val < 50:
                                    ui.notify(
                                        "في المحاولة الثالثة (الدور الثالث)، يجب أن تكون الدرجة 50 أو أعلى (ناجح) لأنه لا يُسمح بفرص إضافية! / On 3rd attempt, score must be >= 50.",
                                        type="warning"
                                    )
                                    return

                                try:
                                    self.enroll_repo.insert(period_id=pid, course_id=cid, score=s_val, is_second=r_val)
                                    ui.notify("تم إضافة المادة بنجاح / Course added successfully", type="positive")
                                    score_input.value = ""
                                    self.render(period, student_data)
                                except Exception as err:
                                    err_msg = str(err)
                                    if "1062" in err_msg or "Duplicate entry" in err_msg:
                                        ui.notify(
                                            "المادة مسجلة بالفعل في هذا الفصل الدراسي! / Course is already enrolled in this period",
                                            type="warning"
                                        )
                                    else:
                                        ui.notify(f"Error adding course: {err}", type="negative")

                            UI.success_button("Add Course / إضافة مادة", icon="add", on_click=submit_add_course).classes("text-sm px-5 py-2.5 shrink-0 h-12")
                    else:
                        ui.label("لا توجد مواد متاحة في دليل المواد لهذه المرحلة والقسم.").classes("text-sm app-text-muted italic py-2")

                # Enrolled Courses List Header
                ui.label("المواد المسجلة في هذه المرحلة — Enrolled Courses").classes('text-lg font-bold app-text-accent mt-4 w-full')

                if not enrollments:
                    with ui.column().classes("w-full items-center py-10 text-center bg-[var(--bg-card)] rounded-xl border border-[var(--border-default)]"):
                        ui.icon("book", size="md").classes("app-text-muted mb-2")
                        ui.label("لا توجد مواد مسجلة بعد في هذه المرحلة").classes("text-base font-bold app-text-muted")
                        ui.label("No courses enrolled yet for this period. Add courses using the form above.").classes("text-xs app-text-muted")
                else:
                    with ui.column().classes("w-full gap-3 overflow-hidden"):
                        for enr in enrollments:
                            eid = enr["id"]
                            raw_score = enr.get("score")
                            if raw_score is not None:
                                try:
                                    fs = float(raw_score)
                                    disp_score = f"{int(fs)}" if fs.is_integer() else f"{fs:.1f}"
                                except:
                                    disp_score = str(raw_score)
                            else:
                                disp_score = ""

                            round_str = str(enr.get("passed_round") or "1")
                            r_num = int(round_str) if round_str.isdigit() else 1
                            r_disp_text = "الدور الأول" if r_num == 1 else ("الدور الثاني" if r_num == 2 else "الدور الثالث")

                            c_ar = enr.get("course_name_ar") or enr.get("name_ar") or "مادة"
                            c_en = enr.get("course_name_en") or enr.get("name_en") or ""

                            # Strictly 1 horizontal row per enrolled course with strict width bounding
                            with ui.row().classes("w-full items-center justify-between p-3.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] gap-3 flex-nowrap overflow-hidden"):
                                # Course Name (Arabic top, English bottom)
                                with ui.column().classes("flex-1 min-w-0 gap-0 text-right overflow-hidden"):
                                    ui.label(c_ar).classes("font-bold text-base app-text-primary truncate")
                                    if c_en:
                                        ui.label(c_en).classes("text-xs text-slate-400 font-mono truncate")

                                with ui.row().classes("items-center gap-3 shrink-0 flex-nowrap"):
                                    score_inp = UI.text_input(label="الدرجة / Score", value=disp_score).classes("text-center text-sm").style("width: 100px; min-width: 100px; max-width: 100px;")

                                    # Display Round as non-editable badge label
                                    with ui.column().classes("gap-0.5 items-center shrink-0").style("width: 110px; min-width: 110px; max-width: 110px;"):
                                        ui.label("الدور / Attempt").classes("text-[10px] app-text-muted font-semibold")
                                        ui.label(r_disp_text).classes("text-xs font-bold px-2 py-1.5 rounded-lg bg-[var(--bg-card)] border border-[var(--border-default)] app-text-accent text-center w-full shadow-sm")

                                    def save_enr(e_id=eid, s_inp=score_inp, cur_r=r_num):
                                        try:
                                            s_val = float(s_inp.value.strip())
                                            if not (0 <= s_val <= 100):
                                                ui.notify("الدرجة يجب أن تكون بين 0 و100", type="warning")
                                                return
                                            # Validate 3rd attempt: MUST be >= 50
                                            if cur_r == 3 and s_val < 50:
                                                ui.notify(
                                                    "في المحاولة الثالثة (الدور الثالث)، يجب أن تكون الدرجة 50 أو أعلى (ناجح) لأنه لا يُسمح بفرص إضافية! / On 3rd attempt, score must be >= 50.",
                                                    type="warning"
                                                )
                                                return
                                            self.enroll_repo.update(e_id, s_val, cur_r)
                                            ui.notify("تم حفظ التعديلات بنجاح", type="positive")
                                            self.render(period, student_data)
                                        except OfflineModeError as err:
                                            ui.notify(str(err), type="warning")
                                        except Exception as err:
                                            ui.notify(f"Error: {err}", type="negative")

                                    def delete_enr(e_id=eid):
                                        try:
                                            self.enroll_repo.delete(e_id)
                                            ui.notify("تم حذف المادة بنجاح", type="positive")
                                            self.render(period, student_data)
                                        except OfflineModeError as err:
                                            ui.notify(str(err), type="warning")
                                        except Exception as err:
                                            ui.notify(f"Error: {err}", type="negative")

                                    UI.primary_button("Save / حفظ", icon="save", on_click=save_enr).classes("text-sm px-4 py-2 shrink-0")
                                    UI.danger_button("Delete / حذف", icon="delete", on_click=delete_enr).classes("text-sm px-4 py-2 shrink-0")


class StudentProfileView:
    def __init__(self, repo, parent_container, on_back, on_edit=None, on_manage_courses=None):
        self.repo = repo
        self.parent = parent_container
        self.on_back = on_back
        self.on_edit = on_edit
        self.on_manage_courses = on_manage_courses
        self.period_repo = AcademicPeriodRepository()
        self.enroll_repo = EnrollmentRepository()
        self.course_repo = CourseRepository()

    def render(self, student_row, initial_tab: str = "info"):
        """Render the profile view inside the parent container, optionally opening directly on a target tab."""
        student_id = student_row.get("id") or student_row.get("student_id")
        if not student_id:
            ui.notify("Error: No student ID provided", type="negative")
            return
            
        data = self.repo.get_by_id(student_id)
        if not data:
            data = student_row
            
        self.parent.clear()
        with self.parent:
            with UI.card().classes('flex-1'):
                # Header
                with ui.row().classes('w-full justify-between items-center pb-3 app-card-header'):
                    with ui.row().classes('items-center gap-4'):
                        ui.button(icon='arrow_back', on_click=self.on_back).props('flat round dense').classes('app-text-primary')
                        ui.icon('person', size='sm').classes('app-text-accent')
                        with ui.column().classes('gap-0'):
                            name_display = data.get("full_name_ar") or data.get("name_ar") or data.get("full_name_en") or "Unknown"
                            dept_display = data.get("dept_name_ar") or data.get("department_name_ar") or "Unknown Dept"
                            grad_year = data.get("graduation_year") or "N/A"
                            ui.label(name_display).classes('text-xl font-bold app-text-primary')
                            ui.label(f"{dept_display} • {grad_year}").classes('text-sm app-text-muted')
                    
                    UI.primary_button(
                        'Edit Student / تعديل البيانات',
                        icon='edit',
                        on_click=lambda: self.on_edit(data) if self.on_edit else ui.notify("Edit handler not connected", type="warning")
                    )
                    
                # Tabs
                with ui.tabs().classes('w-full border-b border-[var(--border-default)] app-text-primary shrink-0') as tabs:
                    info_tab = ui.tab('Info / البيانات الشخصية')
                    academic_tab = ui.tab('Academic / الدراسة والتخرج')
                    periods_tab = ui.tab('Periods & Grades / المراحل والدرجات')
                    
                start_tab = periods_tab if initial_tab == "periods" else (academic_tab if initial_tab == "academic" else info_tab)

                with ui.tab_panels(tabs, value=start_tab).classes('w-full flex-1 overflow-y-auto mt-4 bg-transparent'):
                    with ui.tab_panel(info_tab):
                        with ui.row().classes('w-full gap-12'):
                            with ui.column().classes('gap-4 app-text-primary'):
                                ui.label("Personal Details / البيانات الشخصية").classes('font-bold text-lg mb-2 app-text-accent')
                                
                                gender_map = {1: "ذكر / Male", 2: "أنثى / Female"}
                                gender_val = data.get("gender")
                                gender_str = gender_map.get(gender_val, str(gender_val)) if gender_val else "—"
                                
                                ui.label(f"Gender / الجنس: {gender_str}")
                                ui.label(f"Date of Birth / تاريخ الميلاد: {data.get('date_of_birth', '—')}")
                                ui.label(f"Nationality / الجنسية: {data.get('nationality_ar', '—')}")
                                ui.label(f"Birthplace / مكان الولادة: {data.get('birthplace_ar') or data.get('birthplace_other') or '—'}")
                    
                    with ui.tab_panel(academic_tab):
                        with ui.row().classes('w-full gap-12'):
                            with ui.column().classes('gap-4 app-text-primary flex-1'):
                                ui.label("Academic Details / البيانات الدراسية").classes('font-bold text-lg mb-2 app-text-accent')
                                ui.label(f"Study System / نظام الدراسة: {data.get('study_system_name_ar', '—')}")
                                ui.label(f"Study Type / نوع الدراسة: {data.get('study_type', '—')}")
                                ui.label(f"Admission Year / سنة القبول: {data.get('admission_year', '—')}")
                                ui.label(f"Average / المعدل: {data.get('average', '—')}")
                            
                            with ui.column().classes('gap-4 app-text-primary flex-1'):
                                ui.label("Graduation Details / بيانات التخرج").classes('font-bold text-lg mb-2 app-text-accent')
                                ui.label(f"Order / الامر الجامعي: {data.get('order_number', '—')}")
                                ui.label(f"Graduation Date / تاريخ التخرج: {data.get('graduation_date', '—')}")
                                ui.label(f"Sequence / التسلسل: {data.get('sequence_number', '—')}")
                                ui.label(f"Semester/Role / الدور: {data.get('graduation_semester', '—')}")
                    
                    with ui.tab_panel(periods_tab):
                        self._render_periods_tab(student_id)

    def _render_periods_tab(self, student_id: int):
        """Render reactive academic periods & 3-semester year cards timeline."""
        student_data = self.repo.get_by_id(student_id) or {}
        adm_year = student_data.get("admission_year")
        sys_id = student_data.get("study_system_id") or 1
        is_annual = sys_id in [1, 3]

        periods_container = ui.column().classes("w-full gap-6")

        def refresh_timeline():
            periods_container.clear()
            with periods_container:
                # Top Action Bar: Add Academic Year input
                with ui.row().classes("w-full items-center justify-between gap-4 p-4 rounded-xl app-card-header"):
                    with ui.row().classes("items-center gap-3 flex-1 max-w-lg"):
                        year_input = UI.text_input(
                            label="السنة الدراسية (Academic Year)",
                            placeholder="مثال: 2024-2025"
                        ).classes("flex-1 text-sm")
                        
                        def on_add_year():
                            yr_str = year_input.value.strip() if year_input.value else ""
                            if not yr_str:
                                ui.notify("يرجى إدخال السنة الدراسية / Enter Academic Year", type="warning")
                                return
                            
                            db_yr = normalize_year(yr_str)
                            stage = calculate_stage(db_yr, adm_year)
                            try:
                                self.period_repo.insert(
                                    student_id=student_id,
                                    year=db_yr,
                                    sys_id=sys_id,
                                    stage=stage,
                                    semester_num=1
                                )
                                ui.notify("تم إضافة السنة الدراسية بنجاح / Academic Year added", type="positive")
                                refresh_timeline()
                            except Exception as err:
                                ui.notify(f"Error adding year: {err}", type="negative")

                        UI.success_button("Add Academic Year / إضافة سنة دراسية", icon="add", on_click=on_add_year).classes("text-sm px-4 py-2")

                # Fetch student periods
                try:
                    periods = self.period_repo.get_by_student(student_id) or []
                except Exception as err:
                    log.warning(f"Error fetching periods for student {student_id}: {err}")
                    periods = []

                if not periods:
                    with ui.column().classes("w-full items-center py-12 text-center"):
                        ui.icon("school", size="lg").classes("app-text-muted mb-2")
                        ui.label("لا توجد فترات دراسية مسجلة بعد").classes("text-lg font-bold app-text-muted")
                        ui.label("No academic periods recorded yet. Add an Academic Year above.").classes("text-xs app-text-muted")
                    return

                # Build enrollments & group by normalized academic year
                enrollments_list = []
                for period in periods:
                    try:
                        enrs = self.enroll_repo.get_by_period(period["id"]) or []
                    except Exception:
                        enrs = []
                    norm_yr = normalize_year(period.get("academic_year", ""))
                    for enr in enrs:
                        enr["semester_num"] = period.get("semester_num", 1)
                        enr["academic_year"] = norm_yr
                        enr["period"] = period
                        enrollments_list.append(enr)

                distinct_years = sorted(list(set(normalize_year(p.get("academic_year", "")) for p in periods if p.get("academic_year"))))

                # For each academic year, render Year Card
                for yr in distinct_years:
                    yr_periods = [p for p in periods if normalize_year(p.get("academic_year", "")) == yr]
                    sem1_enrs = [e for e in enrollments_list if e["academic_year"] == yr and e["semester_num"] == 1]
                    sem2_enrs = [e for e in enrollments_list if e["academic_year"] == yr and e["semester_num"] == 2]
                    sem3_enrs = [e for e in enrollments_list if e["academic_year"] == yr and e["semester_num"] == 3]

                    with UI.card().classes("w-full p-4 gap-4 rounded-xl border border-[var(--border-default)]"):
                        # Card Header
                        with ui.row().classes("w-full justify-between items-center pb-2 app-card-header"):
                            with ui.row().classes("items-center gap-2"):
                                ui.icon("calendar_today", size="xs").classes("app-text-accent")
                                ui.label(f"العام الدراسي  |  Academic Year: {yr}").classes("font-bold text-base app-text-primary")

                        # 3 Semester Columns Grid
                        with ui.row().classes("w-full gap-4 flex-nowrap items-start"):
                            # Col 1: Semester 1
                            self._render_semester_box(
                                sem_title="الفصل الأول / Term 1" if is_annual else "الفصل الأول / Semester 1",
                                semester_num=1,
                                academic_year=yr,
                                period=next((p for p in yr_periods if p.get("semester_num") == 1), None),
                                enrollments=sem1_enrs,
                                student_id=student_id,
                                student_data=student_data,
                                refresh_callback=refresh_timeline
                            )

                            # Col 2: Semester 2
                            self._render_semester_box(
                                sem_title="الفصل الثاني / Term 2" if is_annual else "الفصل الثاني / Semester 2",
                                semester_num=2,
                                academic_year=yr,
                                period=next((p for p in yr_periods if p.get("semester_num") == 2), None),
                                enrollments=sem2_enrs,
                                student_id=student_id,
                                student_data=student_data,
                                refresh_callback=refresh_timeline
                            )

                            # Col 3: Semester 3 (Summer)
                            self._render_semester_box(
                                sem_title="الفصل الصيفي / Summer",
                                semester_num=3,
                                academic_year=yr,
                                period=next((p for p in yr_periods if p.get("semester_num") == 3), None),
                                enrollments=sem3_enrs,
                                student_id=student_id,
                                student_data=student_data,
                                refresh_callback=refresh_timeline
                            )

        refresh_timeline()

    def _render_semester_box(
        self,
        sem_title: str,
        semester_num: int,
        academic_year: str,
        period: dict | None,
        enrollments: list,
        student_id: int,
        student_data: dict,
        refresh_callback
    ):
        with ui.column().classes("flex-1 p-4 rounded-lg border border-[var(--border-default)] app-card-header gap-3 min-w-[260px]"):
            with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)]"):
                ui.label(sem_title).classes("font-bold text-sm app-text-accent")

                if period:
                    with ui.row().classes("gap-2"):
                        UI.secondary_button(
                            "📝 الدرجات",
                            on_click=lambda p=period: self.on_manage_courses(p, student_data) if self.on_manage_courses else None
                        ).classes("text-sm px-3 py-1.5")

                        def delete_p(p_id=period["id"]):
                            try:
                                self.period_repo.delete(p_id)
                                ui.notify("تم حذف المرحلة / Period deleted", type="positive")
                                refresh_callback()
                            except OfflineModeError as err:
                                ui.notify(str(err), type="warning")
                            except Exception as err:
                                ui.notify(f"Error: {err}", type="negative")

                        UI.danger_button(
                            "🗑 حذف",
                            on_click=delete_p
                        ).classes("text-sm px-3 py-1.5")
                else:
                    def add_p_and_open():
                        stage = calculate_stage(academic_year, student_data.get("admission_year"))
                        sys_id = student_data.get("study_system_id") or 1
                        try:
                            pid = self.period_repo.insert(
                                student_id=student_id,
                                year=academic_year,
                                sys_id=sys_id,
                                stage=stage,
                                semester_num=semester_num
                            )
                            p_data = {"id": pid, "student_id": student_id, "academic_year": academic_year, "stage_number": stage, "semester_num": semester_num, "study_system_id": sys_id}
                            if self.on_manage_courses:
                                self.on_manage_courses(p_data, student_data)
                        except Exception as err:
                            ui.notify(f"Error: {err}", type="negative")

                    UI.success_button(
                        "+ إضافة مواد",
                        on_click=add_p_and_open
                    ).classes("text-sm px-3 py-1.5")

            # List Enrolled Courses with Arabic and English names
            if enrollments:
                with ui.column().classes("w-full gap-2 mt-1"):
                    for enr in enrollments:
                        score_val = enr.get("score")
                        if score_val is not None:
                            try:
                                raw_score = float(score_val)
                                display_score = f"{int(raw_score)}" if raw_score.is_integer() else f"{raw_score:.1f}"
                            except Exception:
                                display_score = str(score_val)
                        else:
                            display_score = "—"
                        
                        c_ar = enr.get("course_name_ar") or enr.get("name_ar") or "مادة"
                        c_en = enr.get("course_name_en") or enr.get("name_en") or ""

                        with ui.row().classes("w-full justify-between items-center p-2 rounded bg-[var(--bg-card)] gap-2"):
                            with ui.column().classes("flex-1 min-w-0 text-right gap-0"):
                                ui.label(c_ar).classes("font-bold text-sm app-text-primary truncate")
                                if c_en:
                                    ui.label(c_en).classes("text-xs text-slate-400 font-mono truncate")
                            ui.label(f":  {display_score}").classes("font-bold text-sm app-text-accent shrink-0")
            else:
                ui.label("لا توجد مواد / No courses").classes("text-sm app-text-muted italic text-center py-2 w-full")


class StudentFormView:
    def __init__(self, repo, parent_container, on_back, on_save_callback=None):
        self.repo = repo
        self.parent = parent_container
        self.on_back = on_back
        self.on_save = on_save_callback
        self.dept_repo = DepartmentRepository()
        self.sys_repo = StudySystemRepository()
        self.student_id = None
        
    def render_add(self):
        """Render form in add mode"""
        self.student_id = None
        self._build_ui(mode="Add New Student / إضافة طالب جديد")
        
    def render_edit(self, student_row):
        """Render form in edit mode"""
        self.student_id = student_row.get("id") or student_row.get("student_id")
        data = None
        if self.student_id:
            try:
                data = self.repo.get_by_id(self.student_id)
            except Exception as e:
                log.warning(f"Failed to load student details for edit: {e}")
        if not data:
            data = student_row
            
        self._build_ui(mode="Edit Student / تعديل بيانات الطالب", data=data)
        
    def _build_ui(self, mode="Add New Student", data=None):
        self.parent.clear()
        
        # Load active dynamic dropdown options
        try:
            depts = self.dept_repo.get_all()
            dept_opts = {d["id"]: d.get("name_ar", str(d["id"])) for d in depts} if depts else {1: "قسم علوم الحاسوب"}
        except:
            dept_opts = {1: "قسم علوم الحاسوب"}

        try:
            systems = self.sys_repo.get_all()
            sys_opts = {s["id"]: s.get("name_ar", str(s["id"])) for s in systems} if systems else {1: "Annual / صباحي", 2: "Semester / مسائي"}
        except:
            sys_opts = {1: "Annual / صباحي", 2: "Semester / مسائي"}

        with self.parent:
            with UI.card().classes('flex-1'):
                # Header
                with ui.row().classes('w-full justify-between items-center pb-3 app-card-header'):
                    with ui.row().classes('items-center gap-3'):
                        ui.button(icon='arrow_back', on_click=self.on_back).props('flat round dense').classes('app-text-primary')
                        UI.section_header(mode)
                    ui.icon('person_add' if 'Add' in mode else 'edit', size='sm').classes('app-text-accent')
                    
                # Form Body
                with ui.column().classes('w-full flex-1 overflow-y-auto gap-8 mt-4'):
                    
                    # Section: Name
                    ui.label("Name / الاسم").classes('text-lg font-bold app-text-accent w-full')
                    with ui.row().classes('w-full gap-4'):
                        self.name_ar = UI.text_input("Full Arabic Name / الاسم الكامل بالعربية").classes('flex-1')
                        self.name_en = UI.text_input("Full English Name / الاسم الكامل بالإنكليزية").classes('flex-1')
                    
                    # Section: Personal
                    ui.label("Personal Details / البيانات الشخصية").classes('text-lg font-bold app-text-accent w-full')
                    with ui.row().classes('w-full gap-4'):
                        self.dob = UI.text_input("Date of Birth / تاريخ الميلاد (YYYY-MM-DD)").classes('flex-1')
                        self.gender = UI.select("Gender / الجنس", {1: "Male / ذكر", 2: "Female / أنثى"}, value=1).classes('flex-1')
                    
                    # Section: Academic
                    ui.label("Academic / الدراسة").classes('text-lg font-bold app-text-accent w-full')
                    with ui.row().classes('w-full gap-4'):
                        default_dept = list(dept_opts.keys())[0] if dept_opts else 1
                        self.department = UI.select("Department / القسم", dept_opts, value=default_dept).classes('flex-1')
                        self.degree = UI.select("Degree Level / الدرجة العلمية", {1: "Bachelor / بكالوريوس", 2: "Higher Diploma / دبلوم عالي", 3: "Master / ماجستير", 4: "PhD / دكتوراه"}, value=1).classes('flex-1')
                        default_sys = list(sys_opts.keys())[0] if sys_opts else 1
                        self.study_system = UI.select("Study System / نظام الدراسة", sys_opts, value=default_sys).classes('flex-1')
                    
                    # Section: Graduation
                    ui.label("Graduation / التخرج").classes('text-lg font-bold app-text-accent w-full')
                    with ui.row().classes('w-full gap-4'):
                        self.grad_date = UI.text_input("Graduation Date / تاريخ التخرج").classes('flex-1')
                        self.average = UI.text_input("Average / المعدل (50-100)").classes('flex-1')
                        self.sequence = UI.text_input("Sequence Number / رقم التسلسل").classes('flex-1')
                    
                # Footer
                with ui.row().classes('w-full pt-4 mt-4 justify-end gap-4 shrink-0 app-card-header'):
                    UI.success_button('Save / حفظ', icon='save', on_click=self.save)
                    UI.secondary_button('Cancel / إلغاء', on_click=self.on_back)

            # Populate data if edit
            if data:
                self.name_ar.value = data.get("full_name_ar") or data.get("name_ar") or ""
                self.name_en.value = data.get("full_name_en") or data.get("name_en") or ""
                self.dob.value = str(data.get("date_of_birth") or "")
                if data.get("gender") in [1, 2]:
                    self.gender.value = data.get("gender")
                if data.get("department_id") in dept_opts:
                    self.department.value = data.get("department_id")
                if data.get("degree_level") in [1, 2, 3, 4]:
                    self.degree.value = data.get("degree_level")
                if data.get("study_system_id") in sys_opts:
                    self.study_system.value = data.get("study_system_id")
                self.grad_date.value = str(data.get("graduation_date") or "")
                self.average.value = str(data.get("average") or "")
                self.sequence.value = str(data.get("sequence_number") or "")

    def save(self):
        """Extract inputs and persist student changes to database."""
        name_ar_val = self.name_ar.value.strip() if self.name_ar.value else ""
        if not name_ar_val:
            ui.notify("يرجى إدخال اسم الطالب بالعربية / Please enter Arabic Name", type="warning")
            return

        payload = {
            "full_name_ar": name_ar_val,
            "full_name_en": self.name_en.value.strip() if self.name_en.value else "",
            "gender": int(self.gender.value) if self.gender.value else 1,
            "date_of_birth": self.dob.value.strip() if self.dob.value else None,
            "department_id": self.department.value if isinstance(self.department.value, int) else None,
            "study_system_id": self.study_system.value if isinstance(self.study_system.value, int) else 1,
            "degree_level": self.degree.value if isinstance(self.degree.value, int) else 1,
            "graduation_date": self.grad_date.value.strip() if self.grad_date.value else None,
            "average": float(self.average.value) if self.average.value and str(self.average.value).replace('.', '', 1).isdigit() else None,
            "sequence_number": self.sequence.value.strip() if self.sequence.value else None,
        }

        try:
            if self.student_id:
                self.repo.update(self.student_id, payload)
                ui.notify("تم تعديل بيانات الطالب بنجاح / Student updated successfully", type="positive")
            else:
                new_id = self.repo.insert(payload)
                ui.notify(f"تم إضافة الطالب بنجاح (ID: {new_id}) / Student added successfully", type="positive")
            
            if self.on_save:
                self.on_save()
            self.on_back()
        except OfflineModeError as err:
            ui.notify(str(err), type="warning")
        except Exception as err:
            log.error(f"Error saving student: {err}")
            ui.notify(f"Error saving student: {err}", type="negative")
