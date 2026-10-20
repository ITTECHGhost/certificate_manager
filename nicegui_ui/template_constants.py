# =============================================================================
# nicegui_ui/template_constants.py — Certificate Template Registry & Helpers
# =============================================================================

import os
import json
import logging
from typing import Dict, Any, List, Optional

log = logging.getLogger(__name__)

TEMPLATES_DIR = "templets"
CONFIG_FILE = os.path.join(TEMPLATES_DIR, "templates_config.json")

# Standard abbreviation and terminology legend (aligned with official naming)
TEMPLATE_ABBREVIATIONS = {
    "En": {"ar": "اللغة الإنكليزية", "en": "English Language"},
    "Ar": {"ar": "اللغة العربية", "en": "Arabic Language"},
    "Semester": {"ar": "نظام المقررات (فصلي)", "en": "Semester Course System"},
    "Annual": {"ar": "النظام السنوي", "en": "Annual / Yearly System"},
    "Master": {"ar": "الماجستير (دراسات عليا)", "en": "Master's Degree"},
    "SBS": {"ar": "درجات مقترنة جنباً إلى جنب", "en": "Side-By-Side Courses"},
    "cr": {"ar": "وثيقة تخرج رسمية", "en": "Certificate"},
    "Temp": {"ar": "ملف قالب Word", "en": "Template File"},
    "D": {"ar": "كشف درجات تفصيلي", "en": "Detailed Transcript"},
}

# The 10 canonical templates required by specification
# Format: [Language: En|Ar], [System: Semester|Annual|Master], [SBS if paired], cr
DEFAULT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "semester - Temp - En": {
        "display_name": "En, Semester, cr",
        "file": "semester - Temp - En.docx",
        "lang": "En",
        "lang_ar": "إنكليزي",
        "system": "Semester",
        "system_ar": "نظام المقررات (فصلي)",
        "sbs": False,
        "type_ar": "بدون درجات",
    },
    "semester - Temp - En - D - SBS": {
        "display_name": "En, Semester, SBS, cr",
        "file": "semester - Temp - En - D - SBS.docx",
        "lang": "En",
        "lang_ar": "إنكليزي",
        "system": "Semester",
        "system_ar": "نظام المقررات (فصلي)",
        "sbs": True,
        "type_ar": "درجات مقترنة SBS",
    },
    "semester - Temp - Ar": {
        "display_name": "Ar, Semester, cr",
        "file": "semester - Temp - Ar.docx",
        "lang": "Ar",
        "lang_ar": "عربي",
        "system": "Semester",
        "system_ar": "نظام المقررات (فصلي)",
        "sbs": False,
        "type_ar": "بدون درجات",
    },
    "semester - Temp - Ar - D - SBS": {
        "display_name": "Ar, Semester, SBS, cr",
        "file": "semester - Temp - Ar - D - SBS.docx",
        "lang": "Ar",
        "lang_ar": "عربي",
        "system": "Semester",
        "system_ar": "نظام المقررات (فصلي)",
        "sbs": True,
        "type_ar": "درجات مقترنة SBS",
    },
    "year - Temp - En": {
        "display_name": "En, Annual, cr",
        "file": "year - Temp - En.docx",
        "lang": "En",
        "lang_ar": "إنكليزي",
        "system": "Annual",
        "system_ar": "النظام السنوي",
        "sbs": False,
        "type_ar": "بدون درجات",
    },
    "year - Temp - En - D - SBS": {
        "display_name": "En, Annual, SBS, cr",
        "file": "year - Temp - En - D - SBS.docx",
        "lang": "En",
        "lang_ar": "إنكليزي",
        "system": "Annual",
        "system_ar": "النظام السنوي",
        "sbs": True,
        "type_ar": "درجات مقترنة SBS",
    },
    "year - Temp - Ar": {
        "display_name": "Ar, Annual, cr",
        "file": "year - Temp - Ar.docx",
        "lang": "Ar",
        "lang_ar": "عربي",
        "system": "Annual",
        "system_ar": "النظام السنوي",
        "sbs": False,
        "type_ar": "بدون درجات",
    },
    "year - Temp - Ar - D - SBS": {
        "display_name": "Ar, Annual, SBS, cr",
        "file": "year - Temp - Ar - D - SBS.docx",
        "lang": "Ar",
        "lang_ar": "عربي",
        "system": "Annual",
        "system_ar": "النظام السنوي",
        "sbs": True,
        "type_ar": "درجات مقترنة SBS",
    },
    "master - Temp - Ar": {
        "display_name": "Ar, Master, cr",
        "file": "master - Temp - Ar.docx",
        "lang": "Ar",
        "lang_ar": "عربي",
        "system": "Master",
        "system_ar": "ماجستير (دراسات عليا)",
        "sbs": False,
        "type_ar": "وثيقة ماجستير",
    },
    "master - Temp - En": {
        "display_name": "En, Master, cr",
        "file": "master - Temp - En.docx",
        "lang": "En",
        "lang_ar": "إنكليزي",
        "system": "Master",
        "system_ar": "ماجستير (دراسات عليا)",
        "sbs": False,
        "type_ar": "وثيقة ماجستير",
    },
}


