"""Archive files of «سجل الوثائق الصادرة» (client side). Online only."""
import api_client
from api_config import get_api_url
from sync_engine import is_online

_DETAIL_AR = {403: "ليست لديك صلاحية لهذا الإجراء في الأرشيف", 404: "الوثيقة أو الملف غير موجود",
              413: "الملف كبير جدًا (الحد 20 MB)", 400: "نوع الملف غير مقبول: النسخة الموقعة PDF أو JPG أو PNG",
              422: "البيانات غير صحيحة",
              409: "لا تُؤرشف الوثيقة قبل أن يكون لها رقم صادر وتاريخ"}
KIND_AR = {"signed": "نسخة موقعة مختومة", "draft": "المسودة (Word)"}


def _base() -> str:
    return f"{get_api_url()}/api/issued-doc-files"


def _need_online():
    if not is_online():
        raise RuntimeError("أرشيف الوثائق يحتاج الاتصال بالخادم")


def _check(resp, default: str):
    if resp.status_code == 409 and "archived" in (resp.text or ""):
        raise RuntimeError("الوثيقة مؤرشفة (نهائية). لاستبدال نسختها الموقعة استخدم «استبدال» (للمشرف).")
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


def status() -> dict:
    """{certificate_id: {"printed_at", "archived"}} for the two lists."""
    _need_online()
    resp = api_client.get(f"{_base()}/status", timeout=15.0)
    _check(resp, "تعذر قراءة حالة الوثائق")
    return {int(r["certificate_id"]): r for r in resp.json()}


def save_draft_quietly(cert_id, docx_path: str, personnel_id) -> bool:
    """After a print: the editable Word file goes to the server as the record's draft (the
    print date moves too). Never raises: offline / refused / no file -> logged, False."""
    import logging
    import os
    log = logging.getLogger(__name__)
    if not cert_id or not docx_path or not os.path.exists(docx_path) or not is_online():
        return False
    try:
        with open(docx_path, "rb") as fh:
            data = fh.read()
        upload(int(cert_id), os.path.basename(docx_path), data, personnel_id, kind="draft")
        return True
    except Exception as exc:
        log.warning("Draft not saved to the archive for certificate %s: %s", cert_id, exc)
        return False


def latest_draft(items: list) -> dict | None:
    drafts = [it for it in items if it.get("kind") == "draft"]
    return max(drafts, key=lambda it: it.get("id") or 0) if drafts else None
