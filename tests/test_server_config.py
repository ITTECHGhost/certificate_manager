import importlib.util
import re
import subprocess

import pytest

from tests.helpers import API_DIR, PROJECT_ROOT


def _load_api_config():
    spec = importlib.util.spec_from_file_location("api_server_config", API_DIR / "config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_db_config_reads_json(tmp_path):
    config = _load_api_config()
    path = tmp_path / "db_config.json"
    path.write_text('{"host": "h", "user": "u", "password": "p", "database": "d"}', encoding="utf-8")
    assert config.load_db_settings(path) == {"host": "h", "user": "u", "password": "p", "database": "d"}


def test_db_config_missing_names_setup(tmp_path):
    config = _load_api_config()
    with pytest.raises(RuntimeError, match="setup_server.bat"):
        config.load_db_settings(tmp_path / "db_config.json")


def test_api_has_no_fallback_db_login():
    source = (API_DIR / "deps.py").read_text(encoding="utf-8")
    assert "12345678" not in source
    assert '"root"' not in source


def test_no_db_password_literal_in_tracked_python():
    listing = subprocess.run(["git", "ls-files", "-z", "--", "*.py"], cwd=PROJECT_ROOT,
                             capture_output=True, check=True).stdout.decode("utf-8")
    pattern = re.compile(r"""DB_PASSWORD\s*=\s*['"]|['"]password['"]\s*:\s*['"][^'"]+['"]""")
    hits = [p for p in listing.split("\0")
            if p and not p.startswith(("old/", "tests/"))
            and pattern.search((PROJECT_ROOT / p).read_text(encoding="utf-8", errors="ignore"))]
    assert hits == []
