import sys
import os
sys.path.append('.')
from screens.certificate_screen1 import CertificateScreen
from data.queries import get_full_certificate_data
from docxtpl import DocxTemplate

def generate_test_doc():
    data = get_full_certificate_data(124)
    tables = []
    semesters = []
    for period in data.get("periods", []):
        sem_label = f"Stage {period['stage_number']} - {period['academic_year']}"
        rows_for_loop = []
        doc_rows = []
        enrollments = period.get("enrollments", [])
        
        for enr in enrollments:
            rows_for_loop.append({
                "Course": enr.get("name_en", ""),
                "Mark": str(enr.get("score", "")),
                "Unit": str(enr.get("credit_hours", ""))
            })
        
        for i in range(0, len(enrollments), 2):
            left = enrollments[i]
            right = enrollments[i+1] if i+1 < len(enrollments) else {}
            doc_rows.append({
                "left_name": left.get("name_en", ""),
                "left_mark": str(left.get("score", "")),
                "left_unit": str(left.get("credit_hours", "")),
                "right_name": right.get("name_en", ""),
                "right_mark": str(right.get("score", "")),
                "right_unit": str(right.get("credit_hours", ""))
            })
            
        tables.append({
            "Semester_year": sem_label,
            "rows": rows_for_loop
        })
        semesters.append({
            "label": sem_label,
            "rows": doc_rows
        })

    ctx = {
        "Title": "Whom it May Concern",
        "student_name": data.get("full_name_en", ""),
        "Birthday": data.get("date_of_birth", ""),
        "Birthplace": data.get("birthplace_en", "") or data.get("birthplace_other", ""),
        "Nationality": data.get("nationality_en", ""),
        "admission_year": data.get("admission_year", ""),
        "department_id": data.get("dept_name_en", ""),
        "study_type": "Morning",
        "graduation_date": data.get("graduation_date", ""),
        "graduation_semester": "First",
        "average": data.get("average", ""),
        "Grade": "Good",
        "Sequence_of_Graduation": data.get("rank", ""),
        "num_students": data.get("total_graduates", ""),
        "Average_of_First_Student": data.get("top_average", ""),
        "tables": tables,
        "semesters": semesters
    }

    doc = DocxTemplate(r'c:\Users\alhayat\Music\certificate_manager\templets\semster - Temp.docx')
    doc.render(ctx)
    doc.save('test_output.docx')
    print("Generated test_output.docx")

if __name__ == '__main__':
    generate_test_doc()
