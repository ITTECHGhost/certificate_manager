"""The server bundle holds what setup_server needs, and never this laptop's secrets."""
import subprocess

import pytest

from tests.helpers import PROJECT_ROOT

SECRET_NAMES = {"app_keys.json", "db_config.json", "server_settings.json", "server_config.json"}
REQUIRED = [
    "api/main.py", "api/.htaccess", "api/install_service.bat", "api/config.py", "api/db_config.example.json",
    "sql/schema.sql", "sql/SP.sql", "sql/fixes/2026-10-27_04_api_db_account.sql",
    "templets/templates_config.json", "requirements-server.txt", "setup_server.bat", "setup_server.ps1",
    "SERVER_SETUP_GUIDE.md", "VERSION.txt",
]


@pytest.fixture(scope="module")
def built_bundle(tmp_path_factory):
    out = tmp_path_factory.mktemp("bundle")
    subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(PROJECT_ROOT / "scripts" / "build_server_bundle.ps1"), "-OutDir", str(out), "-SkipWheels"],
                   check=True, capture_output=True, timeout=600)
    return next(path for path in out.iterdir() if path.is_dir())


def test_bundle_has_no_secrets(built_bundle):
    names = [path.relative_to(built_bundle).as_posix() for path in built_bundle.rglob("*") if path.is_file()]
    leaked = [name for name in names
              if name.endswith(".key") or name.rsplit("/", 1)[-1] in SECRET_NAMES
              or name.startswith(("api/certs/", "api/client_package/", "api/logs/"))]
    assert leaked == []


def test_bundle_has_required_files(built_bundle):
    missing = [name for name in REQUIRED if not (built_bundle / name).is_file()]
    assert missing == []
