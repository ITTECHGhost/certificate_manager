"""Multi-row actions are all-or-nothing: /sp/write-batch runs every step in one
transaction, a failure part-way rolls everything back, and the client uses it
(falling back to the old step-by-step path only on a server without it)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.path.join(ROOT, "certificate_manager_api")


@pytest.fixture()
def system():
    sys.path.insert(0, API)
    try:
        import importlib
        mod = importlib.import_module("routers.system")
        yield mod
    finally:
        sys.path.remove(API)


class _Res:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _Cur:
    def __init__(self, log, fail_at=None):
        self.log, self.fail_at, self._last = log, fail_at, None

    def callproc(self, name, args):
        if self.fail_at is not None and len(self.log["calls"]) == self.fail_at:
            raise RuntimeError("connection lost")
        self.log["calls"].append((name, args))
        self._last = {"new_id": 100 + len(self.log["calls"])}

    def stored_results(self):
        return [_Res(self._last)]

    def close(self):
        pass


class _Conn:
    def __init__(self, fail_at=None):
        self.log = {"calls": [], "commit": 0, "rollback": 0}
        self.fail_at = fail_at

    def cursor(self, **kw):
        return _Cur(self.log, self.fail_at)

    def commit(self):
        self.log["commit"] += 1

    def rollback(self):
        self.log["rollback"] += 1


def _payload(system, steps):
    return system.SPBatchPayload(steps=[system.SPCallPayload(proc=p, args=a) for p, a in steps])


def test_batch_commits_once_and_resolves_refs(system):
    conn = _Conn()
    out = system.sp_write_batch(_payload(system, [
        ("InsertStudyRoutine", ["r", "r", 1, 1]),
        ("InsertStudyRoutinePeriod", [{"$ref": 0}, 1, 1]),
        ("InsertStudyRoutinePeriod", [{"$ref": 0}, 1, 2]),
    ]), conn=conn)
    assert out["new_ids"] == [101, 102, 103]
    assert conn.log["calls"][1] == ("InsertStudyRoutinePeriod", (101, 1, 1))
    assert conn.log["commit"] == 1 and conn.log["rollback"] == 0


def test_failure_part_way_saves_nothing(system):
    from fastapi import HTTPException
    conn = _Conn(fail_at=2)
    with pytest.raises(HTTPException) as e:
        system.sp_write_batch(_payload(system, [
            ("InsertStudyRoutine", ["r", "r", 1, 1]),
            ("InsertStudyRoutinePeriod", [{"$ref": 0}, 1, 1]),
            ("InsertStudyRoutinePeriod", [{"$ref": 0}, 1, 2]),
        ]), conn=conn)
    assert e.value.status_code == 500 and "Nothing was saved" in e.value.detail
    assert conn.log["commit"] == 0 and conn.log["rollback"] == 1


def test_unlisted_procedure_refused_before_anything_runs(system):
    from fastapi import HTTPException
    conn = _Conn()
    with pytest.raises(HTTPException) as e:
        system.sp_write_batch(_payload(system, [("InsertStudyRoutine", []), ("DropEverything", [])]), conn=conn)
    assert e.value.status_code == 403 and conn.log["calls"] == []


def test_bad_ref_is_refused(system):
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        system.resolve_refs([{"$ref": 3}], [1])
    assert system.resolve_refs([{"$ref": 0}, "x", 5], [9]) == (9, "x", 5)


def test_get_db_rolls_back_an_open_transaction():
    src = open(os.path.join(API, "deps.py"), encoding="utf-8").read()
    assert "if conn.in_transaction:" in src and "conn.rollback()" in src


# ---- client side ----

class _Resp:
    def __init__(self, code, body=None):
        self.status_code, self._body, self.text = code, body or {}, ""

    def json(self):
        return self._body


def _routine_repo(monkeypatch, resp):
    from data.repositories import study_routines as mod
    from data.repositories import base
    sent = []
    monkeypatch.setattr(base, "is_online", lambda: True)
    monkeypatch.setattr(mod, "is_online", lambda: True)
    monkeypatch.setattr(base.api_client, "post", lambda url, **kw: sent.append((url, kw.get("data"))) or resp)
    repo = mod.StudyRoutineRepository.__new__(mod.StudyRoutineRepository)
    repo.api_url = "http://api"
    return mod, repo, sent


def test_new_routine_is_one_request(monkeypatch):
    import json
    mod, repo, sent = _routine_repo(monkeypatch, _Resp(200, {"new_ids": [7] + [None] * 8}))
    monkeypatch.setattr(mod, "log_activity", lambda *a, **k: None)
    assert repo.insert({"name_ar": "ر", "department_id": 2, "study_system_id": 1}) == 7
    assert len(sent) == 1 and sent[0][0].endswith("/sp/write-batch")
    steps = json.loads(sent[0][1])["steps"]
    assert steps[0]["proc"] == "InsertStudyRoutine" and len(steps) == 9
    assert all(s["args"][0] == {"$ref": 0} for s in steps[1:])


def test_server_refusal_raises_instead_of_saving_locally(monkeypatch):
    mod, repo, sent = _routine_repo(monkeypatch, _Resp(500))
    called = []
    monkeypatch.setattr(mod, "insert_offline_study_routine", lambda *a: called.append(a) or 1)
    with pytest.raises(RuntimeError):
        repo.insert({"name_ar": "ر"})
    assert called == []          # no half-saved local copy


def test_old_server_falls_back(monkeypatch):
    from data.repositories.base import BatchNotSupported
    mod, repo, sent = _routine_repo(monkeypatch, _Resp(404))
    with pytest.raises(BatchNotSupported):
        repo._call_write_batch([("InsertStudyRoutine", ())])


def test_personnel_save_sends_role_and_permissions_together():
    src = open(os.path.join(ROOT, "nicegui_screens", "personnel_screen.py"), encoding="utf-8").read()
    assert 'payload["role_id"] = str(chosen_role_id)' in src
    assert 'payload["permission_keys"] = perm_keys' in src
    assert "self.repo.last_save_combined" in src
    api = open(os.path.join(API, "routers", "personnel.py"), encoding="utf-8").read()
    assert api.count("    _save_role_and_permissions(cur, ") == 2   # insert and update, not the def
