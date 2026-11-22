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


STATUSES = ("new", "in_progress", "done")   # 0011


class ReplyPayload(BaseModel):
    personnel_id: Optional[int] = None
    reply: Optional[str] = ""
    status: str = "in_progress"


class EditPayload(BaseModel):
    personnel_id: Optional[int] = None
    message: str


def _person(conn, personnel_id: Optional[int]) -> dict:
    """The calling account (active), or 403. NOTE: the server has no per-user token yet
    (known gap, docs/PLAN_archive_and_next.md), so this trusts the id the client sends."""
    if not personnel_id:
        raise HTTPException(403, "A signed-in user is required")
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT id, personnel_role, is_active FROM personnel WHERE id = %s", (personnel_id,))
        row = cur.fetchone()
    finally:
        cur.close()
    if not row or not row.get("is_active"):
        raise HTTPException(403, "Account not found or disabled")
    return row


def _is_admin(person: dict) -> bool:
    return str(person.get("personnel_role") or "").lower() == "admin"


def _note(conn, feedback_id: int) -> dict:
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT created_by, status FROM feedback WHERE id = %s AND deleted_at IS NULL",
                    (feedback_id,))
        row = cur.fetchone()
    finally:
        cur.close()
    if not row:
        raise HTTPException(404, "Note not found")
    return row


def _write(conn, sql: str, params: tuple) -> int:
    """One statement, one commit; any error rolls back (all or nothing)."""
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        n = cur.rowcount
        conn.commit()
        return n
    except Exception as exc:
        conn.rollback()
        raise HTTPException(500, f"Nothing was changed: {exc}")
    finally:
        cur.close()


@router.get("")
def list_feedback(conn=Depends(get_db), personnel_id: Optional[int] = None):
    """Admins see every note; other users only their own (with the reply)."""
    person = _person(conn, personnel_id)
    where, params = "f.deleted_at IS NULL", ()
    if not _is_admin(person):
        where, params = "f.deleted_at IS NULL AND f.created_by = %s", (person["id"],)
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT f.id, f.message, f.screen, f.app_version, f.created_by, f.status, f.reply, "
            "DATE_FORMAT(f.created_at, '%Y-%m-%d %H:%i') AS created_at, "
            "DATE_FORMAT(f.replied_at, '%Y-%m-%d %H:%i') AS replied_at, "
            "COALESCE(p.name_ar, '') AS user_name, COALESCE(r.name_ar, '') AS replied_by_name "
            "FROM feedback f LEFT JOIN personnel p ON p.id = f.created_by "
            "LEFT JOIN personnel r ON r.id = f.replied_by "
            f"WHERE {where} ORDER BY f.id DESC LIMIT 500", params)
        return cur.fetchall()
    finally:
        cur.close()


@router.put("/{feedback_id}/reply")
def reply_feedback(feedback_id: int, p: ReplyPayload, conn=Depends(get_db)):
    """Admin only: reply text + status, in one statement."""
    if not _is_admin(_person(conn, p.personnel_id)):
        raise HTTPException(403, "Admin account required")
    if p.status not in STATUSES:
        raise HTTPException(422, f"status must be one of {STATUSES}")
    reply = (p.reply or "").strip()[:MAX_MESSAGE]
    n = _write(conn, "UPDATE feedback SET reply = %s, status = %s, replied_by = %s, replied_at = NOW() "
                     "WHERE id = %s AND deleted_at IS NULL",
               (reply, p.status, p.personnel_id, feedback_id))
    return {"updated": n}


@router.put("/{feedback_id}")
def edit_feedback(feedback_id: int, p: EditPayload, conn=Depends(get_db)):
    """The author edits the text while the note is still new."""
    person = _person(conn, p.personnel_id)
    note = _note(conn, feedback_id)
    if note.get("created_by") != person["id"]:
        raise HTTPException(403, "Only the author may edit the note")
    if note.get("status") != "new":
        raise HTTPException(409, "The note is already being handled")
    message = (p.message or "").strip()[:MAX_MESSAGE]
    if not message:
        raise HTTPException(422, "the note is empty")
    n = _write(conn, "UPDATE feedback SET message = %s, edited_at = NOW() "
                     "WHERE id = %s AND deleted_at IS NULL AND status = 'new'",
               (message, feedback_id))
    return {"updated": n}


@router.delete("/{feedback_id}")
def delete_feedback(feedback_id: int, conn=Depends(get_db), personnel_id: Optional[int] = None):
    """Soft delete: an admin, or the author while the note is new."""
    person = _person(conn, personnel_id)
    note = _note(conn, feedback_id)
    if not _is_admin(person):
        if note.get("created_by") != person["id"]:
            raise HTTPException(403, "Only the author or an admin may delete the note")
        if note.get("status") != "new":
            raise HTTPException(409, "The note is already being handled")
    n = _write(conn, "UPDATE feedback SET deleted_at = NOW(), deleted_by = %s "
                     "WHERE id = %s AND deleted_at IS NULL", (person["id"], feedback_id))
    return {"deleted": n}
