# Phase 2 — Install-readiness: data folder, updater, version (Haiku runbook)

Goal: every file the program writes goes through one module, `app_paths.py`.
- Running from source (`py -3 main.py`), nothing changes: data stays in the project folder.
- Installed (PyInstaller build), data goes to `%LOCALAPPDATA%\CertificateManager`.

This phase also:
- fixes the in-app updater, so a patch lands next to the `.exe` and the `.bat` never overwrites itself;
- adds one version file;
- shows a clear message when Microsoft Word is missing.

Read `00-README.md` first. Follow its rules exactly.

## Before you start

````powershell run skip-validate
git branch --show-current
git status --porcelain | Where-Object { $_ -notmatch '^.. "?(logs/|certificates/|\.nicegui/)' }
py -3 -m pytest
````
Expected: `44 passed, 1 deselected`. The first line must be `refactor/install-ready`, and no `git status` lines may be printed. Otherwise STOP.

## Step 2.1 — Write `app_paths.py` (new file, project root)

````python file=app_paths.py
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
````

## Step 2.2 — Write `tests/test_app_paths.py` (new file)

````python file=tests/test_app_paths.py
"""app_paths: where the program reads resources and writes data (source, installed, tests)."""
import importlib
import os
import sys
from pathlib import Path

import pytest

import app_paths
from tests.helpers import PROJECT_ROOT


@pytest.fixture
def reload_paths(monkeypatch):
    """Reload app_paths after changing sys/env. Restores the cwd and the module afterwards."""
    cwd = os.getcwd()
    yield lambda: importlib.reload(app_paths)
    os.chdir(cwd)
    monkeypatch.undo()
    importlib.reload(app_paths)


@pytest.fixture
def frozen_layout(tmp_path, monkeypatch, reload_paths):
    """A fake installed program: install/CertificateManager.exe + install/_internal/... ."""
    install = tmp_path / "install"
    internal = install / "_internal"
    (internal / "templets").mkdir(parents=True)
    (internal / "templets" / "a.docx").write_text("template", encoding="utf-8")
    (internal / "assets").mkdir()
    (internal / "assets" / "logo.png").write_text("logo", encoding="utf-8")
    (internal / "data").mkdir()
    (internal / "data" / "roles_config.json").write_text('{"shipped": true}', encoding="utf-8")
    (internal / "server_config.example.json").write_text('{"host": "example"}', encoding="utf-8")
    exe = install / "CertificateManager.exe"
    exe.write_text("", encoding="utf-8")
    local = tmp_path / "LocalAppData"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(internal), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.delenv("CERTMAN_DATA_DIR", raising=False)
    paths = reload_paths()
    return {"install": install, "internal": internal, "data": local / "CertificateManager", "paths": paths}


def test_source_mode_uses_project_root(monkeypatch, reload_paths):
    monkeypatch.delenv("CERTMAN_DATA_DIR", raising=False)
    paths = reload_paths()
    assert paths.is_frozen() is False
    assert paths.DATA_DIR == PROJECT_ROOT
    assert paths.RESOURCE_DIR == PROJECT_ROOT
    assert paths.INSTALL_DIR == PROJECT_ROOT


def test_env_override_wins(monkeypatch, reload_paths, tmp_path):
    monkeypatch.setenv("CERTMAN_DATA_DIR", str(tmp_path))
    assert reload_paths().DATA_DIR == tmp_path


def test_frozen_uses_localappdata(frozen_layout):
    paths = frozen_layout["paths"]
    assert paths.is_frozen() is True
    assert paths.DATA_DIR == frozen_layout["data"]
    assert paths.RESOURCE_DIR == frozen_layout["internal"]
    assert paths.INSTALL_DIR == frozen_layout["install"]


