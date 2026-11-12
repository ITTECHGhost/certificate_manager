from services.excel_import_service import generate_students_template, parse_students_file, parse_semester


def test_template_round_trip_reads_optional_columns():
    import io
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(generate_students_template()))
    ws = wb.active
    ws.cell(row=4, column=10).value = "2025"
    ws.cell(row=4, column=11).value = "الثاني"
    ws.cell(row=4, column=12).value = "18515/13/2"
    buf = io.BytesIO()
    wb.save(buf)
    students, _ = parse_students_file(buf.getvalue())
    first, second = students[0], students[1]
    assert first["expected_graduation_year"] == 2025
    assert first["expected_graduation_semester"] == "second"
    assert first["order_number"] == "18515/13/2"
    assert second["order_number"] == "" and second["expected_graduation_year"] is None
    assert first["date_of_birth"] == "2001-05-14" and first["admission_year"]


def test_semester_words():
    assert parse_semester("الفصل الأول") == "first"
    assert parse_semester("صيفي") == "summer"
    assert parse_semester("") == ""
