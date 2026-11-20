import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "certificate_manager_api"))

from routers.feedback import FeedbackPayload, save_feedback, list_feedback, delete_feedback  # noqa: E402
from data.repositories.base import OfflineModeError  # noqa: E402


class _Cur:
    lastrowid = 5
    rowcount = 1

    def __init__(self, fail=False, rows=None):
        self.fail, self.rows, self.sql = fail, rows or [], []

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        if self.fail:
            raise RuntimeError("boom")

    def fetchall(self): return self.rows
    def close(self): pass


class _Conn:
    def __init__(self, **k):
        self.cur, self.commits, self.rollbacks = _Cur(**k), 0, 0

    def cursor(self, **k): return self.cur
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


def test_save_is_one_insert_one_commit():
    conn = _Conn()
    out = save_feedback(FeedbackPayload(message="  لا أستطيع الكتابة بالعربي  ", screen="الطلاب",
                                        app_version="2.5.9", created_by=3), conn)
    assert out == {"id": 5}
    assert conn.commits == 1 and conn.rollbacks == 0
    sql, params = conn.cur.sql[0]
    assert sql.startswith("INSERT INTO feedback")
    assert params[0] == "لا أستطيع الكتابة بالعربي"


def test_empty_message_rejected_without_touching_db():
    from fastapi import HTTPException
    conn = _Conn()
    with pytest.raises(HTTPException) as e:
        save_feedback(FeedbackPayload(message="   "), conn)
    assert e.value.status_code == 422 and not conn.cur.sql


def test_save_rolls_back_on_error():
    from fastapi import HTTPException
    conn = _Conn(fail=True)
    with pytest.raises(HTTPException) as e:
        save_feedback(FeedbackPayload(message="x"), conn)
    assert e.value.status_code == 500 and conn.rollbacks == 1 and conn.commits == 0


def test_message_is_capped():
    conn = _Conn()
    save_feedback(FeedbackPayload(message="ا" * 9000), conn)
    assert len(conn.cur.sql[0][1][0]) == 4000


def test_list_skips_deleted_and_delete_is_soft():
    conn = _Conn(rows=[{"id": 1}])
    assert list_feedback(conn) == [{"id": 1}]
    assert "deleted_at IS NULL" in conn.cur.sql[0][0]
    conn2 = _Conn()
    delete_feedback(1, conn2, deleted_by=2)
    sql = conn2.cur.sql[0][0]
    assert sql.startswith("UPDATE feedback SET deleted_at") and "DELETE" not in sql
    assert conn2.commits == 1


def test_repository_send_offline_raises(monkeypatch):
    import data.repositories.feedback as fb
    monkeypatch.setattr(fb, "is_online", lambda: False)
    with pytest.raises(OfflineModeError):
        fb.FeedbackRepository().send("نص", "الطلاب", 1)
    assert fb.FeedbackRepository().list_all() == []


def test_repository_send_payload(monkeypatch):
    import data.repositories.feedback as fb
    seen = {}

    class R:
        status_code = 200
        def json(self): return {"id": 9}

    monkeypatch.setattr(fb, "is_online", lambda: True)
    monkeypatch.setattr(fb.api_client, "post", lambda url, json=None, timeout=None: seen.update(url=url, json=json) or R())
    assert fb.FeedbackRepository().send("نص", "الطلاب", 4) == 9
    assert seen["json"]["screen"] == "الطلاب" and seen["json"]["created_by"] == 4
    from app_version import APP_VERSION
    assert seen["json"]["app_version"] == APP_VERSION


def test_migration_files_exist_and_match():
    mig = (ROOT / "sql/migrations/0009_feedback.sql").read_text(encoding="utf-8")
    rb = (ROOT / "sql/fixes/rollback_0009_feedback.sql").read_text(encoding="utf-8")
    assert "utf8mb4" in mig and "deleted_at" in mig and "created_by" in mig and "created_at" in mig
    assert "DROP TABLE IF EXISTS `feedback`" in rb and "0009_feedback.sql" in rb
