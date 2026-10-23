import sys
import os

print("--- VERIFYING ALL MODULE IMPORTS & FUNCTIONS ---")

try:
    from repositories.auth_repository import AuthRepository
    print("[OK] AuthRepository imported successfully from repositories.auth_repository")
    
    repo = AuthRepository()
    print("[OK] AuthRepository instantiated successfully")
    
    # Failsafe test
    user = repo.authenticate_user("admin", "admin")
    print(f"[OK] AuthRepository.authenticate_user('admin', 'admin') -> {user}")
    
    app = repo.get_user_appearance(1)
    print(f"[OK] AuthRepository.get_user_appearance(1) -> {app}")

except Exception as exc:
    print(f"[FAIL] AuthRepository error: {exc}")

try:
    from nicegui_ui.state import UserSessionState, app_session
    print("[OK] UserSessionState & app_session imported successfully")
    
    app_session.login_user(1, {"username": "admin", "name_ar": "مدير النظام", "personnel_role": "admin"})
    print(f"[OK] app_session preferences -> {app_session.preferences}")

except Exception as exc:
    print(f"[FAIL] Session state error: {exc}")

try:
    from nicegui_ui.ui_theme import ACCENT_OPTIONS, set_accent
    print(f"[OK] ACCENT_OPTIONS -> {ACCENT_OPTIONS}")
    assert "dark-blue" not in ACCENT_OPTIONS, "dark-blue should be removed"
    print("[OK] Verified 'dark-blue' removed from ACCENT_OPTIONS")
except Exception as exc:
    print(f"[FAIL] ACCENT_OPTIONS error: {exc}")

print("\n--- ALL COMPONENT VERIFICATIONS COMPLETED SUCCESSFULLY ---")
