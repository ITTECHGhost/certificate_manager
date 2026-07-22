from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union
import mysql.connector
from mysql.connector import pooling
import os
import logging
from contextlib import asynccontextmanager

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database on server startup...")
    try:
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from db import init_db
        init_db()
        logger.info("Database initialization successful.")
    except Exception as e:
        logger.error(f"Failed to initialize database on startup: {e}")
    yield

app = FastAPI(title="Certificate Manager API", lifespan=lifespan)


# Database Configuration (supports overrides from environment variables)
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "12345678")
DB_NAME = os.environ.get("DB_NAME", "certificate_manager")

# Global API Connection Pool
_api_connection_pool = None

# Table metadata matching sync_engine.py
TABLE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "students": {
        "sp_name": "InsertStudent",
        "sp_args": [
            "full_name_ar", "full_name_en", "gender",
            "sequence_number", "postgraduation_number", "date_of_birth",
            "birthplace_id", "birthplace_other", "nationality_id",
            "department_id", "study_system_id", "degree_level",
            "order_id", "admission_year", "summer_training_data",
            "average", "graduation_date", "graduation_semester",
        ],
    },
    "academic_periods": {
        "sp_name": None,
        "insert_sql": (
            "INSERT INTO academic_periods "
            "(student_id, academic_year, study_system_id, stage_number, semester_num) "
            "VALUES (%s, %s, %s, %s, %s)"
        ),
        "insert_keys": [
            "student_id", "academic_year", "study_system_id",
            "stage_number", "semester_num",
        ],
    },
    "enrollments": {
        "sp_name": None,
        "insert_sql": (
            "INSERT INTO enrollments "
            "(period_id, course_id, score, passed_round) "
            "VALUES (%s, %s, %s, %s)"
        ),
        "insert_keys": [
            "period_id", "course_id", "score", "passed_round",
        ],
    },
}

# Request Validation Models
class SyncAction(BaseModel):
    id: int
    table_name: str
    operation: str
    temp_id: int
    payload: Dict[str, Any]

class SyncPayload(BaseModel):
    actions: List[SyncAction]

def get_db():
    """Dependency to retrieve a MySQL database connection from the connection pool."""
    global _api_connection_pool
    if _api_connection_pool is None:
        _api_connection_pool = pooling.MySQLConnectionPool(
            pool_name="api_pool",
            pool_size=15,
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
        )
    conn = _api_connection_pool.get_connection()
    try:
        yield conn
    finally:
        conn.close()

@app.get("/ping")
def ping():
    """Health check endpoint to verify database server connectivity/status."""
    return {"status": "online"}

def resolve_payload_fks(payload: dict, id_map: dict) -> dict:
    """Resolve temporary IDs (negative integers) to real database auto-increment IDs."""
    resolved = {}
    for k, v in payload.items():
        if v in id_map:
            resolved[k] = id_map[v]
        elif isinstance(v, str) and v.lstrip('-').isdigit():
            # If the value is a stringified negative number, resolve it if mapped
            int_val = int(v)
            if int_val in id_map:
                resolved[k] = id_map[int_val]
            else:
                resolved[k] = v
        else:
            resolved[k] = v
    return resolved

