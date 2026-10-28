import os
import sys
from datetime import date, datetime
from decimal import Decimal
import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional, Union

import mysql.connector
from mysql.connector import pooling
from fastapi import FastAPI, HTTPException, Depends, APIRouter, status, Query, UploadFile, File
from pydantic import BaseModel

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
from password_hashing import hash_password, verify_password, needs_upgrade, prepare_for_storage, is_hashed

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
from deps import (  # noqa: E402
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


# ===========================================================================
# 1. System & Health & Offline Sync  (routers/system.py, routers/sync.py)
# ===========================================================================

from routers.system import router as system_router  # noqa: E402
from routers.sync import router as sync_router, batch_router as sync_batch_router  # noqa: E402
app.include_router(system_router)
app.include_router(sync_router)


# ===========================================================================
# 2.-5. Students, Departments, Study Systems, Courses  (routers/*.py)
# ===========================================================================

from routers.students import router as students_router  # noqa: E402
from routers.departments import router as departments_router  # noqa: E402
from routers.study_systems import router as study_systems_router  # noqa: E402
from routers.courses import router as courses_router  # noqa: E402
app.include_router(students_router)
app.include_router(departments_router)
app.include_router(study_systems_router)
app.include_router(courses_router)


# ===========================================================================
# 6. Personnel & Authentication Module
# ===========================================================================

class PersonnelPayload(BaseModel):
    name_ar: str
    name_en: str
    academic_title_ar: Optional[str] = None
    academic_title_en: Optional[str] = None
    responsibility_ar: Optional[str] = None
    responsibility_en: Optional[str] = None
    display_order: Optional[int] = 0
    username: str
    password_hash: Optional[str] = None   # the typed password; stored hashed
    personnel_role: Optional[str] = "user"
    university_settings_id: Optional[int] = 1
    is_active: Optional[int] = 1
    must_change_password: Optional[bool] = None


class PersonnelResponse(BaseModel):
    id: int
    name_ar: str
    name_en: str
    academic_title_ar: Optional[str] = None
    academic_title_en: Optional[str] = None
    responsibility_ar: Optional[str] = None
    responsibility_en: Optional[str] = None
    display_order: int = 0
    is_signature: bool = False
    page_location: int = 0
    username: str
    personnel_role: Optional[str] = "user"
    university_settings_id: Optional[int] = None
    is_active: int = 1
    created_at: Optional[Any] = None


class LoginPayload(BaseModel):
    username: str
    password_hash: str


class LoginRequest(BaseModel):
    username: str
    password: str


@app.get("/personnel", response_model=List[PersonnelResponse])
def get_personnel(conn=Depends(get_db)):
    try:
        rows = execute_sp_fetchall(conn, "GetAllPersonnel")
        for r in rows:
            r["is_signature"] = bool(r.get("is_signature"))
            r["page_location"] = int(r.get("page_location") or 0)
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/personnel/active")
def get_active_personnel(conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetActivePersonnel")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/personnel/{person_id}", response_model=PersonnelResponse)
def get_personnel_by_id(person_id: int, conn=Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "GetPersonnelById", (person_id,))
        if not row:
            raise HTTPException(status_code=404, detail=f"Personnel with id {person_id} not found")
        row["is_signature"] = bool(row.get("is_signature"))
        row["page_location"] = int(row.get("page_location") or 0)
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _must_change_password(conn, person_id: int) -> bool:
    """personnel.must_change_password (added by the 2026-10-24_02 SQL); False if the column is missing."""
    cur = conn.cursor(buffered=True)
    try:
        cur.execute("SELECT must_change_password FROM personnel WHERE id = %s", (person_id,))
        row = cur.fetchone()
        return bool(row and row[0])
    except Exception:
        return False
    finally:
        cur.close()


def _authenticate_user(conn, username: str, password: str) -> Optional[dict]:
    """
    Check a login. Passwords are stored hashed (password_hashing.py); a legacy
    plain-text password is still accepted once and replaced by its hash.
    Returns the same fields AuthenticateUser returned, plus must_change_password.
    """
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute(
            "SELECT id, name_ar, name_en, personnel_role, password_hash FROM personnel "
            "WHERE username = %s AND is_active = 1 LIMIT 1",
            (username,)
        )
        row = cur.fetchone()
    finally:
        cur.close()
    if not row or not verify_password(password, row.get("password_hash")):
        return None
    if needs_upgrade(row.get("password_hash")):
        upd = conn.cursor()
        try:
            upd.execute("UPDATE personnel SET password_hash = %s WHERE id = %s", (hash_password(password), row["id"]))
            conn.commit()
            logger.info(f"Password of personnel {row['id']} upgraded to a hash")
        except Exception as exc:
            conn.rollback()
            logger.warning(f"Could not upgrade password hash for personnel {row['id']}: {exc}")
        finally:
            upd.close()
    user = decode_db_value({k: row[k] for k in ("id", "name_ar", "name_en", "personnel_role")})
    user["must_change_password"] = _must_change_password(conn, row["id"])
    return user


@app.post("/personnel/login")
def authenticate_personnel(payload: LoginPayload, conn=Depends(get_db)):
    # payload.password_hash carries the password the user typed (historic field name)
    try:
        row = _authenticate_user(conn, payload.username, payload.password_hash)
        if not row:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/login")
def api_login(req: LoginRequest, conn=Depends(get_db)):
    try:
        row = _authenticate_user(conn, req.username, req.password)
        if not row:
            raise HTTPException(status_code=401, detail="Invalid username or password")
        return {"success": True, "user": row}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class PasswordChangePayload(BaseModel):
    password: str
    must_change: Optional[bool] = False
    # Offline resets send the hash they started from; if the server's hash changed
    # meanwhile, the newer server password wins and this request is refused (409).
    base_hash: Optional[str] = None


@app.put("/personnel/{person_id}/password")
def change_personnel_password(person_id: int, payload: PasswordChangePayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT password_hash FROM personnel WHERE id = %s", (person_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Personnel {person_id} not found")
        if payload.base_hash is not None and (row.get("password_hash") or "") != payload.base_hash:
            raise HTTPException(status_code=409, detail="Password was changed on the server meanwhile; this change was not applied")
        stored = prepare_for_storage(payload.password)
        cur.execute("UPDATE personnel SET password_hash = %s WHERE id = %s", (stored, person_id))
        _set_must_change_password(conn, person_id, bool(payload.must_change))
        conn.commit()
        # The laptop keeps this exact hash for offline logins and for later offline resets
        return {"status": "success", "password_hash": stored}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.post("/api/logout")
def logout():
    return {"success": True, "message": "Logged out successfully"}


@app.post("/personnel")
def insert_personnel(payload: PersonnelPayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("InsertPersonnel", (
            payload.name_ar,
            payload.name_en,
            payload.academic_title_ar,
            payload.academic_title_en,
            payload.responsibility_ar or "",
            payload.responsibility_en or "",
            payload.display_order if payload.display_order is not None else 0,
            payload.username,
            prepare_for_storage(payload.password_hash),
            payload.personnel_role or "user",
            payload.university_settings_id,
            payload.is_active if payload.is_active is not None else 1
        ))

        inserted_id = None
        if hasattr(cur, "stored_results"):
            for result_set in cur.stored_results():
                row = result_set.fetchone()
                if row:
                    if isinstance(row, dict):
                        inserted_id = row.get("inserted_id")
                    elif isinstance(row, (tuple, list)):
                        inserted_id = row[0]
                    break

        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        if inserted_id and payload.must_change_password is not None:
            _set_must_change_password(conn, int(inserted_id), bool(payload.must_change_password))
        conn.commit()
        return {"new_id": inserted_id, "inserted_id": inserted_id, "status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.put("/personnel/{person_id}")
def update_personnel(person_id: int, payload: PersonnelPayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UpdatePersonnel", (
            person_id,
            payload.name_ar,
            payload.name_en,
            payload.academic_title_ar,
            payload.academic_title_en,
            payload.responsibility_ar or "",
            payload.responsibility_en or "",
            payload.display_order if payload.display_order is not None else 0,
            payload.username,
            payload.personnel_role or "user",
            payload.university_settings_id,
            payload.is_active if payload.is_active is not None else 1
        ))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        if payload.password_hash:
            cur.callproc("UpdatePersonnelPassword", (person_id, prepare_for_storage(payload.password_hash)))
            try:
                while cur.nextset():
                    pass
            except Exception:
                pass
            if payload.must_change_password is not None:
                _set_must_change_password(conn, person_id, bool(payload.must_change_password))

        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.post("/personnel/{person_id}/toggle")
def toggle_personnel(person_id: int, is_active: int, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.callproc("TogglePersonnelStatus", (person_id, is_active))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.delete("/personnel/{person_id}")
def delete_personnel(person_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeletePersonnel", (person_id,))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


class PermissionsUpdatePayload(BaseModel):
    permission_keys: List[str]


@app.get("/permissions")
def get_all_permissions(conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT permission_key, category, name_ar, name_en, description_ar FROM permissions ORDER BY category, permission_key")
        return cur.fetchall()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.get("/personnel/{person_id}/permissions")
def get_user_permissions(person_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        try:
            cur.callproc("GetPersonnelPermissions", (person_id,))
            for res in cur.stored_results():
                rows = res.fetchall()
                return [r["permission_key"] for r in rows]
        except Exception:
            pass
        # Fallback direct SELECT
        cur.execute("SELECT permission_key FROM personnel_permissions WHERE personnel_id = %s AND is_granted = 1", (person_id,))
        rows = cur.fetchall()
        return [r["permission_key"] for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.put("/personnel/{person_id}/permissions")
def update_user_permissions(person_id: int, payload: PermissionsUpdatePayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        keys_csv = ",".join(payload.permission_keys) if payload.permission_keys else ""
        try:
            cur.callproc("BulkSetPersonnelPermissions", (person_id, keys_csv))
            try:
                while cur.nextset():
                    pass
            except Exception:
                pass
            conn.commit()
            return {"status": "success", "count": len(payload.permission_keys)}
        except Exception as sp_err:
            logger.warning(f"BulkSetPersonnelPermissions SP failed ({sp_err}), using direct transaction")
            cur.execute("DELETE FROM personnel_permissions WHERE personnel_id = %s", (person_id,))
            for k in payload.permission_keys:
                cur.execute(
                    "INSERT INTO personnel_permissions (personnel_id, permission_key, is_granted) VALUES (%s, %s, 1) ON DUPLICATE KEY UPDATE is_granted = 1",
                    (person_id, k)
                )
            conn.commit()
            return {"status": "success", "count": len(payload.permission_keys)}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


# ---------------------------------------------------------------------------
# Roles & Responsibility Profiles Endpoints
# ---------------------------------------------------------------------------

class RolePayload(BaseModel):
    id: Optional[str] = None
    name_ar: str
    name_en: str
    description_ar: Optional[str] = ""
    base_role: Optional[str] = "user"
    allowed_pages: Optional[List[str]] = []
    allowed_actions: Optional[List[str]] = []
    department_scope: Optional[str] = "all"
    is_system: Optional[int] = 0

# Roles live in MySQL tables `roles` and `user_roles`
# (created by sql/fixes/2026-10-24_02_accounts_roles_passwords.sql).
# allowed_pages / allowed_actions are stored as JSON text, as in the client's SQLite copy.

def _role_row_out(row: dict) -> dict:
    item = decode_db_value(dict(row))
    for key in ("allowed_pages", "allowed_actions"):
        try:
            item[key] = _json.loads(item.get(key) or "[]")
        except Exception:
            item[key] = []
    return item


@app.get("/roles")
def get_all_roles(conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM roles ORDER BY is_system DESC, id ASC")
        return [_role_row_out(r) for r in cur.fetchall()]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.post("/roles")
def save_role_endpoint(payload: RolePayload, conn=Depends(get_db)):
    role_id = (payload.id or "").strip()
    if not role_id:
        raise HTTPException(status_code=400, detail="Role id is required")
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO roles (id, name_ar, name_en, description_ar, base_role,
                               allowed_pages, allowed_actions, department_scope, is_system)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                name_ar = VALUES(name_ar), name_en = VALUES(name_en),
                description_ar = VALUES(description_ar), base_role = VALUES(base_role),
                allowed_pages = VALUES(allowed_pages), allowed_actions = VALUES(allowed_actions),
                department_scope = VALUES(department_scope), is_system = VALUES(is_system)
        """, (
            role_id, payload.name_ar, payload.name_en, payload.description_ar or "",
            payload.base_role or "user",
            _json.dumps(payload.allowed_pages or [], ensure_ascii=False),
            _json.dumps(payload.allowed_actions or [], ensure_ascii=False),
            str(payload.department_scope or "all"), int(payload.is_system or 0),
        ))
        conn.commit()
        return {"status": "success", "id": role_id}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.delete("/roles/{role_id}")
def delete_role_endpoint(role_id: str, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT is_system FROM roles WHERE id = %s", (role_id,))
        row = cur.fetchone()
        if not row:
            return {"status": "not_found"}
        if int(row.get("is_system") or 0):
            raise HTTPException(status_code=400, detail="Cannot delete built-in system roles")
        cur.execute("DELETE FROM roles WHERE id = %s", (role_id,))
        conn.commit()
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


class UserRolePayload(BaseModel):
    role_id: str


@app.get("/user-roles")
def get_user_roles(conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT personnel_id, role_id FROM user_roles")
        return decode_db_value(cur.fetchall())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.put("/user-roles/{personnel_id}")
def set_user_role(personnel_id: int, payload: UserRolePayload, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO user_roles (personnel_id, role_id) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE role_id = VALUES(role_id)
        """, (personnel_id, payload.role_id.strip()))
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()



# ===========================================================================
# 7. Academic Periods Module
# ===========================================================================

class AcademicPeriodPayload(BaseModel):
    student_id: int
    academic_year: str
    study_system_id: int
    stage_number: int
    semester_num: Optional[int] = 1
    result_status: Optional[str] = "PASSED"


class AcademicPeriodStatusPayload(BaseModel):
    result_status: str


@app.get("/academic-periods/by-student/{student_id}")
def get_academic_periods_by_student(student_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAcademicPeriodsByStudent", (student_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/academic-periods")
def insert_academic_period(payload: AcademicPeriodPayload, conn=Depends(get_db)):
    try:
        status_val = result_status_code(payload.result_status)
        res = execute_sp_fetchone(
            conn, "InsertAcademicPeriod",
            (payload.student_id, payload.academic_year, payload.stage_number, payload.semester_num, status_val)
        )
        new_id = res.get("new_period_id") or res.get("new_id", 0) if res else 0
        conn.commit()
        return {"new_id": new_id}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@app.patch("/academic-periods/{period_id}/status")
@app.patch("/api/periods/{period_id}/status")
def update_academic_period_status(period_id: int, payload: AcademicPeriodStatusPayload, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        raw_st = payload.result_status
        code_val = result_status_code(raw_st)
        cur.callproc("UpdateAcademicPeriodStatus", (period_id, str(code_val)))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success", "result_status": code_val}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.delete("/academic-periods/{period_id}")
def delete_academic_period(period_id: int, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.callproc("DeleteAcademicPeriod", (period_id,))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


# ===========================================================================
# 8. Enrollments Module
# ===========================================================================

class EnrollmentPayload(BaseModel):
    period_id: int
    course_id: int
    score: float
    is_second: Optional[int] = 0


@app.get("/enrollments/by-period/{period_id}")
def get_enrollments_by_period(period_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetEnrollmentsByPeriod", (period_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/enrollments")
def insert_enrollment(payload: EnrollmentPayload, conn=Depends(get_db)):
    try:
        val = payload.is_second
        if val == 2:
            passed_round = 2
        elif val == 3:
            passed_round = 3
        else:
            passed_round = 1
        res = execute_sp_fetchone(
            conn, "InsertEnrollment",
            (payload.period_id, payload.course_id, float(payload.score), int(passed_round))
        )
        new_id = res.get("new_enrollment_id") or res.get("new_id", 0) if res else 0
        conn.commit()
        return {"new_id": new_id}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@app.put("/enrollments/{enrollment_id}")
@app.put("/api/enrollments/{enrollment_id}")
def update_enrollment(enrollment_id: int, score: float, is_second: int, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        val = int(is_second)
        if val == 2:
            passed_round = 2
        elif val == 3:
            passed_round = 3
        elif val == 0:
            passed_round = 0
        else:
            passed_round = 1
        cur.callproc("UpdateEnrollment", (enrollment_id, float(score), int(passed_round)))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.delete("/enrollments/{enrollment_id}")
def delete_enrollment(enrollment_id: int, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.callproc("DeleteEnrollment", (enrollment_id,))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


# ===========================================================================
# 9. Graduation Orders Module
# ===========================================================================

class GraduationOrderPayload(BaseModel):
    order_number: str
    order_date: str
    department_id: int
    study_type: str
    graduation_year: Union[int, str]
    graduation_semester: str
    num_students: int
    notes: Optional[str] = None
    study_system_id: Optional[int] = 1


@app.get("/graduation-orders")
@app.get("/orders")
def get_graduation_orders(limit: int = 25, offset: int = 0, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAllGraduationOrders", (limit, offset))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/graduation-orders/{order_id}")
@app.get("/orders/{order_id}")
def get_graduation_order(order_id: int, conn=Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "GetGraduationOrderByID", (order_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Order not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/graduation-orders")
@app.post("/orders")
def insert_graduation_order(payload: GraduationOrderPayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        args = (
            payload.order_number, payload.order_date, payload.department_id,
            payload.study_type, payload.graduation_year, payload.graduation_semester,
            payload.num_students, payload.notes, payload.study_system_id
        )
        cur.callproc("InsertGraduationOrder", args)
        real_id = None
        if hasattr(cur, "stored_results"):
            for result in cur.stored_results():
                row = result.fetchone()
                if row:
                    if "new_id" in row:
                        real_id = row["new_id"]
                    elif "inserted_id" in row:
                        real_id = row["inserted_id"]
                    break
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        if real_id is None:
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            real_id = cur.fetchone()["new_id"]
        conn.commit()
        return {"new_id": real_id, "inserted_id": real_id, "status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.put("/graduation-orders/{order_id}")
@app.put("/orders/{order_id}")
def update_graduation_order(order_id: int, payload: GraduationOrderPayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        args = (
            order_id, payload.order_number, payload.order_date, payload.department_id,
            payload.study_type, payload.graduation_year, payload.graduation_semester,
            payload.num_students, payload.notes, payload.study_system_id
        )
        cur.callproc("UpdateGraduationOrder", args)
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.delete("/graduation-orders/{order_id}")
@app.delete("/orders/{order_id}")
def delete_graduation_order(order_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteGraduationOrder", (order_id,))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


# ===========================================================================
# 10. Settings & Appearance Preferences Module
# ===========================================================================

class SettingsPayload(BaseModel):
    univ_name_ar: str
    univ_name_en: str
    college_name_ar: str
    college_name_en: str
    univ_logo_path: Optional[str] = None
    college_logo_path: Optional[str] = None


class AppearancePayload(BaseModel):
    theme: str
    accent_color: str
    font_family: str
    font_size_base: int
    rtl: Optional[int] = 1


@app.get("/settings")
def get_settings(conn=Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "GetUniversitySettings")
        return row or {}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.put("/settings")
def update_settings(payload: SettingsPayload, conn=Depends(get_db)):
    cur = conn.cursor()
    try:
        cur.callproc("UpdateUniversitySettings", (
            payload.univ_name_ar,
            payload.univ_name_en,
            payload.college_name_ar,
            payload.college_name_en,
            payload.univ_logo_path,
            payload.college_logo_path
        ))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.get("/settings/appearance/{user_id}")
@app.get("/api/user/appearance/{emp_id}")
def get_user_appearance(user_id: int | None = None, emp_id: int | None = None, conn=Depends(get_db)):
    target_id = emp_id if emp_id is not None else user_id
    try:
        row = execute_sp_fetchone(conn, "Get_User_Settings", (target_id,))
        if not row:
            return {
                "EMP_ID": target_id,
                "theme": "System",
                "accent_color": "blue",
                "font_family": "Segoe UI",
                "font_size_base": 13,
                "is_arabic_rtl": 1
            }
        return row
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.put("/settings/appearance/{user_id}")
def update_user_appearance(user_id: int, payload: AppearancePayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UpdateUserPreferences", (user_id, payload.theme, payload.accent_color, payload.font_family, payload.font_size_base, payload.rtl))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.post("/api/user/appearance")
def api_update_user_appearance(payload: dict, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        emp_id = payload.get("emp_id") or payload.get("EMP_ID")
        theme = payload.get("theme", "System")
        accent = payload.get("accent_color", "blue")
        font = payload.get("font_family", "Arial")
        size = payload.get("font_size_base", 13)
        rtl = payload.get("is_arabic_rtl", 1)
        cur.callproc("Update_User_Settings", (emp_id, theme, accent, font, size, rtl))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"success": True}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.post("/settings/clear-logs")
def clear_audit_logs(conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("ClearAuditLogs")
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


# ===========================================================================
# 11. Certificates & Transcripts Module
# ===========================================================================

@app.get("/certificates/{student_id}")
@app.get("/api/certificates/{student_id}")
def get_certificate_raw_data(student_id: int, grouping_mode: str = Query("DEFAULT"), conn=Depends(get_db)):
    try:
        cur = conn.cursor(dictionary=True)
        try:
            cur.callproc("sp_GetFullCertificateData", (student_id, grouping_mode))
            result_sets = []
            if hasattr(cur, "stored_results"):
                for result in cur.stored_results():
                    rows = decode_db_value(result.fetchall())
                    result_sets.append(rows)
            try:
                while cur.nextset():
                    pass
            except Exception:
                pass

            student_info_list = result_sets[0] if len(result_sets) > 0 and result_sets[0] else []
            ranking_list = result_sets[1] if len(result_sets) > 1 and result_sets[1] else []
            signers_list = result_sets[2] if len(result_sets) > 2 else []
            timeline_list = result_sets[3] if len(result_sets) > 3 else []
            courses_list = result_sets[4] if len(result_sets) > 4 else []

            settings_list = []
            if student_info_list and isinstance(student_info_list[0], dict):
                s = student_info_list[0]
                settings_list = [{
                    "id": s.get("university_settings_id") or s.get("id"),
                    "univ_name_ar": s.get("univ_name_ar", ""),
                    "univ_name_en": s.get("univ_name_en", ""),
                    "college_name_ar": s.get("college_name_ar", ""),
                    "college_name_en": s.get("college_name_en", ""),
                }]

            return {
                "student_id": student_id,
                "grouping_mode": grouping_mode,
                "settings": settings_list,
                "student_info": student_info_list,
                "ranking": ranking_list,
                "signers": signers_list,
                "academic_timeline": timeline_list,
                "courses_grouped": courses_list
            }
        finally:
            cur.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class AcademicFlatRecord(BaseModel):
    student_id: int
    student_name_ar: str
    study_system_ar: Optional[str] = ""
    academic_year: Optional[str] = ""
    stage_number: Optional[int] = 1
    stage_name_ar: Optional[str] = ""
    course_id: Optional[int] = 0
    course_code: Optional[str] = ""
    course_name_ar: Optional[str] = ""
    course_name_en: Optional[str] = ""
    units: Optional[float] = 0.0
    mark: Optional[float] = 0.0
    result_status_code: Optional[int] = 1
    result_status_label: Optional[str] = "PASSED"


@app.get("/certificates/flat-yearly/{student_id}")
def get_flat_yearly_certificate_courses(student_id: int, grouping_mode: str = Query("DEFAULT"), conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        try:
            cur.callproc("sp_GetCertificate_Yearly_ByAcademicDefualte", (student_id,))
        except Exception:
            try:
                cur.callproc("sp_GetCertificate_Courses_Yearly_ByAcademicDefualte", (student_id,))
            except Exception:
                cur.callproc("sp_GetCertificate_AcademicCourses", (student_id, grouping_mode))

        rows = []
        if hasattr(cur, "stored_results"):
            for result in cur.stored_results():
                rows = result.fetchall()
                break
        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        return decode_db_value(rows)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


# ===========================================================================
# 12. Lookups Module
# ===========================================================================

@app.get("/lookups/countries")
def get_countries(conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAllCountries")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/lookups/governorates")
def get_governorates(conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAllGovernorates")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ===========================================================================
# 13. Thesis & Supervisor Module
# ===========================================================================

class ThesisPayload(BaseModel):
    student_id: int
    title_ar: str
    title_en: str
    defense_date: Optional[str] = None
    committee_decision: Optional[str] = None
    final_grade: Optional[float] = None


class SupervisorPayload(BaseModel):
    student_id: int
    personnel_id: int
    supervision_role: str


@app.get("/thesis/by-student/{student_id}")
def get_thesis_by_student(student_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetThesisByStudent", (student_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/thesis")
def insert_thesis(payload: ThesisPayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("InsertThesis", (payload.student_id, payload.title_ar, payload.title_en, payload.defense_date, payload.committee_decision, payload.final_grade))
        real_id = None
        if hasattr(cur, "stored_results"):
            for result in cur.stored_results():
                row = result.fetchone()
                if row:
                    if "new_id" in row:
                        real_id = row["new_id"]
                    elif "inserted_id" in row:
                        real_id = row["inserted_id"]
                    break
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        if real_id is None:
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            real_id = cur.fetchone()["new_id"]
        conn.commit()
        return {"new_id": real_id, "inserted_id": real_id, "status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.put("/thesis/{thesis_id}")
def update_thesis(thesis_id: int, payload: ThesisPayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UpdateThesis", (thesis_id, payload.title_ar, payload.title_en, payload.defense_date, payload.committee_decision, payload.final_grade))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.delete("/thesis/{thesis_id}")
def delete_thesis(thesis_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteThesis", (thesis_id,))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.get("/supervisors/by-student/{student_id}")
def get_supervisors_by_student(student_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetSupervisorsByStudent", (student_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/supervisors")
def insert_supervisor(payload: SupervisorPayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("InsertStudentSupervisor", (payload.student_id, payload.personnel_id, payload.supervision_role))
        real_id = None
        if hasattr(cur, "stored_results"):
            for result in cur.stored_results():
                row = result.fetchone()
                if row:
                    if "new_id" in row:
                        real_id = row["new_id"]
                    elif "inserted_id" in row:
                        real_id = row["inserted_id"]
                    break
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        if real_id is None:
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            real_id = cur.fetchone()["new_id"]
        conn.commit()
        return {"new_id": real_id, "inserted_id": real_id, "status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.put("/supervisors/{record_id}")
def update_supervisor(record_id: int, payload: SupervisorPayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("UpdateStudentSupervisor", (record_id, payload.personnel_id, payload.supervision_role))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.delete("/supervisors/{record_id}")
def delete_supervisor(record_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteStudentSupervisor", (record_id,))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


# ===========================================================================
# 14. Dashboard Counts Module
# ===========================================================================

class DashboardCountsResponse(BaseModel):
    total_students: int
    total_departments: int
    total_courses: int
    total_personnel: int


@app.get("/api/dashboard/counts", response_model=DashboardCountsResponse)
def get_dashboard_counts(conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        result = None
        for sp_name in ("Get_dashboard_counts", "GetDashboardCounts"):
            try:
                cur.callproc(sp_name)
                if hasattr(cur, "stored_results"):
                    for r in cur.stored_results():
                        result = r.fetchone()
                        if result:
                            break
                try:
                    while cur.nextset():
                        pass
                except Exception:
                    pass
                if result:
                    break
            except Exception as sp_exc:
                logger.debug(f"{sp_name} SP call attempt failed: {sp_exc}")

        if not result:
            return DashboardCountsResponse(
                total_students=0,
                total_departments=0,
                total_courses=0,
                total_personnel=0
            )


        return DashboardCountsResponse(
            total_students=result.get("total_students", 0),
            total_departments=result.get("total_departments", 0),
            total_courses=result.get("total_courses", 0),
            total_personnel=result.get("total_personnel", 0)
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


# ===========================================================================
# 15. Study Routines, Periods & Courses Module
# ===========================================================================

class StudyRoutinePayload(BaseModel):
    name_ar: str
    name_en: str
    department_id: int
    study_system_id: Optional[int] = 1
    stage_number: Optional[int] = 1
    semester_num: Optional[int] = 1


class RoutineCoursePayload(BaseModel):
    routine_id: int
    course_id: int


class RoutinePeriodPayload(BaseModel):
    routine_id: int
    stage_number: int
    semester_num: Optional[int] = 1


class RoutinePeriodCoursePayload(BaseModel):
    period_id: int
    course_id: int


@app.get("/api/study-routines")
@app.get("/study-routines")
def get_all_study_routines(conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAllStudyRoutines")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/study-routines/{routine_id}")
@app.get("/study-routines/{routine_id}")
def get_study_routine_by_id(routine_id: int, conn=Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "GetStudyRoutineById", (routine_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Study routine not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/study-routines")
@app.post("/study-routines")
def insert_study_routine(payload: StudyRoutinePayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc(
            "InsertStudyRoutine",
            (
                payload.name_ar,
                payload.name_en,
                payload.department_id,
                payload.study_system_id or 1,
            )
        )
        real_id = None
        if hasattr(cur, "stored_results"):
            for result in cur.stored_results():
                row = result.fetchone()
                if row:
                    if "new_id" in row:
                        real_id = row["new_id"]
                    elif "inserted_id" in row:
                        real_id = row["inserted_id"]
                    elif "id" in row:
                        real_id = row["id"]
                    break
        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        if real_id is None:
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            r = cur.fetchone()
            if r:
                real_id = r.get("new_id")

        conn.commit()
        return {"new_id": real_id, "inserted_id": real_id, "status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.put("/api/study-routines/{routine_id}")
@app.put("/study-routines/{routine_id}")
def update_study_routine(routine_id: int, payload: StudyRoutinePayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc(
            "UpdateStudyRoutine",
            (
                routine_id,
                payload.name_ar,
                payload.name_en,
                payload.department_id,
                payload.study_system_id or 1,
            )
        )
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success", "message": "Study routine updated successfully"}
    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        err_msg = str(exc)
        if "Duplicate entry" in err_msg or "45000" in err_msg:
            raise HTTPException(
                status_code=400,
                detail="Duplicate entry: A routine with this name already exists in this department and study system."
            )
        raise HTTPException(status_code=500, detail=err_msg)
    finally:
        cur.close()


@app.delete("/api/study-routines/{routine_id}")
@app.delete("/study-routines/{routine_id}")
def delete_study_routine(routine_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteStudyRoutine", (routine_id,))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.get("/api/study-routine-courses/{routine_id}")
@app.get("/study-routine-courses/{routine_id}")
def get_study_routine_courses(routine_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetStudyRoutineCourses", (routine_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/study-routine-courses")
def insert_study_routine_course(payload: RoutineCoursePayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("InsertStudyRoutineCourse", (payload.routine_id, payload.course_id))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.delete("/api/study-routine-courses/{routine_id}/{course_id}")
def delete_study_routine_course(routine_id: int, course_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteStudyRoutineCourse", (routine_id, course_id))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.get("/api/study-routine-periods/{routine_id}")
def get_study_routine_periods(routine_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetStudyRoutinePeriods", (routine_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/study-routine-periods")
def insert_study_routine_period(payload: RoutinePeriodPayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc(
            "InsertStudyRoutinePeriod",
            (payload.routine_id, payload.stage_number, payload.semester_num or 1)
        )
        real_id = None
        if hasattr(cur, "stored_results"):
            for result in cur.stored_results():
                row = result.fetchone()
                if row:
                    real_id = row.get("new_id") or row.get("inserted_id") or row.get("id")
                    break
        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        if real_id is None:
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            r = cur.fetchone()
            if r:
                real_id = r.get("new_id")

        conn.commit()
        return {"new_id": real_id, "inserted_id": real_id, "status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.put("/api/study-routine-periods/{period_id}")
def update_study_routine_period(period_id: int, payload: RoutinePeriodPayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc(
            "UpdateStudyRoutinePeriod",
            (period_id, payload.stage_number, payload.semester_num or 1)
        )
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.delete("/api/study-routine-periods/{period_id}")
def delete_study_routine_period(period_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteStudyRoutinePeriod", (period_id,))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.get("/api/study-routine-period-courses/{period_id}")
def get_study_routine_period_courses(period_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetStudyRoutinePeriodCourses", (period_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/study-routine-period-courses")
def insert_study_routine_period_course(payload: RoutinePeriodCoursePayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("InsertStudyRoutinePeriodCourse", (payload.period_id, payload.course_id))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.delete("/api/study-routine-period-courses/{period_id}/{course_id}")
def delete_study_routine_period_course(period_id: int, course_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteStudyRoutinePeriodCourse", (period_id, course_id))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


# ===========================================================================
# 16. Issued Certificates Module
# ===========================================================================

class IssuedCertificatePayload(BaseModel):
    student_id: Optional[int] = None
    to_title: Optional[str] = "من يهمه الأمر"
    template_type: Optional[str] = "graduation"
    issue_date: Optional[str] = None
    certificate_number: Optional[str] = None


@app.get("/api/issued-certificates")
@app.get("/issued-certificates")
def get_all_issued_certificates(conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAllIssuedCertificates")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/issued-certificates/latest-number")
@app.get("/issued-certificates/latest-number")
def get_latest_certificate_number(conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute(
            "SELECT certificate_number FROM issued_certificates "
            "WHERE certificate_number IS NOT NULL AND certificate_number != '' "
            "ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
        latest = row["certificate_number"] if row else None
        # Numbers reserved by laptops for offline use must never be handed out online:
        # report the end of the highest reserved block if it is above the latest issued number
        parts = _cert_number_parts(latest)
        if parts:
            block_end = _max_reserved_block_end(conn, parts[1])
            if block_end and block_end >= parts[0]:
                latest = f"{block_end}/{parts[1]}"
        return {"latest_number": latest}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


def _cert_number_parts(number) -> Optional[tuple]:
    """'893/26' -> (893, '26'); anything else -> None."""
    import re as _re
    m = _re.match(r"^\s*(\d+)\s*/\s*(\S+)\s*$", str(number or ""))
    return (int(m.group(1)), m.group(2)) if m else None


def _max_reserved_block_end(conn, year_suffix: str) -> Optional[int]:
    cur = conn.cursor(buffered=True)
    try:
        cur.execute("SELECT MAX(end_no) FROM certificate_number_blocks WHERE year_suffix = %s", (year_suffix,))
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else None
    except Exception:
        return None  # table not created yet
    finally:
        cur.close()


class CertificateBlockRequest(BaseModel):
    device_id: str
    count: Optional[int] = 20
    year_suffix: Optional[str] = None


@app.post("/certificate-numbers/reserve")
def reserve_certificate_numbers(payload: CertificateBlockRequest, conn=Depends(get_db)):
    """
    Reserve a block of certificate numbers for one laptop to use while offline, so two
    offline laptops can never print the same number. The block starts above every number
    already issued or reserved for that year.
    """
    suffix = (payload.year_suffix or datetime.now().strftime("%y")).strip()
    count = max(1, min(int(payload.count or 20), 200))
    cur = conn.cursor(buffered=True)
    try:
        cur.execute("SELECT GET_LOCK('certificate_number_blocks', 10)")
        cur.fetchone()
        cur.execute(
            "SELECT certificate_number FROM issued_certificates WHERE certificate_number LIKE %s",
            (f"%/{suffix}",)
        )
        issued_max = max((p[0] for p in (_cert_number_parts(r[0]) for r in cur.fetchall()) if p and p[1] == suffix),
                         default=0)
        start = max(issued_max, _max_reserved_block_end(conn, suffix) or 0) + 1
        end = start + count - 1
        cur.execute(
            "INSERT INTO certificate_number_blocks (device_id, year_suffix, start_no, end_no) VALUES (%s, %s, %s, %s)",
            (payload.device_id[:64], suffix, start, end)
        )
        conn.commit()
        return {"year_suffix": suffix, "start_no": start, "end_no": end}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        try:
            cur.execute("SELECT RELEASE_LOCK('certificate_number_blocks')")
            cur.fetchone()
        except Exception:
            pass
        cur.close()


@app.get("/api/issued-certificates/report")
@app.get("/issued-certificates/report")
def get_issued_certificates_report(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    template_type: Optional[str] = Query(None),
    graduation_year: Optional[int] = Query(None),
    study_system_id: Optional[int] = Query(None),
    search_text: Optional[str] = Query(None),
    conn=Depends(get_db)
):
    try:
        return execute_sp_fetchall(
            conn,
            "GetIssuedCertificatesReport",
            (start_date, end_date, department_id, template_type, graduation_year, study_system_id, search_text)
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/issued-certificates/{cert_id}")
@app.get("/issued-certificates/{cert_id}")
def get_issued_certificate_by_id(cert_id: int, conn=Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "GetIssuedCertificateById", (cert_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Issued certificate not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/issued-certificates/by-student/{student_id}")
@app.get("/issued-certificates/by-student/{student_id}")
def get_issued_certificates_by_student(student_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetIssuedCertificatesByStudent", (student_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/issued-certificates")
@app.post("/issued-certificates")
def insert_issued_certificate(payload: IssuedCertificatePayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        issue_date = payload.issue_date or datetime.now().strftime("%Y-%m-%d")
        student_id = payload.student_id or 0
        cur.callproc(
            "InsertIssuedCertificate",
            (
                student_id,
                payload.to_title or "من يهمه الأمر",
                payload.template_type or "graduation",
                str(issue_date),
                payload.certificate_number,
            )
        )
        real_id = None
        if hasattr(cur, "stored_results"):
            for result in cur.stored_results():
                row = result.fetchone()
                if row:
                    if "inserted_id" in row:
                        real_id = row["inserted_id"]
                    elif "new_id" in row:
                        real_id = row["new_id"]
                    elif "id" in row:
                        real_id = row["id"]
                    break
        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        if real_id is None:
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            r = cur.fetchone()
            if r:
                real_id = r.get("new_id")

        conn.commit()
        return {"new_id": real_id, "inserted_id": real_id, "status": "success"}
    except mysql.connector.errors.IntegrityError as db_err:
        conn.rollback()
        if "Duplicate entry" in str(db_err) or "1062" in str(db_err):
            raise HTTPException(status_code=409, detail="Certificate record already exists for this student, date, and template.")
        raise HTTPException(status_code=400, detail=str(db_err))
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.put("/api/issued-certificates/{cert_id}")
@app.put("/issued-certificates/{cert_id}")
def update_issued_certificate(cert_id: int, payload: IssuedCertificatePayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        issue_date = payload.issue_date or datetime.now().strftime("%Y-%m-%d")
        cur.callproc(
            "UpdateIssuedCertificate",
            (
                cert_id,
                payload.to_title or "",
                payload.template_type or "graduation",
                str(issue_date),
                payload.certificate_number,
            )
        )
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success", "message": "Issued certificate updated successfully"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@app.delete("/api/issued-certificates/{cert_id}")
@app.delete("/issued-certificates/{cert_id}")
def delete_issued_certificate(cert_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteIssuedCertificate", (cert_id,))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success", "message": "Issued certificate deleted successfully"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


# ===========================================================================
# 17. Batch Offline Synchronization Engine Endpoint  (routers/sync.py: batch_router)
# ===========================================================================

app.include_router(sync_batch_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=2030)

