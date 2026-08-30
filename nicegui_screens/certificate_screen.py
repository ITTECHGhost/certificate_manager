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


def parse_stage_num(val, default: int = 1) -> int:
    """Safely extracts integer stage number from int, float, or string (e.g. '2', 'Stage 2', 'المرحلة 2')."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default
    s = str(val).strip()
    if not s:
        return default
    match = re.search(r"\d+", s)
    if match:
        try:
            return int(match.group())
        except (ValueError, TypeError):
            return default
    return default


def safe_int_val(v, default: int = 1) -> int:
    return parse_stage_num(v, default)


def consolidate_courses_for_certificate(courses_grouped: list, is_annual: bool = True) -> list:
    """
    Consolidates course records for certificate printing and transcript display:
    1. EXCLUDES any failed courses (score/mark < 50.0) that were never passed.
    2. Rule A (Annual study system):
       - Carried-over ("accros" / عبور) courses appear in their original stage period card, but with their final PASSED degree.
       - If a whole year/stage was FAILED_REPEAT, courses appear in the repeated stage period where they were passed.
    3. Rule B (Semester study system):
       - Failed courses appear ONLY in the semester period where they were eventually PASSED.
    """
    if not courses_grouped:
        return []

    from collections import defaultdict

    course_groups = defaultdict(list)
    for c in courses_grouped:
        c_key = c.get("subject_name") or c.get("course_name_ar") or c.get("name_ar") or c.get("course_id")
        if c_key:
            course_groups[c_key].append(dict(c))

    consolidated_list = []

    for c_key, group in course_groups.items():
        # Sort chronologically by academic_year, stage_number, semester_num
        group.sort(key=lambda x: (
            str(x.get("academic_year") or ""),
            parse_stage_num(x.get("stage_number"), 1),
            parse_stage_num(x.get("semester_num"), 1)
        ))

        # Filter for passing attempts (mark >= 50.0 or valid numeric degree >= 50)
        passing_entries = []
        for e in group:
            mk = e.get("mark")
            if mk is None:
                mk = e.get("score")
            if mk is not None:
                try:
                    if float(mk) >= 50.0:
                        passing_entries.append(e)
                except (ValueError, TypeError):
                    if str(mk).strip() and str(mk) != "—":
                        passing_entries.append(e)

        # FAILED COURSES RULE: If student NEVER passed this course, EXCLUDE IT completely!
        if not passing_entries:
            continue

        best_passed = passing_entries[-1]  # Latest passed attempt (highest/final degree)
        earliest_attempt = group[0]         # First attempt

        final_item = dict(best_passed)

        # Ensure mark/score is set cleanly
        best_mark = best_passed.get("mark") if best_passed.get("mark") is not None else best_passed.get("score")
        if best_mark is not None:
            try:
                bm_float = float(best_mark)
                final_item["mark"] = int(bm_float) if bm_float.is_integer() else round(bm_float, 2)
                final_item["score"] = final_item["mark"]
            except (ValueError, TypeError):
                final_item["mark"] = best_mark
                final_item["score"] = best_mark

        if is_annual:
            # Rule A.2: Annual System -> Place in ORIGINAL STAGE card with the PASSED degree!
            orig_stg = parse_stage_num(earliest_attempt.get("stage_number") or best_passed.get("stage_number"), 1)
            orig_year = earliest_attempt.get("academic_year") or best_passed.get("academic_year")
            orig_year_fmt = earliest_attempt.get("academic_year_formatted") or best_passed.get("academic_year_formatted")

            final_item["stage_number"] = orig_stg
            if orig_year:
                final_item["academic_year"] = orig_year
            if orig_year_fmt:
                final_item["academic_year_formatted"] = orig_year_fmt

            sem_num = parse_stage_num(earliest_attempt.get("semester_num") or best_passed.get("semester_num"), 1)
            final_item["semester_num"] = sem_num

            # PRESERVE original grouping_key from backend if present, so grouping dropdown works correctly
            backend_gkey = best_passed.get("grouping_key") or earliest_attempt.get("grouping_key")
            final_item["grouping_key"] = backend_gkey or f"{orig_stg}_{sem_num}"
        else:
            # Rule B.1: Semester System -> Place ONLY in the SEMESTER period where course WAS PASSED!
            pass_stg = parse_stage_num(best_passed.get("stage_number"), 1)
            pass_sem = parse_stage_num(best_passed.get("semester_num"), 1)
            pass_year = best_passed.get("academic_year")
            pass_year_fmt = best_passed.get("academic_year_formatted")

            final_item["stage_number"] = pass_stg
            final_item["semester_num"] = pass_sem
            if pass_year:
                final_item["academic_year"] = pass_year
            if pass_year_fmt:
                final_item["academic_year_formatted"] = pass_year_fmt

            # PRESERVE original grouping_key from backend if present, so grouping dropdown works correctly
            backend_gkey = best_passed.get("grouping_key") or earliest_attempt.get("grouping_key")
            final_item["grouping_key"] = backend_gkey or f"{pass_stg}_{pass_sem}"

        # If retaken or passed in round 2/3, flag round info
        if len(group) > 1 or str(best_passed.get("passed_round")) in ('2', '3') or best_passed.get("is_second_round"):
            final_item["passed_round"] = best_passed.get("passed_round", "2")
            final_item["is_second_round"] = 1
        else:
            final_item["passed_round"] = "1"
            final_item["is_second_round"] = 0

        consolidated_list.append(final_item)

    # Sort consolidated list chronologically & by stage
    consolidated_list.sort(key=lambda x: (
        parse_stage_num(x.get("stage_number"), 1),
        parse_stage_num(x.get("semester_num"), 1),
        str(x.get("academic_year") or ""),
        str(x.get("subject_name") or "")
    ))

    return consolidated_list


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

    stage_primary_map = {}
    for p in periods:
        st_status = p.get("result_status") or "PASSED"
        if st_status == "FAILED_REPEAT":
            continue
        stg_key = (p.get("stage_number", 1), p.get("semester_num", 1))
        if stg_key not in stage_primary_map:
            stage_primary_map[stg_key] = p["id"]

    # Fallback if all periods for a stage were FAILED_REPEAT
    for p in periods:
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
        stg_key = (int(first_enr["_period"].get("stage_number") or 1), int(first_enr["_period"].get("semester_num") or 1))
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

    # Filter out empty FAILED_REPEAT periods that surrendered all their passed courses
    final_periods = []
    for p in copied_periods:
        st_status = p.get("result_status") or "PASSED"
        if st_status == "FAILED_REPEAT" and not p["enrollments"]:
            continue
        final_periods.append(p)

    return final_periods


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


def to_arabic_num(val: str | int | float | None, is_english: bool = False) -> str:
    """Helper to convert standard ASCII digits (0-9) to Eastern Arabic numerals (٠-٩) when generating Arabic certificates."""
    if val is None:
        return ""
    s = str(val)
    if not is_english:
        trans = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
        return s.translate(trans)
    return s


def format_date_rtl(val: str | None, is_english: bool = False) -> str:
    """Formats YYYY-MM-DD date strings into DD-MM-YYYY order with Eastern Arabic numerals for RTL display."""
    if not val:
        return ""
    s = str(val).strip()
    match = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", s)
    if match:
        y, m, d = match.groups()
        s = f"{d.zfill(2)}-{m.zfill(2)}-{y}"
    return to_arabic_num(s, is_english)


def format_academic_year_ltr(val: str | None, is_english: bool = False) -> str:
    """
    Ensures academic year range is strictly LTR ordered (smaller year on the left: e.g. 2016-2017 / ٢٠١٦-٢٠١٧).
    Uses Left-to-Right Mark (\u200e) to prevent RTL text reversal in Word tables.
    """
    if not val:
        return ""
    s = str(val).strip()
    years = re.findall(r"\d{4}", s)
    if len(years) >= 2:
        y1, y2 = int(years[0]), int(years[1])
        smaller, larger = min(y1, y2), max(y1, y2)
        formatted = f"{smaller}-{larger}"
        return f"\u200e{to_arabic_num(formatted, is_english)}\u200e"
    return to_arabic_num(s, is_english)


def get_subj_display(enr: dict, is_english: bool) -> str:
    """Formats course name, appending attempt round indicator (*) for retaken courses."""
    if not enr:
        return ""
    if is_english:
        name = enr.get("course_name_en") or enr.get("subject_name_en") or enr.get("name_en") or enr.get("subject_name") or ""
    else:
        name = enr.get("course_name_ar") or enr.get("subject_name_ar") or enr.get("name_ar") or enr.get("subject_name") or ""
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
        return f"{name}*"
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

    # 4. Consolidate course history according to Rules A (Annual) & B (Semester)
    period_disp = str(data.get("period_display") or "year").lower()
    is_annual = (period_disp == "year")
    raw_courses = data.get("courses_grouped", [])
    courses_grouped = consolidate_courses_for_certificate(raw_courses, is_annual=is_annual)
    
    from collections import OrderedDict
    groups_in_order = OrderedDict()
    for c in courses_grouped:
        gkey = str(c.get("grouping_key", ""))
        if gkey not in groups_in_order:
            groups_in_order[gkey] = []
        groups_in_order[gkey].append(c)
        
    group_lists = list(groups_in_order.values())
    paired_semesters = []
    
    stage_names_ar = {1: "الأولى", 2: "الثانية", 3: "الثالثة", 4: "الرابعة", 5: "الخامسة", 6: "السادسة"}
    stage_names_en = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth", 6: "Sixth"}
    is_annual = (period_disp == "year")
    
    for i in range(0, len(group_lists), 2):
        pair_idx = i // 2
        first_stg_default = pair_idx * 2 + 1
        second_stg_default = pair_idx * 2 + 2

        if is_english:
            # In English LTR tables, Column 1 is on the LEFT and Column 2 is on the RIGHT.
            # Therefore, Stage 1 (2016-2017) goes to the LEFT, and Stage 2 (2017-2018) goes to the RIGHT.
            left_courses = group_lists[i]
            right_courses = group_lists[i + 1] if i + 1 < len(group_lists) else []
            
            right_c = right_courses[0] if right_courses else {}
            left_c = left_courses[0] if left_courses else {}
            
            stg_left_raw = left_c.get("stage_number")
            stg_right_raw = right_c.get("stage_number")
            
            stg_left = stg_left_raw if (stg_left_raw and int(stg_left_raw) > pair_idx * 2) else first_stg_default
            stg_right = stg_right_raw if (stg_right_raw and int(stg_right_raw) > pair_idx * 2) else (second_stg_default if right_courses else (stg_left + 1))
        else:
            # In Arabic RTL tables, Column 1 is on the RIGHT and Column 2 is on the LEFT.
            # Therefore, Stage 1 (2016-2017) goes to the RIGHT, and Stage 2 (2017-2018) goes to the LEFT.
            right_courses = group_lists[i]
            left_courses = group_lists[i + 1] if i + 1 < len(group_lists) else []
            
            right_c = right_courses[0] if right_courses else {}
            left_c = left_courses[0] if left_courses else {}
            
            stg_right_raw = right_c.get("stage_number")
            stg_left_raw = left_c.get("stage_number")
            
            stg_right = stg_right_raw if (stg_right_raw and int(stg_right_raw) > pair_idx * 2) else first_stg_default
            stg_left = stg_left_raw if (stg_left_raw and int(stg_left_raw) > pair_idx * 2) else (second_stg_default if left_courses else (stg_right + 1))
        
        ay_right = right_c.get("academic_year_formatted") or right_c.get("academic_year", "")
        ay_left = left_c.get("academic_year_formatted") or left_c.get("academic_year", "")
        
        sem_right = right_c.get("semester_num") or 1
        sem_left = left_c.get("semester_num") or 2
        
        stg_num_right_str = to_arabic_num(stg_right, is_english)
        stg_num_left_str = to_arabic_num(stg_left, is_english) if left_courses else ""
        stg_text_right = (stage_names_en if is_english else stage_names_ar).get(int(stg_right) if str(stg_right).isdigit() else 1, str(stg_right))
        stg_text_left = (stage_names_en if is_english else stage_names_ar).get(int(stg_left) if str(stg_left).isdigit() else 2, str(stg_left)) if left_courses else ""
        
        right_year_disp = format_academic_year_ltr(ay_right, is_english)
        left_year_disp = format_academic_year_ltr(ay_left, is_english) if left_courses else ""
        
        doc_rows = []
        for right, left in zip_longest(right_courses, left_courses, fillvalue={}):
            rname = get_subj_display(right, is_english) if right else ""
            lname = get_subj_display(left, is_english) if left else ""
            
            rmark = to_arabic_num(right.get("mark", ""), is_english) if right else ""
            runit = to_arabic_num(right.get("unit", ""), is_english) if right else ""
            lmark = to_arabic_num(left.get("mark", ""), is_english) if left else ""
            lunit = to_arabic_num(left.get("unit", ""), is_english) if left else ""
            
            doc_rows.append({
                "left_name": lname, "left_subj": lname,
                "left_mark": lmark, "left_unit": lunit,
                "right_name": rname, "right_subj": rname,
                "right_mark": rmark, "right_unit": runit,
            })
            
        if is_annual:
            paired_semesters.append({
                "left_label": left_year_disp,
                "right_label": right_year_disp,
                "year_left_label": left_year_disp,
                "year_right_label": right_year_disp,
                "year_label_l": left_year_disp,
                "year_label_r": right_year_disp,
                "year_label": right_year_disp,
                "academic_year": right_year_disp,
                "rows": doc_rows,
                "num_s_l": stg_num_left_str,
                "num_s_r": stg_num_right_str,
                "year_s_l": stg_num_left_str,
                "year_s_r": stg_num_right_str,
                "stage_s_l": stg_num_left_str,
                "stage_s_r": stg_num_right_str,
                "stage_l": stg_num_left_str,
                "stage_r": stg_num_right_str,
                "stage": stg_num_right_str,
                "stage_num": stg_num_right_str,
                "stage_num_l": stg_num_left_str,
                "stage_num_r": stg_num_right_str,
                "stage_text": stg_text_right,
                "stage_name": stg_text_right,
                "stage_name_l": stg_text_left,
                "stage_name_r": stg_text_right,
            })
        else:
            right_sem_label = "First Semester" if is_english else "الفصل الأول"
            left_sem_label = "Second Semester" if is_english else "الفصل الثاني"
            row_year_display = f"العام الدراسي {right_year_disp}" if right_year_disp else ""
            
            paired_semesters.append({
                "left_label": left_sem_label,
                "right_label": right_sem_label,
                "year_left_label": left_year_disp,
                "year_right_label": right_year_disp,
                "year_label_l": left_year_disp,
                "year_label_r": right_year_disp,
                "year_label": row_year_display,
                "academic_year": right_year_disp,
                "rows": doc_rows,
                "num_s_l": stg_num_left_str,
                "num_s_r": stg_num_right_str,
                "sem_num_l": to_arabic_num(sem_left, is_english),
                "sem_num_r": to_arabic_num(sem_right, is_english),
                "year_s_l": stg_num_left_str,
                "year_s_r": stg_num_right_str,
                "stage_s_l": stg_num_left_str,
                "stage_s_r": stg_num_right_str,
                "stage_l": stg_num_left_str,
                "stage_r": stg_num_right_str,
                "stage": stg_num_right_str,
                "stage_num": stg_num_right_str,
                "stage_num_l": stg_num_left_str,
                "stage_num_r": stg_num_right_str,
                "stage_text": stg_text_right,
                "stage_name": stg_text_right,
                "stage_name_l": stg_text_left,
                "stage_name_r": stg_text_right,
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

    first_pair = paired_semesters[0] if paired_semesters else {}

    second_subjects = options.get("second_trial_subjects") or ""
    if is_english and data.get("courses_grouped"):
        second_en = []
        for c in data.get("courses_grouped", []):
            pr = str(c.get("passed_round") or "1").strip()
            isr = c.get("is_second_round", 0)
            if pr in ('2', '3') or isr == 1 or pr in (2, 3):
                cname = c.get("subject_name_en") or c.get("course_name_en") or c.get("name_en") or c.get("subject_name")
                if cname and cname not in second_en:
                    second_en.append(cname)
        if second_en:
            second_subjects = ", ".join(second_en)

    raw_title = (options.get("to_title") or "").strip()
    if is_english:
        if not raw_title or raw_title == "من يهمه الأمر":
            title_val = "Whom it May Concern"
        else:
            title_val = raw_title
    else:
        if not raw_title or raw_title == "Whom it May Concern":
            title_val = "من يهمه الأمر"
        else:
            title_val = raw_title

    ctx = {
        "Title": title_val,
        "to_title": title_val,
        "student_name": data.get("full_name_en" if is_english else "full_name_ar", ""),
        "Birthday": format_date_rtl(data.get("date_of_birth") or "", is_english),
        "Birthplace": data.get("birthplace_en" if is_english else "birthplace_ar") or data.get("birthplace_other", ""),
        "Nationality": data.get("nationality_en" if is_english else "nationality_ar", ""),
        "admission_year": to_arabic_num(data.get("admission_year") or "", is_english),
        "graduation_year": to_arabic_num(data.get("graduation_year") or "", is_english),
        "department_id": data.get("dept_name_en" if is_english else "dept_name_ar", ""),
        "study_type": study_type_disp,
        "graduation_date": format_date_rtl(data.get("graduation_date") or "", is_english),
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
        "Subjects_Passed_with_Second_Trial": second_subjects,
        "order_number": to_arabic_num(ord_num, is_english),
        "order_date": format_date_rtl(ord_date, is_english),
        "num_s_r": first_pair.get("num_s_r", ""),
        "num_s_l": first_pair.get("num_s_l", ""),
        "stage_s_r": first_pair.get("stage_s_r", ""),
        "stage_s_l": first_pair.get("stage_s_l", ""),
        "year_right_label": first_pair.get("year_right_label", ""),
        "year_left_label": first_pair.get("year_left_label", ""),
        "paired_semesters": paired_semesters,
        "paired_years": paired_semesters,
        "semesters": paired_semesters,
    }

    # Signatories mapping strictly by display_order column (1 to 10)
    for idx in range(1, 11):
        ctx[f"sig{idx}_name"] = ""
        ctx[f"sig{idx}_title"] = ""
        ctx[f"sig{idx}_resp"] = ""

    all_sigs = data.get("all_personnel")
    if not all_sigs:
        all_sigs = (data.get("front_signatories", []) or []) + (data.get("back_signatories", []) or [])

    valid_sigs = []
    for sig in all_sigs:
        order_raw = sig.get("display_order")
        try:
            order_val = int(order_raw) if order_raw is not None else 0
        except (ValueError, TypeError):
            order_val = 0

        if 1 <= order_val <= 10:
            valid_sigs.append((order_val, sig))

    valid_sigs.sort(key=lambda x: x[0])

    for order, sig in valid_sigs:
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
        self.current_grouping_mode = "DEFAULT"

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
            if hasattr(self, "render_preview_grid"):
                self.render_preview_grid()

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

                        UI.primary_button("العودة لبيانات الطالب / Back to Student", icon="arrow_forward", on_click=self.show_info_view).classes("text-xs px-4 py-2 font-bold")

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
                        
                        def on_grouping_change(e):
                            if not hasattr(self, 'student_full_data') or not self.student_full_data: return
                            student_id = self.student_full_data.get('student_id') or self.student_full_data.get('id')
                            if not student_id: return
                            self.student_full_data = self.cert_repo.get_full_certificate_data(student_id, e.value)
                            if hasattr(self, "render_preview_grid"):
                                self.render_preview_grid()

                        GROUPING_OPTIONS = {
                            "DEFAULT": "الافتراضي / Default",
                            "BY_YEAR": "حسب السنة الدراسية / By Year",
                            "BY_STAGE": "حسب المرحلة الدراسية / By Stage",
                            "BY_CURRICULUM": "حسب الخطة الدراسية / By Curriculum"
                        }
                        self.grouping_sel = UI.select(
                            "نمط التجميع / Grouping",
                            options=GROUPING_OPTIONS,
                            value="DEFAULT",
                            on_change=on_grouping_change
                        ).classes("flex-1 text-sm")

                        UI.primary_button("تعديل الطالب / Edit", icon="edit", on_click=self.handle_edit_student).classes("text-sm px-4 py-3.5 mt-2")

                    ui.separator().classes("my-1")

                    # Row 2: University Order Section (3 Components in 1 Row)
                    with UI.card().classes("w-full p-4 gap-3 bg-[var(--bg-main)] rounded-xl border border-[var(--border-default)]"):
                        ui.label("بيانات الأمر الجامعي — University Order").classes("text-xs font-bold app-text-accent")
                        with ui.row().classes("w-full gap-4 items-center"):
                            self.sw_order = UI.switch("تفعيل الأمر الجامعي / Enable Order", value=False).classes("w-64")
                            self.inp_order_num = UI.text_input("رقم الأمر الجامعي / Order No", value="").classes("flex-1 text-sm")
                            self.inp_order_date = UI.text_input("تاريخ الأمر / Order Date", value="").classes("flex-1 text-sm")

                    # Row 3: Graduation Rank Section (5 Components in 1 Row)
                    with UI.card().classes("w-full p-4 gap-3 bg-[var(--bg-main)] rounded-xl border border-[var(--border-default)]"):
                        ui.label("بيانات تسلسل التخرج والترتيب — Graduation Rank").classes("text-xs font-bold app-text-accent")
                        with ui.row().classes("w-full gap-4 items-center"):
                            self.sw_rank = UI.switch("تفعيل تسلسل التخرج / Enable Rank", value=False).classes("w-52")
                            self.inp_rank_val = UI.text_input("تسلسل الطالب / Rank", value="").classes("flex-1 text-sm")

                            def on_rank_source_change(e):
                                if not hasattr(self, "student_full_data") or not self.student_full_data: return
                                src = e.value
                                order_cnt = self.student_full_data.get("order_num_students")
                                custom_cnt = self.student_full_data.get("postgraduation_number")
                                db_cnt = self.student_full_data.get("db_total_graduates")

                                if src == "custom":
                                    sel_val = custom_cnt if custom_cnt is not None and str(custom_cnt).strip() != "" else ""
                                elif src == "order":
                                    sel_val = order_cnt if order_cnt is not None and str(order_cnt).strip() != "" else ""
                                elif src == "db":
                                    sel_val = db_cnt if db_cnt is not None and str(db_cnt).strip() != "" else ""
                                else:
                                    sel_val = ""

                                self.inp_rank_total.value = str(sel_val) if sel_val != "" else ""
                                self.student_full_data["total_graduates"] = sel_val
                                rank_v = self.inp_rank_val.value or self.student_full_data.get("rank")
                                if hasattr(self, "rank_str_label") and self.rank_str_label:
                                    self.rank_str_label.text = f"المرتبة {rank_v} من {sel_val} خريج" if rank_v and sel_val != "" else "—"

                            self.rank_source_sel = UI.select(
                                "مصدر العدد / Count Source",
                                options={
                                    "order": "الأمر الجامعي / Order Count",
                                    "custom": "يدوي للطالب / Total Postgrad Students",
                                    "db": "قاعدة البيانات / DB Count"
                                },
                                value="order",
                                on_change=on_rank_source_change
                            ).classes("flex-1 text-sm")

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
                    
                    # Row 4.5: Data Validation Grid
                    with UI.card().classes("w-full p-4 gap-3 bg-[var(--bg-main)] rounded-xl border border-[var(--border-default)]"):
                        ui.label("معاينة البيانات (للتدقيق فقط) — Data Preview").classes("text-xs font-bold app-text-accent")
                        self.preview_grid_container = ui.column().classes("w-full max-h-[300px] overflow-y-auto")

                    # Row 5: Primary Action Buttons
                    with ui.row().classes("w-full gap-4 items-center pt-2"):
                        self.btn_generate = UI.success_button(
                            "إصدار وتوليد الوثيقة (Word)",
                            icon="description",
                            on_click=self.generate_and_open_word
                        ).classes("flex-1 py-3 text-base font-bold")

                        self.btn_open = UI.primary_button(
                            "فتح المعاينة والطباعة",
                            icon="print",
                            on_click=self.print_certificate
                        ).classes("flex-1 py-3 text-base")
                        self.btn_open.disable()
                        self.btn_open.set_visibility(False)

                        UI.primary_button("العودة لبيانات الطالب", icon="arrow_forward", on_click=self.show_info_view).classes("px-6 py-3 text-sm")

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

    def render_preview_grid(self):
        if not hasattr(self, 'preview_grid_container'): return
        self.preview_grid_container.clear()
        
        data = self.student_full_data
        if not data: return
        
        courses = data.get("courses_grouped", [])
        if not courses:
            with self.preview_grid_container:
                ui.label("لا توجد بيانات / No data").classes("text-xs app-text-muted italic")
            return
            
        columns = [
            {'name': 'academic_year', 'label': 'السنة / Year', 'field': 'academic_year_formatted', 'align': 'left'},
            {'name': 'stage', 'label': 'المرحلة / Stage', 'field': 'stage_number', 'align': 'center'},
            {'name': 'sem', 'label': 'الفصل / Sem', 'field': 'semester_num', 'align': 'center'},
            {'name': 'subj', 'label': 'المادة / Subject', 'field': 'subject_name', 'align': 'left'},
            {'name': 'mark', 'label': 'الدرجة / Mark', 'field': 'mark', 'align': 'center'},
            {'name': 'unit', 'label': 'الوحدات / Units', 'field': 'unit', 'align': 'center'},
            {'name': 'status', 'label': 'الحالة / Status', 'field': 'result_status_label', 'align': 'center'}
        ]
        
        normalized_courses = []
        for idx, c in enumerate(courses):
            c_copy = dict(c)
            c_copy['row_id'] = c_copy.get('course_id') or idx
            c_copy['subject_name'] = c_copy.get('course_name_ar') or c_copy.get('subject_name') or ''
            c_copy['academic_year_formatted'] = c_copy.get('academic_year_formatted') or c_copy.get('academic_year') or ''
            c_copy['unit'] = c_copy.get('units') if c_copy.get('units') is not None else c_copy.get('unit', 0)
            c_copy['semester_num'] = c_copy.get('semester_num', 1)
            c_copy['result_status_label'] = c_copy.get('result_status_label') or c_copy.get('result_status') or 'PASSED'
            normalized_courses.append(c_copy)

        with self.preview_grid_container:
            ui.table(columns=columns, rows=normalized_courses, row_key='row_id').classes('w-full text-xs')

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
        self.current_grouping_mode = getattr(self, "current_grouping_mode", "DEFAULT")

        try:
            self.student_full_data = self.cert_repo.get_full_certificate_data(
                student_id, grouping_mode=self.current_grouping_mode
            )
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
            UI.notify(f"خطأ أثناء تحميل بيانات الطالب: {e}", type="negative")

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
        if not data: return

        period_disp = str(data.get("period_display") or "").lower().strip()
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
                        UI.primary_button("تعديل الطالب / Edit Student", icon="edit", on_click=self.handle_edit_student).classes("text-xs px-4 py-2.5")

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

            # Academic Transcript Table Section (Cards Grouped by Dynamic Grouping Mode)
            period_disp = str(data.get("period_display") or "").lower().strip()
            if "semester" in period_disp:
                group_opts = {
                    "DEFAULT": "حسب السنة الدراسية (الافتراضي)",
                    "BY_SEMESTER_stage": "حسب المرحلة الدراسية"
                }
            else:
                group_opts = {
                    "DEFAULT": "حسب السنة الدراسية (الافتراضي)",
                    "BY_PERIOD_STAGE": "حسب مرحلة القيد",
                    "BY_CURRICULUM_STAGE": "حسب المرحلة الدراسية للمادة"
                }

            current_mode = getattr(self, "current_grouping_mode", "DEFAULT")
            if current_mode not in group_opts:
                current_mode = "DEFAULT"

            async def on_grouping_change(e):
                new_mode = str(getattr(e, 'value', e) or "DEFAULT")
                self.current_grouping_mode = new_mode
                if self.selected_student:
                    try:
                        self.student_full_data = self.cert_repo.get_full_certificate_data(
                            self.selected_student["id"], grouping_mode=new_mode
                        )
                        self.update_student_ui()
                    except Exception as exc:
                        log.error(f"Error updating grouping: {exc}")
                        UI.notify(f"خطأ في تحديث التجميع: {exc}", type="negative")

            with ui.row().classes("w-full justify-between items-center mt-2 pb-1"):
                ui.label("السجل الأكاديمي والدرجات — Academic Transcript").classes("text-lg font-extrabold app-text-primary tracking-wide")
                
                UI.select(
                    "خيارات التجميع / Grouping Options",
                    options=group_opts,
                    value=current_mode,
                    on_change=lambda e: on_grouping_change(e)
                ).classes("w-72 text-xs")

            with ui.column().classes("w-full border border-[var(--border-default)] rounded-2xl p-5 bg-[var(--bg-main)] gap-5 max-h-[540px] overflow-y-auto"):
                courses = data.get("courses_grouped", [])
                if not courses:
                    ui.label("لا توجد سجلات دراسية / No course records").classes("text-sm app-text-muted italic p-4")
                else:
                    grouped_data = {}
                    for c in courses:
                        k = c.get("grouping_key") or f"{c.get('stage_number', '')}_{c.get('semester_num', 1)}"
                        if k not in grouped_data:
                            grouped_data[k] = {
                                "academic_year": c.get("academic_year_formatted") or c.get("academic_year", ""),
                                "stage_number": c.get("stage_number", ""),
                                "semester_num": c.get("semester_num", 1),
                                "enrollments": []
                            }
                        grouped_data[k]["enrollments"].append(c)

                    with ui.grid(columns=2).classes("w-full gap-5 items-start"):
                        for k, p in grouped_data.items():
                            stg = p.get("stage_number", "")
                            year = p.get("academic_year", "")
                            sem = p.get("semester_num", 1)
                            enrs = p.get("enrollments", [])

                            parts = []
                            if year:
                                parts.append(f"العام الدراسي ({year})")
                            if stg:
                                parts.append(f"المرحلة {stg}")
                            if "semester" in period_disp and sem:
                                parts.append(f"الفصل {sem}")
                            header_label = " — ".join(parts) if parts else f"المجموعة ({k})"

                            with ui.column().classes("w-full gap-3 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-sm"):
                                with ui.row().classes("w-full justify-between items-center pb-2 border-b border-[var(--border-default)]"):
                                    ui.label(header_label).classes("text-sm font-extrabold app-text-accent tracking-wide")
                                    ui.label(f"عدد المواد: {len(enrs)}").classes("text-xs app-text-muted font-medium")

                                with ui.column().classes("w-full gap-2"):
                                    for enr in enrs:
                                        cname = enr.get("subject_name") or enr.get("course_name_ar") or enr.get("course_name_en") or ""
                                        score = enr.get("mark", "—")
                                        units = enr.get("unit", 0)
                                        pr = str(enr.get("passed_round", "1"))
                                        is_2nd = (pr in ('2', '3') or enr.get("is_second_round"))

                                        with ui.row().classes("w-full justify-between items-center text-sm py-2 px-3.5 rounded-xl bg-[var(--bg-main)] transition-all border border-[var(--border-default)] hover:border-amber-500/30"):
                                            with ui.row().classes("items-center gap-2"):
                                                ui.label(cname).classes("app-text-primary font-bold text-xs")
                                                if is_2nd:
                                                    ui.label("الدور الثاني").classes("px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-amber-500/20 text-amber-400 border border-amber-500/30")

                                            with ui.row().classes("items-center gap-2"):
                                                ui.label(f"الدرجة: {score}").classes("font-extrabold text-emerald-400 font-mono text-xs")
                                                ui.label(f"{units} وحدات").classes("text-[10px] font-bold px-2 py-0.5 bg-[var(--bg-card)] rounded-lg text-slate-300 font-mono border border-[var(--border-default)]")

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
        tpl_path = os.path.join("templets", tpl_name)
        if not os.path.exists(tpl_path):
            UI.notify(f"قالب الوثيقة غير موجود: {tpl_name}", type="negative")
            return False
    
        if not self.student_full_data:
            UI.notify("لم يتم تحميل بيانات الطالب", type="warning")
            return False
    
        # options is already fully populated by generate_certificate
    
        out_file = ""
        try:
            ctx = build_certificate_context(self.student_full_data, options)
    
            # Print all context variables line-by-line to terminal & log
            self.print_certificate_context(ctx)
    
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

            # Record issued certificate into database via Stored Procedure (InsertIssuedCertificate)
            try:
                student_id = self.student_full_data.get("id") or self.student_full_data.get("student_id")
                if student_id:
                    to_title = (self.to_input.value or "").strip() or "من يهمه الأمر"
                    tpl_type = os.path.splitext(tpl_name)[0]
                    from data.repositories import IssuedCertificateRepository
                    IssuedCertificateRepository().insert(
                        student_id=student_id,
                        to_title=to_title,
                        template_type=tpl_type
                    )
                    log.info(f"Successfully recorded issued certificate for student ID {student_id} via InsertIssuedCertificate SP.")
            except Exception as sp_err:
                log.error(f"Failed to record issued certificate into database via SP: {sp_err}")

            UI.notify(f"تم إصدار وتوليد الوثيقة بنجاح: {os.path.basename(out_file)}", type="positive")

            # Trigger automatic browser download
            ui.download(out_file, filename=os.path.basename(out_file))
            return True
        except PermissionError as pe:
            log.error(f"Permission denied while saving certificate file {out_file}: {pe}")
            UI.notify(
                "الملف مفتوح حالياً في برنامج Word! يرجى إغلاق ملف الوثيقة المفتوح وإعادة التوليد.\n"
                "Permission denied: The certificate document is open in Microsoft Word. Please close Word and try again.",
                type="warning"
            )
            return False
        except Exception as err:
            err_str = str(err)
            if "Permission denied" in err_str or "[Errno 13]" in err_str or ("13" in err_str and "Permission" in err_str):
                log.error(f"Permission denied saving document: {err}")
                UI.notify(
                    "الملف مفتوح حالياً في برنامج Word! يرجى إغلاق ملف الوثيقة المفتوح وإعادة المحاولة.\n"
                    "The certificate document is open in Word. Please close Word and try again.",
                    type="warning"
                )
            else:
                log.error(f"Error generating certificate: {err}")
                UI.notify(f"خطأ أثناء توليد الوثيقة: {err}", type="negative")
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
