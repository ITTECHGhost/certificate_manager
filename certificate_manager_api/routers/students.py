"""Students routes: /students/* and /api/students/*.

search_router holds GET /students/search only. Before the split it was registered on main.py's
`router`, which is included first (before bulk_import), so main.py includes search_router there.
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel

from deps import logger, get_db, execute_sp_fetchall, execute_sp_fetchone

router = APIRouter()
search_router = APIRouter()


# ===========================================================================
# 2. Students Module
# ===========================================================================

class StudentPayload(BaseModel):
    full_name_ar: str
    full_name_en: str
    gender: Optional[int] = 1
    sequence_number: Optional[int] = None
    postgraduation_number: Optional[int] = None
    date_of_birth: Optional[str] = None
    birthplace_id: Optional[int] = None
    birthplace_other: Optional[str] = None
    nationality_id: Optional[int] = 1
    national_id: Optional[str] = None
    department_id: Optional[int] = None
    study_system_id: Optional[int] = None
    degree_level: Optional[int] = 1
    order_id: Optional[int] = None
    admission_year: Optional[str] = None
    summer_training_data: Optional[str] = None
    average: Optional[float] = None
    graduation_date: Optional[str] = None
    graduation_semester: Optional[str] = None


class StudentSearchResponse(BaseModel):
    student_id: int
    name_ar: Optional[str] = ""
    name_en: Optional[str] = ""
    department_name_ar: Optional[str] = ""
    graduation_year: Optional[str] = ""
    average: Optional[float] = 0.0


@router.get("/students/paginated")
def get_students_paginated(
    limit: int = 25,
    offset: int = 0,
    name_query: str = "",
    dept_id: Optional[int] = None,
    year: Optional[str] = None,
    conn=Depends(get_db)
):
    try:
        return execute_sp_fetchall(conn, "GetStudentsPaginated", (limit, offset, name_query, dept_id, year))
    except Exception as exc:
        logger.error(f"Error fetching paginated students: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@search_router.get("/students/search", response_model=List[StudentSearchResponse])
def search_students_paginated(
    query: str = Query("", description="Search term (Arabic or English)"),
    limit: int = Query(25, description="Rows per page (25, 50, 100)"),
    offset: int = Query(0, description="Pagination offset"),
    dept_id: Optional[int] = Query(None, description="Department ID filter"),
    conn=Depends(get_db)
):
    try:
        search_term = query.strip()
        if dept_id is not None:
            cur = conn.cursor(dictionary=True)
            if len(search_term) < 2:
                cur.execute("""
                    SELECT
                        s.id AS student_id,
                        COALESCE(s.full_name_ar, 'Unknown') AS name_ar,
                        COALESCE(s.full_name_en, 'Unknown') AS name_en,
                        COALESCE(d.name_ar, 'Unknown') AS department_name_ar,
                        COALESCE(YEAR(s.graduation_date), 'N/A') AS graduation_year,
                        COALESCE(s.average, 0.0) AS average
                    FROM students s
                    LEFT JOIN departments d ON s.department_id = d.id
                    WHERE s.department_id = %s
                    ORDER BY s.id DESC
                    LIMIT %s OFFSET %s
                """, (dept_id, limit, offset))
                raw_rows = cur.fetchall()
            else:
                search_pat = f"%{search_term}%"
                cur.execute("""
                    SELECT
                        s.id AS student_id,
                        COALESCE(s.full_name_ar, 'Unknown') AS name_ar,
                        COALESCE(s.full_name_en, 'Unknown') AS name_en,
                        COALESCE(d.name_ar, 'Unknown') AS department_name_ar,
                        COALESCE(YEAR(s.graduation_date), 'N/A') AS graduation_year,
                        COALESCE(s.average, 0.0) AS average
                    FROM students s
                    LEFT JOIN departments d ON s.department_id = d.id
                    WHERE s.department_id = %s
                      AND (s.full_name_ar LIKE %s OR s.full_name_en LIKE %s OR s.national_id LIKE %s)
                    ORDER BY
                        CASE
                            WHEN s.full_name_ar = %s OR s.full_name_en = %s OR s.national_id = %s THEN 1
                            WHEN s.full_name_ar LIKE %s OR s.full_name_en LIKE %s OR s.national_id LIKE %s THEN 2
                            ELSE 3
                        END,
                        s.full_name_ar ASC
                    LIMIT %s OFFSET %s
                """, (
                    dept_id, search_pat, search_pat, search_pat,
                    search_term, search_term, search_term,
                    f"{search_term}%", f"{search_term}%", f"{search_term}%",
                    limit, offset
                ))
                raw_rows = cur.fetchall()
        else:
            raw_rows = execute_sp_fetchall(conn, "SearchStudentsPaginated", (search_term, limit, offset))

        results = []
        for row in raw_rows:
            if isinstance(row, dict):
                if "id" in row and "student_id" not in row:
                    row["student_id"] = row["id"]
                if "full_name_ar" in row and "name_ar" not in row:
                    row["name_ar"] = row["full_name_ar"]
                if "full_name_en" in row and "name_en" not in row:
                    row["name_en"] = row["full_name_en"]
                if "dept_name_ar" in row and "department_name_ar" not in row:
                    row["department_name_ar"] = row["dept_name_ar"]
                if "admission_year" in row and "graduation_year" not in row:
                    row["graduation_year"] = str(row["admission_year"])
                results.append(row)
        return results
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database execution error: {str(exc)}"
        )


@router.get("/students/search/basic")
@router.get("/students/search/all")
def search_students_basic(query: str = "", limit: int = 50, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "SearchStudentsBasic", (query, limit))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/students/{student_id}")
def get_student_by_id(student_id: int, conn=Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "GetStudentDossierByID", (student_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Student not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error fetching student dossier: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/students/count/all")
def count_students(
    name_query: str = "",
    dept_id: Optional[int] = None,
    year: Optional[str] = None,
    conn=Depends(get_db)
):
    try:
        row = execute_sp_fetchone(conn, "CountStudentsFiltered", (name_query, dept_id, year))
        return row or {"total_count": 0}
    except Exception as exc:
        logger.error(f"Error counting students: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/students/by-order/{order_id}")
def get_students_by_order(order_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetStudentsByOrder", (order_id,))
    except Exception as exc:
        logger.error(f"Error fetching students by order: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/students/search/unlinked")
def search_students_unlinked(
    name_query: str = "",
    dept_id: Optional[int] = None,
    year: Optional[str] = None,
    limit: int = 50,
    conn=Depends(get_db)
):
    cur = conn.cursor(dictionary=True)
    try:
        conditions = ["(s.order_id IS NULL OR s.order_id = 0)"]
        params = []
        if name_query:
            pattern = f"%{name_query.strip()}%"
            conditions.append("(s.full_name_ar LIKE %s OR s.full_name_en LIKE %s)")
            params.extend([pattern, pattern])
        if dept_id:
            conditions.append("s.department_id = %s")
            params.append(dept_id)
        if year:
            conditions.append("(YEAR(s.graduation_date) = %s OR s.admission_year = %s)")
            params.extend([year, year])

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        return execute_sp_fetchall(conn, "SearchUnlinkedStudents", (dept_id, year))
    except Exception as exc:
        logger.error(f"Error searching unlinked students: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.get("/students/distinct/years")
def get_distinct_admission_years(conn=Depends(get_db)):
    try:
        rows = execute_sp_fetchall(conn, "GetDistinctGraduationYears")
        return [str(r["graduation_year"]) for r in rows if r.get("graduation_year") is not None]
    except Exception as exc:
        logger.error(f"Error getting distinct years: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/students")
def insert_student(payload: StudentPayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        args = (
            payload.full_name_ar, payload.full_name_en, payload.gender,
            payload.sequence_number, payload.postgraduation_number, payload.date_of_birth,
            payload.birthplace_id, payload.birthplace_other, payload.nationality_id,
            payload.national_id,
            payload.department_id, payload.study_system_id, payload.degree_level,
            payload.order_id, payload.admission_year, payload.summer_training_data,
            payload.average, payload.graduation_date, payload.graduation_semester
        )
        cur.callproc("InsertStudent", args)
        real_id = None
        if hasattr(cur, "stored_results"):
            for result in cur.stored_results():
                row = result.fetchone()
                if row:
                    if "new_id" in row:
                        real_id = row["new_id"]
                    elif "inserted_id" in row:
                        real_id = row["inserted_id"]
                    break
        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        if real_id is None:
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            real_id = cur.fetchone()["new_id"]
        conn.commit()
        return {"new_id": real_id, "inserted_id": real_id, "status": "success"}
    except Exception as exc:
        conn.rollback()
        logger.error(f"Error inserting student: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.put("/students/{student_id}")
def update_student(student_id: int, payload: StudentPayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        args = (
            student_id,
            payload.full_name_ar, payload.full_name_en, payload.gender,
            payload.sequence_number, payload.postgraduation_number, payload.date_of_birth,
            payload.birthplace_id, payload.birthplace_other, payload.nationality_id,
            payload.national_id,
            payload.department_id, payload.study_system_id, payload.degree_level,
            payload.order_id, payload.admission_year, payload.summer_training_data,
            payload.average, payload.graduation_date, payload.graduation_semester
        )
        cur.callproc("UpdateStudent", args)
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        logger.error(f"Error updating student: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.delete("/students/{student_id}")
@router.delete("/api/students/{student_id}")
def delete_student(student_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteStudent", (student_id,))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        logger.error(f"Error deleting student {student_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.post("/students/{student_id}/unlink-order")
@router.put("/students/{student_id}/unlink-order")
def unlink_from_order(student_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UnlinkStudentFromOrder", (student_id,))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        logger.error(f"Error unlinking student {student_id} from order: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.post("/students/link-order/{order_id}")
def link_students_to_order(order_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("LinkStudentsToOrder", (order_id,))
        row = None
        if hasattr(cur, "stored_results"):
            for result in cur.stored_results():
                row = result.fetchone()
                break
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        affected = row.get("affected_rows", 0) if row else 0
        return {"affected_rows": affected}
    except Exception as exc:
        conn.rollback()
        logger.error(f"Error linking students to order: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.post("/students/{student_id}/link-order/{order_id}")
@router.put("/students/{student_id}/link-order/{order_id}")
def link_student_to_order(student_id: int, order_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("LinkStudentsToOrder", (order_id,))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        logger.error(f"Error linking student to order: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.get("/api/students/{student_id}/periods")
def get_student_periods_api(student_id: int, conn=Depends(get_db)):
    try:
        periods = execute_sp_fetchall(conn, "GetAcademicPeriodsByStudent", (student_id,))
        for p in periods:
            p["enrollments"] = execute_sp_fetchall(conn, "GetEnrollmentsByPeriod", (p["id"],))
        return periods
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
