# =============================================================================
# ctk_screens/students_screen.py — Students Management Screen (CustomTkinter)
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
    "بكالوريوس  /  Bachelor": 1,
    "دبلوم عالي  /  Higher Diploma": 2,
    "ماجستير  /  Master": 3,
    "دكتوراه  /  PhD": 4,
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
    "الفصل الصيفي  /  Summer": "summer",
}
SEMESTER_DISPLAY = {v: k for k, v in SEMESTER_OPTIONS.items()}

ROUND_OPTIONS = {
    "الدور الأول  /  First Round":  "first",
    "الدور الثاني  /  Second Round": "second",
}
ROUND_DISPLAY = {v: k for k, v in ROUND_OPTIONS.items()}

GENDER_OPTIONS = {
    "ذكر  /  Male": 1,
    "أنثى  /  Female": 2,
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


from ui.widgets import normalize_date_format as format_to_standard_date


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

    def _build_fields(self) -> None:
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
        self._study_system = self._add_dropdown("نظام الدراسة", "Study System", values=["سنوي  /  Annual", "مقررات  /  Semester"], row=6, col=0)
        self._adm_year = self._add_entry("سنة التخرج", "Graduation Year", placeholder="مثال: 2020", row=6, col=2)
        self._adm_year.bind("<KeyRelease>", self._on_grad_year_change)
        
        self._study_type = self._add_dropdown("نوع الدراسة", "Study Type", values=list(STUDY_TYPE_OPTIONS.keys()), row=8, col=0)
        self._degree_level = self._add_dropdown("الدرجة العلمية", "Degree Level", values=list(DEGREE_LEVEL_OPTIONS.keys()), row=8, col=1)
        self._degree_level.configure(command=self._on_degree_change)
        self._admission_year = self._add_entry("سنة القبول", "Admission Year", placeholder="مثال: 2016", row=8, col=2)
        
        # -- ROW 10: Graduation Section --
        self._add_section_label("التخرج", "Graduation", row=10, col=3)

        self._grad_date = self._add_entry("تاريخ التخرج", "Graduation Date", placeholder="اتركه فارغاً إن لم يتخرج بعد", row=10, col=0, justify="left")
        self._grad_sem = self._add_combobox("فصل التخرج / الدور", "Graduation Semester / Role", values=["— لم يتخرج بعد / Not yet"] + list(SEMESTER_OPTIONS.keys()), row=10, col=1)
        self._average = self._add_entry("المعدل العام", "Overall Average (50–100)", placeholder="مثال: 78", row=10, col=2)

        self._postgraduation_number = self._add_entry("عدد الخريجين", "Postgraduation No.", placeholder="مثال: 86", row=12, col=0)
        self._sequence_number = self._add_entry("رقم التسلسل", "Sequence of Graduation", placeholder="مثال: 1", row=12, col=1)
        self._summer_training = self._add_entry("التدريب الصيفي", "Summer Training", placeholder="مثال: 2019", row=12, col=2)

        self._order = self._add_combobox("الأمر الجامعي", "Graduation Order", values=["— بدون أمر / None"], row=14, col=0, colspan=3)
        self._order.bind("<KeyRelease>", self._filter_orders)

        # -- ROW 16: Thesis Section --
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
        
        self._thesis_frame.grid_remove()

    def _on_degree_change(self, value: str) -> None:
        degree = DEGREE_LEVEL_OPTIONS.get(value, 1)
        if degree in [2, 3, 4, "Higher Diploma", "Master", "PhD"]:
            self._thesis_frame.grid()
        else:
            self._thesis_frame.grid_remove()

    def _on_grad_year_change(self, event=None) -> None:
        grad_yr = self._adm_year.get().strip()
        if grad_yr.isdigit():
            try:
                default_summer = str(int(grad_yr) - 1)
                current_summer = self._summer_training.get().strip()
                if not current_summer or (current_summer.isdigit() and len(current_summer) == 4):
                    self._summer_training.delete(0, "end")
                    self._summer_training.insert(0, default_summer)
            except Exception:
                pass

    def _filter_orders(self, event=None) -> None:
        typed = self._order.get().strip().lower()
        if not typed:
            self._order.configure(values=self._all_order_labels)
        else:
            filtered = [label for label in self._all_order_labels if typed in label.lower()]
            if not filtered:
                filtered = ["— لا توجد نتائج / No results"]
            self._order.configure(values=filtered)

    def _reload_lookups(self) -> None:
        self._depts    = DepartmentRepository().get_all()
        self._govs     = GovernorateRepository().get_all()
        self._countries = CountryRepository().get_all()
        self._orders   = GraduationOrderRepository().get_all()
        self._study_systems = StudySystemRepository().get_active()
        self._personnel = PersonnelRepository().get_active()

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
            f"{o['order_number']}  |  {o.get('dept_name_ar','')}  |  {o.get('graduation_year','') or '—'}"
            for o in self._orders
        ]
        ss_labels = ["سنوي  /  Annual", "مقررات  /  Semester"]

        self._dept.configure(values=dept_labels)
        self._birthplace_gov.configure(values=gov_labels)
        self._nationality.configure(values=nat_labels)
        self._order.configure(values=self._all_order_labels)
        self._order.set(self._all_order_labels[0])
        
        pers_labels = ["—"] + [f"{p['name_ar']}  /  {p['name_en']}" for p in self._personnel]
        self._primary_supervisor.configure(values=pers_labels)
        self._secondary_supervisor.configure(values=pers_labels)
        
        if ss_labels:
            self._study_system.set("سنوي  /  Annual")
        if hasattr(self, '_study_type') and self._study_type:
            self._study_type.set("صباحي  /  Morning")

        iraq_label = next(
            (f"{c['name_ar']}  ({c['iso_code']})" for c in self._countries
             if c["iso_code"] == "IQ"), nat_labels
        )
        self._nationality.set(iraq_label)

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

    def _populate(self, data: dict) -> None:
        self._set_entry(self._name_ar,      data.get("full_name_ar",   ""))
        self._set_entry(self._name_en,      data.get("full_name_en",   ""))
        self._set_entry(self._dob,          data.get("date_of_birth",  ""))
        self._set_entry(self._adm_year,     str(data.get("graduation_year") or ""))
        
        adm_year = data.get("admission_year")
        if not adm_year and data.get("id"):
            try:
                periods = AcademicPeriodRepository().get_by_student(data["id"])
                if periods:
                    earliest_period = sorted(periods, key=lambda p: p.get("academic_year", ""))[0]
                    ay = earliest_period.get("academic_year", "")
                    import re
                    match = re.search(r"\d{4}", ay)
                    if match:
                        adm_year = match.group()
            except Exception as e:
                print(f"Error fetching periods for fallback: {e}")
        self._set_entry(self._admission_year, str(adm_year or ""))
        grad_date = data.get("graduation_date") or data.get("order_date")
        self._set_entry(self._grad_date,    str(grad_date) if grad_date else "")
        self._set_entry(self._average,      str(data.get("average", "") or ""))
        self._set_entry(self._sequence_number, str(data.get("sequence_number", "") or ""))
        post_num = data.get("postgraduation_number") or data.get("postgraduation_no")
        self._set_entry(self._postgraduation_number, str(post_num) if post_num is not None else "")
        self._set_entry(self._summer_training, data.get("summer_training_data") or "")

        gender_val = data.get("gender")
        if gender_val in [1, "1", "M"]:
            self._set_dropdown(self._gender, "ذكر  /  Male")
        elif gender_val in [2, "2", "F"]:
            self._set_dropdown(self._gender, "أنثى  /  Female")
        else:
            self._set_dropdown(self._gender, GENDER_DISPLAY.get(gender_val, list(GENDER_OPTIONS.keys())[0]))

        for d in self._depts:
            if d["id"] == data.get("department_id"):
                self._set_dropdown(self._dept, f"{d['name_ar']}  /  {d['name_en']}")
                break

        for c in self._countries:
            if c["id"] == data.get("nationality_id"):
                self._set_dropdown(self._nationality, f"{c['name_ar']}  ({c['iso_code']})")
                break

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

        degree_val = data.get("degree_level")
        if degree_val in [1, "1", "Bachelor"]:
            self._set_dropdown(self._degree_level, "بكالوريوس  /  Bachelor")
        elif degree_val in [2, "2", "Higher Diploma"]:
            self._set_dropdown(self._degree_level, "دبلوم عالي  /  Higher Diploma")
        elif degree_val in [3, "3", "Master"]:
            self._set_dropdown(self._degree_level, "ماجستير  /  Master")
        elif degree_val in [4, "4", "PhD"]:
            self._set_dropdown(self._degree_level, "دكتوراه  /  PhD")
        else:
            self._set_dropdown(self._degree_level, DEGREE_LEVEL_DISPLAY.get(degree_val, list(DEGREE_LEVEL_OPTIONS.keys())[-1]))

        grad_sem = data.get("graduation_semester") or data.get("order_graduation_semester")
        if grad_sem:
            val = SEMESTER_DISPLAY.get(grad_sem, grad_sem)
            self._grad_sem.set(val)
        else:
            self._grad_sem.set("— لم يتخرج بعد / Not yet")

        sys_id = data.get("study_system_id")
        try:
            sys_id = int(sys_id) if sys_id is not None else None
        except (ValueError, TypeError):
            sys_id = None

        if sys_id == 1:
            self._set_dropdown(self._study_system, "سنوي  /  Annual")
            self._set_dropdown(self._study_type, "صباحي  /  Morning")
        elif sys_id == 2:
            self._set_dropdown(self._study_system, "مقررات  /  Semester")
            self._set_dropdown(self._study_type, "صباحي  /  Morning")
        elif sys_id == 3:
            self._set_dropdown(self._study_system, "سنوي  /  Annual")
            self._set_dropdown(self._study_type, "مسائي  /  Evening")
        elif sys_id == 4:
            self._set_dropdown(self._study_system, "مقررات  /  Semester")
            self._set_dropdown(self._study_type, "مسائي  /  Evening")
        else:
            self._set_dropdown(self._study_system, "سنوي  /  Annual")
            self._set_dropdown(self._study_type, "صباحي  /  Morning")

        if data.get("order_id"):
            for o in self._orders:
                if o["id"] == data["order_id"]:
                    lbl = (f"{o['order_number']}  |  "
                           f"{o.get('dept_name_ar','')}  |  {o.get('graduation_year','') or '—'}")
                    self._set_dropdown(self._order, lbl)
                    break

        deg_lvl = data.get("degree_level")
        deg_disp = "بكالوريوس  /  Bachelor"
        if deg_lvl in [2, "Higher Diploma"]:
            deg_disp = "دبلوم عالي  /  Higher Diploma"
        elif deg_lvl in [3, "Master"]:
            deg_disp = "ماجستير  /  Master"
        elif deg_lvl in [4, "PhD"]:
            deg_disp = "دكتوراه  /  PhD"
        self._on_degree_change(deg_disp)
        if deg_lvl in [2, 3, 4, "Higher Diploma", "Master", "PhD"]:
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

    def _validate(self) -> str | None:
        dob_raw = self._dob.get().strip()
        if dob_raw:
            dob_norm = format_to_standard_date(dob_raw)
            if dob_norm != dob_raw:
                self._dob.delete(0, "end")
                self._dob.insert(0, dob_norm)
                dob_raw = dob_norm

        grad_raw = self._grad_date.get().strip()
        if grad_raw:
            grad_norm = format_to_standard_date(grad_raw)
            if grad_norm != grad_raw:
                self._grad_date.delete(0, "end")
                self._grad_date.insert(0, grad_norm)
                grad_raw = grad_norm

        thesis_raw = self._thesis_defense_date.get().strip()
        if thesis_raw:
            thesis_norm = format_to_standard_date(thesis_raw)
            if thesis_norm != thesis_raw:
                self._thesis_defense_date.delete(0, "end")
                self._thesis_defense_date.insert(0, thesis_norm)
                thesis_raw = thesis_norm

        if not self._name_ar.get().strip():
            return "الاسم بالعربية مطلوب  —  Arabic name is required"
        if not self._name_en.get().strip():
            return "الاسم بالإنكليزية مطلوب  —  English name is required"
        if not dob_raw or len(dob_raw) != 10:
            return "تاريخ الميلاد مطلوب بصيغة YYYY-MM-DD"
        if grad_raw and len(grad_raw) != 10:
            return "تاريخ التخرج يجب أن يكون بصيغة YYYY-MM-DD"
        if thesis_raw and len(thesis_raw) != 10:
            return "تاريخ المناقشة يجب أن يكون بصيغة YYYY-MM-DD"

        grad_yr = self._adm_year.get().strip()
        if grad_yr and not grad_yr.isdigit():
            return "سنة التخرج يجب أن تكون رقماً  —  Graduation year must be a number"

        adm_yr = self._admission_year.get().strip()
        if adm_yr and not adm_yr.isdigit():
            return "سنة القبول يجب أن تكون رقماً  —  Admission year must be a number"
        if not self._depts:
            return "يجب إضافة قسم أولاً  —  Add a department first"

        avg = self._average.get().strip()
        if avg:
            try:
                avg_float = float(avg)
                if not (50.0 <= avg_float <= 100.0):
                    return "المعدل يجب أن يكون بين 50 و100  —  Average must be 50–100"
            except ValueError:
                return "المعدل يجب أن يكون رقماً  —  Average must be a number"

        is_foreign = "أجنبي" in self._birthplace_gov.get()
        foreign_txt = self._birthplace_other.get().strip()
        if is_foreign and not foreign_txt:
            return "يرجى إدخال محل الولادة للطالب الأجنبي"
        return None

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
                   f"{o.get('dept_name_ar','')}  |  {o.get('graduation_year','') or '—'}")
            if lbl == label or o['order_number'] in label:
                return o["id"]
        return None

    def _get_study_system_id(self) -> int:
        system = self._study_system.get()
        study_type = self._study_type.get()
        
        is_semester = "Semester" in system or "مقررات" in system
        is_evening = "Evening" in study_type or "مسائي" in study_type
        
        if not is_semester and not is_evening:
            return 1
        elif is_semester and not is_evening:
            return 2
        elif not is_semester and is_evening:
            return 3
        else:
            return 4

    def _on_save(self, existing: dict | None) -> None:
        bp_id, bp_other = self._get_birthplace()
        avg_raw = self._average.get().strip()
        avg_val = None
        if avg_raw:
            try:
                avg_val = float(avg_raw)
            except ValueError:
                pass
        
        seq_raw = self._sequence_number.get().strip()
        seq_val = int(seq_raw) if seq_raw.isdigit() else None

        post_raw = self._postgraduation_number.get().strip()
        post_val = int(post_raw) if post_raw.isdigit() else None
        
        gender_val = GENDER_OPTIONS[self._gender.get()]

        grad_sem_label = self._grad_sem.get()
        grad_sem = None
        if "لم يتخرج" not in grad_sem_label:
            grad_sem = SEMESTER_OPTIONS.get(grad_sem_label, grad_sem_label)
        grad_date = self._grad_date.get().strip() or None

        grad_yr = self._adm_year.get().strip()
        if not grad_yr and grad_date:
            try:
                import re
                match = re.search(r"\d{4}", grad_date)
                if match:
                    grad_yr = match.group()
            except Exception:
                pass

        if grad_yr and not grad_date:
            grad_date = f"{grad_yr}-07-01"

        summer_training_val = self._summer_training.get().strip() or None
        if not summer_training_val and grad_yr and grad_yr.isdigit():
            try:
                summer_training_val = str(int(grad_yr) - 1)
            except ValueError:
                pass
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
                    "postgraduation_number": post_val,
                    "date_of_birth": self._dob.get().strip(),
                    "birthplace_id": bp_id,
                    "birthplace_other": bp_other,
                    "nationality_id": self._get_nationality_id(),
                    "department_id": self._get_dept_id(),
                    "study_system_id": self._get_study_system_id(),
                    "admission_year": self._admission_year.get().strip(),
                    "study_type": STUDY_TYPE_OPTIONS[self._study_type.get()],
                    "degree_level": DEGREE_LEVEL_OPTIONS[self._degree_level.get()],
                    "graduation_date": grad_date,
                    "graduation_semester": grad_sem,
                    "average": avg_val,
                    "order_id": order_id,
                    "summer_training_data": summer_training_val,
                }
            )
        else:
            student_id = StudentRepository().insert(
                {
                    "full_name_ar": self._name_ar.get().strip(),
                    "full_name_en": self._name_en.get().strip(),
                    "gender": gender_val,
                    "sequence_number": seq_val,
                    "postgraduation_number": post_val,
                    "date_of_birth": self._dob.get().strip(),
                    "birthplace_id": bp_id,
                    "birthplace_other": bp_other,
                    "nationality_id": self._get_nationality_id(),
                    "department_id": self._get_dept_id(),
                    "study_system_id": self._get_study_system_id(),
                    "admission_year": self._admission_year.get().strip(),
                    "study_type": STUDY_TYPE_OPTIONS[self._study_type.get()],
                    "degree_level": DEGREE_LEVEL_OPTIONS[self._degree_level.get()],
                    "graduation_date": grad_date,
                    "graduation_semester": grad_sem,
                    "average": avg_val,
                    "order_id": order_id,
                    "summer_training_data": summer_training_val,
                }
            )
            
        degree = DEGREE_LEVEL_OPTIONS[self._degree_level.get()]
        if degree in [2, 3, 4, "Higher Diploma", "Master", "PhD"]:
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

        self._list_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._list_scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=4)
        self._list_scroll.grid_columnconfigure(0, weight=1)

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
        self._course_search_entry.bind("<FocusIn>", lambda e: self._course_list_frame.grid(row=2, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 4)))
        self._course_search_entry.bind("<Escape>", lambda e: self._course_list_frame.grid_remove())

        self._score_entry = ctk.CTkEntry(
            add_frame,
            placeholder_text="الدرجة  0-100",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
            width=70, height=30, justify="center",
        )
        self._score_entry.grid(row=1, column=1, padx=(0, 4), pady=4)

        self._round_option = ctk.CTkOptionMenu(
            add_frame,
            values=["1", "2", "3"],
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
            width=60, height=30,
        )
        self._round_option.set("1")
        self._round_option.grid(row=1, column=2, padx=(0, 4), pady=4)

        ctk.CTkButton(
            add_frame, text="إضافة\nAdd", width=60, height=30,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=9),
            corner_radius=6,
            command=self._add_enrollment,
        ).grid(row=1, column=3, padx=(0, 10), pady=4)

        self._course_list_frame = ctk.CTkScrollableFrame(
            add_frame, height=120, fg_color=("gray95", "gray18")
        )

        self._add_error = ctk.CTkLabel(
            add_frame, text="",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
            text_color=AppColors.COLOR_ERROR, anchor="e",
        )
        self._add_error.grid(row=4, column=0, columnspan=3, sticky="e", padx=10, pady=(0, 6))

    def open(self, period: dict, student: dict) -> None:
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
        for child in getattr(self, "_hidden_siblings", []):
            child.grid()
        self._hidden_siblings = []
        self._on_close()

    def _show(self) -> None:
        self._hidden_siblings = []
        for child in self._parent.winfo_children():
            if child is self:
                continue
            if child.winfo_ismapped():
                child.grid_remove()
                self._hidden_siblings.append(child)
        
        self.grid(row=0, column=0, sticky="nsew", rowspan=20)
        self.tkraise()

    def _reload_course_picker(self) -> None:
        if not self._period or not self._student:
            return
        
        dept_id = self._student.get("department_id")
        stage = self._period.get("stage_number")
        system_id = self._period.get("study_system_id") or self._student.get("study_system_id") or 1
        
        if dept_id and stage:
            self._courses = CourseRepository().get_by_dept_stage_system(
                dept_id=dept_id,
                stage=stage,
                system_id=system_id
            )
        else:
            self._courses = CourseRepository().get_all()

        self._selected_course = None
        self._course_search_entry.delete(0, "end")
        self._course_list_frame.grid_remove()
        self._filter_courses_in_list("")
        self._course_list_frame.grid_remove()

    def _on_course_search_key(self, event=None) -> None:
        query = self._course_search_entry.get().strip().lower()
        self._filter_courses_in_list(query)

    def _filter_courses_in_list(self, query: str = "") -> None:
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

            name = enr.get("course_name_ar", "")
            ctk.CTkLabel(
                row_f, text=name[:24] + ("…" if len(name) > 24 else ""),
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
                width=160, anchor="e",
            ).grid(row=0, column=0, padx=4, pady=4)

            if enr["score"] is not None:
                raw_score = float(enr['score'])
                display_score = f"{int(raw_score)}" if raw_score.is_integer() else f"{raw_score:.1f}"
            else:
                display_score = "—"
            score_var = ctk.StringVar(value=display_score)
            score_entry = ctk.CTkEntry(
                row_f, textvariable=score_var,
                width=50, height=26, justify="center",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
            )
            score_entry.grid(row=0, column=1, padx=4, pady=4)

            round_val_str = str(enr.get("passed_round") or "1")
            round_var = ctk.StringVar(value=round_val_str)
            round_menu = ctk.CTkOptionMenu(
                row_f, variable=round_var,
                values=["1", "2", "3"],
                width=50, height=26,
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=10),
            )
            round_menu.grid(row=0, column=2, padx=4, pady=4)

            btn_frame = ctk.CTkFrame(row_f, fg_color="transparent")
            btn_frame.grid(row=0, column=3, padx=4, pady=4)

            ctk.CTkButton(
                btn_frame, text="💾", width=32, height=26,
                font=ctk.CTkFont(size=12), corner_radius=4,
                fg_color=AppColors.COLOR_INFO, hover_color="#1565C0",
                command=lambda e=enr, sv=score_var, rv=round_var: self._save_score(e, sv, rv),
            ).pack(side="left", padx=(0, 2))

            ctk.CTkButton(
                btn_frame, text="🗑", width=32, height=26,
                font=ctk.CTkFont(size=12), corner_radius=4,
                fg_color=AppColors.COLOR_ERROR, hover_color="#B71C1C",
                command=lambda e=enr: self._delete_enrollment(e),
            ).pack(side="left")

    def _add_enrollment(self) -> None:
        self._add_error.configure(text="")
        from ui.widgets import show_modern_alert

        if not getattr(self, "_period", None):
            msg = "لا توجد فترة أكاديمية محددة\nNo academic period selected"
            self._add_error.configure(text=f"⚠️  {msg}")
            show_modern_alert(self, msg)
            return

        if not getattr(self, "_selected_course", None) or not self._courses:
            msg = "الرجاء اختيار مادة من القائمة\nPlease select a course from the list"
            self._add_error.configure(text=f"⚠️  {msg}")
            show_modern_alert(self, msg)
            return

        score_str = self._score_entry.get().strip()
        try:
            score = float(score_str)
            if not (0 <= score <= 100):
                raise ValueError
        except ValueError:
            msg = "الدرجة يجب أن تكون بين 0 و100\nScore must be between 0 and 100"
            self._add_error.configure(text=f"⚠️  {msg}")
            show_modern_alert(self, msg)
            return

        course_id = self._selected_course["id"]
        round_val = int(self._round_option.get())

        try:
            periods = []
            student = getattr(self, "_student", None)
            if student:
                student_id = student["id"]
                periods = AcademicPeriodRepository().get_by_student(student_id)
            
            course_already_taken = False
            for p in periods:
                enrollments = EnrollmentRepository().get_by_period(p["id"])
                for enr in enrollments:
                    if enr["course_id"] == course_id:
                        course_already_taken = True
                        if enr.get("score") is not None and float(enr["score"]) >= 50.0:
                            msg = "هذا الطالب قد نجح في هذه المادة سابقاً!\nThis student has already passed this course!"
                            self._add_error.configure(text=f"⚠️  {msg}")
                            show_modern_alert(self, msg)
                            return
            
            if course_already_taken and round_val == 1:
                msg = "لا يمكن اختيار الدور الأول لمادة معادة!\nCannot select Round 1 for a repeated course! Must be 2 or 3."
                self._add_error.configure(text=f"⚠️  {msg}")
                show_modern_alert(self, msg)
                return

        except Exception as e:
            print(f"Error checking duplicate courses: {e}")

        try:
            EnrollmentRepository().insert(
                period_id=self._period["id"],
                course_id=course_id,
                score=score,
                is_second=round_val,
            )
            self._score_entry.delete(0, "end")
            self._selected_course = None
            self._course_search_entry.delete(0, "end")
            self._course_list_frame.grid_remove()
            self._reload_list()
        except Exception as e:
            self._add_error.configure(text=f"⚠️  {e}")
            show_modern_alert(self, f"⚠️  {e}")

    def _save_score(self, enr: dict, score_var: ctk.StringVar, round_var: ctk.StringVar) -> None:
        from ui.widgets import show_modern_alert
        try:
            score_val = float(score_var.get().strip())
            if not (0 <= score_val <= 100):
                raise ValueError
            round_val = int(round_var.get())
            EnrollmentRepository().update(enr["id"], score_val, round_val)
            score_var.set(format_score(score_val))
            self._reload_list()
        except ValueError:
            show_modern_alert(self, "الدرجة يجب أن تكون بين 0 و100\nScore must be between 0 and 100")

    def _delete_enrollment(self, enr: dict) -> None:
        EnrollmentRepository().delete(enr["id"])
        self._reload_list()


