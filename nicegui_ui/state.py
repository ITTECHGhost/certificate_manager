# =============================================================================
# nicegui_ui/state.py — Application & User Session State Management
# =============================================================================

import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

log = logging.getLogger(__name__)


def log_state(tag: str, data: dict) -> None:
    """Log debug state snapshots to logger instead of dumping print blocks to terminal stdout."""
    try:
        formatted_json = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        log.debug("[DEBUG: %s] %s", tag, formatted_json)
    except Exception as err:
        log.debug("[DEBUG: %s] %s (Formatting error: %s)", tag, data, err)


@dataclass
class UserSessionState:
    """
    Session state for the currently logged-in user.
    Tracks employee ID (EMP_ID), user credentials/role, and active UI preferences.
    Supports 3 appearance modes (Dark, Light, System) and 6 accent colors.
    """
    emp_id: int = 1
    username: str = "admin"
    name_ar: str = "مدير النظام"
    name_en: str = "Admin User"
    role: str = "admin"
    is_active: bool = True
    preferences: Dict[str, Any] = field(default_factory=lambda: {
        "theme": "Dark",
        "accent_color": "blue",
        "font_family": "Segoe UI",
        "font_size_base": 13,
        "is_arabic_rtl": 1
    })

    def save(self) -> None:
        """Persist current state to NiceGUI browser local storage."""
        try:
            from nicegui import app
            app.storage.user['session_state'] = {
                'emp_id': self.emp_id,
                'username': self.username,
                'name_ar': self.name_ar,
                'name_en': self.name_en,
                'role': self.role,
                'is_active': self.is_active,
                'preferences': self.preferences
            }
        except Exception:
            pass

    def load(self) -> None:
        """Restore state from NiceGUI browser local storage if available."""
        try:
            from nicegui import app
            state = app.storage.user.get('session_state')
            if state:
                self.emp_id = state.get('emp_id', self.emp_id)
                self.username = state.get('username', self.username)
                self.name_ar = state.get('name_ar', self.name_ar)
                self.name_en = state.get('name_en', self.name_en)
                self.role = state.get('role', self.role)
                self.is_active = state.get('is_active', self.is_active)
                self.preferences = state.get('preferences', self.preferences)
        except Exception:
            pass

    @property
    def theme_mode(self) -> str:
        """Return normalized appearance mode ('dark', 'light', or 'system')."""
        val = str(self.preferences.get("theme", "Dark")).lower()
        if val in {"dark", "dark mode"}:
            return "dark"
        if val in {"light", "light mode"}:
            return "light"
        return "system"

    @property
    def accent_color(self) -> str:
        """Return normalized accent color name."""
        return str(self.preferences.get("accent_color", "blue")).lower().replace("-", "_")

    def apply_theme_mode(self) -> None:
        """Apply active user preference theme mode, accent color, font family, font size, and layout direction to NiceGUI."""
        try:
            from nicegui_ui.ui_theme import is_windows_dark_mode, set_dark_mode, set_accent, set_font_family, set_font_size, set_rtl
            mode = self.theme_mode
            if mode == "dark":
                set_dark_mode(True)
            elif mode == "light":
                set_dark_mode(False)
            else:
                set_dark_mode(is_windows_dark_mode())

            # Sync accent palette CSS class on body
            set_accent(self.accent_color)

            # Sync font family and font size
            font_family = str(self.preferences.get("font_family") or "Segoe UI")
            font_size = int(self.preferences.get("font_size_base") or 13)
            set_font_family(font_family)
            set_font_size(font_size)

            # Sync RTL layout direction
            rtl = bool(self.preferences.get("is_arabic_rtl", 1))
            set_rtl(rtl)
        except Exception as exc:
            log.warning("Could not apply theme mode: %s", exc)

    def update_preferences(
        self,
        theme: Optional[str] = None,
        accent_color: Optional[str] = None,
        font_family: Optional[str] = None,
        font_size_base: Optional[int] = None,
        is_arabic_rtl: Optional[int] = None
    ) -> None:
        """Update active session preferences in memory and apply live theme mode."""
        if theme is not None:
            self.preferences["theme"] = theme
        if accent_color is not None:
            self.preferences["accent_color"] = accent_color
        if font_family is not None:
            self.preferences["font_family"] = font_family
        if font_size_base is not None:
            self.preferences["font_size_base"] = font_size_base
        if is_arabic_rtl is not None:
            self.preferences["is_arabic_rtl"] = is_arabic_rtl

        self.apply_theme_mode()
        self.save()

    def login_user(self, user_id: int, user_record: Optional[Dict[str, Any]] = None) -> None:
        """
        Set active logged in user ID, fetch user appearance preferences from database settings table,
        and apply active theme mode.
        """
        self.emp_id = user_id
        if user_record:
            self.username = user_record.get("username", self.username)
            self.name_ar = user_record.get("name_ar", self.name_ar)
            self.name_en = user_record.get("name_en", self.name_en)
            self.role = user_record.get("personnel_role", self.role)

        appearance = {}
        try:
            from data.repositories import SettingsRepository
            appearance = SettingsRepository().get_user_appearance(user_id)
            if appearance:
                self.preferences.update({
                    "theme": appearance.get("theme", "Dark"),
                    "accent_color": appearance.get("accent_color", "blue"),
                    "font_family": appearance.get("font_family", "Segoe UI"),
                    "font_size_base": appearance.get("font_size_base", 13),
                    "is_arabic_rtl": appearance.get("is_arabic_rtl", 1)
                })
        except Exception as exc:
            log.error("[login_user] Failed to fetch user appearance preferences for user %s: %s", user_id, exc, exc_info=True)

        # Explicitly synchronize NiceGUI's dark mode controller with the fetched theme preference
        try:
            from nicegui import ui
            fetched_theme = str(self.preferences.get("theme", "Dark")).strip().title()
            if fetched_theme == "Dark":
                ui.dark_mode().enable()
            elif fetched_theme == "Light":
                ui.dark_mode().disable()
            elif fetched_theme == "System":
                ui.dark_mode().auto()
        except Exception as dm_err:
            log.warning("Could not sync ui.dark_mode() in login_user: %s", dm_err)

        self.apply_theme_mode()

        # Log SESSION_INIT debug state snapshot
        dark_mode_val = None
        try:
            from nicegui import ui
            dark_mode_val = getattr(ui.dark_mode(), 'value', None)
        except Exception:
            pass

        log_state("SESSION_INIT", {
            "user_id": user_id,
            "mysql_fetched_settings": appearance,
            "app_session_preferences": dict(self.preferences),
            "ui_dark_mode_value": dark_mode_val
        })
        self.save()

    def logout_user(self) -> None:
        """Reset active user session data back to default state."""
        try:
            from utils.logger import log_activity
            log_activity(f"User '{self.username}' (ID: {self.emp_id}) logged out successfully using function app_session.logout_user()", "INFO")
        except Exception:
            pass

        self.emp_id = 1
        self.username = "admin"
        self.name_ar = "مدير النظام"
        self.name_en = "Admin User"
        self.role = "admin"
        self.is_active = False
        self.save()


_current_session: Optional[UserSessionState] = None


def get_user_session() -> UserSessionState:
    """Return the active UserSessionState singleton."""
    global _current_session
    if _current_session is None:
        _current_session = UserSessionState()
    return _current_session


def set_user_session(session: UserSessionState) -> None:
    """Set the active UserSessionState singleton."""
    global _current_session
    _current_session = session


app_session = get_user_session()
