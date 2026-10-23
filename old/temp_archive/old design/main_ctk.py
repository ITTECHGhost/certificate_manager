# =============================================================================
# main.py — Application Entry Point
# =============================================================================
#
# HOW TO RUN:
#   python main.py
#
# WHAT THIS FILE DOES:
#   1. Configures the global appearance (light/dark mode, color theme)
#   2. Initializes the database (creates tables + seeds data if first run)
#   3. Sets up the dual text-file logging system (System & Activity)
#   4. Creates the main window with sidebar navigation
#   5. Instantiates all screens and handles switching between them
#
# =============================================================================

import sys
import logging
from typing import Any
# pyrefly: ignore [missing-import]
import customtkinter as ctk
from db import get_connection, init_db
from sync_engine import (
    init_local_db, check_network_status, set_online, is_online,
    sync_offline_queue_to_mysql, get_queue_status,
    pull_mysql_to_sqlite_background, download_mysql_snapshot,
    get_local_connection,
)
from config import (
    AppColors, AppFonts, AppSizes,
    NAV_ITEMS, SETTINGS_ITEM, SCREEN_HEADERS,
    refresh_config
)
from ctk_screens.home_screen import HomeScreen
from ctk_screens.placeholder_screen import PlaceholderScreen
from ctk_screens.departments_screen import DepartmentsScreen
from ctk_screens.personnel_screen import PersonnelScreen
from ctk_screens.courses_screen import CoursesScreen
from ctk_screens.graduation_orders_screen import GraduationOrdersScreen
from ctk_screens.students_screen import StudentsScreen
from ctk_screens.order_students_screen import OrderStudentsScreen
from ctk_screens.history_screen import HistoryScreen
from ctk_screens.certificate_screen import CertificateScreen
from ctk_screens.settings_screen import SettingsScreen
from ctk_screens.login_screen import LoginScreen

# ---------------------------------------------------------------------------
# Global Logging Setup (Text Files)
# ---------------------------------------------------------------------------
# Clear existing handlers to prevent duplicates if re-initialized
logging.getLogger().handlers.clear()

# 1. System Log: For structural errors, database warnings, and crashes
system_logger = logging.getLogger("system")
system_logger.setLevel(logging.INFO)
system_logger.handlers.clear()
system_logger.propagate = False  # Prevent propagation to avoid duplicate logs in root

sys_handler = logging.FileHandler("system_log.txt", mode="a", encoding="utf-8")
sys_handler.setFormatter(logging.Formatter('%(asctime)s [SYSTEM] %(levelname)s: %(message)s'))
system_logger.addHandler(sys_handler)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter('%(message)s'))
system_logger.addHandler(stream_handler)

# Reroute root logger to catch generic outputs securely
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers.clear()
root_logger.addHandler(sys_handler)
root_logger.addHandler(stream_handler)

# 2. Activity Log: For tracking user actions and certificate generation
activity_logger = logging.getLogger("activity")
activity_logger.setLevel(logging.INFO)
activity_logger.handlers.clear()
activity_logger.propagate = False

act_handler = logging.FileHandler("activity_log.txt", mode="a", encoding="utf-8")
act_handler.setFormatter(logging.Formatter('%(asctime)s [ACTIVITY] %(message)s'))
activity_logger.addHandler(act_handler)

logger = logging.getLogger(__name__)
logging.captureWarnings(True)

logger.info("Application starting...")

# Note: FastAPI Windows Service is restarted asynchronously at main execution entry.

# ---------------------------------------------------------------------------
# Global appearance — must be set before any CTk widget is created
# ---------------------------------------------------------------------------
try:
    init_db()
except Exception as _init_err:
    system_logger.warning("MySQL unavailable at startup: %s — starting in offline mode.", _init_err)
    set_online(False)
init_local_db()
refresh_config(None)


# ===========================================================================
# Sidebar
# ===========================================================================

