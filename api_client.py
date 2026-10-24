# =============================================================================
# api_client.py — Shared HTTP client for every call to the FastAPI server
#
# One place for: connection reuse (keep-alive), HTTPS verification with the
# college CA, the application key header, and safe automatic retries.
# Use api_client.get/post/put/patch/delete exactly like requests.get/... .
# =============================================================================

import threading

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import api_config

APP_NAME = "certificate_manager"

# One Session per thread: requests.Session is not guaranteed thread-safe, and
# NiceGUI runs network calls on several worker threads.
_local = threading.local()


def _build_session() -> requests.Session:
    session = requests.Session()
    # Retry only when the connection could not be made, or for idempotent methods
    # (GET/PUT/DELETE...). POST is never retried, so a write is never sent twice.
    retry = Retry(total=2, connect=2, read=1, status=0, backoff_factor=0.2, raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=8)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _session() -> requests.Session:
    session = getattr(_local, "session", None)
    if session is None:
        session = _build_session()
        _local.session = session
    return session


def _prepare(kwargs: dict) -> dict:
    settings = api_config.get_client_settings()
    headers = dict(kwargs.pop("headers", None) or {})
    headers.setdefault("X-App-Name", APP_NAME)
    if settings["app_key"]:
        headers.setdefault("X-App-Key", settings["app_key"])
    kwargs["headers"] = headers
    kwargs.setdefault("verify", settings["verify"])
    return kwargs


def request(method: str, url: str, **kwargs) -> requests.Response:
    """Send a request to the API through this thread's shared session."""
    return _session().request(method, url, **_prepare(kwargs))


def get(url: str, **kwargs) -> requests.Response:
    return request("GET", url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    return request("POST", url, **kwargs)


def put(url: str, **kwargs) -> requests.Response:
    return request("PUT", url, **kwargs)


def patch(url: str, **kwargs) -> requests.Response:
    return request("PATCH", url, **kwargs)


def delete(url: str, **kwargs) -> requests.Response:
    return request("DELETE", url, **kwargs)
