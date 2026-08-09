import sys
from pathlib import Path
import time

workspace_root = str(Path(__file__).resolve().parent.parent)
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

# 1. Test System Health Check (Startup)
from utils.health_check import run_system_health_checks
print("--- SIMULATING APP STARTUP ---")
run_system_health_checks()

time.sleep(1)

# 2. Test Login Authentication
from repositories.auth_repository import AuthRepository
print("\n--- SIMULATING LOGIN (User: admin) ---")
repo = AuthRepository()
user = repo.authenticate_user("admin", "admin")
if user:
    print(f"Login Success! Retrieved User ID: {user.get('id')}")
else:
    print("Login Failed!")

time.sleep(1)

print("\n--- SIMULATING LOGIN (User: 1) ---")
user_2 = repo.authenticate_user("1", "1")
if user_2:
    print(f"Login Success! Retrieved User ID: {user_2.get('id')}")
else:
    print("Login Failed!")
