"""Scanned graduation-order lists -> roster files for the students bulk import.

Input: one UTF-8 CSV per order (made by Gemini from the scans), columns
  order_number,order_date,department,study_type,graduation_year,semester,page,row,
  name_ar,gender,average,note
Output (in OUT_DIR, which must be OUTSIDE the repository - real names never go to git):
  roster_<department>.xlsx  one per department, official STUDENT_ROSTER_HEADERS, ready for
                            الطلاب -> استيراد جماعي (choose the same department there)
  review.xlsx               every CSV row with its status, a «يحتاج إكمال» list and the
                            orders found (with "exists in the system?")

The import overwrites gender, birthplace and nationality of a student it finds, and finds
students by national ID or by the EXACT Arabic name in the department. So:
  - exact name           -> linked; the saved gender/birthplace/nationality/ID are written
  - spelling variant     -> (only أ/إ/آ/ا, ة/ه, ى/ي, spaces, diacritics differ; one candidate)
                            linked the same way, the SYSTEM spelling is written
  - several candidates   -> left out, decide by hand
  - no match             -> new student with defaults (birthplace البصرة, nationality العراق,
                            gender from the paper or ذكر), listed under «يحتاج إكمال»
Reads the database through the API only (/replica/*); writes nothing to it.

Usage:  py -3 scripts\\orders_csv_to_roster.py <csv_folder> <out_folder>
"""
import csv
import io
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import Workbook

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from services.excel_import_service import STUDENT_ROSTER_HEADERS  # noqa: E402
from utils.order_number import normalize_order_number  # noqa: E402

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


def _gender_label(value):
    return {1: "ذكر", 2: "أنثى", "1": "ذكر", "2": "أنثى"}.get(value, "")


def build(rows, students, departments, governorates, countries, orders,
          default_birthplace=DEFAULT_BIRTHPLACE):
    gov_name = {g["id"]: g["name_ar"] for g in governorates}
    country_name = {c["id"]: c["name_ar"] for c in countries}
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


def check_out_dir(out_dir):
    out = Path(out_dir).resolve()
    if out == REPO or REPO in out.parents:
        raise SystemExit("[ERROR] Output folder must be OUTSIDE the repository (real names never go to git).")
    return out


def _safe_filename(text):
    return re.sub(r'[\\/:*?"<>|]+', "_", text).strip() or "department"


def _fetch(table):
    import api_client
    import api_config
    resp = api_client.get(f"{api_config.get_api_url()}/replica/{table}")
    resp.raise_for_status()
    data = resp.json()
    rows, cols = data.get("rows", data), data.get("columns")
    if cols and rows and not isinstance(rows[0], dict):
        rows = [dict(zip(cols, r)) for r in rows]
    return rows


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Arabic on a cp1252 console
    except AttributeError:
        pass
    if len(argv) != 2:
        print(__doc__)
        return 2
    csv_dir, out = Path(argv[0]), check_out_dir(argv[1])
    rows = []
    for p in sorted(csv_dir.glob("*.csv")):
        rows += read_csv_text(p.read_text(encoding="utf-8-sig"), p.name)
    if not rows:
        print(f"[ERROR] No CSV rows in {csv_dir}")
        return 1
    res = build(rows, _fetch("students"), _fetch("departments"), _fetch("governorates"),
                _fetch("countries"), _fetch("graduation_orders"))
    out.mkdir(parents=True, exist_ok=True)
    for dept, drows in res.roster.items():
        (out / f"roster_{_safe_filename(dept)}.xlsx").write_bytes(roster_xlsx(drows))
        print(f"[OK] roster_{_safe_filename(dept)}.xlsx: {len(drows)} students")
    (out / "review.xlsx").write_bytes(review_xlsx(res))
    counts = {}
    for r in res.review:
        counts[r["الحالة"]] = counts.get(r["الحالة"], 0) + 1
    print("[OK] review.xlsx: " + "، ".join(f"{k}: {v}" for k, v in counts.items()))
    missing = sum(1 for o in res.orders if o["موجود في النظام"] == "لا")
    if missing:
        print(f"[WARN] {missing} order(s) not in the system yet - create them before importing (sheet «الأوامر»).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
