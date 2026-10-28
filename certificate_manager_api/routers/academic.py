"""Academic periods and enrollments routes: /academic-periods/* /api/periods/* /enrollments/* /api/enrollments/*."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import get_db, execute_sp_fetchall, execute_sp_fetchone, result_status_code

router = APIRouter()


# ===========================================================================
# 7. Academic Periods Module
# ===========================================================================

class AcademicPeriodPayload(BaseModel):
    student_id: int
    academic_year: str
    study_system_id: int
    stage_number: int
    semester_num: Optional[int] = 1
    result_status: Optional[str] = "PASSED"


class AcademicPeriodStatusPayload(BaseModel):
    result_status: str


@router.get("/academic-periods/by-student/{student_id}")
def get_academic_periods_by_student(student_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAcademicPeriodsByStudent", (student_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/academic-periods")
def insert_academic_period(payload: AcademicPeriodPayload, conn=Depends(get_db)):
    try:
        status_val = result_status_code(payload.result_status)
        res = execute_sp_fetchone(
            conn, "InsertAcademicPeriod",
            (payload.student_id, payload.academic_year, payload.stage_number, payload.semester_num, status_val)
        )
        new_id = res.get("new_period_id") or res.get("new_id", 0) if res else 0
        conn.commit()
        return {"new_id": new_id}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/academic-periods/{period_id}/status")
@router.patch("/api/periods/{period_id}/status")
def update_academic_period_status(period_id: int, payload: AcademicPeriodStatusPayload, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        raw_st = payload.result_status
        code_val = result_status_code(raw_st)
        cur.callproc("UpdateAcademicPeriodStatus", (period_id, str(code_val)))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success", "result_status": code_val}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.delete("/academic-periods/{period_id}")
def delete_academic_period(period_id: int, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.callproc("DeleteAcademicPeriod", (period_id,))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


# ===========================================================================
# 8. Enrollments Module
# ===========================================================================

class EnrollmentPayload(BaseModel):
    period_id: int
    course_id: int
    score: float
    is_second: Optional[int] = 0


@router.get("/enrollments/by-period/{period_id}")
def get_enrollments_by_period(period_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetEnrollmentsByPeriod", (period_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/enrollments")
def insert_enrollment(payload: EnrollmentPayload, conn=Depends(get_db)):
    try:
        val = payload.is_second
        if val == 2:
            passed_round = 2
        elif val == 3:
            passed_round = 3
        else:
            passed_round = 1
        res = execute_sp_fetchone(
            conn, "InsertEnrollment",
            (payload.period_id, payload.course_id, float(payload.score), int(passed_round))
        )
        new_id = res.get("new_enrollment_id") or res.get("new_id", 0) if res else 0
        conn.commit()
        return {"new_id": new_id}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/enrollments/{enrollment_id}")
@router.put("/api/enrollments/{enrollment_id}")
def update_enrollment(enrollment_id: int, score: float, is_second: int, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        val = int(is_second)
        if val == 2:
            passed_round = 2
        elif val == 3:
            passed_round = 3
        elif val == 0:
            passed_round = 0
        else:
            passed_round = 1
        cur.callproc("UpdateEnrollment", (enrollment_id, float(score), int(passed_round)))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.delete("/enrollments/{enrollment_id}")
def delete_enrollment(enrollment_id: int, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.callproc("DeleteEnrollment", (enrollment_id,))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()
