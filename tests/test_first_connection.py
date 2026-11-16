"""A new laptop with only the example settings must be seen as "not connected", and
importing the server's client_package must connect it (settings + college CA)."""
import json

import pytest

import api_config
import app_paths
from services import first_connection as fc

EXAMPLE = {"host": "127.0.0.1", "port": 2030, "app_key": fc.PLACEHOLDER_KEY, "scheme": "http"}
PACKAGE = {"host": "10.9.8.7", "port": 2030, "scheme": "https", "secret": "s",
           "app_key": "test-key-not-real", "ca_cert": "certs/college_ca.crt",
           "api_url": "https://10.9.8.7:2030"}


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setattr(app_paths, "DATA_DIR", d)
    monkeypatch.setattr(app_paths, "DOCS_DIR", d)
    monkeypatch.setattr(api_config, "CONFIG_FILE", d / "server_config.json")
    saved = dict(api_config._client_cfg)
    yield d
    api_config._apply(saved)


def _package(folder):
    (folder / "certs").mkdir(parents=True)
    (folder / "server_config.json").write_text(json.dumps(PACKAGE), encoding="utf-8")
    (folder / "certs" / "college_ca.crt").write_text("-----BEGIN CERTIFICATE-----\nx\n", encoding="utf-8")
    return folder


@pytest.mark.parametrize("raw, expected", [
    (EXAMPLE, False),
    ({}, False),
    ({"host": "localhost", "app_key": ""}, False),
    (PACKAGE, True),
    ({"host": "172.50.1.100", "app_key": ""}, True),        # audit mode: address only
    ({"host": "127.0.0.1", "app_key": "real"}, True),        # the server laptop itself
])
def test_is_configured(raw, expected):
    assert fc.is_configured(raw) is expected


def test_example_config_is_not_configured(data_dir):
    (data_dir / "server_config.json").write_text(json.dumps(EXAMPLE), encoding="utf-8")
    assert fc.is_configured() is False


def test_import_client_package(data_dir, tmp_path):
    (data_dir / "server_config.json").write_text(json.dumps(EXAMPLE), encoding="utf-8")
    pkg = _package(tmp_path / "usb" / "client_package")

    ok, msg = fc.import_client_package(pkg)

    assert ok, msg
    assert fc.is_configured() is True
    assert json.loads((data_dir / "server_config.json").read_text(encoding="utf-8"))["host"] == "10.9.8.7"
    assert (data_dir / "certs" / "college_ca.crt").is_file()
    assert api_config.get_api_url() == "https://10.9.8.7:2030"
    assert "test-key-not-real" not in msg


@pytest.mark.parametrize("pick", ["parent", "file"])
def test_import_accepts_parent_or_file(data_dir, tmp_path, pick):
    pkg = _package(tmp_path / "usb" / "client_package")
    target = pkg.parent if pick == "parent" else pkg / "server_config.json"
    ok, _ = fc.import_client_package(target)
    assert ok


def test_import_refuses_example_or_missing(data_dir, tmp_path):
    ok, _ = fc.import_client_package(tmp_path / "nothing")
    assert not ok
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "server_config.json").write_text(json.dumps(EXAMPLE), encoding="utf-8")
    ok, _ = fc.import_client_package(bad)
    assert not ok
    assert not (data_dir / "server_config.json").exists()


def test_save_address_drops_placeholder_key(data_dir):
    (data_dir / "server_config.json").write_text(json.dumps(EXAMPLE), encoding="utf-8")
    ok, _ = fc.save_address("172.50.1.100", "2030")
    assert ok
    saved = json.loads((data_dir / "server_config.json").read_text(encoding="utf-8"))
    assert saved["host"] == "172.50.1.100" and saved["app_key"] == ""
    assert api_config.get_api_url() == "https://172.50.1.100:2030"
    assert fc.is_configured() is True
