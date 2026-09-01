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
    GraduationOrderRepository,
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


STATUS_CODE_MAP = {
    1: "PASSED", "1": "PASSED", "PASSED": "PASSED",
    2: "FAILED_REPEAT", "2": "FAILED_REPEAT", "FAILED": "FAILED_REPEAT", "FAILED_REPEAT": "FAILED_REPEAT",
    3: "EXCEPTIONAL_PASS", "3": "EXCEPTIONAL_PASS", "EXCEPTIONAL_PASS": "EXCEPTIONAL_PASS",
    4: "CARRIED_OVER", "4": "CARRIED_OVER", "CARRIED_OVER": "CARRIED_OVER",
    5: "DEFERRED", "5": "DEFERRED", "DEFERRED": "DEFERRED",
    6: "DISMISSED", "6": "DISMISSED", "DISMISSED": "DISMISSED",
}

STATUS_KEY_TO_CODE = {
    "PASSED": 1,
    "FAILED_REPEAT": 2,
    "FAILED": 2,
    "EXCEPTIONAL_PASS": 3,
    "CARRIED_OVER": 4,
    "DEFERRED": 5,
    "DISMISSED": 6,
}

RESULT_STATUS_MAP = {
    "PASSED": {
        "label_ar": "ناجح",
        "label_en": "Passed",
        "badge_class": "bg-emerald-500/10 text-emerald-500 border border-emerald-500/30",
        "icon": "check_circle",
    },
    "CARRIED_OVER": {
        "label_ar": "عبور (تحميل)",
        "label_en": "Carried Over",
        "badge_class": "bg-amber-500/10 text-amber-500 border border-amber-500/30",
        "icon": "published_with_changes",
    },
    "EXCEPTIONAL_PASS": {
        "label_ar": "قرار وزاري",
        "label_en": "Ministerial Pass",
        "badge_class": "bg-indigo-500/10 text-indigo-400 border border-indigo-500/30",
        "icon": "gavel",
    },
    "FAILED_REPEAT": {
        "label_ar": "راسب (إعادة)",
        "label_en": "Failed Repeat",
        "badge_class": "bg-rose-500/10 text-rose-500 border border-rose-500/30",
        "icon": "cancel",
    },
    "DEFERRED": {
        "label_ar": "تأجيل دراسي",
        "label_en": "Deferred",
        "badge_class": "bg-slate-500/10 text-slate-400 border border-slate-500/30",
        "icon": "pause_circle",
    },
    "DISMISSED": {
        "label_ar": "ترقين قيد",
        "label_en": "Dismissed",
        "badge_class": "bg-red-900/20 text-red-400 border border-red-800/40",
        "icon": "block",
    },
}

ROUND_OPTIONS = {
    1: "الدور الأول / Round 1",
    2: "الدور الثاني / Round 2",
    3: "الدور الثالث / Round 3",
}


