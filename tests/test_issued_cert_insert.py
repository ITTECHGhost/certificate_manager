import pytest

from data.repositories import certificates as mod


class _Resp:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text

    def json(self):
        return {"new_id": 7}


def _setup(monkeypatch, response):
    queued = []
    monkeypatch.setattr(mod, "is_online", lambda: True)
    monkeypatch.setattr(mod.api_client, "post", lambda *a, **k: response() if callable(response) else response)
    monkeypatch.setattr("data.query.insert_offline_issued_certificate", lambda **kw: queued.append(kw) or -1)
    monkeypatch.setattr("sync_engine.mark_cert_number_used", lambda n: None)
    monkeypatch.setattr(mod, "log_activity", lambda *a, **k: None)
    monkeypatch.setattr(mod, "log_system", lambda *a, **k: None)
    return queued


def _insert():
    return mod.IssuedCertificateRepository().insert(student_id=1, issue_date="2026-10-29", certificate_number="5/26")


def test_rejected_certificate_is_not_queued(monkeypatch):
    queued = _setup(monkeypatch, _Resp(409, "exists"))
    with pytest.raises(mod.CertificateRejected):
        _insert()
    assert queued == []


def test_unreachable_server_queues_offline(monkeypatch):
    def boom():
        raise ConnectionError("down")
    queued = _setup(monkeypatch, boom)
    _insert()
    assert len(queued) == 1


def test_accepted_certificate_returns_server_id(monkeypatch):
    queued = _setup(monkeypatch, _Resp(200))
    assert _insert() == 7
    assert queued == []


def test_temp_student_id_is_queued_even_online(monkeypatch):
    """A student created offline (negative id) is unknown to the server (MySQL 1452):
    the print is queued; sync swaps the id. Seen on a user laptop, 2026-11-24."""
    def never():
        raise AssertionError("must not call the server")
    queued = _setup(monkeypatch, never)
    mod.IssuedCertificateRepository().insert(student_id=-3, issue_date="2026-11-24", certificate_number="1084/26")
    assert queued and queued[0]["student_id"] == -3
