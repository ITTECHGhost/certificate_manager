# =============================================================================
# data/repositories/_legacy.py — repositories not yet moved to their own module
# =============================================================================

from .base import *
from .base import _local_ready, _refreshes_local_copy


# ---------------------------------------------------------------------------
# Module 1: Global Settings & System Configurations
# ---------------------------------------------------------------------------

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

class DepartmentRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        # Local-first: the local copy matches the API row for row (refreshed after every change)
        if not is_online() or _local_ready("departments"):
            return get_offline_departments()
        try:
            resp = api_client.get(f"{self.api_url}/departments", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []
        
    def get_by_id(self, dept_id: int) -> dict | None:
        if not is_online():
            return get_offline_department_by_id(dept_id)
        try:
            resp = api_client.get(f"{self.api_url}/departments/{dept_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return None

    @_refreshes_local_copy("departments")
    def insert(self, name_ar: str, name_en: str, uni_settings_id: int = 1, **_ignored) -> int:
        if not is_online():
            return self._call_write("InsertDepartment", (name_ar, name_en, uni_settings_id))
        try:
            payload = {
                "name_ar": name_ar,
                "name_en": name_en,
                "university_settings_id": uni_settings_id
            }
            resp = api_client.post(f"{self.api_url}/departments", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة قسم جديد: {name_ar}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    @_refreshes_local_copy("departments")
    def update(self, dept_id: int, name_ar: str, name_en: str, uni_settings_id: int = 1, **_ignored) -> None:
        if not is_online():
            self._call_write("UpdateDepartment", (dept_id, name_ar, name_en, uni_settings_id))
            log_activity(f"تم تعديل القسم: {name_ar}")
            return
        try:
            payload = {
                "name_ar": name_ar,
                "name_en": name_en,
                "university_settings_id": uni_settings_id
            }
            resp = api_client.put(f"{self.api_url}/departments/{dept_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل القسم: {name_ar}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    @_refreshes_local_copy("departments")
    def delete(self, dept_id: int) -> None:
        if not is_online():
            self._call_write("DeleteDepartment", (dept_id,))
            log_activity(f"تم حذف القسم ID: {dept_id}")
            return
        try:
            resp = api_client.delete(f"{self.api_url}/departments/{dept_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف القسم ID: {dept_id}")
            else:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

# ---------------------------------------------------------------------------
# Module 3: Study Systems
# ---------------------------------------------------------------------------

class StudySystemRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        # Local-first: the local copy matches the API row for row (refreshed after every change)
        if not is_online() or _local_ready("study_systems"):
            return get_offline_study_systems()
        try:
            resp = api_client.get(f"{self.api_url}/study-systems", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []
        
    def get_active(self) -> list[dict]:
        if not is_online():
            return get_offline_active_study_systems()
        try:
            resp = api_client.get(f"{self.api_url}/study-systems/active", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []
        
    def get_by_id(self, system_id: int) -> dict | None:
        if not is_online():
            return get_offline_study_system_by_id(system_id)
        try:
            resp = api_client.get(f"{self.api_url}/study-systems/{system_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return None

    @_refreshes_local_copy("study_systems")
    def insert(self, name_ar: str, name_en: str, calc_rule: str, period_display: str = 'year', calculation_weights: str = None, study_day_type: str = 'Morning') -> int:
        if not is_online():
            return self._call_write("InsertStudySystem", (name_ar, name_en, study_day_type, calc_rule, calculation_weights, period_display, 1))
        try:
            payload = {
                "name_ar": name_ar,
                "name_en": name_en,
                "study_day_type": study_day_type,
                "calculation_rule": calc_rule,
                "calculation_weights": calculation_weights,
                "period_display": period_display,
                "is_active": 1
            }
            resp = api_client.post(f"{self.api_url}/study-systems", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة نظام دراسي جديد: {name_ar}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    @_refreshes_local_copy("study_systems")
    def update(self, sys_id: int, name_ar: str, name_en: str, calc_rule: str, period_display: str = 'year', calculation_weights: str = None, study_day_type: str = 'Morning', is_active: int = 1, **_ignored) -> None:
        if not is_online():
            existing = self.get_by_id(sys_id)
            day_type = study_day_type or (existing.get("study_day_type", "Morning") if existing else "Morning")
            active_val = is_active if is_active is not None else (existing.get("is_active", 1) if existing else 1)
            self._call_write("UpdateStudySystem", (sys_id, name_ar, name_en, day_type, calc_rule, calculation_weights, period_display, active_val))
            log_activity(f"تم تعديل النظام الدراسي: {name_ar}")
            return
        try:
            existing = self.get_by_id(sys_id)
            active_val = is_active if is_active is not None else (existing.get("is_active", 1) if existing else 1)
            day_type = study_day_type or (existing.get("study_day_type", "Morning") if existing else "Morning")
            payload = {
                "name_ar": name_ar,
                "name_en": name_en,
                "study_day_type": day_type,
                "calculation_rule": calc_rule,
                "calculation_weights": calculation_weights,
                "period_display": period_display,
                "is_active": active_val
            }
            resp = api_client.put(f"{self.api_url}/study-systems/{sys_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل النظام الدراسي ID: {sys_id}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    @_refreshes_local_copy("study_systems")
    def toggle(self, sys_id: int, new_status: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = api_client.post(f"{self.api_url}/study-systems/{sys_id}/toggle", params={"is_active": new_status}, timeout=5.0)
            if resp.status_code != 200:
                raise RuntimeError(f"API toggle failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    @_refreshes_local_copy("study_systems")
    def delete(self, sys_id: int) -> None:
        if not is_online():
            self._call_write("DeleteStudySystem", (sys_id,))
            log_activity(f"تم حذف النظام الدراسي ID: {sys_id}")
            return
        try:
            resp = api_client.delete(f"{self.api_url}/study-systems/{sys_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف النظام الدراسي ID: {sys_id}")
            else:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

# ---------------------------------------------------------------------------
# Module 4: Personnel Management & Authentication
# ---------------------------------------------------------------------------

class PersonnelRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            return get_offline_personnel()
        try:
            resp = api_client.get(f"{self.api_url}/personnel", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []
        
    def get_active(self) -> list[dict]:
        if not is_online():
            return get_offline_active_personnel()
        try:
            resp = api_client.get(f"{self.api_url}/personnel/active", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def get_by_id(self, person_id: int) -> dict | None:
        if not is_online():
            return get_offline_personnel_by_id(person_id)
        try:
            resp = api_client.get(f"{self.api_url}/personnel/{person_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return None

    def authenticate(self, username: str, password_hash: str) -> dict | None:
        """Authenticate a user. Online: check MySQL via API + trigger background pull.
        Offline: check local SQLite replica and verify password."""
        def _check_offline_auth() -> dict | None:
            # Accounts are synced to every laptop with their password HASHES, so any
            # user can log in on any laptop while the server is offline. No built-in
            # fallback account: an admin logs in with their own synced password.
            user = get_offline_personnel_by_username(username)
            if not user or not user.get("is_active"):
                log_activity(f"Offline authentication failed for '{username}' (unknown or inactive account)", "WARNING")
                return None
            stored = str(user.get("password_hash") or "").strip()
            if is_password_disabled(stored):
                log_activity(f"Offline authentication rejected for '{username}' (account login is disabled)", "WARNING")
                return None
            if verify_password(password_hash, stored):
                log_activity(f"Offline authentication successful for '{username}'", "OK")
                result = dict(user)
                result.pop("password_hash", None)
                result["must_change_password"] = bool(result.get("must_change_password"))
                return result
            log_activity(f"Offline authentication failed for '{username}' (invalid password)", "WARNING")
            return None

        if not is_online():
            return _check_offline_auth()
        try:
            payload = {"username": username, "password_hash": password_hash}
            resp = api_client.post(f"{self.api_url}/personnel/login", json=payload, timeout=5.0)
            if resp.status_code == 200:
                result = resp.json()
                pull_mysql_to_sqlite_background()
                return result
            elif resp.status_code == 401:
                return None
            return _check_offline_auth()
        except Exception as e:
            log_system(f"API request failed, falling back to offline authentication: {e}", "WARNING")
            return _check_offline_auth()

    def insert(self, data: dict) -> int:
        if not is_online():
            raise OfflineModeError()
        try:
            payload = {
                "name_ar": data.get("name_ar"),
                "name_en": data.get("name_en"),
                "academic_title_ar": data.get("academic_title_ar"),
                "academic_title_en": data.get("academic_title_en"),
                "responsibility_ar": data.get("responsibility_ar"),
                "responsibility_en": data.get("responsibility_en"),
                # display_order encodes signatory state: 0=none, 1-10=signatory position
                "display_order": int(data.get("display_order") or 0),
                "username": data.get("username"),
                "password_hash": data.get("password_hash") or "",
                "personnel_role": data.get("personnel_role", "user"),
                "university_settings_id": int(data.get("university_settings_id") or 1),
                "is_active": int(data.get("is_active") if data.get("is_active") is not None else 1),
            }
            if data.get("must_change_password") is not None:
                payload["must_change_password"] = bool(data.get("must_change_password"))

            resp = api_client.post(f"{self.api_url}/personnel", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة كادر جديد: {data.get('name_ar')}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise
        
    def update(self, person_id: int, data: dict) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            payload = {
                "name_ar": data.get("name_ar"),
                "name_en": data.get("name_en"),
                "academic_title_ar": data.get("academic_title_ar"),
                "academic_title_en": data.get("academic_title_en"),
                "responsibility_ar": data.get("responsibility_ar"),
                "responsibility_en": data.get("responsibility_en"),
                # display_order encodes signatory state: 0=none, 1-10=signatory position
                "display_order": int(data.get("display_order") or 0),
                "username": data.get("username"),
                "password_hash": data.get("password_hash") or "",
                "personnel_role": data.get("personnel_role", "user"),
                "university_settings_id": int(data.get("university_settings_id") or 1),
                "is_active": int(data.get("is_active") if data.get("is_active") is not None else 1),
            }

            resp = api_client.put(f"{self.api_url}/personnel/{person_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل بيانات الكادر ID: {person_id}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def set_password(self, person_id: int, new_password: str, must_change: bool = False) -> str:
        """
        Set a person's password. Returns "saved" (on the server now) or "queued".

        Online: saved on the server. Offline (or server unreachable): hashed and saved on
        this laptop, so the new password works for offline logins immediately, and queued;
        at the next sync the server applies it unless the password was changed on the
        server meanwhile (then the server's password wins).
        must_change=True makes the user choose a new password at the next login.
        """
        from sync_engine import queue_password_change, set_local_personnel_password
        if is_online():
            try:
                resp = api_client.put(
                    f"{self.api_url}/personnel/{person_id}/password",
                    json={"password": new_password, "must_change": bool(must_change)},
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    stored = resp.json().get("password_hash")
                    if stored:
                        set_local_personnel_password(person_id, stored, must_change)
                    log_activity(f"تم تغيير كلمة مرور الكادر ID: {person_id}")
                    return "saved"
                raise RuntimeError(f"API password change failed: {resp.text}")
            except requests.exceptions.RequestException as e:
                log_system(f"Server unreachable for password change, saving offline: {e}", "WARNING")
        row = sqlite_read_one("SELECT password_hash FROM personnel WHERE id = ?", (person_id,)) or {}
        new_hash = hash_password(new_password)
        queue_password_change(person_id, new_hash, row.get("password_hash") or "", must_change)
        set_local_personnel_password(person_id, new_hash, must_change)
        log_activity(f"تم تغيير كلمة مرور الكادر ID: {person_id} على هذا الجهاز (بانتظار المزامنة)")
        return "queued"

    def toggle_active(self, person_id: int, is_active: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = api_client.post(f"{self.api_url}/personnel/{person_id}/toggle", params={"is_active": is_active}, timeout=5.0)
            if resp.status_code != 200:
                raise RuntimeError(f"API toggle failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise
        
    def delete(self, person_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = api_client.delete(f"{self.api_url}/personnel/{person_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف الكادر ID: {person_id}")
            else:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise


# ---------------------------------------------------------------------------
# Module 4.1: Permissions Management (RBAC)
# ---------------------------------------------------------------------------

ALL_SYSTEM_PERMISSIONS = [
    # ── Students ─────────────────────────────────────────────────────────────
    {
        "permission_key": "students:view",
        "category": "students",
        "name_ar": "عرض الطلاب",
        "name_en": "View Students",
        "description_ar": "استعراض قائمة الطلاب والملفات الشخصية والأكاديمية"
    },
    {
        "permission_key": "students:create",
        "category": "students",
        "name_ar": "إضافة طالب",
        "name_en": "Add Student",
        "description_ar": "تسجيل طلاب جدد فردياً أو عبر الاستيراد الجماعي"
    },
    {
        "permission_key": "students:edit",
        "category": "students",
        "name_ar": "تعديل طالب",
        "name_en": "Edit Student",
        "description_ar": "تعديل البيانات الشخصية والأكاديمية للطلاب"
    },
    {
        "permission_key": "students:delete",
        "category": "students",
        "name_ar": "حذف طالب",
        "name_en": "Delete Student",
        "description_ar": "حذف سجلات الطلاب والتسجيلات المرتبطة"
    },
    {
        "permission_key": "students:grades",
        "category": "students",
        "name_ar": "إدارة ورصد الدرجات",
        "name_en": "Manage Grades",
        "description_ar": "إدخال وتعديل وحفظ الدرجات والمراحل والفصول الدراسية"
    },

    # ── Graduation Orders ───────────────────────────────────────────────────
    {
        "permission_key": "orders:view",
        "category": "orders",
        "name_ar": "عرض أوامر التخرج",
        "name_en": "View Orders",
        "description_ar": "عرض أوامر التخرج الوزارية والجامعية وقوائم الخريجين"
    },
    {
        "permission_key": "orders:create",
        "category": "orders",
        "name_ar": "إضافة أمر تخرج",
        "name_en": "Add Order",
        "description_ar": "إنشاء وتوثيق أوامر تخرج جديدة وربط الطلاب"
    },
    {
        "permission_key": "orders:edit",
        "category": "orders",
        "name_ar": "تعديل أمر تخرج",
        "name_en": "Edit Order",
        "description_ar": "تعديل بيانات ورقم وتاريخ الأمر الجامعي"
    },
    {
        "permission_key": "orders:delete",
        "category": "orders",
        "name_ar": "حذف أمر تخرج",
        "name_en": "Delete Order",
        "description_ar": "حذف أوامر التخرج وفصل ارتباط الطلاب"
    },

    # ── Certificates ────────────────────────────────────────────────────────
    {
        "permission_key": "certificates:issue",
        "category": "certificates",
        "name_ar": "إصدار وثيقة تخرج",
        "name_en": "Issue Certificate",
        "description_ar": "توليد وطباعة وثائق التخرج وتعيين الأرقام الصادرة"
    },

    # ── Issued Records ──────────────────────────────────────────────────────
    {
        "permission_key": "issued_certs:view",
        "category": "issued_certs",
        "name_ar": "عرض سجل الصادر",
        "name_en": "View Issued Records",
        "description_ar": "بحث واستعراض الأرشيف وسجل الوثائق الصادرة"
    },
    {
        "permission_key": "issued_certs:export",
        "category": "issued_certs",
        "name_ar": "تصدير تقارير الوثائق",
        "name_en": "Export Reports",
        "description_ar": "تصدير السجلات والتقارير الإحصائية إلى Excel/CSV"
    },
    {
        "permission_key": "issued_certs:delete",
        "category": "issued_certs",
        "name_ar": "حذف وثيقة من السجل",
        "name_en": "Delete Issued Record",
        "description_ar": "إلغاء وحذف قيد الوثيقة الصادرة من الأرشيف"
    },

    # ── Departments Catalog ─────────────────────────────────────────────────
    {
        "permission_key": "departments:view",
        "category": "departments",
        "name_ar": "عرض الأقسام العلمية",
        "name_en": "View Departments",
        "description_ar": "استعراض قائمة وتفاصيل الأقسام الأكاديمية"
    },
    {
        "permission_key": "departments:create",
        "category": "departments",
        "name_ar": "إضافة قسم علمي",
        "name_en": "Add Department",
        "description_ar": "إنشاء أقسام وتخصصات دراسية جديدة بالكلية"
    },
    {
        "permission_key": "departments:edit",
        "category": "departments",
        "name_ar": "تعديل بيانات القسم",
        "name_en": "Edit Department",
        "description_ar": "تعديل مسميات وبيانات وتوصيف الأقسام"
    },
    {
        "permission_key": "departments:delete",
        "category": "departments",
        "name_ar": "حذف قسم علمي",
        "name_en": "Delete Department",
        "description_ar": "حذف الأقسام العلمية غير المرتبطة ببيانات"
    },

    # ── Courses Catalog ─────────────────────────────────────────────────────
    {
        "permission_key": "courses:view",
        "category": "courses",
        "name_ar": "عرض المقررات والمناهج",
        "name_en": "View Courses",
        "description_ar": "استعراض المواد الدراسية والمفردات والوحدات"
    },
    {
        "permission_key": "courses:create",
        "category": "courses",
        "name_ar": "إضافة مقرر دراسي",
        "name_en": "Add Course",
        "description_ar": "إضافة مواد دراسية جديدة وتحديد الساعات والوحدات"
    },
    {
        "permission_key": "courses:edit",
        "category": "courses",
        "name_ar": "تعديل مقرر دراسي",
        "name_en": "Edit Course",
        "description_ar": "تعديل أسماء ووحدات ومراحل المقررات الدراسية"
    },
    {
        "permission_key": "courses:delete",
        "category": "courses",
        "name_ar": "حذف مقرر دراسي",
        "name_en": "Delete Course",
        "description_ar": "حذف المقررات الدراسية غير المسجلة"
    },

    # ── Personnel ───────────────────────────────────────────────────────────
    {
        "permission_key": "personnel:view",
        "category": "personnel",
        "name_ar": "عرض الكوادر والموقعين",
        "name_en": "View Personnel",
        "description_ar": "استعراض قائمة الموظفين وأعضاء الهيئة التدريسية"
    },
    {
        "permission_key": "personnel:manage",
        "category": "personnel",
        "name_ar": "إدارة الكوادر والمستخدمين",
        "name_en": "Manage Personnel",
        "description_ar": "إضافة وتعديل وحسابات الكوادر وتعيين الأدوار"
    },

    # ── System Settings Views & Alter ───────────────────────────────────────
    {
        "permission_key": "settings:institution",
        "category": "settings",
        "name_ar": "معلومات المؤسسة والشعارات",
        "name_en": "Institution Info & Logos",
        "description_ar": "الوصول وتعديل اسم الجامعة والكلية والشعارات الرسمية"
    },
    {
        "permission_key": "settings:study_systems",
        "category": "settings",
        "name_ar": "الأنظمة الدراسية وقواعد الحساب",
        "name_en": "Study Systems & Calculations",
        "description_ar": "ضبط وتعديل الأنظمة الدراسية وتوزيع الأوزان والمعدلات"
    },
    {
        "permission_key": "settings:appearance",
        "category": "settings",
        "name_ar": "المظهر والسمات العامة",
        "name_en": "Appearance & Themes",
        "description_ar": "تخصيص ثيمات النظام والألوان والخطوط والوضع الليلي"
    },
    {
        "permission_key": "settings:roles",
        "category": "settings",
        "name_ar": "إدارة الأدوار والصلاحيات",
        "name_en": "Roles & Permissions Matrix",
        "description_ar": "إنشاء وتعديل مسؤوليات وأدوار النظام وصلاحيات الوصول"
    },
    {
        "permission_key": "settings:templates",
        "category": "settings",
        "name_ar": "قوالب الوثائق والشهادات",
        "name_en": "Document Templates",
        "description_ar": "إدارة ورفع وتعيين قوالب الوثائق الرسمية في النظام"
    },
    {
        "permission_key": "settings:logs",
        "category": "settings",
        "name_ar": "السيرفر والصيانة والسجلات",
        "name_en": "Server, Maintenance & Logs",
        "description_ar": "النسخ الاحتياطي ومزامنة البيانات واستعراض سجلات النظام"
    },
]

ALL_PERMISSION_KEYS = [p["permission_key"] for p in ALL_SYSTEM_PERMISSIONS]


class PermissionRepository(BaseRepository):
    def _ensure_seeded(self) -> None:
        """Self-healing: Ensures all system permissions are seeded into local SQLite."""
        try:
            from sync_engine import _get_local_conn
            with _get_local_conn() as conn:
                for p in ALL_SYSTEM_PERMISSIONS:
                    conn.execute("""
                        INSERT OR IGNORE INTO permissions (
                            permission_key, category, name_ar, name_en, description_ar
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (
                        p["permission_key"], p["category"], p["name_ar"],
                        p["name_en"], p.get("description_ar", "")
                    ))
                conn.commit()
        except Exception as exc:
            log_system(f"PermissionRepository seed error: {exc}", "DEBUG")

    def get_all(self) -> list[dict]:
        """Fetch all available permissions in the system."""
        self._ensure_seeded()
        results = []
        if is_online():
            try:
                resp = api_client.get(f"{self.api_url}/permissions", timeout=5.0)
                if resp.status_code == 200:
                    results = resp.json()
            except Exception as e:
                log_system(f"API request failed: {e}", "WARNING")

        if not results:
            results = sqlite_read_all("SELECT * FROM permissions ORDER BY category, permission_key")

        # Guarantee all defined granular permissions are present
        seen_keys = {r.get("permission_key") for r in results if isinstance(r, dict)}
        for sp in ALL_SYSTEM_PERMISSIONS:
            if sp["permission_key"] not in seen_keys:
                results.append(sp)
                seen_keys.add(sp["permission_key"])

        return sorted(results, key=lambda x: (x.get("category", ""), x.get("permission_key", "")))

    def get_user_permissions(self, person_id: int) -> list[str]:
        """Fetch list of granted permission_keys for a specific personnel user."""
        if not is_online():
            rows = sqlite_read_all(
                "SELECT permission_key FROM personnel_permissions WHERE personnel_id = ? AND is_granted = 1",
                (person_id,)
            )
            return [r["permission_key"] for r in rows if r["permission_key"] not in ("settings:manage", "settings:view", "catalog:manage")]
        try:
            resp = api_client.get(f"{self.api_url}/personnel/{person_id}/permissions", timeout=5.0)
            local_rows = sqlite_read_all(
                "SELECT permission_key FROM personnel_permissions WHERE personnel_id = ? AND is_granted = 1",
                (person_id,)
            )
            local_keys = {r["permission_key"] for r in local_rows} if local_rows else set()
            if resp.status_code == 200:
                remote_keys = set(resp.json()) if isinstance(resp.json(), list) else set()
                combined = remote_keys | local_keys
                return [k for k in sorted(combined) if k not in ("settings:manage", "settings:view", "catalog:manage")]
            return [k for k in sorted(local_keys) if k not in ("settings:manage", "settings:view", "catalog:manage")]
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            rows = sqlite_read_all(
                "SELECT permission_key FROM personnel_permissions WHERE personnel_id = ? AND is_granted = 1",
                (person_id,)
            )
            return [r["permission_key"] for r in rows if r["permission_key"] not in ("settings:manage", "settings:view", "catalog:manage")]

    def set_user_permissions(self, person_id: int, keys: list[str]) -> None:
        """Atomically set granted permissions for a user (Online via API/SP + immediate SQLite sync, or local SQLite replica when offline)."""
        if not is_online():
            try:
                from sync_engine import _get_local_conn
                with _get_local_conn() as l_conn:
                    l_conn.execute("DELETE FROM personnel_permissions WHERE personnel_id = ?", (person_id,))
                    for k in keys:
                        l_conn.execute(
                            "INSERT OR REPLACE INTO personnel_permissions (personnel_id, permission_key, is_granted) VALUES (?, ?, 1)",
                            (person_id, k)
                        )
                    l_conn.commit()
                log_activity(f"تم تحديث صلاحيات الكادر محلياً (Offline) ID: {person_id}")
                return
            except Exception as e:
                log_system(f"Failed to set user permissions offline: {e}", "WARNING")
                raise

        try:
            payload = {"permission_keys": keys}
            resp = api_client.put(f"{self.api_url}/personnel/{person_id}/permissions", json=payload, timeout=5.0)
            if resp.status_code == 200:
                try:
                    from sync_engine import _get_local_conn
                    with _get_local_conn() as l_conn:
                        l_conn.execute("DELETE FROM personnel_permissions WHERE personnel_id = ?", (person_id,))
                        for k in keys:
                            l_conn.execute(
                                "INSERT OR REPLACE INTO personnel_permissions (personnel_id, permission_key, is_granted) VALUES (?, ?, 1)",
                                (person_id, k)
                            )
                        l_conn.commit()
                except Exception:
                    pass
                log_activity(f"تم تحديث صلاحيات الكادر ID: {person_id}")
            else:
                raise RuntimeError(f"API update permissions failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            # Fallback to local SQLite replica write if API network call fails
            try:
                from sync_engine import _get_local_conn
                with _get_local_conn() as l_conn:
                    l_conn.execute("DELETE FROM personnel_permissions WHERE personnel_id = ?", (person_id,))
                    for k in keys:
                        l_conn.execute(
                            "INSERT OR REPLACE INTO personnel_permissions (personnel_id, permission_key, is_granted) VALUES (?, ?, 1)",
                            (person_id, k)
                        )
                    l_conn.commit()
                log_activity(f"تم تحديث صلاحيات الكادر محلياً بالاحتياط ID: {person_id}")
            except Exception:
                raise e


# ---------------------------------------------------------------------------
# Module 4.2: Role & Responsibility Profiles Management (RBAC)
# ---------------------------------------------------------------------------

DEFAULT_SYSTEM_ROLES = [
    {
        "id": "admin",
        "name_ar": "مدير النظام",
        "name_en": "System Administrator",
        "description_ar": "صلاحيات وتحكم كامل بكافة وظائف وشاشات وإعدادات النظام",
        "base_role": "admin",
        "allowed_pages": ["home", "students", "orders", "departments", "courses", "personnel", "certificate", "issued_certs", "settings", "history"],
        "allowed_actions": ALL_PERMISSION_KEYS,
        "department_scope": "all",
        "is_system": 1,
    },
    {
        "id": "registrar",
        "name_ar": "مدير التسجيل وشؤون الطلاب",
        "name_en": "Registrar Director",
        "description_ar": "إدارة كاملة لشؤون الطلاب، الدرجات، أوامر التخرج، وإصدار الوثائق لكافة الأقسام",
        "base_role": "user",
        "allowed_pages": ["home", "students", "orders", "departments", "courses", "certificate", "issued_certs"],
        "allowed_actions": [
            "students:view", "students:create", "students:edit", "students:grades",
            "orders:view", "orders:create", "orders:edit",
            "certificates:issue", "issued_certs:view", "issued_certs:export",
            "departments:view", "courses:view", "settings:appearance"
        ],
        "department_scope": "all",
        "is_system": 1,
    },
    {
        "id": "cert_officer",
        "name_ar": "مسؤول إصدار الوثائق",
        "name_en": "Certificate Officer",
        "description_ar": "صلاحية فحص بيانات الطلاب وإصدار وطباعة الوثائق الرسمية وتصدير السجلات",
        "base_role": "user",
        "allowed_pages": ["home", "students", "orders", "certificate", "issued_certs"],
        "allowed_actions": [
            "students:view", "orders:view", "certificates:issue", "issued_certs:view", "issued_certs:export",
            "settings:appearance"
        ],
        "department_scope": "all",
        "is_system": 1,
    },
    {
        "id": "dept_head",
        "name_ar": "رئيس قسم / مقرر دراسي",
        "name_en": "Department Head / Coordinator",
        "description_ar": "إدارة المقررات الدراسية وإدخال وتدقيق درجات طلبة القسم وإدارة مناهجه",
        "base_role": "user",
        "allowed_pages": ["home", "students", "departments", "courses"],
        "allowed_actions": [
            "students:view", "students:grades", "departments:view", "courses:view", "courses:create", "courses:edit",
            "settings:appearance"
        ],
        "department_scope": "all",
        "is_system": 1,
    },
    {
        "id": "auditor",
        "name_ar": "مدقق درجات وبيانات",
        "name_en": "Academic Data Auditor",
        "description_ar": "تدقيق ومراجعة سجلات الطلاب والدرجات وأوامر التخرج دون صلاحية تعديل مباشر",
        "base_role": "user",
        "allowed_pages": ["home", "students", "orders", "issued_certs"],
        "allowed_actions": [
            "students:view", "orders:view", "issued_certs:view", "departments:view", "courses:view"
        ],
        "department_scope": "all",
        "is_system": 1,
    },
    {
        "id": "signer",
        "name_ar": "موقع معتمد للوثائق",
        "name_en": "Authorized Signer",
        "description_ar": "ظهور الاسم والتوقيع المعتمد على الوثائق الصادرة ومراجعة السجلات",
        "base_role": "signer",
        "allowed_pages": ["home", "issued_certs"],
        "allowed_actions": [
            "issued_certs:view"
        ],
        "department_scope": "all",
        "is_system": 1,
    },
    {
        "id": "user",
        "name_ar": "مستخدم عادي",
        "name_en": "Standard User",
        "description_ar": "صلاحيات الاطلاع الأساسية على لوحة التحكم وبيانات الطلاب",
        "base_role": "user",
        "allowed_pages": ["home", "students", "orders", "issued_certs"],
        "allowed_actions": [
            "students:view", "orders:view", "issued_certs:view"
        ],
        "department_scope": "all",
        "is_system": 1,
    },
]


# academic_periods.result_status codes (MySQL column is INT): key/text/number -> code
_RESULT_STATUS_CODES = {
    "PASSED": 1, "1": 1, 1: 1,
    "FAILED_REPEAT": 2, "FAILED": 2, "2": 2, 2: 2,
    "EXCEPTIONAL_PASS": 3, "3": 3, 3: 3,
    "CARRIED_OVER": 4, "4": 4, 4: 4,
    "DEFERRED": 5, "5": 5, 5: 5,
    "DISMISSED": 6, "6": 6, 6: 6,
}

_USER_ROLE_CACHE: dict | None = None
# Roles tables are created/seeded once per app run, not on every RoleRepository()
_ROLES_INITIALIZED: bool = False


class RoleRepository(BaseRepository):
    """
    Manages Role & Responsibility definitions (RBAC).
    Controls which pages, views, actions (permissions), and departments each responsibility can access.
    Stores profiles in SQLite `roles` table and JSON persistence file for cross-session durability.
    """

    _CONFIG_FILE = str(app_paths.data_path("data", "roles_config.json"))
    _USER_ROLES_FILE = str(app_paths.data_path("data", "user_roles.json"))

    def __init__(self):
        super().__init__()
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        """Ensures the SQLite roles table exists, user_roles table exists, and default roles are seeded (once per run)."""
        global _ROLES_INITIALIZED
        if _ROLES_INITIALIZED:
            return
        try:
            from sync_engine import _get_local_conn
            with _get_local_conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS roles (
                        id               TEXT PRIMARY KEY,
                        name_ar          TEXT NOT NULL,
                        name_en          TEXT NOT NULL,
                        description_ar   TEXT,
                        base_role        TEXT NOT NULL DEFAULT 'user',
                        allowed_pages    TEXT NOT NULL DEFAULT '[]',
                        allowed_actions  TEXT NOT NULL DEFAULT '[]',
                        department_scope TEXT NOT NULL DEFAULT 'all',
                        is_system        INTEGER NOT NULL DEFAULT 0,
                        created_at       TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_roles (
                        personnel_id     INTEGER PRIMARY KEY,
                        role_id          TEXT NOT NULL,
                        updated_at       TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM roles")
                count = cur.fetchone()[0]
                if count == 0:
                    for r in DEFAULT_SYSTEM_ROLES:
                        cur.execute("""
                            INSERT INTO roles (
                                id, name_ar, name_en, description_ar, base_role,
                                allowed_pages, allowed_actions, department_scope, is_system
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            r["id"], r["name_ar"], r["name_en"], r.get("description_ar", ""),
                            r.get("base_role", "user"), json.dumps(r.get("allowed_pages", [])),
                            json.dumps(r.get("allowed_actions", [])),
                            str(r.get("department_scope", "all")), int(r.get("is_system", 0))
                        ))
                    conn.commit()
                else:
                    # Update admin role to always have all permissions
                    cur.execute("SELECT allowed_actions FROM roles WHERE id = 'admin'")
                    adm_row = cur.fetchone()
                    if adm_row:
                        try:
                            acts = json.loads(adm_row[0]) if isinstance(adm_row[0], str) else []
                            if len(acts) < len(ALL_PERMISSION_KEYS):
                                cur.execute(
                                    "UPDATE roles SET allowed_actions = ? WHERE id = 'admin'",
                                    (json.dumps(ALL_PERMISSION_KEYS),)
                                )
                                conn.commit()
                        except Exception:
                            pass
            self._save_to_json_file()
            _ROLES_INITIALIZED = True
        except Exception as exc:
            log_system(f"RoleRepository init error: {exc}", "WARNING")

    def _save_to_json_file(self) -> None:
        """Persists roles to JSON file as durable backup."""
        try:
            roles = self._read_from_sqlite()
            os.makedirs(os.path.dirname(self._CONFIG_FILE), exist_ok=True)
            with open(self._CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(roles, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            log_system(f"Could not persist roles JSON: {exc}", "DEBUG")

    def _read_from_sqlite(self) -> list[dict]:
        """Reads and deserializes roles from SQLite."""
        try:
            from sync_engine import sqlite_read_all
            rows = sqlite_read_all("SELECT * FROM roles ORDER BY is_system DESC, id ASC")
            results = []
            for r in rows:
                item = dict(r)
                if isinstance(item.get("allowed_pages"), str):
                    try:
                        item["allowed_pages"] = json.loads(item["allowed_pages"])
                    except Exception:
                        item["allowed_pages"] = []
                if isinstance(item.get("allowed_actions"), str):
                    try:
                        item["allowed_actions"] = json.loads(item["allowed_actions"])
                    except Exception:
                        item["allowed_actions"] = []
                results.append(item)
            return results
        except Exception as exc:
            log_system(f"Failed to read roles from SQLite: {exc}", "WARNING")
            if os.path.exists(self._CONFIG_FILE):
                try:
                    with open(self._CONFIG_FILE, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
            return list(DEFAULT_SYSTEM_ROLES)

    def get_all(self) -> list[dict]:
        """Fetch all roles / responsibilities."""
        return self._read_from_sqlite()

    def get_by_id(self, role_id: str) -> dict | None:
        """Fetch a specific role by its slug identifier."""
        roles = self._read_from_sqlite()
        for r in roles:
            if r["id"] == role_id:
                return r
        return None

    def _server_write(self, method: str, path: str, payload: dict | None = None) -> bool:
        """
        Send a role change to the server so every laptop gets it at the next sync.
        Roles can only be changed while online (two laptops editing roles offline would
        conflict). Returns False when the server has no roles tables yet (run
        sql/fixes/2026-10-24_02_accounts_roles_passwords.sql): the change then stays on
        this laptop only, as before.
        """
        offline_msg = ("لا يمكن تعديل الأدوار والصلاحيات في وضع عدم الاتصال / "
                       "Roles can only be changed while connected to the server.")
        if not is_online():
            raise OfflineModeError(offline_msg)
        try:
            resp = api_client.request(method, f"{self.api_url}{path}", json=payload, timeout=10.0)
        except requests.exceptions.RequestException as exc:
            raise OfflineModeError(offline_msg) from exc
        if resp.status_code == 200:
            return True
        if resp.status_code == 400:
            raise ValueError(resp.json().get("detail", resp.text))
        log_system(f"Server did not store the role change ({resp.status_code}: {resp.text[:120]}); "
                   f"saved on this laptop only", "WARNING")
        return False

    def save_role(self, role_dict: dict) -> dict:
        """Insert or update a role / responsibility profile."""
        role_id = str(role_dict.get("id") or "").strip().lower()
        if not role_id:
            # Generate slug from name_en or name_ar
            import re
            base = role_dict.get("name_en") or role_dict.get("name_ar") or "role"
            role_id = re.sub(r'[^a-zA-Z0-9_]', '_', base.strip().lower()).strip('_')
            if not role_id:
                role_id = f"role_{int(datetime.now().timestamp())}"

        name_ar = str(role_dict.get("name_ar") or role_id).strip()
        name_en = str(role_dict.get("name_en") or role_id).strip()
        desc_ar = str(role_dict.get("description_ar") or "").strip()
        base_role = str(role_dict.get("base_role") or "user").strip().lower()
        if base_role not in ("admin", "user", "signer"):
            base_role = "user"

        allowed_pages = role_dict.get("allowed_pages") or []
        if isinstance(allowed_pages, str):
            try:
                allowed_pages = json.loads(allowed_pages)
            except Exception:
                allowed_pages = []

        allowed_actions = role_dict.get("allowed_actions") or []
        if isinstance(allowed_actions, str):
            try:
                allowed_actions = json.loads(allowed_actions)
            except Exception:
                allowed_actions = []

        # Sanitize allowed_actions: filter out legacy coarse wildcard keys
        allowed_actions = [a for a in allowed_actions if a not in ("settings:manage", "settings:view", "catalog:manage")]

        dept_scope = role_dict.get("department_scope") or "all"
        if isinstance(dept_scope, (list, dict)):
            dept_scope = json.dumps(dept_scope)
        else:
            dept_scope = str(dept_scope)

        is_system = int(role_dict.get("is_system", 0))

        # Shared roles live in MySQL; this laptop's copy is updated right after
        self._server_write("POST", "/roles", {
            "id": role_id, "name_ar": name_ar, "name_en": name_en, "description_ar": desc_ar,
            "base_role": base_role, "allowed_pages": allowed_pages, "allowed_actions": allowed_actions,
            "department_scope": dept_scope, "is_system": is_system,
        })

        from sync_engine import _get_local_conn
        with _get_local_conn() as conn:
            conn.execute("""
                INSERT INTO roles (
                    id, name_ar, name_en, description_ar, base_role,
                    allowed_pages, allowed_actions, department_scope, is_system
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name_ar = excluded.name_ar,
                    name_en = excluded.name_en,
                    description_ar = excluded.description_ar,
                    base_role = excluded.base_role,
                    allowed_pages = excluded.allowed_pages,
                    allowed_actions = excluded.allowed_actions,
                    department_scope = excluded.department_scope
            """, (
                role_id, name_ar, name_en, desc_ar, base_role,
                json.dumps(allowed_pages), json.dumps(allowed_actions),
                dept_scope, is_system
            ))
            conn.commit()

        self._save_to_json_file()
        log_activity(f"تم حفظ تعريف الدور/المسؤولية ({name_ar}) [ID: {role_id}]")

        # Synchronize updated permissions to all personnel assigned to this role
        try:
            p_repo = PersonnelRepository()
            perm_repo = PermissionRepository()
            all_personnel = p_repo.get_all() or []
            for p in all_personnel:
                pid = p.get("id")
                if not pid:
                    continue
                if self.get_user_role_id(pid, user_dict=p) == role_id:
                    try:
                        old_perms = perm_repo.get_user_permissions(pid) or []
                        user_pages = [k for k in old_perms if k.startswith("page:")]
                        perm_repo.set_user_permissions(pid, list(allowed_actions) + user_pages)
                        log_system(f"Propagated updated role {role_id} permissions to personnel ID {pid}", "INFO")
                    except Exception as u_sync_err:
                        log_system(f"Notice syncing permissions for user {pid} on role update: {u_sync_err}", "DEBUG")
        except Exception as sync_err:
            log_system(f"Error syncing assigned users for role {role_id}: {sync_err}", "WARNING")

        global _USER_ROLE_CACHE
        _USER_ROLE_CACHE = None

        return self.get_by_id(role_id) or role_dict

    def delete_role(self, role_id: str) -> bool:
        """Deletes a custom role (built-in system roles cannot be deleted)."""
        existing = self.get_by_id(role_id)
        if not existing:
            return False
        if existing.get("is_system"):
            raise ValueError("لا يمكن حذف الأدوار الافتراضية للنظام / Cannot delete built-in system roles")

        self._server_write("DELETE", f"/roles/{role_id}")

        from sync_engine import _get_local_conn
        with _get_local_conn() as conn:
            conn.execute("DELETE FROM roles WHERE id = ?", (role_id,))
            conn.commit()

        self._save_to_json_file()
        log_activity(f"تم حذف الدور/المسؤولية [ID: {role_id}]")
        return True

    def _save_user_role_assignment(self, personnel_id: int, role_id: str) -> None:
        """Persists personnel_id -> role_id assignment on the server, in SQLite and data/user_roles.json, invalidating cache."""
        global _USER_ROLE_CACHE
        _USER_ROLE_CACHE = None

        self._server_write("PUT", f"/user-roles/{int(personnel_id)}", {"role_id": str(role_id).strip()})

        try:
            from sync_engine import _get_local_conn
            with _get_local_conn() as conn:
                conn.execute("""
                    INSERT INTO user_roles (personnel_id, role_id, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(personnel_id) DO UPDATE SET
                        role_id = excluded.role_id,
                        updated_at = excluded.updated_at
                """, (int(personnel_id), str(role_id).strip()))
                conn.commit()
        except Exception as exc:
            log_system(f"Could not persist user role to SQLite: {exc}", "DEBUG")

        try:
            assignments = self._load_user_role_assignments(force_refresh=True)
            assignments[str(personnel_id)] = str(role_id).strip()
            os.makedirs(os.path.dirname(self._USER_ROLES_FILE), exist_ok=True)
            with open(self._USER_ROLES_FILE, "w", encoding="utf-8") as f:
                json.dump(assignments, f, ensure_ascii=False, indent=2)
            _USER_ROLE_CACHE = dict(assignments)
        except Exception as exc:
            log_system(f"Could not persist user role to JSON: {exc}", "DEBUG")

    def _load_user_role_assignments(self, force_refresh: bool = False) -> dict:
        """Loads user role assignments dictionary {str(personnel_id): role_id} from cache/JSON/SQLite."""
        global _USER_ROLE_CACHE
        if not force_refresh and _USER_ROLE_CACHE is not None:
            return dict(_USER_ROLE_CACHE)

        results = {}
        if os.path.exists(self._USER_ROLES_FILE):
            try:
                with open(self._USER_ROLES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        results.update(data)
            except Exception:
                pass

        try:
            from sync_engine import sqlite_read_all
            rows = sqlite_read_all("SELECT personnel_id, role_id FROM user_roles")
            for r in rows:
                results[str(r["personnel_id"])] = str(r["role_id"])
        except Exception:
            pass

        _USER_ROLE_CACHE = dict(results)
        return results

    def get_user_role_id(self, personnel_id: int, user_dict: dict | None = None) -> str:
        """
        Determines the active role_id for a given personnel user.
        Resolves in order of priority:
        1. Explicit user_roles assignment mapping (SQLite / JSON / In-memory Cache).
        2. Personnel record checks (using optional user_dict to bypass network/disk):
           - personnel_role == 'admin' -> 'admin'
           - responsibility_ar / responsibility_en matches a known role profile
           - responsibility keywords (e.g. 'وثائق' -> 'cert_officer', 'تسجيل' -> 'registrar')
           - personnel_role == 'signer' -> 'signer'
        3. Fallback to 'user'.
        """
        if not personnel_id:
            return "user"

        # 1. Check persistent assignments map (in-memory cached)
        assignments = self._load_user_role_assignments()
        if str(personnel_id) in assignments:
            r_id = assignments[str(personnel_id)]
            if r_id:
                return r_id

        # 2. Inspect personnel metadata
        try:
            user = user_dict
            if user is None:
                p_repo = PersonnelRepository()
                user = p_repo.get_by_id(personnel_id) or {}
            base_p_role = str(user.get("personnel_role") or "").strip().lower()
            if base_p_role == "admin":
                return "admin"

            resp_ar = str(user.get("responsibility_ar") or "").strip()
            resp_en = str(user.get("responsibility_en") or "").strip()

            # Direct match with role definitions
            roles = self.get_all()
            for r in roles:
                if resp_ar and (r.get("name_ar") == resp_ar or r.get("id") == resp_ar):
                    return r["id"]
                if resp_en and (r.get("name_en") == resp_en or r.get("id") == resp_en):
                    return r["id"]

            # Keyword heuristics for common titles
            if any(k in resp_ar for k in ["وثائق", "الوثائق", "وثيقة"]):
                return "cert_officer"
            if any(k in resp_ar for k in ["تسجيل", "التسجيل"]):
                return "registrar"
            if any(k in resp_ar for k in ["تدقيق", "مدقق"]):
                return "auditor"
            if any(k in resp_ar for k in ["رئيس قسم", "مقرر"]):
                return "dept_head"

            if base_p_role in ("signer", "admin"):
                return base_p_role
        except Exception as exc:
            log_system(f"Error determining user role for ID {personnel_id}: {exc}", "DEBUG")

        return "user"

    def assign_role_to_personnel(self, personnel_id: int, role_id: str) -> bool:
        """
        Assigns a role / responsibility profile to a specific user.
        Updates user's role/responsibility, persists user_roles mapping,
        and synchronizes granular permissions in `personnel_permissions`.
        """
        role = self.get_by_id(role_id)
        if not role:
            # Fallback if standard string
            role = next((r for r in DEFAULT_SYSTEM_ROLES if r["id"] == role_id), None)
            if not role:
                return False

        # 1. Persist user-to-role assignment in SQLite & JSON
        self._save_user_role_assignment(personnel_id, role_id)

        # 2. Update user record in Personnel table ONLY if base_role changed
        # IMPORTANT: Never overwrite a user's institutional responsibility/title (e.g. 'مسؤول وحدة الوثائق')
        # with software RBAC role names.
        try:
            p_repo = PersonnelRepository()
            cur_user = p_repo.get_by_id(personnel_id) or {}
            target_base_role = role.get("base_role", "user")
            if cur_user.get("personnel_role") != target_base_role:
                payload = {
                    "name_ar": cur_user.get("name_ar", ""),
                    "name_en": cur_user.get("name_en", ""),
                    "username": cur_user.get("username", ""),
                    "personnel_role": target_base_role,
                    "academic_title_ar": cur_user.get("academic_title_ar", ""),
                    "academic_title_en": cur_user.get("academic_title_en", ""),
                    "responsibility_ar": cur_user.get("responsibility_ar", ""),
                    "responsibility_en": cur_user.get("responsibility_en", ""),
                    "display_order": cur_user.get("display_order", 0),
                    "is_active": cur_user.get("is_active", 1),
                }
                p_repo.update(personnel_id, payload)
        except Exception as p_err:
            log_system(f"Notice while updating personnel record during role assign: {p_err}", "DEBUG")

        # 3. Synchronize granted permissions
        allowed_actions = role.get("allowed_actions") or []
        try:
            perm_repo = PermissionRepository()
            perm_repo.set_user_permissions(personnel_id, allowed_actions)
        except Exception as perm_err:
            log_system(f"Error syncing user permissions for role {role_id}: {perm_err}", "WARNING")

        log_activity(f"تم تعيين الدور ({role.get('name_ar')}) للمستخدم ID: {personnel_id}")
        return True

    def get_user_department_scope(self, personnel_id: int, user_dict: dict | None = None) -> list[int] | None:
        """
        Determines the restricted department IDs for a user, or None if user has full college-wide access.
        Returns:
            list[int] of department IDs if user is restricted to those departments.
            None if user has access to all departments ('admin', 'all', or unrestricted).
        """
        if not personnel_id:
            return None
        if int(personnel_id) == 1:
            return None

        role_id = self.get_user_role_id(personnel_id, user_dict=user_dict)
        if role_id == "admin":
            return None

        role = self.get_by_id(role_id)
        if not role:
            return None

        dept_scope = role.get("department_scope")
        if not dept_scope or dept_scope == "all":
            # Check if user responsibility specifically mentions a department (fallback heuristic)
            user = user_dict
            if user is None:
                try:
                    user = PersonnelRepository().get_by_id(personnel_id) or {}
                except Exception:
                    user = {}
            resp = (user.get("responsibility_ar") or "") + " " + (user.get("responsibility_en") or "")
            if resp.strip():
                try:
                    all_depts = DepartmentRepository().get_all() or []
                    for d in all_depts:
                        d_ar = str(d.get("name_ar") or "").strip()
                        d_en = str(d.get("name_en") or "").strip()
                        if (d_ar and d_ar in resp) or (d_en and d_en.lower() in resp.lower()):
                            return [int(d["id"])]
                except Exception:
                    pass
            return None

        allowed_ids = []
        if isinstance(dept_scope, str):
            try:
                parsed = json.loads(dept_scope)
                if isinstance(parsed, list):
                    allowed_ids = [int(x) for x in parsed if str(x).isdigit()]
                elif str(parsed).isdigit():
                    allowed_ids = [int(parsed)]
            except Exception:
                allowed_ids = [int(x.strip()) for x in dept_scope.split(",") if x.strip().isdigit()]
        elif isinstance(dept_scope, (list, tuple)):
            allowed_ids = [int(x) for x in dept_scope if str(x).isdigit()]

        return allowed_ids if allowed_ids else None

# ---------------------------------------------------------------------------
# Module 5: Course Catalog
# ---------------------------------------------------------------------------

class CourseRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        # Local-first: the local copy matches the API row for row (refreshed after every change)
        if not is_online() or _local_ready("courses"):
            return get_offline_courses()
        try:
            resp = api_client.get(f"{self.api_url}/courses", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            raise RuntimeError(f"API returned status code {resp.status_code}")
        except Exception as e:
            log_system(f"API request failed: {e}. Falling back to SQLite cache.", "WARNING")
            return get_offline_courses()
        
    def get_by_department(self, dept_id: int) -> list[dict]:
        if not is_online():
            return get_offline_courses_by_department(dept_id)
        try:
            resp = api_client.get(f"{self.api_url}/courses/by-dept/{dept_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            raise RuntimeError(f"API returned status code {resp.status_code}")
        except Exception as e:
            log_system(f"API request failed: {e}. Falling back to SQLite cache.", "WARNING")
            return get_offline_courses_by_department(dept_id)

    def get_by_dept_stage_system(self, dept_id: int, stage: int, system_id: int) -> list[dict]:
        if not is_online():
            return get_offline_courses_by_dept_stage_system(dept_id, stage, system_id)
        try:
            resp = api_client.get(
                f"{self.api_url}/courses/by-dept-stage-system",
                params={"dept_id": dept_id, "stage": stage, "system_id": system_id},
                timeout=5.0
            )
            if resp.status_code == 200:
                return resp.json()
            raise RuntimeError(f"API returned status code {resp.status_code}")
        except Exception as e:
            log_system(f"API request failed: {e}. Falling back to SQLite cache.", "WARNING")
            return get_offline_courses_by_dept_stage_system(dept_id, stage, system_id)

    def get_shared_dept_ids(self, course_id: int) -> list[int]:
        return []

    @_refreshes_local_copy("courses")
    def insert(self, data: dict) -> int:
        if not is_online():
            raise OfflineModeError()
        try:
            payload = dict(data)
            payload["credit_hours"] = int(payload["credit_hours"])
            payload["stage_number"] = int(payload["stage_number"])
            if "department_id" in payload and payload["department_id"] is not None:
                payload["department_id"] = int(payload["department_id"])
            
            resp = api_client.post(f"{self.api_url}/courses", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة مادة دراسية جديدة: {data.get('name_ar')}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    @_refreshes_local_copy("courses")
    def update(self, course_id: int, data: dict) -> None:
        payload = dict(data)
        payload["credit_hours"] = int(payload.get("credit_hours", 3))
        payload["stage_number"] = int(payload.get("stage_number", 1))
        if "department_id" in payload and payload["department_id"] is not None:
            payload["department_id"] = int(payload["department_id"])

        if not is_online():
            update_offline_course(
                course_id,
                payload.get("name_ar"),
                payload.get("name_en"),
                payload["credit_hours"],
                payload.get("department_id"),
                payload["stage_number"]
            )
            return

        try:
            resp = api_client.put(f"{self.api_url}/courses/{course_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل بيانات المادة الدراسية ID: {course_id}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")

            # Sync local SQLite cache
            update_offline_course(
                course_id,
                payload.get("name_ar"),
                payload.get("name_en"),
                payload["credit_hours"],
                payload.get("department_id"),
                payload["stage_number"]
            )
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    @_refreshes_local_copy("courses")
    def delete(self, course_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = api_client.delete(f"{self.api_url}/courses/{course_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف المادة الدراسية ID: {course_id}")
            else:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise


class StudentRepository(BaseRepository):
    def __init__(self, api_url: str | None = None, local_db_path: str = DB_PATH):
        super().__init__(api_url)
        self._api_base_url = api_url
        self.local_db_path = local_db_path

    @property
    def api_base_url(self) -> str:
        return self._api_base_url or get_api_url()

    @api_base_url.setter
    def api_base_url(self, value: str) -> None:
        self._api_base_url = value

    def search_students_paginated(self, query: str = "", limit: int = 25, offset: int = 0, dept_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Paginated student search route supporting online API endpoint with offline SQLite fallback."""
        if is_online():
            try:
                params = {"query": query, "limit": limit, "offset": offset}
                if dept_id is not None:
                    params["dept_id"] = dept_id
                response = api_client.get(
                    f"{self.api_base_url}/students/search", 
                    params=params,
                    timeout=3
                )
                if response.status_code == 200:
                    payload = response.json()
                    return [
                        {
                            "student_id": safe_cast(item.get("student_id"), int, 0),
                            "name_ar": safe_cast(item.get("name_ar"), str, "Unknown"),
                            "name_en": safe_cast(item.get("name_en"), str, "Unknown"),
                            "department_name_ar": safe_cast(item.get("department_name_ar"), str, "Unknown"),
                            "graduation_year": safe_cast(item.get("graduation_year"), str, "N/A"),
                            "average": safe_cast(item.get("average"), float, 0.0)
                        } for item in payload
                    ]
            except Exception as err:
                log_system(f"[WARNING][StudentRepository] API request failed, falling back to SQLite: {err}", "WARNING")

        return search_offline_students_paginated(self.local_db_path, query, limit, offset, dept_id=dept_id)

    def get_last_added_students(self, limit: int = 5) -> list[dict]:
        """Fetch the most recently added students (ordered by id DESC)."""
        return get_offline_last_added_students(limit)

    def get_recent_issued_certificates(self, limit: int = 5) -> list[dict]:
        """Fetch recently issued certificates strictly from issued_certificates table (no graduation_orders fallback)."""
        certs = IssuedCertificateRepository().get_all()
        return certs[:limit] if certs else []

    def get_issued_certificates_report(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        department_id: int | None = None,
        template_type: str | None = None
    ) -> list[dict]:
        """Calls GetIssuedCertificatesReport SP via API or SQLite offline fallback."""
        if is_online():
            try:
                params = {}
                if start_date: params["start_date"] = start_date
                if end_date: params["end_date"] = end_date
                if department_id: params["department_id"] = department_id
                if template_type: params["template_type"] = template_type
                resp = api_client.get(f"{self.api_url}/issued-certificates/report", params=params, timeout=5.0)
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                log_system(f"Failed to fetch issued certificates report via SP API: {e}", "WARNING")

        return get_offline_issued_certificates_report(start_date, end_date, department_id, template_type)

    def get_issued_certificates_by_student(self, student_id: int) -> list[dict]:
        """Calls GetIssuedCertificatesByStudent SP via API or SQLite offline fallback."""
        if is_online():
            try:
                resp = api_client.get(f"{self.api_url}/issued-certificates/by-student/{student_id}", timeout=5.0)
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                log_system(f"API request failed for student issued certs: {e}", "WARNING")

        return get_offline_issued_certificates_by_student(student_id)

    def get_issued_certificate_by_id(self, cert_id: int) -> dict | None:
        """Calls GetIssuedCertificateById SP via API or SQLite offline fallback."""
        if is_online():
            try:
                resp = api_client.get(f"{self.api_url}/issued-certificates/{cert_id}", timeout=5.0)
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                log_system(f"API request failed for issued cert by id: {e}", "WARNING")

        return get_offline_issued_certificate_by_id(cert_id)

    def get_recent_printed_certificates(self, limit: int = 5) -> list[dict]:
        """Fetch recently printed certificates strictly from issued_certificates table."""
        return self.get_recent_issued_certificates(limit=limit)

    def get_recent_graduates(self, limit: int = 5) -> list[dict]:
        """Fetch recently graduated students (students linked to a graduation order)."""
        return self.get_recent_issued_certificates(limit=limit)

    def _inject_missing_graduation_numbers(self, students_list: list[dict]) -> list[dict]:
        """Supplemental fetch for columns omitted by legacy Stored Procedures."""
        if not students_list:
            return students_list
            
        # Check if the key is missing from the first record
        if students_list and "postgraduation_number" not in students_list[0]:
            try:
                # Extract all IDs currently being processed
                student_ids = [s["id"] for s in students_list if "id" in s]
                if not student_ids: return students_list
                
                # Use the appropriate connection (MySQL if online, SQLite if offline)
                if is_online():
                    # For supplemental columns when online, fetch via the API endpoint
                    supp_data = {}
                    for sid in student_ids:
                        try:
                            resp = api_client.get(f"{self.api_url}/students/{sid}", timeout=5.0)
                            if resp.status_code == 200:
                                sdata = resp.json()
                                supp_data[sid] = {
                                    "id": sid,
                                    "sequence_number": sdata.get("sequence_number"),
                                    "postgraduation_number": sdata.get("postgraduation_number")
                                }
                        except Exception as e:
                            log_system(f"API supplemental fetch failed for {sid}: {e}", "WARNING")
                else:
                    supp_data = get_offline_student_supplemental_graduation(student_ids)
                
                # Inject back into the original list (set both keys for robust compatibility)
                for s in students_list:
                    sid = s.get("id")
                    if sid in supp_data:
                        s["sequence_number"] = supp_data[sid].get("sequence_number")
                        s["postgraduation_number"] = supp_data[sid].get("postgraduation_number")
                        
            except Exception as e:
                log_system(f"Supplemental fetch failed: {e}", "WARNING")
                
        return students_list

    def get_all_paginated(self, limit: int = 25, offset: int = 0, name_query: str = "", dept_id: int = None, year: str | int | None = None) -> list[dict]:
        if not is_online():
            res = get_offline_students_paginated(limit=limit, offset=offset, name_query=name_query, dept_id=dept_id, year=year)
        else:
            try:
                resp = api_client.get(
                    f"{self.api_url}/students/paginated",
                    params={
                        "limit": limit,
                        "offset": offset,
                        "name_query": name_query,
                        "dept_id": dept_id,
                        "year": str(year) if year is not None else None
                    },
                    timeout=5.0
                )
                if resp.status_code == 200:
                    res = resp.json()
                    # Sort online results by ID descending as requested by user
                    if not name_query:
                        res.sort(key=lambda x: x.get("id", 0), reverse=True)
                else:
                    res = []
            except Exception as e:
                log_system(f"API request failed: {e}", "WARNING")
                res = []
        return self._inject_missing_graduation_numbers(res)
        
    def get_by_id(self, student_id: int) -> dict | None:
        if not is_online():
            res = get_offline_student_by_id(student_id)
        else:
            try:
                resp = api_client.get(f"{self.api_url}/students/{student_id}", timeout=5.0)
                if resp.status_code == 200:
                    res = resp.json()
                else:
                    res = None
            except Exception as e:
                log_system(f"API request failed: {e}", "WARNING")
                res = None
        if res:
            res = self._inject_missing_graduation_numbers([res])[0]
        return res
 
    def search(self, query: str, limit: int = 8) -> list[dict]:
        clean_query = query.strip()
        
        # 1. Performance Guard: Mirroring the SP logic, abort if less than 2 chars
        if len(clean_query) < 2:
            return []

        if not is_online():
            res = search_offline_students(clean_query, limit=limit)
        else:
            # 3. Online Mode: FastAPI Call
            try:
                resp = api_client.get(
                    f"{self.api_url}/students/search/all",
                    params={"query": clean_query, "limit": limit},
                    timeout=5.0
                )
                if resp.status_code == 200:
                    res = resp.json()
                else:
                    res = []
            except Exception as e:
                log_system(f"API request failed: {e}", "WARNING")
                res = []
                
        # 4. Map back to standard dict format and inject missing numbers
        formatted_res = []
        for row in res:
            formatted_res.append({
                "id": row.get("student_id") if "student_id" in row else row.get("id"),
                "full_name_ar": row.get("name_ar") if "name_ar" in row else row.get("full_name_ar"),
                "full_name_en": row.get("name_en") if "name_en" in row else row.get("full_name_en"),
                "dept_name_ar": row.get("dept_name_ar"),
                "admission_year": row.get("admission_year"),
                "graduation_year": row.get("graduation_year"),
                "average": row.get("average")
            })
            
        return self._inject_missing_graduation_numbers(formatted_res)
        
    def count(self, name_query: str = "", dept_id: int = None, year: str | int | None = None) -> int:
        if not is_online():
            return count_offline_students(name_query=name_query, dept_id=dept_id, year=year)
        try:
            resp = api_client.get(
                f"{self.api_url}/students/count/all",
                params={
                    "name_query": name_query,
                    "dept_id": dept_id,
                    "year": str(year) if year is not None else None
                },
                timeout=5.0
            )
            if resp.status_code == 200:
                row = resp.json()
            else:
                row = {"total_count": 0}
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            row = {"total_count": 0}
        return row['total_count'] if row else 0
 
    def get_by_order(self, order_id: int) -> list[dict]:
        if not is_online():
            return get_offline_students_by_order_id(order_id)
        try:
            resp = api_client.get(f"{self.api_url}/students/by-order/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def link_to_order(self, student_id: int, order_id: int) -> None:
        if not is_online():
            link_offline_students_to_order([student_id], order_id)
            log_activity(f"تم ربط الطالب ID {student_id} بالأمر الجامعي ID {order_id}")
            return
        try:
            resp = api_client.put(f"{self.api_url}/students/{student_id}/link-order/{order_id}", timeout=5.0)
            if resp.status_code != 200:
                st = self.get_by_id(student_id)
                if st:
                    st["order_id"] = order_id
                    self.update(student_id, st)
            log_activity(f"تم ربط الطالب ID {student_id} بالأمر الجامعي ID {order_id}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")

    def unlink_from_order(self, student_id: int) -> None:
        if not is_online():
            unlink_offline_students_from_order([student_id])
            log_activity(f"تم إلغاء ربط الطالب ID {student_id} من الأمر الجامعي")
            return
        try:
            resp = api_client.put(f"{self.api_url}/students/{student_id}/unlink-order", timeout=5.0)
            if resp.status_code != 200:
                st = self.get_by_id(student_id)
                if st:
                    st["order_id"] = None
                    self.update(student_id, st)
            log_activity(f"تم إلغاء ربط الطالب ID {student_id} من الأمر الجامعي")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")

    def search_unlinked(self, name_query: str = "", dept_id: int | None = None, year: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if is_online():
            try:
                resp = api_client.get(
                    f"{self.api_url}/students/search/unlinked",
                    params={
                        "name_query": name_query,
                        "dept_id": dept_id,
                        "year": str(year) if year is not None else None,
                        "limit": limit
                    },
                    timeout=3.0
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                log_system(f"API request failed: {e}", "WARNING")

        return search_offline_unlinked_students(name_query=name_query, dept_id=dept_id, year=year, limit=limit)

    def auto_link_matching(self, order_id: int, order_data: dict) -> int:
        dept_id = order_data.get("department_id")
        grad_year = order_data.get("graduation_year")
        matching = get_offline_unlinked_students_matching(dept_id, grad_year)

        count = 0
        for m in matching:
            sid = m["id"]
            self.link_to_order(sid, order_id)
            count += 1
        return count
 
    def unlink_from_order(self, student_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = api_client.post(f"{self.api_url}/students/{student_id}/unlink-order", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم فك ارتباط الطالب ID: {student_id} بالأمر الجامعي")
            else:
                raise RuntimeError(f"API unlink failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise
 
    def link_students_to_order(self, order_id: int, order_data: dict) -> int:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = api_client.post(f"{self.api_url}/students/link-order/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                row = resp.json()
                count = row.get('affected_rows', 0)
                if count > 0:
                    log_activity(f"تم ربط {count} طالب بالأمر الجامعي ID: {order_id}")
                return count
            else:
                raise RuntimeError(f"API link failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def link_to_order(self, student_id: int, order_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = api_client.post(f"{self.api_url}/students/{student_id}/link-order/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم ربط الطالب ID: {student_id} بالأمر الجامعي ID: {order_id}")
            else:
                raise RuntimeError(f"API single link failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise
 
    def search_for_order(self, name_query: str = "", admission_year: str | int | None = None, department_id: int = None, limit: int = 50, offset: int = 0) -> list[dict]:
        """Legacy wrapper for OrderStudentsScreen mapping to the new paginated SP."""
        return self.get_all_paginated(limit=limit, offset=offset, name_query=name_query, dept_id=department_id, year=admission_year)
 
    def get_distinct_admission_years(self) -> list[str]:
        if not is_online():
            return get_offline_distinct_admission_years()
        try:
            resp = api_client.get(f"{self.api_url}/students/distinct/years", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []
 
    def insert(self, data: dict) -> int:
        if not is_online():
            # Route to offline sync engine
            return log_offline_insert("students", dict(data))
        try:
            payload = {
                "full_name_ar": data.get('full_name_ar'),
                "full_name_en": data.get('full_name_en'),
                "gender": data.get('gender', 1),
                "sequence_number": data.get('sequence_number'),
                "postgraduation_number": data.get('postgraduation_number'),
                "date_of_birth": str(data.get('date_of_birth')) if data.get('date_of_birth') else None,
                "birthplace_id": data.get('birthplace_id', 2),
                "birthplace_other": data.get('birthplace_other'),
                "nationality_id": data.get('nationality_id', 274),
                "national_id": data.get('national_id'),
                "department_id": data.get('department_id'),
                "study_system_id": data.get('study_system_id'),
                "degree_level": data.get('degree_level', 1),
                "order_id": data.get('order_id'),
                "admission_year": str(data.get('admission_year')) if data.get('admission_year') else None,
                "summer_training_data": data.get('summer_training_data'),
                "average": float(data['average']) if data.get('average') is not None else None,
                "graduation_date": str(data.get('graduation_date')) if data.get('graduation_date') else None,
                "graduation_semester": data.get('graduation_semester')
            }
            resp = api_client.post(f"{self.api_url}/students", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة طالب جديد: {data.get('full_name_ar')}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise
        
    def update(self, student_id: int, data: dict) -> None:
        payload = {
            "full_name_ar": data.get('full_name_ar'),
            "full_name_en": data.get('full_name_en'),
            "gender": data.get('gender', 1),
            "sequence_number": data.get('sequence_number'),
            "postgraduation_number": data.get('postgraduation_number'),
            "date_of_birth": str(data.get('date_of_birth')) if data.get('date_of_birth') else None,
            "birthplace_id": data.get('birthplace_id'),
            "birthplace_other": data.get('birthplace_other'),
            "nationality_id": data.get('nationality_id', 1),
            "national_id": data.get('national_id'),
            "department_id": data.get('department_id'),
            "study_system_id": data.get('study_system_id'),
            "degree_level": data.get('degree_level', 1),
            "order_id": data.get('order_id'),
            "admission_year": str(data.get('admission_year')) if data.get('admission_year') else None,
            "summer_training_data": data.get('summer_training_data'),
            "average": float(data['average']) if data.get('average') is not None else None,
            "graduation_date": str(data.get('graduation_date')) if data.get('graduation_date') else None,
            "graduation_semester": data.get('graduation_semester')
        }

        if not is_online():
            log_offline_update("students", student_id, payload)
            log_activity(f"تم تعديل بيانات الطالب ID: {student_id} (أوفلاين)")
            return

        try:
            resp = api_client.put(f"{self.api_url}/students/{student_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل بيانات الطالب ID: {student_id}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def bulk_import(self, students_payload: list[dict]) -> dict:
        """Atomically imports a cohort of students, periods, and enrollments."""
        if not is_online():
            raise OfflineModeError("Bulk import requires active online connection to central server.")
        try:
            resp = api_client.post(
                f"{self.api_url}/api/students/bulk-import",
                json={"students": students_payload},
                timeout=60.0
            )
            if resp.status_code == 200:
                result = resp.json()
                log_activity(f"اكتمل الاستيراد المجمع للطلاب: تم إنشاء {result.get('created_students')}, وتحديث {result.get('updated_students')}")
                pull_mysql_to_sqlite_background()
                return result
            else:
                raise RuntimeError(f"Bulk import failed ({resp.status_code}): {resp.text}")
        except Exception as e:
            log_system(f"Bulk import API error: {e}", "ERROR")
            raise
 
    def delete(self, student_id: int) -> None:
        if not is_online():
            delete_offline_student(student_id)
            log_activity(f"تم حذف الطالب ID: {student_id}")
            return

        try:
            resp = api_client.delete(f"{self.api_url}/students/{student_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف الطالب ID: {student_id}")
            else:
                self._call_write("DeleteStudent", (student_id,))
                log_activity(f"تم حذف الطالب ID: {student_id}")
        except Exception as e:
            log_system(f"API delete failed, using direct write: {e}", "WARNING")
            self._call_write("DeleteStudent", (student_id,))
            log_activity(f"تم حذف الطالب ID: {student_id}")

# ---------------------------------------------------------------------------
# Module 7: Timelines & Enrollments
# ---------------------------------------------------------------------------

class AcademicPeriodRepository(BaseRepository):
    def get_by_student(self, student_id: int) -> list[dict]:
        periods = []
        if is_online():
            try:
                resp = api_client.get(f"{self.api_url}/academic-periods/by-student/{student_id}", timeout=3.0)
                if resp.status_code == 200:
                    periods = resp.json()
            except Exception as e:
                log_system(f"API request failed for get_by_student academic_periods: {e}", "WARNING")

        if not periods:
            periods = get_offline_academic_periods_by_student(student_id)

        status_code_map = {
            1: "PASSED", "1": "PASSED", "PASSED": "PASSED",
            2: "FAILED_REPEAT", "2": "FAILED_REPEAT", "FAILED": "FAILED_REPEAT", "FAILED_REPEAT": "FAILED_REPEAT",
            3: "EXCEPTIONAL_PASS", "3": "EXCEPTIONAL_PASS", "EXCEPTIONAL_PASS": "EXCEPTIONAL_PASS",
            4: "CARRIED_OVER", "4": "CARRIED_OVER", "CARRIED_OVER": "CARRIED_OVER",
            5: "DEFERRED", "5": "DEFERRED", "DEFERRED": "DEFERRED",
            6: "DISMISSED", "6": "DISMISSED", "DISMISSED": "DISMISSED",
        }

        norm_periods = []
        for r in periods:
            if isinstance(r, dict):
                raw_st = r.get("result_status")
                r["result_status"] = status_code_map.get(raw_st, status_code_map.get(str(raw_st).strip(), "PASSED"))
                norm_periods.append(r)
            elif isinstance(r, (tuple, list)) and len(r) >= 7:
                raw_st = r[6]
                st_str = status_code_map.get(raw_st, status_code_map.get(str(raw_st).strip(), "PASSED"))
                norm_periods.append({
                    "id": r[0], "student_id": r[1], "academic_year": r[2],
                    "study_system_id": r[3], "stage_number": r[4], "semester_num": r[5],
                    "result_status": st_str
                })

        return norm_periods

    def insert(self, student_id: int, year: str, sys_id: int, stage: int, semester_num: int = 1, result_status: str = "PASSED") -> int:
        # MySQL academic_periods.result_status is a number (1=PASSED ... 6=DISMISSED);
        # sending the key text 'PASSED' made MySQL store 0, so always send the code
        result_status = _RESULT_STATUS_CODES.get(result_status, _RESULT_STATUS_CODES.get(str(result_status).strip().upper(), 1))
        if not is_online():
            return log_offline_insert("academic_periods", {
                "student_id": student_id,
                "academic_year": year,
                "study_system_id": sys_id,
                "stage_number": stage,
                "semester_num": semester_num,
                "result_status": result_status,
            })
        try:
            payload = {
                "student_id": student_id,
                "academic_year": str(year),
                "study_system_id": sys_id,
                "stage_number": stage,
                "semester_num": semester_num,
                "result_status": str(result_status),
            }
            resp = api_client.post(f"{self.api_url}/academic-periods", json=payload, timeout=3.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                try:
                    from sync_engine import _get_local_conn
                    with _get_local_conn() as conn_loc:
                        conn_loc.execute(
                            "INSERT OR REPLACE INTO academic_periods (id, student_id, academic_year, study_system_id, stage_number, semester_num, result_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (new_id, student_id, str(year), sys_id, stage, semester_num, result_status)
                        )
                        conn_loc.commit()
                except Exception:
                    pass
                return new_id
        except Exception as e:
            log_system(f"API request failed for academic-periods insert: {e}", "WARNING")

        try:
            new_id = self._call_write("InsertAcademicPeriod", (student_id, str(year), stage, semester_num, result_status))
            if new_id:
                return new_id
        except Exception as sp_err:
            log_system(f"SP InsertAcademicPeriod error: {sp_err}", "WARNING")

        return log_offline_insert("academic_periods", {
            "student_id": student_id, "academic_year": year,
            "study_system_id": sys_id, "stage_number": stage,
            "semester_num": semester_num, "result_status": result_status,
        })

    def update_status(self, period_id: int, result_status: str | int) -> None:
        st_code = _RESULT_STATUS_CODES.get(result_status, _RESULT_STATUS_CODES.get(str(result_status).strip().upper(), 1))
        st_key = {1: "PASSED", 2: "FAILED_REPEAT", 3: "EXCEPTIONAL_PASS", 4: "CARRIED_OVER", 5: "DEFERRED", 6: "DISMISSED"}.get(st_code, "PASSED")

        update_offline_academic_period_status(period_id, st_key)

        if not is_online():
            return

        try:
            resp = api_client.patch(
                f"{self.api_url}/academic-periods/{period_id}/status",
                json={"result_status": str(st_code)},
                timeout=3.0
            )
        except Exception as e:
            log_system(f"API update_status failed: {e}", "WARNING")

    def update_stage(self, period_id: int, stage_number: int) -> None:
        update_offline_academic_period_stage(period_id, stage_number)

        if not is_online():
            return

        try:
            resp = api_client.patch(
                f"{self.api_url}/academic-periods/{period_id}/stage",
                json={"stage_number": stage_number},
                timeout=3.0
            )
        except Exception as e:
            log_system(f"API update_stage failed: {e}", "WARNING")

    def delete(self, period_id: int) -> None:
        delete_offline_academic_period(period_id)
        if not is_online():
            log_activity(f"تم حذف المرحلة الدراسية (أوفلاين) ID: {period_id}")
            return
        try:
            resp = api_client.delete(f"{self.api_url}/academic-periods/{period_id}", timeout=5.0)
            if resp.status_code != 200:
                log_system(f"API delete warning for academic-period {period_id}: {resp.text}", "WARNING")
        except Exception as e:
            log_system(f"API request failed for academic-period delete: {e}", "WARNING")
            raise


class EnrollmentRepository(BaseRepository):
    def get_by_period(self, period_id: int) -> list[dict]:
        if not is_online():
            return get_offline_enrollments_by_period(period_id)
        try:
            resp = api_client.get(f"{self.api_url}/enrollments/by-period/{period_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def insert(self, period_id: int, course_id: int, score: float, is_second: int) -> int:
        val = is_second
        passed_round = '2' if val == 2 else ('3' if val == 3 else '1')
        if not is_online():
            return log_offline_insert("enrollments", {
                "period_id": period_id,
                "course_id": course_id,
                "score": score,
                "passed_round": passed_round,
            })
        try:
            payload = {
                "period_id": period_id,
                "course_id": course_id,
                "score": float(score),
                "is_second": int(is_second)
            }
            resp = api_client.post(f"{self.api_url}/enrollments", json=payload, timeout=3.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                try:
                    from sync_engine import _get_local_conn
                    with _get_local_conn() as conn_loc:
                        conn_loc.execute(
                            "INSERT OR REPLACE INTO enrollments (id, period_id, course_id, score, passed_round) VALUES (?, ?, ?, ?, ?)",
                            (new_id, period_id, course_id, float(score), passed_round)
                        )
                        conn_loc.commit()
                except Exception:
                    pass
                return new_id
        except Exception as e:
            log_system(f"API request failed for enrollment insert: {e}", "WARNING")

        try:
            new_id = self._call_write("InsertEnrollment", (period_id, course_id, float(score), passed_round))
            if new_id:
                return new_id
        except Exception as sp_err:
            log_system(f"SP InsertEnrollment error: {sp_err}", "WARNING")

        return log_offline_insert("enrollments", {
            "period_id": period_id, "course_id": course_id,
            "score": score, "passed_round": passed_round
        })

    def update(self, enrollment_id: int, score: float, is_second: int) -> None:
        val = int(is_second)
        if val == 2:
            passed_round = '2'
        elif val == 3:
            passed_round = '3'
        elif val == 0:
            passed_round = '0'
        else:
            passed_round = '1'

        update_offline_enrollment(enrollment_id, score, passed_round)

        if not is_online():
            return

        try:
            resp = api_client.put(
                f"{self.api_url}/enrollments/{enrollment_id}",
                params={"score": float(score), "is_second": int(is_second)},
                timeout=3.0
            )
        except Exception as e:
            log_system(f"API request failed for enrollment update: {e}", "WARNING")

    def delete(self, enrollment_id: int) -> None:
        delete_offline_enrollment(enrollment_id)
        if not is_online():
            log_activity(f"تم حذف تسجيل المادة (أوفلاين) ID: {enrollment_id}")
            return
        try:
            resp = api_client.delete(f"{self.api_url}/enrollments/{enrollment_id}", timeout=5.0)
            if resp.status_code != 200:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

# ---------------------------------------------------------------------------
# Module 8: Integrated Report Engine Pipeline
# ---------------------------------------------------------------------------
class CertificateRepository(BaseRepository):
    
    def get_full_certificate_data(self, student_id: int, grouping_mode: str = "DEFAULT") -> dict | None:
        """Delegates 100% of certificate data fetching & context transformation to cert_repository.py."""
        try:
            from cert_repository import get_certificate_payload
            return get_certificate_payload(student_id, grouping_mode)
        except Exception as e:
            log_system(f"cert_repository.get_certificate_payload failed: {e}", "WARNING")
            return None

    def get_flat_yearly_courses(self, student_id: int) -> list[dict]:
        """Delegates flat-yearly course transcript fetching to cert_repository.py / data.query."""
        if is_online():
            try:
                resp = api_client.get(f"{self.api_url}/certificates/flat-yearly/{student_id}", timeout=5.0)
                if resp.status_code == 200:
                    rows = resp.json()
                    if isinstance(rows, list):
                        return rows
            except Exception as e:
                log_system(f"API flat-yearly courses fetch failed: {e}", "WARNING")

        try:
            from data.query import get_offline_flat_yearly_courses
            return get_offline_flat_yearly_courses(student_id)
        except Exception as e:
            log_system(f"Offline flat-yearly courses query failed: {e}", "WARNING")
            return []

# ---------------------------------------------------------------------------
# Module 9: Graduation Orders
# ---------------------------------------------------------------------------

class GraduationOrderRepository(BaseRepository):
    
    def get_all(self, limit: int = 25, offset: int = 0) -> list[dict]:
        # Local-first: the local copy matches the API row for row (refreshed after every change)
        if not is_online() or _local_ready("graduation_orders"):
            return get_offline_graduation_orders(limit=limit, offset=offset)
        try:
            resp = api_client.get(f"{self.api_url}/graduation-orders", params={"limit": limit, "offset": offset}, timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def get_by_id(self, order_id: int) -> dict | None:
        if not is_online():
            return get_offline_graduation_order_by_id(order_id)
        try:
            resp = api_client.get(f"{self.api_url}/graduation-orders/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return None
        try:
            resp = api_client.get(f"{self.api_url}/graduation-orders/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return None

    @_refreshes_local_copy("graduation_orders")
    def insert(self, data: dict) -> int:
        if not is_online():
            args = (
                data.get('order_number'),
                data.get('order_date'),
                data.get('department_id'),
                data.get('study_type'),
                data.get('graduation_year'),
                data.get('graduation_semester'),
                data.get('num_students'),
                data.get('notes'),
                data.get('study_system_id', 1)
            )
            new_id = self._call_write("InsertGraduationOrder", args)
            log_activity(f"تم إضافة أمر جامعي جديد: {data.get('order_number')}")
            return new_id
        try:
            payload = {
                "order_number": data.get('order_number'),
                "order_date": str(data.get('order_date')),
                "department_id": int(data.get('department_id')),
                "study_type": data.get('study_type'),
                "graduation_year": int(data.get('graduation_year')),
                "graduation_semester": data.get('graduation_semester'),
                "num_students": int(data.get('num_students')),
                "notes": data.get('notes'),
                "study_system_id": int(data.get('study_system_id', 1))
            }
            resp = api_client.post(f"{self.api_url}/graduation-orders", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة أمر جامعي جديد: {data.get('order_number')}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    @_refreshes_local_copy("graduation_orders")
    def update(self, order_id: int, data: dict) -> None:
        if not is_online():
            args = (
                order_id,
                data.get('order_number'),
                data.get('order_date'),
                data.get('department_id'),
                data.get('study_type'),
                data.get('graduation_year'),
                data.get('graduation_semester'),
                data.get('num_students'),
                data.get('notes'),
                data.get('study_system_id', 1)
            )
            self._call_write("UpdateGraduationOrder", args)
            log_activity(f"تم تعديل بيانات الأمر الجامعي: {data.get('order_number')}")
            return
        try:
            payload = {
                "order_number": data.get('order_number'),
                "order_date": str(data.get('order_date')),
                "department_id": int(data.get('department_id')),
                "study_type": data.get('study_type'),
                "graduation_year": int(data.get('graduation_year')),
                "graduation_semester": data.get('graduation_semester'),
                "num_students": int(data.get('num_students')),
                "notes": data.get('notes'),
                "study_system_id": int(data.get('study_system_id', 1))
            }
            resp = api_client.put(f"{self.api_url}/graduation-orders/{order_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل بيانات الأمر الجامعي: {data.get('order_number')}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    @_refreshes_local_copy("graduation_orders")
    def delete(self, order_id: int) -> None:
        if not is_online():
            self._call_write("DeleteGraduationOrder", (order_id,))
            log_activity(f"تم حذف الأمر الجامعي ID: {order_id}")
            return
        try:
            resp = api_client.delete(f"{self.api_url}/graduation-orders/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف الأمر الجامعي ID: {order_id}")
            else:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def get_students_for_order(self, order_id: int) -> list[dict]:
        if not is_online():
            return get_offline_students_by_order_id(order_id)
        try:
            resp = api_client.get(f"{self.api_url}/students/by-order/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    @_refreshes_local_copy("graduation_orders")
    def link_students(self, order_id: int) -> int:
        if not is_online():
            row = self._call_read_one("LinkStudentsToOrder", (order_id,))
            count = row['affected_rows'] if row and 'affected_rows' in row else 0
            if count > 0:
                log_activity(f"تم ربط {count} طالب بالأمر الجامعي ID: {order_id}")
            return count
        try:
            resp = api_client.post(f"{self.api_url}/students/link-order/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                row = resp.json()
                count = row.get('affected_rows', 0)
                if count > 0:
                    log_activity(f"تم ربط {count} طالب بالأمر الجامعي ID: {order_id}")
                return count
            return 0
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return 0

    @_refreshes_local_copy("graduation_orders")
    def unlink_student(self, student_id: int) -> None:
        if not is_online():
            self._call_write("UnlinkStudentFromOrder", (student_id,))
            log_activity(f"تم فك ارتباط الطالب ID: {student_id} بالأمر الجامعي")
            return
        try:
            resp = api_client.post(f"{self.api_url}/students/{student_id}/unlink-order", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم فك ارتباط الطالب ID: {student_id} بالأمر الجامعي")
            else:
                raise RuntimeError(f"API unlink failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

# ---------------------------------------------------------------------------
# Module 10: Thesis Records
# ---------------------------------------------------------------------------
class ThesisRepository(BaseRepository):
    def get_by_student(self, student_id: int) -> list[dict]:
        if not is_online():
            return self._call_read_all("GetThesisByStudent", (student_id,))
        try:
            resp = api_client.get(f"{self.api_url}/thesis/by-student/{student_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def insert(self, student_id: int, title_ar: str, title_en: str, defense_date: str = None, committee_decision: str = None, final_grade: float = None) -> int:
        if not is_online():
            args = (student_id, title_ar, title_en, defense_date, committee_decision, final_grade)
            new_id = self._call_write("InsertThesis", args)
            log_activity(f"تم إضافة سجل أطروحة للطالب ID: {student_id}")
            return new_id
        try:
            payload = {
                "student_id": student_id,
                "title_ar": title_ar,
                "title_en": title_en,
                "defense_date": str(defense_date) if defense_date else None,
                "committee_decision": committee_decision,
                "final_grade": float(final_grade) if final_grade is not None else None
            }
            resp = api_client.post(f"{self.api_url}/thesis", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة سجل أطروحة للطالب ID: {student_id}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def update(self, thesis_id: int, title_ar: str, title_en: str, defense_date: str = None, committee_decision: str = None, final_grade: float = None) -> None:
        if not is_online():
            args = (thesis_id, title_ar, title_en, defense_date, committee_decision, final_grade)
            self._call_write("UpdateThesis", args)
            log_activity(f"تم تعديل سجل الأطروحة ID: {thesis_id}")
            return
        try:
            payload = {
                "student_id": 0,
                "title_ar": title_ar,
                "title_en": title_en,
                "defense_date": str(defense_date) if defense_date else None,
                "committee_decision": committee_decision,
                "final_grade": float(final_grade) if final_grade is not None else None
            }
            resp = api_client.put(f"{self.api_url}/thesis/{thesis_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل سجل الأطروحة ID: {thesis_id}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def delete(self, thesis_id: int) -> None:
        if not is_online():
            self._call_write("DeleteThesis", (thesis_id,))
            log_activity(f"تم حذف سجل الأطروحة ID: {thesis_id}")
            return
        try:
            resp = api_client.delete(f"{self.api_url}/thesis/{thesis_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف سجل الأطروحة ID: {thesis_id}")
            else:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def save(self, student_id: int, title_ar: str, title_en: str, defense_date: str = None, committee_decision: str = None, final_grade: float = None) -> None:
        existing = self.get_by_student(student_id)
        if existing:
            thesis_id = existing[0]['id']
            self.update(thesis_id, title_ar, title_en, defense_date, committee_decision, final_grade)
        else:
            self.insert(student_id, title_ar, title_en, defense_date, committee_decision, final_grade)

# ---------------------------------------------------------------------------
# Module 11: Student Supervisors (Postgraduates)
# ---------------------------------------------------------------------------
class StudentSupervisorRepository(BaseRepository):
    def get_by_student(self, student_id: int) -> list[dict]:
        if not is_online():
            return self._call_read_all("GetSupervisorsByStudent", (student_id,))
        try:
            resp = api_client.get(f"{self.api_url}/supervisors/by-student/{student_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def insert(self, student_id: int, personnel_id: int, supervision_role: str) -> int:
        if not is_online():
            new_id = self._call_write("InsertStudentSupervisor", (student_id, personnel_id, supervision_role))
            log_activity(f"تم إضافة مشرف جديد للطالب ID: {student_id}")
            return new_id
        try:
            payload = {
                "student_id": student_id,
                "personnel_id": personnel_id,
                "supervision_role": supervision_role
            }
            resp = api_client.post(f"{self.api_url}/supervisors", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة مشرف جديد للطالب ID: {student_id}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def update(self, record_id: int, personnel_id: int, supervision_role: str) -> None:
        if not is_online():
            self._call_write("UpdateStudentSupervisor", (record_id, personnel_id, supervision_role))
            log_activity(f"تم تعديل بيانات الإشراف ID: {record_id}")
            return
        try:
            payload = {
                "student_id": 0,
                "personnel_id": personnel_id,
                "supervision_role": supervision_role
            }
            resp = api_client.put(f"{self.api_url}/supervisors/{record_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل بيانات الإشراف ID: {record_id}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def delete(self, record_id: int) -> None:
        if not is_online():
            self._call_write("DeleteStudentSupervisor", (record_id,))
            log_activity(f"تم حذف سجل الإشراف ID: {record_id}")
            return
        try:
            resp = api_client.delete(f"{self.api_url}/supervisors/{record_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف سجل الإشراف ID: {record_id}")
            else:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

# ---------------------------------------------------------------------------
# Compatibility wrapper for students_screen.py
# ---------------------------------------------------------------------------
class SupervisorRepository(BaseRepository):
    def get_by_student(self, student_id: int) -> list[dict]:
        return StudentSupervisorRepository(self.api_url).get_by_student(student_id)

    def add(self, student_id: int, personnel_id: int, role: str) -> None:
        StudentSupervisorRepository(self.api_url).insert(student_id, personnel_id, role)

    def delete_by_student(self, student_id: int) -> None:
        records = self.get_by_student(student_id)
        for r in records:
            if 'id' in r:
                StudentSupervisorRepository(self.api_url).delete(r['id'])

# ---------------------------------------------------------------------------
# Audit Logs (Fallback)
# ---------------------------------------------------------------------------
class AuditRepository(BaseRepository):
    def _read_activity_logs(self) -> list[dict]:
        log_path = str(app_paths.data_path("logs", "activity_log.txt"))
        if not os.path.exists(log_path):
            return []
        logs = []
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    parts = line.split(" [ACTIVITY] ", 1)
                    if len(parts) == 2:
                        dt = parts[0].split(",")[0]
                        msg = parts[1].strip()
                        logs.append({
                            "id": len(logs),
                            "table_name": "System",
                            "action": "INFO",
                            "summary": msg,
                            "created_at": dt,
                            "error_info": None
                        })
        except Exception:
            pass
        return list(reversed(logs))

    def count_audit_log(self, table_filter: str = "", action_filter: str = "") -> int:
        return len(self._read_activity_logs())

    def get_audit_log(self, table_filter: str = "", action_filter: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
        return self._read_activity_logs()[offset:offset+limit]

    def clear_audit_logs(self) -> None:
        try:
            log_path = str(app_paths.data_path("logs", "activity_log.txt"))
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Module 12: Dashboard Analytics
# ---------------------------------------------------------------------------

class DashboardRepository(BaseRepository):
    def get_counts(self) -> dict:
        if not is_online():
            return get_offline_dashboard_counts()
        
        try:
            resp = api_client.get(f"{self.api_url}/api/dashboard/counts", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            raise RuntimeError(f"API returned status code {resp.status_code}")
            
        except Exception as e:
            log_system(f"API request failed: {e}. Falling back to SQLite cache.", "WARNING")
            return get_offline_dashboard_counts()


# ---------------------------------------------------------------------------
# Module 14: Predefined Study Routines
# ---------------------------------------------------------------------------

class StudyRoutineRepository(BaseRepository):
    def get_all(self, dept_id: int | None = None) -> list[dict]:
        """Fetch all predefined study routines with their linked courses and department info (3-Tier Failover)."""
        routines = []
        if is_online():
            try:
                resp = api_client.get(f"{self.api_url}/study-routines", timeout=3.0)
                if resp.status_code == 200:
                    routines = resp.json()
            except Exception as e:
                log_system(f"API request failed for get_all study routines: {e}", "WARNING")

            if not routines:
                try:
                    routines = self._call_read_all("GetAllStudyRoutines")
                except Exception as sp_err:
                    log_system(f"SP GetAllStudyRoutines fallback error: {sp_err}", "WARNING")

        if not routines:
            routines = get_offline_study_routines(dept_id)

        if dept_id:
            routines = [r for r in routines if r.get("department_id") == dept_id]

        for r in routines:
            rid = r.get("id")
            if rid:
                courses = []
                if is_online():
                    try:
                        c_resp = api_client.get(f"{self.api_url}/study-routine-courses/{rid}", timeout=3.0)
                        if c_resp.status_code == 200:
                            courses = c_resp.json()
                    except Exception:
                        pass
                    if not courses:
                        try:
                            courses = self._call_read_all("GetStudyRoutineCourses", (rid,))
                        except Exception:
                            pass
                if not courses:
                    courses = get_offline_study_routine_period_courses(rid)
                r["courses"] = courses
                r["course_ids"] = [c["id"] for c in courses if isinstance(c, dict) and "id" in c]

        return routines

    def get_by_id(self, routine_id: int) -> dict | None:
        """Fetch a single study routine with full course details."""
        routines = self.get_all()
        for r in routines:
            if r.get("id") == routine_id:
                return r
        return None

    def insert(self, data: dict) -> int:
        """Create a new study routine and link default periods/courses (3-Tier Failover)."""
        name_ar = data.get("name_ar", "")
        name_en = data.get("name_en", "")
        dept_id = int(data.get("department_id") or 1)
        sys_id = int(data.get("study_system_id") or 1)
        course_ids = data.get("course_ids") or []

        if not is_online():
            local_id = insert_offline_study_routine(name_ar, name_en, dept_id, sys_id)
            if local_id:
                for stg in range(1, 5):
                    for sem in (1, 2):
                        self.insert_period({"routine_id": local_id, "stage_number": stg, "semester_num": sem})
            log_activity(f"تم إنشاء روتين دراسي جديد (أوفلاين): {name_ar}")
            return local_id or 1

        new_id = None
        try:
            new_id = self._call_write("InsertStudyRoutine", (name_ar, name_en, dept_id, sys_id))
        except Exception as sp_err:
            log_system(f"SP InsertStudyRoutine error: {sp_err}", "WARNING")
            new_id = insert_offline_study_routine(name_ar, name_en, dept_id, sys_id)

        target_id = new_id or 1

        try:
            for stg in range(1, 5):
                for sem in (1, 2):
                    self.insert_period({"routine_id": target_id, "stage_number": stg, "semester_num": sem})
        except Exception as p_err:
            log_system(f"Error auto-creating routine periods: {p_err}", "WARNING")

        log_activity(f"تم إنشاء روتين دراسي جديد: {name_ar}")
        return target_id

    def update(self, routine_id: int, data: dict) -> None:
        """Update an existing study routine header and sync its metadata."""
        name_ar = data.get("name_ar", "")
        name_en = data.get("name_en", "")
        dept_id = int(data.get("department_id") or 1)
        sys_id = int(data.get("study_system_id") or 1)
        course_ids = data.get("course_ids") or []

        update_offline_study_routine(routine_id, name_ar, name_en, dept_id, sys_id)

        if not is_online():
            log_activity(f"تم تعديل الروتين الدراسي (أوفلاين) ID: {routine_id}")
            return

        try:
            payload = {
                "name_ar": name_ar,
                "name_en": name_en,
                "department_id": dept_id,
                "study_system_id": sys_id,
            }
            resp = api_client.put(f"{self.api_url}/study-routines/{routine_id}", json=payload, timeout=3.0)
            if resp.status_code != 200:
                self._call_write("UpdateStudyRoutine", (routine_id, name_ar, name_en, dept_id, sys_id))
        except Exception as e:
            try:
                self._call_write("UpdateStudyRoutine", (routine_id, name_ar, name_en, dept_id, sys_id))
            except Exception as sp_err:
                log_system(f"SP UpdateStudyRoutine error: {sp_err}", "WARNING")

        for cid in course_ids:
            try:
                api_client.post(
                    f"{self.api_url}/study-routine-courses",
                    json={"routine_id": routine_id, "course_id": cid},
                    timeout=3.0
                )
            except Exception:
                try:
                    self._call_write("InsertStudyRoutineCourse", (routine_id, cid))
                except Exception:
                    pass

        log_activity(f"تم تعديل بيانات الروتين الدراسي ID: {routine_id}")

    def delete(self, routine_id: int) -> None:
        """Delete a study routine and its linked period & course entries (3-Tier Failover)."""
        delete_offline_study_routine(routine_id)

        if not is_online():
            log_activity(f"تم حذف الروتين الدراسي (أوفلاين) ID: {routine_id}")
            return

        api_success = False
        try:
            resp = api_client.delete(f"{self.api_url}/study-routines/{routine_id}", timeout=5.0)
            if resp.status_code == 200:
                api_success = True
                log_activity(f"تم حذف الروتين الدراسي ID: {routine_id} عبر API")
        except Exception as e:
            log_system(f"API request failed for delete study routine: {e}", "WARNING")

        if not api_success:
            try:
                self._call_write("DeleteStudyRoutine", (routine_id,))
                log_activity(f"تم حذف الروتين الدراسي ID: {routine_id} عبر SP")
            except Exception as sp_err:
                log_system(f"SP DeleteStudyRoutine error: {sp_err}", "WARNING")

    def get_periods(self, routine_id: int) -> list[dict]:
        """Fetch periods associated with a study routine (3-Tier Failover)."""
        periods = []
        if is_online():
            try:
                periods = self._call_read_all("GetStudyRoutinePeriods", (routine_id,))
            except Exception as e:
                log_system(f"SP GetStudyRoutinePeriods error: {e}", "WARNING")

        if not periods:
            periods = get_offline_study_routine_periods(routine_id)
        return periods

    def get_period_courses(self, period_id: int) -> list[dict]:
        """Fetch courses associated with a routine period (3-Tier Failover)."""
        courses = []
        if is_online():
            try:
                courses = self._call_read_all("GetStudyRoutinePeriodCourses", (period_id,))
            except Exception as e:
                log_system(f"SP GetStudyRoutinePeriodCourses error: {e}", "WARNING")

        if not courses:
            courses = get_offline_study_routine_period_courses(period_id)
        return courses

    def insert_period(self, data: dict) -> int:
        """Add a stage/semester period to a study routine."""
        routine_id = int(data.get("routine_id") or 0)
        stage = int(data.get("stage_number") or 1)
        sem_num = int(data.get("semester_num") or 1)

        local_id = insert_offline_study_routine_period(routine_id, stage, sem_num)

        if not is_online():
            return local_id or 1

        new_id = None
        try:
            new_id = self._call_write("InsertStudyRoutinePeriod", (routine_id, stage, sem_num))
        except Exception as sp_err:
            log_system(f"SP InsertStudyRoutinePeriod error: {sp_err}", "WARNING")

        return new_id or local_id or 1

    def insert_period_course(self, period_id: int, course_id: int) -> None:
        """Assign a course to a routine period."""
        insert_offline_study_routine_period_course(period_id, course_id)

        if is_online():
            try:
                self._call_write("InsertStudyRoutinePeriodCourse", (period_id, course_id))
            except Exception as sp_err:
                log_system(f"SP InsertStudyRoutinePeriodCourse error: {sp_err}", "WARNING")

    def delete_period(self, period_id: int) -> None:
        """Delete a routine period and unassign its courses."""
        delete_offline_study_routine_period(period_id)

        if is_online():
            try:
                self._call_write("DeleteStudyRoutinePeriod", (period_id,))
            except Exception as sp_err:
                log_system(f"SP DeleteStudyRoutinePeriod error: {sp_err}", "WARNING")

    def delete_period_course(self, period_id: int, course_id: int) -> None:
        """Unassign a course from a routine period."""
        delete_offline_study_routine_period_course(period_id, course_id)

        if is_online():
            try:
                self._call_write("DeleteStudyRoutinePeriodCourse", (period_id, course_id))
            except Exception as sp_err:
                log_system(f"SP DeleteStudyRoutinePeriodCourse error: {sp_err}", "WARNING")

    def apply_routine_to_student(self, student_id: int, routine_id: int, academic_year: str = "") -> dict:
        """
        Applies a comprehensive 4-Year Routine to a student:
        1. Reads routine periods and courses across all stages/semesters.
        2. Groups courses by (stage_number, semester_num).
        3. For each stage/semester group:
           - Calculates academic year relative to student's admission year.
           - Creates/finds matching academic_period for the student.
           - Inserts all routine courses into enrollments (score=0.0, passed_round='1').
        """
        routine = self.get_by_id(routine_id) or {}

        sys_id = routine.get("study_system_id", 1)

        # Build comprehensive course map grouped by (stage_number, semester_num)
        courses_by_stage_sem = {}

        # 1. Read period-based courses
        routine_periods = self.get_periods(routine_id) or []
        for p in routine_periods:
            pid = p.get("id") or p.get("period_id")
            stg = int(p.get("stage_number") or 1)
            sem = int(p.get("semester_num") or 1)
            key = (stg, sem)
            if key not in courses_by_stage_sem:
                courses_by_stage_sem[key] = []

            if pid:
                p_courses = self.get_period_courses(pid) or []
                for pc in p_courses:
                    cid = pc.get("course_id") if (isinstance(pc, dict) and pc.get("course_id") is not None) else (pc.get("id") if isinstance(pc, dict) else None)
                    if cid and not any((c.get("id") == cid or c.get("course_id") == cid) for c in courses_by_stage_sem[key]):
                        courses_by_stage_sem[key].append({
                            "id": cid,
                            "course_id": cid,
                            "stage_number": stg,
                            "semester_num": sem
                        })

        # 2. Also check direct header courses if any
        header_courses = routine.get("courses", []) or []
        for c in header_courses:
            cid = c.get("course_id") if (isinstance(c, dict) and c.get("course_id") is not None) else (c.get("id") if isinstance(c, dict) else None)
            stg = int(c.get("stage_number") or 1)
            sem = int(c.get("semester_num") or 1)
            key = (stg, sem)
            if key not in courses_by_stage_sem:
                courses_by_stage_sem[key] = []
            if cid and not any((existing.get("id") == cid or existing.get("course_id") == cid) for existing in courses_by_stage_sem[key]):
                courses_by_stage_sem[key].append({
                    "id": cid,
                    "course_id": cid,
                    "stage_number": stg,
                    "semester_num": sem
                })

        student_repo = StudentRepository()
        st = student_repo.get_by_id(student_id) if hasattr(student_repo, 'get_by_id') else None
        if not st:
            st_list = student_repo.search_students_paginated("", limit=100)
            st = next((s for s in st_list if s.get("student_id") == student_id or s.get("id") == student_id), {})

        target_dept = routine.get("department_id") or st.get("department_id") or 1

        # If no periods/courses found at all, build default 4 stages x 2 semesters
        if not courses_by_stage_sem:
            for stg in range(1, 5):
                for sem in (1, 2):
                    courses_by_stage_sem[(stg, sem)] = []

        # 3. Fallback: If any stage/semester has no assigned courses in routine,
        # fetch catalog courses for student's department and stage
        course_repo = CourseRepository()
        for (stg, sem), c_list in courses_by_stage_sem.items():
            if not c_list:
                dept_courses = course_repo.get_by_dept_stage_system(target_dept, stg, sys_id) or []
                if not dept_courses:
                    all_dept = course_repo.get_by_department(target_dept) or []
                    dept_courses = [c for c in all_dept if safe_cast(c.get("stage_number"), int, 1) == stg]

                for dc in dept_courses:
                    cid = dc.get("id") or dc.get("course_id")
                    if cid and not any((c.get("id") == cid or c.get("course_id") == cid) for c in c_list):
                        c_list.append({
                            "id": cid,
                            "course_id": cid,
                            "stage_number": stg,
                            "semester_num": sem
                        })

        adm_yr_raw = str(st.get("admission_year") or "2024").strip()
        adm_yr = int(adm_yr_raw) if adm_yr_raw.isdigit() else 2024

        period_repo = AcademicPeriodRepository()
        enroll_repo = EnrollmentRepository()
        existing_periods = period_repo.get_by_student(student_id) or []

        # Map existing periods by (stage_number, semester_num)
        period_map = {}
        for p in existing_periods:
            stg_num = p.get("stage_number")
            sem_n = p.get("semester_num")
            if stg_num and sem_n:
                period_map[(int(stg_num), int(sem_n))] = p

        total_added_courses = 0
        periods_affected = 0

        for (stg, sem), c_list in courses_by_stage_sem.items():
            start_yr = adm_yr + (stg - 1)
            calc_year = f"{start_yr}-{start_yr+1}"

            target_period = period_map.get((stg, sem))
            period_created = False
            if not target_period:
                try:
                    period_id = period_repo.insert(
                        student_id=student_id,
                        year=calc_year,
                        sys_id=sys_id,
                        stage=stg,
                        semester_num=sem
                    )
                    target_period = {"id": period_id, "stage_number": stg, "semester_num": sem}
                    period_map[(stg, sem)] = target_period
                    period_created = True
                except Exception as p_err:
                    log_system(f"Failed to create academic period for Stage {stg} Sem {sem}: {p_err}", "WARNING")
                    continue

            pid = target_period["id"]
            existing_enrs = enroll_repo.get_by_period(pid) or []
            existing_cids = {e.get("course_id") for e in existing_enrs if "course_id" in e}

            added_in_period = 0
            for c in c_list:
                cid = c.get("id") or c.get("course_id")
                if cid and cid not in existing_cids:
                    try:
                        enroll_repo.insert(period_id=pid, course_id=cid, score=0.0, is_second=1)
                        total_added_courses += 1
                        added_in_period += 1
                        existing_cids.add(cid)
                    except Exception as err:
                        log_system(f"Failed to add routine course {cid} to period {pid}: {err}", "WARNING")

            if period_created or added_in_period > 0:
                periods_affected += 1

        log_activity(f"تم تطبيق الروتين الشامل ({routine.get('name_ar')}) على الطالب ID: {student_id} — تم إضافة {total_added_courses} مادة عبر {periods_affected} فترة دراسية")
        return {"periods_affected": periods_affected, "added_courses": total_added_courses}


class IssuedCertificateRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            from data.query import get_offline_issued_certificates_report
            return get_offline_issued_certificates_report()
        try:
            resp = api_client.get(f"{self.api_url}/issued-certificates/report", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            from data.query import get_offline_issued_certificates_report
            return get_offline_issued_certificates_report()

    def get_by_student(self, student_id: int) -> list[dict]:
        if not is_online():
            from data.query import get_offline_issued_certificates_by_student
            return get_offline_issued_certificates_by_student(student_id)
        try:
            resp = api_client.get(f"{self.api_url}/issued-certificates/by-student/{student_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            from data.query import get_offline_issued_certificates_by_student
            return get_offline_issued_certificates_by_student(student_id)

    def get_by_id(self, cert_id: int) -> dict | None:
        if not is_online():
            from data.query import get_offline_issued_certificate_by_id
            return get_offline_issued_certificate_by_id(cert_id)
        try:
            resp = api_client.get(f"{self.api_url}/issued-certificates/{cert_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            from data.query import get_offline_issued_certificate_by_id
            return get_offline_issued_certificate_by_id(cert_id)

    def get_report(
        self,
        start_date=None,
        end_date=None,
        dept_id=None,
        template_type=None,
        graduation_year=None,
        study_system_id=None,
        search_text=None
    ) -> list[dict]:
        if not is_online():
            from data.query import get_offline_issued_certificates_report
            return get_offline_issued_certificates_report(
                start_date=start_date,
                end_date=end_date,
                dept_id=dept_id,
                template_type=template_type,
                graduation_year=graduation_year,
                study_system_id=study_system_id,
                search_text=search_text
            )
        try:
            params = {}
            if start_date: params["start_date"] = start_date
            if end_date: params["end_date"] = end_date
            if dept_id is not None and dept_id != 0: params["department_id"] = dept_id
            if template_type: params["template_type"] = template_type
            if graduation_year is not None and graduation_year != 0: params["graduation_year"] = graduation_year
            if study_system_id is not None and study_system_id != 0: params["study_system_id"] = study_system_id
            if search_text: params["search_text"] = search_text
            resp = api_client.get(f"{self.api_url}/issued-certificates/report", params=params, timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            from data.query import get_offline_issued_certificates_report
            return get_offline_issued_certificates_report(
                start_date=start_date,
                end_date=end_date,
                dept_id=dept_id,
                template_type=template_type,
                graduation_year=graduation_year,
                study_system_id=study_system_id,
                search_text=search_text
            )

    def get_latest_number(self) -> str | None:
        if is_online():
            try:
                resp = api_client.get(f"{self.api_url}/issued-certificates/latest-number", timeout=3.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("latest_number"):
                        return data["latest_number"]
            except Exception as e:
                log_system(f"API request latest certificate number failed: {e}", "WARNING")

        from data.query import get_offline_latest_certificate_number
        return get_offline_latest_certificate_number()

    CERT_BLOCK_SIZE = 20

    def ensure_number_block(self) -> None:
        """
        While online, make sure this laptop holds a block of reserved certificate numbers for
        the current year, so certificates printed offline can never repeat a number printed
        on another laptop. Renewed when fewer than 5 numbers are left.
        """
        if not is_online():
            return
        from datetime import datetime as _dt
        from sync_engine import get_cert_number_block, save_cert_number_block, get_device_id
        suffix = _dt.now().strftime("%y")
        block = get_cert_number_block()
        if block and block["year_suffix"] == suffix and block["end_no"] - block["next_no"] + 1 >= 5:
            return
        try:
            resp = api_client.post(
                f"{self.api_url}/certificate-numbers/reserve",
                json={"device_id": get_device_id(), "count": self.CERT_BLOCK_SIZE, "year_suffix": suffix},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                save_cert_number_block(data["year_suffix"], int(data["start_no"]), int(data["end_no"]))
                log_system(f"Reserved certificate numbers {data['start_no']}-{data['end_no']}/{data['year_suffix']} for offline use", "INFO")
            else:
                log_system(f"Certificate number block not reserved ({resp.status_code}): {resp.text[:120]}", "DEBUG")
        except Exception as exc:
            log_system(f"Certificate number block reservation failed: {exc}", "DEBUG")

    def _offline_next_number(self) -> str:
        """Next number when the server cannot be asked: this laptop's reserved block first,
        otherwise one above the highest number this laptop knows for the current year."""
        import re
        from datetime import datetime as _dt
        from sync_engine import get_cert_number_block
        suffix = _dt.now().strftime("%y")
        block = get_cert_number_block()
        if block and block["year_suffix"] == suffix and block["next_no"] <= block["end_no"]:
            return f"{block['next_no']}/{suffix}"
        rows = sqlite_read_all(
            "SELECT certificate_number FROM issued_certificates WHERE certificate_number LIKE ? "
            "UNION ALL SELECT certificate_number FROM local_issued_certificates WHERE certificate_number LIKE ?",
            (f"%/{suffix}", f"%/{suffix}"),
        )
        numbers = [int(m.group(1)) for m in (re.match(r"^\s*(\d+)\s*/", str(r.get("certificate_number") or "")) for r in rows) if m]
        return f"{max(numbers, default=0) + 1}/{suffix}"

    def get_next_number(self) -> str:
        """
        Auto-increments the latest certificate number.
        Handles patterns like '420/44' -> '421/44', '105' -> '106'.
        Defaults to '1' if no previous certificate number exists.
        Offline (or server unreachable): uses this laptop's reserved block (_offline_next_number).
        """
        import re
        latest = None
        if is_online():
            try:
                resp = api_client.get(f"{self.api_url}/issued-certificates/latest-number", timeout=3.0)
                if resp.status_code == 200:
                    latest = resp.json().get("latest_number")
                    if not latest:
                        from datetime import datetime
                        return f"1/{datetime.now().strftime('%y')}"
            except Exception as e:
                log_system(f"API request latest certificate number failed: {e}", "WARNING")
        if latest is None:
            return self._offline_next_number()
        if not latest:
            from datetime import datetime
            curr_year_short = datetime.now().strftime("%y")
            return f"1/{curr_year_short}"

        cleaned = str(latest).strip()
        match = re.match(r"^(\d+)(/.*)?$", cleaned)
        if match:
            num = int(match.group(1)) + 1
            suffix = match.group(2) or ""
            return f"{num}{suffix}"

        # If it ends with digits, e.g. "DOC-420"
        sub_match = re.search(r"(\d+)$", cleaned)
        if sub_match:
            val = int(sub_match.group(1)) + 1
            prefix = cleaned[:sub_match.start(1)]
            return f"{prefix}{val}"

        return f"{cleaned}-1"

    def check_duplicate(self, certificate_number: str, current_student_id: int) -> dict:
        """
        Verifies if a certificate number is already used in the database.
        Returns:
            {"exists": bool, "same_student": bool, "owner_id": int | None, "owner_name": str, "certificate_id": int | None}
        """
        if not certificate_number or not certificate_number.strip():
            return {"exists": False, "same_student": False, "owner_id": None, "owner_name": "", "certificate_id": None}

        num_target = certificate_number.strip().lower()
        records = self.get_report(search_text=certificate_number.strip())
        for r in records:
            cert_num = str(r.get("certificate_number") or "").strip().lower()
            if cert_num == num_target:
                sid = r.get("student_id")
                same = (int(sid) == int(current_student_id)) if sid is not None and current_student_id else False
                name = r.get("student_name_ar") or r.get("full_name_ar") or ""
                cert_id = r.get("certificate_id") or r.get("id")
                return {"exists": True, "same_student": same, "owner_id": sid, "owner_name": name, "certificate_id": cert_id}

        return {"exists": False, "same_student": False, "owner_id": None, "owner_name": "", "certificate_id": None}

    def insert(
        self,
        student_id: int,
        to_title: Optional[str] = "من يهمه الأمر",
        template_type: Optional[str] = "graduation",
        issue_date: Optional[str] = None,
        certificate_number: Optional[str] = None,
        user_id: Optional[int] = None,
        user_name: Optional[str] = None
    ) -> int:
        if not issue_date:
            from datetime import datetime
            issue_date = datetime.now().strftime("%Y-%m-%d")

        payload = {
            "student_id": int(student_id),
            "to_title": str(to_title or "من يهمه الأمر"),
            "template_type": str(template_type or "graduation"),
            "issue_date": str(issue_date),
            "certificate_number": str(certificate_number or "").strip() or None
        }

        new_id = None
        if not is_online():
            from data.query import insert_offline_issued_certificate
            new_id = insert_offline_issued_certificate(
                student_id=payload["student_id"],
                to_title=payload["to_title"],
                template_type=payload["template_type"],
                issue_date=payload["issue_date"],
                certificate_number=payload["certificate_number"]
            )
        else:
            try:
                resp = api_client.post(f"{self.api_url}/issued-certificates", json=payload, timeout=5.0)
                if resp.status_code == 200:
                    res_data = resp.json()
                    new_id = res_data.get("new_id") or res_data.get("inserted_id")
                else:
                    log_system(f"API insert issued certificate warning: {resp.text}", "WARNING")
            except Exception as e:
                log_system(f"API request failed for insert issued certificate: {e}", "WARNING")

            if not new_id:
                from data.query import insert_offline_issued_certificate
                new_id = insert_offline_issued_certificate(
                    student_id=payload["student_id"],
                    to_title=payload["to_title"],
                    template_type=payload["template_type"],
                    issue_date=payload["issue_date"],
                    certificate_number=payload["certificate_number"]
                )

        # A number taken from this laptop's reserved block is now used
        if payload["certificate_number"]:
            from sync_engine import mark_cert_number_used
            mark_cert_number_used(payload["certificate_number"])

        # Log user activity with user_id, user_name, certificate_id, certificate_number
        u_id = user_id if user_id is not None else "—"
        u_name = user_name or "المستخدم"
        c_num = payload["certificate_number"] or "—"
        log_activity(f"المستخدم ID: {u_id} ({u_name}) قام بإصدار وثيقة برقم ID: {new_id}، رقم الوثيقة: {c_num} للطالب ID: {student_id}")

        return new_id or 1

    def update(
        self,
        cert_id: int,
        to_title: Optional[str] = None,
        template_type: Optional[str] = None,
        issue_date: Optional[str] = None,
        certificate_number: Optional[str] = None
    ) -> None:
        payload = {}
        if to_title is not None: payload["to_title"] = to_title
        if template_type is not None: payload["template_type"] = template_type
        if issue_date is not None: payload["issue_date"] = issue_date
        if certificate_number is not None: payload["certificate_number"] = certificate_number

        if not is_online():
            from data.query import update_offline_issued_certificate
            update_offline_issued_certificate(
                cert_id=cert_id,
                to_title=payload.get("to_title"),
                template_type=payload.get("template_type"),
                issue_date=payload.get("issue_date"),
                certificate_number=payload.get("certificate_number")
            )
            return

        try:
            resp = api_client.put(f"{self.api_url}/issued-certificates/{cert_id}", json=payload, timeout=5.0)
            if resp.status_code != 200:
                log_system(f"API update issued certificate warning: {resp.text}", "WARNING")
                from data.query import update_offline_issued_certificate
                update_offline_issued_certificate(
                    cert_id=cert_id,
                    to_title=payload.get("to_title"),
                    template_type=payload.get("template_type"),
                    issue_date=payload.get("issue_date"),
                    certificate_number=payload.get("certificate_number")
                )
        except Exception as e:
            log_system(f"API request failed for update issued certificate: {e}", "WARNING")
            from data.query import update_offline_issued_certificate
            update_offline_issued_certificate(
                cert_id=cert_id,
                to_title=payload.get("to_title"),
                template_type=payload.get("template_type"),
                issue_date=payload.get("issue_date"),
                certificate_number=payload.get("certificate_number")
            )

    def delete(self, cert_id: int) -> None:
        if not is_online():
            from data.query import delete_offline_issued_certificate
            delete_offline_issued_certificate(cert_id)
            return
        try:
            resp = api_client.delete(f"{self.api_url}/issued-certificates/{cert_id}", timeout=5.0)
            if resp.status_code != 200:
                log_system(f"API delete failed: {resp.text}", "WARNING")
                from data.query import delete_offline_issued_certificate
                delete_offline_issued_certificate(cert_id)
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            from data.query import delete_offline_issued_certificate
            delete_offline_issued_certificate(cert_id)


from repositories.auth_repository import AuthRepository