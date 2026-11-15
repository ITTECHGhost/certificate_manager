# =============================================================================
# services/server_update.py — talk to /api/admin/server-update (Settings card)
# =============================================================================

import os
import uuid
import logging
from typing import Any, Callable, Dict, Optional, Tuple

import api_client
from api_config import get_api_url
from sync_engine import is_online

logger = logging.getLogger("server_update")
BASE = "/api/admin/server-update"


def get_status() -> Optional[Dict[str, Any]]:
    """{'server_version', 'pending', 'last', 'updater_running'} or None when the server can't say."""
    if not is_online():
        return None
    try:
        resp = api_client.get(f"{get_api_url()}{BASE}/status", timeout=5.0)
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"Server update status: HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"Server update status failed: {e}")
    return None


def _detail(resp) -> str:
    try:
        return str(resp.json().get("detail") or resp.text[:200])
    except Exception:
        return resp.text[:200]


class MultipartStream:
    """multipart/form-data body read in 1 MB pieces, reporting progress(sent, total).

    requests' files= builds the whole body in memory (the update zip is ~300 MB) and gives
    no progress. This object has a length, so requests sends a Content-Length header
    (not chunked), and read() is called as the socket takes the data.
    """
    CHUNK = 1024 * 1024

    def __init__(self, fields: Dict[str, str], file_field: str, file_path: str,
                 content_type: str = "application/zip", progress: Optional[Callable[[int, int], None]] = None):
        self.boundary = "----CertManUpload" + uuid.uuid4().hex
        b = self.boundary
        head = b"".join(
            f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode("utf-8")
            for k, v in fields.items())
        head += (f'--{b}\r\nContent-Disposition: form-data; name="{file_field}"; '
                 f'filename="{os.path.basename(file_path)}"\r\nContent-Type: {content_type}\r\n\r\n').encode("utf-8")
        self._head, self._tail = head, f"\r\n--{b}--\r\n".encode("ascii")
        self._file = open(file_path, "rb")
        self._total = len(head) + os.path.getsize(file_path) + len(self._tail)
        self._stage, self._sent, self._progress = 0, 0, progress

    @property
    def content_type(self) -> str:
        return f"multipart/form-data; boundary={self.boundary}"

    def __len__(self) -> int:
        return self._total

    def read(self, size: int = -1) -> bytes:
        size = self.CHUNK if size is None or size < 0 else size
        data = b""
        if self._stage == 0:
            data, self._stage = self._head, 1
        elif self._stage == 1:
            data = self._file.read(size)
            if not data:
                data, self._stage = self._tail, 2
        if data:
            self._sent += len(data)
            if self._progress:
                try:
                    self._progress(self._sent, self._total)
                except Exception:
                    pass
        return data

    def close(self) -> None:
        self._file.close()


def upload(zip_path: str, username: str, password: str, run_at: str = "now",
           progress: Optional[Callable[[int, int], None]] = None) -> Tuple[bool, str, Optional[dict]]:
    """Sends the update zip. run_at: 'now' or 'YYYY-MM-DDTHH:MM'. Returns (ok, message, pending).
    progress(sent_bytes, total_bytes) is called from this (worker) thread as the data goes out."""
    if not is_online():
        return False, "تحديث الخادم يحتاج الاتصال بالخادم", None
    if not os.path.isfile(zip_path):
        return False, "ملف التحديث غير موجود", None
    try:
        body = MultipartStream({"username": username, "password": password, "run_at": run_at},
                               "file", zip_path, progress=progress)
        try:
            resp = api_client.post(
                f"{get_api_url()}{BASE}/upload",
                data=body,
                headers={"Content-Type": body.content_type},
                timeout=900.0,
            )
        finally:
            body.close()
        if resp.status_code == 200:
            return True, "", resp.json().get("pending")
        return False, _detail(resp), None
    except Exception as e:
        return False, f"تعذر رفع التحديث: {e}", None


def cancel(username: str, password: str) -> Tuple[bool, str]:
    if not is_online():
        return False, "يحتاج الاتصال بالخادم"
    try:
        resp = api_client.post(f"{get_api_url()}{BASE}/cancel",
                               data={"username": username, "password": password}, timeout=10.0)
        if resp.status_code == 200:
            return True, ""
        return False, _detail(resp)
    except Exception as e:
        return False, str(e)


def request_mode(mode: str, username: str, password: str) -> Tuple[bool, str]:
    """Asks the server to switch to 'https' or 'http' (applied by the updater task within a minute)."""
    if not is_online():
        return False, "يحتاج الاتصال بالخادم"
    try:
        resp = api_client.post(f"{get_api_url()}{BASE}/mode",
                               data={"mode": mode, "username": username, "password": password}, timeout=10.0)
        if resp.status_code == 200:
            return True, ""
        return False, _detail(resp)
    except Exception as e:
        return False, str(e)


STATE_AR = {"running": "قيد التنفيذ", "done": "تم بنجاح", "failed": "فشل — بقي الإصدار السابق"}


def describe(status: Optional[dict]) -> Dict[str, str]:
    """Arabic lines for the card: version, pending, last result, updater health."""
    if not status:
        return {"version": "غير متاح (الخادم غير متصل)", "pending": "", "last": "", "warning": ""}
    pending = status.get("pending") or {}
    last = status.get("last") or {}
    out = {
        "version": status.get("server_version") or "غير معروف (أقدم من 2.3.0)",
        "pending": (f"بانتظار التنفيذ: الإصدار {pending.get('version')} في {pending.get('run_at', '').replace('T', ' ')}"
                    f" — رفعه {pending.get('uploaded_by', '')}") if pending else "",
        "last": (f"آخر تحديث: {last.get('version')} — {STATE_AR.get(last.get('state'), last.get('state', ''))}"
                 f" ({(last.get('finished_at') or last.get('started_at') or '').replace('T', ' ')})") if last else "",
        "warning": "" if status.get("updater_running") else
                   "مهمة التحديث على الخادم لا تعمل: ثبّت هذا الإصدار مرة واحدة بملف Update.bat (USB).",
    }
    return out