@app.post("/sync")
def sync_offline_queue(payload: SyncPayload, conn=Depends(get_db)):
    """
    Synchronize a batch of offline actions to MySQL in a single transaction.
    Returns a dictionary mapping temp_id -> real_id.
    """
    id_map = {}
    
    try:
        for action in payload.actions:
            tbl = action.table_name
            temp_id = action.temp_id
            
            if tbl not in TABLE_REGISTRY:
                logger.error(f"Table '{tbl}' is not in TABLE_REGISTRY.")
                raise HTTPException(status_code=400, detail=f"Unsupported table: {tbl}")
            
            # Resolve foreign keys referencing previously resolved records in this batch
            resolved_payload = resolve_payload_fks(action.payload, id_map)
            
            # Remove the synthetic client-side 'id' key so MySQL generates a fresh PK
            resolved_payload.pop("id", None)
            
            meta = TABLE_REGISTRY[tbl]
            cur = conn.cursor(dictionary=True)
            try:
                if meta["sp_name"]:
                    # Execute Stored Procedure
                    sp_args = tuple(resolved_payload.get(k) for k in meta["sp_args"])
                    logger.info(f"Calling SP {meta['sp_name']} with args {sp_args}")
                    cur.callproc(meta["sp_name"], sp_args)
                    
                    real_id = None
                    # Retrieve the generated ID from the stored procedure result rows
                    for result in cur.stored_results():
                        row = result.fetchone()
                        if row and "new_id" in row:
                            real_id = row["new_id"]
                            break
                    
                    if real_id is None:
                        # Fallback to LAST_INSERT_ID() if SP does not return new_id row
                        cur.execute("SELECT LAST_INSERT_ID() AS new_id")
                        real_id = cur.fetchone()["new_id"]
                else:
                    # Execute Raw INSERT
                    insert_sql = meta["insert_sql"]
                    insert_keys = meta["insert_keys"]
                    values = tuple(resolved_payload.get(k) for k in insert_keys)
                    logger.info(f"Executing raw SQL: {insert_sql} with values {values}")
                    cur.execute(insert_sql, values)
                    real_id = cur.lastrowid
                
                id_map[temp_id] = real_id
                logger.info(f"Successfully inserted {tbl}: temp_id={temp_id} -> real_id={real_id}")
            finally:
                cur.close()
                
        # Commit the transaction for all successfully processed inserts
        conn.commit()
        return {"id_map": id_map}
        
    except Exception as exc:
        conn.rollback()
        logger.exception("Database sync failed. Rolling back transaction.")
        raise HTTPException(
            status_code=500,
            detail=f"Database synchronization failed: {str(exc)}"
        )

class StudentSearchResponse(BaseModel):
    student_id: int
    name_ar: str
    name_en: str
    dept_name_ar: Optional[str] = None
    graduation_year: Optional[Union[str, int]] = None
    admission_year: Optional[Union[str, int]] = None
    average: Optional[float] = None

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
    department_id: Optional[int] = None
    study_system_id: Optional[int] = None
    degree_level: Optional[int] = 1
    order_id: Optional[int] = None
    admission_year: Optional[str] = None
    summer_training_data: Optional[str] = None
    average: Optional[float] = None
    graduation_date: Optional[str] = None
    graduation_semester: Optional[str] = None

@app.get("/students/paginated")
def get_students_paginated(
    limit: int = 25,
    offset: int = 0,
    name_query: str = "",
    dept_id: Optional[int] = None,
    year: Optional[str] = None,
    conn = Depends(get_db)
):
    """Call GetStudentsPaginated SP on the database."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetStudentsPaginated", (limit, offset, name_query, dept_id, year))
        rows = []
        for result in cur.stored_results():
            rows.extend(result.fetchall())
        return rows
    except Exception as exc:
        logger.error(f"Error fetching paginated students: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/students/search/basic", response_model=List[StudentSearchResponse])
def search_students_basic(query: str, limit: int = 50, db = Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    try:
        # Execute the Stored Procedure
        cursor.callproc("SearchStudentsBasic", (query, limit))
        # Fetch the results from the procedure's output
        results = []
        for result_set in cursor.stored_results():
            results.extend(result_set.fetchall())
            
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()

@app.get("/students/{student_id}")
def get_student_by_id(student_id: int, conn = Depends(get_db)):
    """Call GetStudentDossierByID SP on the database."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetStudentDossierByID", (student_id,))
        row = None
        for result in cur.stored_results():
            r = result.fetchone()
            if r:
                row = r
                break
        if not row:
            raise HTTPException(status_code=404, detail="Student not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error fetching student dossier: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/students/search/all")
