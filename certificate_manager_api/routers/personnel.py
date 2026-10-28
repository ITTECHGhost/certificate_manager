"""Personnel & authentication routes: /personnel/* /login /api/login /api/logout /permissions /roles /user-roles."""
import json as _json
from typing import List, Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import (logger, get_db, decode_db_value, execute_sp_fetchall, execute_sp_fetchone,
                  _set_must_change_password)
from password_hashing import hash_password, verify_password, needs_upgrade, prepare_for_storage

router = APIRouter()


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


@router.get("/personnel", response_model=List[PersonnelResponse])
def get_personnel(conn=Depends(get_db)):
    try:
        rows = execute_sp_fetchall(conn, "GetAllPersonnel")
        for r in rows:
            r["is_signature"] = bool(r.get("is_signature"))
            r["page_location"] = int(r.get("page_location") or 0)
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/personnel/active")
def get_active_personnel(conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetActivePersonnel")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/personnel/{person_id}", response_model=PersonnelResponse)
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


@router.post("/personnel/login")
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


@router.post("/api/login")
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


@router.put("/personnel/{person_id}/password")
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


@router.post("/api/logout")
def logout():
    return {"success": True, "message": "Logged out successfully"}


@router.post("/personnel")
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


@router.put("/personnel/{person_id}")
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


@router.post("/personnel/{person_id}/toggle")
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


@router.delete("/personnel/{person_id}")
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


@router.get("/permissions")
def get_all_permissions(conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT permission_key, category, name_ar, name_en, description_ar FROM permissions ORDER BY category, permission_key")
        return cur.fetchall()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.get("/personnel/{person_id}/permissions")
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


@router.put("/personnel/{person_id}/permissions")
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


@router.get("/roles")
def get_all_roles(conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM roles ORDER BY is_system DESC, id ASC")
        return [_role_row_out(r) for r in cur.fetchall()]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.post("/roles")
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


@router.delete("/roles/{role_id}")
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


@router.get("/user-roles")
def get_user_roles(conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT personnel_id, role_id FROM user_roles")
        return decode_db_value(cur.fetchall())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.put("/user-roles/{personnel_id}")
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
