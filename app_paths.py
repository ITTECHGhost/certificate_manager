# =============================================================================
# app_paths.py — Where the program reads its files and writes its data
#
# Running from source: everything stays in the project folder (as before).
# Installed (PyInstaller build): program files are read-only; everything the
# program writes lives in %LOCALAPPDATA%\CertificateManager.
# CERTMAN_DATA_DIR overrides the data folder (tests use this).
# =============================================================================

import os
import secrets
import shutil
import sys
from pathlib import Path

DATA_DIR_ENV = "CERTMAN_DATA_DIR"
APP_FOLDER_NAME = "CertificateManager"

# Copied from the program into the data folder on start, only when missing there,
# so a user's changes are never overwritten.
SEED_ITEMS = (
    "templets",
    "assets",
    "data/roles_config.json",
    "data/user_roles.json",
    "certs/college_ca.crt",
)


def is_frozen() -> bool:
    """True when running as the PyInstaller-built CertificateManager.exe."""
    return bool(getattr(sys, "frozen", False))


def _resolve_dirs() -> tuple[Path, Path, Path]:
    project_root = Path(__file__).resolve().parent
    if is_frozen():
        install_dir = Path(sys.executable).resolve().parent
        resource_dir = Path(getattr(sys, "_MEIPASS", install_dir))
        local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        default_data = Path(local_appdata) / APP_FOLDER_NAME
    else:
        install_dir = project_root
        resource_dir = project_root
        default_data = project_root
    override = os.environ.get(DATA_DIR_ENV)
    data_dir = Path(override) if override else default_data
    return install_dir, resource_dir, data_dir


INSTALL_DIR, RESOURCE_DIR, DATA_DIR = _resolve_dirs()


def data_path(*parts: str) -> Path:
    """A path inside the writable data folder."""
    return DATA_DIR.joinpath(*parts)


def resource_path(*parts: str) -> Path:
    """A path inside the read-only program resources (the _internal folder when installed)."""
    return RESOURCE_DIR.joinpath(*parts)


def _copy_missing(src: Path, dst: Path) -> None:
    """Copy src to dst. Folders are copied file by file. An existing file is never overwritten."""
    if src.is_dir():
        for item in src.rglob("*"):
            if item.is_file():
                target = dst / item.relative_to(src)
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)
    elif src.is_file() and not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _first_existing(*candidates: Path) -> Path | None:
    return next((c for c in candidates if c.is_file()), None)


def prepare_data_dir() -> Path:
    """Create and fill the data folder, then make it the working directory. Safe to call many times."""
    for sub in ("logs", "certificates"):
        data_path(sub).mkdir(parents=True, exist_ok=True)

    if RESOURCE_DIR.resolve() != DATA_DIR.resolve():
        for item in SEED_ITEMS:
            _copy_missing(resource_path(item), data_path(item))

    server_cfg = data_path("server_config.json")
    if not server_cfg.exists():
        source = _first_existing(INSTALL_DIR / "server_config.json", resource_path("server_config.example.json"))
        if source is not None and source.resolve() != server_cfg.resolve():
            shutil.copy2(source, server_cfg)

    # A laptop updated from the old portable build keeps its offline edits.
    local_db = data_path("local_cache.db")
    if not local_db.exists():
        legacy = _first_existing(INSTALL_DIR / "_internal" / "local_cache.db", INSTALL_DIR / "local_cache.db")
        if legacy is not None and legacy.resolve() != local_db.resolve():
            shutil.copy2(legacy, local_db)

    os.environ["NICEGUI_STORAGE_PATH"] = str(data_path(".nicegui"))
    os.chdir(DATA_DIR)
    return DATA_DIR


def get_storage_secret() -> str:
    """Random per-install secret for NiceGUI's browser storage (created on first use)."""
    secret_file = data_path(".storage_secret")
    if secret_file.is_file():
        value = secret_file.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = secrets.token_urlsafe(32)
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    secret_file.write_text(value, encoding="utf-8")
    return value