def test_prepare_seeds_missing_files_only(frozen_layout):
    paths, data = frozen_layout["paths"], frozen_layout["data"]
    (data / "data").mkdir(parents=True)
    (data / "data" / "roles_config.json").write_text('{"edited": true}', encoding="utf-8")
    assert paths.prepare_data_dir() == data
    assert (data / "templets" / "a.docx").read_text(encoding="utf-8") == "template"
    assert (data / "assets" / "logo.png").is_file()
    assert (data / "data" / "roles_config.json").read_text(encoding="utf-8") == '{"edited": true}'
    assert (data / "server_config.json").read_text(encoding="utf-8") == '{"host": "example"}'
    assert (data / "logs").is_dir() and (data / "certificates").is_dir()
    assert Path.cwd() == data
    assert os.environ["NICEGUI_STORAGE_PATH"] == str(data / ".nicegui")


def test_prepare_prefers_server_config_next_to_exe(frozen_layout):
    (frozen_layout["install"] / "server_config.json").write_text('{"host": "laptop"}', encoding="utf-8")
    frozen_layout["paths"].prepare_data_dir()
    assert (frozen_layout["data"] / "server_config.json").read_text(encoding="utf-8") == '{"host": "laptop"}'


def test_prepare_migrates_legacy_db_without_overwriting(frozen_layout):
    paths, data = frozen_layout["paths"], frozen_layout["data"]
    legacy = frozen_layout["internal"] / "local_cache.db"
    legacy.write_bytes(b"old offline edits")
    paths.prepare_data_dir()
    assert (data / "local_cache.db").read_bytes() == b"old offline edits"
    legacy.write_bytes(b"something else")
    paths.prepare_data_dir()
    assert (data / "local_cache.db").read_bytes() == b"old offline edits"


def test_prepare_handles_space_and_arabic_path(frozen_layout, monkeypatch, reload_paths, tmp_path):
    target = tmp_path / "بيانات المستخدم 1"
    monkeypatch.setenv("CERTMAN_DATA_DIR", str(target))
    paths = reload_paths()
    assert paths.prepare_data_dir() == target
    assert Path.cwd() == target
    assert (target / "templets" / "a.docx").is_file()


def test_storage_secret_is_stable(monkeypatch, reload_paths, tmp_path):
    monkeypatch.setenv("CERTMAN_DATA_DIR", str(tmp_path))
    paths = reload_paths()
    first = paths.get_storage_secret()
    assert first == paths.get_storage_secret()
    assert len(first) >= 40
````

````powershell run
py -3 -m pytest tests/test_app_paths.py
````
Expected: `8 passed`

## Step 2.3 — Bootstrap the data folder in `main.py`

Edit `main.py` (three edits).

**Find:**
````text edit-old=main.py
import sys
import asyncio
from nicegui import ui
````
**Replace with:**
````text edit-new=main.py
import sys
import asyncio
from multiprocessing import freeze_support

# Required for the native window in the PyInstaller build (does nothing when run from source).
freeze_support()

import app_paths

# Create the data folder and make it the working directory BEFORE NiceGUI is imported:
# NiceGUI reads NICEGUI_STORAGE_PATH, and relative paths resolve against the data folder.
app_paths.prepare_data_dir()

from nicegui import ui
````

**Find:**
````text edit-old=main.py
    os.makedirs("assets", exist_ok=True)
    app.add_static_files('/assets', 'assets')
````
**Replace with:**
````text edit-new=main.py
    assets_dir = app_paths.data_path("assets")
    assets_dir.mkdir(parents=True, exist_ok=True)
    app.add_static_files('/assets', str(assets_dir))
````

**Find:**
````text edit-old=main.py
        storage_secret = "certificate_manager_secret_key"
````
**Replace with:**
````text edit-new=main.py
        storage_secret = app_paths.get_storage_secret()
````

Write `tests/test_main_bootstrap.py` (new file):

````python file=tests/test_main_bootstrap.py
"""main.py must prepare the data folder before NiceGUI or any screen is imported."""
import ast

from tests.helpers import PROJECT_ROOT

MAIN = PROJECT_ROOT / "main.py"


