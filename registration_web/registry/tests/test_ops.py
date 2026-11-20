"""Day-2 operations: nightly backup and the trial-user command."""
import datetime
import json
import sqlite3

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command

from registry import backup


def _make_db(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    con.executemany("INSERT INTO t (name) VALUES (?)", [("a",), ("b",), ("c",)])
    con.commit()
    return con  # left open on purpose: backup must work while the app is running


def test_backup_produces_readable_db_copy_and_media(tmp_path):
    data = tmp_path / "data"
    (data / "media" / "docs").mkdir(parents=True)
    (data / "media" / "docs" / "scan.pdf").write_bytes(b"%PDF-1.4 test")
    live = _make_db(data / "registration.sqlite3")

    dest = backup.run_backup(data, tmp_path / "backups", today=datetime.date(2026, 11, 21))
    live.close()

    assert dest.name == "2026-11-21"
    copy = sqlite3.connect(dest / "registration.sqlite3")
    assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert copy.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 3
    copy.close()
    assert (dest / "media" / "docs" / "scan.pdf").read_bytes() == b"%PDF-1.4 test"


def test_backup_keeps_only_last_30_days(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    _make_db(data / "registration.sqlite3").close()
    root = tmp_path / "backups"
    for name in ("2026-10-01", "2026-10-22", "2026-10-23", "not-a-date"):
        (root / name).mkdir(parents=True)

    backup.run_backup(data, root, today=datetime.date(2026, 11, 21), keep_days=30)

    names = sorted(p.name for p in root.iterdir())
    assert names == ["2026-10-22", "2026-10-23", "2026-11-21", "not-a-date"]


@pytest.mark.django_db
def test_create_trial_users_is_idempotent(tmp_path):
    spec = tmp_path / "trial_users.json"
    spec.write_text(json.dumps([
        {"username": "sa1", "full_name": "موظف شؤون", "unit": "student_affairs"},
        {"username": "fin1", "full_name": "موظف مالية", "unit": "finance"},
    ], ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "passwords.txt"

    call_command("create_trial_users", str(spec), passwords_file=str(out))
    first_hash = User.objects.get(username="sa1").password
    call_command("create_trial_users", str(spec), passwords_file=str(out))

    assert User.objects.filter(username__in=["sa1", "fin1"]).count() == 2
    sa1 = User.objects.get(username="sa1")
    assert sa1.is_staff and sa1.first_name == "موظف شؤون"
    assert sa1.password == first_hash  # second run does not reset the password
    assert list(sa1.groups.values_list("name", flat=True)) == ["student_affairs"]
    assert Group.objects.get(name="finance").user_set.filter(username="fin1").exists()
    assert out.read_text(encoding="utf-8").count("sa1") == 1  # password written once


@pytest.mark.django_db
def test_create_trial_users_rejects_unknown_unit(tmp_path):
    spec = tmp_path / "u.json"
    spec.write_text(json.dumps([{"username": "x", "unit": "nope"}]), encoding="utf-8")
    with pytest.raises(Exception):
        call_command("create_trial_users", str(spec), passwords_file=str(tmp_path / "p.txt"))
    assert not User.objects.filter(username="x").exists()


def test_nightly_bat_sweeps_parts_after_backup():
    from pathlib import Path
    bat = (Path(__file__).resolve().parents[2] / "regweb_backup.bat").read_text(encoding="utf-8")
    lines = [l for l in bat.splitlines() if "manage.py" in l]
    assert "backup_regweb" in lines[0]
    assert "sweep_parts" in lines[1] and "backup.log" in lines[1]
