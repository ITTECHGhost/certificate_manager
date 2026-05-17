# =============================================================================
# screens/students_screen.py — Students Management Screen
# =============================================================================
#
# WHAT THIS SCREEN DOES:
#   Full lifecycle management of student records:
#     1. Search (fuzzy + exact) with name suggestions
#     2. View full student details
#     3. Add / Edit student information
#     4. Manage academic periods (one per year or semester)
#     5. Manage course enrollments per period (add, edit score, delete)
#
# LAYOUT:
#   Left (col 0, weight=1):
#     [ Search bar ]
#     [ Suggestions list ]        ← appears during typing
#     [ Student detail view ]     ← appears after selecting
#
#   Right (col 1, weight=0):
#     [ StudentFormPanel ]        ← Add / Edit student info
#     OR
#     [ EnrollmentPanel ]         ← Add / Edit enrollments for a period
#
# FUZZY SEARCH:
#   Uses Python's built-in difflib.get_close_matches() to rank candidates
#   by similarity, so "حسين علي" finds "حسين علي خيرالله" even with
#   minor spelling differences.
#
# DATA LAYER (data/queries.py):
#   fuzzy_search_students(), get_student_by_id()
#   insert_student(), update_student(), delete_student()
#   get_periods_for_student(), insert_period(), update_period(), delete_period()
#   get_enrollments_for_period(), insert_enrollment(),
#   update_enrollment(), delete_enrollment()
#   get_courses_for_dept_stage()
#   get_all_departments(), get_all_governorates(),
#   get_all_countries(), get_all_orders()
#
# =============================================================================

import difflib
import customtkinter as ctk
from db import get_grade

from config import AppFonts, AppColors, AppSizes
from data.repositories import (
    StudentRepository, AcademicPeriodRepository, EnrollmentRepository,
    CourseRepository, DepartmentRepository, GovernorateRepository,
    CountryRepository, GraduationOrderRepository, StudySystemRepository,
    PersonnelRepository, ThesisRepository, SupervisorRepository
)
from ui.base_screen import BaseScreen
from ui.side_panel import SidePanel
from ui.widgets import (
    make_section_header, make_primary_button,
    make_secondary_button, make_danger_button,
)


# =============================================================================
# HELPER MAPS
# =============================================================================

DEGREE_LEVEL_OPTIONS = {
    "دبلوم عالي  /  Higher Diploma": "Higher Diploma",
    "ماجستير  /  Master": "Master",
    "دكتوراه  /  PhD": "PhD",
    "بكالوريوس  /  Bachelor": "Bachelor",
}
DEGREE_LEVEL_DISPLAY = {v: k for k, v in DEGREE_LEVEL_OPTIONS.items()}

STUDY_TYPE_OPTIONS = {
    "صباحي  /  Morning": "morning",
    "مسائي  /  Evening": "evening",
}
STUDY_TYPE_DISPLAY = {v: k for k, v in STUDY_TYPE_OPTIONS.items()}

SEMESTER_OPTIONS = {
    "الفصل الأول  /  First":  "first",
    "الفصل الثاني  /  Second": "second",
}
SEMESTER_DISPLAY = {v: k for k, v in SEMESTER_OPTIONS.items()}

ROUND_OPTIONS = {
    "الدور الأول  /  First Round":  "first",
    "الدور الثاني  /  Second Round": "second",
}
ROUND_DISPLAY = {v: k for k, v in ROUND_OPTIONS.items()}

GENDER_OPTIONS = {
    "ذكر  /  Male": "M",
    "أنثى  /  Female": "F",
}
GENDER_DISPLAY = {v: k for k, v in GENDER_OPTIONS.items()}


# =============================================================================
# STUDENT FORM PANEL  (Add / Edit student information)
# =============================================================================