class CourseEnrollmentView:
    """
    Full dedicated view for managing course enrollments & scores for an academic period.
    All controls (course select, score, round dropdown, save, delete) are aligned strictly in single rows with zero overflow.
    Prevents duplicate course enrollments, blocks re-enrolling in passed courses, offers editable Attempt Round dropdowns,
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
            return 1

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
                            label = f"المرحلة {stg} / Stage {stg} — {c_ar}" + (f"  /  {c_en}" if c_en else "") + f" ({units} وحدة) — [مادة مُعادة - محاولات سابقة: {att_count}]"
                        else:
                            label = f"المرحلة {stg} / Stage {stg} — {c_ar}" + (f"  /  {c_en}" if c_en else "") + f" ({units} وحدة)"
                        course_opts[cid] = label

                    if course_opts:
                        initial_cid = list(course_opts.keys())[0]

                        with ui.row().classes("w-full gap-3 items-end flex-nowrap"):
                            def on_course_change(e):
                                sel_id = e.value if hasattr(e, 'value') else e
                                if sel_id:
                                    round_select.value = 1

                            course_select = UI.select("اختيار المادة / Select Course", course_opts, value=initial_cid, with_input=True, on_change=on_course_change).classes("flex-1 min-w-0 text-sm")
                            score_input = UI.text_input("الدرجة / Score", value="").classes("text-sm").style("width: 100px; min-width: 100px; max-width: 100px;")

                            # Editable Round / Attempt Dropdown List (Defaults to 1: Round 1 / الدور الأول)
                            round_select = UI.select("الدور / Attempt", ROUND_OPTIONS, value=1).classes("text-sm").style("width: 160px; min-width: 160px; max-width: 160px;")

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

                                r_val = int(round_select.value or 1)
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
                                    score_inp = UI.text_input(label="الدرجة / Score", value=disp_score).classes("text-center text-sm").style("width: 90px; min-width: 90px; max-width: 90px;")

                                    # Editable Round / Attempt Dropdown List for each enrolled course
                                    round_sel = UI.select(label="الدور / Attempt", options=ROUND_OPTIONS, value=r_num).classes("text-sm").style("width: 150px; min-width: 150px; max-width: 150px;")

                                    def save_enr(e_id=eid, s_inp=score_inp, r_sel=round_sel):
                                        try:
                                            s_val = float(s_inp.value.strip())
                                            if not (0 <= s_val <= 100):
                                                ui.notify("الدرجة يجب أن تكون بين 0 و100", type="warning")
                                                return
                                            sel_r = int(r_sel.value or 1)
                                            # Validate 3rd attempt: MUST be >= 50
                                            if sel_r == 3 and s_val < 50:
                                                ui.notify(
                                                    "في المحاولة الثالثة (الدور الثالث)، يجب أن تكون الدرجة 50 أو أعلى (ناجح) لأنه لا يُسمح بفرص إضافية! / On 3rd attempt, score must be >= 50.",
                                                    type="warning"
                                                )
                                                return
                                            self.enroll_repo.update(e_id, s_val, sel_r)
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
    def __init__(self, repo, parent_container, on_back, on_edit=None, on_manage_courses=None, on_issue_certificate=None):
        self.repo = repo
        self.parent = parent_container
        self.on_back = on_back
        self.on_edit = on_edit
        self.on_manage_courses = on_manage_courses
        self.on_issue_certificate = on_issue_certificate
        self.period_repo = AcademicPeriodRepository()
        self.enroll_repo = EnrollmentRepository()
        self.course_repo = CourseRepository()

    def render(self, student_data: dict, initial_tab: str = "info", from_cert: bool = False, on_back_to_cert = None):
        if not student_data:
            return
            
        student_id = student_data.get("id") or student_data.get("student_id")
        student_row = student_data
        if student_id:
            try:
                fetched = self.repo.get_by_id(student_id)
                if fetched:
                    student_row = {**student_data, **fetched}
            except Exception as e:
                log.warning(f"Could not fetch full student details: {e}")

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
                    
                    with ui.row().classes('items-center gap-3'):
                        if on_back_to_cert:
                            def _go_cert_profile():
                                on_back_to_cert(data)
                            UI.primary_button(
                                'العودة إلى وثيقة الطالب / Back to Certificate',
                                icon='description',
                                on_click=_go_cert_profile
                            ).classes('text-xs px-4 py-2 font-bold')
                        else:
                            def _go_cert():
                                if self.on_issue_certificate:
                                    self.on_issue_certificate(data)
                                else:
                                    UI.notify("الانتقال إلى إعدادات الوثيقة...", type="info")

                            UI.primary_button(
                                'إصدار الوثيقة / Issue Certificate',
                                icon='workspace_premium',
                                on_click=_go_cert
                            ).classes('text-xs px-4 py-2 font-bold shadow-sm')

                        UI.primary_button(
                            'تعديل البيانات / Edit Student',
                            icon='edit',
                            on_click=lambda: self.on_edit(data, on_back_to_cert=on_back_to_cert) if self.on_edit else ui.notify("Edit handler not connected", type="warning")
                        ).classes('text-xs px-4 py-2 font-bold')
                    
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
                                ui.label(f"Degree Level / الدرجة العلمية: {data.get('degree_level', 'Bachelor')}")
                                ui.label(f"Admission Year / سنة القبول: {data.get('admission_year', '—')}")
                                ui.label(f"Average / المعدل: {data.get('average', '—')}")
                            
                            with ui.column().classes('gap-4 app-text-primary flex-1'):
                                ui.label("Graduation Details / بيانات التخرج والأمر الجامعي").classes('font-bold text-lg mb-2 app-text-accent')
                                ui.label(f"Order / الأمر الجامعي: {data.get('order_number', '—')}")
                                ui.label(f"Graduation Date / تاريخ التخرج: {data.get('graduation_date', '—')}")
                                ui.label(f"Semester/Role / فصل ودور التخرج: {data.get('graduation_semester', '—')}")
                                ui.label(f"Sequence / رقم التسلسل: {data.get('sequence_number', '—')}")
                                ui.label(f"Total Batch Graduates / إجمالي الخريجين (الدفعة): {data.get('postgraduation_number') or data.get('total_graduates') or '—'}")
                                ui.label(f"Summer Training / التدريب الصيفي: {data.get('summer_training_data') or data.get('summer_training') or '—'}")
                    
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
                # Top Action Bar: Add Academic Year input & Stage Selector in ONE SINGLE ROW
                with ui.row().classes("w-full items-center justify-between gap-3 p-3 rounded-xl app-card-header flex-nowrap"):
                    def on_add_year():
                        yr_str = year_input.value.strip() if year_input.value else ""
                        if not yr_str:
                            ui.notify("يرجى إدخال السنة الدراسية / Enter Academic Year", type="warning")
                            return
                        
                        db_yr = normalize_year(yr_str)
                        try:
                            selected_stg = int(stage_add_sel.value or calculate_stage(db_yr, adm_year))
                        except Exception:
                            selected_stg = calculate_stage(db_yr, adm_year)

                        try:
                            self.period_repo.insert(
                                student_id=student_id,
                                year=db_yr,
                                sys_id=sys_id,
                                stage=selected_stg,
                                semester_num=1
                            )
                            ui.notify(f"تم إضافة السنة الدراسية للمرحلة {selected_stg} بنجاح / Academic Year added", type="positive")
                            refresh_timeline()
                        except Exception as err:
                            ui.notify(f"Error adding year: {err}", type="negative")

                    def on_apply_routine_click():
                        from data.repositories import StudyRoutineRepository
                        r_repo = StudyRoutineRepository()
                        st_dept = student_data.get("department_id")
                        routines = r_repo.get_all(st_dept) or r_repo.get_all() or []
                        if not routines:
                            ui.notify("لا توجد روتينات دراسية مضافة. يمكنك إنشاء روتين من صفحة (المواد الدراسية).", type="warning")
                            return
                        
                        r_opts = {r["id"]: f"{r.get('name_ar')} — {r.get('dept_name_ar', '')} (مرحلة {r.get('stage_number')})" for r in routines}
                        
                        dialog = ui.dialog()
                        with dialog, UI.card().classes("p-6 gap-6 w-full max-w-md bg-[var(--bg-card)] rounded-2xl border border-[var(--border-default)]"):
                            ui.label("تطبيق روتين دراسي جاهز — Apply Study Routine").classes("text-lg font-bold app-text-primary border-b border-[var(--border-default)] pb-2 w-full")
                            
                            sel_r = UI.select("اختر الروتين الدراسي / Select Routine", options=r_opts, value=list(r_opts.keys())[0]).classes("w-full text-sm")
                            yr_r_inp = UI.text_input("السنة الدراسية (اختياري) / Academic Year", value="", placeholder="مثال: 2024-2025").classes("w-full text-sm")

                            with ui.row().classes("w-full justify-end gap-3 pt-2"):
                                def do_apply():
                                    rid = sel_r.value
                                    if not rid:
                                        ui.notify("يرجى اختيار روتين", type="warning")
                                        return
                                    try:
                                        custom_yr = yr_r_inp.value.strip() if yr_r_inp.value else ""
                                        res = r_repo.apply_routine_to_student(student_id, rid, academic_year=custom_yr)
                                        ui.notify(f"تم تطبيق الروتين بنجاح وإضافة {res.get('added_courses', 0)} مادة!", type="positive")
                                        dialog.close()
                                        refresh_timeline()
                                    except Exception as err:
                                        ui.notify(f"خطأ أثناء تطبيق الروتين: {err}", type="negative")

                                UI.success_button("تطبيق / Apply", icon="flash_on", on_click=do_apply).classes("text-sm px-4 py-2")
                                UI.secondary_button("إلغاء / Cancel", on_click=dialog.close).classes("text-sm px-4 py-2")
                        dialog.open()

                    # Component 1 & 2: Inputs (Compact widths)
                    with ui.row().classes("items-center gap-3 flex-nowrap shrink-0 min-w-0"):
                        year_input = UI.text_input(
                            label="السنة الدراسية (Academic Year)",
                            placeholder="مثال: 2024-2025"
                        ).props("dense").style("width: 220px !important;").classes("text-xs shrink-0")
                        
                        stage_add_opts = {1: "المرحلة الأولى (1)", 2: "المرحلة الثانية (2)", 3: "المرحلة الثالثة (3)", 4: "المرحلة الرابعة (4)"}
                        stage_add_sel = UI.select("المرحلة الدراسية / Stage", options=stage_add_opts, value=1).props("dense").style("width: 190px !important;").classes("text-xs shrink-0")

                    # Component 3 & 4: Action Buttons (Swapped Order)
                    with ui.row().classes("items-center gap-2 flex-nowrap shrink-0"):
                        UI.success_button("إضافة سنة دراسية / Add Academic Year", icon="add", on_click=on_add_year).classes("text-xs px-3 py-2 shrink-0")
                        UI.primary_button("⚡ تطبيق روتين / Apply Routine", icon="bolt", on_click=on_apply_routine_click).classes("text-xs px-3 py-2 shrink-0")

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
                    stg_val = yr_periods[0].get("stage_number") if yr_periods else None
                    if not stg_val:
                        stg_val = calculate_stage(yr, student_data.get("admission_year"))

                    sem1_enrs = [e for e in enrollments_list if e["academic_year"] == yr and e["semester_num"] == 1]
                    sem2_enrs = [e for e in enrollments_list if e["academic_year"] == yr and e["semester_num"] == 2]
                    sem3_enrs = [e for e in enrollments_list if e["academic_year"] == yr and e["semester_num"] == 3]

                    with UI.card().classes("w-full p-4 gap-4 rounded-xl border border-[var(--border-default)]"):
                        # Card Header with Stage Selector Dropdown
                        with ui.row().classes("w-full justify-between items-center pb-2 app-card-header flex-wrap gap-2"):
                            with ui.row().classes("items-center gap-3"):
                                ui.icon("calendar_today", size="xs").classes("app-text-accent")
                                ui.label(f"العام الدراسي  |  Academic Year: {yr}").classes("font-bold text-base app-text-primary")

                            # Editable Stage Number Selector Dropdown
                            with ui.row().classes("items-center gap-2"):
                                ui.label("المرحلة الدراسية:").classes("text-xs font-bold app-text-muted")
                                stage_card_map = {1: "المرحلة الأولى (1)", 2: "المرحلة الثانية (2)", 3: "المرحلة الثالثة (3)", 4: "المرحلة الرابعة (4)"}
                                
                                def make_stage_changer(p_list=yr_periods):
                                    def _on_stage_change(e):
                                        val = e.value if hasattr(e, "value") else e
                                        try:
                                            new_stg = int(val or 1)
                                            for p in p_list:
                                                self.period_repo.update_stage(p["id"], new_stg)
                                            ui.notify(f"تم تحديث المرحلة الدراسية إلى: المرحلة {new_stg}", type="positive")
                                            refresh_timeline()
                                        except Exception as stg_err:
                                            log.error(f"Error updating stage: {stg_err}")
                                    return _on_stage_change

                                UI.select("", stage_card_map, value=int(stg_val or 1), on_change=make_stage_changer(yr_periods)).classes("text-xs w-44 shrink-0")

                        # 3 Semester Columns Grid (Responsive without horizontal scrollbar)
                        with ui.row().classes("w-full gap-3 items-start flex-wrap lg:flex-nowrap"):
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
        with ui.column().classes("flex-1 min-w-0 w-full lg:w-1/3 p-3.5 rounded-lg border border-[var(--border-default)] app-card-header gap-3"):
            with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)] gap-2 flex-wrap"):
                ui.label(sem_title).classes("font-bold text-sm app-text-accent")

                if period:
                    raw_st = period.get("result_status")
                    cur_status = STATUS_CODE_MAP.get(raw_st, STATUS_CODE_MAP.get(str(raw_st).strip(), "PASSED"))
                    status_info = RESULT_STATUS_MAP.get(cur_status, RESULT_STATUS_MAP["PASSED"])

                    # Period Status Badge Chip
                    with ui.row().classes(f"items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold {status_info['badge_class']}"):
                        ui.icon(status_info["icon"], size="14px")
                        ui.label(f"{status_info['label_ar']} / {status_info['label_en']}")

                    # Editable Status Select Dropdown
                    status_opts = {k: f"{v['label_ar']} / {v['label_en']}" for k, v in RESULT_STATUS_MAP.items()}
                    def on_status_change(e, p_id=period["id"]):
                        new_st = e.value if hasattr(e, "value") else e
                        if new_st:
                            st_key = STATUS_CODE_MAP.get(new_st, "PASSED")
                            st_code = STATUS_KEY_TO_CODE.get(st_key, 1)
                            self.period_repo.update_status(p_id, st_code)
                            period["result_status"] = st_key
                            ui.notify(f"تم تغيير حالة الفترة إلى: {RESULT_STATUS_MAP.get(st_key, {}).get('label_ar', st_key)}", type="positive")
                            refresh_callback()

                    UI.select("", status_opts, value=cur_status, on_change=on_status_change).classes("text-xs w-40 shrink-0")

                    with ui.row().classes("gap-2 items-center"):
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

            # List Enrolled Courses with Arabic and English names (Editable Score & Round)
            if enrollments:
                with ui.column().classes("w-full gap-2 mt-1"):
                    for enr in enrollments:
                        enr_id = enr.get("id")
                        score_val = enr.get("score")
                        is_failed = False
                        raw_score = 0.0
                        if score_val is not None:
                            try:
                                raw_score = float(score_val)
                                if raw_score < 50.0:
                                    is_failed = True
                            except Exception:
                                pass
                        
                        c_ar = enr.get("course_name_ar") or enr.get("name_ar") or "مادة"
                        c_en = enr.get("course_name_en") or enr.get("name_en") or ""
                        pr = str(enr.get("passed_round", "1"))
                        if pr not in ("0", "1", "2", "3"):
                            pr = "1"
                        is_2nd = (pr in ('2', '3') or enr.get("is_second_round"))

                        card_style = "w-full justify-between items-center p-2 rounded gap-2 border border-rose-500/40 bg-rose-500/10" if is_failed else "w-full justify-between items-center p-2 rounded bg-[var(--bg-card)] gap-2"
                        title_style = "font-bold text-sm text-rose-400 truncate" if is_failed else "font-bold text-sm app-text-primary truncate"

                        with ui.row().classes(card_style):
                            # Course Title & Badges
                            with ui.column().classes("flex-1 min-w-0 text-right gap-0"):
                                with ui.row().classes("items-center gap-2 flex-wrap"):
                                    ui.label(c_ar).classes(title_style)
                                    if is_failed:
                                        ui.label("راسب / Failed").classes("px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-rose-500/20 text-rose-400 border border-rose-500/40 shrink-0")
                                    elif is_2nd:
                                        ui.label("الدور الثاني").classes("px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-amber-500/20 text-amber-400 border border-amber-500/30 shrink-0")
                                if c_en:
                                    ui.label(c_en).classes("text-xs text-slate-400 font-mono truncate")

                            # Editable Inputs: Attempt Dropdown & Score Field
                            with ui.row().classes("items-center gap-2 shrink-0"):
                                round_opts = {"1": "الدور الأول", "2": "الدور الثاني", "3": "الدور الثالث", "0": "عبور / تحميل"}
                                
                                # Inline save callback creator
                                def make_updater(cur_eid):
                                    def _on_save_val(e=None):
                                        try:
                                            s_num = float(s_field.value) if s_field.value is not None else 0.0
                                            r_val = int(r_select.value or "1")
                                            self.enroll_repo.update(cur_eid, s_num, r_val)
                                            ui.notify("تم حفظ الدرجة والدور بنجاح / Saved!", type="positive", duration=1.5)
                                            if callable(refresh_callback):
                                                refresh_callback()
                                        except Exception as err:
                                            ui.notify(f"خطأ في الحفظ: {err}", type="negative")
                                    return _on_save_val

                                save_cb = make_updater(enr_id)

                                r_select = ui.select(
                                    options=round_opts,
                                    value=pr,
                                    on_change=save_cb
                                ).props("dense outlined").style("width: 110px !important;").classes("text-xs shrink-0 app-input rounded-lg")

                                s_field = ui.number(
                                    value=int(raw_score) if raw_score.is_integer() else raw_score,
                                    min=0, max=100, step=1,
                                    on_change=save_cb
                                ).props('dense outlined input-class="text-center font-bold text-sm"').style("width: 70px !important;").classes("text-xs shrink-0 app-input rounded-lg")
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
        self.order_repo = GraduationOrderRepository()
        self.student_id = None
        self.editing_student_data = None
        self.on_back_to_cert = None
        
    def render_add(self):
        """Render form in add mode"""
        self.student_id = None
        self.editing_student_data = None
        self.on_back_to_cert = None
        self._build_ui(mode="Add New Student / إضافة طالب جديد")
        
    def render_edit(self, student_row, from_cert: bool = False, on_back_to_cert = None):
        """Render form in edit mode"""
        self.on_back_to_cert = on_back_to_cert
        self.student_id = student_row.get("id") or student_row.get("student_id")
        data = None
        if self.student_id:
            try:
                data = self.repo.get_by_id(self.student_id)
            except Exception as e:
                log.warning(f"Failed to load student details for edit: {e}")
        if not data:
            data = student_row
            
        self.editing_student_data = data
        self._build_ui(mode="Edit Student / تعديل بيانات الطالب", data=data)

    def handle_back_action(self):
        """Intelligent back navigation: return to student profile if editing, or list view if adding."""
        if self.editing_student_data:
            st_data = dict(self.editing_student_data)
            self.editing_student_data = None
            if callable(self.on_back):
                try:
                    self.on_back(st_data)
                except TypeError:
                    self.on_back()
        else:
            if callable(self.on_back):
                self.on_back()
        
    def _build_ui(self, mode="Add New Student", data=None):
        self.parent.clear()
        
        # Load active dynamic dropdown options
        try:
            depts = self.dept_repo.get_all()
            dept_opts = {d["id"]: d.get("name_ar", str(d["id"])) for d in depts} if depts else {1: "قسم علوم الحاسوب"}
        except Exception:
            dept_opts = {1: "قسم علوم الحاسوب"}

        try:
            systems = self.sys_repo.get_all()
            sys_opts = {s["id"]: s.get("name_ar", str(s["id"])) for s in systems} if systems else {1: "نظام فصلي", 2: "نظام سنوي"}
        except Exception:
            sys_opts = {1: "نظام فصلي", 2: "نظام سنوي"}

        # Governorates dropdown
        try:
            govs = sqlite_read_all("SELECT id, name_ar FROM governorates ORDER BY id ASC")
            gov_opts = {g["id"]: g.get("name_ar", str(g["id"])) for g in govs} if govs else {1: "بغداد"}
        except Exception:
            gov_opts = {1: "بغداد"}

        # Countries dropdown
        try:
            countries = sqlite_read_all("SELECT id, name_ar FROM countries ORDER BY id ASC")
            country_opts = {c["id"]: c.get("name_ar", str(c["id"])) for c in countries} if countries else {1: "العراق"}
        except Exception:
            country_opts = {1: "العراق"}

        # Graduation Orders dropdown
        try:
            orders = self.order_repo.get_all(limit=500, offset=0) or []
            order_opts = {0: "بدون أمر تخرج / None"}
            for o in orders:
                onum = o.get("order_number") or "—"
                odate = o.get("order_date") or ""
                odept = o.get("dept_name_ar") or ""
                order_opts[o["id"]] = f"أمر: {onum} ({odept} - {odate})"
        except Exception:
            order_opts = {0: "بدون أمر تخرج / None"}

        SEMESTER_OPTS = {
            "first": "الفصل الأول / Term 1",
            "second": "الفصل الثاني / Term 2",
            "summer": "الفصل الصيفي / Summer",
        }

        with self.parent:
            with UI.card().classes('flex-1'):
                # Header
                with ui.row().classes('w-full justify-between items-center pb-3 app-card-header'):
                    with ui.row().classes('items-center gap-3'):
                        ui.button(icon='arrow_back', on_click=self.handle_back_action).props('flat round dense').classes('app-text-primary')
                        UI.section_header(mode)
                    
                    with ui.row().classes('items-center gap-3'):
                        if hasattr(self, 'on_back_to_cert') and self.on_back_to_cert:
                            def _go_cert_header():
                                st = data or self.editing_student_data or {"id": self.student_id}
                                self.on_back_to_cert(st)
                            UI.primary_button(
                                '📄 العودة إلى وثيقة الطالب / Back to Certificate',
                                icon='description',
                                on_click=_go_cert_header
                            ).classes('text-xs px-4 py-2 font-bold')
                        ui.icon('person_add' if 'Add' in mode else 'edit', size='sm').classes('app-text-accent')
                    
                # Form Body
                with ui.column().classes('w-full flex-1 overflow-y-auto gap-8 mt-4'):
                    
                    # Section 1: Name Details
                    ui.label("Name / بيانات الاسم").classes('text-lg font-bold app-text-accent w-full')
                    with ui.row().classes('w-full gap-4'):
                        self.name_ar = UI.text_input("Full Arabic Name / الاسم الكامل بالعربية").classes('flex-1')
                        self.name_en = UI.text_input("Full English Name / الاسم الكامل بالإنكليزية").classes('flex-1')
                    
                    # Section 2: Personal Details
                    ui.label("Personal Details / البيانات الشخصية").classes('text-lg font-bold app-text-accent w-full')
                    with ui.row().classes('w-full gap-4'):
                        self.dob = UI.text_input("Date of Birth / تاريخ الميلاد (YYYY-MM-DD)").classes('flex-1')
                        self.gender = UI.select("Gender / الجنس", {1: "Male / ذكر", 2: "Female / أنثى"}, value=1).classes('flex-1')
                        default_gov = 2 if 2 in gov_opts else (list(gov_opts.keys())[0] if gov_opts else 2)
                        self.birthplace = UI.select("Birthplace / مكان الولادة", gov_opts, value=default_gov).classes('flex-1')
                        default_ctry = 274 if 274 in country_opts else (list(country_opts.keys())[0] if country_opts else 274)
                        self.nationality = UI.select("Nationality / الجنسية", country_opts, value=default_ctry).classes('flex-1')

                    # Section 3: Academic Details
                    ui.label("Academic / الدراسة والأكاديميا").classes('text-lg font-bold app-text-accent w-full')
                    with ui.row().classes('w-full gap-4'):
                        default_dept = list(dept_opts.keys())[0] if dept_opts else 1
                        self.department = UI.select("Department / القسم", dept_opts, value=default_dept).classes('flex-1')
                        self.degree = UI.select("Degree Level / الدرجة العلمية", {1: "Bachelor / بكالوريوس", 2: "Higher Diploma / دبلوم عالي", 3: "Master / ماجستير", 4: "PhD / دكتوراه"}, value=1).classes('flex-1')
                        default_sys = list(sys_opts.keys())[0] if sys_opts else 1
                        self.study_system = UI.select("Study System / نظام الدراسة", sys_opts, value=default_sys).classes('flex-1')
                        self.admission_year = UI.text_input("Admission Year / سنة القبول (مثال: 2021)").classes('flex-1')

                    routine_opts = {0: "بدون روتين دراسي / No Routine"}
                    try:
                        from data.repositories import StudyRoutineRepository
                        all_r = StudyRoutineRepository().get_all() or []
                        for r in all_r:
                            routine_opts[r["id"]] = f"{r.get('name_ar')} — {r.get('dept_name_ar', '')} (مرحلة {r.get('stage_number')})"
                    except Exception:
                        pass

                    with ui.row().classes('w-full gap-4'):
                        self.routine_select = UI.select("Predefined Routine / تطبيق روتين دراسي تلقائي (اختياري)", routine_opts, value=0).classes('w-full')
                    
                    # Section 4: Graduation & Ministerial Order
                    ui.label("Graduation & Ministerial Order / التخرج والأمر الجامعي").classes('text-lg font-bold app-text-accent w-full')
                    with ui.row().classes('w-full gap-4'):
                        self.order_id = UI.select("Graduation Order / الأمر الجامعي", order_opts, value=0).classes('flex-1')
                        self.grad_date = UI.text_input("Graduation Date / تاريخ التخرج (YYYY-MM-DD)").classes('flex-1')
                        self.grad_semester = UI.select("Graduation Semester / فصل التخرج", SEMESTER_OPTS, value="first").classes('flex-1')

                    with ui.row().classes('w-full gap-4'):
                        self.average = UI.text_input("Average / المعدل (50-100)").classes('flex-1')
                        self.sequence = UI.text_input("Sequence Number / رقم التسلسل").classes('flex-1')
                        self.postgrad_num = UI.text_input("إجمالي الخريجين (الدفعة) / Total Postgrad Students").classes('flex-1')

                    with ui.row().classes('w-full gap-4'):
                        self.summer_training = UI.text_input("Summer Training / التدريب الصيفي").classes('w-full')
                    
                # Footer Action Buttons
                with ui.row().classes('w-full pt-4 mt-4 justify-end gap-4 shrink-0 app-card-header'):
                    UI.success_button('Save / حفظ', icon='save', on_click=self.save)
                    if hasattr(self, 'on_back_to_cert') and self.on_back_to_cert:
                        def _go_cert_footer():
                            st = data or self.editing_student_data or {"id": self.student_id}
                            self.on_back_to_cert(st)
                        UI.primary_button(
                            '📄 العودة للوثيقة / Back to Certificate',
                            icon='description',
                            on_click=_go_cert_footer
                        ).classes('text-xs px-4 py-2 font-bold')
                    UI.secondary_button('Cancel / إلغاء', on_click=self.handle_back_action)

            # Populate data if edit mode
            if data:
                self.name_ar.value = data.get("full_name_ar") or data.get("name_ar") or ""
                self.name_en.value = data.get("full_name_en") or data.get("name_en") or ""
                self.dob.value = str(data.get("date_of_birth") or "")
                if data.get("gender") in [1, 2]:
                    self.gender.value = data.get("gender")
                if data.get("birthplace_id") in gov_opts:
                    self.birthplace.value = data.get("birthplace_id")
                if data.get("nationality_id") in country_opts:
                    self.nationality.value = data.get("nationality_id")

                if data.get("department_id") in dept_opts:
                    self.department.value = data.get("department_id")
                if data.get("degree_level") in [1, 2, 3, 4]:
                    self.degree.value = data.get("degree_level")
                if data.get("study_system_id") in sys_opts:
                    self.study_system.value = data.get("study_system_id")
                self.admission_year.value = str(data.get("admission_year") or "")

                oid_val = data.get("order_id")
                if oid_val in order_opts:
                    self.order_id.value = oid_val
                else:
                    self.order_id.value = 0

                self.grad_date.value = str(data.get("graduation_date") or "")
                gsem = str(data.get("graduation_semester") or "").lower()
                if gsem in SEMESTER_OPTS:
                    self.grad_semester.value = gsem

                self.average.value = str(data.get("average") or "")
                self.sequence.value = str(data.get("sequence_number") or "")
                self.postgrad_num.value = str(data.get("postgraduation_number") or "")
                self.summer_training.value = str(data.get("summer_training_data") or data.get("summer_training") or "")

    def save(self):
        """Extract inputs and persist student changes to database."""
        name_ar_val = self.name_ar.value.strip() if self.name_ar.value else ""
        if not name_ar_val:
            ui.notify("يرجى إدخال اسم الطالب بالعربية / Please enter Arabic Name", type="warning")
            return

        # Validate Date of Birth
        dob_raw = self.dob.value.strip() if self.dob.value else None
        if dob_raw:
            from datetime import datetime
            normalized_dob = dob_raw.replace("/", "-").replace(".", "-")
            parts = normalized_dob.split("-")
            valid_dob = False
            if len(parts) == 3 and len(parts[0]) == 4:
                try:
                    dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                    dob_raw = dt.strftime("%Y-%m-%d")
                    valid_dob = True
                except ValueError:
                    pass
            if not valid_dob:
                ui.notify("تاريخ غير صالح في (تاريخ الميلاد). يرجى كتابة التاريخ بصيغة YYYY-MM-DD (مثال: 1995-05-05)", type="warning")
                return

        # Validate Graduation Date
        grad_date_raw = self.grad_date.value.strip() if self.grad_date.value else None
        if grad_date_raw:
            from datetime import datetime
            normalized_gdate = grad_date_raw.replace("/", "-").replace(".", "-")
            parts = normalized_gdate.split("-")
            valid_gdate = False
            if len(parts) == 3 and len(parts[0]) == 4:
                try:
                    dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                    grad_date_raw = dt.strftime("%Y-%m-%d")
                    valid_gdate = True
                except ValueError:
                    pass
            if not valid_gdate:
                ui.notify("تاريخ غير صالح في (تاريخ التخرج). يرجى كتابة التاريخ بصيغة YYYY-MM-DD (مثال: 2025-12-05)", type="warning")
                return

        oid_val = self.order_id.value if isinstance(self.order_id.value, int) and self.order_id.value > 0 else None

        payload = {
            "full_name_ar": name_ar_val,
            "full_name_en": self.name_en.value.strip() if self.name_en.value else "",
            "gender": int(self.gender.value) if self.gender.value else 1,
            "date_of_birth": dob_raw,
            "birthplace_id": self.birthplace.value if isinstance(self.birthplace.value, int) else None,
            "nationality_id": self.nationality.value if isinstance(self.nationality.value, int) else 1,
            "department_id": self.department.value if isinstance(self.department.value, int) else None,
            "study_system_id": self.study_system.value if isinstance(self.study_system.value, int) else 1,
            "degree_level": self.degree.value if isinstance(self.degree.value, int) else 1,
            "admission_year": self.admission_year.value.strip() if self.admission_year.value else None,
            "order_id": oid_val,
            "graduation_date": grad_date_raw,
            "graduation_semester": str(self.grad_semester.value or "first"),
            "average": float(self.average.value) if self.average.value and str(self.average.value).replace('.', '', 1).isdigit() else None,
            "sequence_number": self.sequence.value.strip() if self.sequence.value else None,
            "postgraduation_number": self.postgrad_num.value.strip() if self.postgrad_num.value else None,
            "summer_training_data": self.summer_training.value.strip() if self.summer_training.value else None,
        }

        try:
            if self.student_id:
                self.repo.update(self.student_id, payload)
                ui.notify("تم تعديل بيانات الطالب بنجاح / Student updated successfully", type="positive")
            else:
                new_id = self.repo.insert(payload)
                self.student_id = new_id
                ui.notify(f"تم إضافة الطالب بنجاح (ID: {new_id}) / Student added successfully", type="positive")

                sel_routine_id = self.routine_select.value if hasattr(self, 'routine_select') and isinstance(self.routine_select.value, int) and self.routine_select.value > 0 else None
                if sel_routine_id:
                    try:
                        from data.repositories import StudyRoutineRepository
                        r_repo = StudyRoutineRepository()
                        adm_yr = self.admission_year.value.strip() if self.admission_year.value else ""
                        r_repo.apply_routine_to_student(new_id, sel_routine_id, academic_year=adm_yr)
                        ui.notify("تم تطبيق الروتين الدراسي وإدراج المواد تلقائياً! / Study routine applied", type="positive")
                    except Exception as r_err:
                        log.warning(f"Failed to apply routine to student {new_id}: {r_err}")
            
            if self.on_save:
                self.on_save()
            self.handle_back_action()
        except OfflineModeError as err:
            ui.notify(str(err), type="warning")
        except Exception as err:
            log.error(f"Error saving student: {err}")
            ui.notify(f"Error saving student: {err}", type="negative")
