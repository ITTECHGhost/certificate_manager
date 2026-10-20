# =============================================================================
# repositories/auth_repository.py — Authentication & User Appearance Repository
# =============================================================================

import logging
from utils.logger import log_activity, log_system

log = logging.getLogger(__name__)


class AuthRepository:
    """
    Data repository for user authentication and user appearance preferences.
    Delegates to PersonnelRepository and SettingsRepository for unified,
    offline-aware authentication and theme handling complying with Rule 15.
    """

    def __init__(self, db_connection=None):
        self.db = db_connection

    def authenticate_user(self, username: str, password: str) -> dict | None:
        """
        Authenticates a user via PersonnelRepository.
        Supports online API authentication and secure offline SQLite verification.
        """
        if not username or not password:
            log_activity("Authentication attempted with empty username or password", "WARNING")
            return None

        from data.repositories import PersonnelRepository
        repo = PersonnelRepository()
        return repo.authenticate(username, password)

    def get_user_appearance(self, user_id: int) -> dict:
        """
        Fetches user appearance settings via SettingsRepository.
        Returns dict: {theme, accent_color, font_family, font_size_base, is_arabic_rtl}.
        """
        from data.repositories import SettingsRepository
        repo = SettingsRepository()
        appearance = repo.get_user_appearance(user_id)
        if appearance:
            return appearance

        return {
            "theme": "Dark",
            "accent_color": "blue",
            "font_family": "Segoe UI",
            "font_size_base": 13,
            "is_arabic_rtl": 1
        }