def _top_level_calls() -> list:
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    return [ast.unparse(node.value.func) for node in tree.body
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)]


def test_freeze_support_then_prepare_data_dir_come_first():
    assert _top_level_calls()[:2] == ["freeze_support", "app_paths.prepare_data_dir"]


def test_data_dir_prepared_before_nicegui_import():
    body = ast.parse(MAIN.read_text(encoding="utf-8")).body
    prepare_at = next(i for i, node in enumerate(body)
                      if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                      and ast.unparse(node.value.func) == "app_paths.prepare_data_dir")
    first_ui_import = next(i for i, node in enumerate(body)
                           if isinstance(node, (ast.Import, ast.ImportFrom))
                           and any(name in ast.unparse(node) for name in ("nicegui", "utils.logger", "nicegui_screens")))
    assert prepare_at < first_ui_import


def test_no_hardcoded_storage_secret():
    assert "certificate_manager_secret_key" not in MAIN.read_text(encoding="utf-8")
````

````powershell run
py -3 -m pytest tests/test_main_bootstrap.py tests/test_app_paths.py
````
Expected: `11 passed`

## Step 2.4 — Commit

````powershell run
git add -- app_paths.py main.py tests/test_app_paths.py tests/test_main_bootstrap.py
git commit -q -m "feat: app_paths data folder; main.py prepares it before NiceGUI starts"
git log --oneline -1
````
Expected: `feat: app_paths data folder`

## Step 2.5 — Route every writable path through `app_paths`

Make each edit below exactly. Some edits say **all occurrences**: for those, set `replace_all` to true.

### `sync_engine.py` (two edits)

**Find:**
````text edit-old=sync_engine.py
import api_client
from api_config import API_URL, get_api_url
````
**Replace with:**
````text edit-new=sync_engine.py
import api_client
import app_paths
from api_config import API_URL, get_api_url
````

**Find:**
````text edit-old=sync_engine.py
_LOCAL_DB_PATH = Path(__file__).resolve().parent / "local_cache.db"
````
**Replace with:**
````text edit-new=sync_engine.py
_LOCAL_DB_PATH = app_paths.data_path("local_cache.db")
````

### `data/repositories.py` (three edits; the third is **all occurrences**)

**Find:**
````text edit-old=data/repositories.py
import api_client
from utils.password_hashing import (
````
**Replace with:**
````text edit-new=data/repositories.py
import api_client
import app_paths
from utils.password_hashing import (
````

**Find:**
````text edit-old=data/repositories.py
    _CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "roles_config.json")
    _USER_ROLES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "user_roles.json")
````
**Replace with:**
````text edit-new=data/repositories.py
    _CONFIG_FILE = str(app_paths.data_path("data", "roles_config.json"))
    _USER_ROLES_FILE = str(app_paths.data_path("data", "user_roles.json"))
````

**Find (all occurrences — `replace_all` = true):**
````text edit-old=data/repositories.py replace-all
log_path = os.path.join("logs", "activity_log.txt")
````
**Replace with:**
````text edit-new=data/repositories.py
log_path = str(app_paths.data_path("logs", "activity_log.txt"))
````

### `utils/logger.py` (three edits)

**Find:**
````text edit-old=utils/logger.py
import traceback
from datetime import datetime
````
**Replace with:**
````text edit-new=utils/logger.py
import traceback
from datetime import datetime

import app_paths
````

**Find:**
````text edit-old=utils/logger.py
    _write_to_file(os.path.join("logs", "system_log.txt"), log_line)
````
**Replace with:**
````text edit-new=utils/logger.py
    _write_to_file(str(app_paths.data_path("logs", "system_log.txt")), log_line)
````

**Find:**
````text edit-old=utils/logger.py
    _write_to_file(os.path.join("logs", "activity_log.txt"), log_line)
````
**Replace with:**
````text edit-new=utils/logger.py
    _write_to_file(str(app_paths.data_path("logs", "activity_log.txt")), log_line)
````

