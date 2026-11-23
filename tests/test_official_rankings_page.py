"""Official rankings page: server-side user check, search + paging, soft delete (fake data only)."""
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "certificate_manager_api"))

from routers import official_rankings as R  # noqa: E402


class FakeCur:
    def __init__(self, conn):
        self.c = conn
        self.rowcount = 1
        self.lastrowid = 11
        self._rows = []

    def execute(self, sql, params=()):
        self.c.log.append((" ".join(sql.split()), params))
        s = sql.upper()
        if "FROM PERSONNEL_PERMISSIONS" in s:
            self._rows = [{"permission_key": k} for k in self.c.perms]
        elif "FROM PERSONNEL" in s:
            self._rows = [self.c.user] if self.c.user else []
        elif "INFORMATION_SCHEMA" in s:
            self._rows = [{"n": 1 if self.c.has_soft else 0}]
        elif "COUNT(*) AS N" in s and "OFFICIAL_RANKINGS" in s:
            self._rows = [{"n": self.c.total}]
        elif "FROM OFFICIAL_RANKINGS" in s:
            self._rows = self.c.rows
        else:
            self._rows = []

    def executemany(self, sql, rows):
        self.c.log.append((" ".join(sql.split()), list(rows)))

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class FakeConn:
    def __init__(self, user=None, perms=(), has_soft=True, rows=(), total=0):
        self.user, self.perms, self.has_soft = user, list(perms), has_soft
        self.rows, self.total = list(rows), total
        self.log, self.commits, self.rollbacks = [], 0, 0

    def cursor(self, **k):
        return FakeCur(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def sql(self):
        return [s for s, _ in self.log]


ADMIN = {"id": 1, "personnel_role": "admin", "is_active": 1}
CLERK = {"id": 2, "personnel_role": "user", "is_active": 1}
OFF = {"id": 3, "personnel_role": "admin", "is_active": 0}


def _payload(**kw):
    base = dict(list_type="jobs", department_id=5, created_by=1, study_type="morning", exam_round="1",
                entries=[{"position": 1, "name_written": "اسم تجريبي", "average": 80.5}])
    base.update(kw)
    return R.RankingPayload(**base)


# ── user check ───────────────────────────────────────────────────────────────
def test_write_without_user_is_refused_and_nothing_written():
    conn = FakeConn(user=None)
    with pytest.raises(HTTPException) as e:
        R.save_ranking(_payload(created_by=None), conn)
    assert e.value.status_code == 403 and conn.commits == 0
    assert not any("INSERT" in s for s in conn.sql())


def test_inactive_or_unknown_user_refused():
    for u in (OFF, None):
        with pytest.raises(HTTPException) as e:
            R.save_ranking(_payload(), FakeConn(user=u))
        assert e.value.status_code == 403


def test_plain_user_needs_page_permission():
    with pytest.raises(HTTPException) as e:
        R.save_ranking(_payload(created_by=2), FakeConn(user=CLERK, perms=[]))
    assert e.value.status_code == 403
    ok = FakeConn(user=CLERK, perms=["page:rankings"])
    assert R.save_ranking(_payload(created_by=2), ok)["saved"] == 1
    assert ok.commits == 1


def test_admin_saves_in_one_commit():
    conn = FakeConn(user=ADMIN)
    out = R.save_ranking(_payload(), conn)
    assert out == {"id": 11, "saved": 1} and conn.commits == 1 and conn.rollbacks == 0


def test_set_student_and_delete_check_user():
    for call in (lambda c: R.set_entry_student(1, 1, 9, None, c), lambda c: R.delete_ranking(1, None, c)):
        conn = FakeConn(user=None)
        with pytest.raises(HTTPException) as e:
            call(conn)
        assert e.value.status_code == 403 and conn.commits == 0


# ── soft delete ──────────────────────────────────────────────────────────────
def test_delete_is_soft_when_column_exists():
    conn = FakeConn(user=ADMIN, has_soft=True)
    assert R.delete_ranking(4, 1, conn)["deleted"] == 1
    sql = " ".join(conn.sql())
    assert "UPDATE official_rankings SET deleted_at" in sql and "DELETE FROM" not in sql
    assert conn.commits == 1


def test_delete_hard_fallback_before_migration():
    conn = FakeConn(user=ADMIN, has_soft=False)
    R.delete_ranking(4, 1, conn)
    assert any(s.startswith("DELETE FROM official_rankings") for s in conn.sql())


# ── search + paging ──────────────────────────────────────────────────────────
def test_page_validates_and_filters():
    conn = FakeConn(user=ADMIN, rows=[{"id": 1, "matched": 2, "total": 3}], total=51)
    out = R.rankings_page(search="  ١٢٣  ", page=2, page_size=25, department_id=None, conn=conn)
    assert out["total"] == 51 and out["page"] == 2 and out["page_size"] == 25
    sel = [(s, p) for s, p in conn.log if "FROM official_rankings" in s and "COUNT(*) AS n" not in s][0]
    assert "deleted_at IS NULL" in sel[0] and "LIMIT" in sel[0]
    assert sel[1][-2:] == (25, 25)          # LIMIT 25 OFFSET 25
    assert "%١٢٣%" in sel[1]


def test_page_clamps_bad_numbers():
    conn = FakeConn(user=ADMIN, total=0)
    out = R.rankings_page(search="", page=-3, page_size=100000, department_id=None, conn=conn)
    assert out["page"] == 1 and out["page_size"] == 100


def test_entries_page_search_and_paging():
    conn = FakeConn(user=ADMIN, rows=[], total=0)
    out = R.ranking_entries_page(7, search="علي", only_unlinked=True, page=1, page_size=50, conn=conn)
    assert out["items"] == [] and out["total"] == 0
    s = " ".join(conn.sql())
    assert "student_id IS NULL" in s and "LIMIT" in s


# ── migration files ──────────────────────────────────────────────────────────
def test_soft_delete_migration_and_rollback():
    m = (ROOT / "sql/migrations/0010_official_rankings_soft_delete.sql").read_text(encoding="utf-8")
    assert "deleted_at" in m and "deleted_by" in m and "information_schema" in m
    rb = (ROOT / "sql/fixes/rollback_0010_official_rankings_soft_delete.sql").read_text(encoding="utf-8")
    assert "DROP COLUMN" in rb and "schema_migrations" in rb


# ── client repository (no network: api_client is faked) ──────────────────────
def test_repository_page_and_personnel_id(monkeypatch):
    sys.path.insert(0, str(ROOT))
    import api_client
    from data.repositories import official_rankings as repo_mod

    calls = []

    class Resp:
        def __init__(self, code=200, body=None):
            self.status_code, self._b, self.text = code, body, ""

        def json(self):
            return self._b

    monkeypatch.setattr(repo_mod, "is_online", lambda: True)
    monkeypatch.setattr(api_client, "get", lambda url, **k: (calls.append(("GET", url, k.get("params"))),
                                                             Resp(body={"items": [{"id": 1}], "total": 1}))[1])
    monkeypatch.setattr(api_client, "put", lambda url, **k: (calls.append(("PUT", url, k.get("params"))), Resp())[1])
    monkeypatch.setattr(api_client, "delete", lambda url, **k: (calls.append(("DELETE", url, k.get("params"))), Resp())[1])
    r = repo_mod.OfficialRankingRepository()
    out = r.page(search="x", page=2, page_size=10)
    assert out["total"] == 1 and calls[0][2]["page"] == 2 and calls[0][2]["search"] == "x"
    assert r.entries_page(5, search="a", only_unlinked=True)["total"] == 1
    assert r.set_student(5, 3, 9, personnel_id=7) and calls[-1][2]["personnel_id"] == 7
    assert r.delete(5, personnel_id=7) and calls[-1][2] == {"personnel_id": 7}


def test_repository_page_offline_is_empty(monkeypatch):
    sys.path.insert(0, str(ROOT))
    from data.repositories import official_rankings as repo_mod
    monkeypatch.setattr(repo_mod, "is_online", lambda: False)
    r = repo_mod.OfficialRankingRepository()
    assert r.page() == {"items": [], "total": 0, "page": 1, "page_size": 25}
    assert r.entries_page(1)["items"] == []


def test_save_validates_scope():
    for kw in (dict(department_id=None), dict(study_type=None), dict(exam_round=None)):
        conn = FakeConn(user=ADMIN)
        with pytest.raises(HTTPException) as e:
            R.save_ranking(_payload(**kw), conn)
        assert e.value.status_code == 422 and conn.commits == 0
    masters = _payload(list_type="masters", study_type=None, exam_round=None)
    assert R.save_ranking(masters, FakeConn(user=ADMIN))["saved"] == 1


def test_nav_and_screen_wired():
    # 2026-11-23: a tab inside the graduation orders page, no longer a side-menu page
    orders = (ROOT / "nicegui_screens/graduation_orders_screen.py").read_text(encoding="utf-8")
    assert "OfficialRankingsScreen()" in orders
    assert (ROOT / "nicegui_screens/official_rankings_screen.py").is_file()
