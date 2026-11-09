# =============================================================================
# services/template_sync.py — Dynamic Word Template Synchronizer
# =============================================================================

import os
import logging
import hashlib
import requests
from typing import Dict, Any, List, Optional

from sync_engine import is_online
from api_config import get_api_url
import api_client
import app_paths

logger = logging.getLogger("template_sync")


def calculate_file_sha256(filepath: str) -> str:
    """Computes SHA-256 hex digest for a local file. Returns empty string if file missing."""
    if not os.path.exists(filepath):
        return ""
    try:
        sha = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        return sha.hexdigest().lower()
    except Exception as e:
        logger.warning(f"Failed to calculate SHA-256 for {filepath}: {e}")
        return ""


def get_local_templates_dir() -> str:
    """Returns absolute path to the local templates directory (templets/)."""
    templates_dir = str(app_paths.data_path("templets"))
    os.makedirs(templates_dir, exist_ok=True)
    return templates_dir


def fetch_server_manifest() -> Optional[Dict[str, Any]]:
    """Fetches templates manifest from the central FastAPI server."""
    if not is_online():
        return None

    api_url = get_api_url()
    endpoint = f"{api_url}/api/templates/manifest"

    try:
        resp = api_client.get(endpoint, timeout=5.0)
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"Failed to fetch templates manifest: HTTP {resp.status_code}")
        return None
    except Exception as e:
        logger.debug(f"Template manifest request failed: {e}")
        return None


def _download_and_atomic_swap(
    filename: str,
    expected_sha: str,
    templates_dir: str,
    api_url: str
) -> bool:
    """
    Downloads a single template from the server to a staging temporary file (.tmp_*)
    and atomically replaces the active target file if the checksum validates.
    """
    download_url = f"{api_url}/api/templates/download/{filename}"
    target_path = os.path.join(templates_dir, filename)
    tmp_path = os.path.join(templates_dir, f".tmp_{filename}")

    try:
        resp = api_client.get(download_url, stream=True, timeout=15.0)
        if resp.status_code != 200:
            logger.error(f"Failed to download {filename}: HTTP {resp.status_code}")
            return False

        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)

        # Validate checksum if expected_sha is provided
        if expected_sha:
            downloaded_sha = calculate_file_sha256(tmp_path)
            if downloaded_sha != expected_sha.lower():
                logger.error(
                    f"Checksum mismatch for {filename}! Server: {expected_sha}, Downloaded: {downloaded_sha}"
                )
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                return False

        # Atomic replacement
        os.replace(tmp_path, target_path)
        logger.info(f"Successfully synced template: {filename}")
        return True

    except Exception as e:
        logger.error(f"Error syncing {filename}: {e}")
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return False


def sync_templates_if_online() -> Dict[str, Any]:
    """
    High-level entry point for template synchronization.
    Compares local files against the remote server manifest.
    Downloads and atomically updates any missing or modified templates.
    """
    result: Dict[str, Any] = {
        "success": True,
        "offline": False,
        "synced_files": [],
        "errors": [],
        "up_to_date": True
    }

    if not is_online():
        result["offline"] = True
        return result

    manifest = fetch_server_manifest()
    if not manifest:
        result["success"] = False
        result["errors"].append("Could not fetch remote templates manifest")
        return result

    templates_dir = get_local_templates_dir()
    api_url = get_api_url()

    # 1. Check templates_config.json
    remote_cfg_sha = (manifest.get("config_sha256") or "").strip().lower()
    local_cfg_path = os.path.join(templates_dir, "templates_config.json")
    local_cfg_sha = calculate_file_sha256(local_cfg_path)

    if remote_cfg_sha and remote_cfg_sha != local_cfg_sha:
        logger.info(f"templates_config.json changed on server. Updating...")
        if _download_and_atomic_swap("templates_config.json", remote_cfg_sha, templates_dir, api_url):
            result["synced_files"].append("templates_config.json")
            result["up_to_date"] = False
        else:
            result["errors"].append("templates_config.json")

    # 2. Check each Word docx template
    remote_templates = manifest.get("templates", [])
    for item in remote_templates:
        filename = item.get("filename")
        expected_sha = (item.get("sha256") or "").strip().lower()

        if not filename:
            continue

        local_file_path = os.path.join(templates_dir, filename)
        local_file_sha = calculate_file_sha256(local_file_path)

        if not os.path.exists(local_file_path) or (expected_sha and local_file_sha != expected_sha):
            logger.info(f"Syncing template {filename} from server (Checksum mismatch or missing)...")
            if _download_and_atomic_swap(filename, expected_sha, templates_dir, api_url):
                result["synced_files"].append(filename)
                result["up_to_date"] = False
            else:
                result["errors"].append(filename)

    # 3. Templates deleted on another computer: gone from the server and from the config
    if not result["errors"]:
        try:
            removed = remove_templates_deleted_on_server(
                [t.get("filename") or "" for t in remote_templates], templates_dir)
            if removed:
                result["removed_files"] = removed
                result["up_to_date"] = False
        except Exception as e:
            logger.warning(f"Could not remove templates deleted on the server: {e}")

    if result["errors"]:
        result["success"] = False

    return result


