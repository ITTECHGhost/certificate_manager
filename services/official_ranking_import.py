# =============================================================================
# services/official_ranking_import.py — reads an official ranking list from Excel
# The sheet student affairs prints with the order: a header row with «ت» and «الاسم»
# (and usually «المعدل», «الدور»), then one row per graduate in the order's sequence.
# =============================================================================

import re

HEADER_WORDS = {
    "position": ("ت", "التسلسل", "تسلسل", "#"),
    "name": ("الاسم", "اسم الطالب", "الاسم الثلاثي", "الاسم الرباعي"),
    "average": ("المعدل", "معدل التخرج"),
    "round": ("الدور",),
}


def _clean(v) -> str:
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip()


def _header_map(row) -> dict:
    found = {}
    for idx, cell in enumerate(row):
        text = _clean(cell)
        for key, words in HEADER_WORDS.items():
            if key not in found and text in words:
                found[key] = idx
    return found if "name" in found else {}


def _to_float(v):
    try:
        return float(str(v).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def parse_rows(rows) -> list:
    """[{position, name_written, average, round}] from the sheet's rows (lists of cell values).
    Rows before the header and rows without a name are skipped. A missing «ت» column
    numbers the names in sheet order."""
    rows = list(rows)
    cols, start = {}, 0
    for i, row in enumerate(rows[:30]):
        cols = _header_map(row)
        if cols:
            start = i + 1
            break
    if not cols:
        raise ValueError("لم أجد صف العناوين: يجب أن يحتوي على عمود «الاسم».")
    out, seq = [], 0
    for row in rows[start:]:
        cells = list(row) + [None] * 10
        name = _clean(cells[cols["name"]])
        if not name or name in HEADER_WORDS["name"]:
            continue
        seq += 1
        pos = cells[cols["position"]] if "position" in cols else None
        pos = int(_to_float(pos)) if _to_float(pos) else seq
        out.append({
            "position": pos,
            "name_written": name,
            "average": _to_float(cells[cols["average"]]) if "average" in cols else None,
            "round": _clean(cells[cols["round"]]) if "round" in cols else "",
        })
    positions = [r["position"] for r in out]
    if len(set(positions)) != len(positions):
        raise ValueError("أرقام التسلسل «ت» مكررة في الملف.")
    return out


def read_excel(path_or_bytes) -> list:
    """parse_rows() on the first sheet of an .xlsx file (path or bytes)."""
    import io
    import openpyxl
    src = io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, (bytes, bytearray)) else path_or_bytes
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    try:
        return parse_rows(wb.worksheets[0].iter_rows(values_only=True))
    finally:
        wb.close()
