# =============================================================================
# nicegui_ui/state.py — Application & User Session State Management
# =============================================================================

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

log = logging.getLogger(__name__)


@dataclass
class UserSessionState:
    """
    Session state for the currently logged-in user.
    Tracks employee ID (EMP_ID), user credentials/role, and active UI preferences.
    Supports 3 appearance modes (Dark, Light, System) and 5 accent colors.
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
        """Apply active theme mode to NiceGUI dark_mode controller."""
        try:
            from nicegui import ui
            mode = self.theme_mode
            dark_controller = ui.dark_mode()
            if mode == "dark":
                dark_controller.enable()
            elif mode == "light":
                dark_controller.disable()
            else:
                dark_controller.auto()
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
            log.warning("Could not fetch user appearance on login: %s", exc)

        self.apply_theme_mode()


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
