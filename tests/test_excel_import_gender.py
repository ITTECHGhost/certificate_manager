"""Round-trip: official roster headers must map gender and nationality to their own columns.

«الجنسية» contains «الجنس»; the nationality header must not overwrite the gender mapping.
"""
import io

from openpyxl import Workbook

from services.excel_import_service import STUDENT_ROSTER_HEADERS, parse_students_file


def test_gender_and_nationality_round_trip():
    wb = Workbook()
    ws = wb.active
    ws.append([h for h, _ in STUDENT_ROSTER_HEADERS])
    ws.append(["199901010001", "فاطمة علي حسن محمد", "Fatima Ali", "أنثى", "1999-01-01",
               "بغداد", "أردنية", "2023-2024", "صباحي", "", "", ""])
    buf = io.BytesIO()
    wb.save(buf)

    students, errors = parse_students_file(buf.getvalue())

    assert len(students) == 1, errors
    assert students[0]["gender"] == 2
    assert students[0]["nationality"] == "أردنية"
