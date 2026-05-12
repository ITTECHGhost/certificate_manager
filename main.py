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
import customtkinter as ctk
from db import init_db
from config import (
    AppColors, AppFonts, AppSizes,
    NAV_ITEMS, SETTINGS_ITEM, SCREEN_HEADERS,
    refresh_config
)
from screens.home_screen import HomeScreen
from screens.placeholder_screen import PlaceholderScreen
from screens.departments_screen import DepartmentsScreen
from screens.personnel_screen import PersonnelScreen  # <-- Updated to unified Personnel
from screens.courses_screen import CoursesScreen
from screens.graduation_orders_screen import GraduationOrdersScreen
from screens.students_screen import StudentsScreen
from screens.order_students_screen import OrderStudentsScreen
from screens.history_screen import HistoryScreen
from screens.certificate_screen import CertificateScreen
from screens.settings_screen import SettingsScreen
from screens.login_screen import LoginScreen

# ---------------------------------------------------------------------------
# Global Logging Setup (Text Files)
# ---------------------------------------------------------------------------
# 1. System Log: For structural errors, database warnings, and crashes
system_logger = logging.getLogger("system")
system_logger.setLevel(logging.INFO)
sys_handler = logging.FileHandler("system_log.txt", mode="a", encoding="utf-8")
sys_handler.setFormatter(logging.Formatter('%(asctime)s [SYSTEM] %(levelname)s: %(message)s'))
system_logger.addHandler(sys_handler)
system_logger.addHandler(logging.StreamHandler(sys.stdout))

# Reroute root logger to system_log to catch generic output
logging.getLogger().handlers = system_logger.handlers
logging.getLogger().setLevel(logging.INFO)

# 2. Activity Log: For tracking user actions and certificate generation
activity_logger = logging.getLogger("activity")
activity_logger.setLevel(logging.INFO)
act_handler = logging.FileHandler("activity_log.txt", mode="a", encoding="utf-8")
act_handler.setFormatter(logging.Formatter('%(asctime)s [ACTIVITY] %(message)s'))
activity_logger.addHandler(act_handler)

logger = logging.getLogger(__name__)
logging.captureWarnings(True)

logger.info("Application starting...")

# ---------------------------------------------------------------------------
# Global appearance — must be set before any CTk widget is created
# ---------------------------------------------------------------------------
init_db()
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
            text="إدارة الشهادات",
            font=ctk.CTkFont(
                family=AppFonts.FAMILY,
                size=AppFonts.SIZE_HEADING,
                weight="bold",
            ),
            anchor="center",
        ).grid(row=0, column=0, padx=16, pady=(22, 2), sticky="ew")

        ctk.CTkLabel(
            self,
            text="Certificate Manager",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_TINY),
            text_color=AppColors.TEXT_MUTED,
            anchor="center",
        ).grid(row=1, column=0, padx=16, pady=(0, 10), sticky="ew")

        ctk.CTkFrame(self, height=1, fg_color=AppColors.DIVIDER).grid(
            row=2, column=0, sticky="ew", padx=14, pady=(0, 8)
        )

    def _build_nav_buttons(self) -> None:
        for row_offset, item in enumerate(NAV_ITEMS):
            btn = ctk.CTkButton(
                self,
                text=f"{item['icon']}  {item['ar']}",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_HEADING),
                anchor="e",
                height=AppSizes.NAV_BUTTON_HEIGHT,
                corner_radius=AppSizes.CORNER_RADIUS_BTN,
                fg_color=AppColors.NAV_DEFAULT_BG,
                text_color=AppColors.NAV_TEXT,
                hover_color=AppColors.NAV_HOVER_BG,
                command=lambda key=item["key"]: self._on_navigate(key),
            )
            btn.grid(row=row_offset + 3, column=0, padx=10, pady=2, sticky="ew")
            self._buttons[item["key"]] = btn

        self.grid_rowconfigure(len(NAV_ITEMS) + 3, weight=1)

    def _build_settings_and_toggle(self) -> None:
        base_row = len(NAV_ITEMS) + 4

        ctk.CTkFrame(self, height=1, fg_color=AppColors.DIVIDER).grid(
            row=base_row, column=0, sticky="ew", padx=14, pady=(0, 4)
        )

        settings_btn = ctk.CTkButton(
            self,
            text=f"{SETTINGS_ITEM['icon']}  {SETTINGS_ITEM['ar']}",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_HEADING),
            anchor="e",
            height=AppSizes.SETTINGS_BTN_HEIGHT,
            corner_radius=AppSizes.CORNER_RADIUS_BTN,
            fg_color=AppColors.NAV_DEFAULT_BG,
            text_color=AppColors.NAV_TEXT,
            hover_color=AppColors.NAV_HOVER_BG,
            command=lambda: self._on_navigate(SETTINGS_ITEM["key"]),
        )
        settings_btn.grid(
            row=base_row + 1, column=0, padx=10, pady=2, sticky="ew"
        )
        self._buttons[SETTINGS_ITEM["key"]] = settings_btn

        ctk.CTkOptionMenu(
            self,
            values=["Light", "Dark", "System"],
            variable=ctk.StringVar(value="System"),
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_HEADING),
            command=lambda mode: ctk.set_appearance_mode(mode),
        ).grid(row=base_row + 2, column=0, padx=14, pady=(6, 18), sticky="ew")

    def set_active(self, active_key: str) -> None:
        for key, btn in self._buttons.items():
            if key == active_key:
                btn.configure(fg_color=AppColors.NAV_ACTIVE_BG)
            else:
                btn.configure(fg_color=AppColors.NAV_DEFAULT_BG)


# ===========================================================================
# Header Bar
# ===========================================================================

class HeaderBar(ctk.CTkFrame):
    """Top header bar displaying active screen titles."""

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

    def set_screen(self, screen_key: str) -> None:
        ar, en = SCREEN_HEADERS.get(screen_key, ("", ""))
        self._label_ar.configure(text=ar)
        self._label_en.configure(text=en)


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
        self._build_screens()
        self._show_screen("home")

    def _on_tkinter_error(self, exc, val, tb):
        system_logger.error("Unhandled exception in Tkinter callback:", exc_info=(exc, val, tb))

    def _setup_window(self) -> None:
        self.title("نظام إدارة الشهادات  —  Certificate Manager")
        self.geometry(f"{AppSizes.WINDOW_WIDTH}x{AppSizes.WINDOW_HEIGHT}")
        self.minsize(AppSizes.MIN_WIDTH, AppSizes.MIN_HEIGHT)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        self._sidebar = Sidebar(self, on_navigate=self._show_screen)
        self._sidebar.grid(row=0, column=1, sticky="nsew")

        content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
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
        self._screens: dict[str, ctk.CTkFrame] = {
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


# ===========================================================================
# Entry Point
# ===========================================================================

if __name__ == "__main__":
    try:
        app = CertificateManagerApp()
        app.mainloop()
        logger.info("Application closed normally.")
    except Exception:
        system_logger.exception("A critical error occurred that caused the application to crash:")
        sys.exit(1)