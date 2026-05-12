# =============================================================================
# config.py — Application-wide Constants
# =============================================================================
#
# CHANGE LOG:
#   - Fixed period_type translations:
#       year     -> فصلي  /  Year-based
#       semester -> مقررات  /  Semester-based
#   - Removed study_years and period_type from department-level config
#
# =============================================================================


class DBConfig:
    DB_HOST = 'localhost'
    DB_USER = 'root'
    DB_PASSWORD = '12345678'
    DB_NAME = 'certificate_manager'

class AppColors:
    WINDOW_BG           = ("gray95",  "gray12")
    SIDEBAR_BG          = ("gray88",  "gray18")
    HEADER_BG           = ("gray93",  "gray17")
    CARD_BG             = ("white",   "gray22")
    CONTENT_BG          = "transparent"
    NAV_ACTIVE_BG       = ("gray78",  "gray28")
    NAV_HOVER_BG        = ("gray85",  "gray30")
    NAV_DEFAULT_BG      = "transparent"
    NAV_TEXT            = ("gray15",  "gray90")
    ACCENT_BLUE         = "#2196F3"
    ACCENT_GREEN        = "#4CAF50"
    ACCENT_ORANGE       = "#FF9800"
    ACCENT_PURPLE       = "#9C27B0"
    COLOR_SUCCESS       = "#4CAF50"
    COLOR_WARNING       = "#FF9800"
    COLOR_ERROR         = "#F44336"
    COLOR_INFO          = "#2196F3"
    BORDER              = "gray80"
    DIVIDER             = "gray75"
    TEXT_MUTED          = "gray55"


class AppFonts:
    FAMILY              = "Arial"
    BASE_SIZE           = 13
    
    # These will be properties or updated via refresh_config
    SIZE_TITLE          = 22
    SIZE_HEADING        = 18
    SIZE_SUBHEADING     = 16
    SIZE_BODY           = 13
    SIZE_SMALL          = 12
    SIZE_TINY           = 11

    @classmethod
    def update_sizes(cls, base: int):
        cls.BASE_SIZE = base
        cls.SIZE_TITLE      = int(base * 1.7)
        cls.SIZE_HEADING    = int(base * 1.4)
        cls.SIZE_SUBHEADING = int(base * 1.2)
        cls.SIZE_BODY       = base
        cls.SIZE_SMALL      = int(base * 0.9)
        cls.SIZE_TINY       = int(base * 0.8)

def refresh_config(user_id: int = None):
    """Load settings and appearance. Apply user-specific theme if user_id provided."""
    try:
        from data.repositories import SettingsRepository
        import customtkinter as ctk
        
        if user_id is not None:
            repo = SettingsRepository()
            appearance = repo.get_user_appearance(user_id)
        else:
            appearance = {
                "theme": "System",
                "accent_color": "blue",
                "font_family": "Arial",
                "font_size_base": 13
            }
        
        # Update Fonts
        AppFonts.FAMILY = appearance.get("font_family", "Arial")
        AppFonts.update_sizes(appearance.get("font_size_base", 13))
        
        # Update Theme
        ctk.set_appearance_mode(appearance.get("theme", "System"))
        
        accent = appearance.get("accent_color", "blue")
        if accent in ["orange", "purple", "red"]:
            import os, json
            theme_path = os.path.join(os.getcwd(), "themes", f"{accent}.json")
            if os.path.exists(theme_path):
                ctk.set_default_color_theme("blue")  # Load base first
                try:
                    with open(theme_path, "r", encoding="utf-8") as f:
                        custom = json.load(f)
                    
                    from customtkinter import ThemeManager
                    def deep_update(d, u):
                        for k, v in u.items():
                            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                                deep_update(d[k], v)
                            else:
                                d[k] = v
                    deep_update(ThemeManager.theme, custom)
                except Exception as e:
                    print(f"Error merging custom theme {accent}: {e}")
            else:
                ctk.set_default_color_theme("blue")
        else:
            ctk.set_default_color_theme(accent)
    except Exception:
        # Fallback to defaults if DB not ready
        AppFonts.update_sizes(13)


