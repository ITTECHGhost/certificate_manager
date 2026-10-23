import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from sync_engine import set_online
from data.repositories import SettingsRepository

set_online(False)
settings = SettingsRepository().get_settings()
print(f"Settings retrieved offline: {settings}")
keys = list(settings.keys())
print(f"Keys present: {keys}")
