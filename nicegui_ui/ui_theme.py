# =============================================================================
# nicegui_ui/ui_theme.py — Centralized Theme Tokens & Utilities
# =============================================================================

import sys
import winreg
import logging
from typing import Optional

log = logging.getLogger(__name__)


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
ACCENT_OPTIONS: list[str] = ["blue", "green", "red", "orange", "purple"]


class Styles:
    """
    Pre-composed class strings: CSS hook classes (visual) + Tailwind utilities (structural).
    """
    BODY       = "m-0 p-0 overflow-hidden select-none"
    LAYOUT_ROW = "w-full max-w-full h-screen flex-nowrap m-0 p-0 gap-0 overflow-hidden"

    SIDEBAR_COL_EXPANDED = "app-sidebar w-64 h-full p-0 justify-between shrink-0"
    SIDEBAR_COL_COLLAPSED = "app-sidebar w-20 h-full p-0 justify-between shrink-0 items-center"
    SIDEBAR_HEADER    = "app-sidebar-header w-full h-16 px-4 flex items-center justify-between shrink-0"
    SIDEBAR_NAV_GROUP = "w-full flex-1 overflow-y-auto p-3 gap-1"
    SIDEBAR_APP_TITLE = "app-sidebar-title text-lg font-bold tracking-wide"

    _NAV      = "w-full items-center gap-3 px-3.5 py-2.5 rounded-xl border cursor-pointer"
    NAV_ITEM_ACTIVE   = f"{_NAV} app-nav-item--active"
    NAV_ITEM_INACTIVE = f"{_NAV} app-nav-item"

    _NAV_MINI = "w-full justify-center items-center py-2.5 rounded-xl border cursor-pointer"
    NAV_ITEM_MINI_ACTIVE   = f"{_NAV_MINI} app-nav-item--active"
    NAV_ITEM_MINI_INACTIVE = f"{_NAV_MINI} app-nav-item"

    USER_CHIP      = "app-user-chip w-full items-center gap-3 p-3 rounded-xl border cursor-pointer"
    USER_CHIP_MINI = "app-user-chip w-full justify-center p-3 rounded-xl border cursor-pointer"
    USER_ICON          = "app-sidebar-icon"
    USER_NAME          = "app-sidebar-text text-sm font-semibold leading-tight truncate"
    USER_STATUS_ONLINE = "app-user-status text-xs font-medium leading-tight"

    HEADER_BAR = "app-header-bar w-full h-16 px-6 flex items-center justify-between shrink-0"

    MAIN_SCROLL = "app-main-area flex-1 min-w-0 max-w-full h-full p-5 overflow-x-hidden"
    MAIN_COL    = "w-full max-w-full min-w-0 gap-5 overflow-hidden"

    PAGE_HEADER_ROW  = "w-full justify-between items-end"
    PAGE_TITLE_COL   = "gap-1"
    PAGE_TITLE_LABEL = "app-text-primary text-3xl font-semibold tracking-tight"
    PAGE_SUB_LABEL   = "app-text-muted text-sm"

    CARD = "app-card w-full p-6 rounded-2xl gap-4"
    LOGIN_CARD = (
        "app-login-card login-card-glow w-[440px] max-w-full "
        "rounded-[24px] p-8 pt-10 gap-5 relative mt-8"
    )

    STAT_GRID     = "w-full grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4"
    STAT_CARD     = "app-stat-card p-5 rounded-2xl border gap-4"
    STAT_ICON_ROW = "w-full justify-between items-start"

    ACTION_BTN_BASE = (
        "w-full font-medium rounded-xl px-4 py-3 "
        "shadow-none outline-none normal-case justify-start"
    )
    ACTION_BTN_PRIMARY   = f"{ACTION_BTN_BASE} app-btn-primary"
    ACTION_BTN_SUCCESS   = f"{ACTION_BTN_BASE} app-btn-success"
    ACTION_BTN_SECONDARY = f"{ACTION_BTN_BASE} app-btn-secondary"

    ACTION_BTN_BLUE    = ACTION_BTN_PRIMARY
    ACTION_BTN_EMERALD = ACTION_BTN_SUCCESS
    ACTION_BTN_SLATE   = ACTION_BTN_SECONDARY

    REFRESH_BTN = "app-btn-secondary rounded-lg px-4 py-2 font-medium capitalize shadow-none outline-none"

    TABLE_CLASSES = "app-table w-full no-shadow border-none"

    BOTTOM_ROW    = "w-full gap-6 items-stretch flex-wrap xl:flex-nowrap"
    ACTIONS_PANEL = "app-card w-full xl:w-1/4 xl:max-w-[320px] p-5 rounded-2xl gap-3"
    ACTIONS_TITLE = "app-text-primary text-lg font-bold mb-2"
    TABLE_PANEL   = "app-card w-full xl:flex-1 min-w-0 p-6 rounded-2xl gap-2"
    TABLE_TITLE   = "app-text-primary text-lg font-bold mb-2"
    SETTINGS_CARD = CARD