class Sidebar(ctk.CTkFrame):
    """Right-side navigation panel."""

    def __init__(self, parent: ctk.CTk, on_navigate) -> None:
        super().__init__(
            parent,
            width=AppSizes.SIDEBAR_WIDTH,
            corner_radius=0,
            fg_color=AppColors.SIDEBAR_BG,
            border_width=0,
        )
        self._on_navigate = on_navigate
        self._buttons: dict[str, ctk.CTkButton] = {}

        self.grid_propagate(False)          # keep fixed width
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self) -> None:
        self._build_title()
        self._build_nav_buttons()
        self._build_settings_and_toggle()

    def _build_title(self) -> None:
        ctk.CTkLabel(
            self,
            text="الإدارة  —  Management",
            font=ctk.CTkFont(
                family=AppFonts.FAMILY,
                size=AppFonts.SIZE_HEADING,
                weight="bold",
            ),
            text_color="white",
            anchor="center",
        ).grid(row=0, column=0, padx=16, pady=(22, 10), sticky="ew")

        ctk.CTkFrame(self, height=1, fg_color=AppColors.DIVIDER).grid(
            row=1, column=0, sticky="ew", padx=14, pady=(0, 8)
        )

    def _build_nav_buttons(self) -> None:
        for row_offset, item in enumerate(NAV_ITEMS):
            btn = ctk.CTkButton(
                self,
                text=f"{item['icon']}  {item['ar']}",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_HEADING),
                anchor="e",
                height=AppSizes.NAV_BUTTON_HEIGHT,
                corner_radius=8,
                fg_color=AppColors.NAV_DEFAULT_BG,
                text_color=AppColors.NAV_TEXT,
                hover_color=AppColors.NAV_HOVER_BG,
                command=lambda key=item["key"]: self._on_navigate(key),
            )
            btn.grid(row=row_offset + 2, column=0, padx=10, pady=2, sticky="ew")
            self._buttons[item["key"]] = btn

        self.grid_rowconfigure(len(NAV_ITEMS) + 2, weight=1)

    def _build_settings_and_toggle(self) -> None:
        base_row = len(NAV_ITEMS) + 3

        ctk.CTkFrame(self, height=1, fg_color=AppColors.DIVIDER).grid(
            row=base_row, column=0, sticky="ew", padx=14, pady=(0, 4)
        )

        settings_btn = ctk.CTkButton(
            self,
            text=f"{SETTINGS_ITEM['icon']}  {SETTINGS_ITEM['ar']}",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_HEADING),
            anchor="e",
            height=AppSizes.SETTINGS_BTN_HEIGHT,
            corner_radius=8,
            fg_color=AppColors.NAV_DEFAULT_BG,
            text_color=AppColors.NAV_TEXT,
            hover_color=AppColors.NAV_HOVER_BG,
            command=lambda: self._on_navigate(SETTINGS_ITEM["key"]),
        )
        settings_btn.grid(
            row=base_row + 1, column=0, padx=10, pady=2, sticky="ew"
        )
        self._buttons[SETTINGS_ITEM["key"]] = settings_btn


    def set_active(self, active_key: str) -> None:
        for key, btn in self._buttons.items():
            if key == active_key:
                btn.configure(fg_color=AppColors.NAV_ACTIVE_BG, text_color="white")
            else:
                btn.configure(fg_color=AppColors.NAV_DEFAULT_BG, text_color=AppColors.NAV_TEXT)


# ===========================================================================
# Header Bar
# ===========================================================================

class HeaderBar(ctk.CTkFrame):
    """Top header bar displaying active screen titles and network status."""

    def __init__(self, parent: ctk.CTkFrame) -> None:
        super().__init__(
            parent,
            height=AppSizes.HEADER_HEIGHT,
            corner_radius=0,
            fg_color=AppColors.HEADER_BG,
        )
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self) -> None:
        self._label_ar = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(
                family=AppFonts.FAMILY,
                size=AppFonts.SIZE_TITLE,
                weight="bold",
            ),
            anchor="e",
        )
        self._label_ar.grid(row=0, column=0, sticky="e", padx=(0, 20), pady=12)

        self._label_en = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_TITLE),
            text_color=AppColors.TEXT_MUTED,
            anchor="w",
        )
        self._label_en.grid(row=0, column=0, sticky="w", padx=(20, 0), pady=12)

        # Network status indicator (left-aligned, next to English title)
        self._net_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            anchor="w",
        )
        self._net_label.grid(row=0, column=1, sticky="w", padx=(4, 16), pady=12)
        self.update_network_status(True)  # assume online initially

        # User details label (packed/gridded next to network status indicator)
        self.user_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL, weight="bold"),
            anchor="w",
        )
        self.user_label.grid(row=0, column=2, sticky="w", padx=(16, 20), pady=12)

    def set_user(self, user_data: dict) -> None:
        if user_data:
            name = user_data.get('name_ar') or user_data.get('username') or "مستخدم"
            role = user_data.get('role', '')
            self.user_label.configure(text=f"👤 {name} - {role}")
        else:
            self.user_label.configure(text="")

    def set_screen(self, screen_key: str) -> None:
        ar, en = SCREEN_HEADERS.get(screen_key, ("", ""))
        self._label_ar.configure(text=ar)
        self._label_en.configure(text=en)

    def update_network_status(self, online: bool) -> None:
        """Update the network indicator label."""
        if online:
            self._net_label.configure(
                text="\U0001f7e2 \u0645\u062a\u0635\u0644 (Online)",
                text_color=AppColors.COLOR_SUCCESS,
            )
        else:
            self._net_label.configure(
                text="\U0001f534 \u0648\u0636\u0639 \u0639\u062f\u0645 \u0627\u0644\u0627\u062a\u0635\u0627\u0644 (Offline Mode)",
                text_color=AppColors.COLOR_ERROR,
            )


