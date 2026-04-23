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
    SIZE_TITLE          = 22
    SIZE_HEADING        = 18
    SIZE_SUBHEADING     = 16
    SIZE_BODY           = 13
    SIZE_SMALL          = 12
    SIZE_TINY           = 11


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
    {"key": "personal",    "ar": "الكوادر",         "en": "Personal",         "icon": "👨‍💼"},
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
    {"db_table": "personal",    "ar": "الكوادر", "en": "Personal",
     "icon": "👨‍💼", "color": AppColors.ACCENT_PURPLE,
     "filter": "WHERE is_active = 1"},
]

HOME_QUICK_ACTIONS: list[dict] = [
    {"ar": "👤  إضافة طالب جديد", "en": "Add New Student",   "target": "students"},
    {"ar": "📜  إصدار وثيقة",      "en": "Issue Certificate", "target": "certificate"},
    {"ar": "📚  إضافة مادة دراسية","en": "Add New Course",    "target": "courses"},
]
