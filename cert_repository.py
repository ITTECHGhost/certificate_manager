# =============================================================================
# cert_repository.py — Certificate Generation Database Repository & Transformation Layer
# =============================================================================
#
# PURPOSE:
#   Extracts and modularizes all database querying, stored procedure execution,
#   offline SQLite replica retrieval, and data-transformation logic required for
#   generating student certificates.
#
# ARCHITECTURE:
#   1. Fetch Raw Data from Database:
#      - Online Mode: Calls the API responsible for fetching raw certificate data.
#                     Falls back to direct MySQL Stored Procedure execution (`sp_GetFullCertificateData`).
#      - Offline Mode: Calls local SQLite replica database engine (`get_offline_certificate_data`).
#
#   2. Process & Transform Data:
#      - Formats dates, numbers (Arabic/Eastern & English), averages, qualitative grades,
#        stage pairings (`paired_semesters`/`paired_years`), attempts, and failed years.
#
#   3. Pass Context to Word Templates:
#      - Returns a clean, ready-to-render Python dictionary (`ctx`) containing all
#        parameters expected by Jinja2 Word `.docx` templates.
#
# USAGE MODES:
#   1. Integrated Mode:
#      Imported by FastAPI, NiceGUI, or application modules to fetch certificate payloads:
#        from cert_repository import get_certificate_payload
#        payload = get_certificate_payload(student_id=2138, grouping_mode="DEFAULT")
#
#   2. Standalone Debugging Mode:
#      Executed directly from the terminal to fetch data, pretty-print JSON payload,
#      and verify template variables:
#        python cert_repository.py
#        python cert_repository.py 2138
#        python cert_repository.py --student 2138 --mode DEFAULT --english
#
# =============================================================================

import os
import sys
import json
import logging
import configparser
from pathlib import Path
from itertools import zip_longest
from typing import Dict, List, Any, Optional
from collections import OrderedDict


# Ensure workspace root is in sys.path for config imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))



log = logging.getLogger("cert_repository")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# =============================================================================
# 1. Database Connection & Configuration Management


# =============================================================================
# 2. Data Fetching Layer (Online API / Direct MySQL SP / Offline SQLite)
# =============================================================================

def _normalize_raw_payload(payload_dict: Dict[str, Any], student_id: int, grouping_mode: str) -> Dict[str, Any]:
    """
    Normalizes list/dict payload variations from API or SQLite into a standardized dict representation.
    """
    if not isinstance(payload_dict, dict):
        return {
            "student_id": student_id, "grouping_mode": grouping_mode,
            "settings": {}, "student_info": {}, "ranking": {},
            "signers": [], "academic_timeline": [], "courses_grouped": []
        }

    st_info = payload_dict.get("student_info")
    if isinstance(st_info, list):
        st_info = st_info[0] if st_info else {}
    elif not isinstance(st_info, dict):
        st_info = {}

    settings = payload_dict.get("settings")
    if isinstance(settings, list):
        settings = settings[0] if settings else {}
    elif not isinstance(settings, dict):
        settings = {}

    ranking = payload_dict.get("ranking")
    if isinstance(ranking, list):
        ranking = ranking[0] if ranking else {}
    elif not isinstance(ranking, dict):
        ranking = {}

    signers = payload_dict.get("signers") or []
    timeline = payload_dict.get("academic_timeline") or []
    courses = payload_dict.get("courses_grouped") or []

    return {
        "student_id": student_id,
        "grouping_mode": grouping_mode,
        "settings": settings,
        "student_info": st_info,
        "ranking": ranking,
        "signers": signers if isinstance(signers, list) else [],
        "academic_timeline": timeline if isinstance(timeline, list) else [],
        "courses_grouped": courses if isinstance(courses, list) else []
    }