# =============================================================================
# MAIN STUDENTS SCREEN
# =============================================================================

class StudentsScreen(BaseScreen):
    """
    Students management screen (CustomTkinter).
    """

    def __init__(self, parent, switch_callback) -> None:
        self._selected_student: dict | None = None
        self._search_timer = None
        super().__init__(parent, switch_callback)

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure((0, 1, 2), weight=0)
        self.grid_rowconfigure(3, weight=1)

        self._form_panel = StudentFormPanel(
            self, on_save_callback=self._after_save
        )
        self._academic_panel = AcademicRecordPanel(
            self, on_close=self._reload_detail
        )

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        top.grid_columnconfigure(0, weight=1)
        make_section_header(top, "الطلاب", "Students").grid(row=0, column=0, sticky="e")
        make_primary_button(
            top, "+ إضافة طالب", "Add Student",
            command=self._open_add,
        ).grid(row=0, column=1, padx=(10, 0))

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

        self._suggestion_frame = ctk.CTkScrollableFrame(
            self, height=400, fg_color=("gray94", "gray18")
        )
        self._suggestion_frame.grid_columnconfigure(0, weight=1)
        
        self._sugg_row_font = ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL)
        
        self._suggestion_pool = []
        for r in range(1, 13):
            btn = ctk.CTkButton(
                self._suggestion_frame,
                text="",
                font=self._sugg_row_font,
                height=36,
                anchor="e",
                fg_color="transparent",
                hover_color=AppColors.NAV_HOVER_BG,
                text_color=AppColors.NAV_TEXT,
                corner_radius=6
            )
            self._suggestion_pool.append(btn)

        self._detail_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent"
        )
        self._detail_frame.grid(row=3, column=0, sticky="nsew")
        self._detail_frame.grid_columnconfigure(0, weight=1)

        self._show_empty_state()

    def refresh(self) -> None:
        if self._selected_student:
            refreshed = StudentRepository().get_by_id(self._selected_student["id"])
            if refreshed:
                self._selected_student = refreshed
                self._show_student_detail(refreshed)

    def _after_save(self) -> None:
        self._search_var.set("")
        self._show_empty_state()
        self._selected_student = None

    def _reload_detail(self) -> None:
        if not self._selected_student:
            return
        data = StudentRepository().get_by_id(self._selected_student["id"])
        if data:
            self._selected_student = data
            self._show_student_detail(data)

    def _on_search_change(self, *_) -> None:
        if self._search_timer is not None:
            self.after_cancel(self._search_timer)
            self._search_timer = None

        query = self._search_var.get().strip()
        if len(query) < 2:
            self._hide_suggestions()
            return

        self._search_timer = self.after(100, lambda: self._execute_search_debounced(query))

    def _execute_search_debounced(self, query: str) -> None:
        self._search_timer = None
        self._show_suggestions_for(query)

    def _do_search(self) -> None:
        query = self._search_var.get().strip()
        if query:
            self._show_suggestions_for(query)

    def _show_suggestions_for(self, query: str) -> None:
        import threading
        
        def fetch_and_rank():
            try:
                candidates = StudentRepository().search(query, limit=30)
                if not candidates:
                    self.after(0, self._hide_suggestions)
                    return
                self.after(0, lambda: self._render_suggestions(candidates[:12]))
            except Exception as e:
                print(f"Async search error: {e}")
                self.after(0, self._hide_suggestions)
                
        threading.Thread(target=fetch_and_rank, daemon=True).start()

    def _render_suggestions(self, students: list[dict]) -> None:
        self._suggestion_frame.grid(row=2, column=0, sticky="ew", pady=(0, 2))

        for btn in self._suggestion_pool:
            btn.grid_remove()

        for i, s in enumerate(students):
            btn = self._suggestion_pool[i]
            
            ar_name = s.get("full_name_ar") or ""
            en_name = s.get("full_name_en") or ""
            dept = s.get("dept_name_ar") or ""
            avg = s.get("average") or ""
            
            label_text = f"\u200F{dept} (المعدل: {avg}) |  {en_name}  | {ar_name} \u200F"
            
            sid = s["id"]
            btn.configure(text=label_text, command=lambda current_id=sid: self._select_student(current_id))
            
            btn.grid(row=i + 1, column=0, sticky="ew", padx=4, pady=2)

    def _hide_suggestions(self) -> None:
        self._suggestion_frame.grid_remove()

    def _select_student(self, student_id: int) -> None:
        self._hide_suggestions()
        self._search_var.set("")
        data = StudentRepository().get_by_id(student_id)
        if data:
            self._selected_student = data
            self._show_student_detail(data)
            self._form_panel.close()
            self._academic_panel.close()

    def _show_empty_state(self) -> None:
        for w in self._detail_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._detail_frame,
            text="🔍\n\nابحث عن طالب للبدء\nSearch for a student to begin",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            text_color=AppColors.TEXT_MUTED, justify="center",
        ).place(relx=0.5, rely=0.4, anchor="center")

    def _show_student_detail(self, data: dict) -> None:
        for w in self._detail_frame.winfo_children():
            w.destroy()

        frame = self._detail_frame
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        row = 0

        card = ctk.CTkFrame(frame, corner_radius=12, border_width=1,
                            border_color=AppColors.BORDER, fg_color=("gray98", "gray14"))
        card.grid(row=row, column=0, sticky="nsew", pady=(0, 10), padx=10)
        card.grid_columnconfigure(0, weight=1)
        row += 1

        card_hdr = ctk.CTkFrame(card, fg_color=("gray90", "gray20"), corner_radius=12)
        card_hdr.grid(row=0, column=0, sticky="ew")
        card_hdr.grid_columnconfigure(1, weight=1)

        btn_row = ctk.CTkFrame(card_hdr, fg_color="transparent")
        btn_row.grid(row=0, column=0, sticky="w", padx=15, pady=4)

        ctk.CTkButton(
            btn_row, text="تعديل  /  Edit", height=32, width=100,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=12),
            corner_radius=6,
            command=lambda: self._form_panel.open_edit(self._selected_student),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="السجل الأكاديمي  /  Academic Record", height=32,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=12),
            corner_radius=6,
            command=lambda: self._academic_panel.open(self._selected_student),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="حذف  /  Delete", height=32, width=100,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=12),
            corner_radius=6, fg_color=AppColors.COLOR_ERROR, hover_color="#B71C1C",
            command=self._confirm_delete,
        ).pack(side="left")

        ctk.CTkLabel(
            card_hdr,
            text=f"{data['full_name_ar']}  —  {data['full_name_en']}",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SUBHEADING, weight="bold"),
            anchor="e",
        ).grid(row=0, column=1, sticky="e", padx=20, pady=4)

        info_container = ctk.CTkFrame(card, fg_color="transparent")
        info_container.grid(row=1, column=0, sticky="ew", padx=15, pady=4)
        info_container.grid_columnconfigure((0, 1, 2, 3), weight=1)

        avg   = data.get("average")
        grade_ar, grade_en = get_grade(avg) if avg else ("—", "—")

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
            ("سنة القبول  /  Admission Year",  data.get("admission_year") or "—"),
            ("سنة التخرج  /  Graduation Year", data.get("graduation_year") or "—"),
            ("تاريخ الميلاد  /  Date of Birth", data.get("date_of_birth", "—")),
            ("الجنسية  /  Nationality",      data.get("nationality_ar", "—")),
            ("محل الولادة  /  Birthplace",
                data.get("birthplace_ar") or data.get("birthplace_other", "—")),
            ("نوع الدراسة  /  Study Type",
                "صباحي / Morning" if str(data.get("study_type") or "").strip().lower() == "morning" else "مسائي / Evening"),
            ("المعدل  /  Average",          f"{avg}  ({grade_ar} / {grade_en})" if avg else "—"),
            ("أمر التخرج  /  Graduation Order", data.get("order_number", "—")),
            ("تاريخ التخرج  /  Graduation Date", grad_date_str),
            ("فصل التخرج  /  Graduation Semester", sem_display),
            ("تسلسل وصادر التخرج  /  Grad. Seq & Postgrad No.", grad_seq_display),
            ("التدريب الصيفي  /  Summer Training", data.get("summer_training_data") or "—"),
        ]

        def draw_field(parent, label, value, row_idx, col_offset):
            ctk.CTkLabel(
                parent, text=label,
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=11),
                text_color=AppColors.TEXT_MUTED, anchor="e",
            ).grid(row=row_idx, column=col_offset, sticky="e", padx=(10, 15), pady=3)
            
            val_box = ctk.CTkFrame(parent, fg_color=("gray90", "gray20"), corner_radius=6)
            val_box.grid(row=row_idx, column=col_offset + 1, sticky="we", padx=(0, 20), pady=3)
            ctk.CTkLabel(
                val_box, text=str(value) if value else "—",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=12, weight="bold"),
                anchor="w",
            ).pack(fill="x", padx=12, pady=3)

        for idx, (lbl, val) in enumerate(fields):
            r_idx = idx // 2
            c_offset = 2 if idx % 2 == 0 else 0 
            draw_field(info_container, lbl, val, r_idx, c_offset)

    def _open_add(self) -> None:
        self._academic_panel.close()
        self._form_panel.open_add()

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


