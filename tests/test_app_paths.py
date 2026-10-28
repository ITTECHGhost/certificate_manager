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
