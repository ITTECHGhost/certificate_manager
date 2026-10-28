"""Study systems routes: /study-systems/*."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import get_db, execute_sp_fetchall, execute_sp_fetchone

router = APIRouter()


# ===========================================================================
# 4. Study Systems Module
# ===========================================================================

class StudySystemPayload(BaseModel):
    name_ar: str
    name_en: str
    study_day_type: Optional[str] = "Morning"
    calculation_rule: Optional[str] = "annual"
    calculation_weights: Optional[str] = "10:20:30:40"
    period_display: Optional[str] = "year"
    is_active: Optional[int] = 1


@router.get("/study-systems")
def get_study_systems(conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAllStudySystems")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/study-systems/active")
def get_active_study_systems(conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetActiveStudySystems")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/study-systems/{sys_id}")
def get_study_system(sys_id: int, conn=Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "GetStudySystemByID", (sys_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Study system not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/study-systems")
def insert_study_system(payload: StudySystemPayload, conn=Depends(get_db)):
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


@router.put("/study-systems/{sys_id}")
def update_study_system(sys_id: int, payload: StudySystemPayload, conn=Depends(get_db)):
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


@router.post("/study-systems/{sys_id}/toggle")
def toggle_study_system(sys_id: int, is_active: int, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.callproc("ToggleStudySystemStatus", (sys_id, is_active))
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


@router.delete("/study-systems/{sys_id}")
def delete_study_system(sys_id: int, conn=Depends(get_db)):
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