# ── Navigation Config ───────────────────────────────────────────────────────
NAV_ITEMS: list[dict] = [
    {"key": "home",        "ar": "الرئيسية",       "en": "Dashboard",         "icon": "space_dashboard"},
    {"key": "students",    "ar": "الطلاب",          "en": "Students",          "icon": "people"},
    {"key": "orders",      "ar": "أوامر التخرج",    "en": "Graduation Orders", "icon": "school"},
    {"key": "departments", "ar": "الأقسام",         "en": "Departments",       "icon": "business"},
    {"key": "courses",     "ar": "المواد الدراسية", "en": "Courses",           "icon": "book"},
    {"key": "personnel",   "ar": "الكوادر",         "en": "Personnel",         "icon": "manage_accounts"},
    {"key": "certificate", "ar": "إصدار الوثيقة",   "en": "Issue Certificate", "icon": "print"},
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
        "label_ar": "سجل الشهادات الصادرة",
        "label_en": "Issued Certificates Log",
        "icon":   "workspace_premium",
        "target": "issued_certs",
    },
]


def set_dark_mode(enable: bool, dark_inst=None) -> None:
    """Enables or disables dark mode for Quasar."""
    from nicegui import ui
    
    # Persist the instance on the client to prevent Python garbage collection from destroying it on the frontend
    if dark_inst:
        dark = dark_inst
    else:
        if not getattr(ui.context.client, '_theme_dark_mode', None):
            setattr(ui.context.client, '_theme_dark_mode', ui.dark_mode())
        dark = getattr(ui.context.client, '_theme_dark_mode')

    if enable:
        dark.enable()
        ui.run_javascript("document.body.classList.add('dark', 'body--dark'); document.documentElement.classList.add('dark', 'body--dark');")
    else:
        dark.disable()
        ui.run_javascript("document.body.classList.remove('dark', 'body--dark'); document.documentElement.classList.remove('dark', 'body--dark');")


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
    font = (family or "Cairo").strip()
    ui.run_javascript(f"document.documentElement.style.setProperty('--font-primary', \"'{font}', 'Cairo', 'Roboto', 'Segoe UI', 'Tahoma', sans-serif\");")


def set_font_size(size_base: int) -> None:
    """Live-update base font size on document root element."""
    from nicegui import ui
    size = int(size_base or 14)
    ui.run_javascript(f"document.documentElement.style.setProperty('--font-size-base', '{size}px'); document.documentElement.style.fontSize = '{size}px';")


def set_rtl(enable: bool) -> None:
    """Live-update document layout direction (RTL / LTR) on document body and root element."""
    from nicegui import ui
    direction = "rtl" if enable else "ltr"
    ui.run_javascript(f"""
        document.documentElement.setAttribute('dir', '{direction}');
        document.body.setAttribute('dir', '{direction}');
        document.documentElement.style.direction = '{direction}';
        document.body.style.direction = '{direction}';
        if (window.Quasar && window.Quasar.lang) {{
            window.Quasar.lang.set({{ rtl: {'true' if enable else 'false'} }});
        }}
    """)


def inject_global_styles(is_rtl: Optional[bool] = None):
    """Reads theme.css and injects Tailwind config and global styles into the page head following user preferences."""
    from nicegui import ui
    from nicegui_ui.state import app_session
    import os

    if is_rtl is None:
        try:
            is_rtl = bool(app_session.preferences.get("is_arabic_rtl", 1))
        except Exception:
            is_rtl = True

    dir_val = 'rtl' if is_rtl else 'ltr'
    js_bool = 'true' if is_rtl else 'false'

    css_path = os.path.join(os.path.dirname(__file__), 'theme.css')
    try:
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        ui.add_head_html(f"""
        <script>
        document.documentElement.setAttribute('dir', '{dir_val}');
        if (document.body) {{
            document.body.setAttribute('dir', '{dir_val}');
            document.body.style.direction = '{dir_val}';
        }}
        document.documentElement.style.direction = '{dir_val}';
        window.tailwind = window.tailwind || {{}};
        window.tailwind.config = window.tailwind.config || {{}};
        window.tailwind.config.darkMode = ['class', '.body--dark'];
        if (window.Quasar && window.Quasar.lang) {{
            window.Quasar.lang.set({{ rtl: {js_bool} }});
        }}
        </script>
        <style>
        {css}
        </style>
        """)
    except Exception as exc:
        log.warning(f"[inject_global_styles] Error loading theme.css: {exc}")
