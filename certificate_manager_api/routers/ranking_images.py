"""Scanned pages of an official ranking list (migration 0012) — «الورقة الممسوحة».

Same storage as graduation-order pages: JPEG files on disk (<sha>.jpg + <sha>_t.jpg) in
ranking_images\\<ranking_id>\\; the table keeps the row. Files are written as .part and renamed
only after the row is committed. Delete is a soft delete; the files stay.
Writes: admin or page:rankings only (official_rankings._require_user).
"""
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from deps import get_db
from routers.official_rankings import _require_user

logger = logging.getLogger("api.ranking_images")
router = APIRouter(prefix="/api/official-rankings", tags=["official-rankings"])

MAX_PAGE_BYTES = 12 * 1024 * 1024
API_DIR = Path(__file__).resolve().parents[1]
IMAGES_DIR = Path("C:/AppServ/ranking_images") if os.path.isdir("C:/AppServ") else API_DIR / "ranking_images"
_JPEG = b"\xff\xd8\xff"


def _files(ranking_id: int, sha: str) -> tuple[Path, Path]:
    folder = IMAGES_DIR / str(int(ranking_id))
    return folder / f"{sha}.jpg", folder / f"{sha}_t.jpg"


@router.get("/{ranking_id}/images")
def list_images(ranking_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT id, page_no, sha256, source_name, created_at FROM official_ranking_images "
                    "WHERE ranking_id = %s AND deleted_at IS NULL ORDER BY page_no, id", (ranking_id,))
        return cur.fetchall()
    finally:
        cur.close()


@router.get("/{ranking_id}/images/{image_id}")
def get_image(ranking_id: int, image_id: int, thumb: bool = False, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT sha256 FROM official_ranking_images WHERE id = %s AND ranking_id = %s "
                    "AND deleted_at IS NULL", (image_id, ranking_id))
        row = cur.fetchone()
    finally:
        cur.close()
    if not row:
        raise HTTPException(404, "Image not found")
    full, small = _files(ranking_id, row["sha256"])
    path = small if thumb and small.exists() else full
    if not path.exists():
        raise HTTPException(404, "Image file missing")
    return Response(content=path.read_bytes(), media_type="image/jpeg")


@router.post("/{ranking_id}/images")
async def add_image(ranking_id: int, image: UploadFile = File(...), thumb: UploadFile = File(...),
                    source_name: str = Form(""), personnel_id: Optional[int] = Form(None),
                    conn=Depends(get_db)):
    _require_user(conn, personnel_id)
    data, small = await image.read(), await thumb.read()
    if len(data) > MAX_PAGE_BYTES or len(small) > MAX_PAGE_BYTES:
        raise HTTPException(413, "Page too large")
    if not data.startswith(_JPEG) or not small.startswith(_JPEG):
        raise HTTPException(400, "Only JPEG pages are accepted")
    sha = hashlib.sha256(data).hexdigest()
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT id FROM official_rankings WHERE id = %s", (ranking_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Ranking list not found")
        cur.execute("SELECT id FROM official_ranking_images WHERE ranking_id = %s AND sha256 = %s "
                    "AND deleted_at IS NULL", (ranking_id, sha))
        dup = cur.fetchone()
        if dup:
            return {"id": dup["id"], "duplicate": True, "sha256": sha}
        cur.execute("SELECT COALESCE(MAX(page_no), 0) + 1 AS n FROM official_ranking_images "
                    "WHERE ranking_id = %s AND deleted_at IS NULL", (ranking_id,))
        page_no = int((cur.fetchone() or {}).get("n") or 1)
        full, thumb_path = _files(ranking_id, sha)
        full.parent.mkdir(parents=True, exist_ok=True)
        tmp_full, tmp_thumb = full.with_suffix(".jpg.part"), thumb_path.with_suffix(".jpg.part")
        try:
            tmp_full.write_bytes(data)
            tmp_thumb.write_bytes(small)
            cur.execute("INSERT INTO official_ranking_images (ranking_id, page_no, sha256, file_name, "
                        "source_name, created_by) VALUES (%s, %s, %s, %s, %s, %s)",
                        (ranking_id, page_no, sha, full.name, (source_name or "")[:255] or None,
                         personnel_id))
            new_id = cur.lastrowid
            conn.commit()
        except Exception as exc:
            conn.rollback()
            for p in (tmp_full, tmp_thumb):
                p.unlink(missing_ok=True)
            logger.error("ranking image insert failed: %s", exc)
            raise HTTPException(500, "Could not save the page")
        os.replace(tmp_full, full)
        os.replace(tmp_thumb, thumb_path)
        return {"id": new_id, "duplicate": False, "sha256": sha}
    finally:
        cur.close()


@router.delete("/{ranking_id}/images/{image_id}")
def delete_image(ranking_id: int, image_id: int, personnel_id: Optional[int] = None,
                 conn=Depends(get_db)):
    """Soft delete: the row is hidden, the files stay on disk."""
    _require_user(conn, personnel_id)
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("UPDATE official_ranking_images SET deleted_at = NOW(), deleted_by = %s "
                    "WHERE id = %s AND ranking_id = %s AND deleted_at IS NULL",
                    (personnel_id, image_id, ranking_id))
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("ranking image delete failed: %s", exc)
        raise HTTPException(500, "Could not delete the page")
    finally:
        cur.close()
    if not cur.rowcount:
        raise HTTPException(404, "Image not found")
    return {"ok": True}
