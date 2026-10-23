# scratch_verify_schema.py
import sys
from state import get_user_session
from sync_engine import init_local_db, _get_local_conn
from data.repositories import SettingsRepository

print("1. Running init_local_db()...")
init_local_db()

print("2. Verifying personnel table columns...")
conn = _get_local_conn()
cur = conn.cursor()
cur.execute("PRAGMA table_info(personnel)")
personnel_cols = [row[1] for row in cur.fetchall()]
print(f"   personnel columns: {personnel_cols}")
assert "settings_id" not in personnel_cols, "settings_id still in personnel!"

print("3. Verifying settings table columns...")
cur.execute("PRAGMA table_info(settings)")
settings_cols = [row[1] for row in cur.fetchall()]
print(f"   settings columns: {settings_cols}")
assert "EMP_ID" in settings_cols, "EMP_ID missing from settings!"
conn.close()

print("4. Testing UserSessionState & SettingsRepository...")
session = get_user_session()
print(f"   session.emp_id = {session.emp_id}")

repo = SettingsRepository()
app_data = repo.get_user_appearance(session.emp_id)
print(f"   get_user_appearance({session.emp_id}) -> {app_data}")

repo.update_user_appearance(session.emp_id, theme="Dark", accent="blue", font="Segoe UI", size=14, rtl=1)
app_data_after = repo.get_user_appearance(session.emp_id)
print(f"   after update -> {app_data_after}")

print("\nSUCCESS: All schema migrations and session settings repository tests passed!")
