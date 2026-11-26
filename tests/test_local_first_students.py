"""Student search reads the local copy while it is fresh (2026-11-26, slow user link)."""
import sync_engine as se
from data.repositories import students as mod


def _setup(monkeypatch, online=True, fresh=True):
    monkeypatch.setattr(se, "_is_online", online)
    monkeypatch.setattr(se, "_fresh_at", {})
    if fresh:
        se._mark_fresh("students")
    calls = {"api": 0, "local": 0}

    def api(*a, **k):
        calls["api"] += 1
        raise AssertionError("server must not be asked")
    monkeypatch.setattr(mod.api_client, "get", api)
    monkeypatch.setattr(mod, "search_offline_students",
                        lambda q, limit=8: calls.__setitem__("local", calls["local"] + 1) or [])
    return calls


def test_fresh_copy_is_read_locally(monkeypatch):
    calls = _setup(monkeypatch)
    mod.StudentRepository().search("علي")
    assert calls == {"api": 0, "local": 1}


def test_offline_reads_locally(monkeypatch):
    calls = _setup(monkeypatch, online=False, fresh=False)
    mod.StudentRepository().search("علي")
    assert calls["local"] == 1


def test_stale_copy_asks_the_server(monkeypatch):
    _setup(monkeypatch, fresh=False)
    assert se.read_local_first("students") is False


def test_copy_goes_stale_after_the_limit(monkeypatch):
    _setup(monkeypatch)
    monkeypatch.setitem(se._fresh_at, "students", se._fresh_at["students"] - se.REPLICA_FRESH_SECONDS - 1)
    assert se.read_local_first("students") is False


def test_write_online_makes_reads_go_to_the_server(monkeypatch):
    _setup(monkeypatch)
    refreshed = []
    monkeypatch.setattr(se, "refresh_replica_tables_background", lambda t: refreshed.append(t))
    se.mark_stale_and_refresh(["students"])
    assert se.read_local_first("students") is False and refreshed == [["students"]]
