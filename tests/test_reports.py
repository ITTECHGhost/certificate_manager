"""«تقارير الطلاب»: the server filter whitelist and the Excel file."""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "certificate_manager_api"))


def test_where_ignores_unknown_values():
    from routers.reports import build_where
    where, params = build_where(gender=5, nationality="x; DROP", status="any", semester="z")
    assert where == "" and params == []
    where, params = build_where(department_id=3, status="graduated", graduation_year=2025, name=" علي ")
    assert where.count("%s") == len(params) == 5
    assert params[-1] == "%علي%"


def test_workbook_has_three_sheets():
    from openpyxl import load_workbook
    from nicegui_screens.reports_screen import build_workbook
    report = {"summary": {"total": 2, "graduated": 1, "male": 1, "female": 1, "avg_average": 70.5},
              "group_keys": ["department"],
              "groups": [{"department": "علوم الحاسوب", "count": 2, "male": 1, "female": 1,
                          "graduated": 1, "avg_average": 70.5}],
              "students": [{"id": 1, "full_name_ar": "أ", "graduation_year": 2025, "average": 70.5}]}
    wb = load_workbook(io.BytesIO(build_workbook(report, "")))
    assert wb.sheetnames == ["الملخص", "التجميع", "الطلاب"]
    assert wb["الطلاب"].cell(2, 8).value == "2025/2026"
    assert wb["التجميع"].cell(2, 2).value == 2
