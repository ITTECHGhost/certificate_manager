"""Study routines routes: /study-routines/* /api/study-routine*/*."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import get_db, execute_sp_fetchall, execute_sp_fetchone

router = APIRouter()


# ===========================================================================
# 15. Study Routines, Periods & Courses Module
# ===========================================================================

class StudyRoutinePayload(BaseModel):
    name_ar: str
    name_en: str
    department_id: int
    study_system_id: Optional[int] = 1
    stage_number: Optional[int] = 1
    semester_num: Optional[int] = 1


class RoutineCoursePayload(BaseModel):
    routine_id: int
    course_id: int


class RoutinePeriodPayload(BaseModel):
    routine_id: int
    stage_number: int
    semester_num: Optional[int] = 1


class RoutinePeriodCoursePayload(BaseModel):
    period_id: int
    course_id: int


@router.get("/api/study-routines")
@router.get("/study-routines")
def get_all_study_routines(conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAllStudyRoutines")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/study-routines/{routine_id}")
@router.get("/study-routines/{routine_id}")
def get_study_routine_by_id(routine_id: int, conn=Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "GetStudyRoutineById", (routine_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Study routine not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/study-routines")
@router.post("/study-routines")
def insert_study_routine(payload: StudyRoutinePayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc(
            "InsertStudyRoutine",
            (
                payload.name_ar,
                payload.name_en,
                payload.department_id,
                payload.study_system_id or 1,
            )
        )
        real_id = None
        if hasattr(cur, "stored_results"):
            for result in cur.stored_results():
                row = result.fetchone()
                if row:
                    if "new_id" in row:
                        real_id = row["new_id"]
                    elif "inserted_id" in row:
                        real_id = row["inserted_id"]
                    elif "id" in row:
                        real_id = row["id"]
                    break
        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        if real_id is None:
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            r = cur.fetchone()
            if r:
                real_id = r.get("new_id")

        conn.commit()
        return {"new_id": real_id, "inserted_id": real_id, "status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.put("/api/study-routines/{routine_id}")
@router.put("/study-routines/{routine_id}")
def update_study_routine(routine_id: int, payload: StudyRoutinePayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc(
            "UpdateStudyRoutine",
            (
                routine_id,
                payload.name_ar,
                payload.name_en,
                payload.department_id,
                payload.study_system_id or 1,
            )
        )
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success", "message": "Study routine updated successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        err_msg = str(exc)
        if "Duplicate entry" in err_msg or "45000" in err_msg:
            raise HTTPException(
                status_code=400,
                detail="Duplicate entry: A routine with this name already exists in this department and study system."
            )
        raise HTTPException(status_code=500, detail=err_msg)
    finally:
        cur.close()


@router.delete("/api/study-routines/{routine_id}")
@router.delete("/study-routines/{routine_id}")
def delete_study_routine(routine_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteStudyRoutine", (routine_id,))
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


@router.get("/api/study-routine-courses/{routine_id}")
@router.get("/study-routine-courses/{routine_id}")
def get_study_routine_courses(routine_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetStudyRoutineCourses", (routine_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/study-routine-courses")
def insert_study_routine_course(payload: RoutineCoursePayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("InsertStudyRoutineCourse", (payload.routine_id, payload.course_id))
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


@router.delete("/api/study-routine-courses/{routine_id}/{course_id}")
def delete_study_routine_course(routine_id: int, course_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteStudyRoutineCourse", (routine_id, course_id))
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


@router.get("/api/study-routine-periods/{routine_id}")
def get_study_routine_periods(routine_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetStudyRoutinePeriods", (routine_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/study-routine-periods")
def insert_study_routine_period(payload: RoutinePeriodPayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc(
            "InsertStudyRoutinePeriod",
            (payload.routine_id, payload.stage_number, payload.semester_num or 1)
        )
        real_id = None
        if hasattr(cur, "stored_results"):
            for result in cur.stored_results():
                row = result.fetchone()
                if row:
                    real_id = row.get("new_id") or row.get("inserted_id") or row.get("id")
                    break
        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        if real_id is None:
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            r = cur.fetchone()
            if r:
                real_id = r.get("new_id")

        conn.commit()
        return {"new_id": real_id, "inserted_id": real_id, "status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.put("/api/study-routine-periods/{period_id}")
def update_study_routine_period(period_id: int, payload: RoutinePeriodPayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc(
            "UpdateStudyRoutinePeriod",
            (period_id, payload.stage_number, payload.semester_num or 1)
        )
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


@router.delete("/api/study-routine-periods/{period_id}")
def delete_study_routine_period(period_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteStudyRoutinePeriod", (period_id,))
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


@router.get("/api/study-routine-period-courses/{period_id}")
def get_study_routine_period_courses(period_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetStudyRoutinePeriodCourses", (period_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/study-routine-period-courses")
def insert_study_routine_period_course(payload: RoutinePeriodCoursePayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("InsertStudyRoutinePeriodCourse", (payload.period_id, payload.course_id))
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


@router.delete("/api/study-routine-period-courses/{period_id}/{course_id}")
def delete_study_routine_period_course(period_id: int, course_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteStudyRoutinePeriodCourse", (period_id, course_id))
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
