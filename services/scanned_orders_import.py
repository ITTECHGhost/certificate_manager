"""Scanned graduation-order lists -> students (used by the «استيراد الأوامر الممسوحة» page and by
scripts/orders_csv_to_roster.py).

Gemini (or a person) turns each scanned order into a CSV with the columns
order_number, order_date, department, study_type, graduation_year, semester, page, row, name_ar,
gender, average, note. build() matches every name to the students already saved (exact name in
the department, else one spelling variant), marks the rest NEW with defaults (birthplace البصرة,
nationality العراق), and keeps the saved gender / birthplace / nationality / ID / birth date of
students it finds. payloads() turns the approved rows into /api/students/bulk-import items
(link_only: no academic period is created, the student is linked to the order).
"""
import csv
import io
import re
from dataclasses import dataclass, field

from openpyxl import Workbook

from services.excel_import_service import STUDENT_ROSTER_HEADERS
from utils.order_number import normalize_order_number
from utils.study_type import normalize_study_type

DEFAULT_BIRTHPLACE = "البصرة"
DEFAULT_NATIONALITY = "العراق"
DEFAULT_GENDER = "ذكر"

EXACT = "مطابق"
VARIANT = "مطابق بإملاء مختلف"
AMBIGUOUS = "أكثر من طالب محتمل"
NEW = "طالب جديد"
NO_DEPT = "قسم غير معروف"
DUPLICATE = "مكرر في الأمر"

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_DIACRITICS = re.compile(r"[ً-ْـ]")  # harakat + tatweel


def normalize_name(text):
    t = _DIACRITICS.sub("", str(text or ""))
    t = re.sub("[أإآ]", "ا", t).replace("ة", "ه").replace("ى", "ي")
    return " ".join(t.split())


def _norm_dept(text):
    t = normalize_name(text)
    return re.sub(r"^(قسم|القسم)\s+", "", t).removeprefix("ال")


def _clean(text):
    return " ".join(str(text or "").split())


def read_csv_text(text, source):
    rows = []
    for r in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        r = {k.strip(): _clean(v) for k, v in r.items() if k}
        if not r.get("name_ar"):
            continue
        for k in ("order_number", "graduation_year", "page", "row", "average"):
            r[k] = r.get(k, "").translate(_DIGITS)
        r["order_number"] = normalize_order_number(r["order_number"]).value or r["order_number"]
        r["source"] = source
        rows.append(r)
    return rows


@dataclass
class Result:
    roster: dict = field(default_factory=dict)   # department name -> [row lists]
    review: list = field(default_factory=list)   # dicts, Arabic keys
    orders: list = field(default_factory=list)
    items: list = field(default_factory=list)    # importable rows (dicts), see build()


def _gender_label(value):
    return {1: "ذكر", 2: "أنثى", "1": "ذكر", "2": "أنثى"}.get(value, "")


def build(rows, students, departments, governorates, countries, orders,
          default_birthplace=DEFAULT_BIRTHPLACE):
    gov_name = {g["id"]: g["name_ar"] for g in governorates}
    country_name = {c["id"]: c["name_ar"] for c in countries}
    gov_id = {g["name_ar"]: g["id"] for g in governorates}
    country_id = {c["name_ar"]: c["id"] for c in countries}
    dept_by_norm = {_norm_dept(d["name_ar"]): d for d in departments}
    exact, by_norm = {}, {}
    for s in students:
        key = (s.get("department_id"), _clean(s.get("full_name_ar")))
        exact.setdefault(key, []).append(s)
        by_norm.setdefault((s.get("department_id"), normalize_name(s.get("full_name_ar"))), []).append(s)
    existing_orders = {(normalize_order_number(o.get("order_number")).value, o.get("department_id"))
                       for o in orders}

    res = Result()
    seen = set()
    order_summary = {}
    for r in rows:
        dept = dept_by_norm.get(_norm_dept(r.get("department")))
        rv = {"الملف": r["source"], "الصفحة": r.get("page", ""), "السطر": r.get("row", ""),
              "رقم الأمر": r.get("order_number", ""), "القسم": r.get("department", ""),
              "الاسم في الورقة": r["name_ar"], "الاسم في النظام": "", "الحالة": "",
              "الجنس": r.get("gender", ""), "المعدل": r.get("average", ""),
              "يحتاج إكمال": "", "ملاحظة": r.get("note", "")}
        res.review.append(rv)
        okey = (r.get("order_number", ""), dept["id"] if dept else None)
        o = order_summary.setdefault(okey, {
            "رقم الأمر": r.get("order_number", ""), "التاريخ": r.get("order_date", ""),
            "القسم": dept["name_ar"] if dept else r.get("department", ""),
            "نوع الدراسة": r.get("study_type", ""), "سنة التخرج": r.get("graduation_year", ""),
            "الفصل": r.get("semester", ""),
            "موجود في النظام": "نعم" if okey in existing_orders else "لا", "عدد الأسماء": 0})
        o["عدد الأسماء"] += 1
        if not dept:
            rv["الحالة"] = NO_DEPT
            continue
        dup_key = (r.get("order_number"), dept["id"], normalize_name(r["name_ar"]))
        if dup_key in seen:
            rv["الحالة"] = DUPLICATE
            continue
        seen.add(dup_key)

        cands = exact.get((dept["id"], r["name_ar"])) or []
        status = EXACT
        if len(cands) != 1:
            cands = by_norm.get((dept["id"], normalize_name(r["name_ar"]))) or []
            status = VARIANT
        if len(cands) > 1:
            rv["الحالة"] = AMBIGUOUS
            rv["الاسم في النظام"] = " | ".join(c["full_name_ar"] for c in cands)
            continue

        missing = []
        paper_gender = r.get("gender") if r.get("gender") in ("ذكر", "أنثى") else ""
        if cands:
            s = cands[0]
            saved = _gender_label(s.get("gender"))
            if paper_gender and saved and paper_gender != saved:
                rv["ملاحظة"] = (rv["ملاحظة"] + " الجنس مختلف عن المحفوظ (" + saved + ")").strip()
            name = s["full_name_ar"]
            nat_id = s.get("national_id") or ""
            if nat_id.startswith("GEN_"):
                nat_id = ""
            gender = paper_gender or saved or DEFAULT_GENDER
            dob = str(s.get("date_of_birth") or "")[:10]
            birthplace = gov_name.get(s.get("birthplace_id"), default_birthplace)
            nationality = country_name.get(s.get("nationality_id"), DEFAULT_NATIONALITY)
            rv["الاسم في النظام"] = name
        else:
            status = NEW
            name, nat_id, dob = r["name_ar"], "", ""
            gender = paper_gender or DEFAULT_GENDER
            birthplace, nationality = default_birthplace, DEFAULT_NATIONALITY
        if not paper_gender and status == NEW:
            missing.append("الجنس")
        if not nat_id:
            missing.append("رقم البطاقة")
        if not dob:
            missing.append("تاريخ الميلاد")
        rv["الحالة"] = status
        rv["الجنس"] = gender
        rv["يحتاج إكمال"] = "، ".join(missing)
        res.items.append({
            "review_index": len(res.review) - 1, "status": status,
            "student_id": cands[0].get("id") if cands else None,
            "department_id": dept["id"], "department": dept["name_ar"],
            "full_name_ar": name, "gender": 2 if gender == "أنثى" else 1,
            "date_of_birth": dob or None, "national_id": nat_id or None,
            "birthplace_id": (cands[0].get("birthplace_id") if cands else None) or gov_id.get(birthplace),
            "nationality_id": (cands[0].get("nationality_id") if cands else None) or country_id.get(nationality),
            "study_system_id": cands[0].get("study_system_id") if cands else None,
            "study_type": normalize_study_type(r.get("study_type")),
            "graduation_year": r.get("graduation_year", ""), "semester": r.get("semester", ""),
            "order_number": r.get("order_number", ""), "average": _average(r.get("average")),
        })
        res.roster.setdefault(dept["name_ar"], []).append([
            nat_id, name, "", gender, dob, birthplace, nationality, "",
            r.get("study_type", ""), r.get("graduation_year", ""), r.get("semester", ""),
            r.get("order_number", ""),
        ])
    res.orders = list(order_summary.values())
    return res