# ===========================================================================
# Main Application Window
# ===========================================================================

class CertificateManagerApp(ctk.CTk):
    """Root application window."""

    def __init__(self) -> None:
        super().__init__()
        # Route Tkinter crashes to system_logger
        self.report_callback_exception = self._on_tkinter_error
        
        self.current_user = None
        self._setup_window()
        
        # Show login screen first
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._login_screen = LoginScreen(self, on_login_success=self._on_login_success)
        self._login_screen.grid(row=0, column=0, sticky="nsew")

        # Open in maximized state after a short delay to ensure it takes effect
        self.after(100, lambda: self.state('zoomed'))

    def _on_login_success(self, user_data: dict) -> None:
        self.current_user = user_data
        system_logger.info(f"User '{user_data.get('username')}' logged in successfully.")
        
        # Apply user-specific appearance
        refresh_config(user_data["id"])
        
        # Remove login screen
        self._login_screen.destroy()
        
        # Build main layout
        self._build_layout()
        if hasattr(self, '_header'):
            self._header.set_user(user_data)
        elif hasattr(self, 'header'):
            self.header.set_user(user_data)
        self._build_screens()
        self._show_screen("home")

        # Start network polling loop
        self._prev_online = True
        self._start_network_poller()

        # Trigger DB backup snapshot immediately if online
        if is_online():
            import threading
            from db import get_connection
            def _snapshot_worker():
                try:
                    my_conn = get_connection()
                    sqlite_conn = get_local_connection()
                    try:
                        download_mysql_snapshot(my_conn, sqlite_conn)
                        system_logger.info("Database snapshot backup complete.")
                    finally:
                        my_conn.close()
                        sqlite_conn.close()
                except Exception as e:
                    system_logger.error(f"Snapshot backup failed: {e}")
            threading.Thread(target=_snapshot_worker, daemon=True, name="login-snapshot").start()

    def _on_tkinter_error(self, exc, val, tb):
        system_logger.error("Unhandled exception in Tkinter callback:", exc_info=(exc, val, tb))

    def _setup_window(self) -> None:
        self.title("نظام إدارة الشهادات  —  Certificate Manager")
        self.geometry(f"{AppSizes.WINDOW_WIDTH}x{AppSizes.WINDOW_HEIGHT}")
        self.minsize(AppSizes.MIN_WIDTH, AppSizes.MIN_HEIGHT)
        try:
            self.state('zoomed')
        except Exception:
            pass

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        self._sidebar = Sidebar(self, on_navigate=self._show_screen)
        self._sidebar.grid(row=0, column=1, sticky="nsew")

        content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray90", "gray13"))
        content_frame.grid(row=0, column=0, sticky="nsew")
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(1, weight=1)

        self._header = HeaderBar(content_frame)
        self._header.grid(row=0, column=0, sticky="ew")

        self._screen_slot = ctk.CTkFrame(
            content_frame, corner_radius=0, fg_color="transparent"
        )
        self._screen_slot.grid(
            row=1, column=0, sticky="nsew",
            padx=AppSizes.PAD_SCREEN,
            pady=AppSizes.PAD_SCREEN,
        )
        self._screen_slot.grid_columnconfigure(0, weight=1)
        self._screen_slot.grid_rowconfigure(0, weight=1)

    def _build_screens(self) -> None:
        self._screens: dict[str, Any] = {
            "home": HomeScreen(self._screen_slot, switch_callback=self._show_screen),
            "students": StudentsScreen(self._screen_slot, self._show_screen),
            "orders": GraduationOrdersScreen(self._screen_slot, self._show_screen),
            "order_students": OrderStudentsScreen(self._screen_slot, self._show_screen),
            "departments": DepartmentsScreen(self._screen_slot, self._show_screen),
            "courses": CoursesScreen(self._screen_slot, self._show_screen),
            
            # Unified Personnel Management Screen
            "personnel": PersonnelScreen(self._screen_slot, self._show_screen),
            
            "certificate": CertificateScreen(self._screen_slot, self._show_screen),
            "history": HistoryScreen(self._screen_slot, self._show_screen),
            "settings": SettingsScreen(self._screen_slot, self._show_screen),
        }

        # Wire callbacks
        orders_screen: GraduationOrdersScreen = self._screens["orders"]
        orders_screen.set_view_students_callback(self._open_order_students)

        # Grid screens into the Z-stack
        for screen in self._screens.values():
            screen.grid(row=0, column=0, sticky="nsew")

    def _show_screen(self, key: str) -> None:
        if key not in self._screens:
            return
        self._screens[key].tkraise()
        
        # Trigger dynamic reload of data on screen switch
        if hasattr(self._screens[key], 'refresh'):
            self._screens[key].refresh()
            
        self._header.set_screen(key)
        self._sidebar.set_active(key)

    def _open_order_students(self, order: dict) -> None:
        sub: OrderStudentsScreen = self._screens["order_students"]
        sub.set_order(order, back_callback=lambda: self._show_screen("orders"))
        self._show_screen("order_students")

    # -- Background network poller and status updater -----------------------

    def _start_network_poller(self) -> None:
        """Start a persistent background thread to check network status periodically."""
        def poller_loop():
            import time
            while True:
                try:
                    now_online = check_network_status()
                    self.after(0, lambda online=now_online: self._handle_network_status_update(online))
                except Exception as exc:
                    system_logger.error("Network check exception: %s", exc)
                time.sleep(8)

        import threading
        threading.Thread(target=poller_loop, daemon=True, name="NetworkPoller").start()

    def _handle_network_status_update(self, now_online: bool) -> None:
        """Process network changes and trigger background queue auto-sync on recovery."""
        try:
            was_online = getattr(self, '_prev_online', True)
            set_online(now_online)

            # Update header indicator
            if hasattr(self, '_header'):
                self._header.update_network_status(now_online)

            # Transition: offline -> online => auto-sync
            if now_online and not was_online:
                system_logger.info("Network restored. Triggering offline queue sync...")
                
                def _sync_worker():
                    try:
                        from db import get_connection
                        conn = get_connection()
                        summary = sync_offline_queue_to_mysql(conn)
                        conn.close()
                        if summary["synced"] > 0:
                            system_logger.info(
                                "Auto-sync complete: %d synced, %d failed.",
                                summary["synced"], summary["failed"]
                            )
                    except Exception as exc:
                        system_logger.error("Auto-sync failed: %s", exc)

                    # Refresh local SQLite replica with latest MySQL data
                    pull_mysql_to_sqlite_background()

                import threading
                threading.Thread(target=_sync_worker, daemon=True, name="AutoSyncWorker").start()

            self._prev_online = now_online
        except Exception as exc:
            system_logger.error("Network poll update error: %s", exc)


# ===========================================================================
# Entry Point
# ===========================================================================

def _restart_fastapi_service_async() -> None:
    """Restarts the FastAPI Windows Service asynchronously in a background thread."""
    def run_restart():
        try:
            import subprocess
            system_logger.info("Restarting FastAPI Windows Service asynchronously...")
            subprocess.run(
                ["cmd", "/c", "net stop FastAPICertificateManager && net start FastAPICertificateManager"],
                capture_output=True,
                shell=True
            )
            system_logger.info("FastAPI Windows Service restart sequence completed.")
        except Exception as exc:
            system_logger.warning("Could not restart FastAPI service automatically: %s", exc)

    import threading
    threading.Thread(target=run_restart, daemon=True, name="ServiceRestarter").start()


if __name__ == "__main__":
    try:
        _restart_fastapi_service_async()
        app = CertificateManagerApp()
        app.mainloop()
        logger.info("Application closed normally.")
    except Exception:
        system_logger.exception("A critical error occurred that caused the application to crash:")
        sys.exit(1)