def load_templates_config() -> Dict[str, Dict[str, Any]]:
    """Loads custom and default template metadata from templets/templates_config.json."""
    if not os.path.exists(TEMPLATES_DIR):
        try:
            os.makedirs(TEMPLATES_DIR, exist_ok=True)
        except Exception:
            pass

    config_data: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    config_data = loaded
        except Exception as e:
            log.warning(f"Could not read {CONFIG_FILE}: {e}")

    # Merge default templates if not present in config
    merged = dict(DEFAULT_TEMPLATES)
    merged.update(config_data)
    return merged


def save_templates_config(config_data: Dict[str, Dict[str, Any]]) -> bool:
    """Persists template metadata dictionary to templets/templates_config.json."""
    try:
        if not os.path.exists(TEMPLATES_DIR):
            os.makedirs(TEMPLATES_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log.error(f"Failed to save {CONFIG_FILE}: {e}")
        return False


def register_template(key_or_filename: str, display_name: str, **meta) -> bool:
    """
    Registers a new template or updates an existing template's display name and metadata.
    """
    key = normalize_template_key(key_or_filename)
    if not key:
        return False

    config = load_templates_config()
    existing = config.get(key, {})

    filename = meta.get("file") or existing.get("file") or f"{key}.docx"
    lang = meta.get("lang") or existing.get("lang") or ("En" if "en" in display_name.lower() or "en" in key.lower() else "Ar")
    system = meta.get("system") or existing.get("system") or ("Semester" if "sem" in display_name.lower() or "sem" in key.lower() else ("Master" if "master" in display_name.lower() or "master" in key.lower() else "Annual"))
    sbs = meta.get("sbs") if "sbs" in meta else existing.get("sbs", ("sbs" in display_name.lower() or "sbs" in key.lower()))

    config[key] = {
        "display_name": display_name.strip(),
        "file": filename,
        "lang": lang,
        "lang_ar": "عربي" if lang.lower() == "ar" else "إنكليزي",
        "system": system,
        "system_ar": "نظام المقررات (فصلي)" if system.lower() == "semester" else ("ماجستير (دراسات عليا)" if system.lower() == "master" else "النظام السنوي"),
        "sbs": bool(sbs),
        "type_ar": "درجات مقترنة SBS" if sbs else "بدون درجات",
    }
    return save_templates_config(config)


def delete_template_config(key_or_filename: str) -> bool:
    """Removes a template from templates_config.json."""
    key = normalize_template_key(key_or_filename)
    config = load_templates_config()
    if key in config:
        del config[key]
        return save_templates_config(config)
    return False


# In-memory dictionary for backwards compatibility
TEMPLATE_REGISTRY = load_templates_config()


def normalize_template_key(raw_name: Optional[str]) -> str:
    """Strips file extension and trailing spaces to get clean template key."""
    if not raw_name:
        return ""
    clean = str(raw_name).strip()
    if clean.lower().endswith(".docx"):
        clean = clean[:-5].strip()
    return clean


def get_template_info(raw_name: Optional[str]) -> Dict[str, Any]:
    """
    Retrieves metadata for any template string, key, or filename.
    Never returns any reference to 'general' or 'عامة'.
    """
    key = normalize_template_key(raw_name)
    config = load_templates_config()

    # 1. Exact key match
    if key in config:
        info = dict(config[key])
        info.setdefault("name_ar", info.get("display_name"))
        info.setdefault("short_ar", info.get("display_name"))
        return info

    # 2. Check if raw_name matches any display_name or file directly
    for k, v in config.items():
        if v.get("display_name", "").lower() == str(raw_name or "").lower().strip():
            info = dict(v)
            info.setdefault("name_ar", info.get("display_name"))
            info.setdefault("short_ar", info.get("display_name"))
            return info
        if v.get("file", "").lower() == str(raw_name or "").lower().strip():
            info = dict(v)
            info.setdefault("name_ar", info.get("display_name"))
            info.setdefault("short_ar", info.get("display_name"))
            return info

    # 3. Dynamic heuristic mapping for legacy database records
    # (e.g. 'year - Temp - Ar - D - SBS', 'graduation', 'ARABIC', 'English')
    lower = key.lower()
    is_en = "en" in lower or "english" in lower
    is_master = "master" in lower
    is_sem = "sem" in lower
    is_sbs = "sbs" in lower or "grade" in lower or "d -" in lower or "درجات" in lower

    lang_code = "En" if is_en else "Ar"
    if is_master:
        sys_code = "Master"
    elif is_sem:
        sys_code = "Semester"
    else:
        sys_code = "Annual"

    # Assemble canonical name: [Lang], [System], [SBS, ]cr
    parts = [lang_code, sys_code]
    if is_sbs and not is_master:
        parts.append("SBS")
    parts.append("cr")
    display_name = ", ".join(parts)

    return {
        "display_name": display_name,
        "name_ar": display_name,
        "short_ar": display_name,
        "file": f"{key}.docx" if key else "year - Temp - Ar.docx",
        "lang": lang_code,
        "lang_ar": "إنكليزي" if is_en else "عربي",
        "system": sys_code,
        "system_ar": "نظام المقررات (فصلي)" if is_sem else ("ماجستير (دراسات عليا)" if is_master else "النظام السنوي"),
        "sbs": is_sbs,
        "type_ar": "درجات مقترنة SBS" if is_sbs else "بدون درجات",
    }


def get_friendly_template_name(raw_name: Optional[str], include_file: bool = False) -> str:
    """
    Returns the standard template name (e.g. 'Ar, Annual, SBS, cr').
    Never uses 'General' or 'عامة'.
    """
    if not raw_name:
        return "Ar, Annual, cr"
    info = get_template_info(raw_name)
    disp = info.get("display_name") or "Ar, Annual, cr"
    if include_file and info.get("file"):
        return f"{disp} [{info['file']}]"
    return disp


def get_short_template_badge(raw_name: Optional[str]) -> str:
    """
    Returns the compact badge label (e.g. 'Ar, Semester, SBS, cr') for table cells.
    """
    if not raw_name:
        return "Ar, Annual, cr"
    info = get_template_info(raw_name)
    return info.get("display_name") or "Ar, Annual, cr"


def get_template_filter_options() -> Dict[str, str]:
    """
    Returns dictionary for the template filter dropdown in Issued Certificates screen.
    Begins with 'all' followed strictly by the standard template names.
    """
    options: Dict[str, str] = {
        "all": "كل النماذج / All Templates"
    }
    config = load_templates_config()
    for _, item in config.items():
        d_name = item.get("display_name")
        if d_name and d_name not in options:
            options[d_name] = d_name

    # Ensure canonical 10 are always present in specified order
    canonical_order = [
        "En, Semester, cr",
        "En, Semester, SBS, cr",
        "Ar, Semester, cr",
        "Ar, Semester, SBS, cr",
        "En, Annual, cr",
        "En, Annual, SBS, cr",
        "Ar, Annual, cr",
        "Ar, Annual, SBS, cr",
        "Ar, Master, cr",
        "En, Master, cr",
    ]
    for c in canonical_order:
        if c not in options:
            options[c] = c

    return options
