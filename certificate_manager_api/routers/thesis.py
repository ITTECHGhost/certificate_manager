"""Thesis and supervisor routes: /thesis/* and /supervisors/*."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import get_db, execute_sp_fetchall

router = APIRouter()


# ===========================================================================
# 13. Thesis & Supervisor Module
# ===========================================================================

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


@router.get("/thesis/by-student/{student_id}")
def get_thesis_by_student(student_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetThesisByStudent", (student_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/thesis")
def insert_thesis(payload: ThesisPayload, conn=Depends(get_db)):
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


@router.put("/thesis/{thesis_id}")
def update_thesis(thesis_id: int, payload: ThesisPayload, conn=Depends(get_db)):
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


@router.delete("/thesis/{thesis_id}")
def delete_thesis(thesis_id: int, conn=Depends(get_db)):
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


@router.get("/supervisors/by-student/{student_id}")
def get_supervisors_by_student(student_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetSupervisorsByStudent", (student_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/supervisors")
def insert_supervisor(payload: SupervisorPayload, conn=Depends(get_db)):
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


@router.put("/supervisors/{record_id}")
def update_supervisor(record_id: int, payload: SupervisorPayload, conn=Depends(get_db)):
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


@router.delete("/supervisors/{record_id}")
def delete_supervisor(record_id: int, conn=Depends(get_db)):
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
