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

from nicegui_ui.ui_components import UI
from data.repositories import StudentRepository, CertificateRepository, PersonnelRepository
from nicegui_screens.graduation_orders_screen import extract_event_value

log = logging.getLogger(__name__)


def consolidate_course_history(periods: list) -> list:
    """
    Consolidates retaken/repeated course history across periods:
    1. Identifies the earliest primary period for each (stage_number, semester_num).
    2. Finds the passing/latest degree obtained in subsequent attempts/rounds.
    3. Places the course into its primary Stage/Semester period slot with the passed degree and round info.
    4. Suppresses duplicate listings and empty carried-over secondary period cards.
    """
    if not periods:
        return []

    stage_primary_map = {}
    copied_periods = []
    period_map = {}
    for p in periods:
        p_copy = dict(p)
        p_copy["enrollments"] = []
        copied_periods.append(p_copy)
        period_map[p["id"]] = p_copy

        stg_key = (p.get("stage_number", 1), p.get("semester_num", 1))
        if stg_key not in stage_primary_map:
            stage_primary_map[stg_key] = p["id"]

    all_enrs = []
    for p in periods:
        for enr in p.get("enrollments", []):
            enr_item = dict(enr)
            enr_item["_period"] = p
            all_enrs.append(enr_item)

    from collections import defaultdict
    course_groups = defaultdict(list)
    for enr in all_enrs:
        cid = enr.get("course_id") or enr.get("course_name_ar") or enr.get("course_name_en")
        course_groups[cid].append(enr)

    for cid, group in course_groups.items():
        # Sort group chronologically by academic_year ASC, semester_num ASC, stage_number ASC
        group.sort(key=lambda x: (
            str(x.get("_period", {}).get("academic_year", "")),
            int(x.get("_period", {}).get("semester_num", 1)),
            int(x.get("_period", {}).get("stage_number", 1))
        ))

        first_enr = dict(group[0])  # Earliest attempt
        stg_key = (first_enr["_period"].get("stage_number", 1), first_enr["_period"].get("semester_num", 1))
        target_period_id = stage_primary_map.get(stg_key, first_enr["_period"]["id"])

        # Calculate total attempts and find highest/passing candidate
        total_attempts = len(group)
        passing_candidates = []
        for e in group:
            pr = str(e.get("passed_round", "1"))
            isr = e.get("is_second_round", 0)
            if pr == '3':
                total_attempts = max(total_attempts, 3)
            elif pr in ('2', '3') or isr == 1:
                total_attempts = max(total_attempts, 2)

            sc = e.get("score")
            if sc is not None:
                try:
                    if float(sc) >= 50.0:
                        passing_candidates.append(e)
                except (ValueError, TypeError):
                    if str(sc).strip() and str(sc) != "—":
                        passing_candidates.append(e)

        best_candidate = passing_candidates[-1] if passing_candidates else group[-1]

        # Format final score string
        final_score = best_candidate.get("score")
        if final_score is not None:
            try:
                sf = float(final_score)
                score_str = f"{int(sf)}" if sf.is_integer() else f"{sf:.1f}"
            except (ValueError, TypeError):
                score_str = str(final_score)
        else:
            score_str = "—"

        first_enr["score"] = score_str
        first_enr["passed_round"] = best_candidate.get("passed_round", "1")
        if total_attempts > 1 or str(best_candidate.get("passed_round")) in ('2', '3') or best_candidate.get("is_second_round"):
            first_enr["is_second_round"] = 1
        else:
            first_enr["is_second_round"] = 0

        first_enr["total_attempts"] = total_attempts

        # Attach to the PRIMARY period for that stage/semester
        if target_period_id in period_map:
            period_map[target_period_id]["enrollments"].append(first_enr)

    return copied_periods


