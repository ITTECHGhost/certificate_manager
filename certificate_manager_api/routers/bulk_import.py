# =============================================================================
# certificate_manager_api/routers/bulk_import.py — Atomic Student Bulk Import
# =============================================================================

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

logger = logging.getLogger("api.bulk_import")

router = APIRouter(tags=["bulk-import"])

VALID_RESULT_STATUSES = {
    "PASSED", "FAILED_REPEAT", "CARRIED_OVER", "EXCEPTIONAL_PASS", "DEFERRED", "DISMISSED"
}

STATUS_STR_MAP = {
    "1": "PASSED",
    "2": "FAILED_REPEAT",
    "FAILED": "FAILED_REPEAT",
    "3": "EXCEPTIONAL_PASS",
    "4": "CARRIED_OVER",
    "5": "DEFERRED",
    "6": "DISMISSED",
}

# academic_periods.result_status is an INT column: store the code, never the key text
# (writing 'PASSED' into it stores 0)
STATUS_CODE = {
    "PASSED": 1, "FAILED_REPEAT": 2, "EXCEPTIONAL_PASS": 3,
    "CARRIED_OVER": 4, "DEFERRED": 5, "DISMISSED": 6,
}


class BulkImportScoreItem(BaseModel):
    course_id: int
    score: float
    passed_round: Optional[int] = 1
    stage_number: Optional[int] = None


class BulkImportStudentItem(BaseModel):
    full_name_ar: str
    full_name_en: Optional[str] = ""
    gender: Optional[int] = 1
    date_of_birth: Optional[str] = None
    birthplace_id: Optional[int] = 2
    nationality_id: Optional[int] = 274
    national_id: Optional[str] = None
    department_id: int
    study_system_id: Optional[int] = 1
    degree_level: Optional[int] = 1
    admission_year: Optional[str] = ""
    average: Optional[float] = None
    academic_year: str
    stage_number: Optional[int] = 1
    semester_num: Optional[int] = 1
    result_status: Optional[str] = "PASSED"
    scores: Optional[List[BulkImportScoreItem]] = []


class BulkImportRequest(BaseModel):
    students: List[BulkImportStudentItem]


def get_db_dependency():
    """Deferred import to avoid circular dependency with main.py."""
    from main import get_db
    return get_db