class StudentFormPanel(SidePanel):
    """
    In-screen panel for adding a new student or editing an existing one.
    Covers all fields in the students table.
    """

    PANEL_WIDTH = 440

    def __init__(self, parent_screen, on_save_callback) -> None:
        self._depts:  list[dict] = []
        self._govs:   list[dict] = []
        self._countries: list[dict] = []
        self._orders: list[dict] = []
        self._study_systems: list[dict] = []
        super().__init__(
            parent_screen,
            title_ar_add="إضافة طالب جديد", title_en_add="Add New Student",
            title_ar_edit="تعديل بيانات الطالب", title_en_edit="Edit Student",
            on_save_callback=on_save_callback,
        )

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_fields(self) -> None:
        # Force the form to split into 4 columns (0, 1, 2 for fields, 3 for headers)
        self._fields_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # -- ROW 0: Name Section --
        self._add_section_label("الاسم", "Name", row=0, col=3)

        self._name_ar = self._add_entry("الاسم الكامل بالعربية", "Full Arabic Name", placeholder="مثال: حسين علي خيرالله", row=0, col=1)
        self._name_en = self._add_entry("الاسم الكامل بالإنكليزية", "Full English Name", placeholder="e.g. Hussein Ali Khairallah", row=0, col=0, justify="left")

        # -- ROW 2: Personal Details Section --
        self._add_section_label("البيانات الشخصية", "Personal Details", row=2, col=3)

        self._dob = self._add_entry("تاريخ الميلاد", "Date of Birth (YYYY-MM-DD)", placeholder="مثال: 2000-05-14", row=2, col=0)
        self._nationality = self._add_dropdown("الجنسية", "Nationality", values=["—"], row=2, col=1)
        self._gender = self._add_dropdown("الجنس", "Gender", values=list(GENDER_OPTIONS.keys()), row=2, col=2)

        self._birthplace_gov = self._add_dropdown("محل الولادة (محافظة عراقية)", "Birthplace (Iraqi governorate)", values=["—  أجنبي / Foreign"], row=4, col=1)
        self._birthplace_other = self._add_entry("محل الولادة (خارج العراق)", "Birthplace (outside Iraq)", placeholder="اتركه فارغاً إذا كان عراقي الولادة", row=4, col=0, justify="left")

        # -- ROW 6: Academic Section --
        self._add_section_label("الدراسة", "Academic", row=6, col=3)

        self._dept = self._add_dropdown("القسم", "Department", values=["—"], row=6, col=1)
        self._study_system = self._add_dropdown("نظام الدراسة", "Study System", values=["—"], row=6, col=0)
        self._adm_year = self._add_entry("سنة القبول", "Admission Year", placeholder="مثال: 2020", row=6, col=2)
        
        self._study_type = self._add_dropdown("نوع الدراسة", "Study Type", values=list(STUDY_TYPE_OPTIONS.keys()), row=8, col=0)
        self._degree_level = self._add_dropdown("الدرجة العلمية", "Degree Level", values=list(DEGREE_LEVEL_OPTIONS.keys()), row=8, col=1)
        self._degree_level.configure(command=self._on_degree_change)
        self._sequence_number = self._add_entry("رقم التسلسل", "Sequence of Graduation", placeholder="مثال: 1", row=8, col=2)
        
        self._postgraduation_no = self._add_entry("عدد الخريجين", "Postgraduation No.", placeholder="مثال: 86", row=9, col=0)

        # -- ROW 10: Graduation Section --
        self._add_section_label("التخرج", "Graduation", row=10, col=3)

        self._grad_date = self._add_entry("تاريخ التخرج", "Graduation Date", placeholder="اتركه فارغاً إن لم يتخرج بعد", row=10, col=0, justify="left")
        self._grad_sem = self._add_combobox("فصل التخرج / الدور", "Graduation Semester / Role", values=["— لم يتخرج بعد / Not yet"] + list(SEMESTER_OPTIONS.keys()), row=10, col=1)
        self._average = self._add_entry("المعدل العام", "Overall Average (50–100)", placeholder="مثال: 78", row=10, col=2)

        self._order = self._add_dropdown("الأمر الجامعي", "Graduation Order", values=["— بدون أمر / None"], row=12, col=0, colspan=2)

        # -- ROW 14: Thesis Section (Hidden by default) --
        self._thesis_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
        self._thesis_frame.grid(row=14, column=0, columnspan=4, sticky="ew")
        self._thesis_frame.grid_columnconfigure((0,1,2,3), weight=1)
        
        self._add_section_label("الرسالة / الأطروحة", "Thesis / Dissertation", row=0, col=3, parent=self._thesis_frame)
        self._thesis_title_ar = self._add_entry("العنوان بالعربية", "Arabic Title", placeholder="العنوان", row=0, col=1, parent=self._thesis_frame)
        self._thesis_title_en = self._add_entry("العنوان بالإنكليزية", "English Title", placeholder="Title", row=0, col=0, parent=self._thesis_frame, justify="left")
        
        self._thesis_defense_date = self._add_entry("تاريخ المناقشة", "Defense Date", placeholder="YYYY-MM-DD", row=2, col=2, parent=self._thesis_frame)
        self._thesis_decision = self._add_dropdown("قرار اللجنة", "Committee Decision", values=["—", "قبول بدون تعديل", "قبول بتعديلات طفيفة", "تعديلات جوهرية", "مرفوض"], row=2, col=1, parent=self._thesis_frame)
        self._thesis_grade = self._add_entry("درجة المناقشة", "Final Grade", placeholder="مثال: 90", row=2, col=0, parent=self._thesis_frame)
        
        self._add_section_label("لجنة الإشراف", "Supervisors", row=4, col=3, parent=self._thesis_frame)
        self._primary_supervisor = self._add_dropdown("المشرف الأول", "Primary Supervisor", values=["—"], row=4, col=1, parent=self._thesis_frame)
        self._secondary_supervisor = self._add_dropdown("المشرف الثاني", "Secondary Supervisor", values=["—"], row=4, col=0, parent=self._thesis_frame)
        
        self._thesis_frame.grid_remove()  # hidden initially
        
    def _on_degree_change(self, value: str) -> None:
        """Toggle thesis frame based on degree level"""
        degree = DEGREE_LEVEL_OPTIONS.get(value, "Bachelor")
        if degree in ["Master", "PhD", "Higher Diploma"]:
            self._thesis_frame.grid()
        else:
            self._thesis_frame.grid_remove()

    def _reload_lookups(self) -> None:
        """Reload all dropdown data from the database."""
        self._depts    = DepartmentRepository().get_all()
        self._govs     = GovernorateRepository().get_all()
        self._countries = CountryRepository().get_all()
        self._orders   = GraduationOrderRepository().get_all()
        self._study_systems = StudySystemRepository().get_active()
        self._personnel = PersonnelRepository().get_active()

        dept_labels = [f"{d['name_ar']}  /  {d['name_en']}" for d in self._depts] or ["—"]
        gov_labels  = ["—  أجنبي / Foreign"] + [
            f"{g['name_ar']}  /  {g['name_en']}" for g in self._govs
        ]
        nat_labels  = [f"{c['name_ar']}  ({c['iso_code']})" for c in self._countries]
        order_labels = ["— بدون أمر / None"] + [
            f"{o['order_number']}  |  {o.get('dept_name_ar','')}  |  {o['admission_year']}"
            for o in self._orders
        ]
        ss_labels = [f"{s['name_ar']}  /  {s['name_en']}" for s in self._study_systems] or ["—"]

        self._dept.configure(values=dept_labels)
        self._birthplace_gov.configure(values=gov_labels)
        self._nationality.configure(values=nat_labels)
        self._order.configure(values=order_labels)
        self._study_system.configure(values=ss_labels)
        
        pers_labels = ["—"] + [f"{p['name_ar']}  /  {p['name_en']}" for p in self._personnel]
        self._primary_supervisor.configure(values=pers_labels)
        self._secondary_supervisor.configure(values=pers_labels)
        
        if ss_labels:
            self._study_system.set(ss_labels[0])

        # Default nationality to Iraq
        iraq_label = next(
            (f"{c['name_ar']}  ({c['iso_code']})" for c in self._countries
             if c["iso_code"] == "IQ"), nat_labels
        )
        self._nationality.set(iraq_label)

        # Default birthplace to Basrah
        basrah_label = next(
            (f"{g['name_ar']}  /  {g['name_en']}" for g in self._govs
             if "بصرة" in g["name_ar"] or "Basra" in g["name_en"]), gov_labels
        )
        self._birthplace_gov.set(basrah_label)

    def open_add(self) -> None:
        self._reload_lookups()
        super().open_add()

    def open_edit(self, data: dict) -> None:
        self._reload_lookups()
        super().open_edit(data)

    # ── Populate (Edit mode) ──────────────────────────────────────────────────

    def _populate(self, data: dict) -> None:
        self._set_entry(self._name_ar,      data.get("full_name_ar",   ""))
        self._set_entry(self._name_en,      data.get("full_name_en",   ""))
        self._set_entry(self._dob,          data.get("date_of_birth",  ""))
        self._set_entry(self._adm_year,     str(data.get("admission_year", "")))
        self._set_entry(self._grad_date,    data.get("graduation_date", "") or "")
        self._set_entry(self._average,      str(data.get("average", "") or ""))
        self._set_entry(self._sequence_number, str(data.get("sequence_number", "") or ""))
        self._set_entry(self._postgraduation_no, str(data.get("postgraduation_no", "") or ""))

        # Gender
        self._set_dropdown(
            self._gender,
            GENDER_DISPLAY.get(data.get("gender", "M"), list(GENDER_OPTIONS.keys())[0])
        )

        # Department
        for d in self._depts:
            if d["id"] == data.get("department_id"):
                self._set_dropdown(self._dept, f"{d['name_ar']}  /  {d['name_en']}")
                break

        # Nationality
        for c in self._countries:
            if c["id"] == data.get("nationality_id"):
                self._set_dropdown(self._nationality, f"{c['name_ar']}  ({c['iso_code']})")
                break

        # Birthplace — governorate or free text
        if data.get("birthplace_id"):
            for g in self._govs:
                if g["id"] == data["birthplace_id"]:
                    self._set_dropdown(
                        self._birthplace_gov,
                        f"{g['name_ar']}  /  {g['name_en']}"
                    )
                    break
        else:
            self._set_dropdown(self._birthplace_gov, "—  أجنبي / Foreign")
            self._set_entry(self._birthplace_other, data.get("birthplace_other", "") or "")

        # Study type
        self._set_dropdown(
            self._study_type,
            STUDY_TYPE_DISPLAY.get(data.get("study_type", "morning"), "")
        )
        
        # Degree level
        self._set_dropdown(
            self._degree_level,
            DEGREE_LEVEL_DISPLAY.get(data.get("degree_level", "Bachelor"), list(DEGREE_LEVEL_OPTIONS.keys())[-1])
        )

        # Graduation semester / Role
        if data.get("graduation_semester"):
            val = SEMESTER_DISPLAY.get(data["graduation_semester"], data["graduation_semester"])
            self._grad_sem.set(val)
        else:
            self._grad_sem.set("— لم يتخرج بعد / Not yet")

        # Study System
        for s in self._study_systems:
            if s["id"] == data.get("study_system_id"):
                self._set_dropdown(self._study_system, f"{s['name_ar']}  /  {s['name_en']}")
                break

        # Order
        if data.get("order_id"):
            for o in self._orders:
                if o["id"] == data["order_id"]:
                    lbl = (f"{o['order_number']}  |  "
                           f"{o.get('dept_name_ar','')}  |  {o['admission_year']}")
                    self._set_dropdown(self._order, lbl)
                    break

        # Thesis and Supervisors
        self._on_degree_change(DEGREE_LEVEL_DISPLAY.get(data.get("degree_level", "Bachelor"), "بكالوريوس  /  Bachelor"))
        if data.get("degree_level") in ["Master", "PhD", "Higher Diploma"]:
            thesis = ThesisRepository().get_by_student(data["id"])
            if thesis:
                self._set_entry(self._thesis_title_ar, thesis.get("title_ar", ""))
                self._set_entry(self._thesis_title_en, thesis.get("title_en", ""))
                self._set_entry(self._thesis_defense_date, thesis.get("defense_date", ""))
                self._set_dropdown(self._thesis_decision, thesis.get("committee_decision", "—"))
                self._set_entry(self._thesis_grade, str(thesis.get("final_grade", "") or ""))
            
            supervisors = SupervisorRepository().get_by_student(data["id"])
            for sup in supervisors:
                pers_lbl = None
                for p in self._personnel:
                    if p["id"] == sup["personnel_id"]:
                        pers_lbl = f"{p['name_ar']}  /  {p['name_en']}"
                        break
                
                if pers_lbl:
                    if sup["supervision_role"] == "Primary":
                        self._set_dropdown(self._primary_supervisor, pers_lbl)
                    elif sup["supervision_role"] == "Secondary":
                        self._set_dropdown(self._secondary_supervisor, pers_lbl)

    # ── Validation ────────────────────────────────────────────────────────────

    def _validate(self) -> str | None:
        if not self._name_ar.get().strip():
            return "الاسم بالعربية مطلوب  —  Arabic name is required"
        if not self._name_en.get().strip():
            return "الاسم بالإنكليزية مطلوب  —  English name is required"
        dob = self._dob.get().strip()
        if not dob or len(dob) != 10:
            return "تاريخ الميلاد مطلوب بصيغة YYYY-MM-DD"
        if not self._adm_year.get().strip().isdigit():
            return "سنة القبول يجب أن تكون رقماً  —  Admission year must be a number"
        if not self._depts:
            return "يجب إضافة قسم أولاً  —  Add a department first"
        avg = self._average.get().strip()
        if avg and not (avg.isdigit() and 50 <= int(avg) <= 100):
            return "المعدل يجب أن يكون بين 50 و100  —  Average must be 50–100"
        # Birthplace consistency
        is_foreign = "أجنبي" in self._birthplace_gov.get()
        foreign_txt = self._birthplace_other.get().strip()
        if is_foreign and not foreign_txt:
            return "يرجى إدخال محل الولادة للطالب الأجنبي"
        return None

    # ── Save ──────────────────────────────────────────────────────────────────

    def _get_dept_id(self) -> int | None:
        label = self._dept.get()
        for d in self._depts:
            if f"{d['name_ar']}  /  {d['name_en']}" == label:
                return d["id"]
        return None

    def _get_nationality_id(self) -> int | None:
        label = self._nationality.get()
        for c in self._countries:
            if f"{c['name_ar']}  ({c['iso_code']})" == label:
                return c["id"]
        return None

    def _get_birthplace(self) -> tuple[int | None, str | None]:
        """Return (birthplace_id, birthplace_other) — exactly one is non-None."""
        gov_label = self._birthplace_gov.get()
        if "أجنبي" in gov_label:
            return (None, self._birthplace_other.get().strip() or "غير محدد")
        for g in self._govs:
            if f"{g['name_ar']}  /  {g['name_en']}" == gov_label:
                return (g["id"], None)
        return (None, "غير محدد")

    def _get_order_id(self) -> int | None:
        label = self._order.get()
        if "بدون أمر" in label:
            return None
        for o in self._orders:
            lbl = (f"{o['order_number']}  |  "
                   f"{o.get('dept_name_ar','')}  |  {o['admission_year']}")
            if lbl == label:
                return o["id"]
        return None

    def _get_study_system_id(self) -> int:
        label = self._study_system.get()
        for s in self._study_systems:
            if f"{s['name_ar']}  /  {s['name_en']}" == label:
                return s["id"]
        # fallback: first active system (annual = id 1)
        return self._study_systems[0]["id"] if self._study_systems else 1

    def _on_save(self, existing: dict | None) -> None:
        bp_id, bp_other = self._get_birthplace()
        avg_raw = self._average.get().strip()
        avg_val = int(avg_raw) if avg_raw.isdigit() else None
        
        seq_raw = self._sequence_number.get().strip()
        seq_val = int(seq_raw) if seq_raw.isdigit() else None

        post_raw = self._postgraduation_no.get().strip()
        post_val = int(post_raw) if post_raw.isdigit() else None
        
        gender_val = GENDER_OPTIONS[self._gender.get()]

        grad_sem_label = self._grad_sem.get()
        grad_sem = None
        if "لم يتخرج" not in grad_sem_label:
            # Map back if it's one of the standard ones, otherwise use text directly
            grad_sem = SEMESTER_OPTIONS.get(grad_sem_label, grad_sem_label)
        grad_date = self._grad_date.get().strip() or None

        order_id = self._get_order_id()

        if existing:
            student_id = existing["id"]
            StudentRepository().update(
                student_id,
                {
                    "full_name_ar": self._name_ar.get().strip(),
                    "full_name_en": self._name_en.get().strip(),
                    "gender": gender_val,
                    "sequence_number": seq_val,
                    "postgraduation_no": post_val,
                    "date_of_birth": self._dob.get().strip(),
                    "birthplace_id": bp_id,
                    "birthplace_other": bp_other,
                    "nationality_id": self._get_nationality_id(),
                    "department_id": self._get_dept_id(),
                    "study_system_id": self._get_study_system_id(),
                    "admission_year": int(self._adm_year.get().strip()),
                    "study_type": STUDY_TYPE_OPTIONS[self._study_type.get()],
                    "degree_level": DEGREE_LEVEL_OPTIONS[self._degree_level.get()],
                    "graduation_date": grad_date,
                    "graduation_semester": grad_sem,
                    "average": avg_val,
                    "order_id": order_id,
                }
            )
        else:
            student_id = StudentRepository().insert(
                {
                    "full_name_ar": self._name_ar.get().strip(),
                    "full_name_en": self._name_en.get().strip(),
                    "gender": gender_val,
                    "sequence_number": seq_val,
                    "postgraduation_no": post_val,
                    "date_of_birth": self._dob.get().strip(),
                    "birthplace_id": bp_id,
                    "birthplace_other": bp_other,
                    "nationality_id": self._get_nationality_id(),
                    "department_id": self._get_dept_id(),
                    "study_system_id": self._get_study_system_id(),
                    "admission_year": int(self._adm_year.get().strip()),
                    "study_type": STUDY_TYPE_OPTIONS[self._study_type.get()],
                    "degree_level": DEGREE_LEVEL_OPTIONS[self._degree_level.get()],
                    "graduation_date": grad_date,
                    "graduation_semester": grad_sem,
                    "average": avg_val,
                }
            )
            
        degree = DEGREE_LEVEL_OPTIONS[self._degree_level.get()]
        if degree in ["Master", "PhD", "Higher Diploma"]:
            grade_raw = self._thesis_grade.get().strip()
            grade_val = float(grade_raw) if grade_raw else None
            ThesisRepository().save(
                student_id=student_id,
                title_ar=self._thesis_title_ar.get().strip() or "",
                title_en=self._thesis_title_en.get().strip() or "",
                defense_date=self._thesis_defense_date.get().strip() or None,
                committee_decision=self._thesis_decision.get().replace("—", "") or None,
                final_grade=grade_val
            )
            
            SupervisorRepository().delete_by_student(student_id)
            prim_lbl = self._primary_supervisor.get()
            if "—" not in prim_lbl:
                for p in self._personnel:
                    if f"{p['name_ar']}  /  {p['name_en']}" == prim_lbl:
                        SupervisorRepository().add(student_id, p["id"], "Primary")
                        break
            
            sec_lbl = self._secondary_supervisor.get()
            if "—" not in sec_lbl:
                for p in self._personnel:
                    if f"{p['name_ar']}  /  {p['name_en']}" == sec_lbl:
                        SupervisorRepository().add(student_id, p["id"], "Secondary")
                        break


