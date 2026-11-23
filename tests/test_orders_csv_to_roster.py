"""Scanned graduation-order lists (Gemini CSV) -> roster files for the bulk import.
Fake names only. The import overwrites gender/birthplace/nationality of existing students,
so linked rows must carry the values already saved."""
import io

import openpyxl

from scripts import orders_csv_to_roster as m
from services.excel_import_service import STUDENT_ROSTER_HEADERS, parse_students_file

DEPTS = [{"id": 1, "name_ar": "قسم الحاسبات"}, {"id": 2, "name_ar": "قسم المدني"}]
GOVS = [{"id": 2, "name_ar": "بغداد"}, {"id": 5, "name_ar": "البصرة"}, {"id": 7, "name_ar": "نينوى"}]
COUNTRIES = [{"id": 274, "name_ar": "العراق"}, {"id": 300, "name_ar": "سوريا"}]
ORDERS = [{"order_number": "100/5", "department_id": 1}]
STUDENTS = [
    {"id": 11, "full_name_ar": "سارة أحمد علي", "department_id": 1, "gender": 2,
     "national_id": "199000000011", "birthplace_id": 7, "nationality_id": 300,
     "date_of_birth": "2001-02-03"},
    {"id": 12, "full_name_ar": "فاطمة حسن", "department_id": 1, "gender": 2,
     "national_id": None, "birthplace_id": 2, "nationality_id": 274, "date_of_birth": None},
    {"id": 13, "full_name_ar": "علي كريم", "department_id": 1, "gender": 1,
     "national_id": "GEN_1", "birthplace_id": 2, "nationality_id": 274, "date_of_birth": None},
    {"id": 14, "full_name_ar": "علي  كريم", "department_id": 1, "gender": 1,
     "national_id": "GEN_2", "birthplace_id": 2, "nationality_id": 274, "date_of_birth": None},
]
HEAD = "order_number,order_date,department,study_type,graduation_year,semester,page,row,name_ar,gender,average,note\n"


def _csv(*lines):
    return HEAD + "".join(l + "\n" for l in lines)


def _run(text, **kw):
    rows = m.read_csv_text(text, "o1.csv")
    return m.build(rows, STUDENTS, DEPTS, GOVS, COUNTRIES, ORDERS, **kw)


def _roster_rows(result, dept="قسم الحاسبات"):
    data = m.roster_xlsx(result.roster[dept])
    students, errors = parse_students_file(data)
    assert errors == []
    return students


def test_exact_match_keeps_saved_gender_birthplace_nationality():
    r = _run(_csv("100/5,2025-07-01,قسم الحاسبات,صباحي,2025,الثاني,2,1,سارة أحمد علي,,88.5,"))
    (st,) = _roster_rows(r)
    assert st["full_name_ar"] == "سارة أحمد علي"
    assert st["national_id"] == "199000000011"
    assert st["gender"] == 2
    assert st["birthplace"] == "نينوى" and st["nationality"] == "سوريا"
    assert st["date_of_birth"] == "2001-02-03"
    assert st["order_number"] == "100/5"
    assert r.review[0]["الحالة"] == m.EXACT


def test_spelling_variant_links_with_saved_spelling():
    # ة/ه and إ/ا differences only -> linked, system spelling written (import matches by name)
    r = _run(_csv("100/5,2025-07-01,قسم الحاسبات,,2025,الثاني,2,2,فاطمه حسن,,,"))
    (st,) = _roster_rows(r)
    assert st["full_name_ar"] == "فاطمة حسن" and st["gender"] == 2
    assert r.review[0]["الحالة"] == m.VARIANT
    assert r.review[0]["الاسم في النظام"] == "فاطمة حسن"


def test_ambiguous_match_left_out_of_roster():
    r = _run(_csv("100/5,2025-07-01,قسم الحاسبات,,2025,الثاني,2,3,علي كريم,,,"))
    assert r.roster.get("قسم الحاسبات", []) == []
    assert r.review[0]["الحالة"] == m.AMBIGUOUS


