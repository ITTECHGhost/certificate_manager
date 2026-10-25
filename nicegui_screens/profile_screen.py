# =============================================================================
# nicegui_screens/profile_screen.py — Dedicated User Profile & Account Screen
# =============================================================================

from typing import Callable, Optional
import logging
from nicegui import ui
from nicegui_ui.ui_components import UI
from nicegui_ui.state import app_session
from data.repositories import PersonnelRepository, RoleRepository
from sync_engine import is_online

log = logging.getLogger(__name__)


class ProfileScreen:
    """
    Dedicated Profile & Account screen accessible to ALL authenticated users.
    Displays user identity, role, online status, editable personal & job metadata,
    and secure password update capabilities.
    """

    def __init__(self, on_navigate: Optional[Callable[[str], None]] = None, embedded: bool = False):
        self.on_navigate = on_navigate
        self.embedded = embedded
        self.p_repo = PersonnelRepository()
        self.role_repo = RoleRepository()
        self.session = app_session
        self.emp_id = getattr(self.session, "emp_id", 1)

        self._build_ui()

    def _build_ui(self) -> None:
        user_data = {}
        try:
            user_data = self.p_repo.get_by_id(self.emp_id) or {}
        except Exception as e:
            log.warning(f"[ProfileScreen] Failed to fetch profile user data: {e}")

        cur_name_ar = str(user_data.get("name_ar") or self.session.name_ar or "")
        cur_name_en = str(user_data.get("name_en") or self.session.name_en or "")
        cur_username = str(user_data.get("username") or self.session.username or "")
        cur_title_ar = str(user_data.get("academic_title_ar") or "")
        cur_title_en = str(user_data.get("academic_title_en") or "")
        cur_resp_ar = str(user_data.get("responsibility_ar") or "")
        cur_resp_en = str(user_data.get("responsibility_en") or "")

        # Resolve detailed role definition
        access = self.session.get_access()
        role_id = access.get("role_id") or self.session.role
        role_label_ar = access.get("role_name_ar") or role_id
        role_label_en = access.get("role_name_en") or role_id

        with ui.column().classes("w-full max-w-5xl mx-auto gap-6 pb-12"):
            # Header Navigation Row (Visible when not embedded in settings tab)
            if not self.embedded:
                with ui.row().classes("w-full items-center justify-between pb-3 border-b border-[var(--border-default)] shrink-0 gap-4 flex-wrap"):
                    with ui.row().classes("items-center gap-3"):
                        with ui.element("div").classes("w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-center"):
                            ui.icon("account_circle", size="sm").classes("text-blue-400")

                        with ui.column().classes("gap-0"):
                            ui.label("الملف الشخصي والحساب — Profile & Account").classes("text-lg font-bold app-text-primary")
                            ui.label("إدارة بياناتك الشخصية والوظيفية وكلمة المرور الخاصة بك.").classes("text-xs app-text-muted")

                    if self.on_navigate:
                        UI.secondary_button(
                            "← العودة إلى لوحة التحكم / Back to Dashboard",
                            icon="arrow_forward",
                            on_click=lambda: self.on_navigate("home")
                        ).classes("text-xs px-4 py-2 font-bold shadow-sm")

            with UI.card().classes("w-full p-6 gap-6 shadow-md"):
                if self.embedded:
                    UI.card_header("الملف الشخصي والحساب — Profile & Account", "account_circle", icon_css="stat-text-blue")

                # 1. Identity Header Banner
                with ui.row().classes("w-full items-center justify-between p-4 bg-[var(--bg-main)] rounded-2xl border border-[var(--border-default)] flex-wrap gap-4"):
                    with ui.row().classes("items-center gap-4"):
                        with ui.element("div").classes("w-14 h-14 rounded-2xl bg-blue-500/15 border border-blue-500/30 flex items-center justify-center shrink-0"):
                            ui.icon("badge", size="md").classes("text-blue-400")
                        with ui.column().classes("gap-1"):
                            ui.label(cur_name_ar or cur_username).classes("text-lg font-bold app-text-primary")
                            with ui.row().classes("items-center gap-2 flex-wrap"):
                                ui.label(f"@{cur_username}").classes("text-xs font-mono app-text-muted")
                                ui.label("•").classes("text-xs app-text-muted")
                                ui.label(f"الصلاحية: {role_label_ar} ({role_label_en})").classes(
                                    "text-xs font-semibold px-2.5 py-0.5 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20"
                                )
                    UI.status_badge(online=is_online())

                # 2. Editable User Information Form
                with ui.column().classes("w-full gap-4 mt-2"):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("edit_note", size="xs").classes("text-blue-400")
                        ui.label("تعديل البيانات الشخصية والوظيفية / Edit Personal & Job Info").classes("text-xs font-bold app-text-primary")

                    with ui.grid(columns=2).classes("w-full gap-4"):
                        self.prof_name_ar_input = UI.text_input("الاسم الكامل بالعربية / Full Name (AR)", value=cur_name_ar)
                        self.prof_name_en_input = UI.text_input("الاسم الكامل بالإنكليزية / Full Name (EN)", value=cur_name_en)
                        self.prof_title_ar_input = UI.text_input("اللقب العلمي (عربي) / Academic Title (AR)", value=cur_title_ar)
                        self.prof_title_en_input = UI.text_input("اللقب العلمي (إنكليزي) / Academic Title (EN)", value=cur_title_en)
                        self.prof_resp_ar_input = UI.text_input("المنصب / الصفة الوظيفية (عربي) / Responsibility (AR)", value=cur_resp_ar)
                        self.prof_resp_en_input = UI.text_input("المنصب / الصفة الوظيفية (إنكليزي) / Responsibility (EN)", value=cur_resp_en)
                        self.prof_username_input = UI.text_input("اسم المستخدم لتسجيل الدخول / Username", value=cur_username)
                        self.prof_role_display = UI.text_input("نوع الصلاحية / Role", value=f"{role_label_ar} — {role_id}")
                        self.prof_role_display.props("readonly")

                # 3. Change Password Subsection
                with ui.column().classes("w-full gap-3 p-4 bg-[var(--bg-main)] rounded-2xl border border-[var(--border-default)] mt-2"):
                    with ui.row().classes("items-center justify-between w-full flex-wrap gap-2"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("lock", size="xs").classes("text-amber-400")
                            ui.label("تغيير كلمة المرور / Change Password").classes("text-xs font-bold app-text-primary")
                        ui.label("(اترك الحقول فارغة إذا كنت لا ترغب بتغيير كلمة المرور)").classes("text-[11px] app-text-muted italic")

                    with ui.grid(columns=2).classes("w-full gap-4"):
                        self.prof_new_pass_input = UI.text_input(
                            "كلمة المرور الجديدة / New Password",
                            placeholder="أدخل كلمة المرور الجديدة"
                        ).props("type=password")
                        self.prof_confirm_pass_input = UI.text_input(
                            "تأكيد كلمة المرور / Confirm Password",
                            placeholder="أعد إدخال كلمة المرور للتأكيد"
                        ).props("type=password")

                # 4. Save Button
                with ui.row().classes("w-full justify-end items-center pt-3 border-t border-[var(--border-default)] mt-2"):
                    UI.success_button(
                        "حفظ بيانات الحساب / Save Profile",
                        icon="save",
                        on_click=self._save_profile_data
                    ).classes("px-6 py-2.5 text-xs font-bold shadow-md")

    def _save_profile_data(self) -> None:
        try:
            name_ar = (self.prof_name_ar_input.value if self.prof_name_ar_input else "").strip()
            name_en = (self.prof_name_en_input.value if self.prof_name_en_input else "").strip()
            username = (self.prof_username_input.value if self.prof_username_input else "").strip()
            title_ar = (self.prof_title_ar_input.value if self.prof_title_ar_input else "").strip()
            title_en = (self.prof_title_en_input.value if self.prof_title_en_input else "").strip()
            resp_ar = (self.prof_resp_ar_input.value if self.prof_resp_ar_input else "").strip()
            resp_en = (self.prof_resp_en_input.value if self.prof_resp_en_input else "").strip()

            if not name_ar or not username:
                ui.notify("يرجى ملء الاسم بالعربية واسم المستخدم! / Name and Username are required", type="warning")
                return

            new_pwd = (self.prof_new_pass_input.value if self.prof_new_pass_input else "").strip()
            conf_pwd = (self.prof_confirm_pass_input.value if self.prof_confirm_pass_input else "").strip()

            if new_pwd:
                if len(new_pwd) < 3:
                    ui.notify("كلمة المرور يجب أن لا تقل عن 3 أحرف! / Password too short", type="warning")
                    return
                if new_pwd != conf_pwd:
                    ui.notify("كلمة المرور وتأكيدها غير متطابقين! / Passwords do not match", type="warning")
                    return

            cur_rec = self.p_repo.get_by_id(self.emp_id) or {}
            payload = {
                "name_ar": name_ar,
                "name_en": name_en,
                "academic_title_ar": title_ar,
                "academic_title_en": title_en,
                "responsibility_ar": resp_ar,
                "responsibility_en": resp_en,
                "display_order": cur_rec.get("display_order", 0),
                "username": username,
                "personnel_role": cur_rec.get("personnel_role", getattr(self.session, "role", "user")),
                "university_settings_id": cur_rec.get("university_settings_id", 1),
                "is_active": cur_rec.get("is_active", 1),
            }
            from sync_engine import is_online
            if is_online():
                self.p_repo.update(self.emp_id, payload)
            elif not new_pwd:
                ui.notify("تعديل بيانات الحساب يتطلب الاتصال بالسيرفر / Profile changes need a server connection",
                          type="warning")
                return

            if new_pwd:
                # Works offline too: saved on this laptop and sent to the server at the next sync
                pwd_result = self.p_repo.set_password(self.emp_id, new_pwd, must_change=False)
                if pwd_result == "queued":
                    ui.notify("تم حفظ كلمة المرور على هذا الجهاز وستُرسل للسيرفر عند الاتصال / "
                              "Password saved on this PC; sent to the server when online", type="info", timeout=8000)

            self.session.name_ar = name_ar
            self.session.name_en = name_en
            self.session.username = username
            self.session.save()

            if self.prof_new_pass_input:
                self.prof_new_pass_input.value = ""
            if self.prof_confirm_pass_input:
                self.prof_confirm_pass_input.value = ""

            ui.notify("تم حفظ وتحديث بيانات حسابك بنجاح! / Profile updated successfully!", type="positive")
        except Exception as exc:
            log.error(f"[ProfileScreen] Error saving profile: {exc}", exc_info=True)
            ui.notify(f"خطأ أثناء حفظ الحساب: {exc}", type="negative")