# =============================================================================
# ENROLLMENT PANEL  (Add / Edit courses for one academic period)
# =============================================================================

class EnrollmentPanel(ctk.CTkFrame):
    """
    In-screen panel for managing course enrollments in one academic period.

    Shows:
        - Period header (stage, year, passed round)
        - Scrollable list of enrolled courses with score + edit/delete
        - Bottom area: pick a course and enter a score to add it
    """

    PANEL_WIDTH = 460

    def __init__(self, parent_screen: ctk.CTkFrame, on_close) -> None:
        super().__init__(
            parent_screen,
            corner_radius=0,
            fg_color="transparent",
        )
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._parent   = parent_screen
        self._on_close = on_close
        self._period:  dict | None = None
        self._student: dict | None = None
        self._courses: list[dict]  = []
        self._hidden_siblings: list = []

        self._build()

    def _build(self) -> None:
        # ── Header ────────────────────────────────────────────────────────────
        header = ctk.CTkFrame(
            self, height=52, corner_radius=0, fg_color=AppColors.HEADER_BG
        )
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_propagate(False)

        self._title_lbl = ctk.CTkLabel(
            header, text="",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY, weight="bold"),
            anchor="e",
        )
        self._title_lbl.grid(row=0, column=0, sticky="e", padx=(0, 14), pady=12)

        ctk.CTkButton(
            header, text="✕", width=32, height=32, corner_radius=6,
            fg_color="transparent", hover_color=AppColors.NAV_HOVER_BG,
            text_color=AppColors.NAV_TEXT, font=ctk.CTkFont(size=14),
            command=self.close,
        ).grid(row=0, column=0, sticky="w", padx=(8, 0))

        # ── Enrollment list ───────────────────────────────────────────────────
        self._list_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._list_scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=4)
        self._list_scroll.grid_columnconfigure(0, weight=1)

        # ── Add course row ────────────────────────────────────────────────────
        add_frame = ctk.CTkFrame(
            self, fg_color=("gray92", "gray20"), corner_radius=8
        )
        add_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(4, 4))
        add_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            add_frame,
            text="إضافة مادة  —  Add Course",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL, weight="bold"),
            anchor="e",
        ).grid(row=0, column=0, columnspan=3, sticky="e", padx=10, pady=(8, 4))

        self._course_menu = ctk.CTkOptionMenu(
            add_frame, values=["—"],
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=10), height=30,
        )
        self._course_menu.grid(row=1, column=0, sticky="ew", padx=(10, 4), pady=4)

        self._score_entry = ctk.CTkEntry(
            add_frame,
            placeholder_text="الدرجة  0-100",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
            width=70, height=30, justify="center",
        )
        self._score_entry.grid(row=1, column=1, padx=(0, 4), pady=4)

        ctk.CTkButton(
            add_frame, text="إضافة\nAdd", width=60, height=30,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=9),
            corner_radius=6,
            command=self._add_enrollment,
        ).grid(row=1, column=2, padx=(0, 10), pady=4)

        self._add_error = ctk.CTkLabel(
            add_frame, text="",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
            text_color=AppColors.COLOR_ERROR, anchor="e",
        )
        self._add_error.grid(row=2, column=0, columnspan=3, sticky="e", padx=10, pady=(0, 6))

    # ── Open / Close ──────────────────────────────────────────────────────────

    def open(self, period: dict, student: dict) -> None:
        """Show the panel for the given period."""
        self._period  = period
        self._student = student
        self._title_lbl.configure(
            text=f"{student.get('full_name_ar', '')} — المرحلة {period['stage_number']}  —  {period['academic_year']}"
        )
        self._reload_course_picker()
        self._reload_list()
        self._show()

    def close(self) -> None:
        self.grid_remove()
        # Restore siblings
        for child in getattr(self, "_hidden_siblings", []):
            child.grid()
        self._hidden_siblings = []
        self._on_close()

    def _show(self) -> None:
        # Hide siblings to take full page
        self._hidden_siblings = []
        for child in self._parent.winfo_children():
            if child is self:
                continue
            if child.winfo_ismapped():
                child.grid_remove()
                self._hidden_siblings.append(child)
        
        # Grid as full page
        self.grid(row=0, column=0, sticky="nsew", rowspan=20)
        self.tkraise()

    # ── Data ─────────────────────────────────────────────────────────────────

    def _reload_course_picker(self) -> None:
        """Populate the course dropdown with courses for this stage."""
        if not self._period or not self._student:
            return
        self._courses = CourseRepository().get_by_dept_stage_system(
            self._student.get("department_id", 0),
            self._period["stage_number"],
            self._student.get("study_system_id", 1),
        )
        labels = (
            [f"المرحلة {c['stage_number']} — {c['name_ar']}  ({c['credit_hours']} وحدة)" for c in self._courses]
            or ["— لا توجد مواد محددة لهذه المرحلة —"]
        )
        self._course_menu.configure(values=labels)
        self._course_menu.set(labels[0])

    def _reload_list(self) -> None:
        """Reload the enrollment list for the current period."""
        for w in self._list_scroll.winfo_children():
            w.destroy()

        if not self._period:
            return

        enrollments = EnrollmentRepository().get_by_period(self._period["id"])

        if not enrollments:
            ctk.CTkLabel(
                self._list_scroll,
                text="لا توجد مواد مسجلة بعد\nNo courses enrolled yet",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                text_color=AppColors.TEXT_MUTED, justify="center",
            ).grid(row=0, column=0, pady=16)
            return

        # Column header
        hdr = ctk.CTkFrame(
            self._list_scroll, fg_color=("gray82", "gray25"), corner_radius=6
        )
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        for ci, (txt, w) in enumerate([
            ("المادة  /  Course", 180), ("الدرجة  /  Score", 60), ("", 120)
        ]):
            ctk.CTkLabel(
                hdr, text=txt, width=w,
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=10, weight="bold"),
                anchor="center",
            ).grid(row=0, column=ci, padx=4, pady=6)

        for i, enr in enumerate(enrollments):
            bg = ("gray96", "gray20") if i % 2 == 0 else ("white", "gray23")
            row_f = ctk.CTkFrame(self._list_scroll, fg_color=bg, corner_radius=4)
            row_f.grid(row=i + 1, column=0, sticky="ew", pady=1)

            # Course name (truncated)
            name = enr.get("course_name_ar", "")
            ctk.CTkLabel(
                row_f, text=name[:28] + ("…" if len(name) > 28 else ""),
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
                width=180, anchor="e",
            ).grid(row=0, column=0, padx=4, pady=4)

            # Score (editable inline entry)
            score_var = ctk.StringVar(value=str(enr["score"]))
            score_entry = ctk.CTkEntry(
                row_f, textvariable=score_var,
                width=60, height=26, justify="center",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
            )
            score_entry.grid(row=0, column=1, padx=4, pady=4)

            # Action buttons
            btn_frame = ctk.CTkFrame(row_f, fg_color="transparent")
            btn_frame.grid(row=0, column=2, padx=4, pady=4)

            # Save score button
            ctk.CTkButton(
                btn_frame, text="💾", width=32, height=26,
                font=ctk.CTkFont(size=12), corner_radius=4,
                fg_color=AppColors.COLOR_INFO, hover_color="#1565C0",
                command=lambda e=enr, sv=score_var: self._save_score(e, sv),
            ).pack(side="left", padx=(0, 2))

            # Delete button
            ctk.CTkButton(
                btn_frame, text="🗑", width=32, height=26,
                font=ctk.CTkFont(size=12), corner_radius=4,
                fg_color=AppColors.COLOR_ERROR, hover_color="#B71C1C",
                command=lambda e=enr: self._delete_enrollment(e),
            ).pack(side="left")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _add_enrollment(self) -> None:
        """Add the selected course with the entered score to this period."""
        self._add_error.configure(text="")

        selected = self._course_menu.get()
        if "لا توجد" in selected or not self._courses:
            self._add_error.configure(text="⚠️  لا توجد مواد — أضف مواد للقسم أولاً")
            return

        score_str = self._score_entry.get().strip()
        try:
            score = float(score_str)
            if not (0 <= score <= 100):
                raise ValueError
        except ValueError:
            self._add_error.configure(text="⚠️  الدرجة يجب أن تكون بين 0 و100")
            return

        # Find course id from label
        course_id = None
        for c in self._courses:
            label = f"المرحلة {c['stage_number']} — {c['name_ar']}  ({c['credit_hours']} وحدة)"
            if label == selected:
                course_id = c["id"]
                break

        if not course_id:
            self._add_error.configure(text="⚠️  تعذر تحديد المادة")
            return

        try:
            EnrollmentRepository().insert(
                period_id=self._period["id"],
                course_id=course_id,
                score=score,
                is_second=0,
            )
            self._score_entry.delete(0, "end")
            self._reload_list()
        except Exception as e:
            self._add_error.configure(text=f"⚠️  {e}")

    def _save_score(self, enr: dict, score_var: ctk.StringVar) -> None:
        """Save an edited score inline."""
        try:
            score = float(score_var.get().strip())
            if not (0 <= score <= 100):
                raise ValueError
            EnrollmentRepository().update(enr["id"], score, enr["is_second_round"])
            self._reload_list()
        except ValueError:
            pass    # silently ignore invalid score

    def _delete_enrollment(self, enr: dict) -> None:
        """Delete one enrollment row."""
        EnrollmentRepository().delete(enr["id"])
        self._reload_list()


