# =============================================================================
# main.py — Application Entry Point
# =============================================================================

import sys
import asyncio
from nicegui import ui
from utils.logger import setup_global_exception_logging, log_system

setup_global_exception_logging()

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

def ensure_port_available(port: int = 2323) -> None:
    """
    Check if the required port is already bound by an orphaned background process
    (e.g., from an unclosed previous session). If an orphaned python or webview process
    is holding the port, terminate it to prevent socket bind failure (WinError 10048).
    """
    try:
        import os
        import time
        import psutil
        current_pid = os.getpid()
        killed = False
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.status == "LISTEN":
                if conn.pid and conn.pid != current_pid:
                    try:
                        p = psutil.Process(conn.pid)
                        p_name = p.name().lower()
                        if "python" in p_name or "webview" in p_name:
                            log_system(f"Releasing port {port} held by orphaned process PID {conn.pid} ({p.name()})...", "WARNING")
                            for child in p.children(recursive=True):
                                try:
                                    child.kill()
                                except (psutil.NoSuchProcess, psutil.AccessDenied):
                                    pass
                            p.kill()
                            killed = True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        if killed:
            time.sleep(0.5)
    except Exception as err:
        log_system(f"Port availability check notice: {err}", "WARNING")

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
    return (1440, 900)

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
        ensure_port_available(2323)
        from utils.health_check import run_system_health_checks
        # Run system diagnostic health check once on startup and log to activity_log.txt
        run_system_health_checks()

    is_web_mode = "--web" in sys.argv
    screen_size = get_screen_resolution()
    use_native = False if is_web_mode else can_use_native_mode()
    bind_host = "0.0.0.0" if is_web_mode else "127.0.0.1"

    if is_web_mode:
        log_system("Certificate Manager starting in Web Server / Fallback mode on 0.0.0.0:2323", "INFO")

    if use_native:
        from nicegui import app
        import webview
        webview.settings['OPEN_DEVTOOLS_IN_DEBUG'] = False
        app.native.window_args['min_size'] = (1280, 720)
        app.native.window_args['maximized'] = True
        app.native.start_args['gui'] = 'edgechromium'
        app.native.start_args['debug'] = True

    # Ensure all background processes and threads exit cleanly when closing the app
    from nicegui import app
    import os
    os.makedirs("assets", exist_ok=True)
    app.add_static_files('/assets', 'assets')
    app.on_shutdown(lambda: os._exit(0))

    async def _on_app_startup():
        """Asynchronously sync templates in background on application startup."""
        try:
            from sync_engine import is_online
            if is_online():
                from nicegui import run
                import services.template_sync as t_sync
                res = await run.io_bound(t_sync.sync_templates_if_online)
                if res.get("synced_files"):
                    log_system(f"Startup template sync updated: {res['synced_files']}", "INFO")
        except Exception as exc:
            log_system(f"Startup template sync notice: {exc}", "WARNING")

    app.on_startup(_on_app_startup)

    target_win_size = (max(1400, screen_size[0]), max(880, screen_size[1])) if use_native else None

    ui.run(
        native      = use_native,
        host        = bind_host,
        port        = 2323,
        window_size = target_win_size,
        title       = "Certificate Manager",
        reload      = False,
        dark        = None,
        storage_secret = "certificate_manager_secret_key"
    )
