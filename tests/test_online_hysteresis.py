"""A dropping link must not flip the app online/offline on every check (2026-11-26, user laptop
with mostly-failed pings): 2 failed checks in a row to go offline, 2 good ones to come back.
Reconnects never start a second replica pull while one runs, nor more than one a minute."""
import threading

import pytest

import sync_engine as se


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    monkeypatch.setattr(se, "_is_online", True)
    monkeypatch.setattr(se, "_streak", {"ok": 0, "fail": 0})
    monkeypatch.setattr(se, "_last_pull_start", 0.0)
    se._pull_lock = threading.Lock()


def test_one_failed_check_keeps_online():
    assert se.record_check(False) is True


def test_two_failed_checks_go_offline():
    se.record_check(False)
    assert se.record_check(False) is False


def test_good_check_resets_the_fail_count():
    se.record_check(False)
    se.record_check(True)
    assert se.record_check(False) is True


def test_two_good_checks_needed_to_come_back():
    se.record_check(False)
    se.record_check(False)
    assert se.record_check(True) is False
    assert se.record_check(True) is True


def test_reconnect_pull_runs_once_per_minute(monkeypatch):
    started = []
    monkeypatch.setattr(se, "pull_mysql_to_sqlite", lambda: started.append(1))
    assert se.pull_mysql_to_sqlite_background() is True
    assert se.pull_mysql_to_sqlite_background() is False      # within a minute
    monkeypatch.setattr(se, "_last_pull_start", 0.0)
    assert se.pull_mysql_to_sqlite_background() is True


def test_no_second_pull_while_one_runs(monkeypatch):
    se._pull_lock.acquire()
    try:
        assert se.pull_mysql_to_sqlite_background() is False
    finally:
        se._pull_lock.release()


def test_ping_does_not_retry(monkeypatch):
    seen = {}

    class _R:
        status_code = 200

    def fake_get(url, timeout=None, **k):
        seen.update(k, timeout=timeout)
        return _R()
    monkeypatch.setattr(se.api_client, "get", fake_get)
    monkeypatch.setattr(se, "_ensure_ca_cert", lambda: None)
    assert se.check_network_status() is True
    assert seen.get("retry") is False and seen["timeout"] <= 2.0


def test_queue_counts_for_the_header_badge(monkeypatch, tmp_path):
    import sqlite3
    db = tmp_path / "q.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE sync_queue (id INTEGER PRIMARY KEY, status TEXT)")
    c.executemany("INSERT INTO sync_queue (status) VALUES (?)", [(None,), ("pending",), ("failed",)])
    c.commit(); c.close()
    monkeypatch.setattr(se, "_get_local_conn", lambda: sqlite3.connect(db))
    assert se.get_queue_counts() == {"pending": 2, "failed": 1}
