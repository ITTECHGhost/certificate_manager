# =============================================================================
# services/order_images.py — scanned pages of a graduation order (client side)
# Photos and PDFs become compressed JPEG pages + small thumbnails here, before upload;
# downloaded pages are cached on this computer by checksum, so they open instantly.
# =============================================================================

import io
import os
import logging
from typing import List, Tuple

import api_client
import app_paths
from api_config import get_api_url
from sync_engine import is_online

logger = logging.getLogger("order_images")

PAGE_MAX_SIDE = 2200   # readable A4 scan, roughly 250-450 KB as JPEG
PAGE_QUALITY = 80
THUMB_MAX_SIDE = 260
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp")


def _to_jpeg(img, max_side: int, quality: int) -> bytes:
    from PIL import Image, ImageOps
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, "white")
        bg.paste(rgba, mask=rgba.split()[-1])
        img = bg
    img = img.copy()
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
    return out.getvalue()


def file_to_pages(name: str, data: bytes) -> List[Tuple[bytes, bytes]]:
    """[(page_jpeg, thumb_jpeg), ...] for one uploaded photo or PDF."""
    from PIL import Image
    lower = name.lower()
    images = []
    if lower.endswith(".pdf"):
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(data)
        try:
            for i in range(len(pdf)):
                page = pdf[i]
                w, h = page.get_size()
                scale = min(3.0, PAGE_MAX_SIDE / max(w, h))
                images.append(page.render(scale=scale).to_pil())
        finally:
            pdf.close()
    elif lower.endswith(IMAGE_EXT):
        img = Image.open(io.BytesIO(data))
        for i in range(getattr(img, "n_frames", 1)):  # multi-page TIFF
            img.seek(i)
            images.append(img.copy())
    else:
        raise ValueError("نوع الملف غير مدعوم: صورة أو PDF فقط")
    return [(_to_jpeg(im, PAGE_MAX_SIDE, PAGE_QUALITY), _to_jpeg(im, THUMB_MAX_SIDE, 70)) for im in images]


def _base(order_id: int) -> str:
    return f"{get_api_url()}/orders/{order_id}/images"


def list_images(order_id: int) -> list:
    if not is_online():
        return []
    resp = api_client.get(_base(order_id), timeout=8.0)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}")
    return resp.json()


def upload_file(order_id: int, name: str, data: bytes, username: str = "") -> int:
    """Converts and uploads every page of one file. Returns how many new pages were added."""
    if not is_online():
        raise RuntimeError("رفع صور الأمر يحتاج الاتصال بالخادم")
    added = 0
    for page, thumb in file_to_pages(name, data):
        resp = api_client.post(
            _base(order_id),
            files={"image": ("page.jpg", page, "image/jpeg"), "thumb": ("thumb.jpg", thumb, "image/jpeg")},
            data={"source_name": name, "uploaded_by": username},
            timeout=60.0,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"تعذر رفع الصفحة (HTTP {resp.status_code})")
        body = resp.json()
        if not body.get("duplicate"):
            _cache_put(body.get("sha256", ""), False, page)
            _cache_put(body.get("sha256", ""), True, thumb)
            added += 1
    return added


def _cache_dir() -> str:
    d = str(app_paths.data_path(os.path.join("cache", "order_images")))
    os.makedirs(d, exist_ok=True)
    return d


def _cache_put(sha: str, thumb: bool, data: bytes) -> None:
    if not sha:
        return
    try:
        path = os.path.join(_cache_dir(), f"{sha}{'_t' if thumb else ''}.jpg")
        with open(path + ".tmp", "wb") as f:
            f.write(data)
        os.replace(path + ".tmp", path)
    except OSError as e:
        logger.warning(f"Image cache write failed: {e}")


def get_image(order_id: int, item: dict, thumb: bool = False) -> bytes:
    """One page (or its thumbnail), from this computer's cache when possible."""
    sha = item.get("sha256") or ""
    path = os.path.join(_cache_dir(), f"{sha}{'_t' if thumb else ''}.jpg")
    if sha and os.path.isfile(path):
        with open(path, "rb") as f:
            return f.read()
    resp = api_client.get(f"{_base(order_id)}/{item['id']}", params={"thumb": thumb}, timeout=30.0)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}")
    _cache_put(sha, thumb, resp.content)
    return resp.content


def set_rotation(order_id: int, image_id: int, rotation: int) -> None:
    resp = api_client.put(f"{_base(order_id)}/{image_id}/rotation", json={"rotation": rotation % 360}, timeout=8.0)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}")


def delete_image(order_id: int, image_id: int) -> None:
    resp = api_client.delete(f"{_base(order_id)}/{image_id}", timeout=8.0)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}")


def build_pdf(order_id: int, items: list) -> bytes:
    """All pages, rotated as saved, in one PDF (for download or print)."""
    from PIL import Image
    pages = []
    for it in items:
        img = Image.open(io.BytesIO(get_image(order_id, it))).convert("RGB")
        rot = int(it.get("rotation") or 0) % 360
        if rot:
            img = img.rotate(-rot, expand=True)
        pages.append(img)
    if not pages:
        raise ValueError("لا توجد صفحات")
    out = io.BytesIO()
    pages[0].save(out, "PDF", save_all=True, append_images=pages[1:], resolution=200)
    return out.getvalue()
