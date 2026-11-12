# =============================================================================
# routers/server_update.py — upload a server update from Settings (admins only)
#
# The admin's program uploads CertificateManagerUpdate-<v>.zip (made by
# scripts\build_update.ps1) with their username + password and a time.
# The zip waits in UPDATES_DIR\incoming\ with pending.json; the scheduled task
# "CertificateManagerServerUpdater" (server_updater.ps1, runs as SYSTEM every
# minute) runs its update.ps1 when the time comes and writes status.json.
# UPDATES_DIR is outside C:\AppServ\www, so Apache never serves it.
# =============================================================================

import hashlib
import json
import os
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from deps import get_db
from routers.personnel import _authenticate_user

router = APIRouter(prefix="/api/admin/server-update", tags=["server-update"])

API_DIR = Path(__file__).resolve().parents[1]
UPDATES_DIR = Path("C:/AppServ/server_updates") if os.path.isdir("C:/AppServ") else API_DIR / "server_updates"
HEARTBEAT_MAX_AGE_S = 180


def _paths(base: Path) -> dict:
    return {
        "incoming": base / "incoming",
        "pending": base / "pending.json",
        "status": base / "status.json",
        "heartbeat": base / "heartbeat.txt",
    }


def parse_version(text: str) -> tuple:
    parts = [int(p) for p in re.findall(r"\d+", text or "")[:3]]
    return tuple(parts + [0] * (3 - len(parts)))


def installed_version(api_dir: Path = API_DIR) -> str:
    f = api_dir / "server_version.txt"
    try:
        return f.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return ""


def read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def zip_version(zip_path: Path) -> str:
    """VERSION.txt of an update zip (at the root or inside its one top folder); checks
    that update.ps1 and checksums.txt sit beside it. Raises ValueError otherwise."""
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = [n.replace("\\", "/") for n in z.namelist()]
            for n in names:
                parts = n.split("/")
                if parts[-1] == "VERSION.txt" and len(parts) <= 2:
                    prefix = "/".join(parts[:-1])
                    prefix = prefix + "/" if prefix else ""
                    if f"{prefix}update.ps1" in names and f"{prefix}checksums.txt" in names:
                        version = z.read(n).decode("utf-8-sig").strip()
                        if re.fullmatch(r"\d+\.\d+\.\d+", version):
                            return version
    except zipfile.BadZipFile:
        raise ValueError("الملف ليس ملفاً مضغوطاً صالحاً")
    raise ValueError("هذا ليس ملف تحديث (CertificateManagerUpdate-x.y.z.zip)")


def parse_run_at(value: str) -> datetime:
    """'now' or 'YYYY-MM-DDTHH:MM' (server local time)."""
    if not value or value == "now":
        return datetime.now().replace(second=0, microsecond=0)
    try:
        return datetime.strptime(value[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        raise ValueError("وقت التحديث غير صالح")


def _require_admin(conn, username: str, password: str) -> dict:
    user = _authenticate_user(conn, username or "", password or "")
    if not user:
        raise HTTPException(status_code=401, detail="اسم المستخدم أو كلمة المرور غير صحيحة")
    if str(user.get("personnel_role") or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="تحديث الخادم لمدير النظام فقط")
    return user


def build_status(base: Path = UPDATES_DIR, api_dir: Path = API_DIR) -> dict:
    p = _paths(base)
    beat_ok = False
    try:
        beat_ok = (datetime.now().timestamp() - p["heartbeat"].stat().st_mtime) < HEARTBEAT_MAX_AGE_S
    except OSError:
        pass
    return {
        "server_version": installed_version(api_dir),
        "pending": read_json(p["pending"]),
        "last": read_json(p["status"]),
        "updater_running": beat_ok,
        "https": server_https(api_dir),
        "https_ready": (api_dir / "certs" / "server.crt").exists(),
        "mode_request": read_json(base / "mode.json"),
        "mode_result": read_json(base / "mode_status.json"),
    }


def server_https(api_dir: Path = API_DIR) -> bool:
    s = read_json(api_dir / "server_settings.json") or {}
    return str(s.get("https")).lower() == "true"


@router.get("/status")
def get_status():
    return build_status()


@router.post("/upload")
async def upload_update(
    file: UploadFile = File(...),
    username: str = Form(...),
    password: str = Form(...),
    run_at: str = Form("now"),
    conn=Depends(get_db),
):
    user = _require_admin(conn, username, password)
    p = _paths(UPDATES_DIR)
    p["incoming"].mkdir(parents=True, exist_ok=True)
    current = read_json(p["status"]) or {}
    if current.get("state") == "running":
        raise HTTPException(status_code=409, detail="يوجد تحديث قيد التنفيذ الآن")

    tmp = p["incoming"] / ".upload.tmp"
    h = hashlib.sha256()
    with open(tmp, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)
            h.update(chunk)
    try:
        version = zip_version(tmp)
        when = parse_run_at(run_at)
    except ValueError as exc:
        tmp.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc))

    have = installed_version()
    if have and parse_version(version) <= parse_version(have):
        tmp.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"الخادم لديه الإصدار {have} بالفعل؛ الملف المرفوع {version}")

    # One waiting update at a time: a new upload replaces the old one
    for old in p["incoming"].glob("*.zip"):
        old.unlink(missing_ok=True)
    target = p["incoming"] / f"CertificateManagerUpdate-{version}.zip"
    tmp.replace(target)
    pending = {
        "version": version,
        "file": str(target),
        "sha256": h.hexdigest(),
        "run_at": when.strftime("%Y-%m-%dT%H:%M"),
        "uploaded_by": user.get("name_ar") or username,
        "uploaded_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    p["pending"].write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "success", "pending": pending, "updater_running": build_status()["updater_running"]}


@router.post("/mode")
def request_mode(mode: str = Form(...), username: str = Form(...), password: str = Form(...),
                 conn=Depends(get_db)):
    """Asks the updater task to switch the server between HTTP and HTTPS within a minute."""
    _require_admin(conn, username, password)
    mode = (mode or "").lower()
    if mode not in ("http", "https"):
        raise HTTPException(status_code=400, detail="mode: http أو https")
    if mode == "https" and not (API_DIR / "certs" / "server.crt").exists():
        raise HTTPException(status_code=409, detail="شهادات HTTPS غير موجودة على الخادم: ثبّت الإصدار 2.4.0 بملف Update.bat أولاً")
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    (UPDATES_DIR / "mode.json").write_text(
        json.dumps({"mode": mode, "requested_by": username, "requested_at": datetime.now().strftime("%Y-%m-%dT%H:%M")}),
        encoding="utf-8")
    return {"status": "success", "mode": mode}


@router.post("/cancel")
def cancel_update(username: str = Form(...), password: str = Form(...), conn=Depends(get_db)):
    _require_admin(conn, username, password)
    p = _paths(UPDATES_DIR)
    if not p["pending"].exists():
        return {"status": "success", "cancelled": False}
    p["pending"].unlink(missing_ok=True)
    shutil.rmtree(p["incoming"], ignore_errors=True)
    return {"status": "success", "cancelled": True}
