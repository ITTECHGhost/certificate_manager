"""Login on a dead link falls back to this laptop's stored password after ONE short attempt
(2026-11-26: logins took very long on a user laptop with a dropping link)."""
import requests

from data.repositories import personnel as mod


def test_unreachable_server_uses_local_password_after_one_attempt(monkeypatch):
    seen = []

    def fake_post(url, **k):
        seen.append(k)
        raise requests.ConnectTimeout("no route")
    monkeypatch.setattr(mod, "is_online", lambda: True)
    monkeypatch.setattr(mod.api_client, "post", fake_post)
    monkeypatch.setattr(mod, "get_offline_personnel_by_username",
                        lambda u: {"id": 5, "username": u, "is_active": 1, "password_hash": "H"})
    monkeypatch.setattr(mod, "is_password_disabled", lambda h: False)
    monkeypatch.setattr(mod, "verify_password", lambda p, h: p == "H")
    monkeypatch.setattr(mod, "log_activity", lambda *a, **k: None)
    monkeypatch.setattr(mod, "log_system", lambda *a, **k: None)
    user = mod.PersonnelRepository().authenticate("ali", "H")
    assert user and user["id"] == 5 and "password_hash" not in user
    assert len(seen) == 1 and seen[0]["retry"] is False and seen[0]["timeout"][0] <= 3.0
