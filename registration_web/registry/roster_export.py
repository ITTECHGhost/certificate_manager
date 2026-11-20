"""Accepted students -> roster .xlsx for the Windows program's bulk student import
(services/excel_import_service.parse_students_file). One file per department: the
department is chosen on the import screen. Read only; registration_web never writes MySQL.
Headers are a copy of STUDENT_ROSTER_HEADERS (tests check they stay identical)."""
import io
import re

from openpyxl import Workbook

from .models import Student

ROSTER_HEADERS = [
    "الرقم الوطني / الهوية / الجواز",
    "الاسم الكامل بالعربية (الرباعي واللقب)",
    "الاسم الكامل بالإنكليزية",
    "الجنس (ذكر / أنثى)",
    "تاريخ الميلاد (YYYY-MM-DD)",
    "المحافظة / مسقط الرأس",
    "الجنسية",
    "سنة القبول (مثال: 2023-2024)",
    "نوع الدراسة (صباحي / مسائي)",
    "سنة التخرج المتوقعة (مثال: 2025/2026، اختياري)",
    "فصل التخرج المتوقع (الأول / الثاني / الصيفي)",
    "رقم أمر التخرج (فارغ = لم يتخرج)",
]
DEFAULT_NATIONALITY = "عراقي"


def check_admission_year(value):
    """'2026-2027' (second year = first + 1) or ValueError."""
    m = re.fullmatch(r"(\d{4})-(\d{4})", (value or "").strip())
    if not m or int(m.group(2)) != int(m.group(1)) + 1:
        raise ValueError("سنة القبول بصيغة 2026-2027.")
    return m.group(0)


def accepted_departments():
    return list(Student.objects.filter(status="accepted").order_by("department")
                .values_list("department", flat=True).distinct())


def accepted_roster_xlsx(department, admission_year):
    year = check_admission_year(admission_year)
    wb = Workbook()
    ws = wb.active
    ws.title = "students"
    ws.sheet_view.rightToLeft = True
    ws.append(ROSTER_HEADERS)
    qs = Student.objects.filter(status="accepted", department=department).order_by("name_ar", "pk")
    for s in qs:
        ws.append([
            s.national_id or "",
            s.name_ar,
            s.name_en or "",
            s.get_gender_display() if s.gender else "",
            s.birth_date.strftime("%Y-%m-%d") if s.birth_date else "",
            s.birth_place or "",
            DEFAULT_NATIONALITY,
            year,
            s.get_study_type_display(),
            "", "", "",
        ])
    for col in ws.columns:  # IDs as text, so Excel keeps leading zeros
        col[0].parent.column_dimensions[col[0].column_letter].width = 24
    for row in ws.iter_rows(min_row=2, max_col=1):
        row[0].number_format = "@"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
