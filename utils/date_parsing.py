"""One place that reads what people type into date and academic-year fields.

parse_date("13.10.2025")        -> "2025-10-13"   (the app's one date format)
format_academic_year("25/26")   -> "2025/2026"    (the app's one academic-year format)
academic_year_start("2025/2026") -> 2025
Both parsers return None for text they cannot read; "" stays "".
"""
from __future__ import annotations

import re
from datetime import date

_SEP = re.compile(r"[\s\-/.]+")


def _valid(y: int, m: int, d: int) -> str | None:
    if not 1900 <= y <= 2100:
        return None
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def parse_date(text) -> str | None:
    """Read a typed date and return it as YYYY-MM-DD.

    Separators: '-', '/', '.', spaces (any mix). Order: year first or day first.
    Digits only: YYYYMMDD or DDMMYYYY. Returns "" for empty input, None if invalid.
    """
    if text is None:
        return ""
    s = str(text).strip()
    if not s:
        return ""
    # Arabic-Indic digits → ASCII
    s = s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
    if s.isdigit():
        if len(s) != 8:
            return None
        return _valid(int(s[:4]), int(s[4:6]), int(s[6:])) or _valid(int(s[4:]), int(s[2:4]), int(s[:2]))
    parts = [p for p in _SEP.split(s) if p]
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    a, b, c = parts
    if len(a) == 4:
        return _valid(int(a), int(b), int(c))
    if len(c) == 4:
        return _valid(int(c), int(b), int(a))
    return None


def _year(token: str) -> int | None:
    if not token.isdigit():
        return None
    if len(token) == 2:
        return 2000 + int(token)
    if len(token) == 4:
        return int(token)
    return None


def format_academic_year(text) -> str | None:
    """Read an academic year and return it as 'YYYY/YYYY+1'.

    Accepts 2025, 2025-2026, 2025/2026, 2025 2026, 25/26, 2025-26.
    A single year Y becomes Y/Y+1. Returns "" for empty input, None if invalid.
    """
    if text is None:
        return ""
    s = str(text).strip()
    if not s:
        return ""
    s = s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
    parts = [p for p in _SEP.split(s) if p]
    if len(parts) == 1:
        y = _year(parts[0]) if len(parts[0]) == 4 else None
        return f"{y}/{y + 1}" if y and 1900 <= y <= 2100 else None
    if len(parts) != 2:
        return None
    y1, y2 = _year(parts[0]), _year(parts[1])
    if y1 is None or y2 is None or not 1900 <= y1 <= 2100:
        return None
    if len(parts[1]) == 2 and len(parts[0]) == 4:
        y2 = y1 // 100 * 100 + int(parts[1])
    if y2 != y1 + 1:
        return None
    return f"{y1}/{y2}"


def academic_year_start(text) -> int | None:
    """First calendar year of an academic year in any accepted form ('2025/2026' -> 2025)."""
    f = format_academic_year(text)
    return int(f[:4]) if f else None


def academic_year_from_date(text) -> str:
    """Academic year in the Y/Y+1 form for a date: the year of the date, then the next one."""
    d = parse_date(text)
    return f"{int(d[:4])}/{int(d[:4]) + 1}" if d else ""
