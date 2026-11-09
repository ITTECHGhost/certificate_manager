import json

from services.template_sync import remove_templates_deleted_on_server


def _make(d, *names):
    for n in names:
        (d / n).write_bytes(b"x")


def test_removes_only_unregistered_files_missing_on_server(tmp_path):
    _make(tmp_path, "gone.docx", "local_new.docx", "kept.docx")
    (tmp_path / "templates_config.json").write_text(json.dumps({
        "local_new": {"file": "local_new.docx"}, "kept": {"file": "kept.docx"}}), encoding="utf-8")
    removed = remove_templates_deleted_on_server(["kept.docx"], str(tmp_path))
    assert removed == ["gone.docx"]
    assert (tmp_path / "local_new.docx").exists()
    assert not (tmp_path / "gone.docx").exists()
    assert len(list((tmp_path / ".deleted").iterdir())) == 1


def test_unreadable_or_empty_config_removes_nothing(tmp_path):
    _make(tmp_path, "a.docx")
    assert remove_templates_deleted_on_server([], str(tmp_path)) == []
    (tmp_path / "templates_config.json").write_text("{}", encoding="utf-8")
    assert remove_templates_deleted_on_server([], str(tmp_path)) == []
    assert (tmp_path / "a.docx").exists()


def test_api_delete_moves_file_to_trash(tmp_path, monkeypatch):
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "certificate_manager_api"))
    from routers import templates as r
    monkeypatch.setattr(r, "SERVER_TEMPLATES_DIR", tmp_path)
    _make(tmp_path, "x.docx")
    assert r.delete_template("x.docx")["status"] == "success"
    assert not (tmp_path / "x.docx").exists()
    assert len(list((tmp_path / ".deleted").iterdir())) == 1
    assert r.delete_template("x.docx").get("already_absent")