def search_students(query: str, limit: int = 8, conn = Depends(get_db)):
    """Call SearchStudentsBasic SP on the database."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("SearchStudentsBasic", (query, limit))
        rows = []
        for result in cur.stored_results():
            rows.extend(result.fetchall())
        return rows
    except Exception as exc:
        logger.error(f"Error searching students: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/students/count/all")
def count_students(
    name_query: str = "",
    dept_id: Optional[int] = None,
    year: Optional[str] = None,
    conn = Depends(get_db)
):
    """Call CountStudentsFiltered SP on the database."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("CountStudentsFiltered", (name_query, dept_id, year))
        row = None
        for result in cur.stored_results():
            row = result.fetchone()
            break
        return row or {"total_count": 0}
    except Exception as exc:
        logger.error(f"Error counting students: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/students/by-order/{order_id}")
def get_students_by_order(order_id: int, conn = Depends(get_db)):
    """Call GetStudentsByOrder SP on the database."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetStudentsByOrder", (order_id,))
        rows = []
        for result in cur.stored_results():
            rows.extend(result.fetchall())
        return rows
    except Exception as exc:
        logger.error(f"Error fetching students by order: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/students/distinct/years")
def get_distinct_admission_years(conn = Depends(get_db)):
    """Select distinct graduation years (extracted from graduation_date) from the students table."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT DISTINCT YEAR(graduation_date) AS graduation_year FROM students WHERE graduation_date IS NOT NULL ORDER BY graduation_year DESC")
        rows = cur.fetchall()
        return [str(r["graduation_year"]) for r in rows if r["graduation_year"] is not None]
    except Exception as exc:
        logger.error(f"Error getting distinct years: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/students")
def insert_student(payload: StudentPayload, conn = Depends(get_db)):
    """Call InsertStudent SP on the database."""
    cur = conn.cursor(dictionary=True)
    try:
        args = (
            payload.full_name_ar, payload.full_name_en, payload.gender,
            payload.sequence_number, payload.postgraduation_number, payload.date_of_birth,
            payload.birthplace_id, payload.birthplace_other, payload.nationality_id,
            payload.department_id, payload.study_system_id, payload.degree_level,
            payload.order_id, payload.admission_year, payload.summer_training_data,
            payload.average, payload.graduation_date, payload.graduation_semester
        )
        cur.callproc("InsertStudent", args)
        conn.commit()
        
        real_id = None
        for result in cur.stored_results():
            row = result.fetchone()
            if row and "new_id" in row:
                real_id = row["new_id"]
                break
        if real_id is None:
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            real_id = cur.fetchone()["new_id"]
        return {"new_id": real_id}
    except Exception as exc:
        conn.rollback()
        logger.error(f"Error inserting student: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/students/{student_id}")
