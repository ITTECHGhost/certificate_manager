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

    if result["errors"]:
        result["success"] = False

    return result
