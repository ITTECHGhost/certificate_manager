# =============================================================================
# nicegui_ui/ui_theme.py — Centralized Theme Tokens & Utilities
#
# This module provides:
#   - Styles: structural layout tokens (widths, padding, flex, grid) + CSS hook
#     class names. All visual styling (colors, backgrounds, borders, shadows)
#     lives in theme.css via CSS custom properties.
#   - Typography: structural font-size/weight tokens only.
#   - set_dark_mode() / set_accent(): live theme + accent switching.
#   - inject_global_styles(): injects theme.css + Tailwind config into page head.
#   - is_windows_dark_mode(): OS mode detection.
# =============================================================================

import sys
import winreg


def is_windows_dark_mode() -> bool:
    """Detects if Windows OS app mode is set to Dark mode (AppsUseLightTheme = 0)."""
    if sys.platform != "win32":
        return False
    try:
        registry_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_path) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
    except Exception:
        return False


class Typography:
    """Structural typography tokens (sizes and weights only — no colors)."""

    APP_TITLE     = "text-lg font-bold"
    PAGE_TITLE    = "text-3xl font-semibold tracking-tight"
    PAGE_SUBTITLE = "text-sm"
    SECTION_HEAD  = "text-lg font-bold"
    STAT_VALUE    = "text-3xl font-extrabold"
    STAT_LABEL    = "text-sm font-semibold"
    NAV_LABEL     = "font-medium"
    USER_NAME     = "text-sm font-semibold leading-tight"
    USER_STATUS   = "text-xs font-medium leading-tight"
    BTN_TEXT      = "font-medium capitalize"


# ── Valid accent palette names ──────────────────────────────────────────────
ACCENT_OPTIONS: list[str] = ["blue", "green", "red", "dark-blue", "orange", "purple"]


class Styles:
    """
    Pre-composed class strings: CSS hook classes (visual) + Tailwind utilities (structural).

    CSS hook classes (app-*) handle all visual styling via CSS custom properties
    defined in theme.css. Tailwind classes handle structural layout only:
    width, height, padding, margin, gap, flex, grid, rounded, overflow, etc.
    """

    # ── Body & Layout ───────────────────────────────────────────────────────
    BODY       = "m-0 p-0 overflow-hidden select-none"
    LAYOUT_ROW = "w-full h-screen flex-nowrap m-0 p-0 gap-0"

    # ── Sidebar ─────────────────────────────────────────────────────────────
    SIDEBAR_COL_EXPANDED = (
        "app-sidebar w-64 h-full p-0 justify-between shrink-0"
    )
    SIDEBAR_COL_COLLAPSED = (
        "app-sidebar w-20 h-full p-0 justify-between shrink-0 items-center"
    )
    SIDEBAR_HEADER    = "app-sidebar-header w-full h-16 px-4 flex items-center justify-between shrink-0"
    SIDEBAR_NAV_GROUP = "w-full flex-1 overflow-y-auto p-3 gap-1"
    SIDEBAR_APP_TITLE = "app-sidebar-title text-lg font-bold tracking-wide"

    # ── Navigation Items ────────────────────────────────────────────────────
    _NAV      = "w-full items-center gap-3 px-3.5 py-2.5 rounded-xl border cursor-pointer"
    NAV_ITEM_ACTIVE   = f"{_NAV} app-nav-item--active"
    NAV_ITEM_INACTIVE = f"{_NAV} app-nav-item"

    _NAV_MINI = "w-full justify-center items-center py-2.5 rounded-xl border cursor-pointer"
    NAV_ITEM_MINI_ACTIVE   = f"{_NAV_MINI} app-nav-item--active"
    NAV_ITEM_MINI_INACTIVE = f"{_NAV_MINI} app-nav-item"

<<<<<<< HEAD
    HEADER_BAR = (
        "w-full h-16 !bg-white dark:!bg-slate-950 border-b border-slate-200 dark:border-slate-800 "
        "px-6 flex items-center justify-between shrink-0 transition-colors duration-200"
    )
