import os

import services.template_sync as ts


def _setup(tmp_path, monkeypatch, server_sha):
    monkeypatch.setattr(ts, "is_online", lambda: True)
    monkeypatch.setattr(ts, "get_local_templates_dir", lambda: str(tmp_path))
    monkeypatch.setattr(ts, "get_api_url", lambda: "http://x")
    monkeypatch.setattr(ts, "fetch_server_manifest", lambda: {
        "config_sha256": "", "templates": [{"filename": "a.docx", "sha256": server_sha}]})
    calls = []
    monkeypatch.setattr(ts, "_download_and_atomic_swap", lambda f, *a: calls.append(f) or True)
    monkeypatch.setattr(ts, "remove_templates_deleted_on_server", lambda *a: [])
    return calls


def test_local_edit_is_kept(tmp_path, monkeypatch):
    (tmp_path / "a.docx").write_bytes(b"edited")
    ts.record_server_hash("a.docx", "serversha", str(tmp_path))
    calls = _setup(tmp_path, monkeypatch, "serversha")
    res = ts.sync_templates_if_online()
    assert calls == [] and res["local_edits"] == ["a.docx"]
    assert ts.is_locally_modified("a.docx", str(tmp_path))


def test_conflict_is_kept_and_reported(tmp_path, monkeypatch):
    (tmp_path / "a.docx").write_bytes(b"edited")
    ts.record_server_hash("a.docx", "old", str(tmp_path))
    calls = _setup(tmp_path, monkeypatch, "new")
    assert calls == [] and ts.sync_templates_if_online()["conflicts"] == ["a.docx"]


def test_unedited_file_is_updated(tmp_path, monkeypatch):
    (tmp_path / "a.docx").write_bytes(b"same")
    ts.record_server_hash("a.docx", ts.calculate_file_sha256(str(tmp_path / "a.docx")), str(tmp_path))
    calls = _setup(tmp_path, monkeypatch, "new")
    ts.sync_templates_if_online()
    assert calls == ["a.docx"]
