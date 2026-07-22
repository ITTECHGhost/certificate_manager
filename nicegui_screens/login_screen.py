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
        # 1. Reset container padding & enable auto OS theme mode
        ui.query(".nicegui-content").classes("p-0 m-0")
        ui.query("body").classes("m-0 p-0 overflow-hidden")
        ui.dark_mode().auto()

        ui.add_head_html(
            "<script>\n"
            "function syncDarkClass() {\n"
            "  if (document.body && document.body.classList.contains('body--dark')) {\n"
            "    document.documentElement.classList.add('dark');\n"
            "  } else {\n"
            "    document.documentElement.classList.remove('dark');\n"
            "  }\n"
            "}\n"
            "syncDarkClass();\n"
            "setInterval(syncDarkClass, 200);\n"
            "document.addEventListener('DOMContentLoaded', () => {\n"
            "  syncDarkClass();\n"
            "  const observer = new MutationObserver(syncDarkClass);\n"
            "  if (document.body) {\n"
            "    observer.observe(document.body, { attributes: true, attributeFilter: ['class'] });\n"
            "  }\n"
            "});\n"
            "</script>\n"
        )

        # 2. Main 2-Column Split Container
        with ui.row().classes("w-full h-screen flex-nowrap m-0 p-0 gap-0"):
            
            # --- LEFT COLUMN: University Logo Area (60% width) ---
            with ui.column().classes(
                "w-3/5 h-full items-center justify-center bg-slate-100 dark:bg-[#020617] "
                "border-r border-slate-200 dark:border-slate-800 p-8"
            ):
                if os.path.exists("csit.png"):
                    ui.image("csit.png").classes("w-80 h-80 object-contain")
                else:
                    ui.label("UNIVERSITY LOGO").classes(
                        "text-4xl font-extrabold text-slate-400 dark:text-slate-600 tracking-wider text-center"
                    )

            # --- RIGHT COLUMN: Login Card Form Area (40% width) ---
            with ui.column().classes(
                "w-2/5 h-full items-center justify-center bg-[#070c18] p-6"
            ):
                with ui.column().classes(
                    "w-[440px] bg-[#0b1329] rounded-3xl border border-slate-800/80 shadow-2xl p-8 gap-5"
                ):
                    # Top User Badge Icon
                    with ui.element("div").classes(
                        "w-16 h-16 rounded-2xl bg-blue-500/10 border border-blue-500/20 "
                        "flex items-center justify-center self-center"
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
                            ui.label("Username / Email").classes("text-[11px] text-slate-400 font-medium")
                            ui.label("اسم المستخدم / البريد الأكاديمي").classes("text-xs font-bold text-slate-200")
                        
                        self.username_input = ui.input(
                            placeholder="admin.cs"
                        ).classes(
                            "w-full bg-[#070e1e] text-white rounded-xl border border-slate-700/80 transition-colors"
                        ).props(
                            'outlined dense input-class="text-white font-semibold text-right" '
                            'append-icon="person"'
                        )

                    # Password Input Group
                    with ui.column().classes("w-full gap-1.5"):
                        with ui.row().classes("w-full justify-between items-center px-1"):
                            ui.label("نسيت كلمة المرور؟").classes(
                                "text-xs text-slate-400 hover:text-blue-400 cursor-pointer font-medium"
                            )
                            ui.label("كلمة المرور").classes("text-xs font-bold text-slate-200")

                        self.password_input = ui.input(
                            placeholder="••••••••",
                            password=True,
                            password_toggle_button=True
                        ).classes(
                            "w-full bg-[#070e1e] text-white rounded-xl border border-slate-700/80 transition-colors"
                        ).props(
                            'outlined dense input-class="text-white font-semibold text-right" '
                            'append-icon="key"'
                        )

                    # Remember Me & Role Row
                    with ui.row().classes("w-full justify-between items-center px-1 my-1"):
                        ui.label("الصلاحية: مسؤول النظام").classes("text-xs text-slate-400 font-medium")
                        ui.checkbox("تذكر بياناتي", value=True).classes(
                            "text-xs font-semibold text-slate-300 text-right"
                        )

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
                        "text-base py-3 rounded-xl shadow-lg shadow-blue-600/30 normal-case transition-all mt-1"
                    )

    def handle_login(self) -> None:
        """Validates credentials via AuthRepository and updates session state."""
        username = (self.username_input.value or "").strip()
        password = self.password_input.value or ""

        if not username or not password:
            self.error_label.set_text("يرجى إدخال اسم المستخدم وكلمة المرور / Please enter username and password")
            self.error_label.set_visibility(True)
            return

        conn = None
        try:
            conn = get_connection()
            auth_repo = AuthRepository(conn)
            user_record = auth_repo.authenticate(username, password)

            if user_record:
                self.error_label.set_visibility(False)
                from nicegui_ui.state import app_session
                user_id = user_record.get("id", 1)
                app_session.login_user(user_id, user_record)

                if self.on_login_success:
                    self.on_login_success(user_record)

                ui.navigate.to("/dashboard")
            else:
                self.error_label.set_text("اسم المستخدم أو كلمة المرور غير صحيحة / Invalid username or password")
                self.error_label.set_visibility(True)

        except Exception as exc:
            print(f"[LoginScreen] Authentication Error: {exc}")
            self.error_label.set_text("اسم المستخدم أو كلمة المرور غير صحيحة / Invalid username or password")
            self.error_label.set_visibility(True)
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
