import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from data.repositories import (
    BaseRepository,
    SettingsRepository,
    CountryRepository,
    GovernorateRepository,
    DepartmentRepository,
    StudySystemRepository,
    PersonnelRepository,
    CourseRepository,
    StudentRepository,
    AcademicPeriodRepository,
    EnrollmentRepository,
    CertificateRepository,
    GraduationOrderRepository,
    ThesisRepository,
    StudentSupervisorRepository,
    AuditRepository
)

def test_retrieval():
    print("Testing settings:")
    try:
        settings = SettingsRepository().get_settings()
        print(f"Success: {settings}")
    except Exception as e:
        print(f"Failed: {e}")

    print("Testing countries:")
    try:
        countries = CountryRepository().get_all()
        print(f"Success: {len(countries)} countries found")
    except Exception as e:
        print(f"Failed: {e}")

    print("Testing departments:")
    try:
        depts = DepartmentRepository().get_all()
        print(f"Success: {len(depts)} departments found")
    except Exception as e:
        print(f"Failed: {e}")

    print("Testing personnel:")
    try:
        pers = PersonnelRepository().get_all()
        print(f"Success: {len(pers)} personnel found")
    except Exception as e:
        print(f"Failed: {e}")

    print("Testing students:")
    try:
        students = StudentRepository().get_all_paginated()
        print(f"Success: {len(students)} students found")
        if students:
            first_std = students[0]
            print(f"First student ID: {first_std['id']}, name: {first_std['full_name_ar']}")
            print("Testing full certificate retrieval for ID:", first_std['id'])
            cert = CertificateRepository().get_full_certificate_data(first_std['id'])
            print(f"Success: {cert is not None}")
    except Exception as e:
        print(f"Failed: {e}")

    print("Testing count_table_rows:")
    try:
        repo = BaseRepository()
        for tbl in ["students", "departments", "courses", "personnel", "graduation_orders", "study_systems"]:
            cnt = repo.count_table_rows(tbl)
            print(f"  Table '{tbl}' count: {cnt}")
    except Exception as e:
        print(f"Failed count_table_rows: {e}")

if __name__ == "__main__":
    test_retrieval()
