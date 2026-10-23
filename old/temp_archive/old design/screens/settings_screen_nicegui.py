# =============================================================================
# screens/settings_screen_nicegui.py — Backwards Compatibility Alias
# =============================================================================
#
# SettingsScreen in screens/settings_screen.py is now the canonical NiceGUI
# settings implementation. This alias ensures any legacy references continue
# to work seamlessly.
#
# =============================================================================

from screens.settings_screen import SettingsScreen

# Backwards compatibility alias
SettingsScreenNiceGUI = SettingsScreen
