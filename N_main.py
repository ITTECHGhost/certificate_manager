# =============================================================================
# N_main.py — NiceGUI Application Entry Point
# =============================================================================

import sys
import asyncio
from nicegui import ui

# Import both screens from your new isolated NiceGUI folder
from nicegui_screens.login_screen import LoginScreen
from nicegui_screens.dashboard_screen import DashboardScreen

# Handle Windows ProactorEventLoop socket shutdown bug (WinError 10054) gracefully
if sys.platform == "win32":
    from asyncio.proactor_events import _ProactorBasePipeTransport
    if hasattr(_ProactorBasePipeTransport, "_call_connection_lost"):
        _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost

        def _silenced_call_connection_lost(self, exc=None):
            try:
                _orig_call_connection_lost(self, exc)
            except (ConnectionResetError, OSError):
                pass

        _ProactorBasePipeTransport._call_connection_lost = _silenced_call_connection_lost

def get_screen_resolution() -> tuple[int, int]:
    """Retrieve PC's primary monitor screen resolution for native desktop window sizing."""
    try:
        if sys.platform == "win32":
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
            if width > 0 and height > 0:
                return (width, height)
    except Exception as err:
        print(f"[N_main] Error detecting screen resolution: {err}")
    return (1280, 800)

# --- ROUTING ---

@ui.page('/')
def login_page():
    """The root page loads the Login Screen first."""
    LoginScreen()

@ui.page('/dashboard')
def dashboard_page():
    """Only accessible after login navigates here."""
    DashboardScreen()

# --- APP EXECUTION ---

from nicegui import app

app.native.window_args['maximized'] = True

# The window is maximized via app.native.window_args['maximized'] = True

if __name__ in {"__main__", "__mp_main__"}:
    screen_size = get_screen_resolution()
    ui.run(
        native      = True,           # Open as a native desktop window (PyWebView)
        port        = 2323,           # Avoid conflict with FastAPI on port 2030
        window_size = screen_size,    # Auto-detect PC screen resolution
        title       = "Certificate Manager",
        reload      = False,          # No hot-reload in production
        dark        = None,           # Rely on OS system preference for login screen
    )