"""Release manifest + changes-only zip (scripts/release_manifest.py)."""
import json
import zipfile

from scripts import release_manifest as rm


def _tree(root, files):
    for rel, data in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def test_manifest_lists_sha_and_skips_server_config(tmp_path):
    _tree(tmp_path, {"a.exe": b"1", "_internal/x.dll": b"2", "server_config.json": b"secret"})
    m = rm.build_manifest(tmp_path)
    assert set(m) == {"a.exe", "_internal/x.dll"}
    assert len(m["a.exe"]) == 64


def test_changed_files_new_and_modified_only():
    old = {"a": "1", "b": "2", "gone": "3"}
    new = {"a": "1", "b": "9", "c": "4"}
    assert rm.changed_files(old, new) == ["b", "c"]


def test_changes_zip_holds_only_changed(tmp_path):
    app = tmp_path / "app"
    _tree(app, {"a.exe": b"1", "lib/b.dll": b"new", "lib/c.dll": b"same"})
    old = {"a.exe": rm.sha256_file(app / "a.exe"), "lib/b.dll": "0" * 64, "lib/c.dll": rm.sha256_file(app / "lib/c.dll")}
    z = tmp_path / "c.zip"
    n = rm.write_changes_zip(app, old, z)
    assert n == 1
    assert zipfile.ZipFile(z).namelist() == ["lib/b.dll"]


def test_cli_writes_manifest_and_changes(tmp_path):
    app = tmp_path / "app"
    _tree(app, {"a.exe": b"1"})
    old = tmp_path / "manifest_v1.json"
    old.write_text(json.dumps({"version": "1", "files": {"a.exe": "0" * 64}}))
    out = tmp_path / "out"
    out.mkdir()
    assert rm.main([str(app), "2", str(out), "--changes", str(old)]) == 0
    assert json.loads((out / "manifest_v2.json").read_text())["files"].keys() == {"a.exe"}
    assert (out / "patch_v2_from_1.zip").is_file()