### `nicegui_screens/settings_screen.py` (four edits; the second is **all occurrences**)

**Find:**
````text edit-old=nicegui_screens/settings_screen.py
import api_client
from api_config import get_api_url
````
**Replace with:**
````text edit-new=nicegui_screens/settings_screen.py
import api_client
import app_paths
from api_config import get_api_url
````

**Find (all occurrences — `replace_all` = true):**
````text edit-old=nicegui_screens/settings_screen.py replace-all
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "printer_config.json")
````
**Replace with:**
````text edit-new=nicegui_screens/settings_screen.py
config_path = str(app_paths.data_path("config", "printer_config.json"))
````

**Find:**
````text edit-old=nicegui_screens/settings_screen.py
            log_file = Path("logs/system_log.txt")
````
**Replace with:**
````text edit-new=nicegui_screens/settings_screen.py
            log_file = app_paths.data_path("logs", "system_log.txt")
````

**Find:**
````text edit-old=nicegui_screens/settings_screen.py
        templates_dir = "templets"
````
**Replace with:**
````text edit-new=nicegui_screens/settings_screen.py
        templates_dir = str(app_paths.data_path("templets"))
````

### `nicegui_screens/certificate_screen.py` (six edits)

**Find:**
````text edit-old=nicegui_screens/certificate_screen.py
from docxtpl import DocxTemplate
from nicegui import ui
````
**Replace with:**
````text edit-new=nicegui_screens/certificate_screen.py
from docxtpl import DocxTemplate
from nicegui import ui

import app_paths
````

**Find:**
````text edit-old=nicegui_screens/certificate_screen.py
_cert_dir = os.path.abspath("certificates")
````
**Replace with:**
````text edit-new=nicegui_screens/certificate_screen.py
_cert_dir = str(app_paths.data_path("certificates"))
````

**Find:**
````text edit-old=nicegui_screens/certificate_screen.py
        self.templates_dir = "templets"
````
**Replace with:**
````text edit-new=nicegui_screens/certificate_screen.py
        self.templates_dir = str(app_paths.data_path("templets"))
````

**Find:**
````text edit-old=nicegui_screens/certificate_screen.py
        tpl_path = os.path.join("templets", tpl_name)
````
**Replace with:**
````text edit-new=nicegui_screens/certificate_screen.py
        tpl_path = str(app_paths.data_path("templets", tpl_name))
````

**Find:**
````text edit-old=nicegui_screens/certificate_screen.py
            out_dir = os.path.abspath("certificates")
````
**Replace with:**
````text edit-new=nicegui_screens/certificate_screen.py
            out_dir = str(app_paths.data_path("certificates"))
````

**Find:**
````text edit-old=nicegui_screens/certificate_screen.py
                            p_cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "printer_config.json")
````
**Replace with:**
````text edit-new=nicegui_screens/certificate_screen.py
                            p_cfg_path = str(app_paths.data_path("config", "printer_config.json"))
````

### `services/template_sync.py` (two edits)

**Find:**
````text edit-old=services/template_sync.py
from api_config import get_api_url
import api_client
````
**Replace with:**
````text edit-new=services/template_sync.py
from api_config import get_api_url
import api_client
import app_paths
````

**Find:**
````text edit-old=services/template_sync.py
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(base_dir, "templets")
````
**Replace with:**
````text edit-new=services/template_sync.py
    templates_dir = str(app_paths.data_path("templets"))
````

### `nicegui_ui/template_constants.py` (two edits)

**Find:**
````text edit-old=nicegui_ui/template_constants.py
from typing import Dict, Any, List, Optional
````
**Replace with:**
````text edit-new=nicegui_ui/template_constants.py
from typing import Dict, Any, List, Optional

import app_paths
````

**Find:**
````text edit-old=nicegui_ui/template_constants.py
TEMPLATES_DIR = "templets"
````
**Replace with:**
````text edit-new=nicegui_ui/template_constants.py
TEMPLATES_DIR = str(app_paths.data_path("templets"))
````

