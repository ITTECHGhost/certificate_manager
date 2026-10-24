# =============================================================================
# services/updater.py — Automated OTA Application Updater
# =============================================================================

import os
import sys
import logging
import hashlib
import requests
import subprocess
from typing import Optional, Dict, Any, Callable

from sync_engine import is_online
from api_config import get_api_url
import api_client

logger = logging.getLogger("updater")

CURRENT_APP_VERSION = "2.0.0"


def parse_version(ver_str: str) -> tuple:
    """Parses semantic version string like '2.1.0' into a comparable tuple of integers (2, 1, 0)."""
    try:
        clean = ver_str.strip().lstrip("v")
        parts = [int(p) for p in clean.split(".") if p.isdigit()]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except Exception:
        return (0, 0, 0)


def is_version_newer(remote_ver: str, local_ver: str = CURRENT_APP_VERSION) -> bool:
    """Returns True if remote_ver is strictly greater than local_ver."""
    return parse_version(remote_ver) > parse_version(local_ver)


def check_for_updates() -> Optional[Dict[str, Any]]:
    """
    Checks remote FastAPI server for available updates.
    Returns update metadata dict if an update is available, or None if up to date or offline.
    """
    if not is_online():
        logger.debug("Offline mode: Skipping OTA update check.")
        return None

    api_url = get_api_url()
    endpoint = f"{api_url}/api/update/version.json"

    try:
        resp = api_client.get(endpoint, timeout=5.0)
        if resp.status_code != 200:
            logger.warning(f"OTA check returned HTTP {resp.status_code}")
            return None

        data = resp.json()
        latest_ver = data.get("latest_version", CURRENT_APP_VERSION)
        
        if is_version_newer(latest_ver, CURRENT_APP_VERSION):
            logger.info(f"New version found: v{latest_ver} (Current: v{CURRENT_APP_VERSION})")
            return {
                "has_update": True,
                "current_version": CURRENT_APP_VERSION,
                "latest_version": latest_ver,
                "minimum_supported_version": data.get("minimum_supported_version", "1.0.0"),
                "release_date": data.get("release_date", ""),
                "changelog_ar": data.get("changelog_ar", ""),
                "changelog_en": data.get("changelog_en", ""),
                "patch_filename": data.get("patch_filename", f"patch_v{latest_ver}.zip"),
                "download_url": data.get("download_url", f"/api/update/download/patch_v{latest_ver}.zip"),
                "sha256": data.get("sha256", ""),
                "size_bytes": data.get("size_bytes", 0),
                "mandatory": data.get("mandatory", False),
            }
        else:
            logger.debug(f"Application is up to date: v{CURRENT_APP_VERSION}")
            return None

    except requests.exceptions.RequestException as e:
        logger.debug(f"OTA update check failed (network/timeout): {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error checking for updates: {e}")
        return None


def calculate_file_sha256(filepath: str) -> str:
    """Computes SHA-256 hex digest for a local file."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest().lower()


def download_patch(
    update_info: Dict[str, Any],
    on_progress: Optional[Callable[[int, int], None]] = None
) -> Optional[str]:
    """
    Downloads the patch ZIP file to local temp directory.
    Validates SHA-256 hash if provided.
    Returns absolute path to downloaded file or None on failure.
    """
    if not is_online():
        return None

    api_url = get_api_url()
    download_path = update_info.get("download_url", "")
    if download_path.startswith("http://") or download_path.startswith("https://"):
        full_url = download_path
    else:
        full_url = f"{api_url}{download_path if download_path.startswith('/') else '/' + download_path}"

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_dir = os.path.join(base_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)

    filename = update_info.get("patch_filename") or f"patch_v{update_info.get('latest_version')}.zip"
    dest_path = os.path.join(temp_dir, filename)

    try:
        logger.info(f"Downloading update patch from {full_url}...")
        resp = api_client.get(full_url, stream=True, timeout=30.0)
        if resp.status_code != 200:
            logger.error(f"Failed to download patch: HTTP {resp.status_code}")
            return None

        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress and total_size > 0:
                        on_progress(downloaded, total_size)

        logger.info(f"Downloaded patch to {dest_path} ({downloaded} bytes)")

        # Verify SHA-256 if expected hash is present
        expected_sha = (update_info.get("sha256") or "").strip().lower()
        if expected_sha:
            computed_sha = calculate_file_sha256(dest_path)
            if computed_sha != expected_sha:
                logger.error(f"SHA-256 mismatch for patch! Expected: {expected_sha}, Got: {computed_sha}")
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
                return None
            logger.info("SHA-256 checksum verified successfully.")

        return dest_path

    except Exception as e:
        logger.error(f"Error during patch download: {e}")
        return None


def apply_patch_and_restart(zip_path: str) -> bool:
    """
    Spawns scripts/apply_patch.bat as an independent detached process and prepares
    for application shutdown.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(base_dir, "scripts", "apply_patch.bat")

    if not os.path.exists(script_path):
        logger.error(f"apply_patch.bat not found at {script_path}")
        return False

    current_pid = str(os.getpid())
    app_dir = base_dir

    # Determine executable name / command
    if getattr(sys, 'frozen', False):
        exe_name = os.path.basename(sys.executable)
    else:
        exe_name = "main.py"

    logger.info(f"Spawning patch application script: {script_path} (PID: {current_pid})")

    try:
        # DETACHED_PROCESS flag ensures the batch script outlives the parent Python process
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

        subprocess.Popen(
            [
                "cmd.exe", "/c", script_path,
                current_pid,
                zip_path,
                app_dir,
                exe_name
            ],
            creationflags=flags,
            close_fds=True
        )
        return True
    except Exception as e:
        logger.error(f"Failed to launch patch application script: {e}")
        return False
