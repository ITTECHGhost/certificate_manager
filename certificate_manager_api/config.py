# =============================================================================
# config.py — MySQL login for the FastAPI server
#
# The login lives in db_config.json next to this file. That file is never in git.
# Template: db_config.example.json. setup_server.bat creates the real file.
# (The old CustomTkinter theme code that lived here is in old/root_duplicates/.)
# =============================================================================

import json
from pathlib import Path

DB_CONFIG_FILE = Path(__file__).resolve().parent / "db_config.json"


def load_db_settings(path: Path = DB_CONFIG_FILE) -> dict:
    """Read the MySQL login from db_config.json and return host, user, password and database."""
    if not path.exists():
        raise RuntimeError(f"db_config.json missing at {path} - run setup_server.bat (or copy db_config.example.json)")
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    return {
        "host": str(data.get("host", "localhost")),
        "user": str(data["user"]),
        "password": str(data["password"]),
        "database": str(data.get("database", "certificate_manager")),
    }


class DBConfig:
    """MySQL login used by db.py, main.py and hash_existing_passwords.py."""
    _settings = load_db_settings()
    DB_HOST = _settings["host"]
    DB_USER = _settings["user"]
    DB_PASSWORD = _settings["password"]
    DB_NAME = _settings["database"]
