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
# HELPER FUNCTIONS
# =============================================================================

def normalize_year(year_str: str) -> str:
    """Normalize 'YYYY' to 'YYYY-YYYY+1' so grouping keys always match."""
    year_str = str(year_str).strip()
    if len(year_str) == 4 and year_str.isdigit():
        next_year = int(year_str) + 1
        return f"{year_str}-{next_year}"
    return year_str


def format_score(score) -> str:
    if score is None:
        return "—"
    try:
        raw_score = float(score)
        display_score = f"{int(raw_score)}" if raw_score.is_integer() else f"{raw_score:.1f}"
        return display_score
    except Exception:
        return str(score)


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
        self._all_order_labels: list[str] = []
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
        
        # -- ROW 10: Graduation Section --
        self._add_section_label("التخرج", "Graduation", row=10, col=3)

        self._grad_date = self._add_entry("تاريخ التخرج", "Graduation Date", placeholder="اتركه فارغاً إن لم يتخرج بعد", row=10, col=0, justify="left")
        self._grad_sem = self._add_combobox("فصل التخرج / الدور", "Graduation Semester / Role", values=["— لم يتخرج بعد / Not yet"] + list(SEMESTER_OPTIONS.keys()), row=10, col=1)
        self._average = self._add_entry("المعدل العام", "Overall Average (50–100)", placeholder="مثال: 78", row=10, col=2)

        self._postgraduation_no = self._add_entry("عدد الخريجين", "Postgraduation No.", placeholder="مثال: 86", row=12, col=0)
        self._sequence_number = self._add_entry("رقم التسلسل", "Sequence of Graduation", placeholder="مثال: 1", row=12, col=1)

        self._order = self._add_combobox("الأمر الجامعي", "Graduation Order", values=["— بدون أمر / None"], row=14, col=0, colspan=3)
        self._order.bind("<KeyRelease>", self._filter_orders)

        # -- ROW 16: Thesis Section (Hidden by default) --
        self._thesis_frame = ctk.CTkFrame(self._fields_frame, fg_color="transparent")
        self._thesis_frame.grid(row=16, column=0, columnspan=4, sticky="ew")
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

    def _filter_orders(self, event=None) -> None:
        """Filter the graduation order combobox values based on typed text."""
        typed = self._order.get().strip().lower()
        if not typed:
            self._order.configure(values=self._all_order_labels)
        else:
            filtered = [label for label in self._all_order_labels if typed in label.lower()]
            if not filtered:
                filtered = ["— لا توجد نتائج / No results"]
            self._order.configure(values=filtered)

    def _reload_lookups(self) -> None:
        """Reload all dropdown data from the database."""
        self._depts    = DepartmentRepository().get_all()
        self._govs     = GovernorateRepository().get_all()
        self._countries = CountryRepository().get_all()
        self._orders   = GraduationOrderRepository().get_all()
        self._study_systems = StudySystemRepository().get_active()
        self._personnel = PersonnelRepository().get_active()

        # Sort graduation orders from last recent date (2026 and down)
        def get_order_date_key(o):
            dt = o.get("order_date")
            if dt is None:
                return ""
            if isinstance(dt, str):
                return dt
            return dt.strftime("%Y-%m-%d")
        self._orders = sorted(self._orders, key=get_order_date_key, reverse=True)

        dept_labels = [f"{d['name_ar']}  /  {d['name_en']}" for d in self._depts] or ["—"]
        gov_labels  = ["—  أجنبي / Foreign"] + [
            f"{g['name_ar']}  /  {g['name_en']}" for g in self._govs
        ]
        nat_labels  = [f"{c['name_ar']}  ({c['iso_code']})" for c in self._countries]
        
        self._all_order_labels = ["— بدون أمر / None"] + [
            f"{o['order_number']}  |  {o.get('dept_name_ar','')}  |  {o.get('admission_year','') or '—'}"
            for o in self._orders
        ]
        ss_labels = [f"{s['name_ar']}  /  {s['name_en']}" for s in self._study_systems] or ["—"]

        self._dept.configure(values=dept_labels)
        self._birthplace_gov.configure(values=gov_labels)
        self._nationality.configure(values=nat_labels)
        self._order.configure(values=self._all_order_labels)
        self._order.set(self._all_order_labels[0])
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
        # Graduation details fallback logic
        grad_date = data.get("graduation_date") or data.get("order_date")
        self._set_entry(self._grad_date,    str(grad_date) if grad_date else "")
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
        grad_sem = data.get("graduation_semester") or data.get("order_graduation_semester")
        if grad_sem:
            val = SEMESTER_DISPLAY.get(grad_sem, grad_sem)
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
                           f"{o.get('dept_name_ar','')}  |  {o.get('admission_year','') or '—'}")
                    self._set_dropdown(self._order, lbl)
                    break

        # Thesis and Supervisors
        self._on_degree_change(DEGREE_LEVEL_DISPLAY.get(data.get("degree_level", "Bachelor"), "بكالوريوس  /  Bachelor"))
        if data.get("degree_level") in ["Master", "PhD", "Higher Diploma"]:
            thesis = ThesisRepository().get_by_student(data["id"])
            if thesis:
                if isinstance(thesis, list):
                    thesis = thesis[0] if thesis else None
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
        label = self._order.get().strip()
        if not label or "بدون أمر" in label or "None" in label:
            return None
        for o in self._orders:
            lbl = (f"{o['order_number']}  |  "
                   f"{o.get('dept_name_ar','')}  |  {o.get('admission_year','') or '—'}")
            if lbl == label or o['order_number'] in label:
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
                    "order_id": order_id,
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

        self._selected_course = None

        self._course_search_entry = ctk.CTkEntry(
            add_frame,
            placeholder_text="ابحث عن مادة... / Search course...",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=10), height=30,
        )
        self._course_search_entry.grid(row=1, column=0, sticky="ew", padx=(10, 4), pady=4)
        self._course_search_entry.bind("<KeyRelease>", self._on_course_search_key)
        self._course_search_entry.bind("<FocusIn>", lambda e: self._course_list_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 4)))
        self._course_search_entry.bind("<Escape>", lambda e: self._course_list_frame.grid_remove())

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

        self._course_list_frame = ctk.CTkScrollableFrame(
            add_frame, height=120, fg_color=("gray95", "gray18")
        )
        # Hidden initially, gridded dynamically during search or focus

        self._add_error = ctk.CTkLabel(
            add_frame, text="",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
            text_color=AppColors.COLOR_ERROR, anchor="e",
        )
        self._add_error.grid(row=4, column=0, columnspan=3, sticky="e", padx=10, pady=(0, 6))

    # ── Open / Close ──────────────────────────────────────────────────────────

    def open(self, period: dict, student: dict) -> None:
        """Show the panel for the given period."""
        self._period  = period
        self._student = student
        self._title_lbl.configure(
            text=f"{student.get('full_name_ar', '')} — {period['academic_year']}"
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
        """Populate the course catalog and prepare the search filter list."""
        if not self._period or not self._student:
            return
        
        dept_id = self._student.get("department_id", 0)
        system_id = self._student.get("study_system_id", 1)
        self._courses = CourseRepository().get_by_dept_stage_system(dept_id, 12, system_id)


        self._selected_course = None
        self._course_search_entry.delete(0, "end")
        self._course_list_frame.grid_remove()
        self._filter_courses_in_list("")
        self._course_list_frame.grid_remove()

    def _on_course_search_key(self, event=None) -> None:
        query = self._course_search_entry.get().strip().lower()
        self._filter_courses_in_list(query)

    def _filter_courses_in_list(self, query: str = "") -> None:
        """Filter and render matching courses in the scrollable list frame."""
        for w in self._course_list_frame.winfo_children():
            w.destroy()

        filtered = []
        for c in self._courses:
            lbl = f"المرحلة {c['stage_number']} — {c['name_ar']}  /  {c['name_en']}  ({c['credit_hours']} وحدة)"
            if not query or query in lbl.lower():
                filtered.append((c, lbl))

        if not filtered:
            lbl_no = ctk.CTkLabel(
                self._course_list_frame,
                text="لا توجد نتائج  /  No results",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
                text_color=AppColors.TEXT_MUTED,
            )
            lbl_no.pack(pady=4)
            self._course_list_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 4))
            return

        for c, lbl in filtered:
            btn = ctk.CTkButton(
                self._course_list_frame,
                text=lbl,
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
                height=26, anchor="e",
                fg_color="transparent",
                hover_color=AppColors.NAV_HOVER_BG,
                text_color=AppColors.NAV_TEXT,
                corner_radius=4,
                command=lambda course=c, label=lbl: self._select_course(course, label),
            )
            btn.pack(fill="x", pady=1)

        self._course_list_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 4))

    def _select_course(self, course: dict, label: str) -> None:
        self._selected_course = course
        self._course_search_entry.delete(0, "end")
        self._course_search_entry.insert(0, f"المرحلة {course['stage_number']} — {course['name_ar']}")
        self._course_list_frame.grid_remove()

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
            if enr["score"] is not None:
                raw_score = float(enr['score'])
                display_score = f"{int(raw_score)}" if raw_score.is_integer() else f"{raw_score:.1f}"
            else:
                display_score = "—"
            score_var = ctk.StringVar(value=display_score)
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

        if not getattr(self, "_selected_course", None) or not self._courses:
            self._add_error.configure(text="⚠️  الرجاء اختيار مادة من القائمة")
            return

        score_str = self._score_entry.get().strip()
        try:
            score = float(score_str)
            if not (0 <= score <= 100):
                raise ValueError
        except ValueError:
            self._add_error.configure(text="⚠️  الدرجة يجب أن تكون بين 0 و100")
            return

        course_id = self._selected_course["id"]

        try:
            EnrollmentRepository().insert(
                period_id=self._period["id"],
                course_id=course_id,
                score=score,
                is_second=0,
            )
            self._score_entry.delete(0, "end")
            self._selected_course = None
            self._course_search_entry.delete(0, "end")
            self._course_list_frame.grid_remove()
            self._reload_list()
        except Exception as e:
            self._add_error.configure(text=f"⚠️  {e}")

    def _save_score(self, enr: dict, score_var: ctk.StringVar) -> None:
        """Save an edited score inline."""
        try:
            score_val = float(score_var.get().strip())
            if not (0 <= score_val <= 100):
                raise ValueError
            EnrollmentRepository().update(enr["id"], score_val, enr["is_second_round"])
            score_var.set(format_score(score_val))
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
        self.grid_rowconfigure((0, 1, 2), weight=0)
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
        top.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        top.grid_columnconfigure(0, weight=1)
        make_section_header(top, "الطلاب", "Students").grid(row=0, column=0, sticky="e")
        make_primary_button(
            top, "+ إضافة طالب", "Add Student",
            command=self._open_add,
        ).grid(row=0, column=1, padx=(10, 0))

        # ── Search bar ────────────────────────────────────────────────────────
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.grid(row=1, column=0, sticky="ew", pady=(0, 2))
        search_frame.grid_columnconfigure(0, weight=1)

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._on_search_change)

        self._search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self._search_var,
            placeholder_text="ابحث باسم الطالب (عربي أو إنكليزي)  —  Search student name...",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            height=32, justify="right",
        )
        self._search_entry.grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(
            search_frame,
            text="بحث\nSearch",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_TINY),
            width=70, height=32, corner_radius=8,
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

        self._suggestion_frame.grid(row=2, column=0, sticky="ew", pady=(0, 2))

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
        card.grid(row=row, column=0, sticky="ew", pady=(0, 10), padx=10)
        card.grid_columnconfigure(0, weight=1)
        row += 1

        # Card header (Distinct background)
        card_hdr = ctk.CTkFrame(card, fg_color=("gray90", "gray20"), corner_radius=12)
        card_hdr.grid(row=0, column=0, sticky="ew")
        card_hdr.grid_columnconfigure(1, weight=1)

        # Action Buttons (Left side)
        btn_row = ctk.CTkFrame(card_hdr, fg_color="transparent")
        btn_row.grid(row=0, column=0, sticky="w", padx=15, pady=4)

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
        ).grid(row=0, column=1, sticky="e", padx=20, pady=4)

        # ── Info Fields Grid (2 Columns) ──────────────────────────────────────
        info_container = ctk.CTkFrame(card, fg_color="transparent")
        info_container.grid(row=1, column=0, sticky="ew", padx=15, pady=4)
        # 4 internal columns: [Label L] [Value L] [Label R] [Value R]
        info_container.grid_columnconfigure((0, 1, 2, 3), weight=1)

        avg   = data.get("average")
        grade_ar, grade_en = get_grade(avg) if avg else ("—", "—")

        # Graduation details fallback logic
        grad_date = data.get("graduation_date") or data.get("order_date")
        grad_date_str = str(grad_date) if grad_date else "—"

        grad_sem = data.get("graduation_semester") or data.get("order_graduation_semester")
        if grad_sem == "first":
            sem_display = "الأول / First"
        elif grad_sem == "second":
            sem_display = "الثاني / Second"
        elif grad_sem == "summer":
            sem_display = "الصيفي / Summer"
        elif grad_sem:
            sem_display = str(grad_sem)
        else:
            sem_display = "—"

        seq_num = data.get('sequence_number')
        post_num = data.get('postgraduation_number') or data.get('postgraduation_no')
        seq_str = str(seq_num) if seq_num is not None and str(seq_num).strip().lower() != 'none' else "—"
        post_str = str(post_num) if post_num is not None and str(post_num).strip().lower() != 'none' else "—"
        grad_seq_display = f"{seq_str}  /  {post_str}"

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
            ("المعدل  /  Average",          f"{avg}  ({grade_ar} / {grade_en})" if avg else "—"),
            ("أمر التخرج  /  Graduation Order", data.get("order_number", "—")),
            ("تاريخ التخرج  /  Graduation Date", grad_date_str),
            ("فصل التخرج  /  Graduation Semester", sem_display),
            ("تسلسل وصادر التخرج  /  Grad. Seq & Postgrad No.", grad_seq_display),
        ]

        def draw_field(parent, label, value, row_idx, col_offset):
            # Text Label
            ctk.CTkLabel(
                parent, text=label,
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=11),
                text_color=AppColors.TEXT_MUTED, anchor="e",
            ).grid(row=row_idx, column=col_offset, sticky="e", padx=(10, 15), pady=3)
            
            # Data Value Box (Badge styling)
            val_box = ctk.CTkFrame(parent, fg_color=("gray90", "gray20"), corner_radius=6)
            val_box.grid(row=row_idx, column=col_offset + 1, sticky="we", padx=(0, 20), pady=3)
            ctk.CTkLabel(
                val_box, text=str(value) if value else "—",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=12, weight="bold"),
                anchor="w",
            ).pack(fill="x", padx=12, pady=3)

        # Distribute fields across 2 columns (RTL logical flow)
        for idx, (lbl, val) in enumerate(fields):
            r_idx = idx // 2
            # Start filling from the right side to respect Arabic reading direction
            c_offset = 2 if idx % 2 == 0 else 0 
            draw_field(info_container, lbl, val, r_idx, c_offset)

        # ── Academic Periods ──────────────────────────────────────────────────
        ctk.CTkLabel(
            frame,
            text="السجل الأكاديمي والدرجات  —  Academic Record & Grades",
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
        year_placeholder = "السنة الدراسية  2024" if ss_id == 1 else "السنة الدراسية  2024-2025"
        
        if ss_id == 1:
            self._new_stage = ctk.CTkOptionMenu(
                add_period_frame,
                values=["1", "2", "3", "4", "5", "6"],
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                width=200, height=34,
            )
            self._new_stage.set("1")
        else:
            self._new_stage = ctk.CTkOptionMenu(
                add_period_frame,
                values=["Semester 1", "Semester 2", "Summer Semester"],
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                width=200, height=34,
            )
            self._new_stage.set("Semester 1")
            
        self._new_stage.grid(row=0, column=0, sticky="w")

        self._new_year = ctk.CTkEntry(
            add_period_frame,
            placeholder_text=year_placeholder,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=160, height=34, justify="center",
        )
        self._new_year.grid(row=0, column=1, padx=6, sticky="w")

        ctk.CTkButton(
            add_period_frame,
            text="+ إضافة سنة دراسية  /  Add Academic Year",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            height=34, corner_radius=8,
            command=self._add_period,
        ).grid(row=0, column=2)

        # Period cards
        periods = AcademicPeriodRepository().get_by_student(data["id"])
        if not periods:
            ctk.CTkLabel(
                frame,
                text="لا توجد فترات دراسية مسجلة بعد.\nNo academic periods recorded yet.",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                text_color=AppColors.TEXT_MUTED, justify="center",
            ).grid(row=row, column=0, pady=20)
            row += 1
        else:
            # Pre-process the incoming rows into a flat, chronologically sequenced dictionary map using academic_year as the unique master key
            enrollments_list = []
            for period in periods:
                enrollments = EnrollmentRepository().get_by_period(period["id"])
                norm_year = normalize_year(period["academic_year"])
                for enr in enrollments:
                    enr["semester_num"] = period["semester_num"]
                    enr["academic_year"] = norm_year
                    enr["period"] = period
                    enrollments_list.append(enr)

            distinct_years = sorted(list(set(normalize_year(p["academic_year"]) for p in periods)))
            clean_academic_timeline = {}
            for year in distinct_years:
                clean_academic_timeline[year] = {
                    "sem_1_list": [e for e in enrollments_list if e["academic_year"] == year and e["semester_num"] == 1],
                    "sem_2_list": [e for e in enrollments_list if e["academic_year"] == year and e["semester_num"] == 2],
                    "periods": [p for p in periods if normalize_year(p["academic_year"]) == year]
                }

            for year, timeline_data in clean_academic_timeline.items():
                self._render_academic_year_card(frame, year, timeline_data, data, row)
                row += 1

    def _render_academic_year_card(
        self, parent, academic_year: str, timeline_data: dict, student: dict, row: int
    ) -> None:
        """Render one academic year master card with a two-column split layout for semesters."""
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
            text=f"العام الدراسي  |  Academic Year: {academic_year}",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL, weight="bold"),
            anchor="e",
        ).grid(row=0, column=0, sticky="e", padx=(0, 10), pady=6)

        # Inner Content Frame: two columns
        cols_frame = ctk.CTkFrame(card, fg_color="transparent")
        cols_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        cols_frame.grid_columnconfigure((0, 1), weight=1)

        # Column 1 (Semester 1)
        col1_frame = ctk.CTkFrame(cols_frame, fg_color="transparent")
        col1_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        col1_frame.grid_columnconfigure(0, weight=1)

        # Column 2 (Semester 2)
        col2_frame = ctk.CTkFrame(cols_frame, fg_color="transparent")
        col2_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        col2_frame.grid_columnconfigure(0, weight=1)

        is_annual = (student.get("study_system_id") == 1)
        sem1_header_text = "الفصل الأول / Term 1" if is_annual else "الفصل الأول / Semester 1"
        sem2_header_text = "الفصل الثاني / Term 2" if is_annual else "الفصل الثاني / Semester 2"

        # -- Render Semester 1 Header --
        h1_frame = ctk.CTkFrame(col1_frame, fg_color=("gray90", "gray20"), corner_radius=6)
        h1_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        h1_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            h1_frame,
            text=sem1_header_text,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL, weight="bold"),
            anchor="e",
        ).grid(row=0, column=0, sticky="e", padx=10, pady=6)

        # Find period for sem 1
        p_sem1 = next((p for p in timeline_data["periods"] if p["semester_num"] == 1), None)
        if p_sem1:
            pb1 = ctk.CTkFrame(h1_frame, fg_color="transparent")
            pb1.grid(row=0, column=0, sticky="w", padx=6, pady=4)

            ctk.CTkButton(
                pb1, text="📝 الدرجات\nGrades",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=9),
                width=70, height=28, corner_radius=6,
                command=lambda p=p_sem1, s=student: self._enroll_panel.open(p, s),
            ).pack(side="left", padx=(0, 3))

            ctk.CTkButton(
                pb1, text="🗑 حذف\nDelete",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=9),
                width=60, height=28, corner_radius=6,
                fg_color=AppColors.COLOR_ERROR, hover_color="#B71C1C",
                command=lambda p=p_sem1: self._delete_period(p),
            ).pack(side="left")

        # -- Render Semester 2 Header --
        h2_frame = ctk.CTkFrame(col2_frame, fg_color=("gray90", "gray20"), corner_radius=6)
        h2_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        h2_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            h2_frame,
            text=sem2_header_text,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL, weight="bold"),
            anchor="e",
        ).grid(row=0, column=0, sticky="e", padx=10, pady=6)

        # Find period for sem 2
        p_sem2 = next((p for p in timeline_data["periods"] if p["semester_num"] == 2), None)
        if p_sem2:
            pb2 = ctk.CTkFrame(h2_frame, fg_color="transparent")
            pb2.grid(row=0, column=0, sticky="w", padx=6, pady=4)

            ctk.CTkButton(
                pb2, text="📝 الدرجات\nGrades",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=9),
                width=70, height=28, corner_radius=6,
                command=lambda p=p_sem2, s=student: self._enroll_panel.open(p, s),
            ).pack(side="left", padx=(0, 3))

            ctk.CTkButton(
                pb2, text="🗑 حذف\nDelete",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=9),
                width=60, height=28, corner_radius=6,
                fg_color=AppColors.COLOR_ERROR, hover_color="#B71C1C",
                command=lambda p=p_sem2: self._delete_period(p),
            ).pack(side="left")

        # -- Render Enrollments Semester 1 --
        sem1_list = timeline_data["sem_1_list"]
        if sem1_list:
            for idx, enr in enumerate(sem1_list):
                if enr['score'] is not None:
                    raw_score = float(enr['score'])
                    display_score = f"{int(raw_score)}" if raw_score.is_integer() else f"{raw_score:.1f}"
                else:
                    display_score = "—"
                lbl_text = f"{enr['course_name_ar']} : {display_score}"
                lbl = ctk.CTkLabel(
                    col1_frame,
                    text=lbl_text,
                    font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                    anchor="e",
                )
                lbl.grid(row=idx + 1, column=0, sticky="e", padx=10, pady=2)
        else:
            ctk.CTkLabel(
                col1_frame,
                text="لا توجد مواد  /  No courses",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                text_color=AppColors.TEXT_MUTED,
                anchor="center",
            ).grid(row=1, column=0, pady=10)

        # -- Render Enrollments Semester 2 --
        sem2_list = timeline_data["sem_2_list"]
        if sem2_list:
            for idx, enr in enumerate(sem2_list):
                if enr['score'] is not None:
                    raw_score = float(enr['score'])
                    display_score = f"{int(raw_score)}" if raw_score.is_integer() else f"{raw_score:.1f}"
                else:
                    display_score = "—"
                lbl_text = f"{enr['course_name_ar']} : {display_score}"
                lbl = ctk.CTkLabel(
                    col2_frame,
                    text=lbl_text,
                    font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                    anchor="e",
                )
                lbl.grid(row=idx + 1, column=0, sticky="e", padx=10, pady=2)
        else:
            ctk.CTkLabel(
                col2_frame,
                text="لا توجد مواد  /  No courses",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                text_color=AppColors.TEXT_MUTED,
                anchor="center",
            ).grid(row=1, column=0, pady=10)

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
        
        import re
        is_valid = bool(re.match(r"^\d{4}$", year_str) or re.match(r"^\d{4}-\d{4}$", year_str))
        if not is_valid:
            self.show_error("السنة الدراسية يجب أن تكون بصيغة YYYY أو YYYY-YYYY\nمثال: 2024 أو 2024-2025")
            return

        # Standardize and format consistently before saving — always normalize
        # to "YYYY-YYYY" so grouping never splits a single academic year.
        db_year = normalize_year(year_str)

        # Calculate calculated_stage based on db_year and admission_year
        try:
            if "-" in db_year:
                year_start = int(db_year.split("-")[0])
            else:
                year_start = int(db_year)
            admission_year = self._selected_student.get("admission_year", year_start)
            if isinstance(admission_year, str) and "-" in admission_year:
                admission_year = int(admission_year.split("-")[0])
            else:
                admission_year = int(admission_year)
            calculated_stage = year_start - admission_year + 1
            calculated_stage = max(1, min(6 if ss_id == 1 else 4, calculated_stage))
        except Exception:
            calculated_stage = 1

        if ss_id == 1:
            stage_val = int(stage_str) if stage_str.isdigit() else 1
            semester_val = 1
        else:
            stage_val = calculated_stage
            if stage_str == "Semester 1":
                semester_val = 1
            elif stage_str == "Semester 2":
                semester_val = 2
            elif stage_str == "Summer Semester":
                semester_val = 3
            else:
                semester_val = 1

        try:
            AcademicPeriodRepository().insert(
                student_id=self._selected_student["id"],
                year=db_year,
                sys_id=ss_id,
                stage=stage_val,
                semester_num=semester_val
            )


            # Clean up inputs
            if isinstance(self._new_stage, ctk.CTkOptionMenu):
                if ss_id == 1:
                    self._new_stage.set("1")
                else:
                    self._new_stage.set("Semester 1")
            else:
                self._new_stage.delete(0, "end")
            self._new_year.delete(0, "end")
            self._reload_detail()
        except Exception as e:
            self.show_error(f"خطأ في إضافة الفترة:\n{e}")

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
