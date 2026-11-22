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


_DETAIL_AR = {403: "ليست لديك صلاحية لهذا الإجراء", 404: "الملاحظة غير موجودة",
              409: "لا يمكن التعديل: الملاحظة قيد المعالجة", 422: "البيانات غير صحيحة"}


def _detail(resp, default: str) -> str:
    return _DETAIL_AR.get(resp.status_code, default)