def generate_pdf_from_docx(docx_path: str) -> str | None:
    """Converts a rendered Word .docx document into a .pdf file for direct print preview."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    abs_docx = os.path.abspath(docx_path)
    abs_pdf = os.path.splitext(abs_docx)[0] + ".pdf"
    word = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(abs_docx)
        doc.SaveAs(abs_pdf, FileFormat=17)  # 17 = wdFormatPDF
        doc.Close()
        return abs_pdf
    except Exception as err:
        log.error(f"Error converting docx to pdf: {err}")
        return None
    finally:
        if word:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def convert_docx_to_html(docx_path: str) -> str | None:
    """Converts a rendered Word .docx document into a filtered .html file for in-app web preview."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    abs_docx = os.path.abspath(docx_path)
    abs_html = os.path.splitext(abs_docx)[0] + ".html"
    word = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(abs_docx)
        doc.SaveAs(abs_html, FileFormat=10)  # 10 = wdFormatFilteredHTML
        doc.Close()
        return abs_html
    except Exception as err:
        log.error(f"Error converting docx to html: {err}")
        return None
    finally:
        if word:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def to_arabic_num(val: Any, is_english: bool = False) -> str:
    """Helper to convert standard ASCII digits (0-9) to Eastern Arabic numerals (٠-٩) when generating Arabic certificates."""
    if val is None:
        return ""
    s = str(val)
    if not is_english:
        trans = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
        return s.translate(trans)
    return s


def get_subj_display(enr: dict, is_english: bool) -> str:
    """Formats course name, appending attempt round indicator (2) or (3) for retaken courses."""
    if not enr:
        return ""
    name = enr.get("course_name_en" if is_english else "course_name_ar", "")
    if not name:
        return ""
    pr = str(enr.get("passed_round") or "1").strip()
    tot = enr.get("total_attempts", 1)

    attempt = 1
    if pr in ("2", "3"):
        attempt = int(pr)
    elif tot > 1:
        attempt = int(tot)

    if attempt > 1:
        att_num_str = to_arabic_num(attempt, is_english)
        return f"{name} ({att_num_str})"
    return name


