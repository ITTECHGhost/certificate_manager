from pathlib import Path
import sys
from db import backup_db

try:
    print("Testing backup_db...")
    backup_db(Path("backup_pre_float_fix.sql"))
    print("Backup completed successfully!")
except Exception as e:
    print(f"Error during backup: {e}", file=sys.stderr)
