"""Suggestions for the «إلى» field come from earlier issued certificates (local replica, read-only)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data.query as q  # noqa: E402


def test_most_used_first(monkeypatch):
    seen = {}

    def fake(sql, params=()):
        seen["sql"], seen["params"] = sql, params
        return [{"t": "وزارة التربية", "n": 5}, {"t": "من يهمه الأمر", "n": 3}, {"t": None, "n": 1}]
    monkeypatch.setattr(q, "sqlite_read_all", fake)
    assert q.get_past_to_titles() == ["وزارة التربية", "من يهمه الأمر"]
    assert "local_issued_certificates" in seen["sql"] and "ORDER BY n DESC" in seen["sql"]
    assert "INSERT" not in seen["sql"].upper() and "UPDATE" not in seen["sql"].upper()


def test_error_gives_empty_list(monkeypatch):
    monkeypatch.setattr(q, "sqlite_read_all", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no db")))
    assert q.get_past_to_titles() == []
