# =============================================================================
# services/certificate_context.py — pure helpers that build the docxtpl context
# =============================================================================
# Moved from nicegui_screens/certificate_screen.py, which re-imports every name.

import re
from itertools import zip_longest


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
    latest_period_for_stage = {}

    for c in courses_grouped:
        c_key = c.get("subject_name") or c.get("course_name_ar") or c.get("name_ar") or c.get("course_id")
        if c_key:
            course_groups[c_key].append(dict(c))

        # Track the latest academic period for each stage
        p_stg = parse_stage_num(c.get("period_stage") or c.get("stage_number"), 1)
        yr = str(c.get("academic_year") or "").strip()
        if yr:
            if p_stg not in latest_period_for_stage:
                latest_period_for_stage[p_stg] = c
            else:
                curr_yr = str(latest_period_for_stage[p_stg].get("academic_year") or "").strip()
                if yr > curr_yr:
                    latest_period_for_stage[p_stg] = c

    consolidated_list = []

    for c_key, group in course_groups.items():
        # Sort chronologically by academic_year, period_stage/stage_number, semester_num
        group.sort(key=lambda x: (
            str(x.get("academic_year") or ""),
            parse_stage_num(x.get("stage_number") or x.get("period_stage"), 1),
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

        best_passed = passing_entries[-1]  # Latest passed attempt
        earliest_attempt = group[0]         # First attempt
        latest_attempt = group[-1]         # Latest / retaken attempt

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

        is_carry_over = False
        ctype = latest_attempt.get("course_type", "")
        if ctype == "عبور":
            is_carry_over = True
        else:
            c_stg = latest_attempt.get("course_curriculum_stage")
            p_stg = latest_attempt.get("period_stage") or latest_attempt.get("stage_number")
            if c_stg is not None and p_stg is not None:
                if parse_stage_num(c_stg, 1) < parse_stage_num(p_stg, 1):
                    is_carry_over = True

        # Preserve the authentic grouping_key and fields from the database Stored Procedure / API
        if best_passed.get("grouping_key"):
            final_item["grouping_key"] = best_passed["grouping_key"]
            if best_passed.get("academic_year"):
                final_item["academic_year"] = best_passed["academic_year"]
            if best_passed.get("academic_year_formatted"):
                final_item["academic_year_formatted"] = best_passed["academic_year_formatted"]
            if best_passed.get("stage_number"):
                final_item["stage_number"] = best_passed["stage_number"]
            if best_passed.get("semester_num"):
                final_item["semester_num"] = best_passed["semester_num"]
        else:
            course_stg = parse_stage_num(best_passed.get("course_curriculum_stage") or best_passed.get("period_stage") or best_passed.get("stage_number"), 1)
            target_info = latest_period_for_stage.get(course_stg) or best_passed

            if is_annual:
                # Rule A: Annual System
                pass_year = target_info.get("academic_year")
                pass_year_fmt = target_info.get("academic_year_formatted")
                stage_num = course_stg
                sem_num = parse_stage_num(best_passed.get("semester_num") or earliest_attempt.get("semester_num"), 1)

                final_item["stage_number"] = stage_num
                final_item["semester_num"] = sem_num
                if pass_year:
                    final_item["academic_year"] = pass_year
                if pass_year_fmt:
                    final_item["academic_year_formatted"] = pass_year_fmt

                backend_gkey = target_info.get("grouping_key")
                final_item["grouping_key"] = backend_gkey or f"{pass_year}_{stage_num}_{sem_num}"
            else:
                # Rule B: Semester System
                pass_year = target_info.get("academic_year")
                pass_year_fmt = target_info.get("academic_year_formatted")
                pass_stg = course_stg
                pass_sem = parse_stage_num(best_passed.get("semester_num"), 1)

                final_item["stage_number"] = pass_stg
                final_item["semester_num"] = pass_sem
                if pass_year:
                    final_item["academic_year"] = pass_year
                if pass_year_fmt:
                    final_item["academic_year_formatted"] = pass_year_fmt

                backend_gkey = target_info.get("grouping_key")
                final_item["grouping_key"] = backend_gkey or f"{pass_year}_{pass_stg}_{pass_sem}"

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
    """Formats YYYY-MM-DD date strings into visual YYYY/MM/DD order with Eastern Arabic numerals for RTL display."""
    if not val:
        return ""
    s = str(val).strip()
    match = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", s)
    if match:
        y, m, d = match.groups()
        # Intelligently fix if user accidentally entered YYYY-DD-MM in database (e.g. 2021-20-2)
        if int(m) > 12:
            m, d = d, m
        s = f"{y}/{m.zfill(2)}/{d.zfill(2)}"
    return f"‎{to_arabic_num(s, is_english)}‎"


def format_academic_year_ltr(val: str | None, is_english: bool = False) -> str:
    """
    Ensures academic year range is strictly LTR ordered (smaller year on the left: e.g. 2016-2017 / ٢٠١٦-٢٠١٧).
    Uses Left-to-Right Mark (‎) to prevent RTL text reversal in Word tables.
    """
    if not val:
        return ""
    s = str(val).strip()
    years = re.findall(r"\d{4}", s)
    if len(years) >= 2:
        y1, y2 = int(years[0]), int(years[1])
        smaller, larger = min(y1, y2), max(y1, y2)
        formatted = f"{smaller}-{larger}"
        return f"‎{to_arabic_num(formatted, is_english)}‎"
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
    grouping_mode = str(options.get("grouping_mode") or data.get("grouping_mode") or "DEFAULT").upper()
    if "SEMESTER" in grouping_mode:
        is_annual = False
    elif any(k in grouping_mode for k in ("YEAR", "PERIOD", "CURRICULUM")):
        is_annual = True
    else:
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

    def _group_sort_key(course_list):
        if not course_list:
            return ("", 0, 0)
        c0 = course_list[0]
        ay = str(c0.get("academic_year") or c0.get("academic_year_formatted") or "")
        stg = parse_stage_num(c0.get("stage_number") or c0.get("period_stage"), 1)
        sem = parse_stage_num(c0.get("semester_num"), 1)
        return (ay, stg, sem)

    # Sort group lists chronologically by academic_year ASC, stage ASC, semester ASC
    group_lists = sorted(list(groups_in_order.values()), key=_group_sort_key)
    paired_semesters = []

    stage_names_ar = {1: "الأولى", 2: "الثانية", 3: "الثالثة", 4: "الرابعة", 5: "الخامسة", 6: "السادسة"}
    stage_names_en = {1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth", 6: "Sixth"}

    def _extract_group_stage(course_list, default_val):
        if not course_list:
            return default_val
        p_stages = [c.get("period_stage") for c in course_list if c.get("period_stage")]
        if p_stages:
            return max(p_stages, key=p_stages.count)
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

        def _has_second_round(courses):
            for c in courses:
                pr = str(c.get("passed_round") or "1").strip()
                isr = c.get("is_second_round", 0)
                if pr in ('2', '3') or isr == 1 or pr in (2, 3):
                    return True
            return False

        attempt_right = ("Second" if is_english else "الثاني") if _has_second_round(right_courses) else ("First" if is_english else "الأول")
        attempt_left = (("Second" if is_english else "الثاني") if _has_second_round(left_courses) else ("First" if is_english else "الأول")) if left_courses else ""

        if is_annual:
            paired_semesters.append({
                "left_label": left_year_disp,
                "right_label": right_year_disp,
                "semester_right_label": f"المرحلة {stg_text_right}" if not is_english else f"Stage {stg_text_right}",
                "semester_left_label": (f"المرحلة {stg_text_left}" if not is_english else f"Stage {stg_text_left}") if left_courses else "",
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
                "attempt_right": attempt_right,
                "attempt_left": attempt_left,
            })
        else:
            right_sem_label = "First Semester" if is_english else "الفصل الأول"
            left_sem_label = "Second Semester" if is_english else "الفصل الثاني"
            if sem_right == 3: right_sem_label = "Summer Semester" if is_english else "الفصل الصيفي"
            if sem_left == 3: left_sem_label = "Summer Semester" if is_english else "الفصل الصيفي"

            row_year_display = f"العام الدراسي {right_year_disp}" if (right_year_disp and not is_english) else (f"Academic Year {right_year_disp}" if right_year_disp else "")

            paired_semesters.append({
                "left_label": left_sem_label,
                "right_label": right_sem_label,
                "semester_right_label": right_sem_label,
                "semester_left_label": left_sem_label,
                "sem_right_label": right_sem_label,
                "sem_left_label": left_sem_label,
                "right_semester_label": right_sem_label,
                "left_semester_label": left_sem_label,
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
                "attempt_right": attempt_right,
                "attempt_left": attempt_left,
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
    seq_val = options.get("rank_val") or data.get("rank") or data.get("sequence_number") or (data.get("student_info") or {}).get("sequence_number") or ""
    num_stds = options.get("rank_total") or data.get("total_graduates") or data.get("postgraduation_number") or data.get("order_num_students") or data.get("num_students") or ""
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

    from cert_repository import extract_failed_years, extract_attempts
    raw_timeline = data.get("academic_timeline") or data.get("periods") or []
    failed_years = extract_failed_years(raw_timeline, is_english=is_english)

    user_postpone_text = (options.get("postpone_years") or "").strip()
    if not failed_years and user_postpone_text:
        failed_years = [{
            "year_d": user_postpone_text,
            "stage": "",
            "state": "",
            "year": user_postpone_text,
            "status": "",
            "academic_year": user_postpone_text
        }]

    raw_courses = data.get("courses_grouped") or data.get("courses") or []
    attempts = extract_attempts(raw_courses, is_english=is_english)

    user_second_text = (options.get("second_trial_subjects") or second_subjects or "").strip()
    if not attempts and user_second_text:
        attempts = [{
            "year": "",
            "stage": "",
            "subjects": user_second_text,
            "year_d": "",
            "stage_text": "",
            "academic_year": ""
        }]

    ctx = {
        "Title": title_val,
        "to_title": title_val,
        "student_name": data.get("full_name_en" if is_english else "full_name_ar", ""),
        "Birthday": format_date_rtl(data.get("date_of_birth") or "", is_english),
        "Birthplace": data.get("birthplace_en" if is_english else "birthplace_ar") or data.get("birthplace_other", ""),
        "Nationality": data.get("nationality_en" if is_english else "nationality_ar", ""),
        "national_id": to_arabic_num(data.get("national_id") or options.get("national_id") or "", is_english),
        "National_ID": to_arabic_num(data.get("national_id") or options.get("national_id") or "", is_english),
        "National_id": to_arabic_num(data.get("national_id") or options.get("national_id") or "", is_english),
        "national_number": to_arabic_num(data.get("national_id") or options.get("national_id") or "", is_english),
        "admission_year": format_date_rtl(data.get("admission_year") or "", is_english),
        "graduation_year": format_date_rtl(data.get("graduation_year") or "", is_english),
        "department_id": data.get("dept_name_en" if is_english else "dept_name_ar", ""),
        "study_type": study_type_disp,
        "graduation_date": format_date_rtl(data.get("graduation_date") or "", is_english),
        "graduation_semester": grad_sem_text,
        "average": to_arabic_num(avg_str, is_english),
        "Grade": grade,
        "sequence_ON": bool(options.get("opt_rank")),
        "Failure_ON": bool(options.get("opt_postpone")),
        "failure_on": bool(options.get("opt_postpone")),
        "FAILURE_ON": bool(options.get("opt_postpone")),
        "failed_years": failed_years,
        "Passed_ON": bool(options.get("opt_second_trial")),
        "passed_on": bool(options.get("opt_second_trial")),
        "PASSED_ON": bool(options.get("opt_second_trial")),
        "attempts": attempts,
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
        "Back_page": "",
        "not_first_page": False,
        "attempt": "First" if is_english else "الأول",
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
