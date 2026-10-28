
import json
from pathlib import Path

import app_paths

CONFIG_FILE = app_paths.data_path("server_config.json")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 2030
DEFAULT_CA_CERT = "certs/college_ca.crt"


def _build_url(scheme: str, host: str, port: int) -> str:
    return f"{scheme}://{host}:{port}"


def _split_host(raw_host: str, default_scheme: str = "http") -> tuple[str, str]:
    """Accept 'host', 'http://host' or 'https://host' and return (scheme, clean_host)."""
    text = str(raw_host or "").strip()
    scheme = default_scheme
    if text.lower().startswith("https://"):
        scheme = "https"
    elif text.lower().startswith("http://"):
        scheme = "http"
    clean = text.replace("http://", "").replace("https://", "").strip().rstrip("/")
    return scheme, clean or DEFAULT_HOST


def _read_config_file() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            pass
    return {}


def load_server_config() -> dict:
    """Loads local server API configuration from server_config.json."""
    data = _read_config_file()
    scheme = str(data.get("scheme") or "http").lower()
    scheme, host = _split_host(data.get("host", DEFAULT_HOST), scheme if scheme in ("http", "https") else "http")
    try:
        port = int(data.get("port", DEFAULT_PORT))
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    try:
        timeout = float(data.get("timeout", 5.0))
    except (TypeError, ValueError):
        timeout = 5.0
    return {
        "host": host,
        "port": port,
        "scheme": scheme,
        "secret": str(data.get("secret", "certificate_manager_secret_key")),
        "timeout": timeout,
        "auto_sync": bool(data.get("auto_sync", True)),
        # HTTPS: certificate of the college CA used to verify the server (path relative to the app folder)
        "ca_cert": str(data.get("ca_cert") or DEFAULT_CA_CERT),
        # Application key sent to FastAPI in the X-App-Key header
        "app_key": str(data.get("app_key") or ""),
        "api_url": _build_url(scheme, host, port),
    }


def save_server_config(host: str, port: int | str, secret: str = "certificate_manager_secret_key", timeout: float = 5.0, auto_sync: bool = True) -> dict:
    """Saves server API configuration locally to server_config.json (keeps scheme, CA and app key settings)."""
    existing = _read_config_file()
    scheme, clean_host = _split_host(host, str(existing.get("scheme") or "http").lower())
    clean_port = int(port)
    cfg = dict(existing)
    cfg.update({
        "host": clean_host,
        "port": clean_port,
        "scheme": scheme,
        "secret": secret,
        "timeout": float(timeout),
        "auto_sync": bool(auto_sync),
        "api_url": _build_url(scheme, clean_host, clean_port),
    })
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception as exc:
        print(f"[api_config] Failed to save server_config.json: {exc}")

    _apply(load_server_config())
    return cfg


def _apply(cfg: dict) -> None:
    """Update module-level globals from a loaded config."""
    global API_HOST, API_PORT, API_URL, _client_cfg
    API_HOST = cfg["host"]
    API_PORT = cfg["port"]
    API_URL = cfg["api_url"]
    _client_cfg = cfg


# Load initial configuration from local server_config.json
_client_cfg: dict = {}
_apply(load_server_config())


def get_api_url() -> str:
    """Returns the current dynamic API URL."""
    return API_URL


def get_client_settings() -> dict:
    """Settings the shared HTTP client needs: TLS verification and the application key."""
    cfg = _client_cfg
    verify: bool | str = True
    if cfg.get("scheme") == "https":
        ca_path = _find_ca_cert(cfg.get("ca_cert") or DEFAULT_CA_CERT)
        # Trust only the college CA when its certificate is available
        verify = str(ca_path) if ca_path else True
    return {"verify": verify, "app_key": cfg.get("app_key", "")}


def _find_ca_cert(ca_cert: str) -> Path | None:
    """Locate the college CA file. The laptop's own copy (next to server_config.json / the
    program) wins over the copy built into the program, so a new server CA can be installed
    by copying one file, without a new build."""
    path = Path(ca_cert)
    if path.is_absolute():
        return path if path.exists() else None
    candidates = [app_paths.DATA_DIR / path, app_paths.INSTALL_DIR / path, app_paths.RESOURCE_DIR / path]
    return next((c for c in candidates if c.exists()), None)