def fetch_raw_certificate_data(
    student_id: int,
    grouping_mode: str = "DEFAULT",
    config_override: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Fetches raw database payload using dual-mode routing:
      1. Online Mode: Calls FastAPI backend endpoint (GET /certificates/raw/{student_id}).
                      If API is unreachable, falls back to direct MySQL Stored Procedure execution (`sp_GetFullCertificateData`).
      2. Offline Mode: Calls local SQLite replica database engine (`get_offline_certificate_data`).
    """
    st_id = int(student_id)
    raw_payload: Dict[str, Any] = {
        "student_id": st_id,
        "grouping_mode": grouping_mode,
        "settings": {},
        "student_info": {},
        "ranking": {},
        "signers": [],
        "academic_timeline": [],
        "courses_grouped": []
    }

    try:
        from sync_engine import is_online
        online = is_online()
    except Exception:
        online = True

    if online:
        # Attempt 1: Call FastAPI Backend API Route
        try:
            from api_config import API_URL
            import requests
            url = f"{API_URL}/certificates/{st_id}?grouping_mode={grouping_mode}"
            resp = requests.get(url, timeout=3.5)
            if resp.status_code == 200:
                api_data = resp.json()
                if api_data and (api_data.get("student_info") or api_data.get("full_name_ar")):
                    log.info("Online Mode: Successfully fetched raw certificate payload via API for student_id=%s.", st_id)
                    return _normalize_raw_payload(api_data, st_id, grouping_mode)
        except Exception as api_err:
            log.warning("Online API certificate request failed (%s). Falling back to direct MySQL SP execution...", api_err)



    # Offline Mode (or Fallback when Online DB connection fails)
    try:
        from data.query import get_offline_certificate_data
        log.info("Offline Mode: Executing local SQLite replica database engine for student_id=%s...", st_id)
        off_data = get_offline_certificate_data(st_id, grouping_mode)
        return _normalize_raw_payload(off_data, st_id, grouping_mode)
    except Exception as off_err:
        log.error("Local SQLite replica engine failed for student_id=%s: %s", st_id, off_err)

    return raw_payload


# =============================================================================
# 3. Data Formatting & Number Translation Helpers
# =============================================================================

ARABIC_DIGIT_MAP = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

def to_arabic_num(val: Any, is_english: bool = False) -> str:
    """Converts standard digits to Eastern Arabic numerals if is_english is False."""
    if val is None:
        return ""
    s = str(val)
    if is_english:
        return s
    return s.translate(ARABIC_DIGIT_MAP)


def format_academic_year_ltr(ay_str: Any, is_english: bool = False) -> str:
    """Ensures academic year spans (e.g. 2021-2022) format cleanly LTR."""
    if not ay_str:
        return ""
    clean = str(ay_str).strip()
    if "-" in clean:
        parts = [p.strip() for p in clean.split("-") if p.strip()]
        if len(parts) == 2:
            p1 = to_arabic_num(parts[0], is_english)
            p2 = to_arabic_num(parts[1], is_english)
            return f"\u200e{p1} - {p2}\u200e"
    return f"\u200e{to_arabic_num(clean, is_english)}\u200e"


def parse_stage_num(val: Any, default: int = 1) -> int:
    """Safely extracts an integer stage number from various input formats."""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        s = str(val)
        for char in s:
            if char.isdigit():
                return int(char)
        return default


def get_subj_display(course: dict, is_english: bool = False) -> str:
    """Extracts course title based on language selection."""
    if not course or not isinstance(course, dict):
        return ""
    if is_english:
        return course.get("subject_name_en") or course.get("course_name_en") or course.get("name_en") or course.get("subject_name") or course.get("course_name_ar") or ""
    return course.get("subject_name") or course.get("course_name_ar") or course.get("name_ar") or course.get("subject_name_en") or ""


def consolidate_courses_for_certificate(courses: list, is_annual: bool = False) -> list:
    """
    Consolidates course enrollment history into formatted groups for certificate layout.
    """
    if not courses:
        return []

    processed = []
    for c in courses:
        c_copy = dict(c)
        ay = str(c_copy.get("academic_year") or "").strip()
        c_copy["academic_year_formatted"] = format_academic_year_ltr(ay)
        
        pr = str(c_copy.get("passed_round") or "1").strip()
        isr = c_copy.get("is_second_round", 0)
        c_copy["is_second"] = True if (pr in ('2', '3') or isr == 1 or pr in (2, 3)) else False

        # Build grouping key
        if is_annual:
            c_copy["grouping_key"] = f"{ay}_Annual"
        else:
            sem = c_copy.get("semester_num", 1)
            c_copy["grouping_key"] = f"{ay}_Sem{sem}"

        processed.append(c_copy)

    return processed


def extract_failed_years(timeline: list, is_english: bool = False) -> list:
    """
    Extracts failed and postponed years from academic timeline.
    Returns list of dicts: [{'year_d': '2020-2021', 'stage': 'الأولى', 'state': 'تأجيل', 'semester': 'الأولى'}, ...]
    """
    stage_names_ar = {1: "الأولى", 2: "الثانية", 3: "الثالثة", 4: "الرابعة", 5: "الخامسة", 6: "السادسة"}
    stage_names_en = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth", 6: "Sixth"}
    
    failed_years = []
    seen = set()
    for p in (timeline or []):
        st_raw = str(p.get("result_status") or p.get("result_status_code") or "").upper().strip()
        st_label = str(p.get("result_status_label") or "").upper().strip()
        
        is_deferred = ("DEFERRED" in st_raw or "5" in st_raw or "تأجيل" in st_raw or "DEFERRED" in st_label)
        is_failed = ("FAILED" in st_raw or "2" in st_raw or "رسوب" in st_raw or "FAILED" in st_label)
        
        if is_deferred or is_failed:
            ay = format_academic_year_ltr(p.get("academic_year") or "", is_english)
            stg_num = parse_stage_num(p.get("stage_number"), 1)
            stg_text = (stage_names_en if is_english else stage_names_ar).get(stg_num, str(stg_num))
            
            state_text = ("Postponed" if is_english else "تأجيل") if is_deferred else ("Failed" if is_english else "رسوب")
            key = (ay, stg_num, state_text)
            if key not in seen:
                seen.add(key)
                failed_years.append({
                    "year_d": ay,
                    "stage": stg_text,
                    "state": state_text,
                    "year": ay,
                    "status": state_text,
                    "semester": stg_text
                })
    return failed_years


def extract_attempts(courses: list, is_english: bool = False) -> list:
    """
    Extracts 2nd/3rd attempt subjects grouped by academic year and stage.
    Returns list of dicts: [{'year': '2020-2021', 'stage': 'الأولى', 'subjects': 'الإنكليزي 1، البرمجة 1'}, ...]
    """
    stage_names_ar = {1: "الأولى", 2: "الثانية", 3: "الثالثة", 4: "الرابعة", 5: "الخامسة", 6: "السادسة"}
    stage_names_en = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth", 6: "Sixth"}
    
    grouped = OrderedDict()
    
    for c in (courses or []):
        pr = str(c.get("passed_round") or "1").strip()
        isr = c.get("is_second_round", 0)
        if pr in ('2', '3') or isr == 1 or pr in (2, 3):
            ay = format_academic_year_ltr(c.get("academic_year") or "", is_english)
            stg_num = parse_stage_num(c.get("period_stage") or c.get("stage_number"), 1)
            stg_text = (stage_names_en if is_english else stage_names_ar).get(stg_num, str(stg_num))
            
            cname = get_subj_display(c, is_english)
            key = (ay, stg_num, stg_text)
            if key not in grouped:
                grouped[key] = []
            if cname and cname not in grouped[key]:
                grouped[key].append(cname)
                
    attempts = []
    sep = ", " if is_english else "، "
    for (ay, stg_num, stg_text), c_list in grouped.items():
        subj_str = sep.join(c_list)
        attempts.append({
            "year": ay,
            "stage": stg_text,
            "subjects": subj_str,
            "year_d": ay,
            "academic_year": ay,
            "stage_text": stg_text,
            "courses": c_list
        })
        
    return attempts


# =============================================================================
# 4. Data Transformation & Jinja2 Template Context Generator
# =============================================================================

def _format_demographics(ctx: Dict[str, Any], data: Dict[str, Any], is_english: bool) -> None:
    student_info = data.get("student_info") or data
    settings = data.get("settings") or data
    ranking = data.get("ranking") or data

    ctx.update({
        "student_id": data.get("student_id"),
        "grouping_mode": data.get("grouping_mode", "DEFAULT"),
        "is_english": is_english,
        "full_name_ar": student_info.get("full_name_ar") or "",
        "full_name_en": student_info.get("full_name_en") or "",
        "student_name": (student_info.get("full_name_en") if is_english else student_info.get("full_name_ar")) or "",
        "student_name_ar": student_info.get("full_name_ar") or "",
        "student_name_en": student_info.get("full_name_en") or "",
        "gender": student_info.get("gender") or "Male",
        "date_of_birth": student_info.get("date_of_birth") or "",
        "birthplace_ar": student_info.get("birthplace_ar") or "",
        "birthplace_en": student_info.get("birthplace_en") or "",
        "nationality_ar": student_info.get("nationality_ar") or "",
        "nationality_en": student_info.get("nationality_en") or "",
        "admission_year": student_info.get("admission_year") or "",
        "graduation_year": student_info.get("graduation_year") or "",
        "graduation_date": student_info.get("graduation_date") or "",
        "graduation_semester": student_info.get("graduation_semester") or "",
        "order_number": student_info.get("order_number") or "",
        "order_date": student_info.get("order_date") or "",
        "dept_name_ar": student_info.get("dept_name_ar") or "",
        "dept_name_en": student_info.get("dept_name_en") or "",
        "study_system_name_ar": student_info.get("study_system_name_ar") or "",
        "study_system_name_en": student_info.get("study_system_name_en") or "",
        "period_display": student_info.get("period_display") or "year",
        "study_type": student_info.get("study_type") or "Morning",
        
        "university_name_ar": settings.get("university_name_ar") or "",
        "university_name_en": settings.get("university_name_en") or "",
        "college_name_ar": settings.get("college_name_ar") or "",
        "college_name_en": settings.get("college_name_en") or "",
        "republic_ar": settings.get("republic_ar") or "الجمهورية العراقية",
        "republic_en": settings.get("republic_en") or "Republic of Iraq",
        "ministry_ar": settings.get("ministry_ar") or "وزارة التعليم العالي والبحث العلمي",
        "ministry_en": settings.get("ministry_en") or "Ministry of Higher Education and Scientific Research",
        
        "rank": ranking.get("rank") or ranking.get("sequence_number") or ranking.get("class_rank") or student_info.get("sequence_number") or student_info.get("sequence_no") or "",
        "total_graduates": ranking.get("total_graduates") or ranking.get("num_students") or student_info.get("postgraduation_number") or student_info.get("postgraduation_no") or student_info.get("order_num_students") or "",
        "top_average": ranking.get("top_average") or "",
        "average": student_info.get("average") or ranking.get("average"),
    })


def _format_average_and_grade(ctx: Dict[str, Any], is_english: bool) -> None:
    avg_val = ctx.get("average")
    if avg_val is not None:
        try:
            avg_float = float(avg_val)
            avg_str = f"{avg_float:.3f}"
        except (ValueError, TypeError):
            avg_str = str(avg_val)
            avg_float = 0.0
    else:
        avg_str = "—"
        avg_float = 0.0

    ctx["average_formatted"] = to_arabic_num(avg_str, is_english)
    ctx["average_float"] = avg_float

    if avg_float >= 90:
        grade = "Excellent" if is_english else "ممتاز"
    elif avg_float >= 80:
        grade = "Very Good" if is_english else "جيد جداً"
    elif avg_float >= 70:
        grade = "Good" if is_english else "جيد"
    elif avg_float >= 60:
        grade = "Medium" if is_english else "متوسط"
    elif avg_float >= 50:
        grade = "Pass" if is_english else "مقبول"
    else:
        grade = "—"

    ctx["academic_grade"] = grade


def _format_second_round_courses(ctx: Dict[str, Any], raw_courses: list, is_english: bool) -> None:
    second_round_courses = []
    second_round_names = []
    for c in raw_courses:
        pr = str(c.get("passed_round") or "1").strip()
        isr = c.get("is_second_round", 0)
        if pr in ('2', '3') or isr == 1 or pr in (2, 3):
            second_round_courses.append(c)
            cname = get_subj_display(c, is_english)
            if cname and cname not in second_round_names:
                second_round_names.append(cname)

    ctx["second_round_courses"] = second_round_courses
    ctx["second_round_count"] = len(second_round_courses)
    ctx["second_trial_subjects"] = "، ".join(second_round_names) if not is_english else ", ".join(second_round_names)


def _format_attempts(ctx: Dict[str, Any], raw_courses: list, is_english: bool) -> None:
    attempts = extract_attempts(raw_courses, is_english=is_english)
    ctx["attempts"] = attempts
    ctx["Passed_ON"] = len(attempts) > 0
    ctx["passed_on"] = len(attempts) > 0
    ctx["PASSED_ON"] = len(attempts) > 0


def _format_failed_years(ctx: Dict[str, Any], timeline: list, is_english: bool) -> None:
    failed_years = extract_failed_years(timeline, is_english=is_english)
    ctx["failed_years"] = failed_years
    ctx["Failure_ON"] = len(failed_years) > 0
    ctx["failure_on"] = len(failed_years) > 0
    ctx["FAILURE_ON"] = len(failed_years) > 0

    deferred_years = [y["year_d"] for y in failed_years if y.get("status") in ("تأجيل", "Postponed")]
    ctx["deferred_years"] = deferred_years
    ctx["has_deferred_years"] = len(deferred_years) > 0


def _format_paired_semesters(ctx: Dict[str, Any], data: Dict[str, Any], raw_courses: list, is_english: bool) -> None:
    grouping_mode = str(data.get("grouping_mode") or "DEFAULT").upper()
    period_disp = str(ctx.get("period_display", "")).lower()
    is_annual = (period_disp == "year") or ("SEMESTER" not in grouping_mode and ("YEAR" in grouping_mode or "PERIOD" in grouping_mode))

    courses_grouped = consolidate_courses_for_certificate(raw_courses, is_annual=is_annual)
    
    groups_in_order = OrderedDict()
    for c in courses_grouped:
        gkey = str(c.get("grouping_key", ""))
        if gkey not in groups_in_order:
            groups_in_order[gkey] = []
        groups_in_order[gkey].append(c)

    def _group_sort_key(course_list):
        if not course_list: return ("", 0, 0)
        c0 = course_list[0]
        ay = str(c0.get("academic_year") or c0.get("academic_year_formatted") or "")
        stg = parse_stage_num(c0.get("stage_number") or c0.get("period_stage"), 1)
        sem = parse_stage_num(c0.get("semester_num"), 1)
        return (ay, stg, sem)

    group_lists = sorted(list(groups_in_order.values()), key=_group_sort_key)
    paired_semesters = []
    
    stage_names_ar = {1: "الأولى", 2: "الثانية", 3: "الثالثة", 4: "الرابعة", 5: "الخامسة", 6: "السادسة"}
    stage_names_en = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth", 6: "Sixth"}

    def _extract_group_stage(course_list, default_val):
        if not course_list: return default_val
        p_stages = [c.get("period_stage") for c in course_list if c.get("period_stage")]
        if p_stages: return max(p_stages, key=p_stages.count)
        c0 = course_list[0]
        stg = c0.get("period_stage") or c0.get("stage_number") or c0.get("course_curriculum_stage")
        return stg if stg is not None else default_val

    for i in range(0, len(group_lists), 2):
        pair_idx = i // 2
        first_stg_default = pair_idx * 2 + 1
        second_stg_default = pair_idx * 2 + 2

        if is_english:
            left_courses = group_lists[i]
            right_courses = group_lists[i + 1] if i + 1 < len(group_lists) else []
            stg_left = _extract_group_stage(left_courses, first_stg_default)
            stg_right = _extract_group_stage(right_courses, second_stg_default if right_courses else (stg_left + 1))
        else:
            right_courses = group_lists[i]
            left_courses = group_lists[i + 1] if i + 1 < len(group_lists) else []
            stg_right = _extract_group_stage(right_courses, first_stg_default)
            stg_left = _extract_group_stage(left_courses, second_stg_default if left_courses else (stg_right + 1))

        right_c = right_courses[0] if right_courses else {}
        left_c = left_courses[0] if left_courses else {}

        ay_right = right_c.get("academic_year_formatted") or right_c.get("academic_year", "")
        ay_left = left_c.get("academic_year_formatted") or left_c.get("academic_year", "")

        stg_num_right_str = to_arabic_num(stg_right, is_english)
        stg_num_left_str = to_arabic_num(stg_left, is_english) if left_courses else ""
        stg_text_right = (stage_names_en if is_english else stage_names_ar).get(int(stg_right) if str(stg_right).isdigit() else 1, str(stg_right))
        stg_text_left = (stage_names_en if is_english else stage_names_ar).get(int(stg_left) if str(stg_left).isdigit() else 2, str(stg_left)) if left_courses else ""

        right_year_disp = format_academic_year_ltr(ay_right, is_english)
        left_year_disp = format_academic_year_ltr(ay_left, is_english) if left_courses else ""

        def _has_second_round(courses):
            for c in courses:
                pr = str(c.get("passed_round") or "1").strip()
                isr = c.get("is_second_round", 0)
                if pr in ('2', '3') or isr == 1:
                    return True
            return False

        attempt_right = ("Second" if is_english else "الثاني") if _has_second_round(right_courses) else ("First" if is_english else "الأول")
        attempt_left = (("Second" if is_english else "الثاني") if _has_second_round(left_courses) else ("First" if is_english else "الأول")) if left_courses else ""

        doc_rows = []
        for right, left in zip_longest(right_courses, left_courses, fillvalue={}):
            rname = get_subj_display(right, is_english) if right else ""
            lname = get_subj_display(left, is_english) if left else ""

            rmark_val = right.get("mark") if right else (right.get("score") if right else "")
            lmark_val = left.get("mark") if left else (left.get("score") if left else "")
            runit_val = right.get("unit") if right else (right.get("credit_hours") if right else "")
            lunit_val = left.get("unit") if left else (left.get("credit_hours") if left else "")

            rmark = to_arabic_num(rmark_val, is_english) if right else ""
            runit = to_arabic_num(runit_val, is_english) if right else ""
            lmark = to_arabic_num(lmark_val, is_english) if left else ""
            lunit = to_arabic_num(lunit_val, is_english) if left else ""

            doc_rows.append({
                "left_name": lname, "left_subj": lname,
                "left_mark": lmark, "left_unit": lunit,
                "right_name": rname, "right_subj": rname,
                "right_mark": rmark, "right_unit": runit,
            })

        paired_semesters.append({
            "left_label": left_year_disp,
            "right_label": right_year_disp,
            "semester_right_label": f"المرحلة {stg_text_right}" if not is_english else f"Stage {stg_text_right}",
            "semester_left_label": (f"المرحلة {stg_text_left}" if not is_english else f"Stage {stg_text_left}") if left_courses else "",
            "year_left_label": left_year_disp,
            "year_right_label": right_year_disp,
            "rows": doc_rows,
            "num_s_l": stg_num_left_str,
            "num_s_r": stg_num_right_str,
            "stage_text": stg_text_right,
            "stage_text_left": stg_text_left,
            "attempt_right": attempt_right,
            "attempt_left": attempt_left,
        })
        
    ctx["paired_semesters"] = paired_semesters
    ctx["paired_years"] = paired_semesters
    ctx["semesters"] = paired_semesters


def _format_sequence_and_rank(ctx: Dict[str, Any], is_english: bool) -> None:
    rank_str_val = str(ctx.get("rank") or "").strip()
    num_stds_val = str(ctx.get("total_graduates") or "").strip()
    top_avg_val = str(ctx.get("top_average") or "").strip()

    ctx["Sequence_of_Graduation"] = to_arabic_num(rank_str_val, is_english)
    ctx["num_students"] = to_arabic_num(num_stds_val, is_english)
    ctx["Average_of_First_Student"] = to_arabic_num(top_avg_val, is_english)
    ctx["sequence_ON"] = bool(rank_str_val)
    ctx["Back_page"] = ""
    ctx["not_first_page"] = False
    ctx["attempt"] = "First" if is_english else "الأول"


def transform_raw_payload_to_context(data: Dict[str, Any], is_english: bool = False, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Transforms raw multi-resultset database payload into rich Jinja2/docxtpl context dictionary.
    Encapsulated via sub-functions to cleanly process dates, numbers, averages, grades, 
    stage pairings, and attempts.
    """
    ctx: Dict[str, Any] = {}
    
    _format_demographics(ctx, data, is_english)
    _format_average_and_grade(ctx, is_english)
    
    raw_courses = data.get("courses_grouped") or []
    _format_second_round_courses(ctx, raw_courses, is_english)
    _format_attempts(ctx, raw_courses, is_english)
    
    timeline = data.get("academic_timeline") or []
    _format_failed_years(ctx, timeline, is_english)
    
    _format_paired_semesters(ctx, data, raw_courses, is_english)
    _format_sequence_and_rank(ctx, is_english)
    
    ctx["signers"] = data.get("signers") or []

    if options:
        ctx["Summer_ON"] = bool(options.get("opt_summer"))
        ctx["Summer_Training_year"] = to_arabic_num(options.get("summer_year") or "", is_english)

    # Merge enriched ctx back into data structure
    data.update(ctx)
    return data


# =============================================================================
# 5. Master Orchestrator Wrapper (`get_certificate_payload`)
# =============================================================================

def get_certificate_payload(
    student_id: int,
    grouping_mode: str = "DEFAULT",
    config_override: Optional[Dict[str, Any]] = None,
    is_english: bool = False
) -> Dict[str, Any]:
    """
    Master Orchestrator Wrapper for Certificate Generation:
      1. Fetch Raw Data from Database (Online API / Direct MySQL SP / Offline SQLite replica)
      2. Process & Transform Data (dates, numbers, averages, grades, stage pairings, attempts, failed years)
      3. Pass Context to Word Templates (returns clean Jinja2 ready-to-render context dictionary)
    """
    raw_payload = fetch_raw_certificate_data(
        student_id=student_id,
        grouping_mode=grouping_mode,
        config_override=config_override
    )
    enriched_context = transform_raw_payload_to_context(raw_payload, is_english=is_english)
    return enriched_context


def _execute_fallback_subprocedures(cur, student_id: int, grouping_mode: str) -> List[List[Dict[str, Any]]]:
    """
    Fallback method that executes individual sub-procedures sequentially if master SP fails.
    """
    datasets = []
    sp_calls = [
        ("sp_GetCertificate_UniversitySettings", ()),
        ("sp_GetCertificate_StudentInfo", (student_id,)),
        ("sp_GetCertificate_Ranking", (student_id,)),
        ("sp_GetCertificate_Signers", ()),
        ("sp_GetCertificate_AcademicTimeline", (student_id,)),
        ("sp_GetCertificate_AcademicCourses", (student_id, grouping_mode)),
    ]

    for sp_name, args in sp_calls:
        try:
            cur.callproc(sp_name, args)
            rows = []
            if hasattr(cur, "stored_results"):
                for res in cur.stored_results():
                    rows.extend(res.fetchall())
            else:
                rows = cur.fetchall()
            datasets.append(rows)
            try:
                while cur.nextset(): pass
            except Exception: pass
        except Exception as sub_err:
            log.warning("Fallback SP %s failed: %s", sp_name, sub_err)
            datasets.append([])

    return datasets


# =============================================================================
# 6. Standalone Execution Block (`if __name__ == "__main__":`)
# =============================================================================

if __name__ == "__main__":
    import argparse
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Certificate Repository Debugger & Standalone Data Fetcher")
    parser.add_argument("student_id", nargs="?", type=int, help="Target Student ID (e.g. 2138 or 12)")
    parser.add_argument("--student", type=int, help="Target Student ID")
    parser.add_argument("--mode", type=str, default="DEFAULT", help="Grouping Mode (DEFAULT, BY_PERIOD_STAGE, BY_CURRICULUM_STAGE, etc.)")
    parser.add_argument("--english", action="store_true", help="Format payload for English transcript template")
    parser.add_argument("--host", type=str, help="MySQL DB Host override")
    parser.add_argument("--database", type=str, help="MySQL Database name override")
    args = parser.parse_args()

    # Determine Student ID
    target_student_id = args.student_id or args.student

    if target_student_id is None:
        print("\n=====================================================================")
        print("  Certificate Repository Layer — Standalone Debugging Mode")
        print("=====================================================================")
        user_input = input("Enter Student ID to inspect [default: 2138]: ").strip()
        if user_input.isdigit():
            target_student_id = int(user_input)
        else:
            target_student_id = 2138

    print(f"\n[cert_repository] Fetching certificate payload for Student ID: {target_student_id} (Mode: {args.mode})...\n")

    override = {}
    if args.host: override["host"] = args.host
    if args.database: override["database"] = args.database

    try:
        payload = get_certificate_payload(
            student_id=target_student_id,
            grouping_mode=args.mode,
            config_override=override if override else None,
            is_english=args.english
        )

        print("\n=====================================================================")
        print("  RAW & TRANSFORMED PAYLOAD DICTIONARY (JSON PRETTY-PRINT)")
        print("=====================================================================")
        print(json.dumps(payload, indent=4, ensure_ascii=False, default=str))

        print("\n=====================================================================")
        print("  DATA STRUCTURE SUMMARY VERIFICATION")
        print("=====================================================================")
        print(f"  Student Name (AR)   : {payload.get('student_name_ar')}")
        print(f"  Student Name (EN)   : {payload.get('student_name_en')}")
        print(f"  Department (AR)     : {payload.get('dept_name_ar')}")
        print(f"  Study System        : {payload.get('study_system_name_ar')} ({payload.get('period_display')})")
        print(f"  Graduation Year     : {payload.get('graduation_year')}")
        print(f"  Average             : {payload.get('average_formatted')} ({payload.get('academic_grade')})")
        print(f"  Rank / Total        : {payload.get('rank')} / {payload.get('total_graduates')}")
        print(f"  Total Courses       : {len(payload.get('courses_grouped', []))}")
        print(f"  Paired Semesters    : {len(payload.get('paired_semesters', []))} pairs")
        print(f"  Second Round Count  : {payload.get('second_round_count')} courses ({payload.get('second_trial_subjects')})")
        print(f"  Deferred Years      : {payload.get('deferred_years')}")
        print(f"  Signers Count       : {len(payload.get('signers', []))}")
        print("=====================================================================\n")

    except Exception as e:
        print(f"\n[ERROR] Failed to fetch certificate payload: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