=======
    # ── User Chip (sidebar) ─────────────────────────────────────────────────
    USER_CHIP      = "app-user-chip w-full items-center gap-3 p-3 rounded-xl border cursor-pointer"
    USER_CHIP_MINI = "app-user-chip w-full justify-center p-3 rounded-xl border cursor-pointer"
    USER_ICON          = "app-sidebar-icon"
    USER_NAME          = "app-sidebar-text text-sm font-semibold leading-tight truncate"
    USER_STATUS_ONLINE = "app-user-status text-xs font-medium leading-tight"
>>>>>>> 9562a1d23cd6479a6a3565da19e2625b4fc10329

    # ── Top Header Bar ──────────────────────────────────────────────────────
    HEADER_BAR = "app-header-bar w-full h-16 px-6 flex items-center justify-between shrink-0"

    # ── Main Content Area ───────────────────────────────────────────────────
    MAIN_SCROLL = "app-main-area flex-1 h-full p-5"
    MAIN_COL    = "w-full gap-5"

    # ── Page Header ─────────────────────────────────────────────────────────
    PAGE_HEADER_ROW  = "w-full justify-between items-end"
    PAGE_TITLE_COL   = "gap-1"
    PAGE_TITLE_LABEL = "app-text-primary text-3xl font-semibold tracking-tight"
    PAGE_SUB_LABEL   = "app-text-muted text-sm"

    # ── Cards ───────────────────────────────────────────────────────────────
    CARD = "app-card w-full p-6 rounded-2xl gap-4"
    LOGIN_CARD = (
        "app-login-card login-card-glow w-[440px] max-w-full "
        "rounded-[24px] p-8 pt-10 gap-5 relative mt-8"
    )

    # ── Stat Cards ──────────────────────────────────────────────────────────
    STAT_GRID     = "w-full gap-5"
    STAT_CARD     = "app-stat-card p-5 rounded-2xl border gap-4"
    STAT_ICON_ROW = "w-full justify-between items-start"

    # ── Action Buttons ──────────────────────────────────────────────────────
    ACTION_BTN_BASE = (
        "w-full font-medium rounded-xl px-4 py-3 "
        "shadow-none outline-none normal-case justify-start"
    )
    ACTION_BTN_PRIMARY   = f"{ACTION_BTN_BASE} app-btn-primary"
    ACTION_BTN_SUCCESS   = f"{ACTION_BTN_BASE} app-btn-success"
    ACTION_BTN_SECONDARY = f"{ACTION_BTN_BASE} app-btn-secondary"

    # Backward-compatible aliases
    ACTION_BTN_BLUE    = ACTION_BTN_PRIMARY
    ACTION_BTN_EMERALD = ACTION_BTN_SUCCESS
    ACTION_BTN_SLATE   = ACTION_BTN_SECONDARY

    # ── Refresh Button ──────────────────────────────────────────────────────
    REFRESH_BTN = "app-btn-secondary rounded-lg px-4 py-2 font-medium capitalize shadow-none outline-none"

    # ── Tables ──────────────────────────────────────────────────────────────
    TABLE_CLASSES = "app-table w-full no-shadow border-none"

    # ── Dashboard Panels ────────────────────────────────────────────────────
    BOTTOM_ROW    = "w-full gap-6 items-stretch"
    ACTIONS_PANEL = "app-card w-1/3 p-6 rounded-2xl gap-4"
    ACTIONS_TITLE = "app-text-primary text-lg font-bold mb-2"
    TABLE_PANEL   = "app-card w-full p-6 rounded-2xl gap-2"
    TABLE_TITLE   = "app-text-primary text-lg font-bold mb-2"

    # ── Settings ────────────────────────────────────────────────────────────
    SETTINGS_CARD = CARD


<<<<<<< HEAD
=======
# ── Navigation Config ───────────────────────────────────────────────────────

