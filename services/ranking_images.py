"""Scanned pages of an official ranking list (client side). Online only.
Pages are converted exactly like graduation-order pages (services.order_images.file_to_pages)."""
import api_client
from api_config import get_api_url
from sync_engine import is_online
from services.order_images import file_to_pages

_DETAIL_AR = {403: "ليست لديك صلاحية لقوائم الترتيب", 404: "القائمة أو الصفحة غير موجودة",
              413: "الصفحة كبيرة جدًا", 400: "نوع الملف غير مقبول"}


def _base(ranking_id: int) -> str:
    return f"{get_api_url()}/api/official-rankings/{int(ranking_id)}/images"


def _need_online():
    if not is_online():
        raise RuntimeError("الورقة الممسوحة تحتاج الاتصال بالخادم")


def list_images(ranking_id: int) -> list:
    if not is_online():
        return []
    resp = api_client.get(_base(ranking_id), timeout=8.0)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}")
    return resp.json()


def get_image(ranking_id: int, image_id: int, thumb: bool = False) -> bytes:
    _need_online()
    resp = api_client.get(f"{_base(ranking_id)}/{int(image_id)}", params={"thumb": thumb}, timeout=30.0)
    if resp.status_code != 200:
        raise RuntimeError(_DETAIL_AR.get(resp.status_code, f"HTTP {resp.status_code}"))
    return resp.content


def upload_file(ranking_id: int, name: str, data: bytes, personnel_id) -> int:
    """Converts and uploads every page of one file (image or PDF). Returns pages added."""
    _need_online()
    added = 0
    for page, thumb in file_to_pages(name, data):
        resp = api_client.post(
            _base(ranking_id),
            files={"image": ("page.jpg", page, "image/jpeg"), "thumb": ("thumb.jpg", thumb, "image/jpeg")},
            data={"source_name": name, "personnel_id": str(personnel_id or "")},
            timeout=60.0)
        if resp.status_code != 200:
            raise RuntimeError(_DETAIL_AR.get(resp.status_code, f"تعذر رفع الصفحة (HTTP {resp.status_code})"))
        if not resp.json().get("duplicate"):
            added += 1
    return added


def delete_image(ranking_id: int, image_id: int, personnel_id) -> None:
    _need_online()
    resp = api_client.delete(f"{_base(ranking_id)}/{int(image_id)}",
                             params={"personnel_id": int(personnel_id)} if personnel_id else {}, timeout=8.0)
    if resp.status_code != 200:
        raise RuntimeError(_DETAIL_AR.get(resp.status_code, "تعذر حذف الصفحة"))
