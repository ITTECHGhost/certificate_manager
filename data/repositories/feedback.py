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

    def list_all(self) -> list:
        if not is_online():
            return []
        try:
            resp = api_client.get(f"{self.api_url}{self.BASE}", timeout=10.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            log_system(f"Feedback list failed: {e}", "WARNING")
        return []

    def delete(self, feedback_id: int, user_id=None) -> bool:
        if not is_online():
            raise OfflineModeError()
        params = {"deleted_by": int(user_id)} if user_id else {}
        resp = api_client.delete(f"{self.api_url}{self.BASE}/{int(feedback_id)}", params=params, timeout=10.0)
        return resp.status_code == 200
