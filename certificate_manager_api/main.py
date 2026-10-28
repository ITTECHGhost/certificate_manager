"""Certificate Manager API: the FastAPI app, its startup, the app-key guard and the routers.

uvicorn runs `main:app` with this folder as the working directory. Every route lives in
routers/*.py; the include order below is the order requests are matched in, and
tests/snapshots/api_routes.json pins it.
"""
import os
import sys
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database on server startup...")
    try:
        from db import init_db
        init_db()
        logger.info("Database initialization successful.")
    except Exception as e:
        logger.error(f"Failed to initialize database on startup: {e}")
    yield


app = FastAPI(title="Certificate Manager API", lifespan=lifespan)
# GET /students/search was registered on this first-included router; it lives in routers/students.py
from routers.students import search_router as router  # noqa: E402
app.include_router(router)


# ---------------------------------------------------------------------------
# Application keys: FastAPI guards the database per PROGRAM, not per user.
# app_keys.json (next to this file, never in git):
#   {"enforce": false, "apps": {"certificate_manager": "<secret key>"}}
# enforce=false -> audit mode: requests without a valid key are logged, not blocked.
# enforce=true  -> requests without a valid X-App-Key header get 401.
# ---------------------------------------------------------------------------
import json as _json
import secrets as _secrets
from fastapi import Request
from fastapi.responses import JSONResponse

APP_KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_keys.json")
# Reachable without a key: the connectivity check only
APP_KEY_EXEMPT_PATHS = {"/ping"}


def _load_app_keys() -> dict:
    try:
        # utf-8-sig: also accepts a file saved by Notepad/PowerShell with a byte-order mark
        with open(APP_KEYS_FILE, "r", encoding="utf-8-sig") as f:
            data = _json.load(f)
        apps = {str(k): str(v) for k, v in (data.get("apps") or {}).items() if v}
        return {"enforce": bool(data.get("enforce", False)), "apps": apps}
    except FileNotFoundError:
        return {"enforce": False, "apps": {}}
    except Exception as exc:
        logger.error(f"Could not read {APP_KEYS_FILE}: {exc}")
        return {"enforce": False, "apps": {}}


_APP_KEYS = _load_app_keys()
_audit_seen: set = set()
logger.info(
    f"App keys: {len(_APP_KEYS['apps'])} program(s) registered, "
    f"mode={'ENFORCE' if _APP_KEYS['enforce'] else 'audit (not blocking)'}"
)


@app.middleware("http")
async def app_key_guard(request: Request, call_next):
    if request.url.path not in APP_KEY_EXEMPT_PATHS and _APP_KEYS["apps"]:
        sent = request.headers.get("X-App-Key", "")
        app_name = next((name for name, key in _APP_KEYS["apps"].items()
                         if sent and _secrets.compare_digest(sent, key)), None)
        if app_name is None:
            if _APP_KEYS["enforce"]:
                return JSONResponse(status_code=401, content={"detail": "Missing or invalid application key"})
            client = request.client.host if request.client else "?"
            if client not in _audit_seen:  # one warning per client address
                _audit_seen.add(client)
                logger.warning(f"[app-key audit] {client} called {request.url.path} without a valid X-App-Key "
                               f"(allowed in audit mode; would be blocked when enforce=true)")
        else:
            request.state.app_name = app_name
    return await call_next(request)

# Database configuration, the connection pool and the shared helpers live in deps.py.
# They are re-imported here so `from main import get_db` (routers/bulk_import.py) keeps working.
from deps import (  # noqa: E402,F401
    DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, get_db, decode_db_value,
    execute_sp_fetchall, execute_sp_fetchone, table_has_updated_at, _require_admin,
    _set_must_change_password, STATUS_STR_TO_INT, result_status_code,
)


try:
    from routers.bulk_import import router as bulk_import_router
    app.include_router(bulk_import_router)
except ImportError:
    try:
        from certificate_manager_api.routers.bulk_import import router as bulk_import_router
        app.include_router(bulk_import_router)
    except Exception as e:
        logger.warning(f"Could not load bulk_import_router: {e}")

try:
    from routers.updates import router as updates_router
    app.include_router(updates_router)
except ImportError:
    try:
        from certificate_manager_api.routers.updates import router as updates_router
        app.include_router(updates_router)
    except Exception as e:
        logger.warning(f"Could not load updates_router: {e}")

try:
    from routers.templates import router as templates_router
    app.include_router(templates_router)
except ImportError:
    try:
        from certificate_manager_api.routers.templates import router as templates_router
        app.include_router(templates_router)
    except Exception as e:
        logger.warning(f"Could not load templates_router: {e}")


# ---------------------------------------------------------------------------
# The routes, in the order they were registered before the split
# ---------------------------------------------------------------------------
from routers.system import router as system_router  # noqa: E402
from routers.sync import router as sync_router, batch_router as sync_batch_router  # noqa: E402
from routers.students import router as students_router  # noqa: E402
from routers.departments import router as departments_router  # noqa: E402
from routers.study_systems import router as study_systems_router  # noqa: E402
from routers.courses import router as courses_router  # noqa: E402
from routers.personnel import router as personnel_router  # noqa: E402
from routers.academic import router as academic_router  # noqa: E402
from routers.graduation import router as graduation_router  # noqa: E402
from routers.settings import router as settings_router  # noqa: E402
from routers.certificates import router as certificates_router  # noqa: E402
from routers.thesis import router as thesis_router  # noqa: E402
from routers.dashboard import router as dashboard_router  # noqa: E402
from routers.study_routines import router as study_routines_router  # noqa: E402
from routers.issued_certificates import router as issued_certificates_router  # noqa: E402

app.include_router(system_router)               # /ping /health/db /sp/* /replica/* /table-count/* /admin/*
app.include_router(sync_router)                 # POST /sync
app.include_router(students_router)             # /students/* /api/students/*
app.include_router(departments_router)          # /departments/*
app.include_router(study_systems_router)        # /study-systems/*
app.include_router(courses_router)              # /courses/* /api/courses/*
app.include_router(personnel_router)            # /personnel/* /api/login /api/logout /permissions /roles /user-roles
app.include_router(academic_router)             # /academic-periods/* /api/periods/* /enrollments/*
app.include_router(graduation_router)           # /graduation-orders/* /orders/*
app.include_router(settings_router)             # /settings/* /api/user/appearance*
app.include_router(certificates_router)         # /certificates/* /lookups/*
app.include_router(thesis_router)               # /thesis/* /supervisors/*
app.include_router(dashboard_router)            # /api/dashboard/*
app.include_router(study_routines_router)       # /study-routines/* /api/study-routine*
app.include_router(issued_certificates_router)  # /issued-certificates/* /certificate-numbers/*
app.include_router(sync_batch_router)           # POST /sync (shadowed) and POST /api/sync


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=2030)