>>>>>>> 9562a1d23cd6479a6a3565da19e2625b4fc10329
NAV_ITEMS: list[dict] = [
    {"key": "home",        "ar": "الرئيسية",       "en": "Dashboard",         "icon": "space_dashboard"},
    {"key": "students",    "ar": "الطلاب",          "en": "Students",          "icon": "people"},
    {"key": "orders",      "ar": "أوامر التخرج",    "en": "Graduation Orders", "icon": "school"},
    {"key": "departments", "ar": "الأقسام",         "en": "Departments",       "icon": "domain"},
    {"key": "courses",     "ar": "المواد الدراسية", "en": "Courses",           "icon": "menu_book"},
    {"key": "personnel",   "ar": "الكوادر",         "en": "Personnel",         "icon": "badge"},
    {"key": "certificate", "ar": "إصدار الوثيقة",   "en": "Certificate",       "icon": "workspace_premium"},
    {"key": "history",     "ar": "سجل التغييرات",  "en": "History",           "icon": "history"},
    {"key": "settings",    "ar": "الإعدادات",       "en": "Settings",          "icon": "settings"},
]


STAT_CARDS: list[dict] = [
    {"label_ar": "إجمالي الطلاب", "label_en": "Total Students", "count_key": "total_students", "icon": "people",    "variant": "blue"},
    {"label_ar": "الأقسام",       "label_en": "Departments",    "count_key": "total_departments", "icon": "domain",  "variant": "emerald"},
    {"label_ar": "المواد الدراسية", "label_en": "Courses",        "count_key": "total_courses",  "icon": "menu_book",  "variant": "amber"},
    {"label_ar": "الكوادر",       "label_en": "Personnel",      "count_key": "total_personnel", "icon": "badge",     "variant": "purple"},
]


QUICK_ACTIONS: list[dict] = [
    {
        "label_ar": "إضافة طالب جديد",
        "label_en": "Add New Student",
        "icon":   "person_add",
        "target": "students",
    },
    {
        "label_ar": "إصدار وثيقة",
        "label_en": "Issue Certificate",
        "icon":   "workspace_premium",
        "target": "certificate",
    },
    {
        "label_ar": "توليد تقرير",
        "label_en": "Generate Report",
        "icon":   "summarize",
        "target": None,
    },
]


# ── Theme Switching Functions ───────────────────────────────────────────────

def set_dark_mode(enable: bool) -> None:
    """Enables or disables dark mode for Quasar and syncs the 'dark' CSS class to body and documentElement."""
    from nicegui import ui
    dark = ui.dark_mode()
    if enable:
        dark.enable()
        ui.run_javascript("document.body.classList.add('dark'); document.documentElement.classList.add('dark');")
    else:
        dark.disable()
        ui.run_javascript("document.body.classList.remove('dark'); document.documentElement.classList.remove('dark');")


def set_accent(accent_name: str) -> None:
    """Live-swap accent palette CSS class on body element for instant accent color change."""
    from nicegui import ui
    normalized = (accent_name or "blue").lower().replace(" ", "-").replace("_", "-")
    if normalized not in ACCENT_OPTIONS:
        normalized = "blue"
    css_class = f"accent-{normalized}"
    ui.run_javascript(f"""
        document.body.className = document.body.className.replace(/\\baccent-[a-z-]+\\b/g, '').trim();
        document.body.classList.add('{css_class}');
    """)


def set_font_family(family: str) -> None:
    """Live-update font family CSS custom property on document root."""
    from nicegui import ui
    font = (family or "Segoe UI").strip()
    ui.run_javascript(f"document.documentElement.style.setProperty('--font-primary', \"'{font}', 'Segoe UI', 'Tahoma', sans-serif\");")


def set_font_size(size_base: int) -> None:
    """Live-update base font size on document root element."""
    from nicegui import ui
    size = int(size_base or 13)
    ui.run_javascript(f"document.documentElement.style.fontSize = '{size}px';")


def inject_global_styles():
    """Reads theme.css and injects Tailwind config and global styles into the page head."""
    from nicegui import ui
    import os

    css_path = os.path.join(os.path.dirname(__file__), 'theme.css')
    try:
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        ui.add_head_html(f"""
        <script>
        window.tailwind = window.tailwind || {{}};
        window.tailwind.config = window.tailwind.config || {{}};
        window.tailwind.config.darkMode = ['class', '.body--dark'];
        </script>
        <style>
        {css}
        </style>
        """)
    except Exception as e:
        print(f"[Theme] Failed to load theme.css: {e}")

