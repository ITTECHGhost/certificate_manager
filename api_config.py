import json
from pathlib import Path

CONFIG_FILE = Path("server_config.json")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 2030

def load_server_config() -> dict:
    """Loads local server API configuration from server_config.json."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                host = str(data.get("host", DEFAULT_HOST)).replace("http://", "").replace("https://", "").strip().rstrip("/")
                port = int(data.get("port", DEFAULT_PORT))
                secret = str(data.get("secret", "certificate_manager_secret_key"))
                timeout = float(data.get("timeout", 5.0))
                auto_sync = bool(data.get("auto_sync", True))
                return {
                    "host": host,
                    "port": port,
                    "secret": secret,
                    "timeout": timeout,
                    "auto_sync": auto_sync,
                    "api_url": f"http://{host}:{port}"
                }
        except Exception:
            pass
    return {
        "host": DEFAULT_HOST,
        "port": DEFAULT_PORT,
        "secret": "certificate_manager_secret_key",
        "timeout": 5.0,
        "auto_sync": True,
        "api_url": f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
    }

def save_server_config(host: str, port: int | str, secret: str = "certificate_manager_secret_key", timeout: float = 5.0, auto_sync: bool = True) -> dict:
    """Saves server API configuration locally to server_config.json."""
    clean_host = str(host).replace("http://", "").replace("https://", "").strip().rstrip("/")
    clean_port = int(port)
    cfg = {
        "host": clean_host,
        "port": clean_port,
        "secret": secret,
        "timeout": float(timeout),
        "auto_sync": bool(auto_sync),
        "api_url": f"http://{clean_host}:{clean_port}"
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception as exc:
        print(f"[api_config] Failed to save server_config.json: {exc}")

    # Update module-level globals dynamically
    global API_HOST, API_PORT, API_URL
    API_HOST = cfg["host"]
    API_PORT = cfg["port"]
    API_URL = cfg["api_url"]

    return cfg

# Load initial configuration from local server_config.json
_cfg = load_server_config()
API_HOST = _cfg["host"]
API_PORT = _cfg["port"]
API_URL = _cfg["api_url"]

def get_api_url() -> str:
    """Returns the current dynamic API URL."""
    return API_URL

