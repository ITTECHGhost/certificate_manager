"""Settings & appearance routes: /settings/* and /api/user/appearance*."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import get_db, execute_sp_fetchone

router = APIRouter()


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


@router.get("/settings")
def get_settings(conn=Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "GetUniversitySettings")
        return row or {}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/settings")
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


@router.get("/settings/appearance/{user_id}")
@router.get("/api/user/appearance/{emp_id}")
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


@router.put("/settings/appearance/{user_id}")
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


@router.post("/api/user/appearance")
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


@router.post("/settings/clear-logs")
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
