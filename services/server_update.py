# =============================================================================
# services/server_update.py — talk to /api/admin/server-update (Settings card)
# =============================================================================

import os
import logging
from typing import Any, Dict, Optional, Tuple

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


def upload(zip_path: str, username: str, password: str, run_at: str = "now") -> Tuple[bool, str, Optional[dict]]:
    """Sends the update zip. run_at: 'now' or 'YYYY-MM-DDTHH:MM'. Returns (ok, message, pending)."""
    if not is_online():
        return False, "تحديث الخادم يحتاج الاتصال بالخادم", None
    if not os.path.isfile(zip_path):
        return False, "ملف التحديث غير موجود", None
    try:
        with open(zip_path, "rb") as f:
            resp = api_client.post(
                f"{get_api_url()}{BASE}/upload",
                files={"file": (os.path.basename(zip_path), f, "application/zip")},
                data={"username": username, "password": password, "run_at": run_at},
                timeout=900.0,
            )
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
