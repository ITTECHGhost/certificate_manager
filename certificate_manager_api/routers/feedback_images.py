"""Pictures attached to a feedback note (migration 0014): screenshots or photos of the problem.

JPEG files on disk (feedback_images\\<feedback_id>\\<sha>.jpg); the table keeps the row. The file
is written as .part and renamed only after the row is committed. Delete is soft; files stay.
Rights: the note's author or an admin (feedback._person; the server still trusts the id the
client sends, known gap).
"""
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from deps import get_db
from routers.feedback import _is_admin, _note, _person

logger = logging.getLogger("api.feedback_images")
router = APIRouter(prefix="/api/feedback", tags=["feedback"])

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGES_PER_NOTE = 10
API_DIR = Path(__file__).resolve().parents[1]
IMAGES_DIR = Path("C:/AppServ/feedback_images") if os.path.isdir("C:/AppServ") else API_DIR / "feedback_images"
_JPEG = b"\xff\xd8\xff"


_GZIP = b"\x1f\x8b"   # the user's program log (system_log tail), gzipped by the client
_MEDIA = {"jpg": "image/jpeg", "gz": "application/gzip"}


def _file(feedback_id: int, sha: str, ext: str = "jpg") -> Path:
    return IMAGES_DIR / str(int(feedback_id)) / f"{sha}.{ext}"


def _ext_of(file_name) -> str:
    return "gz" if str(file_name or "").endswith(".gz") else "jpg"


def _allowed(conn, feedback_id: int, personnel_id: Optional[int]) -> dict:
    person = _person(conn, personnel_id)
    note = _note(conn, feedback_id)
    if not _is_admin(person) and note.get("created_by") != person["id"]:
        raise HTTPException(403, "Only the author or an admin")
    return person


@router.get("/{feedback_id}/images")
def list_images(feedback_id: int, personnel_id: Optional[int] = None, conn=Depends(get_db)):
    _allowed(conn, feedback_id, personnel_id)
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT id, source_name FROM feedback_images WHERE feedback_id = %s "
                    "AND deleted_at IS NULL ORDER BY id", (feedback_id,))
        return cur.fetchall()
    finally:
        cur.close()


@router.get("/{feedback_id}/images/{image_id}")
def get_image(feedback_id: int, image_id: int, personnel_id: Optional[int] = None, conn=Depends(get_db)):
    _allowed(conn, feedback_id, personnel_id)
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT sha256, file_name FROM feedback_images WHERE id = %s AND feedback_id = %s "
                    "AND deleted_at IS NULL", (image_id, feedback_id))
        row = cur.fetchone()
    finally:
        cur.close()
    if not row:
        raise HTTPException(404, "Image not found")
    ext = _ext_of(row.get("file_name"))
    path = _file(feedback_id, row["sha256"], ext)
    if not path.exists():
        raise HTTPException(404, "Image file missing")
    return Response(content=path.read_bytes(), media_type=_MEDIA[ext])


@router.post("/{feedback_id}/images")
async def add_image(feedback_id: int, image: UploadFile = File(...), source_name: str = Form(""),
                    personnel_id: Optional[int] = Form(None), conn=Depends(get_db)):
    person = _allowed(conn, feedback_id, personnel_id)
    data = await image.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image too large")
    if data.startswith(_JPEG):
        ext = "jpg"
    elif data.startswith(_GZIP):
        ext = "gz"
    else:
        raise HTTPException(400, "Only JPEG images (or the gzipped program log) are accepted")
    sha = hashlib.sha256(data).hexdigest()
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT id FROM feedback_images WHERE feedback_id = %s AND sha256 = %s "
                    "AND deleted_at IS NULL", (feedback_id, sha))
        dup = cur.fetchone()
        if dup:
            return {"id": dup["id"], "duplicate": True}
        cur.execute("SELECT COUNT(*) AS n FROM feedback_images WHERE feedback_id = %s AND deleted_at IS NULL",
                    (feedback_id,))
        if int((cur.fetchone() or {}).get("n") or 0) >= MAX_IMAGES_PER_NOTE:
            raise HTTPException(409, "Too many images for one note")
        path = _file(feedback_id, sha, ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{ext}.part")
        try:
            tmp.write_bytes(data)
            cur.execute("INSERT INTO feedback_images (feedback_id, sha256, file_name, source_name, created_by) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (feedback_id, sha, path.name, (source_name or "")[:255] or None, person["id"]))
            new_id = cur.lastrowid
            conn.commit()
        except Exception as exc:
            conn.rollback()
            tmp.unlink(missing_ok=True)
            logger.error("feedback image insert failed: %s", exc)
            raise HTTPException(500, "Could not save the image")
        os.replace(tmp, path)
        return {"id": new_id, "duplicate": False}
    finally:
        cur.close()
