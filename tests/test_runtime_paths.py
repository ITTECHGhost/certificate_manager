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
