# =============================================================================
# certificate_manager_api/routers/templates.py — Template Synchronization API
# =============================================================================

import os
import re
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger("api.templates")

router = APIRouter(prefix="/api/templates", tags=["templates"])

# Primary server templates directory
SERVER_TEMPLATES_DIR = Path("C:/AppServ/www/certificate_manager_api/templets")
if not SERVER_TEMPLATES_DIR.exists():
    SERVER_TEMPLATES_DIR = Path("templets")

SERVER_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def compute_file_hash(path: Path) -> str:
    """Computes SHA-256 hash of a file on disk."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@router.get("/manifest")
def get_templates_manifest():
    """
    Returns a manifest of all available .docx certificate templates
    and templates_config.json with SHA-256 hashes and file metrics.
    """
    templates_list = []
    config_hash = ""

    config_file = SERVER_TEMPLATES_DIR / "templates_config.json"
    if config_file.exists():
        try:
            config_hash = compute_file_hash(config_file)
        except Exception as e:
            logger.warning(f"Error hashing templates_config.json: {e}")

    for file_path in SERVER_TEMPLATES_DIR.glob("*.docx"):
        try:
            f_stat = file_path.stat()
            file_hash = compute_file_hash(file_path)
            templates_list.append({
                "filename": file_path.name,
                "sha256": file_hash,
                "size_bytes": f_stat.st_size,
                "modified_at": datetime.fromtimestamp(f_stat.st_mtime).isoformat()
            })
        except Exception as err:
            logger.warning(f"Failed to process template '{file_path.name}': {err}")

    return {
        "status": "success",
        "config_sha256": config_hash,
        "templates": sorted(templates_list, key=lambda x: x["filename"])
    }


@router.get("/download/{template_name}")
def download_template(template_name: str):
    """Streams the requested .docx template or configuration file."""
    # Strict validation against path traversal
    if not re.match(r"^[a-zA-Z0-9_\-\.\s\(\)]+\.(docx|json)$", template_name, re.IGNORECASE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid template filename."
        )

    target_path = SERVER_TEMPLATES_DIR / template_name
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_name}' not found on server."
        )

    media_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if template_name.lower().endswith(".docx")
        else "application/json"
    )

    return FileResponse(
        path=str(target_path),
        filename=template_name,
        media_type=media_type
    )


@router.post("/upload")
async def upload_template(
    file: UploadFile = File(...),
    admin_secret: Optional[str] = Form(None)
):
    """
    Privileged endpoint to upload/replace a .docx certificate template or configuration file.
    """
    filename = file.filename or ""
    if not re.match(r"^[a-zA-Z0-9_\-\.\s\(\)]+\.(docx|json)$", filename, re.IGNORECASE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .docx and .json files are permitted for template updates."
        )

    target_path = SERVER_TEMPLATES_DIR / filename
    temp_path = SERVER_TEMPLATES_DIR / f".tmp_{filename}"

    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        # Atomic replacement
        temp_path.replace(target_path)
        new_hash = compute_file_hash(target_path)
        logger.info(f"Successfully uploaded template '{filename}' (SHA-256: {new_hash[:8]}...)")

        return {
            "status": "success",
            "filename": filename,
            "sha256": new_hash,
            "size_bytes": target_path.stat().st_size
        }
    except Exception as exc:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        logger.error(f"Failed to upload template '{filename}': {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Template upload failed: {str(exc)}"
        )
