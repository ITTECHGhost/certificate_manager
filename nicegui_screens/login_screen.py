# =============================================================================
# nicegui_screens/login_screen.py — NiceGUI Authentication Login Screen
#
# Visual styling: CSS hook classes (app-*) from theme.css
# This file contains ONLY structural layout classes (w-*, h-*, p-*, gap-*, flex, etc.)
# =============================================================================

import os
from nicegui import ui
from db import get_connection
from data.repositories import AuthRepository
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
        set_dark_mode(is_windows_dark_mode())
        set_accent(app_session.accent_color)

        # 1. Reset container padding & inject global styles
        ui.query(".nicegui-content").classes("p-0 m-0")
        ui.query("body").classes("m-0 p-0 overflow-hidden")

<<<<<<< HEAD
        # 1. Reset container padding & set background to adapt to theme
        ui.query(".nicegui-content").classes("p-0 m-0 bg-slate-50 dark:bg-[#0f172a] transition-colors duration-500")
        ui.query("body").classes("m-0 p-0 overflow-hidden bg-slate-50 dark:bg-[#0f172a] transition-colors duration-500")
        

=======
>>>>>>> 9562a1d23cd6479a6a3565da19e2625b4fc10329
        inject_global_styles()
        
        # Explicitly allow unsafe-eval for Vue's runtime compiler in PyWebView
        ui.add_head_html('<meta http-equiv="Content-Security-Policy" content="default-src * \'unsafe-inline\' \'unsafe-eval\' data: blob:; script-src * \'unsafe-inline\' \'unsafe-eval\'; style-src * \'unsafe-inline\';">')

        # 2. Main 2-Column Split Container
        with ui.row().classes("w-full h-screen flex-nowrap m-0 p-0 gap-0"):

            # --- LEFT COLUMN: University Logo Area ---
            with ui.column().classes(
                "app-login-bg w-1/2 md:w-3/5 h-full items-center justify-center p-8"
            ):
                if os.path.exists("csit.png"):
<<<<<<< HEAD
                    ui.image("csit.png").classes("w-[340px] max-w-full h-auto object-contain drop-shadow-xl dark:drop-shadow-[0_10px_30px_rgba(0,137,255,0.6)]")
=======
                    ui.image("csit.png").classes(
                        "app-login-logo w-[340px] max-w-full h-auto object-contain"
                    )
>>>>>>> 9562a1d23cd6479a6a3565da19e2625b4fc10329
                else:
                    ui.label("UNIVERSITY LOGO").classes(
                        "app-text-faint text-4xl font-extrabold tracking-wider text-center"
                    )

            # --- RIGHT COLUMN: Login Card Form Area ---
            with ui.column().classes(
<<<<<<< HEAD
                "w-1/2 md:w-2/5 h-full items-center justify-center login-right-col p-6 transition-colors duration-500 relative"
=======
                "app-login-right w-1/2 md:w-2/5 h-full items-center justify-center p-6 relative"
>>>>>>> 9562a1d23cd6479a6a3565da19e2625b4fc10329
            ):
                # The Card Container loaded from global UI factory
                with UI.login_card():
                    # Top User Badge Icon (Offset)
                    with ui.element("div").classes(
<<<<<<< HEAD
                        "w-16 h-16 rounded-2xl avatar-badge border "
                        "flex items-center justify-center shadow-md avatar-offset"
                    ):
                        with ui.element("div").classes("w-12 h-12 rounded-xl avatar-inner flex items-center justify-center"):
                            ui.icon("person_outline", size="sm").classes("login-badge-icon")
=======
                        "app-avatar-badge w-16 h-16 rounded-2xl border "
                        "flex items-center justify-center shadow-md avatar-offset"
                    ):
                        with ui.element("div").classes(
                            "app-avatar-inner w-12 h-12 rounded-xl flex items-center justify-center"
                        ):
                            ui.icon("person_outline", size="sm").classes("app-avatar-icon")
>>>>>>> 9562a1d23cd6479a6a3565da19e2625b4fc10329

                    # Title & Subtitle
                    with ui.column().classes("w-full items-center gap-1 text-center mt-2"):
                        ui.label("SYSTEM LOGIN / تسجيل الدخول").classes(
<<<<<<< HEAD
                            "text-[1.2rem] font-bold login-title tracking-wide"
                        )
                        ui.label("Enter credentials to access the system").classes(
                            "text-[11px] font-medium login-subtitle -mb-0.5"
                        )
                        ui.label("يرجى إدخال بيانات الاعتماد الخاصة بك للوصول").classes(
                            "text-[11px] font-medium login-subtitle"
=======
                            "app-login-title text-[1.2rem] font-bold tracking-wide"
                        )
                        ui.label("Enter credentials to access the system").classes(
                            "app-login-subtitle text-[11px] font-medium -mb-0.5"
                        )
                        ui.label("يرجى إدخال بيانات الاعتماد الخاصة بك للوصول").classes(
                            "app-login-subtitle text-[11px] font-medium"
>>>>>>> 9562a1d23cd6479a6a3565da19e2625b4fc10329
                        )

                    # Username Input Group
                    with ui.column().classes("w-full gap-1 mt-3"):
                        with ui.row().classes("w-full justify-between items-end px-1"):
