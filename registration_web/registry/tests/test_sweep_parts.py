"""Orphan .part sweep: upload temps left by a rolled-back request are deleted by age."""
import os
import time
from io import StringIO

from django.core.management import call_command

from registry import uploads


def _make(path, age_hours):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    t = time.time() - age_hours * 3600
    os.utime(path, (t, t))
    return path


def _tree(root):
    d = root / "student_docs" / "2026" / "11"
    return {
        "old": _make(d / "a.png.part", 30),
        "fresh": _make(d / "b.png.part", 1),
        "old_real": _make(d / "c.png", 30),
        "partial": _make(root / "backups" / "x.partial" / "y.part", 30),
    }


def test_sweep_deletes_only_old_parts(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    f = _tree(tmp_path)
    found, deleted = uploads.sweep_orphan_parts(max_age_hours=24)
    assert (found, deleted) == (1, 1)
    assert not f["old"].exists()
    assert f["fresh"].exists() and f["old_real"].exists() and f["partial"].exists()


def test_sweep_dry_run_and_hours(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    f = _tree(tmp_path)
    assert uploads.sweep_orphan_parts(max_age_hours=0, dry_run=True) == (2, 0)
    assert f["old"].exists() and f["fresh"].exists()
    assert uploads.sweep_orphan_parts(max_age_hours=0) == (2, 2)


def test_sweep_missing_folder_is_ok(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "none"
    assert uploads.sweep_orphan_parts() == (0, 0)


def test_sweep_command(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    f = _tree(tmp_path)
    out = StringIO()
    call_command("sweep_parts", "--hours", "24", stdout=out)
    assert "1" in out.getvalue() and not f["old"].exists()