def build_certificate_context(data: dict, options: dict) -> dict:
    """
    Builds the template context dictionary for docxtpl rendering.
    Supports both annual and semester study systems, attempt tracking,
    bilingual fields, Eastern Arabic numeral formatting, and signatories.
    """
    is_english = options.get("is_english", False)
    period_disp = str(data.get("period_display") or "year").lower()

    # 1. Graduation Semester display formatting
    grad_sem_raw = str(data.get("graduation_semester") or "").strip().lower()
    sem_map_ar = {"first": "الأول", "second": "الثاني", "summer": "الصيفي", "1": "الأول", "2": "الثاني", "3": "الصيفي"}
    sem_map_en = {"first": "First", "second": "Second", "summer": "Summer", "1": "First", "2": "Second", "3": "Summer"}
    grad_sem_text = (sem_map_en if is_english else sem_map_ar).get(grad_sem_raw)
    if not grad_sem_text:
        grad_sem_text = data.get("graduation_semester") or ("First" if is_english else "الأول")

    # 2. Average formatting (xx.xxx) to 3 decimal places
    avg = data.get("average")
    if avg is not None:
        try:
            avg_float = float(avg)
            avg_str = f"{avg_float:.3f}"
        except (ValueError, TypeError):
            avg_str = str(avg)
            avg_float = 0.0
    else:
        avg_str = "—"
        avg_float = 0.0

    # 3. Study Type display formatting
    stype_raw = str(data.get("study_type") or "").strip().lower()
    if "even" in stype_raw or "مساء" in stype_raw or "night" in stype_raw:
        study_type_disp = "Evening" if is_english else "المسائية"
    else:
        study_type_disp = "Morning" if is_english else "الصباحية"

    # 4. Consolidate course history by Academic Year
    periods = consolidate_course_history(data.get("periods", []))
    non_empty_periods = [p for p in periods if p.get("enrollments")]
    if not non_empty_periods:
        non_empty_periods = periods

    is_annual = (period_disp == "year")
    num_periods = len(non_empty_periods)
    paired_semesters = []

    # Group periods by Academic Year ('academic_year')
    from collections import OrderedDict
    year_groups = OrderedDict()
    for p in non_empty_periods:
        ay = p.get("academic_year", "")
        if ay not in year_groups:
            year_groups[ay] = []
        year_groups[ay].append(p)

    stage_names_ar = {1: "الأولى", 2: "الثانية", 3: "الثالثة", 4: "الرابعة", 5: "الخامسة", 6: "السادسة"}
    stage_names_en = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth", 6: "Sixth"}

    if is_annual:
        # Annual System (Year-Based): Combine both periods of the same year into 1 column per year.
        # Pair 2 Academic Years per row: Left = Year 1 (Stage 1), Right = Year 2 (Stage 2)
        from collections import OrderedDict
        year_summary_list = []
        year_groups = OrderedDict()
        for p in non_empty_periods:
            ay = p.get("academic_year", "")
            if ay not in year_groups:
                year_groups[ay] = []
            year_groups[ay].append(p)

        for year_idx, (ay, p_list) in enumerate(year_groups.items()):
            stg_raw = p_list[0].get("stage_number") if p_list else None
            try:
                stg_val = int(stg_raw) if stg_raw is not None and int(stg_raw) > 0 else (year_idx + 1)
            except (ValueError, TypeError):
                stg_val = year_idx + 1

            # Combine all courses from all periods of this year into a single course list
            combined_courses = []
            for p in p_list:
                combined_courses.extend(p.get("enrollments", []))

            year_summary_list.append({
                "academic_year": ay,
                "stage_num": stg_val,
                "courses": combined_courses,
            })

        # Pair the academic years 2-by-2 into rows (e.g. 2016 Stage 1 Left | 2017 Stage 2 Right)
        num_years = len(year_summary_list)
        for i in range(0, num_years, 2):
            y_left = year_summary_list[i]
            y_right = year_summary_list[i + 1] if i + 1 < num_years else None

            left_courses = y_left["courses"] if y_left else []
            right_courses = y_right["courses"] if y_right else []

            stg_left = y_left["stage_num"] if y_left else (i + 1)
            stg_right = y_right["stage_num"] if y_right else (i + 2)

            ay_left = y_left["academic_year"] if y_left else ""
            ay_right = y_right["academic_year"] if y_right else ""

            stg_num_left_str = to_arabic_num(stg_left, is_english)
            stg_num_right_str = to_arabic_num(stg_right, is_english)
            stg_text_left = (stage_names_en if is_english else stage_names_ar).get(stg_left, stg_num_left_str)
            stg_text_right = (stage_names_en if is_english else stage_names_ar).get(stg_right, stg_num_right_str)

            left_year_disp = to_arabic_num(ay_left, is_english)
            right_year_disp = to_arabic_num(ay_right, is_english)

            doc_rows = []
            for left, right in zip_longest(left_courses, right_courses, fillvalue={}):
                lname = get_subj_display(left, is_english)
                rname = get_subj_display(right, is_english)

                lmark = to_arabic_num(left.get("score", ""), is_english) if left else ""
                lunit = to_arabic_num(left.get("credit_hours", ""), is_english) if left else ""
                rmark = to_arabic_num(right.get("score", ""), is_english) if right else ""
                runit = to_arabic_num(right.get("credit_hours", ""), is_english) if right else ""

                doc_rows.append({
                    "left_name": lname, "left_subj": lname,
                    "left_mark": lmark, "left_unit": lunit,
                    "right_name": rname, "right_subj": rname,
                    "right_mark": rmark, "right_unit": runit,
                })

            paired_semesters.append({
                "left_label": left_year_disp,
                "right_label": right_year_disp,
                "year_label": left_year_disp,
                "academic_year": left_year_disp,
                "rows": doc_rows,
                "num_s_l": stg_num_left_str,       # 1, 3
                "num_s_r": stg_num_right_str,      # 2, 4
                "year_s_l": stg_num_left_str,      # 1, 3
                "year_s_r": stg_num_right_str,     # 2, 4
                "stage_s_l": stg_num_left_str,
                "stage_s_r": stg_num_right_str,
                "stage_l": stg_num_left_str,
                "stage_r": stg_num_right_str,
                "stage": stg_num_left_str,
                "stage_num": stg_num_left_str,
                "stage_text": stg_text_left,
                "stage_name": stg_text_left,
                "stage_name_l": stg_text_left,
                "stage_name_r": stg_text_right,
            })
    else:
        # Semester System: Semester 1 on Left, Semester 2 on Right for each Academic Year
        from collections import OrderedDict
        year_groups = OrderedDict()
        for p in non_empty_periods:
            ay = p.get("academic_year", "")
            if ay not in year_groups:
                year_groups[ay] = []
            year_groups[ay].append(p)

        for year_idx, (ay, p_list) in enumerate(year_groups.items()):
            stg_raw = p_list[0].get("stage_number") if p_list else None
            try:
                stg_val = int(stg_raw) if stg_raw is not None and int(stg_raw) > 0 else (year_idx + 1)
            except (ValueError, TypeError):
                stg_val = year_idx + 1

            stage_num_str = to_arabic_num(stg_val, is_english)
            stage_text = (stage_names_en if is_english else stage_names_ar).get(stg_val, stage_num_str)

            if len(p_list) >= 2:
                left_period = p_list[0]
                right_period = p_list[1]
                left_courses = left_period.get("enrollments", [])
                right_courses = right_period.get("enrollments", [])
            elif len(p_list) == 1:
                single_p = p_list[0]
                all_c = single_p.get("enrollments", [])
                half = (len(all_c) + 1) // 2
                left_courses = all_c[:half]
                right_courses = all_c[half:]
                left_period = single_p
                right_period = single_p
            else:
                left_courses, right_courses = [], []

            row_year_display = f"العام الدراسي {to_arabic_num(ay, is_english)}" if ay else ""

            doc_rows = []
            for left, right in zip_longest(left_courses, right_courses, fillvalue={}):
                lname = get_subj_display(left, is_english)
                rname = get_subj_display(right, is_english)

                lmark = to_arabic_num(left.get("score", ""), is_english) if left else ""
                lunit = to_arabic_num(left.get("credit_hours", ""), is_english) if left else ""
                rmark = to_arabic_num(right.get("score", ""), is_english) if right else ""
                runit = to_arabic_num(right.get("credit_hours", ""), is_english) if right else ""

                doc_rows.append({
                    "left_name": lname, "left_subj": lname,
                    "left_mark": lmark, "left_unit": lunit,
                    "right_name": rname, "right_subj": rname,
                    "right_mark": rmark, "right_unit": runit,
                })

            paired_semesters.append({
                "left_label": row_year_display,
                "right_label": row_year_display,
                "year_label": row_year_display,
                "academic_year": to_arabic_num(ay, is_english),
                "rows": doc_rows,
                "num_s_l": to_arabic_num(1, is_english),
                "num_s_r": to_arabic_num(2 if len(p_list) >= 2 else 1, is_english),
                "year_s_l": stage_num_str,
                "year_s_r": stage_num_str,
                "stage_s_l": stage_num_str,
                "stage_s_r": stage_num_str,
                "stage_l": stage_num_str,
                "stage_r": stage_num_str,
                "stage": stage_num_str,
                "stage_num": stage_num_str,
                "stage_text": stage_text,
                "stage_name": stage_text,
                "stage_name_l": stage_text,
                "stage_name_r": stage_text,
            })

    # Academic Grade Calculation
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

    # Context variables with Eastern Arabic numerals for Arabic certificates
    seq_val = options.get("rank_val") or data.get("rank") or ""
    num_stds = options.get("rank_total") or data.get("total_graduates") or ""
    top_avg = options.get("rank_avg") or data.get("top_average") or ""
    ord_num = (options.get("order_num") or data.get("order_number") or "") if options.get("opt_order") else ""
    ord_date = (options.get("order_date") or data.get("order_date") or "") if options.get("opt_order") else ""

    ctx = {
        "Title": options.get("to_title") or ("Whom it May Concern" if is_english else "من يهمه الأمر"),
        "student_name": data.get("full_name_en" if is_english else "full_name_ar", ""),
        "Birthday": to_arabic_num(data.get("date_of_birth") or "", is_english),
        "Birthplace": data.get("birthplace_en" if is_english else "birthplace_ar") or data.get("birthplace_other", ""),
        "Nationality": data.get("nationality_en" if is_english else "nationality_ar", ""),
        "admission_year": to_arabic_num(data.get("admission_year") or "", is_english),
        "graduation_year": to_arabic_num(data.get("graduation_year") or "", is_english),
        "department_id": data.get("dept_name_en" if is_english else "dept_name_ar", ""),
        "study_type": study_type_disp,
        "graduation_date": to_arabic_num(data.get("graduation_date") or "", is_english),
        "graduation_semester": grad_sem_text,
        "average": to_arabic_num(avg_str, is_english),
        "Grade": grade,
        "sequence_ON": bool(options.get("opt_rank")),
        "Failure_ON": bool(options.get("opt_postpone")),
        "Passed_ON": bool(options.get("opt_second_trial")),
        "Summer_ON": bool(options.get("opt_summer")),
        "Sequence_of_Graduation": to_arabic_num(seq_val, is_english),
        "num_students": to_arabic_num(num_stds, is_english),
        "Average_of_First_Student": to_arabic_num(top_avg, is_english),
        "Summer_Training_year": to_arabic_num(options.get("summer_year") or "", is_english),
        "Postponement_and_Failure_Years": to_arabic_num(options.get("postpone_years") or "", is_english),
        "Subjects_Passed_with_Second_Trial": options.get("second_trial_subjects") or "",
        "order_number": to_arabic_num(ord_num, is_english),
        "order_date": to_arabic_num(ord_date, is_english),
        "paired_semesters": paired_semesters,
        "paired_years": paired_semesters,
        "semesters": paired_semesters,
    }

    # Signatories mapping strictly by display_order column (1 to 10)
    for idx in range(1, 11):
        ctx[f"sig{idx}_name"] = ""
        ctx[f"sig{idx}_title"] = ""
        ctx[f"sig{idx}_resp"] = ""

    all_sigs = data.get("all_personnel") or (data.get("front_signatories", []) + data.get("back_signatories", []))
    for sig in all_sigs:
        order = sig.get("display_order")
        if order and isinstance(order, int) and 1 <= order <= 10:
            name = sig.get("name_en" if is_english else "name_ar") or ""
            title = sig.get("academic_title_en" if is_english else "academic_title_ar") or ""
            resp = sig.get("responsibility_en" if is_english else "responsibility_ar") or ""

            # Ensure 'None' values from DB render as empty string ""
            ctx[f"sig{order}_name"] = name if name and str(name).strip() != "None" else ""
            ctx[f"sig{order}_title"] = title if title and str(title).strip() != "None" else ""
            ctx[f"sig{order}_resp"] = resp if resp and str(resp).strip() != "None" else ""

    return ctx


