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
#   3. Creates the main window with sidebar navigation
#   4. Instantiates all screens and handles switching between them
#
# WHAT THIS FILE DOES NOT DO:
#   • No SQL — all queries are in data/queries.py
#   • No widget styling — all constants are in config.py
#   • No screen-specific logic — each screen is in screens/
#
# PROJECT STRUCTURE:
#   main.py              ← this file (entry point + window shell)
#   db.py                ← database connection + initialization
#   config.py            ← all constants: colors, fonts, sizes, nav items
#   data/queries.py      ← all SQL queries as typed functions
#   ui/base_screen.py    ← abstract base class all screens inherit from
#   ui/widgets.py        ← reusable widget factory functions
#   screens/
#       home_screen.py        ← dashboard
#       placeholder_screen.py ← placeholder for unbuilt screens
#
# =============================================================================

import customtkinter as ctk
from db import init_db
from config import (
    AppColors, AppFonts, AppSizes,
    NAV_ITEMS, SETTINGS_ITEM, SCREEN_HEADERS,
)
from screens.home_screen import HomeScreen
from screens.placeholder_screen import PlaceholderScreen
from screens.departments_screen import DepartmentsScreen
from screens.personal_screen import PersonalScreen
from screens.courses_screen import CoursesScreen
from screens.graduation_orders_screen import GraduationOrdersScreen
from screens.students_screen import StudentsScreen
from screens.order_students_screen import OrderStudentsScreen
from screens.history_screen import HistoryScreen
from screens.certificate_screen1 import CertificateScreen

# ---------------------------------------------------------------------------
# Global appearance — must be set before any CTk widget is created
# ---------------------------------------------------------------------------
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


# ===========================================================================
# Sidebar
# ===========================================================================

class Sidebar(ctk.CTkFrame):
    """
    Right-side navigation panel.

    Responsibilities:
        • Display app title and subtitle
        • Render one nav button per item in config.NAV_ITEMS
        • Render a settings button at the bottom
        • Highlight the currently active nav button
        • Provide a light/dark mode toggle
    """

    def __init__(self, parent: ctk.CTk, on_navigate) -> None:
        """
        Args:
            parent:      The root CTk window.
            on_navigate: Callback called with a screen key when a button
                         is clicked. Signature: on_navigate(key: str)
        """
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
        """Construct all sidebar widgets."""
        self._build_title()
        self._build_nav_buttons()
        self._build_settings_and_toggle()

    def _build_title(self) -> None:
        """App title and subtitle at the top of the sidebar."""
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

        # Divider below title
        ctk.CTkFrame(self, height=1, fg_color=AppColors.DIVIDER).grid(
            row=2, column=0, sticky="ew", padx=14, pady=(0, 8)
        )

    def _build_nav_buttons(self) -> None:
        """One navigation button per item in config.NAV_ITEMS."""
        for row_offset, item in enumerate(NAV_ITEMS):
            btn = ctk.CTkButton(
                self,
                text=f"{item['icon']}  {item['ar']}",
                font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_BODY),
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

        # Push everything below to the bottom of the sidebar
        self.grid_rowconfigure(len(NAV_ITEMS) + 3, weight=1)

    def _build_settings_and_toggle(self) -> None:
        """Settings button and appearance toggle at the bottom."""
        base_row = len(NAV_ITEMS) + 4

        # Divider above settings
        ctk.CTkFrame(self, height=1, fg_color=AppColors.DIVIDER).grid(
            row=base_row, column=0, sticky="ew", padx=14, pady=(0, 4)
        )

        # Settings button
        settings_btn = ctk.CTkButton(
            self,
            text=f"{SETTINGS_ITEM['icon']}  {SETTINGS_ITEM['ar']}",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
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

        # Light / Dark / System toggle
        ctk.CTkOptionMenu(
            self,
            values=["Light", "Dark", "System"],
            variable=ctk.StringVar(value="System"),
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_TINY),
            command=lambda mode: ctk.set_appearance_mode(mode),
        ).grid(row=base_row + 2, column=0, padx=14, pady=(6, 18), sticky="ew")

    def set_active(self, active_key: str) -> None:
        """
        Highlight the button for the active screen key and
        reset all others to their default (transparent) style.

        Args:
            active_key: The screen key that is now active.
        """
        for key, btn in self._buttons.items():
            if key == active_key:
                btn.configure(fg_color=AppColors.NAV_ACTIVE_BG)
            else:
                btn.configure(fg_color=AppColors.NAV_DEFAULT_BG)


# ===========================================================================
# Header Bar
# ===========================================================================

class HeaderBar(ctk.CTkFrame):
    """
    Top header bar that displays the name of the currently active screen.
    Updates automatically when screens change.
    """

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
        # Arabic title (right-aligned)
        self._label_ar = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(
                family=AppFonts.FAMILY,
                size=AppFonts.SIZE_SUBHEADING,
                weight="bold",
            ),
            anchor="e",
        )
        self._label_ar.grid(row=0, column=0, sticky="e", padx=(0, 20), pady=12)

        # English title (left-aligned, muted)
        self._label_en = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family=AppFonts.FAMILY, size=AppFonts.SIZE_SMALL),
            text_color=AppColors.TEXT_MUTED,
            anchor="w",
        )
        self._label_en.grid(row=0, column=0, sticky="w", padx=(20, 0), pady=12)

    def set_screen(self, screen_key: str) -> None:
        """
        Update the displayed titles to match the given screen key.

        Args:
            screen_key: Must be a key in config.SCREEN_HEADERS.
        """
        ar, en = SCREEN_HEADERS.get(screen_key, ("", ""))
        self._label_ar.configure(text=ar)
        self._label_en.configure(text=en)