def test_new_student_gets_defaults_and_is_flagged():
    r = _run(_csv("100/5,2025-07-01,قسم الحاسبات,مسائي,2025,الثاني,3,1,زيد جديد,,,غير واضح"))
    (st,) = _roster_rows(r)
    assert st["full_name_ar"] == "زيد جديد"
    assert st["national_id"].startswith("GEN_")
    assert st["gender"] == 1
    assert st["birthplace"] == "البصرة" and st["nationality"] == "العراق"
    assert st["study_type"] == "evening"
    rv = r.review[0]
    assert rv["الحالة"] == m.NEW
    assert "الجنس" in rv["يحتاج إكمال"] and "رقم البطاقة" in rv["يحتاج إكمال"]
    assert "غير واضح" in rv["ملاحظة"]


def test_new_female_from_paper():
    r = _run(_csv("100/5,2025-07-01,قسم الحاسبات,,2025,الثاني,3,2,هدى جديدة,أنثى,,"))
    (st,) = _roster_rows(r)
    assert st["gender"] == 2
    assert "الجنس" not in r.review[0]["يحتاج إكمال"]


def test_paper_gender_differs_from_saved_is_flagged_and_paper_wins():
    r = _run(_csv("100/5,2025-07-01,قسم الحاسبات,,2025,الثاني,2,1,سارة أحمد علي,ذكر,,"))
    (st,) = _roster_rows(r)
    assert st["gender"] == 1
    assert "الجنس مختلف" in r.review[0]["ملاحظة"]


def test_unknown_department_left_out():
    r = _run(_csv("100/5,2025-07-01,قسم الفلك,,2025,الثاني,2,1,زيد,,,"))
    assert r.roster == {}
    assert r.review[0]["الحالة"] == m.NO_DEPT


def test_department_spelling_variant_accepted():
    r = _run(_csv("100/5,2025-07-01,الحاسبات,,2025,الثاني,2,1,سارة احمد علي,,,"))
    assert len(r.roster["قسم الحاسبات"]) == 1


def test_duplicate_name_in_same_order_flagged():
    r = _run(_csv("100/5,2025-07-01,قسم الحاسبات,,2025,الثاني,2,1,زيد جديد,ذكر,,",
                  "100/5,2025-07-01,قسم الحاسبات,,2025,الثاني,2,2,زيد جديد,ذكر,,"))
    assert len(r.roster["قسم الحاسبات"]) == 1
    assert r.review[1]["الحالة"] == m.DUPLICATE


def test_orders_summary_marks_missing_orders():
    r = _run(_csv("100/5,2025-07-01,قسم الحاسبات,,2025,الثاني,2,1,زيد,ذكر,,",
                  "200/9,2025-08-01,قسم المدني,,2025,الثاني,2,1,عمر,ذكر,,"))
    by_no = {o["رقم الأمر"]: o for o in r.orders}
    assert by_no["100/5"]["موجود في النظام"] == "نعم"
    assert by_no["200/9"]["موجود في النظام"] == "سيُنشأ"   # has a date: created first on import
    assert by_no["200/9"]["عدد الأسماء"] == 1


def test_roster_headers_are_official():
    r = _run(_csv("100/5,2025-07-01,قسم الحاسبات,,2025,الثاني,2,1,زيد,ذكر,,"))
    ws = openpyxl.load_workbook(io.BytesIO(m.roster_xlsx(r.roster["قسم الحاسبات"]))).active
    assert [c.value for c in ws[1]] == [h for h, _ in STUDENT_ROSTER_HEADERS]


def test_csv_with_bom_and_arabic_digits():
    text = "﻿" + _csv("١٠٠/٥,2025-07-01,قسم الحاسبات,,٢٠٢٥,الثاني,2,1,زيد,ذكر,,")
    r = m.build(m.read_csv_text(text, "x.csv"), STUDENTS, DEPTS, GOVS, COUNTRIES, ORDERS)
    (st,) = _roster_rows(r)
    assert st["order_number"] == "100/5"


def test_out_dir_inside_repo_refused(tmp_path):
    import pytest
    with pytest.raises(SystemExit):
        m.check_out_dir(m.REPO / "docs")
    m.check_out_dir(tmp_path)
