# =============================================================================
# nicegui_ui/ui_theme.py — NiceGUI UI Theme Constants & Accent Palettes
# =============================================================================

class Colors:
    """Centralized hex color palette for the NiceGUI UI."""

    BG_MAIN       = "#0f172a"   # slate-900
    BG_SIDEBAR    = "#020617"   # slate-950
    BG_SURFACE    = "#1e293b"   # slate-800

    LIGHT_BG_MAIN    = "#f1f5f9"   # slate-100
    LIGHT_BG_SIDEBAR = "#0f172a"   # slate-900
    LIGHT_BG_SURFACE = "#ffffff"   # white

    BORDER_DARK   = "#334155"   # slate-700
    BORDER_LIGHT  = "#cbd5e1"   # slate-300

    BLUE_TEXT     = "#60a5fa"
    BLUE_BG       = "rgba(59,130,246,0.1)"
    BLUE_BORDER   = "rgba(59,130,246,0.2)"
    BLUE_BTN      = "#2563eb"

    EMERALD_TEXT  = "#34d399"
    EMERALD_BG    = "rgba(16,185,129,0.1)"

    AMBER_TEXT    = "#fbbf24"
    AMBER_BG      = "rgba(245,158,11,0.1)"

    PURPLE_TEXT   = "#c084fc"
    PURPLE_BG     = "rgba(168,85,247,0.1)"

    ONLINE        = "#10b981"
    OFFLINE       = "#ef4444"


# ── 5 Dynamic Accent Color Palettes ────────────────────────────────────────

ACCENT_PALETTES: dict[str, dict[str, str]] = {
    "blue": {
        "primary_btn": "bg-blue-600 hover:bg-blue-500 text-white",
        "primary_text": "text-blue-600 dark:text-blue-400",
        "bg_soft": "bg-blue-500/10",
        "border_soft": "border-blue-500/20",
        "active_nav": "bg-blue-600/20 text-blue-400 border-blue-500/50",
        "hex": "#2563eb",
    },
    "green": {
        "primary_btn": "bg-emerald-600 hover:bg-emerald-500 text-white",
        "primary_text": "text-emerald-600 dark:text-emerald-400",
        "bg_soft": "bg-emerald-500/10",
        "border_soft": "border-emerald-500/20",
        "active_nav": "bg-emerald-600/20 text-emerald-400 border-emerald-500/50",
        "hex": "#059669",
    },
    "red": {
        "primary_btn": "bg-rose-600 hover:bg-rose-500 text-white",
        "primary_text": "text-rose-600 dark:text-rose-400",
        "bg_soft": "bg-rose-500/10",
        "border_soft": "border-rose-500/20",
        "active_nav": "bg-rose-600/20 text-rose-400 border-rose-500/50",
        "hex": "#e11d48",
    },
    "dark_blue": {
        "primary_btn": "bg-indigo-700 hover:bg-indigo-600 text-white",
        "primary_text": "text-indigo-600 dark:text-indigo-400",
        "bg_soft": "bg-indigo-500/10",
        "border_soft": "border-indigo-500/20",
        "active_nav": "bg-indigo-600/20 text-indigo-400 border-indigo-500/50",
        "hex": "#4338ca",
    },
    "orange": {
        "primary_btn": "bg-orange-500 hover:bg-orange-400 text-white",
        "primary_text": "text-orange-600 dark:text-orange-400",
        "bg_soft": "bg-orange-500/10",
        "border_soft": "border-orange-500/20",
        "active_nav": "bg-orange-500/20 text-orange-400 border-orange-500/50",
        "hex": "#f97316",
    },
}


def get_accent_palette(accent_name: str = "blue") -> dict[str, str]:
    """Return theme classes dictionary for the requested accent color name."""
    normalized = (accent_name or "blue").lower().replace("-", "_").replace(" ", "_")
    return ACCENT_PALETTES.get(normalized, ACCENT_PALETTES["blue"])


class Typography:
    """Tailwind CSS typography class tokens."""

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