# =============================================================================
# ACADEMIC RECORD PANEL
# =============================================================================

class AcademicRecordPanel(ctk.CTkFrame):
    """
    Full-screen overlay panel showing student's academic record, grades,
    thesis details, and supervisors.
    """

    def __init__(self, parent_screen: ctk.CTkFrame, on_close) -> None:
        super().__init__(
            parent_screen,
            corner_radius=0,
            fg_color="transparent",
        )
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._parent = parent_screen
        self._on_close = on_close
        self._student: dict | None = None
        self._hidden_siblings: list = []

        self._build()

    def _build(self) -> None:
        header = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color=AppColors.HEADER_BG)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        header.grid_propagate(False)

        ctk.CTkButton(
            header, text="←  رجوع  /  Back",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
            width=130, height=36, corner_radius=AppSizes.CORNER_RADIUS_BTN,
            fg_color="transparent", hover_color=AppColors.NAV_HOVER_BG,
            text_color=AppColors.NAV_TEXT, anchor="w",
            command=self.close,
        ).grid(row=0, column=0, padx=8, pady=8, sticky="w")

        self._title_lbl = ctk.CTkLabel(
            header, text="",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY, weight="bold"),
            anchor="e",
        )
        self._title_lbl.grid(row=0, column=1, sticky="e", padx=(0, 14), pady=12)

        self.scroll_area = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_area.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        self.scroll_area.grid_columnconfigure(0, weight=1)

        self._enroll_panel = EnrollmentPanel(self, on_close=self.load_data)

    def open(self, student: dict) -> None:
        self._student = student
        if self._student:
            self._title_lbl.configure(
                text=f"السجل الأكاديمي  —  {student.get('full_name_ar', '')}"
            )
        self.load_data()
        self._show()

    def close(self) -> None:
        if not self.winfo_ismapped():
            return
        self._enroll_panel.close()
        self.grid_remove()
        for child in self._hidden_siblings:
            if child.winfo_exists():
                child.grid()
        self._hidden_siblings = []
        self._on_close()

    def _show(self) -> None:
        self._hidden_siblings = []
        for child in self._parent.winfo_children():
            if child is self:
                continue
            if child.winfo_ismapped():
                child.grid_remove()
                self._hidden_siblings.append(child)

        self._parent.grid_columnconfigure(0, weight=1)
        self.grid(row=0, column=0, sticky="nsew", rowspan=20)

    def load_data(self) -> None:
        if not self._student:
            return

        for w in self.scroll_area.winfo_children():
            if w is not self._enroll_panel:
                w.destroy()

        frame = self.scroll_area
        row = 0

        ss_id = self._student.get("study_system_id", 1)
        year_placeholder = "السنة الدراسية  2024" if ss_id in [1, 3] else "السنة الدراسية  2024-2025"

        add_period_frame = ctk.CTkFrame(frame, fg_color="transparent")
        add_period_frame.grid(row=row, column=0, sticky="ew", pady=(10, 10))
        add_period_frame.grid_columnconfigure(0, weight=1)
        row += 1

        self._new_year = ctk.CTkEntry(
            add_period_frame,
            placeholder_text=year_placeholder,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            width=200, height=34, justify="center",
        )
        self._new_year.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            add_period_frame,
            text="+ إضافة سنة دراسية  /  Add Academic Year",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            height=34, corner_radius=8,
            command=self._add_period,
        ).grid(row=0, column=1, padx=8, sticky="w")

        periods = AcademicPeriodRepository().get_by_student(self._student["id"])
        if not periods:
            ctk.CTkLabel(
                frame,
                text="لا توجد فترات دراسية مسجلة بعد.\nNo academic periods recorded yet.",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
                text_color=AppColors.TEXT_MUTED, justify="center",
            ).grid(row=row, column=0, pady=20)
            row += 1
        else:
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
                    "sem_3_list": [e for e in enrollments_list if e["academic_year"] == year and e["semester_num"] == 3],
                    "periods": [p for p in periods if normalize_year(p["academic_year"]) == year]
                }

            for year, timeline_data in clean_academic_timeline.items():
                self._render_academic_year_card(frame, year, timeline_data, self._student, row)
                row += 1

        degree = self._student.get("degree_level", 1)
        if degree in [2, 3, 4, "Higher Diploma", "Master", "PhD"]:
            self._render_thesis_and_supervisors(frame, row)
            row += 1

    def _render_academic_year_card(
        self, parent, academic_year: str, timeline_data: dict, student: dict, row: int
    ) -> None:
        card = ctk.CTkFrame(
            parent, corner_radius=8, border_width=1, border_color=AppColors.BORDER
        )
        card.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)

        p_hdr = ctk.CTkFrame(card, fg_color=("gray88", "gray22"), corner_radius=0)
        p_hdr.grid(row=0, column=0, sticky="ew")
        p_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            p_hdr,
            text=f"العام الدراسي  |  Academic Year: {academic_year}",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL, weight="bold"),
            anchor="e",
        ).grid(row=0, column=0, sticky="e", padx=(0, 10), pady=6)

        cols_frame = ctk.CTkFrame(card, fg_color="transparent")
        cols_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        cols_frame.grid_columnconfigure((0, 1, 2), weight=1)

        col1_frame = ctk.CTkFrame(cols_frame, fg_color="transparent")
        col1_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        col1_frame.grid_columnconfigure(0, weight=1)

        col2_frame = ctk.CTkFrame(cols_frame, fg_color="transparent")
        col2_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        col2_frame.grid_columnconfigure(0, weight=1)

        col3_frame = ctk.CTkFrame(cols_frame, fg_color="transparent")
        col3_frame.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)
        col3_frame.grid_columnconfigure(0, weight=1)

        is_annual = (student.get("study_system_id") in [1, 3])
        sem1_hdr = "الفصل الأول / Term 1" if is_annual else "الفصل الأول / Semester 1"
        sem2_hdr = "الفصل الثاني / Term 2" if is_annual else "الفصل الثاني / Semester 2"
        sem3_hdr = "الفصل الصيفي / Summer Term" if is_annual else "الفصل الصيفي / Summer Semester"

        h1 = ctk.CTkFrame(col1_frame, fg_color=("gray90", "gray20"), corner_radius=6)
        h1.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        h1.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(h1, text=sem1_hdr, font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL, weight="bold"), anchor="e").grid(row=0, column=0, sticky="e", padx=10, pady=6)
        
        p_sem1 = next((p for p in timeline_data["periods"] if p["semester_num"] == 1), None)
        pb1 = ctk.CTkFrame(h1, fg_color="transparent")
        pb1.grid(row=0, column=0, sticky="w", padx=6, pady=4)
        if p_sem1:
            ctk.CTkButton(pb1, text="📝 الدرجات\nGrades", font=ctk.CTkFont(family=AppFonts.FAMILY, size=9), width=70, height=28, corner_radius=6, command=lambda p=p_sem1, s=student: self._enroll_panel.open(p, s)).pack(side="left", padx=(0, 3))
            ctk.CTkButton(pb1, text="🗑 حذف\nDelete", font=ctk.CTkFont(family=AppFonts.FAMILY, size=9), width=60, height=28, corner_radius=6, fg_color=AppColors.COLOR_ERROR, hover_color="#B71C1C", command=lambda p=p_sem1: self._delete_period(p)).pack(side="left")
        else:
            ctk.CTkButton(pb1, text="+ إضافة مواد\n+ Add Courses", font=ctk.CTkFont(family=AppFonts.FAMILY, size=9), width=90, height=28, corner_radius=6, command=lambda sem=1, yr=academic_year: self._add_period_and_open(sem, yr)).pack(side="left")

        sem1_list = timeline_data["sem_1_list"]
        if sem1_list:
            for idx, enr in enumerate(sem1_list):
                raw_score = float(enr['score']) if enr.get('score') is not None else None
                display_score = f"{int(raw_score)}" if raw_score is not None and raw_score.is_integer() else (f"{raw_score:.1f}" if raw_score is not None else "—")
                lbl_text = f"{enr['course_name_ar']} : {display_score}"
                ctk.CTkLabel(col1_frame, text=lbl_text, font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL), anchor="e").grid(row=idx + 1, column=0, sticky="e", padx=10, pady=2)
        else:
            ctk.CTkLabel(col1_frame, text="لا توجد مواد  /  No courses", font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL), text_color=AppColors.TEXT_MUTED, anchor="center").grid(row=1, column=0, pady=10)

        h2 = ctk.CTkFrame(col2_frame, fg_color=("gray90", "gray20"), corner_radius=6)
        h2.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        h2.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(h2, text=sem2_hdr, font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL, weight="bold"), anchor="e").grid(row=0, column=0, sticky="e", padx=10, pady=6)

        p_sem2 = next((p for p in timeline_data["periods"] if p["semester_num"] == 2), None)
        pb2 = ctk.CTkFrame(h2, fg_color="transparent")
        pb2.grid(row=0, column=0, sticky="w", padx=6, pady=4)
        if p_sem2:
            ctk.CTkButton(pb2, text="📝 الدرجات\nGrades", font=ctk.CTkFont(family=AppFonts.FAMILY, size=9), width=70, height=28, corner_radius=6, command=lambda p=p_sem2, s=student: self._enroll_panel.open(p, s)).pack(side="left", padx=(0, 3))
            ctk.CTkButton(pb2, text="🗑 حذف\nDelete", font=ctk.CTkFont(family=AppFonts.FAMILY, size=9), width=60, height=28, corner_radius=6, fg_color=AppColors.COLOR_ERROR, hover_color="#B71C1C", command=lambda p=p_sem2: self._delete_period(p)).pack(side="left")
        else:
            ctk.CTkButton(pb2, text="+ إضافة مواد\n+ Add Courses", font=ctk.CTkFont(family=AppFonts.FAMILY, size=9), width=90, height=28, corner_radius=6, command=lambda sem=2, yr=academic_year: self._add_period_and_open(sem, yr)).pack(side="left")

        sem2_list = timeline_data["sem_2_list"]
        if sem2_list:
            for idx, enr in enumerate(sem2_list):
                raw_score = float(enr['score']) if enr.get('score') is not None else None
                display_score = f"{int(raw_score)}" if raw_score is not None and raw_score.is_integer() else (f"{raw_score:.1f}" if raw_score is not None else "—")
                lbl_text = f"{enr['course_name_ar']} : {display_score}"
                ctk.CTkLabel(col2_frame, text=lbl_text, font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL), anchor="e").grid(row=idx + 1, column=0, sticky="e", padx=10, pady=2)
        else:
            ctk.CTkLabel(col2_frame, text="لا توجد مواد  /  No courses", font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL), text_color=AppColors.TEXT_MUTED, anchor="center").grid(row=1, column=0, pady=10)

        h3 = ctk.CTkFrame(col3_frame, fg_color=("gray90", "gray20"), corner_radius=6)
        h3.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        h3.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(h3, text=sem3_hdr, font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL, weight="bold"), anchor="e").grid(row=0, column=0, sticky="e", padx=10, pady=6)

        p_sem3 = next((p for p in timeline_data["periods"] if p["semester_num"] == 3), None)
        pb3 = ctk.CTkFrame(h3, fg_color="transparent")
        pb3.grid(row=0, column=0, sticky="w", padx=6, pady=4)
        if p_sem3:
            ctk.CTkButton(pb3, text="📝 الدرجات\nGrades", font=ctk.CTkFont(family=AppFonts.FAMILY, size=9), width=70, height=28, corner_radius=6, command=lambda p=p_sem3, s=student: self._enroll_panel.open(p, s)).pack(side="left", padx=(0, 3))
            ctk.CTkButton(pb3, text="🗑 حذف\nDelete", font=ctk.CTkFont(family=AppFonts.FAMILY, size=9), width=60, height=28, corner_radius=6, fg_color=AppColors.COLOR_ERROR, hover_color="#B71C1C", command=lambda p=p_sem3: self._delete_period(p)).pack(side="left")
        else:
            ctk.CTkButton(pb3, text="+ إضافة مواد\n+ Add Courses", font=ctk.CTkFont(family=AppFonts.FAMILY, size=9), width=90, height=28, corner_radius=6, command=lambda sem=3, yr=academic_year: self._add_period_and_open(sem, yr)).pack(side="left")

        sem3_list = timeline_data["sem_3_list"]
        if sem3_list:
            for idx, enr in enumerate(sem3_list):
                raw_score = float(enr['score']) if enr.get('score') is not None else None
                display_score = f"{int(raw_score)}" if raw_score is not None and raw_score.is_integer() else (f"{raw_score:.1f}" if raw_score is not None else "—")
                lbl_text = f"{enr['course_name_ar']} : {display_score}"
                ctk.CTkLabel(col3_frame, text=lbl_text, font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL), anchor="e").grid(row=idx + 1, column=0, sticky="e", padx=10, pady=2)
        else:
            ctk.CTkLabel(col3_frame, text="لا توجد مواد  /  No courses", font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL), text_color=AppColors.TEXT_MUTED, anchor="center").grid(row=1, column=0, pady=10)

    def _add_period(self) -> None:
        if not self._student:
            return

        year_str  = self._new_year.get().strip()
        ss_id = self._student.get("study_system_id", 1)
        
        import re
        is_valid = bool(re.match(r"^\d{4}$", year_str) or re.match(r"^\d{4}-\d{4}$", year_str))
        if not is_valid:
            from ui.widgets import show_modern_alert
            show_modern_alert(self, "صيغة السنة الدراسية غير صالحة!\nInvalid Academic Year format! Use YYYY or YYYY-YYYY.")
            return

        db_year = normalize_year(year_str)

        try:
            if "-" in db_year:
                year_start = int(db_year.split("-")[0])
            else:
                year_start = int(db_year)
            adm_year = self._student.get("admission_year", year_start)
            if isinstance(adm_year, str) and "-" in adm_year:
                adm_year = int(adm_year.split("-")[0])
            else:
                adm_year = int(adm_year)
            diff = year_start - adm_year
            calculated_stage = max(1, diff + 1)
        except Exception:
            calculated_stage = 1

        try:
            AcademicPeriodRepository().insert(
                student_id=self._student["id"],
                year=db_year,
                sys_id=ss_id,
                stage=calculated_stage,
                semester_num=1,
            )
            self._new_year.delete(0, "end")
            self.load_data()
        except Exception as e:
            print(f"Failed to add period: {e}")

    def _add_period_and_open(self, semester_num: int, year_str: str) -> None:
        if not self._student:
            return
        db_year = normalize_year(year_str)
        ss_id = self._student.get("study_system_id", 1)
        
        try:
            if "-" in db_year:
                year_start = int(db_year.split("-")[0])
            else:
                year_start = int(db_year)
            adm_year = self._student.get("admission_year", year_start)
            if isinstance(adm_year, str) and "-" in adm_year:
                adm_year = int(adm_year.split("-")[0])
            else:
                adm_year = int(adm_year)
            diff = year_start - adm_year
            calculated_stage = max(1, diff + 1)
        except Exception:
            calculated_stage = 1

        try:
            new_period_id = AcademicPeriodRepository().insert(
                student_id=self._student["id"],
                year=db_year,
                sys_id=ss_id,
                stage=calculated_stage,
                semester_num=semester_num,
            )
            self.load_data()
            periods = AcademicPeriodRepository().get_by_student(self._student["id"])
            p_new = next((p for p in periods if p["id"] == new_period_id or (p["semester_num"] == semester_num and normalize_year(p["academic_year"]) == db_year)), None)
            if p_new:
                self._enroll_panel.open(p_new, self._student)
        except Exception as e:
            print(f"Failed to add and open period: {e}")

    def _delete_period(self, period: dict) -> None:
        from tkinter import messagebox
        if messagebox.askyesno("تأكيد الحذف", "هل أنت متأكد من حذف هذه الفترة الدراسية وكل الدرجات المرتبطة بها؟"):
            self._do_delete_period(period)

    def _do_delete_period(self, period: dict) -> None:
        try:
            AcademicPeriodRepository().delete(period["id"])
            self.load_data()
        except Exception as e:
            print(f"Failed to delete period: {e}")

    def _render_thesis_and_supervisors(self, parent, row: int) -> None:
        card = ctk.CTkFrame(parent, corner_radius=8, border_width=1, border_color=AppColors.BORDER)
        card.grid(row=row, column=0, sticky="ew", pady=(10, 8))
        card.grid_columnconfigure(0, weight=1)

        t_hdr = ctk.CTkFrame(card, fg_color=("gray88", "gray22"), corner_radius=0)
        t_hdr.grid(row=0, column=0, sticky="ew")
        t_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            t_hdr, text="بيانات الرسالة والمشرفين  |  Thesis & Supervisors",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL, weight="bold"),
            anchor="e"
        ).grid(row=0, column=0, sticky="e", padx=(0, 10), pady=6)

        t_content = ctk.CTkFrame(card, fg_color="transparent")
        t_content.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        t_content.grid_columnconfigure((0, 1), weight=1)

        t_col1 = ctk.CTkFrame(t_content, fg_color="transparent")
        t_col1.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        t_col1.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(t_col1, text="تفاصيل الأطروحة / Thesis Details", font=ctk.CTkFont(family=AppFonts.FAMILY, size=11, weight="bold"), anchor="e").grid(row=0, column=0, sticky="e", pady=(0, 6))

        thesis_list = ThesisRepository().get_by_student(self._student["id"])
        if thesis_list:
            thesis = thesis_list[0]
            ctk.CTkLabel(t_col1, text=f"العنوان (عربي): {thesis.get('title_ar') or '—'}", font=ctk.CTkFont(family=AppFonts.FAMILY, size=10), anchor="e", justify="right").grid(row=1, column=0, sticky="e", pady=2)
            ctk.CTkLabel(t_col1, text=f"Title (English): {thesis.get('title_en') or '—'}", font=ctk.CTkFont(family=AppFonts.FAMILY, size=10), anchor="e", justify="left").grid(row=2, column=0, sticky="e", pady=2)
            ctk.CTkLabel(t_col1, text=f"تاريخ المناقشة: {thesis.get('defense_date') or '—'}", font=ctk.CTkFont(family=AppFonts.FAMILY, size=10), anchor="e").grid(row=3, column=0, sticky="e", pady=2)
            
            dec = thesis.get('committee_decision', '') or '—'
            dec_label = f"قرار اللجنة: {dec}"
            ctk.CTkLabel(t_col1, text=dec_label, font=ctk.CTkFont(family=AppFonts.FAMILY, size=10), anchor="e").grid(row=4, column=0, sticky="e", pady=2)
            
            grade_raw = thesis.get('final_grade')
            grade_val = float(grade_raw) if grade_raw is not None else None
            grade_str = f"{int(grade_val)}" if grade_val is not None and grade_val.is_integer() else (f"{grade_val:.1f}" if grade_val is not None else "—")
            ctk.CTkLabel(t_col1, text=f"الدرجة النهائية: {grade_str}", font=ctk.CTkFont(family=AppFonts.FAMILY, size=10), anchor="e").grid(row=5, column=0, sticky="e", pady=2)
        else:
            ctk.CTkLabel(t_col1, text="لم يتم إدخال بيانات الأطروحة بعد.\nNo thesis details recorded.", font=ctk.CTkFont(family=AppFonts.FAMILY, size=10), text_color=AppColors.TEXT_MUTED, anchor="center").grid(row=1, column=0, pady=10)

        t_col0 = ctk.CTkFrame(t_content, fg_color="transparent")
        t_col0.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        t_col0.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(t_col0, text="المشرفون / Supervisors", font=ctk.CTkFont(family=AppFonts.FAMILY, size=11, weight="bold"), anchor="e").grid(row=0, column=0, sticky="e", pady=(0, 6))

        add_sup_frame = ctk.CTkFrame(t_col0, fg_color="transparent")
        add_sup_frame.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        add_sup_frame.grid_columnconfigure(0, weight=1)

        personnel = PersonnelRepository().get_active()
        pers_labels = ["—"] + [f"{p['name_ar']}  /  {p['name_en']}" for p in personnel]
        self._new_supervisor_menu = ctk.CTkOptionMenu(
            add_sup_frame, values=pers_labels,
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=9),
            height=28
        )
        self._new_supervisor_menu.set("—")
        self._new_supervisor_menu.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        ctk.CTkButton(
            add_sup_frame, text="إضافة مشرف\nAdd Supervisor",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=8),
            width=80, height=28, corner_radius=6,
            command=self._add_supervisor
        ).grid(row=0, column=1)

        supervisors = SupervisorRepository().get_by_student(self._student["id"])
        if supervisors:
            for idx, sup in enumerate(supervisors):
                sup_row = ctk.CTkFrame(t_col0, fg_color="transparent")
                sup_row.grid(row=2 + idx, column=0, sticky="ew", pady=1)
                sup_row.grid_columnconfigure(0, weight=1)

                name = sup.get('personnel_name_ar') or sup.get('name_ar') or ''
                ctk.CTkLabel(sup_row, text=f"• {name}", font=ctk.CTkFont(family=AppFonts.FAMILY, size=10), anchor="e").grid(row=0, column=1, sticky="e", padx=(4, 0))
                
                ctk.CTkButton(
                    sup_row, text="✕", width=20, height=20, corner_radius=4,
                    fg_color=AppColors.COLOR_ERROR, hover_color="#B71C1C",
                    font=ctk.CTkFont(size=8),
                    command=lambda s=sup: self._delete_supervisor(s)
                ).grid(row=0, column=0, sticky="w")
        else:
            ctk.CTkLabel(t_col0, text="لا يوجد مشرفون معينون بعد.\nNo supervisors assigned yet.", font=ctk.CTkFont(family=AppFonts.FAMILY, size=10), text_color=AppColors.TEXT_MUTED, anchor="center").grid(row=2, column=0, pady=10)

    def _add_supervisor(self) -> None:
        if not self._student:
            return

        label = self._new_supervisor_menu.get()
        if label == "—":
            return

        personnel = PersonnelRepository().get_active()
        personnel_id = None
        for p in personnel:
            if f"{p['name_ar']}  /  {p['name_en']}" == label:
                personnel_id = p["id"]
                break

        if personnel_id:
            try:
                SupervisorRepository().add(self._student["id"], personnel_id, "Supervisor")
                self._new_supervisor_menu.set("—")
                self.load_data()
            except Exception as e:
                print(f"Failed to add supervisor: {e}")

    def _delete_supervisor(self, supervisor: dict) -> None:
        from tkinter import messagebox
        if messagebox.askyesno("تأكيد الحذف", "هل أنت متأكد من إزالة هذا المشرف؟"):
            self._do_delete_supervisor(supervisor)

    def _do_delete_supervisor(self, supervisor: dict) -> None:
        try:
            from data.repositories import StudentSupervisorRepository
            StudentSupervisorRepository(SupervisorRepository().api_url).delete(supervisor["id"])
            self.load_data()
        except Exception as e:
            print(f"Failed to delete supervisor: {e}")