def push_templates_config() -> bool:
    """Sends the local templates_config.json to the server, so names and tags saved in
    Settings survive the startup sync (which otherwise restores the server's copy).
    Returns False when offline or the upload fails; the local file is kept either way."""
    if not is_online():
        return False
    path = os.path.join(get_local_templates_dir(), "templates_config.json")
    if not os.path.exists(path):
        return False
    try:
        with open(path, "rb") as f:
            files = {"file": ("templates_config.json", f.read(), "application/json")}
        resp = api_client.post(f"{get_api_url()}/api/templates/upload", files=files, timeout=10.0)
        if resp.status_code == 200:
            return True
        logger.warning(f"Template config upload failed: HTTP {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Template config upload failed: {e}")
    return False


def push_template_file(filename: str) -> bool:
    """Sends one local .docx to the server, so other computers receive it at their next sync."""
    if not is_online():
        return False
    path = os.path.join(get_local_templates_dir(), filename)
    if not os.path.isfile(path):
        return False
    try:
        with open(path, "rb") as f:
            files = {"file": (filename, f.read(),
                              "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        resp = api_client.post(f"{get_api_url()}/api/templates/upload", files=files, timeout=20.0)
        if resp.status_code == 200:
            return True
        logger.warning(f"Template upload failed: HTTP {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Template upload failed: {e}")
    return False


def delete_template_everywhere(filename: str) -> tuple[bool, str]:
    """Deletes a template on the server, then here. Needs the server: deleting only here would
    come back at the next sync. Local files go to templets/.deleted/, never erased."""
    from urllib.parse import quote
    from nicegui_ui.template_constants import delete_template_config

    if not is_online():
        return False, "حذف القالب يحتاج الاتصال بالخادم"
    try:
        resp = api_client.delete(f"{get_api_url()}/api/templates/{quote(filename)}", timeout=10.0)
        if resp.status_code != 200:
            return False, f"رفض الخادم الحذف (HTTP {resp.status_code})"
    except Exception as e:
        return False, f"تعذر الاتصال بالخادم: {e}"
    _move_to_local_trash(filename)
    delete_template_config(filename)
    if not push_templates_config():
        return False, "حُذف الملف، لكن تعذر تحديث قائمة القوالب على الخادم"
    return True, ""


def _move_to_local_trash(filename: str, templates_dir: str = "") -> None:
    from datetime import datetime
    templates_dir = templates_dir or get_local_templates_dir()
    src = os.path.join(templates_dir, filename)
    if not os.path.isfile(src):
        return
    trash = os.path.join(templates_dir, ".deleted")
    os.makedirs(trash, exist_ok=True)
    os.replace(src, os.path.join(trash, f"{datetime.now():%Y%m%d-%H%M%S} {filename}"))


def remove_templates_deleted_on_server(server_files: List[str], templates_dir: str) -> List[str]:
    """Local .docx files that the server no longer has AND that have no entry in the (already
    synced) templates_config.json were deleted on another computer: move them to .deleted/.
    A local template that is still registered (e.g. not uploaded yet) is kept."""
    import json
    from nicegui_ui.template_constants import normalize_template_key
    on_server = {f.lower() for f in server_files}
    try:  # the file itself, not load_templates_config(): that one re-adds the built-in defaults
        with open(os.path.join(templates_dir, "templates_config.json"), encoding="utf-8") as fh:
            config = json.load(fh)
    except Exception:
        return []  # unreadable config: never remove anything
    if not isinstance(config, dict) or not config:
        return []
    registered = {normalize_template_key(v.get("file") or k).lower() for k, v in config.items()} | \
                 {normalize_template_key(k).lower() for k in config}
    removed = []
    for f in os.listdir(templates_dir):
        if not f.lower().endswith(".docx") or f.startswith("~") or f.lower() in on_server:
            continue
        if normalize_template_key(f).lower() in registered:
            continue
        _move_to_local_trash(f, templates_dir)
        removed.append(f)
    return removed