# =============================================================================
# MAIN STUDENTS SCREEN
# =============================================================================

class StudentsScreen(BaseScreen):
    """
    Students management screen.

    Grid layout:
        col 0 (weight=1) → search bar, suggestions, student detail view
        col 1 (weight=0) → StudentFormPanel or EnrollmentPanel (hidden until needed)
    """

    def __init__(self, parent, switch_callback) -> None:
        self._selected_student: dict | None = None
        super().__init__(parent, switch_callback)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(3, weight=1)

        # Side panels — created once
        self._form_panel = StudentFormPanel(
            self, on_save_callback=self._after_save
        )
        self._enroll_panel = EnrollmentPanel(
            self, on_close=self._reload_detail
        )

        # ── Top bar: title + Add button ───────────────────────────────────────
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top.grid_columnconfigure(0, weight=1)
        make_section_header(top, "الطلاب", "Students").grid(row=0, column=0, sticky="e")
        make_primary_button(
            top, "+ إضافة طالب", "Add Student",
            command=self._open_add,
        ).grid(row=0, column=1, padx=(10, 0))

        # ── Search bar ────────────────────────────────────────────────────────
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        search_frame.grid_columnconfigure(0, weight=1)

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._on_search_change)

        self._search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self._search_var,
            placeholder_text="ابحث باسم الطالب (عربي أو إنكليزي)  —  Search student name...",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            height=40, justify="right",
        )
        self._search_entry.grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(
            search_frame,
            text="بحث\nSearch",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_TINY),
            width=70, height=40, corner_radius=8,
            command=self._do_search,
        ).grid(row=0, column=1, padx=(6, 0))

        # ── Suggestions list (shown while searching) ──────────────────────────
        self._suggestion_frame = ctk.CTkScrollableFrame(
            self, height=180, fg_color=("gray94", "gray18")
        )
        self._suggestion_frame.grid_columnconfigure(0, weight=1)
        # Not gridded initially — shown only when suggestions exist

        # ── Student detail view ───────────────────────────────────────────────
        self._detail_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent"
        )
        self._detail_frame.grid(row=3, column=0, sticky="nsew")
        self._detail_frame.grid_columnconfigure(0, weight=1)

        # Initial empty state
        self._show_empty_state()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Called every time this screen becomes active."""
        # If a student was selected before, reload their data
        if self._selected_student:
            refreshed = StudentRepository().get_by_id(self._selected_student["id"])
            if refreshed:
                self._selected_student = refreshed
                self._show_student_detail(refreshed)

    def _after_save(self) -> None:
        """Called by StudentFormPanel after a successful save."""
        self._search_var.set("")
        self._show_empty_state()
        self._selected_student = None

    def _reload_detail(self) -> None:
        """Reload the detail view after enrollment changes."""
        data = StudentRepository().get_by_id(self._selected_student["id"])
        if data:
            self._selected_student = data
            self._show_student_detail(data)

    # ── Search + Fuzzy matching ───────────────────────────────────────────────

    def _on_search_change(self, *_) -> None:
        """Show suggestions as the user types (live, after 2 chars)."""
        query = self._search_var.get().strip()
        if len(query) < 2:
            self._hide_suggestions()
            return
        self._show_suggestions_for(query)

    def _do_search(self) -> None:
        """Explicit search button — same as typing but forces a result."""
        query = self._search_var.get().strip()
        if query:
            self._show_suggestions_for(query)

    def _show_suggestions_for(self, query: str) -> None:
        """
        Fetch candidates, rank by difflib similarity, and display as buttons.

        difflib.get_close_matches ranks Arabic names by character similarity,
        so partial or misspelled names still find the right student.
        """
        candidates = StudentRepository().search(query, limit=30)
        if not candidates:
            self._hide_suggestions()
            return

        # Rank by similarity score
        names_ar = [c["full_name_ar"] for c in candidates]
        names_en = [c["full_name_en"] for c in candidates]

        def similarity(row: dict) -> float:
            ar_score = difflib.SequenceMatcher(None, query, row.get("full_name_ar") or "").ratio()
            en_score = difflib.SequenceMatcher(None, query.lower(),
                                               (row.get("full_name_en") or "").lower()).ratio()
            return max(ar_score, en_score)

        ranked = sorted(candidates, key=similarity, reverse=True)[:8]
        self._render_suggestions(ranked)

    def _render_suggestions(self, students: list[dict]) -> None:
        """Display a button for each suggestion."""
        for w in self._suggestion_frame.winfo_children():
            w.destroy()

        self._suggestion_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(
            self._suggestion_frame,
            text="اختر طالباً  —  Select a student",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_TINY),
            text_color=AppColors.TEXT_MUTED, anchor="e",
        ).grid(row=0, column=0, sticky="e", padx=8, pady=(4, 2))

        for i, s in enumerate(students):
            dept  = s.get("dept_name_ar") or "—"
            year  = str(s.get("admission_year") or "—")
            avg   = f"  |  معدل: {s['average']}" if s.get("average") else ""
            label = f"  {s.get('full_name_ar') or '—'}  —  {dept}  |  دفعة {year}{avg}"

            ctk.CTkButton(
                self._suggestion_frame,
                text=label,
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                height=36, anchor="e",
                fg_color="transparent",
                hover_color=AppColors.NAV_HOVER_BG,
                text_color=AppColors.NAV_TEXT,
                corner_radius=6,
                command=lambda sid=s["id"]: self._select_student(sid),
            ).grid(row=i + 1, column=0, sticky="ew", padx=4, pady=2)

    def _hide_suggestions(self) -> None:
        self._suggestion_frame.grid_remove()
        for w in self._suggestion_frame.winfo_children():
            w.destroy()

    def _select_student(self, student_id: int) -> None:
        """Load the full student record and display it."""
        self._hide_suggestions()
        self._search_var.set("")
        data = StudentRepository().get_by_id(student_id)
        if data:
            self._selected_student = data
            self._show_student_detail(data)
            self._form_panel.close()
            self._enroll_panel.close()

    # ── Detail view ───────────────────────────────────────────────────────────

    def _show_empty_state(self) -> None:
        """Show a prompt when no student is selected."""
        for w in self._detail_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._detail_frame,
            text="🔍\n\nابحث عن طالب للبدء\nSearch for a student to begin",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            text_color=AppColors.TEXT_MUTED, justify="center",
        ).place(relx=0.5, rely=0.4, anchor="center")

    def _show_student_detail(self, data: dict) -> None:
        """
        Render the full student detail view:
            1. Identity card (name, DOB, dept, etc.)
            2. Academic periods + enrollments (expandable)
        """
        for w in self._detail_frame.winfo_children():
            w.destroy()

        frame = self._detail_frame
        frame.grid_columnconfigure(0, weight=1)
        row = 0

        # ── Identity card ─────────────────────────────────────────────────────
        card = ctk.CTkFrame(frame, corner_radius=12, border_width=1,
                            border_color=AppColors.BORDER, fg_color=("gray98", "gray14"))
        card.grid(row=row, column=0, sticky="ew", pady=(0, 20), padx=10)
        card.grid_columnconfigure(0, weight=1)
        row += 1

        # Card header (Distinct background)
        card_hdr = ctk.CTkFrame(card, fg_color=("gray90", "gray20"), corner_radius=12)
        card_hdr.grid(row=0, column=0, sticky="ew")
        card_hdr.grid_columnconfigure(1, weight=1)

        # Action Buttons (Left side)
        btn_row = ctk.CTkFrame(card_hdr, fg_color="transparent")
        btn_row.grid(row=0, column=0, sticky="w", padx=15, pady=10)

        ctk.CTkButton(
            btn_row, text="تعديل  /  Edit", height=32, width=100,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=12),
            corner_radius=6,
            command=lambda: self._form_panel.open_edit(self._selected_student),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="حذف  /  Delete", height=32, width=100,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=12),
            corner_radius=6, fg_color=AppColors.COLOR_ERROR, hover_color="#B71C1C",
            command=self._confirm_delete,
        ).pack(side="left")

        # Student Name (Right side)
        ctk.CTkLabel(
            card_hdr,
            text=f"{data['full_name_ar']}  —  {data['full_name_en']}",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SUBHEADING, weight="bold"),
            anchor="e",
        ).grid(row=0, column=1, sticky="e", padx=20, pady=10)

        # ── Info Fields Grid (2 Columns) ──────────────────────────────────────
        info_container = ctk.CTkFrame(card, fg_color="transparent")
        info_container.grid(row=1, column=0, sticky="ew", padx=15, pady=15)
        # 4 internal columns: [Label L] [Value L] [Label R] [Value R]
        info_container.grid_columnconfigure((0, 1, 2, 3), weight=1)

        avg   = data.get("average")
        grade_ar, grade_en = get_grade(avg) if avg else ("—", "—")

        fields = [
            ("القسم  /  Department",        data.get("dept_name_ar", "—")),
            ("نظام الدراسة  /  Study System", data.get("study_system_name_ar", "—")),
            ("سنة القبول  /  Admission Year", data.get("admission_year", "—")),
            ("تاريخ الميلاد  /  Date of Birth", data.get("date_of_birth", "—")),
            ("الجنسية  /  Nationality",      data.get("nationality_ar", "—")),
            ("محل الولادة  /  Birthplace",
                data.get("birthplace_ar") or data.get("birthplace_other", "—")),
            ("نوع الدراسة  /  Study Type",
                "صباحي / Morning" if data.get("study_type") == "morning" else "مسائي / Evening"),
            ("تاريخ التخرج  /  Graduation Date", data.get("graduation_date", "—")),
            ("فصل التخرج  /  Graduation Semester",
                "الأول / First" if data.get("graduation_semester") == "first"
                else ("الثاني / Second" if data.get("graduation_semester") == "second" else "—")),
            ("المعدل  /  Average",          f"{avg}  ({grade_ar} / {grade_en})" if avg else "—"),
        ]

        def draw_field(parent, label, value, row_idx, col_offset):
            # Text Label
            ctk.CTkLabel(
                parent, text=label,
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=11),
                text_color=AppColors.TEXT_MUTED, anchor="e",
            ).grid(row=row_idx, column=col_offset, sticky="e", padx=(10, 15), pady=8)
            
            # Data Value Box (Badge styling)
            val_box = ctk.CTkFrame(parent, fg_color=("gray90", "gray20"), corner_radius=6)
            val_box.grid(row=row_idx, column=col_offset + 1, sticky="we", padx=(0, 20), pady=6)
            ctk.CTkLabel(
                val_box, text=str(value) if value else "—",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=12, weight="bold"),
                anchor="w",
            ).pack(fill="x", padx=12, pady=5)

        # Distribute fields across 2 columns (RTL logical flow)
        for idx, (lbl, val) in enumerate(fields):
            r_idx = idx // 2
            # Start filling from the right side to respect Arabic reading direction
            c_offset = 2 if idx % 2 == 0 else 0 
            draw_field(info_container, lbl, val, r_idx, c_offset)

        # ── Academic Periods ──────────────────────────────────────────────────
        ctk.CTkLabel(
            frame,
            text="المراحل الدراسية والدرجات  —  Academic Periods & Grades",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY, weight="bold"),
            anchor="e",
        ).grid(row=row, column=0, sticky="e", pady=(0, 8))
        row += 1

        # Add period button
        add_period_frame = ctk.CTkFrame(frame, fg_color="transparent")
        add_period_frame.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        add_period_frame.grid_columnconfigure(0, weight=1)
        row += 1

        # Stage placeholder based on system
        ss_id = data.get("study_system_id", 1)
        stage_placeholder = "رقم السنة  /  Year No. (1-4)" if ss_id == 1 else "رقم الفصل  /  Sem No. (1-8)"
        
        self._new_stage = ctk.CTkEntry(
            add_period_frame,
            placeholder_text=stage_placeholder,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=200, height=34, justify="center",
        )
        self._new_stage.grid(row=0, column=0, sticky="w")

        self._new_year = ctk.CTkEntry(
            add_period_frame,
            placeholder_text="السنة الدراسية  2024-2025",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=160, height=34, justify="center",
        )
        self._new_year.grid(row=0, column=1, padx=6, sticky="w")

        ctk.CTkButton(
            add_period_frame,
            text="+ إضافة مرحلة  /  Add Period",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            height=34, corner_radius=8,
            command=self._add_period,
        ).grid(row=0, column=2)

        # Period cards
        periods = AcademicPeriodRepository().get_by_student(data["id"])
        if not periods:
            ctk.CTkLabel(
                frame,
                text="لا توجد مراحل دراسية مسجلة بعد.\nNo academic periods recorded yet.",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                text_color=AppColors.TEXT_MUTED, justify="center",
            ).grid(row=row, column=0, pady=20)
            row += 1
        else:
            for period in periods:
                self._render_period_card(frame, period, data, row)
                row += 1

    def _render_period_card(
        self, parent, period: dict, student: dict, row: int
    ) -> None:
        """Render one period summary card with its enrollment preview."""
        ROUND_AR = {"first": "الدور الأول", "second": "الدور الثاني"}

        card = ctk.CTkFrame(
            parent, corner_radius=8, border_width=1, border_color=AppColors.BORDER
        )
        card.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)

        # Period header
        p_hdr = ctk.CTkFrame(card, fg_color=("gray88", "gray22"), corner_radius=0)
        p_hdr.grid(row=0, column=0, sticky="ew")
        p_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            p_hdr,
            text=(f"  {'السنة' if student.get('study_system_id') == 1 else 'الفصل'} {period['stage_number']}  |  "
                  f"{period['academic_year']}"),
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL, weight="bold"),
            anchor="e",
        ).grid(row=0, column=0, sticky="e", padx=(0, 10), pady=6)

        # Action buttons
        pb = ctk.CTkFrame(p_hdr, fg_color="transparent")
        pb.grid(row=0, column=0, sticky="w", padx=6, pady=4)

        ctk.CTkButton(
            pb, text="📝 الدرجات\nGrades",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=9),
            width=70, height=28, corner_radius=6,
            command=lambda p=period, s=student: self._enroll_panel.open(p, s),
        ).pack(side="left", padx=(0, 3))

        ctk.CTkButton(
            pb, text="🗑 حذف\nDelete",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=9),
            width=60, height=28, corner_radius=6,
            fg_color=AppColors.COLOR_ERROR, hover_color="#B71C1C",
            command=lambda p=period: self._delete_period(p),
        ).pack(side="left")

        # Enrollment summary (first 6 courses)
        enrollments = EnrollmentRepository().get_by_period(period["id"])
        if enrollments:
            summary = ctk.CTkFrame(card, fg_color="transparent")
            summary.grid(row=1, column=0, sticky="ew", padx=10, pady=6)

            for ci, enr in enumerate(enrollments[:6]):
                ctk.CTkLabel(
                    summary,
                    text=f"  {enr['course_name_ar'][:22]}…  {enr['score']:.0f}",
                    font=ctk.CTkFont(family=AppFonts.FAMILY, size=9),
                    text_color=AppColors.TEXT_MUTED, anchor="e",
                ).grid(row=ci // 2, column=ci % 2, sticky="e", padx=4, pady=1)

            if len(enrollments) > 6:
                ctk.CTkLabel(
                    summary,
                    text=f"  + {len(enrollments) - 6} مادة أخرى  /  more courses...",
                    font=ctk.CTkFont(family=AppFonts.FAMILY, size=9),
                    text_color=AppColors.TEXT_MUTED, anchor="e",
                ).grid(row=3, column=0, columnspan=2, sticky="e", padx=4)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _open_add(self) -> None:
        self._enroll_panel.close()
        self._form_panel.open_add()

    def _add_period(self) -> None:
        """Add a new academic period for the selected student."""
        if not self._selected_student:
            return

        stage_str = self._new_stage.get().strip()
        year_str  = self._new_year.get().strip()

        ss_id = self._selected_student.get("study_system_id", 1)
        max_stage = 4 if ss_id == 1 else 12 # some systems have up to 12 semesters (medicine)
        
        if not stage_str.isdigit() or not (1 <= int(stage_str) <= max_stage):
            self.show_error(f"رقم المرحلة يجب أن يكون بين 1 و {max_stage}.")
            return
        if len(year_str) != 9 or "-" not in year_str:
            self.show_error(
                "السنة الدراسية يجب أن تكون بصيغة YYYY-YYYY\n"
                "مثال: 2023-2024"
            )
            return

        try:
            AcademicPeriodRepository().insert(
                student_id    = self._selected_student["id"],
                year          = year_str,
                sys_id        = self._selected_student.get("study_system_id", 1),
                stage         = int(stage_str),
                round_val     = "first",
            )
            self._new_stage.delete(0, "end")
            self._new_year.delete(0, "end")
            self._reload_detail()
        except Exception as e:
            self.show_error(f"خطأ في إضافة المرحلة:\n{e}")

    def _delete_period(self, period: dict) -> None:
        self.show_confirm(
            message=(
                f"هل تريد حذف المرحلة {period['stage_number']} "
                f"({period['academic_year']})؟\n\n"
                "سيتم حذف جميع الدرجات المرتبطة بها.\n"
                "All grades in this period will also be deleted."
            ),
            on_confirm=lambda: self._do_delete_period(period),
        )

    def _do_delete_period(self, period: dict) -> None:
        AcademicPeriodRepository().delete(period["id"])
        self._reload_detail()

    def _confirm_delete(self) -> None:
        if not self._selected_student:
            return
        self.show_confirm(
            message=(
                f"هل تريد حذف الطالب: {self._selected_student['full_name_ar']}؟\n"
                "Delete this student?\n\n"
                "سيتم حذف جميع المراحل والدرجات المرتبطة به.\n"
                "All academic periods and grades will also be deleted."
            ),
            on_confirm=self._do_delete_student,
        )

    def _do_delete_student(self) -> None:
        if self._selected_student:
            StudentRepository().delete(self._selected_student["id"])
            self._selected_student = None
            self._show_empty_state()
