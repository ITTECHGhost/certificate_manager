# =============================================================================
# state.py — Application & User Session State Management
# =============================================================================
#
# Provides a clean `UserSessionState` data structure tracking the logged-in user
# (EMP_ID), credentials, role, and active UI preferences (Theme, RTL, Font Size).
#
# Usage:
#   from state import get_user_session
#   
#   session = get_user_session()
#   emp_id = session.emp_id
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

    def update_preferences(
        self,
        theme: Optional[str] = None,
        accent_color: Optional[str] = None,
        font_family: Optional[str] = None,
        font_size_base: Optional[int] = None,
        is_arabic_rtl: Optional[int] = None
    ) -> None:
        """Update active session preferences in memory."""
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

    def login_user(self, user_id: int) -> None:
        """Set active logged in user ID."""
        self.emp_id = user_id


# Global session singleton
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