@router.post("/api/students/bulk-import")
@router.post("/students/bulk-import")
def bulk_import_students(payload: BulkImportRequest, conn=Depends(get_db_dependency())):
    """
    Ingests an entire cohort of students, academic periods, and course enrollments
    within a single atomic database transaction.
    """
    if not payload.students:
        return {
            "status": "success",
            "message": "No students provided in payload",
            "created_students": 0,
            "updated_students": 0,
            "saved_enrollments": 0,
            "total_processed": 0
        }

    cur = conn.cursor(dictionary=True)
    created_students = 0
    updated_students = 0
    created_periods = 0
    reused_periods = 0
    saved_enrollments = 0

    try:
        conn.start_transaction()

        for item in payload.students:
            student_id = None
            nat_id = str(item.national_id or "").strip()

            # 1. Check if student already exists by real national_id (excluding GEN_ fallback)
            if nat_id and not nat_id.startswith("GEN_"):
                cur.execute(
                    "SELECT id FROM students WHERE national_id = %s LIMIT 1",
                    (nat_id,)
                )
                existing = cur.fetchone()
                if existing:
                    student_id = existing["id"]

            # Fallback check by name and department
            if student_id is None and item.full_name_ar:
                cur.execute(
                    "SELECT id FROM students WHERE full_name_ar = %s AND department_id = %s LIMIT 1",
                    (item.full_name_ar.strip(), item.department_id)
                )
                existing = cur.fetchone()
                if existing:
                    student_id = existing["id"]

            # Save student (Update vs Insert)
            if student_id is not None:
                cur.execute("""
                    UPDATE students SET
                        full_name_en = CASE WHEN %s != '' THEN %s ELSE full_name_en END,
                        gender = %s,
                        date_of_birth = COALESCE(%s, date_of_birth),
                        birthplace_id = %s,
                        nationality_id = %s,
                        national_id = CASE WHEN %s != '' AND %s NOT LIKE 'GEN_%%' THEN %s ELSE national_id END,
                        study_system_id = COALESCE(%s, study_system_id),
                        average = CASE WHEN %s IS NOT NULL THEN %s ELSE average END
                    WHERE id = %s
                """, (
                    item.full_name_en or "", item.full_name_en or "",
                    item.gender or 1,
                    item.date_of_birth,
                    item.birthplace_id or 2,
                    item.nationality_id or 274,
                    nat_id, nat_id, nat_id,
                    item.study_system_id or 1,
                    item.average, item.average,
                    student_id
                ))
                updated_students += 1
            else:
                cur.execute("""
                    INSERT INTO students (
                        full_name_ar, full_name_en, gender, date_of_birth,
                        birthplace_id, nationality_id, national_id,
                        department_id, study_system_id, degree_level,
                        admission_year, average
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    item.full_name_ar.strip(), item.full_name_en or "",
                    item.gender or 1, item.date_of_birth,
                    item.birthplace_id or 2, item.nationality_id or 274,
                    nat_id if nat_id and not nat_id.startswith("GEN_") else None,
                    item.department_id, item.study_system_id or 1,
                    item.degree_level or 1,
                    item.admission_year or "", item.average
                ))
                student_id = cur.lastrowid
                created_students += 1

            # 2. Check or create academic periods & enrollments
            sem_num = item.semester_num if item.semester_num is not None else 1
            raw_status = str(item.result_status or "PASSED").strip().upper()
            result_status_str = STATUS_STR_MAP.get(raw_status, raw_status)
            if result_status_str not in VALID_RESULT_STATUSES:
                result_status_str = "PASSED"
            result_status_db = STATUS_CODE[result_status_str]

            if item.scores:
                # Group scores by stage number (from score item, or fallback to student's stage_number or 1)
                scores_by_stage = {}
                for sc in item.scores:
                    stg = sc.stage_number or item.stage_number or 1
                    scores_by_stage.setdefault(stg, []).append(sc)

                for stg, sc_list in scores_by_stage.items():
                    cur.execute("""
                        SELECT id FROM academic_periods
                        WHERE student_id = %s AND academic_year = %s AND stage_number = %s AND semester_num = %s
                        LIMIT 1
                    """, (student_id, item.academic_year.strip(), stg, sem_num))
                    p_row = cur.fetchone()

                    if p_row:
                        period_id = p_row["id"]
                        cur.execute(
                            "UPDATE academic_periods SET result_status = %s WHERE id = %s",
                            (result_status_db, period_id)
                        )
                        reused_periods += 1
                    else:
                        cur.execute("""
                            INSERT INTO academic_periods (
                                student_id, academic_year, study_system_id,
                                stage_number, semester_num, result_status
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            student_id, item.academic_year.strip(), item.study_system_id or 1,
                            stg, sem_num, result_status_db
                        ))
                        period_id = cur.lastrowid
                        created_periods += 1

                    for sc in sc_list:
                        round_str = str(sc.passed_round or 1)
                        if round_str not in ("1", "2", "3"):
                            round_str = "1"

                        cur.execute("""
                            INSERT INTO enrollments (period_id, course_id, score, passed_round)
                            VALUES (%s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                                score = VALUES(score),
                                passed_round = VALUES(passed_round)
                        """, (period_id, sc.course_id, float(sc.score), round_str))
                        saved_enrollments += 1
            else:
                # No scores provided: ensure base academic period exists
                stg = item.stage_number or 1
                cur.execute("""
                    SELECT id FROM academic_periods
                    WHERE student_id = %s AND academic_year = %s AND stage_number = %s AND semester_num = %s
                    LIMIT 1
                """, (student_id, item.academic_year.strip(), stg, sem_num))
                p_row = cur.fetchone()

                if p_row:
                    period_id = p_row["id"]
                    cur.execute(
                        "UPDATE academic_periods SET result_status = %s WHERE id = %s",
                        (result_status_db, period_id)
                    )
                    reused_periods += 1
                else:
                    cur.execute("""
                        INSERT INTO academic_periods (
                            student_id, academic_year, study_system_id,
                            stage_number, semester_num, result_status
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        student_id, item.academic_year.strip(), item.study_system_id or 1,
                        stg, sem_num, result_status_db
                    ))
                    period_id = cur.lastrowid
                    created_periods += 1

        conn.commit()
        logger.info(
            f"Bulk import successfully completed: {created_students} created, "
            f"{updated_students} updated, {saved_enrollments} enrollments saved."
        )
        return {
            "status": "success",
            "created_students": created_students,
            "updated_students": updated_students,
            "created_periods": created_periods,
            "reused_periods": reused_periods,
            "saved_enrollments": saved_enrollments,
            "total_processed": len(payload.students)
        }

    except Exception as exc:
        conn.rollback()
        logger.error(f"Bulk student import transaction failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Atomic bulk import failed: {str(exc)}"
        )
    finally:
        cur.close()
