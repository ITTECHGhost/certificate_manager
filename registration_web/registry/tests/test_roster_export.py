"""Accepted students -> roster xlsx the Windows app's bulk import reads (never MySQL).
Fake data only. The round trip uses the program's real parse_students_file."""
import datetime
import sys
from pathlib import Path

import pytest

from registry import roster_export
from registry.models import Student
from registry.tests.test_week2 import _client

pytestmark = pytest.mark.django_db

REPO = Path(__file__).resolve().parents[3]


def _parse(data):
    sys.path.insert(0, str(REPO))
    try:
        mod = pytest.importorskip("services.excel_import_service")
    finally:
        sys.path.remove(str(REPO))
    return mod.parse_students_file(data)


def _st(name, dept="حاسبات", status="accepted", **kw):
    base = dict(name_ar=name, department=dept, study_type="morning", status=status)
    base.update(kw)
    return Student.objects.create(**base)


@pytest.fixture
def data():
    a = _st("زيد علي حسن", national_id="199012345678", name_en="Zaid Ali Hasan",
            gender="female", birth_date=datetime.date(2005, 3, 7), birth_place="البصرة",
            study_type="parallel")
    _st("باء مقبول", national_id="2")
    _st("جديد", status="new", national_id="3")
    _st("قسم آخر", dept="مدني", national_id="4")
    gone = _st("محذوف", national_id="5")
    gone.soft_delete(None)
    return a


def test_round_trip_through_windows_parser(data):
    rows, errors = _parse(roster_export.accepted_roster_xlsx("حاسبات", "2026-2027"))
    assert errors == []
    assert [r["full_name_ar"] for r in rows] == ["باء مقبول", "زيد علي حسن"]
    z = rows[1]
    assert z["national_id"] == "199012345678"
    assert z["full_name_en"] == "Zaid Ali Hasan"
    assert z["date_of_birth"] == "2005-03-07"
    assert z["birthplace"] == "البصرة"
    assert z["nationality"] == "عراقي"
    assert z["admission_year"] == "2026-2027"
    assert z["study_type"] == "parallel"
    assert z["order_number"] == "" and z["expected_graduation_year"] is None


def test_gender_cell_written(data):
    import io
    import openpyxl
    ws = openpyxl.load_workbook(io.BytesIO(
        roster_export.accepted_roster_xlsx("حاسبات", "2026-2027"))).active
    assert ws.cell(row=3, column=4).value == "أنثى"


@pytest.mark.xfail(strict=True, reason="Windows program bug: excel_import_service checks "
                   "'الجنس' before 'الجنسية', so gender is read from the nationality column")
def test_gender_round_trip(data):
    rows, _ = _parse(roster_export.accepted_roster_xlsx("حاسبات", "2026-2027"))
    assert rows[1]["gender"] == 2


def test_headers_match_program_roster(data):
    import openpyxl, io
    sys.path.insert(0, str(REPO))
    try:
        mod = pytest.importorskip("services.excel_import_service")
    finally:
        sys.path.remove(str(REPO))
    ws = openpyxl.load_workbook(io.BytesIO(
        roster_export.accepted_roster_xlsx("حاسبات", "2026-2027"))).active
    assert [c.value for c in ws[1]] == [h for h, _ in mod.STUDENT_ROSTER_HEADERS]


@pytest.mark.parametrize("year", ["", "2026", "2026-2028", "abcd-efgh"])
def test_bad_admission_year_refused(year):
    with pytest.raises(ValueError):
        roster_export.accepted_roster_xlsx("حاسبات", year)


def test_page_student_affairs_only(data):
    assert _client("f", "finance").get("/students/roster/").status_code == 403
    c = _client("sa", "student_affairs")
    page = c.get("/students/roster/")
    assert page.status_code == 200 and "حاسبات" in page.content.decode()
    resp = c.get("/students/roster/", {"department": "حاسبات", "admission_year": "2026-2027"})
    assert resp.status_code == 200
    assert "spreadsheetml" in resp["Content-Type"]
    assert _parse(b"".join(resp.streaming_content) if resp.streaming else resp.content)[0]


def test_page_bad_year_shows_error_not_file(data):
    c = _client("sa", "student_affairs")
    resp = c.get("/students/roster/", {"department": "حاسبات", "admission_year": "x"})
    assert resp.status_code == 200 and "text/html" in resp["Content-Type"]