def roster_xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "students"
    ws.sheet_view.rightToLeft = True
    ws.append([h for h, _ in STUDENT_ROSTER_HEADERS])
    for row in rows:
        ws.append(row)
    for cell in ws["A"]:
        cell.number_format = "@"  # IDs stay text
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def review_xlsx(result):
    wb = Workbook()
    for title, dicts in (("المراجعة", result.review), ("الأوامر", result.orders),
                         ("يحتاج إكمال", [r for r in result.review if r["يحتاج إكمال"]])):
        ws = wb.active if title == "المراجعة" else wb.create_sheet(title)
        ws.title = title
        ws.sheet_view.rightToLeft = True
        if dicts:
            ws.append(list(dicts[0].keys()))
            for d in dicts:
                ws.append(list(d.values()))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _average(text):
    try:
        v = float(str(text or "").replace("،", ".").replace(",", "."))
    except ValueError:
        return None
    return v if 0 <= v <= 100 else None


def missing_orders(result):
    """Orders named on the papers that are not in the system yet (students would stay unlinked)."""
    return [o for o in result.orders if o["موجود في النظام"] == "لا"]


def payloads(items, default_system_id=1):
    """bulk-import items for the approved rows. link_only: no academic period is created (the
    papers have no grades), existing students keep their saved study system."""
    out = []
    for it in items:
        out.append({
            "full_name_ar": it["full_name_ar"], "gender": int(it.get("gender") or 1),
            "date_of_birth": it.get("date_of_birth"), "national_id": it.get("national_id"),
            "birthplace_id": it.get("birthplace_id"), "nationality_id": it.get("nationality_id"),
            "department_id": int(it["department_id"]),
            "study_system_id": it.get("study_system_id") or default_system_id,
            "study_type": it.get("study_type"), "average": it.get("average"),
            "academic_year": str(it.get("graduation_year") or ""),
            "expected_graduation_semester": it.get("semester") or "",
            "order_number": it.get("order_number") or "", "link_only": True,
        })
    return out


def fetch_table(table):
    """One table from the server's replica endpoint as a list of dicts (online only)."""
    import api_client
    import api_config
    resp = api_client.get(f"{api_config.get_api_url()}/replica/{table}", timeout=60.0)
    resp.raise_for_status()
    data = resp.json()
    rows, cols = data.get("rows", data), data.get("columns")
    if cols and rows and not isinstance(rows[0], dict):
        rows = [dict(zip(cols, r)) for r in rows]
    return rows


def analyse(csv_files):
    """[(file name, text), ...] -> Result, matched against the server's current data."""
    rows = []
    for name, text in csv_files:
        rows += read_csv_text(text, name)
    if not rows:
        raise ValueError("لا توجد أسماء في الملفات: تأكد أن السطر الأول عناوين الأعمدة (name_ar ...)")
    return build(rows, fetch_table("students"), fetch_table("departments"), fetch_table("governorates"),
                 fetch_table("countries"), fetch_table("graduation_orders"))


def group_by_order(items):
    """One bulk-import request per order (each all-or-nothing on the server)."""
    groups = {}
    for it in items:
        groups.setdefault((it.get("order_number") or "", it["department_id"]), []).append(it)
    return groups
