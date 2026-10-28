"""Departments routes: /departments/*."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import get_db, execute_sp_fetchall, execute_sp_fetchone

router = APIRouter()


# ===========================================================================
# 3. Departments Module
# ===========================================================================

class DepartmentPayload(BaseModel):
    name_ar: str
    name_en: str
    university_settings_id: Optional[int] = 1


@router.get("/departments")
def get_departments(conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAllDepartments")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/departments/{dept_id}")
def get_department(dept_id: int, conn=Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "GetDepartmentByID", (dept_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Department not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/departments")
def insert_department(payload: DepartmentPayload, conn=Depends(get_db)):
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


@router.put("/departments/{dept_id}")
def update_department(dept_id: int, payload: DepartmentPayload, conn=Depends(get_db)):
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


@router.delete("/departments/{dept_id}")
def delete_department(dept_id: int, conn=Depends(get_db)):
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