<<<<<<< HEAD
                            ui.label("Username").classes("text-xs login-label-en font-medium")
                            ui.label("اسم المستخدم").classes("text-xs font-bold login-label-ar")
                        
=======
                            ui.label("Username").classes("app-text-muted text-xs font-medium")
                            ui.label("اسم المستخدم").classes("app-text-secondary text-xs font-bold")

>>>>>>> 9562a1d23cd6479a6a3565da19e2625b4fc10329
                        self.username_input = ui.input(
                            placeholder="Enter Username"
                        ).classes(
                            "w-full app-input"
                        ).props(
                            'outlined dense input-class="font-semibold text-left"'
                        )
                        with self.username_input.add_slot('prepend'):
<<<<<<< HEAD
                            ui.icon('person_outline', size='sm').classes("login-badge-icon mr-1")
=======
                            ui.icon('person_outline', size='sm').classes("app-text-faint mr-1")
>>>>>>> 9562a1d23cd6479a6a3565da19e2625b4fc10329
                        self.username_input.on('keydown.enter', self.handle_login)

                    # Password Input Group
                    with ui.column().classes("w-full gap-1"):
                        with ui.row().classes("w-full justify-between items-end px-1"):
<<<<<<< HEAD
                            ui.label("Password").classes("text-xs login-label-en font-medium")
                            ui.label("كلمة المرور").classes("text-xs font-bold login-label-ar")
=======
                            ui.label("Password").classes("app-text-muted text-xs font-medium")
                            ui.label("كلمة المرور").classes("app-text-secondary text-xs font-bold")
>>>>>>> 9562a1d23cd6479a6a3565da19e2625b4fc10329

                        self.password_input = ui.input(
                            placeholder="Enter Password",
                            password=True,
                            password_toggle_button=True
                        ).classes(
                            "w-full app-input"
                        ).props(
                            'outlined dense input-class="font-semibold text-left"'
                        )
                        with self.password_input.add_slot('prepend'):
<<<<<<< HEAD
                            ui.icon('key', size='sm').classes("login-badge-icon mr-1")
=======
                            ui.icon('key', size='sm').classes("app-text-faint mr-1")
>>>>>>> 9562a1d23cd6479a6a3565da19e2625b4fc10329
                        self.password_input.on('keydown.enter', self.handle_login)

                    # Error Feedback Label
                    self.error_label = ui.label("").classes(
                        "app-text-error text-xs text-center w-full font-medium"
                    )
                    self.error_label.set_visibility(False)

                    # Primary Sign-In Button
                    with ui.button(on_click=self.handle_login).classes(
                        "app-btn-primary w-full text-sm py-3 rounded-xl font-bold "
                        "normal-case mt-2 cursor-pointer flex-row justify-between px-6"
                    ):
                        ui.label("SIGN IN / تسجيل الدخول")
                        ui.icon("arrow_forward", size="sm")

                # Bottom Actions (Theme Toggle)
                with ui.row().classes("w-[440px] max-w-full justify-end items-center mt-6 px-2"):
                    with ui.row().classes(
                        "app-theme-toggle gap-2 items-center px-3 py-1.5 rounded-full border shadow-sm"
                    ):
                        ui.icon("dark_mode", size="xs").classes("app-text-faint")
                        ui.switch(
                            on_change=lambda e: set_dark_mode(e.value)
                        ).props("dense size=sm").bind_value(self.dark_mode, 'value')
                        ui.icon("light_mode", size="xs").classes("app-text-faint")

    def _toggle_theme(self, is_dark: bool) -> None:
        """Explicitly enables/disables dark mode."""
        if is_dark:
            self.dark_mode.enable()
        else:
            self.dark_mode.disable()


    def handle_login(self, e=None) -> None:
        """Validates credentials via AuthRepository and updates session state."""
        if not self.username_input or not self.password_input:
            return

        username = (self.username_input.value or "").strip()
        password = self.password_input.value or ""

        if not username or not password:
            if self.error_label:
                self.error_label.set_text("يرجى إدخال اسم المستخدم وكلمة المرور / Please enter username and password")
                self.error_label.set_visibility(True)
            return

        conn = None
        try:
            conn = get_connection()
            auth_repo = AuthRepository(conn)
            user_record = auth_repo.authenticate(username, password)

            if user_record:
                if self.error_label:
                    self.error_label.set_visibility(False)
                from nicegui_ui.state import app_session
                user_id = user_record.get("id", 1)
                app_session.login_user(user_id, user_record)

                if self.on_login_success:
                    self.on_login_success(user_record)

                ui.navigate.to("/dashboard")
            else:
                if self.error_label:
                    self.error_label.set_text("اسم المستخدم أو كلمة المرور غير صحيحة / Invalid username or password")
                    self.error_label.set_visibility(True)

        except Exception as exc:
            print(f"[LoginScreen] Authentication Error: {exc}")
            if self.error_label:
                self.error_label.set_text("اسم المستخدم أو كلمة المرور غير صحيحة / Invalid username or password")
                self.error_label.set_visibility(True)
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