class Styles:
    """
    Pre-composed Tailwind utility strings with responsive Light + Dark classes.
    """

    BODY = (
        "bg-slate-100 dark:bg-slate-900 text-slate-900 dark:text-slate-200 "
        "m-0 p-0 overflow-hidden font-sans select-none transition-colors duration-200"
    )

    LAYOUT_ROW = "w-full h-screen flex-nowrap m-0 p-0 gap-0"

    SIDEBAR_COL_EXPANDED = (
        "w-64 h-full bg-slate-900 dark:bg-slate-950 "
        "border-r border-slate-800 p-0 justify-between shrink-0 transition-all duration-300"
    )
    SIDEBAR_COL_COLLAPSED = (
        "w-20 h-full bg-slate-900 dark:bg-slate-950 "
        "border-r border-slate-800 p-0 justify-between shrink-0 items-center transition-all duration-300"
    )
    SIDEBAR_HEADER = (
        "w-full h-16 border-b border-slate-800 px-4 flex items-center justify-between shrink-0"
    )
    SIDEBAR_NAV_GROUP  = "w-full flex-1 overflow-y-auto p-3 gap-1"
    SIDEBAR_APP_TITLE  = f"{Typography.APP_TITLE} text-white tracking-wide"

    NAV_ITEM_BASE    = "w-full items-center gap-3 px-3.5 py-2.5 rounded-xl border cursor-pointer transition-all"
    NAV_ITEM_ACTIVE  = f"{NAV_ITEM_BASE} bg-blue-600/20 text-blue-400 border-blue-500/50"
    NAV_ITEM_INACTIVE= f"{NAV_ITEM_BASE} bg-transparent text-slate-400 hover:bg-slate-800/50 hover:text-slate-200 border-transparent"
    
    NAV_ITEM_MINI_BASE    = "w-full justify-center items-center py-2.5 rounded-xl border cursor-pointer transition-all"
    NAV_ITEM_MINI_ACTIVE  = f"{NAV_ITEM_MINI_BASE} bg-blue-600/20 text-blue-400 border-blue-500/50"
    NAV_ITEM_MINI_INACTIVE= f"{NAV_ITEM_MINI_BASE} bg-transparent text-slate-400 hover:bg-slate-800/50 hover:text-slate-200 border-transparent"

    USER_CHIP = (
        "w-full items-center gap-3 p-3 bg-slate-800/40 rounded-xl "
        "border border-slate-800/60 cursor-pointer hover:bg-slate-800/80 transition-colors"
    )
    USER_CHIP_MINI = (
        "w-full justify-center p-3 bg-slate-800/40 rounded-xl "
        "border border-slate-800/60 cursor-pointer hover:bg-slate-800/80 transition-colors"
    )
    USER_ICON  = "text-slate-400"
    USER_NAME  = f"text-slate-200 {Typography.USER_NAME}"
    USER_STATUS_ONLINE = f"text-emerald-500 {Typography.USER_STATUS}"

    HEADER_BAR = (
        "w-full h-16 !bg-white dark:!bg-slate-950 border-b border-slate-200 dark:border-slate-800 "
        "px-6 flex items-center justify-between shrink-0 transition-colors duration-200"
    )

    MAIN_SCROLL = "flex-1 h-full bg-slate-100 dark:bg-slate-900 p-5 transition-colors duration-200"
    MAIN_COL    = "w-full gap-5"

    PAGE_HEADER_ROW  = "w-full justify-between items-end"
    PAGE_TITLE_COL   = "gap-1"
    PAGE_TITLE_LABEL = f"{Typography.PAGE_TITLE} text-slate-900 dark:text-white"
    PAGE_SUB_LABEL   = f"{Typography.PAGE_SUBTITLE} text-slate-600 dark:text-slate-400"

    REFRESH_BTN = (
        "bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-300 "
        "hover:bg-slate-300 dark:hover:bg-slate-700 "
        "outline-none shadow-none rounded-lg px-4 py-2 font-medium capitalize transition-colors"
    )

    CARD = (
        "p-6 !bg-white dark:!bg-[#1e293b] rounded-2xl border border-slate-200 "
        "dark:border-slate-800 shadow-md dark:shadow-xl gap-4 transition-colors duration-200"
    )

    STAT_GRID  = "w-full gap-5"
    STAT_CARD  = (
        "p-5 !bg-white dark:!bg-[#1e293b] rounded-2xl border border-slate-200 "
        "dark:border-slate-800 shadow-md dark:shadow-xl gap-4 transition-colors duration-200"
    )
    STAT_ICON_ROW = "w-full justify-between items-start"
    STAT_VALUE = f"{Typography.STAT_VALUE} text-slate-900 dark:text-white"
    STAT_LABEL = f"{Typography.STAT_LABEL} text-slate-700 dark:text-slate-300"

    BOTTOM_ROW = "w-full gap-6 items-stretch"

    ACTIONS_PANEL = (
        "p-6 !bg-white dark:!bg-[#1e293b] "
        "rounded-2xl border border-slate-200 dark:border-slate-800 gap-4 shadow-md dark:shadow-xl transition-colors duration-200"
    )
    ACTIONS_TITLE = f"{Typography.SECTION_HEAD} text-slate-900 dark:text-white mb-2"

    ACTION_BTN_BASE = (
        "w-full text-white font-medium rounded-xl px-4 py-3 "
        "shadow-none outline-none normal-case justify-start"
    )
    ACTION_BTN_BLUE    = f"{ACTION_BTN_BASE} bg-blue-600 hover:bg-blue-500"
    ACTION_BTN_EMERALD = f"{ACTION_BTN_BASE} bg-emerald-600 hover:bg-emerald-500"
    ACTION_BTN_SLATE   = f"{ACTION_BTN_BASE} bg-slate-700 hover:bg-slate-600"

    TABLE_PANEL = (
        "p-6 !bg-white dark:!bg-[#1e293b] "
        "rounded-2xl border border-slate-200 dark:border-slate-800 shadow-md dark:shadow-xl gap-2 transition-colors duration-200"
    )
    TABLE_TITLE  = f"{Typography.SECTION_HEAD} text-slate-900 dark:text-white mb-2"
    TABLE_CLASSES = "w-full bg-transparent text-slate-900 dark:text-slate-300 no-shadow border-none"

    SETTINGS_CARD = (
        "w-full p-6 !bg-white dark:!bg-[#1e293b] rounded-2xl border border-slate-200 "
        "dark:border-slate-800 shadow-md dark:shadow-xl gap-6 transition-colors duration-200"
    )

    LOGIN_CARD = (
        "rounded-[24px] p-8 pt-10 gap-5 "
        "transition-all duration-300 login-card-glow login-card-container relative mt-8"
    )


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
    {
        "label":      "Total Students",
        "count_key":  "total_students",
        "icon":       "people",
        "text_color": "text-blue-600 dark:text-blue-400",
        "icon_bg":    "bg-blue-500/10 border-blue-500/20",
    },
    {
        "label":      "Departments",
        "count_key":  "total_departments",
        "icon":       "domain",
        "text_color": "text-emerald-600 dark:text-emerald-400",
        "icon_bg":    "bg-emerald-500/10 border-emerald-500/20",
    },
    {
        "label":      "Courses",
        "count_key":  "total_courses",
        "icon":       "menu_book",
        "text_color": "text-amber-600 dark:text-amber-400",
        "icon_bg":    "bg-amber-500/10 border-amber-500/20",
    },
    {
        "label":      "Personnel",
        "count_key":  "total_personnel",
        "icon":       "badge",
        "text_color": "text-purple-600 dark:text-purple-400",
        "icon_bg":    "bg-purple-500/10 border-purple-500/20",
    },
]

QUICK_ACTIONS: list[dict] = [
    {
        "label":   "Add New Student",
        "icon":    "person_add",
        "style":   Styles.ACTION_BTN_BLUE,
        "target":  "students",
    },
    {
        "label":   "Issue Certificate",
        "icon":    "workspace_premium",
        "style":   Styles.ACTION_BTN_EMERALD,
        "target":  "certificate",
    },
    {
        "label":   "Generate Report",
        "icon":    "summarize",
        "style":   Styles.ACTION_BTN_SLATE,
        "target":  None,
    },
]

def inject_global_styles():
    """Reads theme.css and injects it cleanly into head."""
    from nicegui import ui
    import os
    
    css_path = os.path.join(os.path.dirname(__file__), 'theme.css')
    try:
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()
            
        ui.add_head_html(f"<style>{css}</style>")
        ui.add_head_html('''
            <script>
                tailwind.config = {
                    darkMode: ['class', '.body--dark'],
                }
            </script>
        ''')
    except Exception as e:
        print(f"[Theme] Failed to load theme.css: {e}")

