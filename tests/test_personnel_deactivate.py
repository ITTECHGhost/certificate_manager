"""Deactivating a user: the button in الكادر sends is_active=0, the API runs
TogglePersonnelStatus with it, and an inactive account cannot log in (online or offline)."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_screen_sends_zero_for_an_active_row(monkeypatch):
    from nicegui_screens import personnel_screen as ps
    calls = []

    class _Repo:
        def toggle_active(self, pid, value):
            calls.append((pid, value))

    scr = ps.PersonnelScreen.__new__(ps.PersonnelScreen)
    scr.repo = _Repo()
    scr._render_content = lambda: None
    monkeypatch.setattr(ps.UI, "notify", lambda *a, **k: None)
    scr._toggle_active({"id": 7, "name": "x", "active": True})
    scr._toggle_active({"id": 7, "name": "x", "active": False})
    assert calls == [(7, 0), (7, 1)]


def test_edit_form_has_an_active_switch_that_is_saved():
    src = open(os.path.join(ROOT, "nicegui_screens", "personnel_screen.py"), encoding="utf-8").read()
    assert "active_switch = UI.switch(" in src
    assert '"is_active": 1 if active_switch.value else 0' in src
    assert 'existing_data.get("is_active", 1)\n' not in src


def test_repo_posts_the_value(monkeypatch):
    from data.repositories import personnel as mod
    sent = []

    class _Resp:
        status_code, text = 200, ""

    monkeypatch.setattr(mod, "is_online", lambda: True)
    monkeypatch.setattr(mod.api_client, "post", lambda url, **kw: sent.append((url, kw.get("params"))) or _Resp())
    repo = mod.PersonnelRepository.__new__(mod.PersonnelRepository)
    repo.api_url = "http://api"
    repo.toggle_active(7, 0)
    assert sent == [("http://api/personnel/7/toggle", {"is_active": 0})]


def test_stored_procedure_and_logins_respect_is_active():
    sp = open(os.path.join(ROOT, "sql", "SP.sql"), encoding="utf-8").read()
    body = re.search(r"PROCEDURE `TogglePersonnelStatus`.*?END //", sp, re.S).group(0)
    assert "SET is_active = p_is_active WHERE id = p_person_id" in body
    api = open(os.path.join(ROOT, "certificate_manager_api", "routers", "personnel.py"), encoding="utf-8").read()
    assert "AND is_active = 1" in api
    repo = open(os.path.join(ROOT, "data", "repositories", "personnel.py"), encoding="utf-8").read()
    assert 'not user.get("is_active")' in repo
