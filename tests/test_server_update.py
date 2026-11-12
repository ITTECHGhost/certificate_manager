import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "certificate_manager_api"))
from routers import server_update as su  # noqa: E402


def _zip(path: Path, version="2.3.0", prefix="CertificateManagerUpdate-2.3.0/", files=("update.ps1", "checksums.txt")):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(prefix + "VERSION.txt", version + "\r\n")
        for f in files:
            z.writestr(prefix + f, "x")
    return path


def test_zip_version_reads_folder_or_root(tmp_path):
    assert su.zip_version(_zip(tmp_path / "a.zip")) == "2.3.0"
    assert su.zip_version(_zip(tmp_path / "b.zip", prefix="")) == "2.3.0"


def test_zip_version_refuses_other_zips(tmp_path):
    with pytest.raises(ValueError):
        su.zip_version(_zip(tmp_path / "c.zip", files=("update.ps1",)))  # no checksums.txt
    with pytest.raises(ValueError):
        su.zip_version(_zip(tmp_path / "d.zip", version="latest"))
    (tmp_path / "e.zip").write_text("not a zip")
    with pytest.raises(ValueError):
        su.zip_version(tmp_path / "e.zip")


def test_parse_run_at():
    assert su.parse_run_at("2026-11-10T22:00") == datetime(2026, 11, 10, 22, 0)
    assert su.parse_run_at("now") <= datetime.now()
    with pytest.raises(ValueError):
        su.parse_run_at("tonight")


def test_version_compare():
    assert su.parse_version("2.10.0") > su.parse_version("2.9.9")
    assert su.parse_version("2.3") == (2, 3, 0)


def test_status_reads_files(tmp_path):
    api = tmp_path / "api"
    api.mkdir()
    (api / "server_version.txt").write_text("2.3.0\n")
    base = tmp_path / "upd"
    base.mkdir()
    (base / "pending.json").write_text(json.dumps({"version": "2.4.0"}))
    s = su.build_status(base, api)
    assert s["server_version"] == "2.3.0" and s["pending"]["version"] == "2.4.0"
    assert s["last"] is None and s["updater_running"] is False
    (base / "heartbeat.txt").write_text("now")
    assert su.build_status(base, api)["updater_running"] is True


def test_require_admin(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(su, "_authenticate_user", lambda c, u, p: None)
    with pytest.raises(HTTPException) as e:
        su._require_admin(None, "a", "b")
    assert e.value.status_code == 401
    monkeypatch.setattr(su, "_authenticate_user", lambda c, u, p: {"personnel_role": "user"})
    with pytest.raises(HTTPException) as e:
        su._require_admin(None, "a", "b")
    assert e.value.status_code == 403
    monkeypatch.setattr(su, "_authenticate_user", lambda c, u, p: {"personnel_role": "admin"})
    assert su._require_admin(None, "a", "b")


def test_client_staged_update(tmp_path, monkeypatch):
    import services.updater as upd
    monkeypatch.setattr(upd, "_staged_file", lambda: str(tmp_path / "staged.json"))
    z = tmp_path / "patch_v9.0.0.zip"
    z.write_bytes(b"patch")
    assert upd.stage_update({"latest_version": "9.0.0"}, str(z))
    assert upd.staged_update(current="2.2.1")["version"] == "9.0.0"
    # changed file -> forgotten
    z.write_bytes(b"other")
    assert upd.staged_update(current="2.2.1") is None
    assert not (tmp_path / "staged.json").exists()
    # not newer -> forgotten
    z.write_bytes(b"patch")
    upd.stage_update({"latest_version": "2.2.1"}, str(z))
    assert upd.staged_update(current="2.2.1") is None


def test_describe_lines():
    import services.server_update as cs
    d = cs.describe({"server_version": "", "pending": {"version": "2.4.0", "run_at": "2026-11-10T22:00", "uploaded_by": "م"},
                     "last": {"version": "2.3.0", "state": "failed", "finished_at": "2026-11-09T22:01:00"},
                     "updater_running": False})
    assert "2.4.0" in d["pending"] and "22:00" in d["pending"]
    assert "فشل" in d["last"] and d["warning"]
    assert cs.describe(None)["pending"] == ""
