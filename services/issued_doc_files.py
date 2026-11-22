"""Archive files of «سجل الوثائق الصادرة» (client side). Online only."""
import api_client
from api_config import get_api_url
from sync_engine import is_online

_DETAIL_AR = {403: "ليست لديك صلاحية لأرشيف الوثائق", 404: "الوثيقة أو الملف غير موجود",
              413: "الملف كبير جدًا (الحد 20 MB)", 400: "نوع الملف غير مقبول: PDF أو JPG أو PNG فقط",
              422: "البيانات غير صحيحة",
              409: "لا تُؤرشف الوثيقة قبل أن يكون لها رقم صادر وتاريخ"}
KIND_AR = {"signed": "نسخة موقعة مختومة"}


def _base() -> str:
    return f"{get_api_url()}/api/issued-doc-files"


def _need_online():
    if not is_online():
        raise RuntimeError("أرشيف الوثائق يحتاج الاتصال بالخادم")


def _check(resp, default: str):
    if resp.status_code != 200:
        raise RuntimeError(_DETAIL_AR.get(resp.status_code, f"{default} (HTTP {resp.status_code})"))


def signed_ids() -> set:
    _need_online()
    resp = api_client.get(f"{_base()}/signed-ids", timeout=10.0)
    _check(resp, "تعذر قراءة الأرشيف")
    return {int(x) for x in resp.json()}


def list_files(cert_id: int) -> list:
    _need_online()
    resp = api_client.get(f"{_base()}/{int(cert_id)}", timeout=10.0)
    _check(resp, "تعذر قراءة الأرشيف")
    return resp.json()


def current_and_old(items: list) -> tuple[list, list]:
    """Splits the rows into current files and older versions (replaced by a newer row)."""
    replaced = {it.get("supersedes_id") for it in items if it.get("supersedes_id")}
    return ([it for it in items if it.get("id") not in replaced],
            [it for it in items if it.get("id") in replaced])


def get_file(cert_id: int, file_id: int) -> bytes:
    _need_online()
    resp = api_client.get(f"{_base()}/{int(cert_id)}/{int(file_id)}", timeout=60.0)
    _check(resp, "تعذر فتح الملف")
    return resp.content


def upload(cert_id: int, name: str, data: bytes, personnel_id, kind: str = "signed",
           replace_id=None) -> dict:
    _need_online()
    form = {"kind": kind, "personnel_id": str(personnel_id or "")}
    if replace_id:
        form["replace_id"] = str(int(replace_id))
    resp = api_client.post(f"{_base()}/{int(cert_id)}", files={"file": (name or "file", data)},
                           data=form, timeout=120.0)
    _check(resp, "تعذر رفع الملف")
    return resp.json()


def delete(cert_id: int, file_id: int, personnel_id) -> None:
    _need_online()
    resp = api_client.delete(f"{_base()}/{int(cert_id)}/{int(file_id)}",
                             params={"personnel_id": int(personnel_id)} if personnel_id else {},
                             timeout=10.0)
    _check(resp, "تعذر حذف الملف")
