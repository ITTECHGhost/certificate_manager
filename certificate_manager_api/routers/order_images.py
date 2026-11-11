# =============================================================================
# certificate_manager_api/routers/order_images.py — scanned pages of a graduation order
# The client turns photos and PDFs into compressed JPEG pages + thumbnails before upload;
# the server only stores them (table graduation_order_images, migration 0001).
# =============================================================================

import hashlib
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Response
from pydantic import BaseModel

from deps import get_db

router = APIRouter(prefix="/orders", tags=["order-images"])

MAX_PAGE_BYTES = 12 * 1024 * 1024  # mediumblob holds 16 MB


@router.get("/{order_id}/images")
def list_images(order_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT id, page_no, sha256, rotation, source_name, uploaded_by, "
            "DATE_FORMAT(uploaded_at, '%Y-%m-%d %H:%i') AS uploaded_at, LENGTH(image) AS size "
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
        col = "thumb" if thumb else "image"
        cur.execute(f"SELECT {col}, sha256 FROM graduation_order_images WHERE id = %s AND order_id = %s",
                    (image_id, order_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Image not found")
        return Response(content=bytes(row[0]), media_type="image/jpeg",
                        headers={"ETag": row[1], "Cache-Control": "private, max-age=31536000"})
    finally:
        cur.close()


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
            return {"id": dup[0], "duplicate": True}
        cur.execute("SELECT COALESCE(MAX(page_no), 0) + 1 FROM graduation_order_images WHERE order_id = %s",
                    (order_id,))
        page_no = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO graduation_order_images (order_id, page_no, image, thumb, sha256, source_name, uploaded_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (order_id, page_no, data, small, sha, source_name[:255], uploaded_by[:100]),
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
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM graduation_order_images WHERE id = %s AND order_id = %s", (image_id, order_id))
        conn.commit()
        return {"status": "success", "deleted": cur.rowcount}
    finally:
        cur.close()
