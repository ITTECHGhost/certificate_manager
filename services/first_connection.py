# =============================================================================
# services/first_connection.py — Connect a new laptop to the server
#
# A fresh install has only the example server_config.json (127.0.0.1, no app key),
# so the program cannot reach the server and every login falls back to the empty
# offline cache: nobody can log in. This module tells that state apart and imports
# the server's client_package (server_config.json + certs/college_ca.crt) into the
# data folder, so IT can log in with a server account on the first start.
# Never logs or returns the app key or the secret.
# =============================================================================

import json
import os
import shutil
from pathlib import Path

import api_config
import app_paths

PLACEHOLDER_KEY = "ask-the-server-admin-for-this-key"
_LOOPBACK = {"127.0.0.1", "localhost", "::1", ""}


def is_configured(raw: dict | None = None) -> bool:
    """True when server_config.json points at a real server: a real app key, or a
    host other than this machine (a server in audit mode needs no key)."""
    data = api_config._read_config_file() if raw is None else raw
    key = str(data.get("app_key") or "").strip()
    if key and key != PLACEHOLDER_KEY:
        return True
    _, host = api_config._split_host(str(data.get("host") or ""))
    return host.lower() not in _LOOPBACK


def candidate_folders() -> list[Path]:
    """Places a client_package folder is usually copied to."""
    home = Path.home()
    places = [app_paths.INSTALL_DIR, app_paths.DATA_DIR, home / "Desktop", home / "Downloads", home / "Documents"]
    if os.environ.get("USERPROFILE"):
        places.append(Path(os.environ["USERPROFILE"]) / "OneDrive" / "Desktop")
    return [p / "client_package" for p in places]


def find_client_package() -> Path | None:
    """The first known folder that holds a client_package server_config.json."""
    for folder in candidate_folders():
        if (folder / "server_config.json").is_file():
            return folder
    return None


def _normalize_folder(folder: str | Path) -> Path:
    """Accept the client_package folder, its parent, or the server_config.json file itself."""
    path = Path(str(folder).strip().strip('"'))
    if path.is_file():
        path = path.parent
    if not (path / "server_config.json").is_file() and (path / "client_package" / "server_config.json").is_file():
        path = path / "client_package"
    return path


def import_client_package(folder: str | Path) -> tuple[bool, str]:
    """Copy server_config.json (and certs/college_ca.crt when present) into the data
    folder and switch the running program to it. Returns (ok, Arabic message)."""
    src = _normalize_folder(folder)
    cfg_file = src / "server_config.json"
    if not cfg_file.is_file():
        return False, "لم يُعثر على الملف server_config.json في هذا المجلد."
    try:
        data = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
    except Exception:
        return False, "الملف server_config.json تالف أو غير مقروء."
    if not isinstance(data, dict) or not is_configured(data):
        return False, "الملف server_config.json لا يحتوي على عنوان السيرفر أو مفتاح البرنامج."

    target = app_paths.data_path("server_config.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)

    ca_src = src / "certs" / "college_ca.crt"
    if ca_src.is_file():
        ca_dst = app_paths.DATA_DIR / api_config.DEFAULT_CA_CERT
        ca_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ca_src, ca_dst)

    reload_config()
    return True, f"تم ربط الجهاز بالسيرفر {api_config.get_api_url()}"


def save_address(host: str, port: int | str) -> tuple[bool, str]:
    """Typed address (no app key: only while the server is in audit mode)."""
    host = (host or "").strip()
    if not host or " " in host or '"' in host:
        return False, "اكتب عنوان السيرفر بشكل صحيح."
    try:
        port_num = int(str(port).strip())
        if not 0 < port_num < 65536:
            raise ValueError
    except ValueError:
        return False, "رقم المنفذ غير صحيح."
    data = api_config._read_config_file()
    if str(data.get("app_key") or "") == PLACEHOLDER_KEY:
        data["app_key"] = ""
        target = app_paths.data_path("server_config.json")
        target.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
    if "://" not in host:
        host = f"https://{host}"
    api_config.save_server_config(host=host, port=port_num, secret=str(data.get("secret") or "certificate_manager_secret_key"))
    return True, f"تم حفظ عنوان السيرفر {api_config.get_api_url()}"


def reload_config() -> None:
    api_config._apply(api_config.load_server_config())


def check_and_set_online() -> bool:
    """Ping the configured server and update the program's online flag."""
    from sync_engine import check_network_status, set_online
    online = bool(check_network_status())
    set_online(online)
    return online
