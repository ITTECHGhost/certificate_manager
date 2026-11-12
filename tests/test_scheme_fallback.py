import requests

import api_config
import sync_engine


class _Resp:
    status_code = 200


def test_switches_to_the_scheme_that_answers(monkeypatch):
    calls = []

    def fake_get(url, timeout=None):
        calls.append(url)
        if url.startswith("https://"):
            return _Resp()
        raise requests.ConnectionError("refused")

    saved = []
    monkeypatch.setattr(sync_engine.api_client, "get", fake_get)
    monkeypatch.setattr(api_config, "set_scheme", lambda s: saved.append(s))
    monkeypatch.setattr(api_config, "other_scheme_url", lambda: "https://10.0.0.5:2030")
    monkeypatch.setattr(sync_engine, "get_api_url", lambda: "http://10.0.0.5:2030")
    monkeypatch.setattr(sync_engine, "_last_scheme_probe", 0.0)
    assert sync_engine.check_network_status() is True
    assert saved == ["https"]
    # rate limited: a second failure within a minute does not probe again
    monkeypatch.setattr(api_config, "other_scheme_url", lambda: "http://x:1")
    assert sync_engine.check_network_status() is False


def test_explicit_target_never_switches(monkeypatch):
    monkeypatch.setattr(sync_engine.api_client, "get",
                        lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError()))
    monkeypatch.setattr(sync_engine, "_last_scheme_probe", 0.0)
    assert sync_engine.check_network_status(target_url="http://h:1") is False
