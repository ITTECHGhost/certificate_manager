from fastapi import FastAPI, HTTPException, Depends, APIRouter, status, Query
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
router = APIRouter()
app.include_router(router)


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

def decode_db_value(obj: Any) -> Any:
    """Recursively decode bytes or bytearray values to UTF-8 strings."""
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8")
    elif isinstance(obj, dict):
        return {k: decode_db_value(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decode_db_value(v) for v in obj]
    elif isinstance(obj, tuple):
        return tuple(decode_db_value(v) for v in obj)
    return obj


def execute_sp_fetchall(conn, sp_name: str, args: tuple = ()) -> List[Dict[str, Any]]:
    """
    Execute a stored procedure and fetch all rows across all result sets,
    fully consuming cursor result sets (nextset) and decoding any byte payloads.
    """
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc(sp_name, args)
        rows = []
        if hasattr(cur, "stored_results"):
            for result_set in cur.stored_results():
                rows.extend(result_set.fetchall())
        else:
            rows = cur.fetchall()

        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        return decode_db_value(rows)
    finally:
        cur.close()


def execute_sp_fetchone(conn, sp_name: str, args: tuple = ()) -> Optional[Dict[str, Any]]:
    """
    Execute a stored procedure and fetch the first matching row,
    draining all cursor result sets and decoding any byte payloads.
    """
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc(sp_name, args)
        row = None
        if hasattr(cur, "stored_results"):
            for result_set in cur.stored_results():
                r = result_set.fetchone()
                if r:
                    row = r
                    break
        else:
            row = cur.fetchone()

        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        return decode_db_value(row) if row else None
    finally:
        cur.close()


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
    try:
        return execute_sp_fetchall(conn, "GetStudentsPaginated", (limit, offset, name_query, dept_id, year))
    except Exception as exc:
        logger.error(f"Error fetching paginated students: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

class StudentSearchResponse(BaseModel):
    student_id: int
    name_ar: Optional[str] = ""
    name_en: Optional[str] = ""
    department_name_ar: Optional[str] = ""
    graduation_year: Optional[str] = ""
    average: Optional[float] = 0.0

@router.get("/students/search", response_model=List[StudentSearchResponse])
def search_students_paginated(
    query: str = Query("", description="Search term (Arabic or English)"),
    limit: int = Query(25, description="Rows per page (25, 50, 100)"),
    offset: int = Query(0, description="Pagination offset"),
    conn = Depends(get_db)
):
    try:
        raw_rows = execute_sp_fetchall(conn, "SearchStudentsPaginated", (query.strip(), limit, offset))
        results = []
        for row in raw_rows:
            if isinstance(row, dict):
                # Normalize column aliases if present in SP output
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

@app.get("/students/search/basic")
def search_students_basic(query: str, limit: int = 50, conn = Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "SearchStudentsBasic", (query, limit))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/students/{student_id}")
def get_student_by_id(student_id: int, conn = Depends(get_db)):
    """Call GetStudentDossierByID SP on the database."""
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

@app.get("/students/search/all")
def search_students_all(query: str, limit: int = 8, conn = Depends(get_db)):
    """Call SearchStudentsBasic SP on the database."""
    try:
        return execute_sp_fetchall(conn, "SearchStudentsBasic", (query, limit))
    except Exception as exc:
        logger.error(f"Error searching students: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/students/count/all")
def count_students(
    name_query: str = "",
    dept_id: Optional[int] = None,
    year: Optional[str] = None,
    conn = Depends(get_db)
):
    """Call CountStudentsFiltered SP on the database."""
    try:
        row = execute_sp_fetchone(conn, "CountStudentsFiltered", (name_query, dept_id, year))
        return row or {"total_count": 0}
    except Exception as exc:
        logger.error(f"Error counting students: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/students/by-order/{order_id}")
def get_students_by_order(order_id: int, conn = Depends(get_db)):
    """Call GetStudentsByOrder SP on the database."""
    try:
        return execute_sp_fetchall(conn, "GetStudentsByOrder", (order_id,))
    except Exception as exc:
        logger.error(f"Error fetching students by order: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/students/search/unlinked")
def search_students_unlinked(
    name_query: str = "",
    dept_id: Optional[int] = None,
    year: Optional[str] = None,
    limit: int = 50,
    conn = Depends(get_db)
):
    """Fetch unlinked students matching name, dept_id, or graduation year."""
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

        where = "WHERE " + " AND ".join(conditions)
        query = f"""
            SELECT s.id, s.full_name_ar, s.full_name_en, s.admission_year,
                   YEAR(s.graduation_date) AS graduation_year, s.average, s.order_id,
                   d.name_ar AS dept_name_ar
            FROM students s
            LEFT JOIN departments d ON s.department_id = d.id
            {where}
            ORDER BY s.id DESC LIMIT %s
        """
        params.append(limit)
        cur.execute(query, tuple(params))
        return cur.fetchall()
    except Exception as exc:
        logger.error(f"Error searching unlinked students: {exc}")
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

@app.delete("/students/{student_id}")
def delete_student(student_id: int, conn = Depends(get_db)):
    """Call DeleteStudent SP on the database."""
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
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
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
    try:
        return execute_sp_fetchall(conn, "GetAllDepartments")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/departments/{dept_id}")
def get_department(dept_id: int, conn = Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "GetDepartmentByID", (dept_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Department not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/departments")
def insert_department(payload: DepartmentPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("InsertDepartment", (payload.name_ar, payload.name_en, payload.university_settings_id))
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
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/departments/{dept_id}")
def update_department(dept_id: int, payload: DepartmentPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UpdateDepartment", (dept_id, payload.name_ar, payload.name_en, payload.university_settings_id))
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

@app.delete("/departments/{dept_id}")
def delete_department(dept_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteDepartment", (dept_id,))
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

# --- STUDY SYSTEMS ENDPOINTS ---
class StudySystemPayload(BaseModel):
    name_ar: str
    name_en: str
    study_day_type: Optional[str] = "Morning"
    calculation_rule: Optional[str] = "annual"
    calculation_weights: Optional[str] = "10:20:30:40"
    period_display: Optional[str] = "year"
    is_active: Optional[int] = 1

@app.get("/study-systems")
def get_study_systems(conn = Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAllStudySystems")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/study-systems/active")
def get_active_study_systems(conn = Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetActiveStudySystems")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/study-systems/{sys_id}")
def get_study_system(sys_id: int, conn = Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "GetStudySystemByID", (sys_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Study system not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/study-systems")
def insert_study_system(payload: StudySystemPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("InsertStudySystem", (
            payload.name_ar,
            payload.name_en,
            payload.study_day_type or "Morning",
            payload.calculation_rule or "annual",
            payload.calculation_weights,
            payload.period_display or "year",
            payload.is_active if payload.is_active is not None else 1
        ))
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
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/study-systems/{sys_id}")
def update_study_system(sys_id: int, payload: StudySystemPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UpdateStudySystem", (
            sys_id,
            payload.name_ar,
            payload.name_en,
            payload.study_day_type or "Morning",
            payload.calculation_rule or "annual",
            payload.calculation_weights,
            payload.period_display or "year",
            payload.is_active if payload.is_active is not None else 1
        ))
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
            "ORDER BY stage_number ASC, name_ar ASC"
        )
        cur.execute(query, (dept_id,))
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
    display_order: Optional[int] = 0          # 0 = not a signatory; 1-10 = signatory order
    username: str
    password_hash: Optional[str] = None       # plain-text/hash; used in InsertPersonnel or password update
    personnel_role: Optional[str] = "user"
    university_settings_id: Optional[int] = 1
    is_active: Optional[int] = 1

class PersonnelResponse(BaseModel):
    id: int
    name_ar: str
    name_en: str
    academic_title_ar: Optional[str] = None
    academic_title_en: Optional[str] = None
    responsibility_ar: Optional[str] = None
    responsibility_en: Optional[str] = None
    display_order: int = 0
    is_signature: bool = False
    page_location: int = 0
    username: str
    personnel_role: Optional[str] = "user"
    university_settings_id: Optional[int] = None
    is_active: int = 1
    created_at: Optional[Any] = None

class LoginPayload(BaseModel):
    username: str
    password_hash: str

@app.get("/personnel", response_model=List[PersonnelResponse])
def get_personnel(conn = Depends(get_db)):
    try:
        rows = execute_sp_fetchall(conn, "GetAllPersonnel")
        for r in rows:
            r["is_signature"] = bool(r.get("is_signature"))
            r["page_location"] = int(r.get("page_location") or 0)
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/personnel/active")
def get_active_personnel(conn = Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetActivePersonnel")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/personnel/{person_id}", response_model=PersonnelResponse)
def get_personnel_by_id(person_id: int, conn = Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "GetPersonnelById", (person_id,))
        if not row:
            raise HTTPException(status_code=404, detail=f"Personnel with id {person_id} not found")
        row["is_signature"] = bool(row.get("is_signature"))
        row["page_location"] = int(row.get("page_location") or 0)
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/personnel/login")
def authenticate_personnel(payload: LoginPayload, conn = Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "AuthenticateUser", (payload.username, payload.password_hash))
        if not row:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/personnel")
def insert_personnel(payload: PersonnelPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("InsertPersonnel", (
            payload.name_ar,
            payload.name_en,
            payload.academic_title_ar,
            payload.academic_title_en,
            payload.responsibility_ar or "",
            payload.responsibility_en or "",
            payload.display_order if payload.display_order is not None else 0,
            payload.username,
            payload.password_hash or "",
            payload.personnel_role or "user",
            payload.university_settings_id,
            payload.is_active if payload.is_active is not None else 1
        ))

        inserted_id = None
        if hasattr(cur, "stored_results"):
            for result_set in cur.stored_results():
                row = result_set.fetchone()
                if row:
                    if isinstance(row, dict):
                        inserted_id = row.get("inserted_id")
                    elif isinstance(row, (tuple, list)):
                        inserted_id = row[0]
                    break

        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        conn.commit()
        return {"new_id": inserted_id, "inserted_id": inserted_id, "status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/personnel/{person_id}")
def update_personnel(person_id: int, payload: PersonnelPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UpdatePersonnel", (
            person_id,
            payload.name_ar,
            payload.name_en,
            payload.academic_title_ar,
            payload.academic_title_en,
            payload.responsibility_ar or "",
            payload.responsibility_en or "",
            payload.display_order if payload.display_order is not None else 0,
            payload.username,
            payload.personnel_role or "user",
            payload.university_settings_id,
            payload.is_active if payload.is_active is not None else 1
        ))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        # If a new password was provided, update it separately
        if payload.password_hash:
            cur.execute("UPDATE personnel SET password_hash = %s WHERE id = %s", (payload.password_hash, person_id))

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
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeletePersonnel", (person_id,))
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

# --- ACADEMIC PERIODS ENDPOINTS ---
class AcademicPeriodPayload(BaseModel):
    student_id: int
    academic_year: str
    study_system_id: int
    stage_number: int
    semester_num: Optional[int] = 1
    result_status: Optional[str] = "PASSED"

class AcademicPeriodStatusPayload(BaseModel):
    result_status: str

@app.get("/academic-periods/by-student/{student_id}")
def get_academic_periods_by_student(student_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT id, student_id, academic_year, study_system_id, stage_number, semester_num, "
            "COALESCE(result_status, 'PASSED') AS result_status "
            "FROM academic_periods WHERE student_id=%s ORDER BY stage_number, semester_num",
            (student_id,)
        )
        return cur.fetchall() or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.post("/academic-periods")
def insert_academic_period(payload: AcademicPeriodPayload, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        query = (
            "INSERT INTO academic_periods (student_id, academic_year, study_system_id, stage_number, semester_num, result_status) "
            "VALUES (%s, %s, %s, %s, %s, %s)"
        )
        status_val = payload.result_status or "PASSED"
        cur.execute(query, (payload.student_id, payload.academic_year, payload.study_system_id, payload.stage_number, payload.semester_num, status_val))
        conn.commit()
        return {"new_id": cur.lastrowid}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.patch("/academic-periods/{period_id}/status")
@app.patch("/api/periods/{period_id}/status")
def update_academic_period_status(period_id: int, payload: AcademicPeriodStatusPayload, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.execute("UPDATE academic_periods SET result_status=%s WHERE id=%s", (payload.result_status, period_id))
        conn.commit()
        return {"status": "success", "result_status": payload.result_status}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.get("/api/students/{student_id}/periods")
def get_student_periods_api(student_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT id, student_id, academic_year, study_system_id, stage_number, semester_num, "
            "COALESCE(result_status, 'PASSED') AS result_status "
            "FROM academic_periods WHERE student_id=%s ORDER BY stage_number, semester_num",
            (student_id,)
        )
        periods = cur.fetchall() or []
        for p in periods:
            cur.execute(
                "SELECT e.id, e.period_id, e.course_id, e.score, e.passed_round, "
                "c.name_ar AS course_name_ar, c.name_en AS course_name_en, c.credit_hours "
                "FROM enrollments e JOIN courses c ON e.course_id=c.id "
                "WHERE e.period_id=%s ORDER BY c.name_ar",
                (p["id"],)
            )
            p["enrollments"] = cur.fetchall() or []
        return periods
    except Exception as exc:
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
    try:
        return execute_sp_fetchall(conn, "GetEnrollmentsByPeriod", (period_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

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
    try:
        return execute_sp_fetchall(conn, "GetAllGraduationOrders", (limit, offset))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/graduation-orders/{order_id}")
@app.get("/orders/{order_id}")
def get_graduation_order(order_id: int, conn = Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "GetGraduationOrderByID", (order_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Order not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

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

@app.delete("/graduation-orders/{order_id}")
@app.delete("/orders/{order_id}")
def delete_graduation_order(order_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteGraduationOrder", (order_id,))
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

@app.put("/students/{student_id}/link-order/{order_id}")
def link_student_order(student_id: int, order_id: int, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.execute("UPDATE students SET order_id = %s WHERE id = %s", (order_id, student_id))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/students/{student_id}/unlink-order")
def unlink_student_order(student_id: int, conn = Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.execute("UPDATE students SET order_id = NULL WHERE id = %s", (student_id,))
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
    try:
        row = execute_sp_fetchone(conn, "Get_User_Settings", (user_id,))
        if not row:
            return {
                "EMP_ID": user_id,
                "theme": "Dark",
                "accent_color": "blue",
                "font_family": "Segoe UI",
                "font_size_base": 13,
                "is_arabic_rtl": 1
            }

        return {
            "EMP_ID": row.get("EMP_ID", user_id),
            "theme": row.get("theme") or "Dark",
            "accent_color": row.get("accent_color") or "blue",
            "font_family": row.get("font_family") or "Segoe UI",
            "font_size_base": int(row.get("font_size_base") or 13),
            "is_arabic_rtl": int(row.get("is_arabic_rtl") if row.get("is_arabic_rtl") is not None else 1)
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.put("/settings/appearance/{user_id}")
def update_user_appearance(user_id: int, payload: AppearancePayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UpdateUserPreferences", (user_id, payload.theme, payload.accent_color, payload.font_family, payload.font_size_base, payload.rtl))
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

@app.post("/settings/clear-logs")
def clear_audit_logs(conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("ClearAuditLogs")
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

# --- CERTIFICATES ENDPOINTS ---
@app.get("/certificates/{student_id}")
def get_certificate_data(student_id: int, grouping_mode: str = "DEFAULT", conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("sp_GetFullCertificateData", (student_id, grouping_mode))
        datasets = []
        if hasattr(cur, "stored_results"):
            for result in cur.stored_results():
                datasets.append(result.fetchall())
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        
        # sp_GetFullCertificateData order:
        # 0: UniversitySettings
        # 1: StudentInfo
        # 2: Ranking
        # 3: Signers
        # 4: AcademicTimeline
        # 5: AcademicCourses
        
        response_data = {
            "settings": datasets[0] if len(datasets) > 0 else [],
            "student_info": datasets[1] if len(datasets) > 1 else [],
            "ranking": datasets[2] if len(datasets) > 2 else [],
            "signers": datasets[3] if len(datasets) > 3 else [],
            "academic_timeline": datasets[4] if len(datasets) > 4 else [],
            "courses_grouped": datasets[5] if len(datasets) > 5 else [],
        }
        return decode_db_value(response_data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

# --- LOOKUPS ENDPOINTS ---
@app.get("/lookups/countries")
def get_countries(conn = Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAllCountries")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/lookups/governorates")
def get_governorates(conn = Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAllGovernorates")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

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
    try:
        return execute_sp_fetchall(conn, "GetThesisByStudent", (student_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/thesis")
def insert_thesis(payload: ThesisPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("InsertThesis", (payload.student_id, payload.title_ar, payload.title_en, payload.defense_date, payload.committee_decision, payload.final_grade))
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
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/thesis/{thesis_id}")
def update_thesis(thesis_id: int, payload: ThesisPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UpdateThesis", (thesis_id, payload.title_ar, payload.title_en, payload.defense_date, payload.committee_decision, payload.final_grade))
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

@app.delete("/thesis/{thesis_id}")
def delete_thesis(thesis_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteThesis", (thesis_id,))
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

@app.get("/supervisors/by-student/{student_id}")
def get_supervisors_by_student(student_id: int, conn = Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetSupervisorsByStudent", (student_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/supervisors")
def insert_supervisor(payload: SupervisorPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("InsertStudentSupervisor", (payload.student_id, payload.personnel_id, payload.supervision_role))
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
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

@app.put("/supervisors/{record_id}")
def update_supervisor(record_id: int, payload: SupervisorPayload, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UpdateStudentSupervisor", (record_id, payload.personnel_id, payload.supervision_role))
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

@app.delete("/supervisors/{record_id}")
def delete_supervisor(record_id: int, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteStudentSupervisor", (record_id,))
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
        result = None
        try:
            cur.callproc("Get_dashboard_counts")
            if hasattr(cur, "stored_results"):
                for r in cur.stored_results():
                    result = r.fetchone()
                    break
            try:
                while cur.nextset():
                    pass
            except Exception:
                pass
        except Exception as sp_exc:
            logger.warning(f"Get_dashboard_counts SP call failed ({sp_exc}). Falling back to direct SQL.")
            result = None

        if not result:
            cur.execute(
                "SELECT "
                "(SELECT COUNT(id) FROM students) AS total_students, "
                "(SELECT COUNT(id) FROM departments) AS total_departments, "
                "(SELECT COUNT(id) FROM courses) AS total_courses, "
                "(SELECT COUNT(id) FROM personnel) AS total_personnel"
            )
            result = cur.fetchone()

        if not result:
            return DashboardCountsResponse(
                total_students=0,
                total_departments=0,
                total_courses=0,
                total_personnel=0
            )

        return DashboardCountsResponse(
            total_students=result.get("total_students", 0),
            total_departments=result.get("total_departments", 0),
            total_courses=result.get("total_courses", 0),
            total_personnel=result.get("total_personnel", 0)
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

# --- Authentication & User Preferences Endpoints ---

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/login")
def api_login(req: LoginRequest, conn = Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "AuthenticateUser", (req.username, req.password))
        if not row:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        return {"success": True, "user": row}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/api/logout")
def logout():
    return {"success": True, "message": "Logged out successfully"}

class AppearanceUpdate(BaseModel):
    theme: str
    accent_color: str
    font_family: str
    font_size_base: int
    is_arabic_rtl: int

@app.get("/api/user/appearance/{emp_id}")
def api_get_user_appearance(emp_id: int, conn = Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "Get_User_Settings", (emp_id,))
        if not row:
            return {
                "EMP_ID": emp_id,
                "theme": "System",
                "accent_color": "blue",
                "font_family": "Arial",
                "font_size_base": 13,
                "is_arabic_rtl": 1
            }
        return row
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/api/user/appearance")
def api_update_user_appearance(payload: dict, conn = Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        emp_id = payload.get("emp_id") or payload.get("EMP_ID")
        theme = payload.get("theme", "System")
        accent = payload.get("accent_color", "blue")
        font = payload.get("font_family", "Arial")
        size = payload.get("font_size_base", 13)
        rtl = payload.get("is_arabic_rtl", 1)
        cur.callproc("Update_User_Settings", (emp_id, theme, accent, font, size, rtl))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"success": True}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=2030)



