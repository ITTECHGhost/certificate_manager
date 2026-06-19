from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import mysql.connector
import os
import logging

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

app = FastAPI(title="Certificate Manager API")

# Database Configuration (supports overrides from environment variables)
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "12345678")
DB_NAME = os.environ.get("DB_NAME", "certificate_manager")

# Table metadata matching sync_engine.py
TABLE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "students": {
        "sp_name": "InsertStudent",
        "sp_args": [
            "full_name_ar", "full_name_en", "gender",
            "sequence_number", "postgraduation_no", "date_of_birth",
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
    """Dependency to retrieve a MySQL database connection."""
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
    )
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

class StudentPayload(BaseModel):
    full_name_ar: str
    full_name_en: str
    gender: Optional[str] = "M"
    sequence_number: Optional[int] = None
    postgraduation_no: Optional[int] = None
    date_of_birth: Optional[str] = None
    birthplace_id: Optional[int] = None
    birthplace_other: Optional[str] = None
    nationality_id: Optional[int] = 1
    department_id: Optional[int] = None
    study_system_id: Optional[int] = None
    degree_level: Optional[str] = "Bachelor"
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
    """Select distinct admission years from the students table."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT DISTINCT admission_year FROM students ORDER BY admission_year DESC")
        rows = cur.fetchall()
        return [str(r["admission_year"]) for r in rows if r["admission_year"] is not None]
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
            payload.sequence_number, payload.postgraduation_no, payload.date_of_birth,
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
            payload.sequence_number, payload.postgraduation_no, payload.date_of_birth,
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