### `api_config.py` (three edits)

**Find:**
````text edit-old=api_config.py
import json
from pathlib import Path
````
**Replace with:**
````text edit-new=api_config.py
import json
from pathlib import Path

import app_paths
````

**Find:**
````text edit-old=api_config.py
CONFIG_FILE = Path("server_config.json")
````
**Replace with:**
````text edit-new=api_config.py
CONFIG_FILE = app_paths.data_path("server_config.json")
````

**Find:**
````text edit-old=api_config.py
    import sys
    candidates = [Path.cwd() / path]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / path)
    candidates.append(Path(__file__).resolve().parent / path)
    return next((c for c in candidates if c.exists()), None)
````
**Replace with:**
````text edit-new=api_config.py
    candidates = [app_paths.DATA_DIR / path, app_paths.INSTALL_DIR / path, app_paths.RESOURCE_DIR / path]
    return next((c for c in candidates if c.exists()), None)
````

## Step 2.6 — One version file, and the updater fix

Write `app_version.py` (new file, project root):

````python file=app_version.py
# =============================================================================
# app_version.py — The one place the program version is written
#
# Raise it before every release. scripts\make_client_patch.ps1, the installer
# (via scripts\build_release.bat) and the in-app updater all read it from here.
# =============================================================================

APP_VERSION = "2.1.0"
````

Edit `services/updater.py` (three edits).

**Find:**
````text edit-old=services/updater.py
import api_client

logger = logging.getLogger("updater")

CURRENT_APP_VERSION = "2.0.0"
````
**Replace with:**
````text edit-new=services/updater.py
import api_client
import app_paths
from app_version import APP_VERSION as CURRENT_APP_VERSION

logger = logging.getLogger("updater")
````

**Find:**
````text edit-old=services/updater.py
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_dir = os.path.join(base_dir, "temp")
````
**Replace with:**
````text edit-new=services/updater.py
    temp_dir = str(app_paths.data_path("temp"))
````

**Find:**
````text edit-old=services/updater.py
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
````
**Replace with:**
````text edit-new=services/updater.py
    """
    Copies scripts/apply_patch.bat to %TEMP% and starts that copy as an independent
    detached process (a batch file must not be overwritten while it runs), then the
    caller shuts the application down. The patch is extracted next to the program
    (app_paths.INSTALL_DIR), never into the _internal resources folder.
    """
    source_script = app_paths.resource_path("scripts", "apply_patch.bat")
    if not source_script.exists():
        logger.error(f"apply_patch.bat not found at {source_script}")
        return False

    current_pid = str(os.getpid())
    script_path = build_temp_patch_script_path(current_pid)
    try:
        shutil.copy2(source_script, script_path)
    except OSError as e:
        logger.error(f"Could not copy apply_patch.bat to {script_path}: {e}")
        return False

    app_dir = str(app_paths.INSTALL_DIR)
    log_dir = str(app_paths.data_path("logs"))
````

**Find:**
````text edit-old=services/updater.py
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
````
**Replace with:**
````text edit-new=services/updater.py
        subprocess.Popen(
            build_patch_command(script_path, current_pid, zip_path, app_dir, exe_name, log_dir),
            creationflags=flags,
            close_fds=True
        )
````

**Find:**
````text edit-old=services/updater.py
def apply_patch_and_restart(zip_path: str) -> bool:
````
**Replace with:**
````text edit-new=services/updater.py
def build_temp_patch_script_path(pid: str) -> str:
    """Where the running copy of apply_patch.bat is placed (outside the program folder)."""
    return os.path.join(tempfile.gettempdir(), f"cm_apply_patch_{pid}.bat")


def build_patch_command(script_path: str, pid: str, zip_path: str, app_dir: str, exe_name: str, log_dir: str) -> str:
    """cmd.exe line for apply_patch.bat. /s keeps every quoted path intact (spaces, Arabic letters)."""
    args = " ".join(f'"{value}"' for value in (pid, zip_path, app_dir, exe_name, log_dir))
    return f'cmd.exe /s /c ""{script_path}" {args}"'


