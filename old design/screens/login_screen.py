# =============================================================================
# screens/login_screen.py — NiceGUI Login Screen
# =============================================================================

from nicegui import ui
from db import get_connection
from data.repositories import AuthRepository
from state import app_session


class LoginScreen:
    """
    NiceGUI Login Screen component.
    Provides responsive flexbox centering, username/password inputs,
    error validation label, and authentication routing.
    """

    def __init__(self, on_login_success=None) -> None:
        self.on_login_success = on_login_success
        self.username_input = None
        self.password_input = None
        self.error_label = None
        self.build_ui()

    def build_ui(self) -> None:
        """Renders the centered login card layout."""
        with ui.row().classes("w-full h-screen items-center justify-center bg-[#0f172a] m-0 p-0"):
            with ui.card().classes("w-96 p-8 bg-[#1e293b] rounded-2xl shadow-xl border border-slate-800 gap-4"):
                ui.label("Certificate Manager - Login").classes(
                    "text-2xl font-bold text-white text-center mb-2"
                )

                self.username_input = ui.input(
                    label="Username",
                    placeholder="Enter username"
                ).classes("w-full").props("outlined dark")

                self.password_input = ui.input(
                    label="Password",
                    placeholder="Enter password",
                    password=True,
                    password_toggle_button=True
                ).classes("w-full").props("outlined dark")

                self.error_label = ui.label("Invalid username or password").classes(
                    "text-red-400 text-sm text-center w-full font-medium"
                )
                self.error_label.set_visibility(False)

                ui.button(
                    "Login",
                    on_click=self.handle_login
                ).classes(
                    "w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-3 rounded-xl normal-case transition-colors mt-2"
                )

    def handle_login(self) -> None:
        """Validates credentials via AuthRepository and updates session state."""
        username = (self.username_input.value or "").strip()
        password = self.password_input.value or ""

        if not username or not password:
            self.error_label.set_text("Invalid username or password")
            self.error_label.set_visibility(True)
            return

        conn = None
        try:
            conn = get_connection()
            auth_repo = AuthRepository(conn)
            user_record = auth_repo.authenticate(username, password)

            if user_record:
                self.error_label.set_visibility(False)
                user_id = user_record.get("id", 1)
                app_session.login_user(user_id)

                if self.on_login_success:
                    self.on_login_success(user_record)
                else:
                    ui.navigate.to("/")
            else:
                self.error_label.set_text("Invalid username or password")
                self.error_label.set_visibility(True)

        except Exception as exc:
            print(f"[LoginScreen] Authentication Error: {exc}")
            self.error_label.set_text("Invalid username or password")
            self.error_label.set_visibility(True)
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
