# =============================================================================
# nicegui_screens/settings_screen.py — compatibility shim
# =============================================================================
# The Settings screen lives in nicegui_screens/settings/ (one mixin per section).
# This module keeps the old import path and every name it used to expose.

from nicegui_screens.settings.screen import (  # noqa: F401
    SettingsScreen,
    ALL_PERMISSION_KEYS,
    TEMPLATE_ABBREVIATIONS,
    TEMPLATE_REGISTRY,
    UI,
)
from nicegui_screens.settings.server import (  # noqa: F401
    _SYNC_KIND_LABELS,
    _friendly_sync_reason,
    _summarize_sync_payload,
)
