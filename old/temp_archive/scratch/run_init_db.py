import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from sync_engine import init_local_db
init_local_db()
print("init_local_db called.")