def apply_patch_and_restart(zip_path: str) -> bool:
````

**Find:**
````text edit-old=services/updater.py
import subprocess
from typing import Optional, Dict, Any, Callable
````
**Replace with:**
````text edit-new=services/updater.py
import shutil
import subprocess
import tempfile
from typing import Optional, Dict, Any, Callable
````

Edit `scripts/apply_patch.bat` (four edits).

**Find:**
````text edit-old=scripts/apply_patch.bat
::   %4 = Application executable name (e.g. CertificateManager.exe or main.py)
````
**Replace with:**
````text edit-new=scripts/apply_patch.bat
::   %4 = Application executable name (e.g. CertificateManager.exe or main.py)
::   %5 = Folder for system_log.txt (optional; default: the application folder)
````

**Find:**
````text edit-old=scripts/apply_patch.bat
set "EXE_NAME=%~4"
````
**Replace with:**
````text edit-new=scripts/apply_patch.bat
set "EXE_NAME=%~4"
set "LOG_DIR=%~5"
if "%LOG_DIR%"=="" set "LOG_DIR=%APP_DIR%"
````

**Find:**
````text edit-old=scripts/apply_patch.bat
set "LOG_FILE=%APP_DIR%\system_log.txt"
````
**Replace with:**
````text edit-new=scripts/apply_patch.bat
set "LOG_FILE=%LOG_DIR%\system_log.txt"
````

**Find:**
````text edit-old=scripts/apply_patch.bat
:: 6. Relaunch the updated application
````
**Replace with:**
````text edit-new=scripts/apply_patch.bat
:: Test hook: tests/test_updater.py sets CM_PATCH_NO_RELAUNCH=1 to stop here.
if "%CM_PATCH_NO_RELAUNCH%"=="1" exit /b 0

:: 6. Relaunch the updated application
````

Edit `scripts/make_client_patch.ps1` (two edits).

**Find:**
````text edit-old=scripts/make_client_patch.ps1
# Version = CURRENT_APP_VERSION in services\updater.py (raise it before building,
````
**Replace with:**
````text edit-new=scripts/make_client_patch.ps1
# Version = APP_VERSION in app_version.py (raise it before building,
````

**Find:**
````text edit-old=scripts/make_client_patch.ps1
$verLine = Select-String -Path (Join-Path $root "services\updater.py") -Pattern '^CURRENT_APP_VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
if (-not $verLine) { Write-Host "[ERROR] CURRENT_APP_VERSION not found in services\updater.py" -ForegroundColor Red; exit 1 }
````
**Replace with:**
````text edit-new=scripts/make_client_patch.ps1
$verLine = Select-String -Path (Join-Path $root "app_version.py") -Pattern '^APP_VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
if (-not $verLine) { Write-Host "[ERROR] APP_VERSION not found in app_version.py" -ForegroundColor Red; exit 1 }
````

## Step 2.7 — Tests for the paths and the updater

Write `tests/test_runtime_paths.py` (new file):

````python file=tests/test_runtime_paths.py
"""No client module may write next to its own source file or into a cwd-relative folder."""
import os
import subprocess
import sys

from tests.helpers import PROJECT_ROOT

CLIENT_DIRS = ["nicegui_screens", "nicegui_ui", "services", "utils", "data"]
CLIENT_TOP = ["main.py", "sync_engine.py", "api_client.py", "api_config.py", "cert_repository.py"]
FORBIDDEN = [
    'os.path.join("logs"',
    'Path("logs/',
    'parent / "local_cache.db"',
    'os.path.abspath("certificates")',
    '= "templets"',
    'os.path.join("templets"',
    'os.path.join(base_dir, "templets")',
    'os.path.join(base_dir, "temp")',
    'os.path.join(base_dir, "scripts"',
    'Path("server_config.json")',
    'os.path.abspath(__file__))), "data"',
    'os.path.abspath(__file__))), "config"',
]


