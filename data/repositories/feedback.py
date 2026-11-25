# =============================================================================
# data/repositories/feedback.py — ملاحظات المستخدمين (online only)
# =============================================================================

from .base import *


class FeedbackRepository(BaseRepository):
    BASE = "/api/feedback"

    def send(self, message: str, screen: str, user_id=None) -> int:
        """One note in ONE request. Offline: OfflineModeError (the note is not queued)."""
        if not is_online():
            raise OfflineModeError()
        from app_version import APP_VERSION
        resp = api_client.post(f"{self.api_url}{self.BASE}",
                               json={"message": message, "screen": screen, "app_version": APP_VERSION,
                                     "created_by": user_id}, timeout=15.0)
        if resp.status_code != 200:
            raise RuntimeError("تعذر إرسال الملاحظة")
        return int(resp.json().get("id"))

    def list_all(self, user_id=None) -> list:
        """Admins get every note, other users their own (the server decides)."""
        if not is_online() or not user_id:
            return []
        try:
            resp = api_client.get(f"{self.api_url}{self.BASE}", params={"personnel_id": int(user_id)},
                                  timeout=10.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            log_system(f"Feedback list failed: {e}", "WARNING")
        return []

    def reply(self, feedback_id: int, user_id, reply: str, status: str) -> None:
        """Admin reply + status in ONE request."""
        if not is_online():
            raise OfflineModeError()
        resp = api_client.put(f"{self.api_url}{self.BASE}/{int(feedback_id)}/reply",
                              json={"personnel_id": user_id, "reply": reply, "status": status},
                              timeout=10.0)
        if resp.status_code != 200:
            raise RuntimeError(_detail(resp, "تعذر حفظ الرد"))

    def edit(self, feedback_id: int, user_id, message: str) -> None:
        if not is_online():
            raise OfflineModeError()
        resp = api_client.put(f"{self.api_url}{self.BASE}/{int(feedback_id)}",
                              json={"personnel_id": user_id, "message": message}, timeout=10.0)
        if resp.status_code != 200:
            raise RuntimeError(_detail(resp, "تعذر تعديل الملاحظة"))

    def delete(self, feedback_id: int, user_id=None) -> None:
        if not is_online():
            raise OfflineModeError()
        params = {"personnel_id": int(user_id)} if user_id else {}
        resp = api_client.delete(f"{self.api_url}{self.BASE}/{int(feedback_id)}", params=params, timeout=10.0)
        if resp.status_code != 200:
            raise RuntimeError(_detail(resp, "تعذر حذف الملاحظة"))


    # ── pictures (0014) ──────────────────────────────────────────────────────
    def add_image(self, feedback_id: int, user_id, name: str, data: bytes) -> None:
        """One picture (PNG/JPEG/screenshot) -> JPEG, ONE request."""
        if not is_online():
            raise OfflineModeError()
        from services.order_images import to_feedback_jpeg
        resp = api_client.post(f"{self.api_url}{self.BASE}/{int(feedback_id)}/images",
                               files={"image": ("image.jpg", to_feedback_jpeg(data), "image/jpeg")},
                               data={"source_name": name or "", "personnel_id": str(user_id or "")},
                               timeout=60.0)
        if resp.status_code != 200:
            raise RuntimeError(_detail(resp, "تعذر رفع الصورة"))

    def add_log(self, feedback_id: int, user_id, lines: int = 400) -> None:
        """The last lines of this laptop's logs\\system_log.txt, gzipped, ONE request.
        IT opens it on the «الملاحظات» page (no more photos of the log)."""
        if not is_online():
            raise OfflineModeError()
        import gzip
        import app_paths
        path = app_paths.data_path("logs", "system_log.txt")
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                tail = "".join(f.readlines()[-lines:])
        except OSError:
            tail = "(no system_log.txt on this laptop)"
        resp = api_client.post(f"{self.api_url}{self.BASE}/{int(feedback_id)}/images",
                               files={"image": ("system_log.txt.gz", gzip.compress(tail.encode("utf-8")),
                                                "application/gzip")},
                               data={"source_name": "system_log.txt", "personnel_id": str(user_id or "")},
                               timeout=60.0)
        if resp.status_code != 200:
            raise RuntimeError(_detail(resp, "تعذر رفع السجل"))

    def list_images(self, feedback_id: int, user_id) -> list:
        if not is_online() or not user_id:
            return []
        try:
            resp = api_client.get(f"{self.api_url}{self.BASE}/{int(feedback_id)}/images",
                                  params={"personnel_id": int(user_id)}, timeout=10.0)
            return resp.json() if resp.status_code == 200 else []
        except Exception as e:
            log_system(f"Feedback images list failed: {e}", "WARNING")
            return []

    def get_image(self, feedback_id: int, image_id: int, user_id) -> bytes:
        resp = api_client.get(f"{self.api_url}{self.BASE}/{int(feedback_id)}/images/{int(image_id)}",
                              params={"personnel_id": int(user_id)}, timeout=30.0)
        if resp.status_code != 200:
            raise RuntimeError(_detail(resp, "تعذر تحميل الصورة"))
        return resp.content


_DETAIL_AR = {403: "ليست لديك صلاحية لهذا الإجراء", 404: "الملاحظة غير موجودة",
              409: "لا يمكن: الملاحظة قيد المعالجة أو الصور كثيرة", 413: "الصورة كبيرة جدًا", 422: "البيانات غير صحيحة"}


def _detail(resp, default: str) -> str:
    return _DETAIL_AR.get(resp.status_code, default)