# Register static path for certificates preview in NiceGUI
_cert_dir = os.path.abspath("certificates")
os.makedirs(_cert_dir, exist_ok=True)
try:
    from nicegui import app
    app.add_static_files('/certificates_files', _cert_dir)
except Exception:
    pass


def get_installed_printers() -> list[str]:
    """Queries installed Windows local and network printer names."""
    try:
        import win32print
        printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
        printer_names = [p[2] for p in printers]
        if not printer_names:
            default_p = win32print.GetDefaultPrinter()
            if default_p:
                printer_names = [default_p]
        return printer_names
    except Exception:
        return ["Default Printer"]


def get_default_printer() -> str:
    """Returns the default printer name on Windows."""
    try:
        import win32print
        return win32print.GetDefaultPrinter()
    except Exception:
        printers = get_installed_printers()
        return printers[0] if printers else "Default Printer"


def print_file_to_printer(file_path: str, printer_name: str, copies: int = 1) -> bool:
    """Sends a .docx or .pdf file directly to the selected Windows printer via Word COM."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    abs_path = os.path.abspath(file_path)
    word = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        if printer_name:
            try:
                word.ActivePrinter = printer_name
            except Exception as pe:
                log.warning(f"Could not set ActivePrinter to '{printer_name}': {pe}")
        doc = word.Documents.Open(abs_path)
        doc.PrintOut(Copies=copies)
        doc.Close(False)
        return True
    except Exception as e:
        log.error(f"Error printing to {printer_name}: {e}")
        return False
    finally:
        if word:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


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
            filtered_templates = self.get_templates(self.student_full_data)
            if hasattr(self, "template_sel") and self.template_sel:
                self.template_sel.options = {t: t for t in filtered_templates}
                self.template_sel.value = filtered_templates[0] if filtered_templates else None
                self.template_sel.update()
            self.show_info_view()

    def get_templates(self, data: dict = None) -> list[str]:
        """
        Returns docx templates filtered by the student's study system (semester vs year/annual).
        If the student is semester-based ('semester'), returns only templates matching 'semester'.
        If the student is annual/year-based ('year' / 'annual'), returns only templates matching 'year'.
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
                system_key = "semester"
            elif "year" in period_disp or "annual" in calc_rule or "year" in calc_rule:
                system_key = "year"
            else:
                system_key = None

            if system_key:
                matching = [f for f in files if system_key in f.lower()]
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

                        UI.secondary_button("⬅️ العودة لبيانات الطالب", icon="arrow_forward", on_click=self.show_info_view).classes("text-xs px-4 py-2 font-bold")

                    # Row 1: Template Selector + Issued To + Edit Student (3 Components in 1 Row)
                    with ui.row().classes("w-full gap-4 items-center"):
                        initial_templates = self.get_templates()
                        self.template_sel = UI.select(
                            "قالب الوثيقة / Certificate Template",
                            options={t: t for t in initial_templates},
                            value=initial_templates[0] if initial_templates else None
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

            # Filter template dropdown options dynamically based on student's study system (semester vs year)
            filtered_templates = self.get_templates(self.student_full_data)
            if hasattr(self, "template_sel") and self.template_sel:
                self.template_sel.options = {t: t for t in filtered_templates}
                self.template_sel.value = filtered_templates[0] if filtered_templates else None
                self.template_sel.update()

            self.show_info_view()
        except Exception as e:
            log.error(f"Error loading student: {e}")
            UI.notify(e, type="negative")
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

            # Academic Transcript Table Section (Cards Grouped by Academic Year)
            ui.label("السجل الأكاديمي والدرجات — Academic Transcript").classes("text-lg font-extrabold app-text-primary mt-2 tracking-wide")
            with ui.column().classes("w-full border border-[var(--border-default)] rounded-2xl p-5 bg-[var(--bg-main)] gap-5 max-h-[540px] overflow-y-auto"):
                periods = consolidate_course_history(data.get("periods", []))
                active_periods = [p for p in periods if p.get("enrollments")]
                if not active_periods:
                    ui.label("لا توجد سجلات دراسية / No course records").classes("text-sm app-text-muted italic p-4")
                for p in active_periods:
                    stg = p.get("stage_number", "")
                    year = p.get("academic_year", "")
                    enrs = p.get("enrollments", [])

                    header_label = f"العام الدراسي ({year}) — المرحلة {stg}" if stg else f"العام الدراسي ({year})"

                    with ui.column().classes("w-full gap-3 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)]"):
                        with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)]"):
                            ui.label(header_label).classes("text-sm font-extrabold app-text-accent tracking-wide")
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
    def show_in_app_print_dialog(self, pdf_path: str | None, html_path: str | None, docx_path: str):
        """
        Opens a modern in-app modal dialog featuring live document preview,
        system printer selection, copies count, and one-click direct printing.
        """
        rel_doc_name = os.path.basename(docx_path)

        # Read HTML content if available for 100% reliable in-app document preview
        html_content = ""
        if html_path and os.path.exists(html_path):
            try:
                with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
                    html_content = f.read()
            except Exception as e:
                log.error(f"Error reading html preview file: {e}")

        pdf_url = ""
        if pdf_path:
            quoted_pdf = urllib.parse.quote(os.path.basename(pdf_path))
            pdf_url = f"/certificates_files/{quoted_pdf}"

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
                with ui.column().classes("flex-1 h-full rounded-xl overflow-y-auto p-4 border border-[var(--border-default)] bg-slate-900 shadow-inner"):
                    if html_content:
                        # Clean white document container wrapping Word's HTML output
                        with UI.card().classes("w-full min-h-full p-8 bg-white text-black shadow-lg rounded-lg overflow-x-auto"):
                            ui.html(html_content).classes("w-full font-sans text-slate-900")
                    elif pdf_url:
                        ui.html(
                            f'<object data="{pdf_url}#toolbar=0" type="application/pdf" class="w-full h-full min-h-[600px]">'
                            f'<embed src="{pdf_url}" type="application/pdf" class="w-full h-full min-h-[600px]" />'
                            f'</object>'
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
        if not self.generated_file_path or not os.path.exists(self.generated_file_path):
            success = self.generate_certificate()
            if not success:
                return

        if self.generated_file_path and os.path.exists(self.generated_file_path):
            try:
                UI.notify("جاري تحويل الوثيقة وتحضير المعاينة...", type="info")

                # Run COM conversions asynchronously off main event loop thread to prevent connection loss!
                res = await asyncio.gather(
                    asyncio.to_thread(generate_pdf_from_docx, self.generated_file_path),
                    asyncio.to_thread(convert_docx_to_html, self.generated_file_path),
                    return_exceptions=True
                )

                pdf_res = res[0] if len(res) > 0 else None
                html_res = res[1] if len(res) > 1 else None

                pdf_path = pdf_res if isinstance(pdf_res, str) and os.path.exists(pdf_res) else None
                html_path = html_res if isinstance(html_res, str) and os.path.exists(html_res) else None

                self.show_in_app_print_dialog(pdf_path, html_path, self.generated_file_path)
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