def _client_files() -> list:
    files = [PROJECT_ROOT / name for name in CLIENT_TOP]
    for folder in CLIENT_DIRS:
        files.extend(sorted((PROJECT_ROOT / folder).rglob("*.py")))
    return files


def test_no_cwd_or_module_relative_runtime_paths():
    offenders = []
    for path in _client_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if any(pattern in line for pattern in FORBIDDEN):
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{number}: {line.strip()}")
    assert offenders == []


def test_runtime_files_land_in_data_dir(tmp_path):
    code = (
        "import utils.logger as logger; logger.log_system('probe'); "
        "import sync_engine, api_config; "
        "print(sync_engine.DB_PATH); print(api_config.CONFIG_FILE)"
    )
    env = {**os.environ, "CERTMAN_DATA_DIR": str(tmp_path), "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run([sys.executable, "-c", code], cwd=str(PROJECT_ROOT), env=env,
                            capture_output=True, text=True, encoding="utf-8", check=True)
    lines = result.stdout.strip().splitlines()
    assert (tmp_path / "logs" / "system_log.txt").is_file()
    assert lines[-2] == str(tmp_path / "local_cache.db")
    assert lines[-1] == str(tmp_path / "server_config.json")
````

Write `tests/test_updater.py` (new file):

````python file=tests/test_updater.py
"""In-app update: one version source, patch lands next to the exe, the .bat copes with any path."""
import json
import os
import subprocess
import zipfile

import app_paths
import app_version
import services.updater as updater
from tests.helpers import PROJECT_ROOT

APPLY_PATCH = PROJECT_ROOT / "scripts" / "apply_patch.bat"


def test_version_single_source():
    assert updater.CURRENT_APP_VERSION == app_version.APP_VERSION
    assert "app_version.py" in (PROJECT_ROOT / "scripts" / "make_client_patch.ps1").read_text(encoding="utf-8")


def test_patch_targets_install_dir_and_runs_temp_copy(monkeypatch):
    calls = []
    monkeypatch.setattr(updater.subprocess, "Popen", lambda command, **kwargs: calls.append(command))
    assert updater.apply_patch_and_restart(r"C:\patches\patch_v9.zip") is True
    temp_script = updater.build_temp_patch_script_path(str(os.getpid()))
    assert os.path.isfile(temp_script)
    command = calls[0]
    assert command.startswith(f'cmd.exe /s /c ""{temp_script}" ')
    assert f'"{app_paths.INSTALL_DIR}"' in command
    assert f'"{app_paths.data_path("logs")}"' in command
    os.remove(temp_script)


def test_apply_patch_handles_space_and_arabic_paths(tmp_path):
    base = tmp_path / "برنامج الشهادات 1"
    app_dir = base / "app"
    log_dir = base / "logs"
    app_dir.mkdir(parents=True)
    log_dir.mkdir()
    (app_dir / "server_config.json").write_text('{"host": "keep"}', encoding="utf-8")
    zip_path = base / "patch v1.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("a.txt", "new file")
        archive.writestr("server_config.json", '{"host": "lose"}')
    command = updater.build_patch_command(str(APPLY_PATCH), "999999", str(zip_path), str(app_dir),
                                          "CertificateManager.exe", str(log_dir))
    env = {**os.environ, "CM_PATCH_NO_RELAUNCH": "1"}
    result = subprocess.run(command, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=180)
    output = result.stdout.decode("mbcs", "replace") + result.stderr.decode("mbcs", "replace")
    assert result.returncode == 0, output
    assert (app_dir / "a.txt").read_text(encoding="utf-8") == "new file"
    assert json.loads((app_dir / "server_config.json").read_text(encoding="utf-8"))["host"] == "keep"
    assert not zip_path.exists()
    assert (log_dir / "system_log.txt").is_file()
````

