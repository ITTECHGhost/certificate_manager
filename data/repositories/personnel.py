# =============================================================================
# data/repositories/personnel.py — Module 4: Personnel, Permissions and Roles (RBAC)
# =============================================================================

from .base import *
from .departments import DepartmentRepository


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
