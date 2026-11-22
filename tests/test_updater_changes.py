"""Updater picks the changes-only zip when it fits the installed version, else the full zip."""
import services.updater as updater


class _Resp:
    def __init__(self, data, status=200):
        self.status_code, self._d, self.headers = status, data, {}

    def json(self):
        return self._d

    def iter_content(self, chunk_size=0):
        yield self._d


def _server(monkeypatch, **extra):
    data = {"latest_version": "9.9.9", "patch_filename": "patch_v9.9.9.zip",
            "download_url": "/api/update/download/patch_v9.9.9.zip", "sha256": "f", **extra}
    monkeypatch.setattr(updater, "is_online", lambda: True)
    monkeypatch.setattr(updater.api_client, "get", lambda *a, **k: _Resp(data))


CH = {"changes_filename": "patch_v9.9.9_from_X.zip", "changes_download_url": "/api/update/download/patch_v9.9.9_from_X.zip",
      "changes_sha256": "c", "changes_size_bytes": 5}


def test_changes_offered_when_installed_version_matches(monkeypatch):
    _server(monkeypatch, changes_from=updater.CURRENT_APP_VERSION, **CH)
    info = updater.check_for_updates()
    assert info["changes"]["patch_filename"] == CH["changes_filename"]
    assert info["patch_filename"] == "patch_v9.9.9.zip"


def test_no_changes_when_version_differs_or_fields_missing(monkeypatch):
    _server(monkeypatch, changes_from="0.0.1", **CH)
    assert not updater.check_for_updates().get("changes")
    _server(monkeypatch, changes_from=updater.CURRENT_APP_VERSION)
    assert not updater.check_for_updates().get("changes")


def _info():
    return {"latest_version": "9.9.9", "patch_filename": "full.zip", "download_url": "/full", "sha256": "",
            "changes": {"patch_filename": "small.zip", "download_url": "/small", "sha256": ""}}


def test_download_prefers_small_zip(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "is_online", lambda: True)
    monkeypatch.setattr(updater.app_paths, "data_path", lambda n: tmp_path)
    got = []
    monkeypatch.setattr(updater.api_client, "get", lambda url, **k: got.append(url) or _Resp(b"z"))
    path = updater.download_patch(_info())
    assert path.endswith("small.zip") and len(got) == 1 and got[0].endswith("/small")


def test_download_falls_back_to_full_on_any_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "is_online", lambda: True)
    monkeypatch.setattr(updater.app_paths, "data_path", lambda n: tmp_path)
    monkeypatch.setattr(updater.api_client, "get", lambda url, **k: _Resp(b"z", 404 if url.endswith("/small") else 200))
    assert updater.download_patch(_info()).endswith("full.zip")
    info = _info()
    info["changes"]["sha256"] = "bad"
    monkeypatch.setattr(updater.api_client, "get", lambda url, **k: _Resp(b"z"))
    assert updater.download_patch(info).endswith("full.zip")
