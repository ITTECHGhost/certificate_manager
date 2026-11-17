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

    from nicegui_ui.state import app_session
    monkeypatch.setattr(app_session, "emp_id", 1, raising=False)
    scr = ps.PersonnelScreen.__new__(ps.PersonnelScreen)
    scr.repo = _Repo()
    scr._render_content = lambda: None
    monkeypatch.setattr(ps.UI, "notify", lambda *a, **k: None)
    scr._toggle_active({"id": 7, "name": "x", "active": True})
    scr._toggle_active({"id": 7, "name": "x", "active": False})
    scr._toggle_active({"id": 1, "name": "me", "active": True})   # own account: refused
    assert calls == [(7, 0), (7, 1)]


def test_status_column_is_a_switch():
    src = open(os.path.join(ROOT, "nicegui_screens", "personnel_screen.py"), encoding="utf-8").read()
    assert "<q-toggle" in src and "$parent.$emit('toggle_active', props.row)" in src


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


def test_is_account_active(monkeypatch):
    from data.repositories import personnel as mod

    class _Resp:
        def __init__(self, code, body=None):
            self.status_code, self._body = code, body or {}

        def json(self):
            return self._body

    repo = mod.PersonnelRepository.__new__(mod.PersonnelRepository)
    repo.api_url = "http://api"
    monkeypatch.setattr(mod, "is_online", lambda: True)
    for resp, want in ((_Resp(200, {"is_active": 0}), False), (_Resp(200, {"is_active": 1}), True),
                       (_Resp(404), False), (_Resp(500), None)):
        monkeypatch.setattr(mod.api_client, "get", lambda url, r=resp, **kw: r)
        assert repo.is_account_active(3) is want
    monkeypatch.setattr(mod, "is_online", lambda: False)
    assert repo.is_account_active(3) is None


def test_dashboard_signs_out_a_disabled_account():
    src = open(os.path.join(ROOT, "nicegui_screens", "dashboard_screen.py"), encoding="utf-8").read()
    assert "is_account_active" in src and "if active is False:" in src


def test_stored_procedure_and_logins_respect_is_active():
    sp = open(os.path.join(ROOT, "sql", "SP.sql"), encoding="utf-8").read()
    body = re.search(r"PROCEDURE `TogglePersonnelStatus`.*?END //", sp, re.S).group(0)
    assert "SET is_active = p_is_active WHERE id = p_person_id" in body
    api = open(os.path.join(ROOT, "certificate_manager_api", "routers", "personnel.py"), encoding="utf-8").read()
    assert "AND is_active = 1" in api
    repo = open(os.path.join(ROOT, "data", "repositories", "personnel.py"), encoding="utf-8").read()
    assert 'not user.get("is_active")' in repo
