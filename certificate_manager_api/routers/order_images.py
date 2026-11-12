# =============================================================================
# certificate_manager_api/routers/order_images.py — scanned pages of a graduation order
# The client turns photos and PDFs into compressed JPEG pages + thumbnails before upload.
# Since 2.5.0 the pages are files on the server (IMAGES_DIR\<order_id>\<sha>.jpg and
# <sha>_t.jpg); the table graduation_order_images keeps only their name. Pages stored in the
# database by 2.4.0 are moved out at the API's start (move_blobs_to_files).
# =============================================================================

import hashlib
import logging
import os
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Response
from pydantic import BaseModel

from deps import get_db

logger = logging.getLogger("api.order_images")
router = APIRouter(prefix="/orders", tags=["order-images"])

MAX_PAGE_BYTES = 12 * 1024 * 1024
API_DIR = Path(__file__).resolve().parents[1]
# Outside C:\AppServ\www, so Apache never serves the archive; the server update backs it up
IMAGES_DIR = Path("C:/AppServ/order_images") if os.path.isdir("C:/AppServ") else API_DIR / "order_images"


def _files(order_id: int, sha: str) -> tuple[Path, Path]:
    folder = IMAGES_DIR / str(int(order_id))
    return folder / f"{sha}.jpg", folder / f"{sha}_t.jpg"


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def move_blobs_to_files(conn) -> int:
    """Pages saved inside the database (2.4.0) become files; the blobs are emptied. Safe to repeat."""
    cur = conn.cursor()
    moved = 0
    try:
        cur.execute("SELECT id FROM graduation_order_images WHERE file_name IS NULL AND image IS NOT NULL")
        ids = [r[0] for r in cur.fetchall()]
        for img_id in ids:
            cur.execute("SELECT order_id, sha256, image, thumb FROM graduation_order_images WHERE id = %s", (img_id,))
            order_id, sha, image, thumb = cur.fetchone()
            big, small = _files(order_id, sha)
            _write(big, bytes(image))
            if thumb:
                _write(small, bytes(thumb))
            if big.read_bytes() != bytes(image):   # never empty a blob that was not written
                continue
            cur.execute("UPDATE graduation_order_images SET file_name = %s, image = NULL, thumb = NULL WHERE id = %s",
                        (f"{sha}.jpg", img_id))
            conn.commit()
            moved += 1
    finally:
        cur.close()
    if moved:
        logger.info(f"Moved {moved} order page(s) from the database to {IMAGES_DIR}")
    return moved


@router.get("/{order_id}/images")
def list_images(order_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT id, page_no, sha256, rotation, source_name, uploaded_by, "
            "DATE_FORMAT(uploaded_at, '%Y-%m-%d %H:%i') AS uploaded_at "
            "FROM graduation_order_images WHERE order_id = %s ORDER BY page_no, id",
            (order_id,),
        )
        return cur.fetchall()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.get("/{order_id}/images/{image_id}")
def get_image(order_id: int, image_id: int, thumb: bool = False, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.execute("SELECT sha256, file_name, " + ("thumb" if thumb else "image") +
                    " FROM graduation_order_images WHERE id = %s AND order_id = %s", (image_id, order_id))
        row = cur.fetchone()
    finally:
        cur.close()
    if not row:
        raise HTTPException(status_code=404, detail="Image not found")
    sha, file_name, blob = row
    if file_name:
        big, small = _files(order_id, sha)
        path = small if thumb and small.exists() else big
        if not path.exists():
            raise HTTPException(status_code=404, detail="Image file missing on the server")
        data = path.read_bytes()
    elif blob:
        data = bytes(blob)
    else:
        raise HTTPException(status_code=404, detail="Image not found")
    return Response(content=data, media_type="image/jpeg",
                    headers={"ETag": sha, "Cache-Control": "private, max-age=31536000"})


@router.post("/{order_id}/images")
async def add_image(order_id: int, image: UploadFile = File(...), thumb: UploadFile = File(...),
                    source_name: str = Form(""), uploaded_by: str = Form(""), conn=Depends(get_db)):
    data = await image.read()
    small = await thumb.read()
    if not data or not small:
        raise HTTPException(status_code=400, detail="Empty image")
    if len(data) > MAX_PAGE_BYTES:
        raise HTTPException(status_code=413, detail="Page too large")
    if data[:3] != b"\xff\xd8\xff" or small[:3] != b"\xff\xd8\xff":
        raise HTTPException(status_code=400, detail="JPEG expected")
    sha = hashlib.sha256(data).hexdigest()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM graduation_order_images WHERE order_id = %s AND sha256 = %s", (order_id, sha))
        dup = cur.fetchone()
        if dup:
            return {"id": dup[0], "duplicate": True, "sha256": sha}
        big, small_path = _files(order_id, sha)
        _write(big, data)
        _write(small_path, small)
        cur.execute("SELECT COALESCE(MAX(page_no), 0) + 1 FROM graduation_order_images WHERE order_id = %s",
                    (order_id,))
        page_no = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO graduation_order_images (order_id, page_no, sha256, file_name, source_name, uploaded_by) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (order_id, page_no, sha, f"{sha}.jpg", source_name[:255], uploaded_by[:100]),
        )
        conn.commit()
        return {"id": cur.lastrowid, "page_no": page_no, "sha256": sha, "duplicate": False}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


class RotationPayload(BaseModel):
    rotation: int


@router.put("/{order_id}/images/{image_id}/rotation")
def set_rotation(order_id: int, image_id: int, payload: RotationPayload, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.execute("UPDATE graduation_order_images SET rotation = %s WHERE id = %s AND order_id = %s",
                    (payload.rotation % 360, image_id, order_id))
        conn.commit()
        return {"status": "success"}
    finally:
        cur.close()


class OrderPayload(BaseModel):
    image_ids: List[int]


@router.put("/{order_id}/images-order")
def reorder(order_id: int, payload: OrderPayload, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        for i, img_id in enumerate(payload.image_ids, start=1):
            cur.execute("UPDATE graduation_order_images SET page_no = %s WHERE id = %s AND order_id = %s",
                        (i, img_id, order_id))
        conn.commit()
        return {"status": "success"}
    finally:
        cur.close()


@router.delete("/{order_id}/images/{image_id}")
def delete_image(order_id: int, image_id: int, conn=Depends(get_db)):
    """Removes the page from the order. The files move to IMAGES_DIR\\.deleted\\, never erased."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT sha256 FROM graduation_order_images WHERE id = %s AND order_id = %s", (image_id, order_id))
        row = cur.fetchone()
        cur.execute("DELETE FROM graduation_order_images WHERE id = %s AND order_id = %s", (image_id, order_id))
        conn.commit()
        deleted = cur.rowcount
    finally:
        cur.close()
    if row:
        trash = IMAGES_DIR / ".deleted" / str(int(order_id))
        for path in _files(order_id, row[0]):
            if path.exists():
                trash.mkdir(parents=True, exist_ok=True)
                os.replace(path, trash / path.name)
    return {"status": "success", "deleted": deleted}
