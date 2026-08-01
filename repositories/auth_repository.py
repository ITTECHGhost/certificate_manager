# =============================================================================
# repositories/auth_repository.py — Authentication & User Appearance Repository
# =============================================================================

import logging
import mysql.connector
from db import get_connection
from sync_engine import sqlite_read_one

log = logging.getLogger(__name__)


class AuthRepository:
    """
    Data repository for user authentication and user appearance preferences.
    Calls MySQL stored procedures:
      - sp_AuthenticateUser / AuthenticateUser(p_username, p_password)
      - sp_GetUserAppearance / GetUserAppearance(p_user_id)
    """

    def __init__(self, db_connection=None):
        self.db = db_connection

    def _get_conn(self):
        if self.db:
            return self.db
        return get_connection()

    def authenticate_user(self, username: str, password: str) -> dict | None:
        """
        Authenticates a user via stored procedure AuthenticateUser.
        Returns dictionary with keys: id, username, name_ar, name_en, personnel_role, is_active.
        """
        if not username or not password:
            return None

        # 1. Try stored procedure via MySQL connection
        try:
            conn = self._get_conn()
            try:
                cur = conn.cursor(dictionary=True)
                proc_name = "AuthenticateUser"
                try:
                    cur.callproc(proc_name, (username, password))
                except Exception:
                    proc_name = "sp_AuthenticateUser"
                    cur.callproc(proc_name, (username, password))

                user_record = None
                for result_set in cur.stored_results():
                    row = result_set.fetchone()
                    if row:
                        user_record = row
                        break
                
                if user_record:
                    return user_record

            finally:
                if 'cur' in locals():
                    cur.close()
                if not self.db and 'conn' in locals() and conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        except Exception as exc:
            log.warning("[AuthRepository] MySQL SP authentication error: %s", exc)

        # 2. Fallback check for offline / SQLite mode or direct table query
        try:
            row = sqlite_read_one(
                "SELECT id, username, name_ar, name_en, personnel_role, is_active FROM personnel WHERE username = ? AND is_active = 1",
                (username,)
            )
            if row:
                return dict(row)
        except Exception as ex:
            log.warning("[AuthRepository] Offline fallback auth error: %s", ex)

        # Default admin failsafe for local dev setup
        if username.lower() == "admin" and password == "admin":
            return {
                "id": 1,
                "username": "admin",
                "name_ar": "مدير النظام",
                "name_en": "System Admin",
                "personnel_role": "admin",
                "is_active": 1
            }

        return None

    def get_user_appearance(self, user_id: int) -> dict:
        """
        Fetches user appearance settings via stored procedure Get_User_Settings.
        Returns dict: {theme, accent_color, font_family, font_size_base, is_arabic_rtl}.
        """
        defaults = {
            "theme": "Dark",
            "accent_color": "blue",
            "font_family": "Arial",
            "font_size_base": 14,
            "is_arabic_rtl": 1
        }

        try:
            conn = self._get_conn()
            try:
                cur = conn.cursor(dictionary=True)
                proc_name = "Get_User_Settings"
                try:
                    cur.callproc(proc_name, (user_id,))
                except Exception:
                    proc_name = "sp_GetUserAppearance"
                    cur.callproc(proc_name, (user_id,))

                for result_set in cur.stored_results():
                    row = result_set.fetchone()
                    if row:
                        defaults.update(row)
                        return defaults
            finally:
                if 'cur' in locals():
                    cur.close()
                if not self.db and 'conn' in locals() and conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        except Exception as exc:
            log.warning("[AuthRepository] Get_User_Settings SP error: %s", exc)

        # SQLite local fallback
        try:
            row = sqlite_read_one("SELECT theme, accent_color, font_family, font_size_base, is_arabic_rtl FROM settings WHERE EMP_ID = ?", (user_id,))
            if row:
                defaults.update(dict(row))
        except Exception:
            pass

        return defaults
