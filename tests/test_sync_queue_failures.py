"""Every queue row the sync counts as failed shows in the failed list, or stays pending with a reason.

Before: a row the server did not confirm (e.g. a DELETE, whose id the server never
returned) was counted as failed but left 'pending', so the screen said "5 failed"
while the failed-records list was empty, and the row was resent forever.
"""
import json

import pytest

import sync_engine


class _Resp:
    def __init__(self, status_code, data=None, text=""):
        self.status_code = status_code
        self._data = data or {}
        self.text = text or json.dumps(self._data)

    def json(self):
        return self._data


@pytest.fixture
def queue(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_engine, "_LOCAL_DB_PATH", tmp_path / "local_cache.db")
    sync_engine.init_local_db()

    def add(table, operation, temp_id, payload=None):
        conn = sync_engine._get_local_conn()
        cur = conn.execute(
            "INSERT INTO sync_queue (table_name, operation, temp_id, payload) VALUES (?, ?, ?, ?)",
            (table, operation, temp_id, json.dumps(payload or {})),
        )
        conn.commit()
        conn.close()
        return cur.lastrowid

    return add


def _rows():
    conn = sync_engine._get_local_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT id, COALESCE(status, 'pending') AS status, last_error FROM sync_queue ORDER BY id")]
    conn.close()
    return rows


def _server(monkeypatch, response):
    monkeypatch.setattr(sync_engine.api_client, "post", lambda *a, **k: response)


def test_unconfirmed_row_is_marked_failed_with_reason(queue, monkeypatch):
    queue("students", "DELETE", 12, {"id": 12})
    _server(monkeypatch, _Resp(200, {"id_map": {}, "failed": []}))
    result = sync_engine.sync_offline_queue_to_mysql()
    assert result["failed"] == 1
    [row] = _rows()
    assert row["status"] == "failed" and row["last_error"]
    assert sync_engine.get_queue_status()["failed"] == 1


def test_refused_request_keeps_rows_pending_and_reports_why(queue, monkeypatch):
    queue("students", "DELETE", 12, {"id": 12})
    queue("students", "DELETE", 13, {"id": 13})
    _server(monkeypatch, _Resp(403, text="Missing application key"))
    result = sync_engine.sync_offline_queue_to_mysql()
    assert result["failed"] == 0 and result["pending"] == 2
    assert "403" in result["error"] and "application key" in result["error"]
    assert [r["status"] for r in _rows()] == ["pending", "pending"]
    message, kind = sync_engine.sync_result_message(result)
    assert kind == "negative" and "403" in message


def test_connection_error_keeps_rows_pending(queue, monkeypatch):
    queue("students", "DELETE", 12, {"id": 12})

    def boom(*a, **k):
        raise sync_engine.requests.ConnectionError("no route to host")

    monkeypatch.setattr(sync_engine.api_client, "post", boom)
    result = sync_engine.sync_offline_queue_to_mysql()
    assert result["error"] and result["pending"] == 1
    assert [r["status"] for r in _rows()] == ["pending"]


def test_confirmed_delete_leaves_the_queue(queue, monkeypatch):
    queue("students", "DELETE", 12, {"id": 12})
    _server(monkeypatch, _Resp(200, {"id_map": {"12": 12}, "failed": []}))
    result = sync_engine.sync_offline_queue_to_mysql()
    assert result == {"synced": 1, "failed": 0, "id_map": {12: 12}}
    assert _rows() == []
    assert sync_engine.sync_result_message(result) is None


def test_refused_settings_row_is_marked_failed(queue, monkeypatch):
    queue("settings", "UPDATE", 1, {"theme": "Dark"})
    monkeypatch.setattr(sync_engine.api_client, "put", lambda *a, **k: _Resp(404, text="no user"))
    result = sync_engine.sync_offline_queue_to_mysql()
    assert result["failed"] == 1
    [row] = _rows()
    assert row["status"] == "failed" and "404" in row["last_error"]
