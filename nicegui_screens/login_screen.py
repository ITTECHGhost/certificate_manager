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
        # 1. Reset container padding & force dark theme background
        ui.query(".nicegui-content").classes("p-0 m-0 bg-[#030712]")
        ui.query("body").classes("m-0 p-0 overflow-hidden bg-[#030712]")
        ui.dark_mode().enable()

        ui.add_head_html(
            """
            <style>
                body {
                    background-color: #030712 !important;
                }
                .login-card-glow {
                    box-shadow: 0 0 35px rgba(59, 130, 246, 0.25), 0 0 15px rgba(37, 99, 235, 0.15), 0 25px 50px rgba(0, 0, 0, 0.7);
                    border: 1px solid rgba(59, 130, 246, 0.3);
                }
                .login-card-glow:hover {
                    box-shadow: 0 0 45px rgba(59, 130, 246, 0.35), 0 0 20px rgba(37, 99, 235, 0.25), 0 25px 50px rgba(0, 0, 0, 0.8);
                    border: 1px solid rgba(59, 130, 246, 0.45);
                }
                .custom-input .q-field__control {
                    background-color: #070e1e !important;
                    border-radius: 12px !important;
                }
                .custom-input .q-field__control:before {
                    border-color: rgba(51, 65, 85, 0.7) !important;
                }
                .custom-input.q-field--focused .q-field__control:after {
                    border-color: #3b82f6 !important;
                    box-shadow: 0 0 12px rgba(59, 130, 246, 0.35) !important;
                }
            </style>
            <script>
            function syncDarkClass() {
              if (document.body && !document.body.classList.contains('body--dark')) {
                document.body.classList.add('body--dark');
              }
              if (document.documentElement && !document.documentElement.classList.contains('dark')) {
                document.documentElement.classList.add('dark');
              }
            }
            syncDarkClass();
            setInterval(syncDarkClass, 200);
            </script>
            """
        )

        # 2. Main 2-Column Split Container
        with ui.row().classes("w-full h-screen flex-nowrap m-0 p-0 gap-0 bg-[#030712]"):
            
            # --- LEFT COLUMN: University Logo Area (60% width) ---
            with ui.column().classes(
                "w-3/5 h-full items-center justify-center bg-[#030712] p-8"
            ):
                if os.path.exists("csit.png"):
                    ui.image("csit.png").classes("w-[340px] max-w-full h-auto object-contain drop-shadow-[0_10px_30px_rgba(0,0,0,0.6)]")
                else:
                    ui.label("UNIVERSITY LOGO").classes(
                        "text-4xl font-extrabold text-slate-400 dark:text-slate-600 tracking-wider text-center"
                    )

            # --- RIGHT COLUMN: Login Card Form Area (40% width) ---
            with ui.column().classes(
                "w-2/5 h-full items-center justify-center bg-[#030712] p-6"
            ):
                with ui.column().classes(
                    "w-[440px] max-w-full bg-[#0b1329] rounded-3xl p-8 gap-5 transition-all duration-300 login-card-glow"
                ):
                    # Top User Badge Icon
                    with ui.element("div").classes(
                        "w-16 h-16 rounded-2xl bg-blue-500/10 border border-blue-500/20 "
                        "flex items-center justify-center self-center shadow-inner shadow-blue-500/20"
                    ):
                        ui.icon("manage_accounts", size="md").classes("text-blue-400")

                    # Title & Subtitle
                    with ui.column().classes("w-full items-center gap-1 text-center"):
                        ui.label("تسجيل الدخول للنظام").classes(
                            "text-2xl font-black text-white tracking-wide"
                        )
                        ui.label("يرجى إدخال بيانات الاعتماد الخاصة بك للوصول للمنظومة").classes(
                            "text-xs font-medium text-slate-400"
                        )

                    # Username Input Group
                    with ui.column().classes("w-full gap-1.5 mt-2"):
                        with ui.row().classes("w-full justify-between items-center px-1"):
                            ui.label("Username").classes("text-xs text-slate-400 font-medium")
                            ui.label("اسم المستخدم").classes("text-xs font-bold text-slate-200")
                        
                        self.username_input = ui.input(
                            placeholder="username"
                        ).classes(
                            "w-full custom-input"
                        ).props(
                            'outlined dense dark input-class="text-white font-semibold text-right" '
                            'append-icon="person"'
                        )
                        self.username_input.on('keydown.enter', self.handle_login)

                    # Password Input Group
                    with ui.column().classes("w-full gap-1.5"):
                        with ui.row().classes("w-full justify-between items-center px-1"):
                            ui.label("password").classes("text-xs text-slate-400 font-medium")
                            ui.label("كلمة المرور").classes("text-xs font-bold text-slate-200")

                        self.password_input = ui.input(
                            placeholder="••••••••",
                            password=True,
                            password_toggle_button=True
                        ).classes(
                            "w-full custom-input"
                        ).props(
                            'outlined dense dark input-class="text-white font-semibold text-right"'
                        )
                        self.password_input.on('keydown.enter', self.handle_login)

                    # Error Feedback Label
                    self.error_label = ui.label("").classes(
                        "text-red-400 text-xs text-center w-full font-medium"
                    )
                    self.error_label.set_visibility(False)

                    # Primary Sign-In Button
                    ui.button(
                        "تسجيل الدخول",
                        icon="arrow_back",
                        on_click=self.handle_login
                    ).classes(
                        "w-full bg-blue-600 hover:bg-blue-500 text-white font-extrabold "
                        "text-base py-3.5 rounded-xl shadow-lg shadow-blue-600/35 hover:shadow-blue-500/50 normal-case transition-all mt-1 cursor-pointer"
                    )

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