def update_student(student_id: int, payload: StudentPayload, conn = Depends(get_db)):
    """Call UpdateStudent SP on the database."""
    cur = conn.cursor(dictionary=True)
    try:
        args = (
            student_id,
            payload.full_name_ar, payload.full_name_en, payload.gender,
            payload.sequence_number, payload.postgraduation_number, payload.date_of_birth,
            payload.birthplace_id, payload.birthplace_other, payload.nationality_id,
            payload.department_id, payload.study_system_id, payload.degree_level,
            payload.order_id, payload.admission_year, payload.summer_training_data,
            payload.average, payload.graduation_date, payload.graduation_semester
        )
        cur.callproc("UpdateStudent", args)
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        logger.error(f"Error updating student: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.delete("/students/{student_id}")
def delete_student(student_id: int, conn = Depends(get_db)):
    """Call DeleteStudent SP on the database."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteStudent", (student_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        logger.error(f"Error deleting student: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/students/{student_id}/unlink-order")
def unlink_from_order(student_id: int, conn = Depends(get_db)):
    """Call UnlinkStudentFromOrder SP on the database."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UnlinkStudentFromOrder", (student_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        logger.error(f"Error unlinking student from order: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/students/link-order/{order_id}")
def link_students_to_order(order_id: int, conn = Depends(get_db)):
    """Call LinkStudentsToOrder SP on the database."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("LinkStudentsToOrder", (order_id,))
        conn.commit()
        row = None
        for result in cur.stored_results():
            row = result.fetchone()
            break
        affected = row.get("affected_rows", 0) if row else 0
        return {"affected_rows": affected}
    except Exception as exc:
        conn.rollback()
        logger.error(f"Error linking students to order: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/students/{student_id}/link-order/{order_id}")
def link_student_to_order(student_id: int, order_id: int, conn = Depends(get_db)):
    """Link a single student to a graduation order."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT order_date, graduation_semester FROM graduation_orders WHERE id = %s",
            (order_id,)
        )
        order = cur.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Graduation order not found")
        
        cur.execute(
            "UPDATE students SET order_id = %s, graduation_date = %s, graduation_semester = %s WHERE id = %s",
            (order_id, order["order_date"], order["graduation_semester"], student_id)
        )
        conn.commit()
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        logger.error(f"Error linking student to order: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

# --- DEPARTMENTS ENDPOINTS ---
class DepartmentPayload(BaseModel):
    name_ar: str
    name_en: str
    university_settings_id: Optional[int] = 1

@app.get("/departments")
def get_departments(conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetAllDepartments")
        rows = []
        for result in cur.stored_results():
            rows.extend(result.fetchall())
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/departments/{dept_id}")
def get_department(dept_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetDepartmentByID", (dept_id,))
        row = None
        for result in cur.stored_results():
            row = result.fetchone()
            break
        if not row:
            raise HTTPException(status_code=404, detail="Department not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/departments")
def insert_department(payload: DepartmentPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("InsertDepartment", (payload.name_ar, payload.name_en, payload.university_settings_id))
        conn.commit()
        real_id = None
        for result in cur.stored_results():
            row = result.fetchone()
            if row and "new_id" in row:
                real_id = row["new_id"]
                break
        if real_id is None:
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            real_id = cur.fetchone()["new_id"]
        return {"new_id": real_id}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/departments/{dept_id}")
def update_department(dept_id: int, payload: DepartmentPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UpdateDepartment", (dept_id, payload.name_ar, payload.name_en, payload.university_settings_id))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.delete("/departments/{dept_id}")
def delete_department(dept_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteDepartment", (dept_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

# --- STUDY SYSTEMS ENDPOINTS ---
class StudySystemPayload(BaseModel):
    name_ar: str
    name_en: str
    calculation_rule: Optional[str] = "annual"
    calculation_weights: Optional[str] = "10:20:30:40"
    period_display: Optional[str] = "year"
    is_active: Optional[int] = 1

@app.get("/study-systems")
def get_study_systems(conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetAllStudySystems")
        rows = []
        for result in cur.stored_results():
            rows.extend(result.fetchall())
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/study-systems/active")
def get_active_study_systems(conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetActiveStudySystems")
        rows = []
        for result in cur.stored_results():
            rows.extend(result.fetchall())
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/study-systems/{sys_id}")
def get_study_system(sys_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetStudySystemByID", (sys_id,))
        row = None
        for result in cur.stored_results():
            row = result.fetchone()
            break
        if not row:
            raise HTTPException(status_code=404, detail="Study system not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/study-systems")
def insert_study_system(payload: StudySystemPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("InsertStudySystem", (payload.name_ar, payload.name_en, "Morning", payload.calculation_rule, payload.calculation_weights, payload.period_display, 1))
        conn.commit()
        real_id = None
        for result in cur.stored_results():
            row = result.fetchone()
            if row and "new_id" in row:
                real_id = row["new_id"]
                break
        if real_id is None:
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            real_id = cur.fetchone()["new_id"]
        return {"new_id": real_id}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/study-systems/{sys_id}")
def update_study_system(sys_id: int, payload: StudySystemPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UpdateStudySystem", (sys_id, payload.name_ar, payload.name_en, "Morning", payload.calculation_rule, payload.calculation_weights, payload.period_display, payload.is_active))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/study-systems/{sys_id}/toggle")
def toggle_study_system(sys_id: int, is_active: int, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.execute("UPDATE study_systems SET is_active = %s WHERE id = %s", (is_active, sys_id))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.delete("/study-systems/{sys_id}")
def delete_study_system(sys_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteStudySystem", (sys_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

# --- COURSES ENDPOINTS ---
class CoursePayload(BaseModel):
    name_ar: str
    name_en: str
    credit_hours: int
    department_id: Optional[int] = None
    stage_number: int
    study_system_id: Optional[int] = None
    is_shared: Optional[int] = None
    shared_dept_ids: Optional[List[int]] = None

@app.get("/courses")
def get_courses(conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        query = (
            "SELECT c.id, c.name_ar, c.name_en, c.credit_hours, c.stage_number, "
            "       c.department_id, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en "
            "FROM courses c "
            "LEFT JOIN departments d ON c.department_id = d.id "
            "ORDER BY c.name_ar ASC"
        )
        cur.execute(query)
        return cur.fetchall()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/courses/by-dept/{dept_id}")
def get_courses_by_dept(dept_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        query = (
            "SELECT id, name_ar, name_en, credit_hours, department_id, stage_number "
            "FROM courses "
            "WHERE department_id = %s "
            "ORDER BY name_ar ASC"
        )
        cur.execute(query, (dept_id,))
        return cur.fetchall()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/courses/by-dept-stage-system")
def get_courses_by_dept_stage_system(dept_id: int, stage: int, system_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        query = (
            "SELECT id, name_ar, name_en, credit_hours, stage_number FROM courses "
            "WHERE department_id = %s AND stage_number <= %s "
            "ORDER BY stage_number, name_ar"
        )
        cur.execute(query, (dept_id, stage))
        return cur.fetchall()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/courses/{course_id}/shared-depts")
def get_shared_dept_ids(course_id: int, conn = Depends(get_db)):
    return []

@app.post("/courses")
def insert_course(payload: CoursePayload, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        # If shared_dept_ids is provided, insert distinct instances per department
        if payload.shared_dept_ids:
            new_ids = []
            for dept_id in payload.shared_dept_ids:
                query = (
                    "INSERT INTO courses (name_ar, name_en, credit_hours, department_id, stage_number) "
                    "VALUES (%s, %s, %s, %s, %s)"
                )
                cur.execute(query, (payload.name_ar, payload.name_en, payload.credit_hours, dept_id, payload.stage_number))
                new_ids.append(cur.lastrowid)
            conn.commit()
            return {"new_id": new_ids[0] if new_ids else 0}
        else:
            query = (
                "INSERT INTO courses (name_ar, name_en, credit_hours, department_id, stage_number) "
                "VALUES (%s, %s, %s, %s, %s)"
            )
            cur.execute(query, (payload.name_ar, payload.name_en, payload.credit_hours, payload.department_id, payload.stage_number))
            new_id = cur.lastrowid
            conn.commit()
            return {"new_id": new_id}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/courses/{course_id}")
def update_course(course_id: int, payload: CoursePayload, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        dept_id = payload.department_id
        if not dept_id and payload.shared_dept_ids:
            dept_id = payload.shared_dept_ids[0]
            
        query = (
            "UPDATE courses SET name_ar=%s, name_en=%s, credit_hours=%s, department_id=%s, stage_number=%s "
            "WHERE id=%s"
        )
        cur.execute(query, (payload.name_ar, payload.name_en, payload.credit_hours, dept_id, payload.stage_number, course_id))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.delete("/courses/{course_id}")
def delete_course(course_id: int, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM courses WHERE id=%s", (course_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

# --- PERSONNEL ENDPOINTS ---
class PersonnelPayload(BaseModel):
    name_ar: str
    name_en: str
    academic_title_ar: Optional[str] = None
    academic_title_en: Optional[str] = None
    responsibility_ar: Optional[str] = None
    responsibility_en: Optional[str] = None
    display_order: Optional[int] = 0
    username: str
    password_hash: str
    personnel_role: Optional[str] = "user"
    settings_id: Optional[int] = 1
    university_settings_id: Optional[int] = 1
    page_location: Optional[str] = "front"
    is_active: Optional[int] = 1

class LoginPayload(BaseModel):
    username: str
    password_hash: str

@app.get("/personnel")
def get_personnel(conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetAllPersonnel")
        rows = []
        for result in cur.stored_results():
            rows.extend(result.fetchall())
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/personnel/active")
def get_active_personnel(conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetActivePersonnel")
        rows = []
        for result in cur.stored_results():
            rows.extend(result.fetchall())
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/personnel/login")
def authenticate_personnel(payload: LoginPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("AuthenticateUser", (payload.username, payload.password_hash))
        row = None
        for result in cur.stored_results():
            row = result.fetchone()
            break
        if not row:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/personnel")
def insert_personnel(payload: PersonnelPayload, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        fields = payload.model_dump()
        columns = ", ".join(fields.keys())
        placeholders = ", ".join(["%s"] * len(fields))
        values = tuple(fields.values())
        query = f"INSERT INTO personnel ({columns}) VALUES ({placeholders})"
        cur.execute(query, values)
        conn.commit()
        return {"new_id": cur.lastrowid}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/personnel/{person_id}")
def update_personnel(person_id: int, payload: PersonnelPayload, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        fields = payload.model_dump()
        set_clause = ", ".join([f"{f}=%s" for f in fields.keys()])
        values = tuple(fields.values()) + (person_id,)
        query = f"UPDATE personnel SET {set_clause} WHERE id=%s"
        cur.execute(query, values)
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/personnel/{person_id}/toggle")
def toggle_personnel(person_id: int, is_active: int, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.execute("UPDATE personnel SET is_active = %s WHERE id = %s", (is_active, person_id))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.delete("/personnel/{person_id}")
def delete_personnel(person_id: int, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM personnel WHERE id = %s", (person_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

# --- ACADEMIC PERIODS ENDPOINTS ---
class AcademicPeriodPayload(BaseModel):
    student_id: int
    academic_year: str
    study_system_id: int
    stage_number: int
    semester_num: Optional[int] = 1

@app.get("/academic-periods/by-student/{student_id}")
def get_academic_periods_by_student(student_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetAcademicPeriodsByStudent", (student_id,))
        rows = []
        for result in cur.stored_results():
            rows.extend(result.fetchall())
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/academic-periods")
def insert_academic_period(payload: AcademicPeriodPayload, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        query = (
            "INSERT INTO academic_periods (student_id, academic_year, study_system_id, stage_number, semester_num) "
            "VALUES (%s, %s, %s, %s, %s)"
        )
        cur.execute(query, (payload.student_id, payload.academic_year, payload.study_system_id, payload.stage_number, payload.semester_num))
        conn.commit()
        return {"new_id": cur.lastrowid}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.delete("/academic-periods/{period_id}")
def delete_academic_period(period_id: int, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM academic_periods WHERE id=%s", (period_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

# --- ENROLLMENTS ENDPOINTS ---
class EnrollmentPayload(BaseModel):
    period_id: int
    course_id: int
    score: float
    is_second: Optional[int] = 0

@app.get("/enrollments/by-period/{period_id}")
def get_enrollments_by_period(period_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetEnrollmentsByPeriod", (period_id,))
        rows = []
        for result in cur.stored_results():
            rows.extend(result.fetchall())
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/enrollments")
def insert_enrollment(payload: EnrollmentPayload, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        val = payload.is_second
        if val == 2:
            passed_round = '2'
        elif val == 3:
            passed_round = '3'
        else:
            passed_round = '1'
        query = "INSERT INTO enrollments (period_id, course_id, score, passed_round) VALUES (%s, %s, %s, %s)"
        cur.execute(query, (payload.period_id, payload.course_id, payload.score, passed_round))
        conn.commit()
        return {"new_id": cur.lastrowid}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/enrollments/{enrollment_id}")
def update_enrollment(enrollment_id: int, score: float, is_second: int, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        val = is_second
        if val == 2:
            passed_round = '2'
        elif val == 3:
            passed_round = '3'
        else:
            passed_round = '1'
        query = "UPDATE enrollments SET score=%s, passed_round=%s WHERE id=%s"
        cur.execute(query, (score, passed_round, enrollment_id))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.delete("/enrollments/{enrollment_id}")
def delete_enrollment(enrollment_id: int, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM enrollments WHERE id=%s", (enrollment_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

# --- GRADUATION ORDERS ENDPOINTS ---
class GraduationOrderPayload(BaseModel):
    order_number: str
    order_date: str
    department_id: int
    study_type: str
    graduation_year: Union[int, str]
    graduation_semester: str
    num_students: int
    notes: Optional[str] = None
    study_system_id: Optional[int] = 1

@app.get("/graduation-orders")
@app.get("/orders")
def get_graduation_orders(limit: int = 25, offset: int = 0, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetAllGraduationOrders", (limit, offset))
        rows = []
        for result in cur.stored_results():
            rows.extend(result.fetchall())
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/graduation-orders/{order_id}")
@app.get("/orders/{order_id}")
def get_graduation_order(order_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetGraduationOrderByID", (order_id,))
        row = None
        for result in cur.stored_results():
            row = result.fetchone()
            break
        if not row:
            raise HTTPException(status_code=404, detail="Order not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/graduation-orders")
@app.post("/orders")
def insert_graduation_order(payload: GraduationOrderPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        args = (
            payload.order_number, payload.order_date, payload.department_id,
            payload.study_type, payload.graduation_year, payload.graduation_semester,
            payload.num_students, payload.notes, payload.study_system_id
        )
        cur.callproc("InsertGraduationOrder", args)
        conn.commit()
        real_id = None
        for result in cur.stored_results():
            row = result.fetchone()
            if row and "new_id" in row:
                real_id = row["new_id"]
                break
        if real_id is None:
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            real_id = cur.fetchone()["new_id"]
        return {"new_id": real_id}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/graduation-orders/{order_id}")
@app.put("/orders/{order_id}")
def update_graduation_order(order_id: int, payload: GraduationOrderPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        args = (
            order_id, payload.order_number, payload.order_date, payload.department_id,
            payload.study_type, payload.graduation_year, payload.graduation_semester,
            payload.num_students, payload.notes, payload.study_system_id
        )
        cur.callproc("UpdateGraduationOrder", args)
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.delete("/graduation-orders/{order_id}")
@app.delete("/orders/{order_id}")
def delete_graduation_order(order_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteGraduationOrder", (order_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

# --- SETTINGS ENDPOINTS ---
class SettingsPayload(BaseModel):
    univ_name_ar: str
    univ_name_en: str
    college_name_ar: str
    college_name_en: str

class AppearancePayload(BaseModel):
    theme: str
    accent_color: str
    font_family: str
    font_size_base: int
    rtl: Optional[int] = 1

@app.get("/settings")
def get_settings(conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM university_settings WHERE id = 1")
        row = cur.fetchone()
        return row or {}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/settings")
def update_settings(payload: SettingsPayload, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE university_settings SET univ_name_ar=%s, univ_name_en=%s, college_name_ar=%s, college_name_en=%s WHERE id=1",
            (payload.univ_name_ar, payload.univ_name_en, payload.college_name_ar, payload.college_name_en)
        )
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/settings/appearance/{user_id}")
def get_user_appearance(user_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetUserPreferences", (user_id,))
        row = None
        for result in cur.stored_results():
            row = result.fetchone()
            break
        if not row or not row.get("theme"):
            cur.callproc("UpdateUserPreferences", (user_id, "Dark", "blue", "Segoe UI", 13, 1))
            conn.commit()
            return {
                "EMP_ID": user_id,
                "id": user_id,
                "theme": "Dark",
                "accent_color": "blue",
                "font_family": "Segoe UI",
                "font_size_base": 13,
                "is_arabic_rtl": 1
            }
        return row
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/settings/appearance/{user_id}")
def update_user_appearance(user_id: int, payload: AppearancePayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UpdateUserPreferences", (user_id, payload.theme, payload.accent_color, payload.font_family, payload.font_size_base, payload.rtl))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/settings/clear-logs")
def clear_audit_logs(conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("ClearAuditLogs")
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

# --- CERTIFICATES ENDPOINTS ---
@app.get("/certificates/{student_id}")
def get_certificate_data(student_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetFullCertificateData", (student_id,))
        datasets = []
        for result in cur.stored_results():
            datasets.append(result.fetchall())
        return datasets
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

# --- LOOKUPS ENDPOINTS ---
@app.get("/lookups/countries")
def get_countries(conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetAllCountries")
        rows = []
        for result in cur.stored_results():
            rows.extend(result.fetchall())
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/lookups/governorates")
def get_governorates(conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetAllGovernorates")
        rows = []
        for result in cur.stored_results():
            rows.extend(result.fetchall())
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

# --- THESIS & SUPERVISOR ENDPOINTS ---
class ThesisPayload(BaseModel):
    student_id: int
    title_ar: str
    title_en: str
    defense_date: Optional[str] = None
    committee_decision: Optional[str] = None
    final_grade: Optional[float] = None

class SupervisorPayload(BaseModel):
    student_id: int
    personnel_id: int
    supervision_role: str

@app.get("/thesis/by-student/{student_id}")
def get_thesis_by_student(student_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetThesisByStudent", (student_id,))
        rows = []
        for result in cur.stored_results():
            rows.extend(result.fetchall())
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/thesis")
def insert_thesis(payload: ThesisPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("InsertThesis", (payload.student_id, payload.title_ar, payload.title_en, payload.defense_date, payload.committee_decision, payload.final_grade))
        conn.commit()
        real_id = None
        for result in cur.stored_results():
            row = result.fetchone()
            if row and "new_id" in row:
                real_id = row["new_id"]
                break
        if real_id is None:
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            real_id = cur.fetchone()["new_id"]
        return {"new_id": real_id}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/thesis/{thesis_id}")
def update_thesis(thesis_id: int, payload: ThesisPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UpdateThesis", (thesis_id, payload.title_ar, payload.title_en, payload.defense_date, payload.committee_decision, payload.final_grade))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.delete("/thesis/{thesis_id}")
def delete_thesis(thesis_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteThesis", (thesis_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/supervisors/by-student/{student_id}")
def get_supervisors_by_student(student_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetSupervisorsByStudent", (student_id,))
        rows = []
        for result in cur.stored_results():
            rows.extend(result.fetchall())
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/supervisors")
def insert_supervisor(payload: SupervisorPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("InsertStudentSupervisor", (payload.student_id, payload.personnel_id, payload.supervision_role))
        conn.commit()
        real_id = None
        for result in cur.stored_results():
            row = result.fetchone()
            if row and "new_id" in row:
                real_id = row["new_id"]
                break
        if real_id is None:
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            real_id = cur.fetchone()["new_id"]
        return {"new_id": real_id}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/supervisors/{record_id}")
def update_supervisor(record_id: int, payload: SupervisorPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UpdateStudentSupervisor", (record_id, payload.personnel_id, payload.supervision_role))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.delete("/supervisors/{record_id}")
def delete_supervisor(record_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteStudentSupervisor", (record_id,))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

# 1. Pydantic Model
class DashboardCountsResponse(BaseModel):
    total_students: int
    total_departments: int
    total_courses: int
    total_personnel: int

# 2. FastAPI Route
@app.get("/api/dashboard/counts", response_model=DashboardCountsResponse)
def get_dashboard_counts(conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("Get_dashboard_counts")
        result = None
        for r in cur.stored_results():
            result = r.fetchone()
            break
        
        if not result:
            return DashboardCountsResponse(
                total_students=0,
                total_departments=0,
                total_courses=0,
                total_personnel=0
            )
            
        return DashboardCountsResponse(
            total_students=result["total_students"],
            total_departments=result["total_departments"],
            total_courses=result["total_courses"],
            total_personnel=result["total_personnel"]
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=2030)



