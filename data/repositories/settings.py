# =============================================================================
# data/repositories/settings.py — Module 1: Global Settings & System Configurations
# =============================================================================

from .base import *
from .base import _local_ready


class SettingsRepository(BaseRepository):
    def get_settings(self) -> dict:
        if not is_online():
            return get_offline_settings()
        try:
            resp = api_client.get(f"{self.api_url}/settings", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return get_offline_settings()
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return get_offline_settings()

    def update_settings(self, univ_ar: str, univ_en: str, college_ar: str, college_en: str, univ_logo: str | None = None, college_logo: str | None = None) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            payload = {
                "univ_name_ar": univ_ar,
                "univ_name_en": univ_en,
                "college_name_ar": college_ar,
                "college_name_en": college_en,
                "univ_logo_path": univ_logo,
                "college_logo_path": college_logo
            }
            resp = api_client.put(f"{self.api_url}/settings", json=payload, timeout=5.0)
            if resp.status_code == 200:
                try:
                    from sync_engine import _get_local_conn
                    with _get_local_conn() as l_conn:
                        l_conn.execute("""
                            UPDATE university_settings
                            SET univ_name_ar = ?, univ_name_en = ?, college_name_ar = ?, college_name_en = ?,
                                univ_logo_path = ?, college_logo_path = ?
                            WHERE id = 1
                        """, (univ_ar, univ_en, college_ar, college_en, univ_logo, college_logo))
                        l_conn.commit()
                except Exception:
                    pass
                log_activity("تم تحديث إعدادات المؤسسة والنظام")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def get_user_appearance(self, emp_id: int) -> dict:
        """
        Fetch appearance preferences tied directly to personnel user via EMP_ID.
        Uses online API routing with automatic fallback to local SQLite cache.
        """
        if not is_online():
            return get_offline_user_appearance(emp_id)

        try:
            resp = api_client.get(f"{self.api_url}/settings/appearance/{emp_id}", timeout=5.0)
            if resp.status_code == 200 and resp.json():
                data = resp.json()
                return {
                    "EMP_ID": int(data.get("EMP_ID") or emp_id),
                    "theme": str(data.get("theme") or "Dark"),
                    "accent_color": str(data.get("accent_color") or "blue"),
                    "font_family": str(data.get("font_family") or "Segoe UI"),
                    "font_size_base": int(data.get("font_size_base") or 13),
                    "is_arabic_rtl": int(data.get("is_arabic_rtl") if data.get("is_arabic_rtl") is not None else 1)
                }
            log_system(f"[WARNING][SettingsRepository.get_user_appearance] API status {resp.status_code}, falling back to SQLite...", "WARNING")
            return get_offline_user_appearance(emp_id)
        except Exception as e:
            log_system(f"[ERROR][SettingsRepository.get_user_appearance] API/DB connection failure for user {emp_id}: {e}", "ERROR")
            return get_offline_user_appearance(emp_id)

    def update_user_appearance(self, emp_id: int, theme: str, accent: str, font: str, size: int, rtl: int = 1) -> None:
        """
        Update appearance preferences tied directly to personnel user via EMP_ID.
        """
        if not is_online():
            update_offline_user_appearance(emp_id, theme, accent, font, size, rtl)
            log_activity(f"تم تحديث المظهر للمستخدم ID: {emp_id}")
            return

        try:
            payload = {
                "emp_id": emp_id,
                "theme": theme,
                "accent_color": accent,
                "font_family": font,
                "font_size_base": size,
                "rtl": rtl
            }
            resp = api_client.put(f"{self.api_url}/settings/appearance/{emp_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تحديث المظهر للمستخدم ID: {emp_id}")
            else:
                log_system(f"[WARNING][SettingsRepository.update_user_appearance] API returned status {resp.status_code}: {resp.text}, writing to local cache fallback...", "WARNING")
                update_offline_user_appearance(emp_id, theme, accent, font, size, rtl)
                log_activity(f"تم تحديث المظهر للمستخدم ID: {emp_id}")
        except Exception as e:
            log_system(f"[ERROR][SettingsRepository.update_user_appearance] API/DB connection failure for user {emp_id}: {e}", "ERROR")
            update_offline_user_appearance(emp_id, theme, accent, font, size, rtl)

    def clear_audit_logs(self) -> None:
        if not is_online():
            self._call_write("ClearAuditLogs")
            log_activity("تم مسح سجل التغييرات بالكامل")
            return
        try:
            resp = api_client.post(f"{self.api_url}/settings/clear-logs", timeout=5.0)
            if resp.status_code == 200:
                log_activity("تم مسح سجل التغييرات بالكامل")
            else:
                raise RuntimeError(f"API clear logs failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

# ---------------------------------------------------------
class CountryRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        # Local-first: the local copy matches the API row for row
        if not is_online() or _local_ready("countries"):
            return get_offline_countries()
        try:
            resp = api_client.get(f"{self.api_url}/lookups/countries", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

class GovernorateRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        # Local-first: the local copy matches the API row for row
        if not is_online() or _local_ready("governorates"):
            return get_offline_governorates()
        try:
            resp = api_client.get(f"{self.api_url}/lookups/governorates", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []
