# =============================================================================
# cert_repository.py — Certificate Generation Database Repository & Transformation Layer
# =============================================================================
#
# PURPOSE:
#   Extracts and modularizes all database querying, stored procedure execution,
#   and data-transformation logic required for generating student certificates.
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

import mysql.connector
from mysql.connector import pooling

# Ensure workspace root is in sys.path for config imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import DBConfig
except ImportError:
    class DBConfig:
        DB_HOST = "localhost"
        DB_USER = "root"
        DB_PASSWORD = "12345678"
        DB_NAME = "certificate_manager"

log = logging.getLogger("cert_repository")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


# =============================================================================
# 1. Database Connection & Configuration Management
# =============================================================================

def load_db_config(config_path: str = "config.ini", config_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Dynamically resolves MySQL connection parameters with 4-tier fallbacks:
      1. Explicit `config_override` dictionary
      2. Configuration INI/JSON file (`config.ini` or `server_config.json`)
      3. Environment variables (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)
      4. Default `DBConfig` / safe fallbacks (localhost:3306, root, 12345678, certificate_manager)
    """
    cfg = {
        "host": DBConfig.DB_HOST,
        "port": 3306,
        "user": DBConfig.DB_USER,
        "password": DBConfig.DB_PASSWORD,
        "database": DBConfig.DB_NAME,
        "charset": "utf8mb4",
        "collation": "utf8mb4_unicode_ci",
    }

    # 1. Try reading config.ini file if it exists
    ini_file = Path(config_path)
    if not ini_file.exists():
        ini_file = Path(__file__).parent / "config.ini"

    if ini_file.exists():
        try:
            parser = configparser.ConfigParser()
            parser.read(str(ini_file), encoding="utf-8")
            if "database" in parser:
                db_sec = parser["database"]
                if "host" in db_sec: cfg["host"] = db_sec["host"]
                if "port" in db_sec: cfg["port"] = int(db_sec["port"])
                if "user" in db_sec: cfg["user"] = db_sec["user"]
                if "password" in db_sec: cfg["password"] = db_sec["password"]
                if "database" in db_sec: cfg["database"] = db_sec["database"]
                if "dbname" in db_sec: cfg["database"] = db_sec["dbname"]
        except Exception as err:
            log.warning("Failed to parse %s: %s", ini_file, err)

    # 2. Try reading server_config.json if config.ini was absent/incomplete
    json_file = Path(__file__).parent / "server_config.json"
    if json_file.exists():
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                jdata = json.load(f)
                if "db_host" in jdata: cfg["host"] = str(jdata["db_host"])
                if "db_port" in jdata: cfg["port"] = int(jdata["db_port"])
                if "db_user" in jdata: cfg["user"] = str(jdata["db_user"])
                if "db_pass" in jdata: cfg["password"] = str(jdata["db_pass"])
                if "db_name" in jdata: cfg["database"] = str(jdata["db_name"])
        except Exception:
            pass

    # 3. Apply Environment Variable Overrides
    if os.environ.get("DB_HOST"): cfg["host"] = os.environ.get("DB_HOST")
    if os.environ.get("DB_PORT"): cfg["port"] = int(os.environ.get("DB_PORT"))
    if os.environ.get("DB_USER"): cfg["user"] = os.environ.get("DB_USER")
    if os.environ.get("DB_PASSWORD"): cfg["password"] = os.environ.get("DB_PASSWORD")
    if os.environ.get("DB_NAME"): cfg["database"] = os.environ.get("DB_NAME")

    # 4. Apply Caller Overrides
    if config_override and isinstance(config_override, dict):
        for k, v in config_override.items():
            if v is not None:
                cfg[k] = v

    return cfg


def get_db_connection(config_override: Optional[Dict[str, Any]] = None) -> mysql.connector.MySQLConnection:
    """
    Creates and returns a live MySQL connection supporting remote servers and dictionary cursors.
    """
    cfg = load_db_config(config_override=config_override)
    log.debug("Connecting to MySQL database '%s' at %s:%s...", cfg["database"], cfg["host"], cfg["port"])
    return mysql.connector.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset=cfg.get("charset", "utf8mb4"),
        collation=cfg.get("collation", "utf8mb4_unicode_ci"),
        connect_timeout=5
    )


# =============================================================================
# 2. Data Formatting & Number Translation Helpers
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
            return f"{p1} - {p2}"
    return to_arabic_num(clean, is_english)


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
    Returns list of dicts: [{'year_d': '2020-2021', 'stage': 'الأولى', 'state': 'تأجيل'}, ...]
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
                    "status": state_text
                })
    return failed_years


def extract_attempts(courses: list, is_english: bool = False) -> list:
    """
    Extracts 2nd/3rd attempt subjects grouped by academic year and stage.
    Returns list of dicts: [{'year': '2020-2021', 'stage': 'الأولى', 'subjects': 'الإنكليزي 1، البرمجة 1'}, ...]
    """
    stage_names_ar = {1: "الأولى", 2: "الثانية", 3: "الثالثة", 4: "الرابعة", 5: "الخامسة", 6: "السادسة"}
    stage_names_en = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth", 6: "Sixth"}
    
    from collections import OrderedDict
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
# 3. Data Transformation & Jinja2 Template Context Generator
# =============================================================================

def transform_raw_payload_to_context(data: Dict[str, Any], is_english: bool = False) -> Dict[str, Any]:
    """
    Transforms raw multi-resultset database payload into rich Jinja2/docxtpl context dictionary.
    Formats paired_semesters via zip_longest, second-round courses, deferred years, and grades.
    """
    student_info = data.get("student_info") or {}
    settings = data.get("settings") or {}
    ranking = data.get("ranking") or {}
    signers = data.get("signers") or []
    timeline = data.get("academic_timeline") or []
    raw_courses = data.get("courses_grouped") or []

    # 1. Basic Demographics & University Settings
    ctx = {
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
        
        "rank": ranking.get("rank") or ranking.get("sequence_number") or "",
        "total_graduates": ranking.get("total_graduates") or ranking.get("num_students") or "",
        "top_average": ranking.get("top_average") or "",
        "average": student_info.get("average") or ranking.get("average"),
    }

    # 2. Average Formatting & Qualitative Grade Calculation
    avg_val = ctx["average"]
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

    # 3. Second-Round Courses Counter, Subject List & Attempts Structure
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

    attempts = extract_attempts(raw_courses, is_english=is_english)
    ctx["attempts"] = attempts
    ctx["Passed_ON"] = len(attempts) > 0
    ctx["passed_on"] = len(attempts) > 0
    ctx["PASSED_ON"] = len(attempts) > 0

    # 4. Deferred / Failed Years & Tracking Structure
    failed_years = extract_failed_years(timeline, is_english=is_english)
    ctx["failed_years"] = failed_years
    ctx["Failure_ON"] = len(failed_years) > 0
    ctx["failure_on"] = len(failed_years) > 0
    ctx["FAILURE_ON"] = len(failed_years) > 0

    deferred_years = [y["year_d"] for y in failed_years if y.get("status") in ("تأجيل", "Postponed")]
    ctx["deferred_years"] = deferred_years
    ctx["has_deferred_years"] = len(deferred_years) > 0

    # 5. Paired Semesters / Year Columns Construction for Word Templates via zip_longest
    grouping_mode = str(data.get("grouping_mode") or "DEFAULT").upper()
    period_disp = str(ctx["period_display"]).lower()
    is_annual = (period_disp == "year") or ("SEMESTER" not in grouping_mode and ("YEAR" in grouping_mode or "PERIOD" in grouping_mode))

    courses_grouped = consolidate_courses_for_certificate(raw_courses, is_annual=is_annual)
    
    from collections import OrderedDict
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
        })

    ctx["paired_semesters"] = paired_semesters
    ctx["signers"] = signers

    # Merge enriched ctx back into data structure
    data.update(ctx)
    return data


# =============================================================================
# 4. Master Orchestrator Wrapper (`get_certificate_payload`)
# =============================================================================

def get_certificate_payload(
    student_id: int,
    grouping_mode: str = "DEFAULT",
    config_override: Optional[Dict[str, Any]] = None,
    is_english: bool = False
) -> Dict[str, Any]:
    """
    Executes stored procedures to fetch and assemble complete certificate payload.
    Iterates sequentially through all 6 result sets returned by `sp_GetFullCertificateData`:
      1. University Settings
      2. Student Info & Demographics
      3. Ranking & Averages
      4. Signers
      5. Academic Timeline
      6. Course Enrollment Grid
      
    Returns enriched dictionary ready for Jinja2 Word template processing.
    """
    conn = get_db_connection(config_override=config_override)
    cur = conn.cursor(dictionary=True)
    datasets = []

    try:
        log.info("Executing sp_GetFullCertificateData for student_id=%s, mode=%s...", student_id, grouping_mode)
        cur.callproc("sp_GetFullCertificateData", (student_id, grouping_mode))
        
        if hasattr(cur, "stored_results"):
            for result in cur.stored_results():
                datasets.append(result.fetchall())
        else:
            datasets.append(cur.fetchall())
            
        try:
            while cur.nextset():
                pass
        except Exception:
            pass

    except mysql.connector.Error as db_err:
        log.warning("sp_GetFullCertificateData execution failed: %s. Executing fallback sub-procedures...", db_err)
        datasets = _execute_fallback_subprocedures(cur, student_id, grouping_mode)
    finally:
        cur.close()
        conn.close()

    # Assemble raw payload dictionary from result sets
    raw_payload = {
        "student_id": student_id,
        "grouping_mode": grouping_mode,
        "settings": datasets[0][0] if (len(datasets) > 0 and datasets[0]) else {},
        "student_info": datasets[1][0] if (len(datasets) > 1 and datasets[1]) else {},
        "ranking": datasets[2][0] if (len(datasets) > 2 and datasets[2]) else {},
        "signers": datasets[3] if (len(datasets) > 3 and datasets[3]) else [],
        "academic_timeline": datasets[4] if (len(datasets) > 4 and datasets[4]) else [],
        "courses_grouped": datasets[5] if (len(datasets) > 5 and datasets[5]) else [],
    }

    # Apply data transformations for template context
    enriched_payload = transform_raw_payload_to_context(raw_payload, is_english=is_english)
    return enriched_payload


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
# 5. Standalone Execution Block (`if __name__ == "__main__":`)
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
