import logging
log = logging.getLogger(__name__)

# =============================================================================
# nicegui_screens/login_screen.py — NiceGUI Authentication Login Screen
#
# Visual styling: CSS hook classes (app-*) from theme.css
# This file contains ONLY structural layout classes (w-*, h-*, p-*, gap-*, flex, etc.)
# =============================================================================

import os
from nicegui import ui
from data.repositories import PersonnelRepository, SettingsRepository
from nicegui_ui.ui_components import UI


class LoginScreen:
    """
    NiceGUI Login Screen built with the UI component factory.
    Features a two-column split layout (Logo on left, Login Card on right),
    theme-aware inputs via CSS custom properties, auto OS theme detection,
    and instant light/dark mode switching.
    """

    def __init__(self, on_login_success=None) -> None:
        self.on_login_success = on_login_success
        self.username_input = None
        self.password_input = None
        self.error_label = None
        self.build_ui()

    def build_ui(self) -> None:
        """Renders the two-column split login layout using UI component factory."""
        from nicegui_ui.ui_theme import is_windows_dark_mode, set_dark_mode, inject_global_styles, set_accent
        from nicegui_ui.state import app_session
        self.dark_mode = ui.dark_mode()
        app_session.load()
        app_session.apply_theme_mode()

        # 1. Reset container padding & inject global styles
        ui.query(".nicegui-content").classes("p-0 m-0")
        ui.query("body").classes("m-0 p-0 overflow-hidden")

        inject_global_styles()
        
        # Explicitly allow unsafe-eval for Vue's runtime compiler in PyWebView
        ui.add_head_html('<meta http-equiv="Content-Security-Policy" content="default-src * \'unsafe-inline\' \'unsafe-eval\' data: blob:; script-src * \'unsafe-inline\' \'unsafe-eval\'; style-src * \'unsafe-inline\';">')

        # 2. Main 2-Column Split Container (Login Card on Right, Logo on Left in RTL)
        with ui.row().classes("w-full h-screen flex-nowrap m-0 p-0 gap-0"):

            # --- RIGHT COLUMN (in RTL): Login Card Form Area ---
            with ui.column().classes(
                "app-login-right w-1/2 md:w-2/5 h-full items-center justify-center p-6 relative"
            ):
                # The Card Container loaded from global UI factory
                with UI.login_card():
                    # Top User Badge Icon (Offset)
                    with ui.element("div").classes(
                        "app-avatar-badge w-16 h-16 rounded-2xl border "
                        "flex items-center justify-center shadow-md avatar-offset"
                    ):
                        with ui.element("div").classes(
                            "app-avatar-inner w-12 h-12 rounded-xl flex items-center justify-center"
                        ):
                            ui.icon("person_outline", size="sm").classes("app-avatar-icon")

                    # Title & Subtitle
                    with ui.column().classes("w-full items-center gap-1 text-center mt-2"):
                        ui.label("تسجيل الدخول / SYSTEM LOGIN").classes(
                            "app-login-title text-[1.2rem] font-bold tracking-wide"
                        )
                        ui.label("يرجى إدخال بيانات الاعتماد الخاصة بك للوصول").classes(
                            "app-login-subtitle text-[11px] font-bold"
                        )
                        ui.label("Enter credentials to access the system").classes(
                            "app-login-subtitle text-[11px] font-medium -mb-0.5"
                        )

                    # Username Input Group
                    with ui.column().classes("w-full gap-1 mt-3"):
                        with ui.row().classes("w-full justify-between items-end px-1"):
                            ui.label("اسم المستخدم").classes("app-text-secondary text-xs font-bold")
                            ui.label("Username").classes("app-text-muted text-xs font-medium")

                        self.username_input = ui.input(
                            placeholder="أدخل اسم المستخدم / Enter Username"
                        ).classes(
                            "w-full app-input"
                        ).props(
                            'outlined dense input-class="font-semibold text-right"'
                        )
                        with self.username_input.add_slot('prepend'):
                            ui.icon('person_outline', size='sm').classes("app-text-faint ml-1")
                        self.username_input.on('keydown.enter', self.handle_login)

                    # Password Input Group
                    with ui.column().classes("w-full gap-1"):
                        with ui.row().classes("w-full justify-between items-end px-1"):
                            ui.label("كلمة المرور").classes("app-text-secondary text-xs font-bold")
                            ui.label("Password").classes("app-text-muted text-xs font-medium")

                        self.password_input = ui.input(
                            placeholder="أدخل كلمة المرور / Enter Password",
                            password=True,
                            password_toggle_button=True
                        ).classes(
                            "w-full app-input"
                        ).props(
                            'outlined dense input-class="font-semibold text-right"'
                        )
                        with self.password_input.add_slot('prepend'):
                            ui.icon('key', size='sm').classes("app-text-faint ml-1")
                        self.password_input.on('keydown.enter', self.handle_login)

                    # Error Feedback Label
                    self.error_label = ui.label("").classes(
                        "app-text-error text-xs text-center w-full font-medium"
                    )
                    self.error_label.set_visibility(False)

                    # Primary Sign-In Button
                    with ui.button(color=None, on_click=self.handle_login).classes(
                        "app-btn-primary w-full text-sm py-3 rounded-xl font-bold "
                        "normal-case mt-2 cursor-pointer flex-row justify-between px-6"
                    ):
                        ui.label("تسجيل الدخول / SIGN IN")
                        ui.icon("arrow_back", size="sm")

                # Bottom Actions (Theme Toggle)
                with ui.row().classes("w-[440px] max-w-full justify-end items-center mt-6 px-2"):
                    with ui.row().classes(
                        "app-theme-toggle gap-2 items-center px-3 py-1.5 rounded-full border shadow-sm"
                    ):
                        ui.icon("light_mode", size="xs").classes("app-text-faint")
                        ui.switch(
                            on_change=lambda e: set_dark_mode(e.value, self.dark_mode)
                        ).props("dense size=sm").bind_value(self.dark_mode, 'value')
                        ui.icon("dark_mode", size="xs").classes("app-text-faint")

            # --- LEFT COLUMN (in RTL): University Logo Area ---
            with ui.column().classes(
                "app-login-bg w-1/2 md:w-3/5 h-full items-center justify-center p-8"
            ):
                logo_src = None
                try:
                    from data.repositories import SettingsRepository
                    s_data = SettingsRepository().get_settings() or {}
                    col_logo = s_data.get("college_logo_path")
                    univ_logo = s_data.get("univ_logo_path")
                    if col_logo and os.path.exists(col_logo):
                        logo_src = col_logo
                    elif univ_logo and os.path.exists(univ_logo):
                        logo_src = univ_logo
                except Exception:
                    pass

                if not logo_src:
                    if os.path.exists("assets/college_logo.png"):
                        logo_src = "assets/college_logo.png"
                    elif os.path.exists("assets/csit.png"):
                        logo_src = "assets/csit.png"

                if logo_src:
                    ui.image(logo_src).classes(
                        "app-login-logo w-[340px] max-w-full h-auto object-contain"
                    )
                else:
                    ui.label("UNIVERSITY LOGO").classes(
                        "app-text-faint text-4xl font-extrabold tracking-wider text-center"
                    )

    def _toggle_theme(self, is_dark: bool) -> None:
        """Explicitly enables/disables dark mode."""
        if is_dark:
            self.dark_mode.enable()
        else:
            self.dark_mode.disable()


    def _finish_login(self, user_record: dict, username: str) -> None:
        from nicegui_ui.state import app_session
        user_id = user_record.get("id", 1)

        # Login user session and initialize user appearance preferences
        app_session.login_user(user_id, user_record)

        if self.on_login_success:
            self.on_login_success(user_record)

        ui.notify(f"مرحباً بك {user_record.get('name_ar', username)} / Welcome!", type="positive")
        ui.navigate.to("/dashboard")

    def _ask_new_password(self, user_record: dict, username: str) -> None:
        """Forced password change after logging in with a temporary password."""
        with ui.dialog().props("persistent") as dialog, UI.login_card():
            ui.label("تغيير كلمة المرور مطلوب / Password change required").classes("text-base font-bold app-text-primary")
            ui.label(
                "تم تعيين كلمة مرور مؤقتة لحسابك. اختر كلمة مرور جديدة للمتابعة. "
                "Your password was set by an administrator. Choose a new one to continue."
            ).classes("text-xs app-text-muted")
            new_inp = ui.input("كلمة المرور الجديدة / New password", password=True, password_toggle_button=True).classes("w-full")
            conf_inp = ui.input("تأكيد كلمة المرور / Confirm password", password=True).classes("w-full")

            def _save():
                new_pwd = new_inp.value or ""
                if len(new_pwd) < 4:
                    ui.notify("كلمة المرور قصيرة جداً (4 أحرف على الأقل) / At least 4 characters", type="warning")
                    return
                if new_pwd != (conf_inp.value or ""):
                    ui.notify("كلمتا المرور غير متطابقتين / Passwords do not match", type="warning")
                    return
                if self.password_input and new_pwd == (self.password_input.value or ""):
                    ui.notify("اختر كلمة مرور مختلفة عن المؤقتة / Choose a different password", type="warning")
                    return
                try:
                    result = PersonnelRepository().set_password(int(user_record["id"]), new_pwd, must_change=False)
                except Exception as exc:
                    ui.notify(f"تعذر حفظ كلمة المرور: {exc}", type="negative")
                    return
                dialog.close()
                if result == "queued":
                    ui.notify("تم حفظ كلمة المرور على هذا الجهاز وستُرسل للسيرفر عند الاتصال / Saved on this PC; sent to the server when online",
                              type="info", timeout=8000)
                user_record["must_change_password"] = False
                self._finish_login(user_record, username)

            with ui.row().classes("w-full justify-end gap-2 pt-2"):
                ui.button("إلغاء / Cancel", on_click=dialog.close).props("flat")
                ui.button("حفظ ومتابعة / Save and continue", icon="lock_reset", on_click=_save).props("color=primary")
        dialog.open()

    def handle_login(self, e=None) -> None:
        """Validates credentials via PersonnelRepository and updates session state."""
        if not self.username_input or not self.password_input:
            return

        username = (self.username_input.value or "").strip()
        password = self.password_input.value or ""

        if not username or not password:
            msg = "يرجى إدخال اسم المستخدم وكلمة المرور / Please enter username and password"
            if self.error_label:
                self.error_label.set_text(msg)
                self.error_label.set_visibility(True)
            ui.notify(msg, type="warning")
            return

        try:
            personnel_repo = PersonnelRepository()
            user_record = personnel_repo.authenticate(username, password)

            if user_record:
                if self.error_label:
                    self.error_label.set_visibility(False)
                
                if user_record.get("must_change_password"):
                    # A temporary password given by an admin: choose your own before continuing
                    self._ask_new_password(user_record, username)
                    return
                self._finish_login(user_record, username)
            else:
                msg = "اسم المستخدم أو كلمة المرور غير صحيحة / Invalid username or password"
                if self.error_label:
                    self.error_label.set_text(msg)
                    self.error_label.set_visibility(True)
                ui.notify(msg, type="negative")

        except Exception as exc:
            log.warning(f"[LoginScreen] Authentication Error: {exc}")
            msg = "خطأ في عملية المصادقة / Authentication failed. Check connection."
            if self.error_label:
                self.error_label.set_text(msg)
                self.error_label.set_visibility(True)
            ui.notify(msg, type="negative")
