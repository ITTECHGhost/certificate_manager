# =============================================================================
# nicegui_ui/issue_helpers.py — Pure helpers for the "إصدار كتاب" screen
#
# Template names (two lines), the template list for a study system, the three
# sources of the graduates count, and the transcript grouped by year/semester.
# Nothing here touches the Word template context.
# =============================================================================

from __future__ import annotations

import re

from nicegui_ui.template_constants import get_template_info, normalize_gender, template_tags

TITLE_BY_SYSTEM = {
    "annual": "وثيقة تخرج — النظام الفصلي",
    "semester": "وثيقة تخرج — نظام المقررات",
    "master": "وثيقة ماجستير",
}


def _is_generated_name(name: str) -> bool:
    """True for the old standard names ('Ar, Annual, SBS, cr'), which the user never chose."""
    return bool(re.match(r"^\s*(ar|en)\s*,", name or "", re.I)) or not (name or "").strip()


def template_lines(raw_name: str | None) -> tuple[str, str]:
    """(name, variant): the name the user gave the template in Settings, then 'عربي • بالدرجات'.

    Templates still carrying a generated name get 'وثيقة تخرج — النظام السنوي' instead.
    """
    info = get_template_info(raw_name)
    tags = template_tags(raw_name)
    name = str(info.get("display_name") or "")
    if _is_generated_name(name):
        name = TITLE_BY_SYSTEM.get(tags["system"].lower(), tags["system_ar"])
    variant = f"{tags['lang_ar']} • {tags['marks_ar']}"
    if tags["gender"] != "Any":
        variant += f" • {tags['gender_ar']}"
    return name, variant


def template_option_label(raw_name: str | None) -> str:
    """The two lines joined by a newline; the select's slots draw them as two lines."""
    return "\n".join(template_lines(raw_name))


def student_system(data: dict | None) -> str:
    """'semester', 'annual' or '' (unknown) from the student's study system data."""
    data = data or {}
    text = " ".join(str(data.get(k) or "") for k in ("period_display", "calculation_rule")).lower()
    if "semester" in text:
        return "semester"
    if "year" in text or "annual" in text:
        return "annual"
    return ""


def filter_templates_for_system(files: list[str], data: dict | None) -> list[str]:
    """The student's study system, then their gender; a step that would leave nothing is skipped."""
    by_system = _filter_by_system(files, data)
    gender = student_gender(data)
    if not gender:
        return by_system
    matching = [f for f in by_system if template_tags(f)["gender"] in (gender, "Any")]
    return matching or by_system


def student_gender(data: dict | None) -> str:
    """'Male' / 'Female' / '' — the certificate data keeps it under student_info."""
    data = data or {}
    info = data.get("student_info") if isinstance(data.get("student_info"), dict) else {}
    return normalize_gender(info.get("gender") if info.get("gender") is not None else data.get("gender"))


def _filter_by_system(files: list[str], data: dict | None) -> list[str]:
    """Only the templates of the student's study system; all of them when it is unknown."""
    # A template tagged with a study-system name matches students of that system by name
    name = str((data or {}).get("study_system_name_ar") or (data or {}).get("study_system_ar") or "").strip()
    if name:
        named = [f for f in files if template_tags(f)["system_name"] == name]
        if named:
            return named
    system = student_system(data)
    if not system:
        return list(files)
    wanted = "Semester" if system == "semester" else "Annual"
    matching = [f for f in files if template_tags(f)["system"] == wanted]
    return matching or list(files)


GRADUATES_SOURCES = {
    "order": "أمر التخرج",
    "student": "معلومات الطالب",
    "manual": "إدخال يدوي",
}


def graduates_count(source: str, data: dict | None, manual: str = "") -> str:
    """The graduates count from one of the three sources; '' when that source has none."""
    data = data or {}
    if source == "order":
        val = data.get("order_num_students")
    elif source == "student":
        val = data.get("postgraduation_number")
    else:
        val = manual
    return "" if val is None else str(val).strip()


def group_transcript(courses: list[dict], is_semester: bool) -> list[dict]:
    """Courses grouped by stage and year (and semester), in order of first appearance.

    Each group: {"header": "المرحلة 1 • 2020-2021", "courses": [...]}.
    """
    groups: dict[tuple, dict] = {}
    for c in courses or []:
        stg = c.get("period_stage") or c.get("stage_number") or c.get("course_curriculum_stage") or ""
        year = str(c.get("academic_year_formatted") or c.get("academic_year") or "")
        sem = c.get("semester_num") if is_semester else None
        key = (str(stg), year, str(sem or ""))
        if key not in groups:
            parts = [f"المرحلة {stg}" if stg else "", year]
            if sem:
                parts.append(f"الفصل {sem}")
            groups[key] = {"header": " • ".join(p for p in parts if p) or "—", "courses": []}
        groups[key]["courses"].append(c)
    return list(groups.values())
