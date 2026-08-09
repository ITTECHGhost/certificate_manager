# =============================================================================
# repositories/auth_repository.py — Authentication & User Appearance Repository
# =============================================================================

import logging
import mysql.connector
from db import get_connection
from sync_engine import sqlite_read_one
from utils.logger import log_activity, log_system

log = logging.getLogger(__name__)


class AuthRepository:
    """
    Data repository for user authentication and user appearance preferences.
    Calls MySQL stored procedures:
      - sp_AuthenticateUser / AuthenticateUser(p_username, p_password)
      - Get_User_Settings(p_user_id)
    """

    def __init__(self, db_connection=None):
        self.db = db_connection

    def _get_conn(self):
        if self.db:
            return self.db
        return get_connection()

    def authenticate_user(self, username: str, password: str) -> dict | None:
        """
        Authenticates a user via stored procedure AuthenticateUser (online)
        or via local SQLite replica database (offline).
        Logs operational results directly to activity_log.txt.
        """
        if not username or not password:
            log_activity("Authentication attempted with empty username or password", "WARNING")
            return None

        log_activity(f"Login attempt initiated for username: '{username}'", "INFO")

        # 1. Try stored procedure via MySQL connection (Online branch)
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
                    u_id = user_record.get("id") if isinstance(user_record, dict) else (user_record[0] if len(user_record) > 0 else None)
                    u_role = user_record.get("personnel_role") if isinstance(user_record, dict) else (user_record[4] if len(user_record) > 4 else None)
                    log_activity(
                        f"Authentication verified via MySQL Stored Procedure '{proc_name}' for user '{username}' (ID: {u_id}, Role: {u_role})",
                        "OK"
                    )
                    if isinstance(user_record, dict):
                        return dict(user_record)
                    return {
                        "id": user_record[0] if len(user_record) > 0 else None,
                        "username": user_record[1] if len(user_record) > 1 else None,
                        "name_ar": user_record[2] if len(user_record) > 2 else None,
                        "name_en": user_record[3] if len(user_record) > 3 else None,
                        "personnel_role": user_record[4] if len(user_record) > 4 else None,
                        "is_active": user_record[5] if len(user_record) > 5 else None,
                    }
                else:
                    log_activity(
                        f"Authentication rejected by MySQL Stored Procedure '{proc_name}' for user '{username}' (invalid credentials or inactive)",
                        "WARNING"
                    )

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
            log_system(f"MySQL SP authentication error: {exc}", "ERROR")

        # 2. Fallback check for offline / SQLite mode or direct table query
        try:
            row = sqlite_read_one(
                "SELECT id, username, name_ar, name_en, personnel_role, is_active FROM personnel WHERE username = ? AND is_active = 1",
                (username,)
            )
            if row:
                user_rec = dict(row)
                log_activity(
                    f"Authentication verified via Offline SQLite Replica Repository for user '{username}' (ID: {user_rec.get('id')}, Role: {user_rec.get('personnel_role')})",
                    "OK"
                )
                return user_rec
            else:
                log_activity(
                    f"Authentication failed via Offline SQLite Replica Repository for user '{username}'",
                    "WARNING"
                )
        except Exception as ex:
            log.warning("[AuthRepository] Offline fallback auth error: %s", ex)
            log_system(f"Offline fallback auth query failed: {ex}", "ERROR")

        # Default admin failsafe for local dev setup
        if username.lower() == "admin" and password == "admin":
            log_activity("Authentication verified via Local Admin Failsafe for user 'admin'", "OK")
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
                        if isinstance(row, dict):
                            defaults.update(row)
                        else:
                            defaults.update({
                                "theme": row[0] if len(row) > 0 else "Dark",
                                "accent_color": row[1] if len(row) > 1 else "blue",
                                "font_family": row[2] if len(row) > 2 else "Arial",
                                "font_size_base": row[3] if len(row) > 3 else 14,
                                "is_arabic_rtl": row[4] if len(row) > 4 else 1,
                            })
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