class AppSizes:
    WINDOW_WIDTH        = 1200
    WINDOW_HEIGHT       = 700
    MIN_WIDTH           = 1000
    MIN_HEIGHT          = 600
    SIDEBAR_WIDTH       = 230
    HEADER_HEIGHT       = 52
    NAV_BUTTON_HEIGHT   = 42
    ACTION_BUTTON_HEIGHT = 60
    SETTINGS_BTN_HEIGHT  = 38
    CORNER_RADIUS_CARD  = 12
    CORNER_RADIUS_BTN   = 8
    PAD_SCREEN          = 24
    PAD_SECTION         = 20
    PAD_INNER           = 10
    STAT_CARD_ICON_SIZE = 28
    STAT_CARD_COUNT_SIZE = 28


# Period type display labels
# year     = فصلي   / Year-based     (annual system)
# semester = مقررات / Semester-based (credit-hour system)
PERIOD_TYPE_OPTIONS: dict[str, str] = {
    "فصلي  /  Year-based":       "year",
    "مقررات  /  Semester-based": "semester",
}
PERIOD_TYPE_DISPLAY: dict[str, str] = {v: k for k, v in PERIOD_TYPE_OPTIONS.items()}


NAV_ITEMS: list[dict] = [
    {"key": "home",        "ar": "الرئيسية",       "en": "Home",             "icon": "🏠"},
    {"key": "students",    "ar": "الطلاب",          "en": "Students",         "icon": "👤"},
    {"key": "orders",      "ar": "أوامر التخرج",    "en": "Graduation Orders","icon": "🎓"},
    {"key": "departments", "ar": "الأقسام",         "en": "Departments",      "icon": "🏫"},
    {"key": "courses",     "ar": "المواد الدراسية", "en": "Courses",          "icon": "📚"},
    {"key": "personnel",   "ar": "الكوادر",         "en": "Personnel",        "icon": "👨‍💼"},
    {"key": "certificate", "ar": "إصدار الوثيقة",   "en": "Certificate",      "icon": "📜"},
    {"key": "history",     "ar": "سجل التغييرات",  "en": "History",          "icon": "📋"},
]

SETTINGS_ITEM: dict = {
    "key": "settings", "ar": "الإعدادات", "en": "Settings", "icon": "⚙️"
}

SCREEN_HEADERS: dict[str, tuple[str, str]] = {
    item["key"]: (item["ar"], item["en"])
    for item in NAV_ITEMS + [SETTINGS_ITEM]
}
SCREEN_HEADERS["order_students"] = ("طلاب الأمر", "Order Students")

HOME_STAT_CARDS: list[dict] = [
    {"db_table": "students",    "ar": "الطلاب",  "en": "Students",
     "icon": "👤", "color": AppColors.ACCENT_BLUE},
    {"db_table": "departments", "ar": "الأقسام", "en": "Departments",
     "icon": "🏫", "color": AppColors.ACCENT_GREEN},
    {"db_table": "courses",     "ar": "المواد",  "en": "Courses",
     "icon": "📚", "color": AppColors.ACCENT_ORANGE},
    {"db_table": "personnel",   "ar": "الكوادر", "en": "Personnel",
     "icon": "👨‍💼", "color": AppColors.ACCENT_PURPLE,
     "filter": "WHERE is_active = 1"},
]

HOME_QUICK_ACTIONS: list[dict] = [
    {"ar": "👤  إضافة طالب جديد", "en": "Add New Student",   "target": "students"},
    {"ar": "📜  إصدار وثيقة",      "en": "Issue Certificate", "target": "certificate"},
    {"ar": "📚  إضافة مادة دراسية","en": "Add New Course",    "target": "courses"},
]
