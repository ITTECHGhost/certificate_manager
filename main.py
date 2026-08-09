# =============================================================================
# main.py — Application Entry Point
# =============================================================================

import sys
import asyncio
from nicegui import ui

# Import screens from isolated NiceGUI folder
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

# Handle restricted Windows multiprocessing Pipe permissions safely (WinError 5 Access is denied)
try:
    import concurrent.futures
    import multiprocessing.connection
    import nicegui.run

    _h1, _h2 = multiprocessing.connection.Pipe(duplex=False)
    _h1.close()
    _h2.close()
except Exception:
    import concurrent.futures
    import nicegui.run
    nicegui.run.setup = lambda: setattr(nicegui.run, 'process_pool', concurrent.futures.ThreadPoolExecutor())

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
        print(f"[main] Error detecting screen resolution: {err}")
    return (1280, 720)

def can_use_native_mode() -> bool:
    """Check whether Windows native pywebview IPC pipes can be created without permission errors."""
    try:
        import webview
        
        # Test if the OS allows creating Named Pipes for multiprocessing (required by Pywebview native mode)
        import multiprocessing.connection
        _h1, _h2 = multiprocessing.connection.Pipe(duplex=False)
        _h1.close()
        _h2.close()
        
        return True
    except Exception as err:
        print(f"[main] Native pywebview mode unavailable ({err}). Serving in web browser mode...")
        return False


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

if __name__ in {"__main__", "__mp_main__"}:
    if __name__ == "__main__":
        from utils.health_check import run_system_health_checks
        # Run system diagnostic health check once on startup and log to activity_log.txt
        run_system_health_checks()

    screen_size = get_screen_resolution()
    use_native = can_use_native_mode()

    if use_native:
        from nicegui import app
        import webview
        webview.settings['OPEN_DEVTOOLS_IN_DEBUG'] = False
        app.native.window_args['maximized'] = True
        app.native.start_args['gui'] = 'edgechromium'
        app.native.start_args['debug'] = True

    ui.run(
        native      = use_native,
        port        = 2323,
        window_size = screen_size if use_native else None,
        title       = "Certificate Manager",
        reload      = False,
        dark        = None,
        storage_secret = "certificate_manager_secret_key"
    )
