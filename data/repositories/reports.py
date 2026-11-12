# =============================================================================
# data/repositories/reports.py — «تقارير الطلاب»: counts and lists from the server (online only)
# =============================================================================

from .base import *


class ReportsRepository(BaseRepository):

    def students_report(self, filters: dict, group_by: str = "department", then_by: str = "",
                        list_limit: int = 2000) -> dict | None:
        """{"summary", "groups", "group_keys", "students"} or None when the server cannot be reached."""
        if not is_online():
            return None
        params = {k: v for k, v in (filters or {}).items() if v not in (None, "", 0)}
        params.update({"group_by": group_by or "", "then_by": then_by or "", "list_limit": list_limit})
        try:
            resp = api_client.get(f"{self.api_url}/api/reports/students", params=params, timeout=30.0)
            if resp.status_code == 200:
                return resp.json()
            log_system(f"Students report failed: {resp.status_code} {resp.text[:200]}", "WARNING")
            return None
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return None
