# =============================================================================
# certificate_manager_api/routers/updates.py — Automated OTA Update Pipeline
# =============================================================================

import os
import re
import json
import hashlib
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger("api.updates")

router = APIRouter(prefix="/api/update", tags=["updates"])

# Update payload directories
BASE_SERVER_DIR = Path("C:/AppServ/www/updates") if os.path.exists("C:/AppServ/www") else Path("updates")
PATCHES_DIR = BASE_SERVER_DIR / "patches"
MANIFEST_FILE = BASE_SERVER_DIR / "version.json"

PATCHES_DIR.mkdir(parents=True, exist_ok=True)

# The updates folder sits in Apache's web root: block direct Apache downloads so
# patches are only served through this API (which checks the application key).
_HTACCESS = BASE_SERVER_DIR / ".htaccess"
if not _HTACCESS.exists():
    try:
        _HTACCESS.write_text("# Served only through the FastAPI /api/update endpoints\nRequire all denied\n", encoding="utf-8")
    except OSError as _ht_err:
        logger.warning(f"Could not write {_HTACCESS}: {_ht_err}")


class VersionManifest(BaseModel):
    latest_version: str
    minimum_supported_version: Optional[str] = "2.0.0"
    release_date: Optional[str] = "2026-10-25"
    changelog_ar: Optional[str] = "إصلاح المصادقة دون اتصال ودعم الاستيراد المجمع الذري ومزامنة القوالب الهوائية"
    changelog_en: Optional[str] = "Offline authentication fix, atomic bulk import, and OTA template sync"
    patch_filename: str
    download_url: str
    sha256: str
    size_bytes: int
    mandatory: Optional[bool] = False


def _get_or_create_manifest() -> dict:
    """Loads existing version manifest or seeds initial default."""
    if MANIFEST_FILE.exists():
        try:
            with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error reading {MANIFEST_FILE}: {e}")

    default_manifest = {
        "latest_version": "2.1.0",
        "minimum_supported_version": "2.0.0",
        "release_date": "2026-10-25",
        "changelog_ar": "إصلاح المصادقة دون اتصال ودعم الاستيراد المجمع الذري ومزامنة القوالب الهوائية",
        "changelog_en": "Offline authentication fix, atomic bulk import, and OTA template sync",
        "patch_filename": "patch_v2.1.0.zip",
        "download_url": "/api/update/download/patch_v2.1.0.zip",
        "sha256": "",
        "size_bytes": 0,
        "mandatory": False
    }

    try:
        with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
            json.dump(default_manifest, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Could not persist default manifest: {e}")

    return default_manifest


@router.get("/version.json")
def get_version_manifest():
    """Returns the latest application release metadata and patch download details."""
    manifest = _get_or_create_manifest()

    # Automatically compute file size and hash if patch exists on disk
    patch_path = PATCHES_DIR / manifest.get("patch_filename", "")
    if patch_path.exists():
        manifest["size_bytes"] = patch_path.stat().st_size
        if not manifest.get("sha256"):
            h = hashlib.sha256()
            with open(patch_path, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            manifest["sha256"] = h.hexdigest()

    return manifest


@router.get("/download/{patch_filename}")
def download_patch(patch_filename: str):
    """Streams the requested .zip patch archive with strict path traversal validation."""
    # Enforce safe alphanumeric and dot filename convention
    if not re.match(r"^[a-zA-Z0-9_\-\.]+\.zip$", patch_filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid patch filename format. Must be a .zip file."
        )

    patch_path = PATCHES_DIR / patch_filename
    if not patch_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patch file '{patch_filename}' was not found on the server."
        )

    return FileResponse(
        path=str(patch_path),
        filename=patch_filename,
        media_type="application/zip"
    )
