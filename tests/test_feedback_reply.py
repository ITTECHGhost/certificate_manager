"""Feedback replies (0011): admin replies + status; the author edits while new; server checks."""
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "certificate_manager_api"))

from routers.feedback import (  # noqa: E402
    EditPayload, ReplyPayload, delete_feedback, edit_feedback, list_feedback, reply_feedback)

ADMIN = {"id": 1, "personnel_role": "admin", "is_active": 1}
USER = {"id": 7, "personnel_role": "user", "is_active": 1}
OTHER = {"id": 8, "personnel_role": "user", "is_active": 1}


class _Cur:
    rowcount = 1

    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None):
        self.conn.sql.append((sql, params))
        if self.conn.fail and sql.lstrip().startswith("UPDATE"):
            raise RuntimeError("boom")

    def fetchone(self):
        return self.conn.one.pop(0) if self.conn.one else None

    def fetchall(self):
        return self.conn.rows

    def close(self):
        pass


class _Conn:
    def __init__(self, one=(), rows=(), fail=False):
        self.one, self.rows, self.fail = list(one), list(rows), fail
        self.sql, self.commits, self.rollbacks = [], 0, 0

    def cursor(self, **k):
        return _Cur(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _writes(conn):
    return [s for s, _ in conn.sql if s.lstrip().startswith(("UPDATE", "INSERT", "DELETE"))]


# --- reply ---------------------------------------------------------------
def test_admin_reply_sets_status_one_commit():
    conn = _Conn(one=[ADMIN])
    reply_feedback(3, ReplyPayload(personnel_id=1, reply=" تم الحل ", status="done"), conn)
    (sql,) = _writes(conn)
    assert "reply" in sql and "status" in sql and "replied_by" in sql
    params = conn.sql[-1][1]
    assert "تم الحل" in params and "done" in params and 1 in params
    assert conn.commits == 1


def test_non_admin_cannot_reply():
    conn = _Conn(one=[USER])
    with pytest.raises(HTTPException) as e:
        reply_feedback(3, ReplyPayload(personnel_id=7, reply="x", status="done"), conn)
    assert e.value.status_code == 403 and not _writes(conn)


def test_reply_bad_status_refused():
    conn = _Conn(one=[ADMIN])
    with pytest.raises(HTTPException) as e:
        reply_feedback(3, ReplyPayload(personnel_id=1, reply="x", status="weird"), conn)
    assert e.value.status_code == 422 and not _writes(conn)


def test_reply_rolls_back_on_error():
    conn = _Conn(one=[ADMIN], fail=True)
    with pytest.raises(HTTPException):
        reply_feedback(3, ReplyPayload(personnel_id=1, reply="x", status="done"), conn)
    assert conn.rollbacks == 1 and conn.commits == 0


# --- edit by the author ---------------------------------------------------
def test_author_edits_while_new():
    conn = _Conn(one=[USER, {"created_by": 7, "status": "new"}])
    edit_feedback(3, EditPayload(personnel_id=7, message=" نص جديد "), conn)
    (sql,) = _writes(conn)
    assert sql.startswith("UPDATE feedback SET message") and "edited_at" in sql
    assert conn.sql[-1][1][0] == "نص جديد" and conn.commits == 1


def test_other_user_cannot_edit():
    conn = _Conn(one=[OTHER, {"created_by": 7, "status": "new"}])
    with pytest.raises(HTTPException) as e:
        edit_feedback(3, EditPayload(personnel_id=8, message="x"), conn)
    assert e.value.status_code == 403 and not _writes(conn)


def test_no_edit_after_admin_started():
    conn = _Conn(one=[USER, {"created_by": 7, "status": "in_progress"}])
    with pytest.raises(HTTPException) as e:
        edit_feedback(3, EditPayload(personnel_id=7, message="x"), conn)
    assert e.value.status_code == 409 and not _writes(conn)


def test_edit_empty_refused():
    conn = _Conn(one=[USER, {"created_by": 7, "status": "new"}])
    with pytest.raises(HTTPException) as e:
        edit_feedback(3, EditPayload(personnel_id=7, message="   "), conn)
    assert e.value.status_code == 422


# --- delete (soft) --------------------------------------------------------
def test_author_soft_deletes_own_new_note():
    conn = _Conn(one=[USER, {"created_by": 7, "status": "new"}])
    delete_feedback(3, conn, personnel_id=7)
    (sql,) = _writes(conn)
    assert sql.startswith("UPDATE feedback SET deleted_at") and conn.commits == 1


def test_admin_soft_deletes_any_note():
    conn = _Conn(one=[ADMIN, {"created_by": 7, "status": "done"}])
    delete_feedback(3, conn, personnel_id=1)
    assert _writes(conn) and conn.commits == 1


def test_other_user_cannot_delete():
    conn = _Conn(one=[OTHER, {"created_by": 7, "status": "new"}])
    with pytest.raises(HTTPException) as e:
        delete_feedback(3, conn, personnel_id=8)
    assert e.value.status_code == 403 and not _writes(conn)


def test_delete_without_user_refused():
    with pytest.raises(HTTPException) as e:
        delete_feedback(3, _Conn(), personnel_id=None)
    assert e.value.status_code == 403


# --- list -----------------------------------------------------------------
def test_admin_lists_all_user_lists_own():
    conn = _Conn(one=[ADMIN], rows=[{"id": 1}])
    assert list_feedback(conn, personnel_id=1) == [{"id": 1}]
    assert "created_by = %s" not in conn.sql[-1][0]
    conn = _Conn(one=[USER], rows=[])
    list_feedback(conn, personnel_id=7)
    assert "created_by = %s" in conn.sql[-1][0] and conn.sql[-1][1] == (7,)
    assert "deleted_at IS NULL" in conn.sql[-1][0] and "reply" in conn.sql[-1][0]


def test_list_without_user_refused():
    with pytest.raises(HTTPException) as e:
        list_feedback(_Conn(), personnel_id=None)
    assert e.value.status_code == 403


def test_migration_0011_and_rollback_exist():
    mig = (ROOT / "sql" / "migrations" / "0011_feedback_reply.sql").read_text(encoding="utf-8")
    rb = (ROOT / "sql" / "fixes" / "rollback_0011_feedback_reply.sql").read_text(encoding="utf-8")
    for col in ("status", "reply", "replied_by", "replied_at", "edited_at"):
        assert col in mig and col in rb
