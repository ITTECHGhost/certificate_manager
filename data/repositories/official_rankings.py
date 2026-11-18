# =============================================================================
# data/repositories/official_rankings.py — قوائم الترتيب الرسمية (online only)
# =============================================================================

from .base import *

LIST_TYPE_LABELS = {"jobs": "للتعيين", "masters": "للدراسات العليا"}


class OfficialRankingRepository(BaseRepository):
    BASE = "/api/official-rankings"

    def _get(self, path: str, default):
        if not is_online():
            return default
        try:
            resp = api_client.get(f"{self.api_url}{self.BASE}{path}", timeout=10.0)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code != 404:          # 404: a server older than 2.5.5
                log_system(f"Official rankings {path}: HTTP {resp.status_code}", "WARNING")
        except Exception as e:
            log_system(f"Official rankings request failed: {e}", "WARNING")
        return default

    def list_all(self) -> list:
        return self._get("", [])

    def entries(self, ranking_id: int) -> list:
        return self._get(f"/{int(ranking_id)}/entries", [])

    def for_student(self, student_id) -> list:
        """[{list_type, position, total, order_number, order_date, first_average, ...}] or []."""
        if not student_id or str(student_id).startswith("-"):
            return []
        return self._get(f"/for-student/{int(student_id)}", [])

    def match(self, names: list, department_id=None) -> list:
        if not is_online():
            raise OfflineModeError()
        resp = api_client.post(f"{self.api_url}{self.BASE}/match",
                               json={"names": names, "department_id": department_id}, timeout=30.0)
        if resp.status_code != 200:
            raise RuntimeError(f"تعذرت مطابقة الأسماء ({resp.status_code})")
        return resp.json().get("student_ids") or [None] * len(names)

    def save(self, header: dict, entries: list) -> int:
        """Header and every entry in ONE request (the server saves all or nothing)."""
        if not is_online():
            raise OfflineModeError()
        resp = api_client.post(f"{self.api_url}{self.BASE}", json={**header, "entries": entries}, timeout=60.0)
        if resp.status_code != 200:
            raise RuntimeError(f"لم يُحفظ شيء: {resp.text[:200]}")
        return int(resp.json().get("id"))

    def set_student(self, ranking_id: int, position: int, student_id) -> bool:
        if not is_online():
            raise OfflineModeError()
        params = {"student_id": int(student_id)} if student_id else {}
        resp = api_client.put(f"{self.api_url}{self.BASE}/{int(ranking_id)}/entries/{int(position)}",
                              params=params, timeout=10.0)
        return resp.status_code == 200

    def delete(self, ranking_id: int) -> bool:
        if not is_online():
            raise OfflineModeError()
        resp = api_client.delete(f"{self.api_url}{self.BASE}/{int(ranking_id)}", timeout=10.0)
        return resp.status_code == 200


def pick_official_rank(lists: list, list_type: str) -> dict | None:
    """The newest list of that type the student appears in, or None."""
    for r in lists or []:
        if r.get("list_type") == list_type:
            return r
    return None