# ===========================================================================
# Main Application Window
# ===========================================================================

class CertificateManagerApp(ctk.CTk):
    """
    Root application window.

    Window layout (RTL — sidebar on the RIGHT):
    ┌─────────────────────────────┬──────────────────┐
    │  Header Bar                 │                  │
    ├─────────────────────────────┤  Sidebar         │
    │  Screen Content Area        │  (col 1)         │
    │  (col 0, expands)           │                  │
    └─────────────────────────────┴──────────────────┘

    Navigation pattern:
        All screens are instantiated once at startup and stored in
        self._screens. Switching screens raises the target frame to
        the top of the Z-order (tkraise), then calls refresh() on it
        to load fresh data from the database.
    """

    def __init__(self) -> None:
        super().__init__()
        self._setup_window()
        init_db()
        self._build_layout()
        self._build_screens()
        self._show_screen("home")       # start on the home / dashboard screen

    # -------------------------------------------------------------------------
    # Window setup
    # -------------------------------------------------------------------------

    def _setup_window(self) -> None:
        """Configure the root window size, title, and minimum dimensions."""
        self.title("نظام إدارة الشهادات  —  Certificate Manager")
        self.geometry(f"{AppSizes.WINDOW_WIDTH}x{AppSizes.WINDOW_HEIGHT}")
        self.minsize(AppSizes.MIN_WIDTH, AppSizes.MIN_HEIGHT)

    # -------------------------------------------------------------------------
    # Layout assembly
    # -------------------------------------------------------------------------

    def _build_layout(self) -> None:
        """
        Set up the two-column grid and place the sidebar, header, and
        content slot. The sidebar is col 1 (right), content is col 0 (left).
        """
        # col 0 = content (expands), col 1 = sidebar (fixed)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar (right) -------------------------------------------------
        self._sidebar = Sidebar(self, on_navigate=self._show_screen)
        self._sidebar.grid(row=0, column=1, sticky="nsew")

        # --- Content frame (left) --------------------------------------------
        content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        content_frame.grid(row=0, column=0, sticky="nsew")
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(1, weight=1)

        # Header bar (top of content area)
        self._header = HeaderBar(content_frame)
        self._header.grid(row=0, column=0, sticky="ew")

        # Screen slot — all screen frames stack here, one visible at a time
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

    # -------------------------------------------------------------------------
    # Screen management
    # -------------------------------------------------------------------------

    def _build_screens(self) -> None:
        """
        Instantiate every screen once and grid them all into the same cell
        of the screen slot. Only one is visible at a time (controlled by
        tkraise() in _show_screen).

        To add a new screen:
            1. Import the class at the top of this file
            2. Add a new entry to self._screens below
            3. Add its nav item to config.NAV_ITEMS
        """
        self._screens: dict[str, ctk.CTkFrame] = {
            "home": HomeScreen(
                self._screen_slot,
                switch_callback=self._show_screen,
            ),
            "students": StudentsScreen(
                self._screen_slot, self._show_screen,
            ),
            "orders": GraduationOrdersScreen(
                self._screen_slot, self._show_screen,
            ),
            "order_students": OrderStudentsScreen(
                self._screen_slot, self._show_screen,
            ),
            "departments": DepartmentsScreen(
                self._screen_slot, self._show_screen,
            ),
            "courses": CoursesScreen(
                self._screen_slot, self._show_screen,
            ),
            "personal": PersonalScreen(
                self._screen_slot, self._show_screen,
            ),
            "certificate": CertificateScreen(
                self._screen_slot, self._show_screen,
            ),
            "history": HistoryScreen(
                self._screen_slot, self._show_screen,
            ),
            "settings": PlaceholderScreen(
                self._screen_slot, self._show_screen, "الإعدادات", "Settings"
            ),
        }

        # Wire the View Students callback on the orders screen
        orders_screen: GraduationOrdersScreen = self._screens["orders"]
        orders_screen.set_view_students_callback(self._open_order_students)

        # Grid all screens into the same cell — Z-order determines visibility
        for screen in self._screens.values():
            screen.grid(row=0, column=0, sticky="nsew")

    def _show_screen(self, key: str) -> None:
        if key not in self._screens:
            return
        self._screens[key].tkraise()
        self._screens[key].refresh()
        self._header.set_screen(key)
        self._sidebar.set_active(key)

    def _open_order_students(self, order: dict) -> None:
        """Navigate to the order-students sub-screen for a given order."""
        sub: OrderStudentsScreen = self._screens["order_students"]
        sub.set_order(order, back_callback=lambda: self._show_screen("orders"))
        self._show_screen("order_students")


# ===========================================================================
# Entry Point
# ===========================================================================

if __name__ == "__main__":
    app = CertificateManagerApp()
    app.mainloop()
