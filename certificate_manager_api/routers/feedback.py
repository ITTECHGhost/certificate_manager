# =============================================================================
# certificate_manager_api/routers/feedback.py — ملاحظات المستخدمين داخل البرنامج
# One note = text + the screen it was written on + program version + user. One insert,
# one commit. Delete is soft (deleted_at). `created_by` comes from the client until the
# server knows the caller (see docs/PLAN_archive_and_next.md).
# =============================================================================

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import get_db

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

MAX_MESSAGE = 4000


class FeedbackPayload(BaseModel):
    message: str
    screen: Optional[str] = ""
    app_version: Optional[str] = ""
    created_by: Optional[int] = None


@router.post("")
def save_feedback(p: FeedbackPayload, conn=Depends(get_db)):
    message = (p.message or "").strip()[:MAX_MESSAGE]
    if not message:
        raise HTTPException(422, "the note is empty")
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO feedback (message, screen, app_version, created_by) VALUES (%s, %s, %s, %s)",
                    (message, (p.screen or "")[:64], (p.app_version or "")[:32], p.created_by))
        fid = cur.lastrowid
        conn.commit()
        return {"id": fid}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(500, f"Nothing was saved: {exc}")
    finally:
        cur.close()


@router.get("")
def list_feedback(conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT f.id, f.message, f.screen, f.app_version, f.created_by, "
            "DATE_FORMAT(f.created_at, '%Y-%m-%d %H:%i') AS created_at, COALESCE(p.name_ar, '') AS user_name "
            "FROM feedback f LEFT JOIN personnel p ON p.id = f.created_by "
            "WHERE f.deleted_at IS NULL ORDER BY f.id DESC LIMIT 500")
        return cur.fetchall()
    finally:
        cur.close()


@router.delete("/{feedback_id}")
def delete_feedback(feedback_id: int, conn=Depends(get_db), deleted_by: Optional[int] = None):
    cur = conn.cursor()
    try:
        cur.execute("UPDATE feedback SET deleted_at = NOW(), deleted_by = %s WHERE id = %s AND deleted_at IS NULL",
                    (deleted_by, feedback_id))
        n = cur.rowcount
        conn.commit()
        return {"deleted": n}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(500, f"Nothing was changed: {exc}")
    finally:
        cur.close()
