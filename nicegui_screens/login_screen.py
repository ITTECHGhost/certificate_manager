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
        self.error_box = None
        self.build_ui()

    def build_ui(self) -> None:
        """Centred sign-in card on a plain background; theme toggle in the corner."""
        from nicegui_ui.ui_theme import set_dark_mode, inject_global_styles
        from nicegui_ui.state import app_session
        self.dark_mode = ui.dark_mode()
        app_session.load()
        app_session.apply_theme_mode()

        ui.query(".nicegui-content").classes("p-0 m-0")
        ui.query("body").classes("m-0 p-0 overflow-hidden")

        inject_global_styles()

        # Explicitly allow unsafe-eval for Vue's runtime compiler in PyWebView
        ui.add_head_html('<meta http-equiv="Content-Security-Policy" content="default-src * \'unsafe-inline\' \'unsafe-eval\' data: blob:; script-src * \'unsafe-inline\' \'unsafe-eval\'; style-src * \'unsafe-inline\';">')

        with ui.column().classes("app-login-right w-full h-screen items-center justify-center p-4 gap-5 relative overflow-auto no-wrap"):
            # Theme toggle in the corner (inline-end = left in RTL)
            with ui.element("div").classes("absolute top-4 left-4"):
                def _toggle():
                    set_dark_mode(not bool(self.dark_mode.value), self.dark_mode)
                    theme_btn.props(f"icon={'light_mode' if self.dark_mode.value else 'dark_mode'}")
                    theme_btn.tooltip("الوضع الفاتح" if self.dark_mode.value else "الوضع الداكن")

                theme_btn = UI.icon_button(
                    "light_mode" if self.dark_mode.value else "dark_mode",
                    "تبديل الوضع الفاتح / الداكن",
                    on_click=_toggle,
                ).classes("app-theme-toggle")

            logo_src = self._find_logo()
            if logo_src:
                ui.image(logo_src).classes("app-login-logo w-[112px] h-[112px] object-contain")

            with UI.login_card():
                with ui.column().classes("w-full items-center gap-1 text-center"):
                    ui.label("تسجيل الدخول").classes("app-login-title")
                    ui.label("أدخل اسم المستخدم وكلمة المرور").classes("app-login-subtitle")

                self.username_input = UI.input("اسم المستخدم").props('autofocus autocomplete="username"')
                self.password_input = UI.input(
                    "كلمة المرور", password=True, password_toggle_button=True
                ).props('autocomplete="current-password"')
                # Enter in either field submits
                self.username_input.on("keydown.enter", self.handle_login)
                self.password_input.on("keydown.enter", self.handle_login)

                # Error: what went wrong and what to do next
                with ui.row().classes("w-full items-start gap-2 no-wrap app-chip--danger rounded-lg p-3") as self.error_box:
                    ui.icon("error_outline", size="20px").classes("app-text-danger shrink-0")
                    self.error_label = ui.label("").classes("app-text-danger text-sm")
                self.error_box.set_visibility(False)

                UI.primary_button("تسجيل الدخول", on_click=self.handle_login).classes("w-full")

    def _find_logo(self) -> str | None:
        """College logo from the settings, else the bundled one."""
        try:
            s_data = SettingsRepository().get_settings() or {}
            for key in ("college_logo_path", "univ_logo_path"):
                path = s_data.get(key)
                if path and os.path.exists(path):
                    return path
        except Exception:
            pass
        for path in ("assets/college_logo.png", "assets/csit.png"):
            if os.path.exists(path):
                return path
        return None

    def _show_error(self, msg: str) -> None:
        if self.error_label:
            self.error_label.set_text(msg)
            self.error_box.set_visibility(True)

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

        ui.notify(f"مرحباً بك {user_record.get('name_ar', username)}", type="positive")
        ui.navigate.to("/dashboard")

    def _ask_new_password(self, user_record: dict, username: str) -> None:
        """Forced password change after logging in with a temporary password."""
        with ui.dialog().props("persistent") as dialog, UI.login_card():
            ui.label("تغيير كلمة المرور مطلوب").classes("text-base font-bold app-text-primary")
            ui.label("تم تعيين كلمة مرور مؤقتة لحسابك. اختر كلمة مرور جديدة للمتابعة.").classes("app-caption")
            new_inp = ui.input("كلمة المرور الجديدة", password=True, password_toggle_button=True).classes("w-full")
            conf_inp = ui.input("تأكيد كلمة المرور", password=True).classes("w-full")

            def _save():
                new_pwd = new_inp.value or ""
                if len(new_pwd) < 4:
                    ui.notify("كلمة المرور قصيرة جداً (4 أحرف على الأقل)", type="warning")
                    return
                if new_pwd != (conf_inp.value or ""):
                    ui.notify("كلمتا المرور غير متطابقتين", type="warning")
                    return
                if self.password_input and new_pwd == (self.password_input.value or ""):
                    ui.notify("اختر كلمة مرور مختلفة عن المؤقتة", type="warning")
                    return
                try:
                    result = PersonnelRepository().set_password(int(user_record["id"]), new_pwd, must_change=False)
                except Exception as exc:
                    ui.notify(f"تعذر حفظ كلمة المرور: {exc}", type="negative")
                    return
                dialog.close()
                if result == "queued":
                    ui.notify("تم حفظ كلمة المرور على هذا الجهاز وستُرسل للسيرفر عند الاتصال",
                              type="info", timeout=8000)
                user_record["must_change_password"] = False
                self._finish_login(user_record, username)

            conf_inp.on("keydown.enter", _save)
            with ui.row().classes("app-dialog-actions"):
                UI.ghost_button("إلغاء", on_click=dialog.close)
                UI.primary_button("حفظ ومتابعة", on_click=_save)
        dialog.open()

    def handle_login(self, e=None) -> None:
        """Validates credentials via PersonnelRepository and updates session state."""
        if not self.username_input or not self.password_input:
            return

        username = (self.username_input.value or "").strip()
        password = self.password_input.value or ""

        if not username or not password:
            self._show_error("أدخل اسم المستخدم وكلمة المرور.")
            return

        try:
            personnel_repo = PersonnelRepository()
            user_record = personnel_repo.authenticate(username, password)

            if user_record:
                if self.error_box:
                    self.error_box.set_visibility(False)

                if user_record.get("must_change_password"):
                    # A temporary password given by an admin: choose your own before continuing
                    self._ask_new_password(user_record, username)
                    return
                self._finish_login(user_record, username)
            else:
                self._show_error("اسم المستخدم أو كلمة المرور غير صحيحة. تأكد منهما وأعد المحاولة.")

        except Exception as exc:
            log.warning(f"[LoginScreen] Authentication Error: {exc}")
            self._show_error("تعذر تسجيل الدخول. تحقق من الاتصال بالشبكة وأعد المحاولة.")
