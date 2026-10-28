"""Courses routes: /courses/* and /api/courses/*."""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import logger, get_db, execute_sp_fetchall, execute_sp_fetchone

router = APIRouter()


# ===========================================================================
# 5. Courses Module
# ===========================================================================

class CoursePayload(BaseModel):
    name_ar: str
    name_en: str
    credit_hours: int
    department_id: Optional[int] = None
    stage_number: int
    study_system_id: Optional[int] = None
    is_shared: Optional[int] = None
    shared_dept_ids: Optional[List[int]] = None


@router.get("/courses")
@router.get("/api/courses")
def get_courses(conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAllCourses")
    except Exception as exc:
        logger.warning(f"GetAllCourses SP failed ({exc}), falling back to direct SELECT")
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute("""
                SELECT
                    c.id,
                    c.name_ar,
                    c.name_en,
                    c.credit_hours,
                    c.stage_number,
                    c.department_id,
                    d.name_ar AS dept_name_ar,
                    d.name_en AS dept_name_en
                FROM courses c
                LEFT JOIN departments d ON c.department_id = d.id
                ORDER BY c.stage_number ASC, c.name_ar ASC
            """)
            return cur.fetchall()
        except Exception as exc2:
            raise HTTPException(status_code=500, detail=str(exc2))
        finally:
            cur.close()


@router.get("/courses/by-dept/{dept_id}")
@router.get("/api/courses/by-dept/{dept_id}")
def get_courses_by_dept(dept_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetCoursesByDepartment", (dept_id,))
    except Exception as exc:
        logger.warning(f"GetCoursesByDepartment SP failed ({exc}), falling back to direct SELECT")
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute("""
                SELECT
                    c.id, c.name_ar, c.name_en, c.credit_hours, c.stage_number, c.department_id,
                    d.name_ar AS dept_name_ar, d.name_en AS dept_name_en
                FROM courses c
                LEFT JOIN departments d ON c.department_id = d.id
                WHERE c.department_id = %s
                ORDER BY c.stage_number ASC, c.name_ar ASC
            """, (dept_id,))
            return cur.fetchall()
        except Exception as exc2:
            raise HTTPException(status_code=500, detail=str(exc2))
        finally:
            cur.close()


@router.get("/courses/by-dept-stage-system")
@router.get("/api/courses/by-dept-stage-system")
def get_courses_by_dept_stage_system(dept_id: int, stage: int, system_id: Optional[int] = None, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            SELECT
                c.id, c.name_ar, c.name_en, c.credit_hours, c.stage_number, c.department_id,
                d.name_ar AS dept_name_ar, d.name_en AS dept_name_en
            FROM courses c
            LEFT JOIN departments d ON c.department_id = d.id
            WHERE c.department_id = %s AND c.stage_number = %s
            ORDER BY c.name_ar ASC
        """, (dept_id, stage))
        return cur.fetchall()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.get("/courses/{course_id}/shared-depts")
def get_shared_dept_ids(course_id: int, conn=Depends(get_db)):
    return []


@router.post("/courses")
@router.post("/api/courses")
def insert_course(payload: CoursePayload, conn=Depends(get_db)):
    try:
        if payload.shared_dept_ids:
            new_ids = []
            for dept_id in payload.shared_dept_ids:
                res = execute_sp_fetchone(conn, "InsertCourse", (payload.name_ar, payload.name_en, payload.credit_hours, dept_id, payload.stage_number))
                if res and "new_course_id" in res:
                    new_ids.append(res["new_course_id"])
            conn.commit()
            return {"new_id": new_ids[0] if new_ids else 0}
        else:
            res = execute_sp_fetchone(conn, "InsertCourse", (payload.name_ar, payload.name_en, payload.credit_hours, payload.department_id, payload.stage_number))
            new_id = res.get("new_course_id", 0) if res else 0
            conn.commit()
            return {"new_id": new_id}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/courses/{course_id}")
@router.put("/api/courses/{course_id}")
def update_course(course_id: int, payload: CoursePayload, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        dept_id = payload.department_id
        if not dept_id and payload.shared_dept_ids:
            dept_id = payload.shared_dept_ids[0]
        cur.callproc("UpdateCourse", (course_id, payload.name_ar, payload.name_en, payload.credit_hours, dept_id, payload.stage_number))
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


@router.delete("/courses/{course_id}")
@router.delete("/api/courses/{course_id}")
def delete_course(course_id: int, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.callproc("DeleteCourse", (course_id,))
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
