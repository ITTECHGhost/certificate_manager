# =============================================================================
# nicegui_screens/login_screen.py — NiceGUI Authentication Login Screen
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
    high-contrast theme-aware inputs, auto OS theme detection, and session routing.
    """

    def __init__(self, on_login_success=None) -> None:
        self.on_login_success = on_login_success
        self.username_input = None
        self.password_input = None
        self.error_label = None
        self.build_ui()

    def build_ui(self) -> None:
        """Renders the two-column split login layout using UI component factory."""
        from nicegui_ui.ui_theme import is_windows_dark_mode, set_dark_mode, inject_global_styles

        self.dark_mode = ui.dark_mode()
        set_dark_mode(is_windows_dark_mode())

        # 1. Reset container padding & set background to adapt to theme
        ui.query(".nicegui-content").classes("p-0 m-0 bg-slate-50 dark:bg-[#0f172a] transition-colors duration-500")
        ui.query("body").classes("m-0 p-0 overflow-hidden bg-slate-50 dark:bg-[#0f172a] transition-colors duration-500")
        
        inject_global_styles()

        # 2. Main 2-Column Split Container
        with ui.row().classes("w-full h-screen flex-nowrap m-0 p-0 gap-0 transition-colors duration-500"):
            
            # --- LEFT COLUMN: University Logo Area (50% or 60% width) ---
            with ui.column().classes(
                "w-1/2 md:w-3/5 h-full items-center justify-center p-8 bg-network transition-colors duration-500 border-r border-slate-200 dark:border-slate-800/50"
            ):
                if os.path.exists("csit.png"):
                    ui.image("csit.png").classes("w-[340px] max-w-full h-auto object-contain drop-shadow-xl dark:drop-shadow-[0_10px_30px_rgba(0,0,0,0.6)]")
                else:
                    ui.label("UNIVERSITY LOGO").classes(
                        "text-4xl font-extrabold text-slate-500 dark:text-slate-400 tracking-wider text-center"
                    )

            # --- RIGHT COLUMN: Login Card Form Area (50% or 40% width) ---
            with ui.column().classes(
                "w-1/2 md:w-2/5 h-full items-center justify-center bg-slate-50 dark:bg-[#0f172a] p-6 transition-colors duration-500 relative"
            ):
                # The Card Container loaded from global UI factory
                with UI.login_card():

                    # Top User Badge Icon (Offset)
                    with ui.element("div").classes(
                        "w-16 h-16 rounded-2xl avatar-badge border "
                        "flex items-center justify-center shadow-md dark:shadow-inner dark:shadow-blue-500/10 avatar-offset"
                    ):
                        with ui.element("div").classes("w-12 h-12 rounded-xl avatar-inner flex items-center justify-center"):
                            ui.icon("person_outline", size="sm").classes("text-slate-600 dark:text-slate-300")

                    # Title & Subtitle
                    with ui.column().classes("w-full items-center gap-1 text-center mt-2"):
                        ui.label("SYSTEM LOGIN / تسجيل الدخول").classes(
                            "text-[1.2rem] font-bold text-slate-800 dark:text-white tracking-wide"
                        )
                        ui.label("Enter credentials to access the system").classes(
                            "text-[11px] font-medium text-slate-500 dark:text-slate-400 -mb-0.5"
                        )
                        ui.label("يرجى إدخال بيانات الاعتماد الخاصة بك للوصول").classes(
                            "text-[11px] font-medium text-slate-500 dark:text-slate-400"
                        )

                    # Username Input Group
                    with ui.column().classes("w-full gap-1 mt-3"):
                        with ui.row().classes("w-full justify-between items-end px-1"):
                            ui.label("Username").classes("text-xs text-slate-500 dark:text-slate-400 font-medium")
                            ui.label("اسم المستخدم").classes("text-xs font-bold text-slate-700 dark:text-slate-200")
                        
                        self.username_input = ui.input(
                            placeholder="Enter Username"
                        ).classes(
                            "w-full custom-input"
                        ).props(
                            'outlined dense input-class="text-slate-800 dark:text-white font-semibold text-left"'
                        )
                        with self.username_input.add_slot('prepend'):
                            ui.icon('person_outline', size='sm').classes("text-slate-400 dark:text-slate-500 mr-1")
                        self.username_input.on('keydown.enter', self.handle_login)

                    # Password Input Group
                    with ui.column().classes("w-full gap-1"):
                        with ui.row().classes("w-full justify-between items-end px-1"):
                            ui.label("Password").classes("text-xs text-slate-500 dark:text-slate-400 font-medium")
                            ui.label("كلمة المرور").classes("text-xs font-bold text-slate-700 dark:text-slate-200")

                        self.password_input = ui.input(
                            placeholder="Enter Password",
                            password=True,
                            password_toggle_button=True
                        ).classes(
                            "w-full custom-input"
                        ).props(
                            'outlined dense input-class="text-slate-800 dark:text-white font-semibold text-left"'
                        )
                        with self.password_input.add_slot('prepend'):
                            ui.icon('key', size='sm').classes("text-slate-400 dark:text-slate-500 mr-1")
                        self.password_input.on('keydown.enter', self.handle_login)

                    # Error Feedback Label
                    self.error_label = ui.label("").classes(
                        "text-red-500 dark:text-red-400 text-xs text-center w-full font-medium"
                    )
                    self.error_label.set_visibility(False)

                    # Primary Sign-In Button
                    with ui.button(on_click=self.handle_login).classes(
                        "w-full bg-[#3b82f6] hover:bg-[#2563eb] text-white font-bold "
                        "text-sm py-3 rounded-xl shadow-lg shadow-blue-500/30 hover:shadow-blue-500/50 normal-case transition-all mt-2 cursor-pointer flex-row justify-between px-6"
                    ):
                        ui.label("SIGN IN / تسجيل الدخول")
                        ui.icon("arrow_forward", size="sm")

                # Bottom Actions (Theme Toggle)
                with ui.row().classes("w-[440px] max-w-full justify-end items-center mt-6 px-2"):
                    with ui.row().classes("gap-2 items-center avatar-badge px-3 py-1.5 rounded-full border shadow-sm"):
                        ui.icon("dark_mode", size="xs").classes("text-slate-400 dark:text-slate-500")
                        ui.switch(on_change=lambda e: set_dark_mode(e.value)).props("dense size=sm").bind_value(self.dark_mode, 'value')
                        ui.icon("light_mode", size="xs").classes("text-slate-500 dark:text-slate-400")

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