````powershell run
py -3 -m pytest tests/test_runtime_paths.py tests/test_updater.py
py -3 -m pytest
````
Expected: `60 passed, 1 deselected`. The first run must print `5 passed`.

## Step 2.8 — Commit

````powershell run
git add -- sync_engine.py data/repositories.py utils/logger.py nicegui_screens/settings_screen.py nicegui_screens/certificate_screen.py services/template_sync.py nicegui_ui/template_constants.py api_config.py app_version.py services/updater.py scripts/apply_patch.bat scripts/make_client_patch.ps1 tests/test_runtime_paths.py tests/test_updater.py
git commit -q -m "refactor: writable client files go through app_paths; OTA patch lands next to the exe"
git log --oneline -1
````
Expected: `refactor: writable client files go through app_paths`

## Step 2.9 — A clear message when Microsoft Word is missing

Edit `nicegui_screens/certificate_screen.py`.

**Find:**
````text edit-old=nicegui_screens/certificate_screen.py
                html_path = html_res if isinstance(html_res, str) and os.path.exists(html_res) else None

                self.show_in_app_print_dialog(pdf_path, html_path, self.generated_file_path)
````
**Replace with:**
````text edit-new=nicegui_screens/certificate_screen.py
                html_path = html_res if isinstance(html_res, str) and os.path.exists(html_res) else None
                if pdf_path is None and html_path is None:
                    UI.notify("تعذر تحويل الوثيقة: يتطلب برنامج Microsoft Word / Microsoft Word is required for preview and PDF", type="warning")

                self.show_in_app_print_dialog(pdf_path, html_path, self.generated_file_path)
````

Write `tests/test_office_fallbacks.py` (new file):

````python file=tests/test_office_fallbacks.py
"""Without Word or a print spooler the Office helpers return a value; they never raise."""
import win32com.client
import win32print

import nicegui_screens.certificate_screen as certificate_screen


def _no_word(name):
    raise Exception("Invalid class string")


def _no_spooler(*args, **kwargs):
    raise Exception("The print spooler is not running")


def test_pdf_and_print_without_word(tmp_path, monkeypatch):
    monkeypatch.setattr(win32com.client, "Dispatch", _no_word)
    docx = tmp_path / "x.docx"
    docx.write_bytes(b"not a real document")
    assert certificate_screen.generate_pdf_from_docx(str(docx)) is None
    assert certificate_screen.convert_docx_to_html(str(docx)) is None
    assert certificate_screen.print_file_to_printer(str(docx), "Any Printer") is False


def test_printers_without_spooler(monkeypatch):
    monkeypatch.setattr(win32print, "EnumPrinters", _no_spooler)
    monkeypatch.setattr(win32print, "GetDefaultPrinter", _no_spooler)
    assert certificate_screen.get_installed_printers() == ["Default Printer"]
    assert certificate_screen.get_default_printer() == "Default Printer"
````

````powershell run
py -3 -m pytest
````
Expected: `62 passed, 1 deselected`

## Step 2.10 — Commit

````powershell run
git add -- nicegui_screens/certificate_screen.py tests/test_office_fallbacks.py
git commit -q -m "fix: tell the user when Microsoft Word is missing for preview/PDF"
git log --oneline -1
````
Expected: `fix: tell the user when Microsoft Word is missing`

## Step 2.11 — Check the program from source (the user watches)

````powershell manual
USER CHECK (about 5 minutes):
1. Start the API: double-click certificate_manager_api\start_server.bat (visible window).
2. Run: py -3 main.py
3. Log in, open Students, search, open a student, generate one certificate.
4. Settings -> the logs tab shows recent lines; the printer tab lists printers.
5. Close the app, close the server window.
6. In the project folder, run: git status --short
   Only logs/, certificates/ and .nicegui/ may show changes (they are ignored or untracked).
Tell the executor "checked" or describe what went wrong.
````

## Done

````powershell run
git log --oneline -4
````
Expected: `fix: tell the user when Microsoft Word is missing`
