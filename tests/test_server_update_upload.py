"""Client side of the server-update upload: streamed multipart body with progress."""
import email
import email.policy
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import services.server_update as su


class _Capture(BaseHTTPRequestHandler):
    got = {}

    def do_POST(self):
        n = int(self.headers["Content-Length"])
        _Capture.got = {"headers": dict(self.headers), "body": self.rfile.read(n),
                        "chunked": "Transfer-Encoding" in self.headers}
        out = json.dumps({"pending": {"version": "9.9.9", "run_at": "now"}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


@pytest.fixture
def server(monkeypatch):
    httpd = HTTPServer(("127.0.0.1", 0), _Capture)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    monkeypatch.setattr(su, "is_online", lambda: True)
    monkeypatch.setattr(su, "get_api_url", lambda: f"http://127.0.0.1:{httpd.server_port}")
    yield _Capture
    httpd.shutdown()


def _parse(headers, body):
    msg = email.message_from_bytes(
        f"Content-Type: {headers['Content-Type']}\r\n\r\n".encode() + body, policy=email.policy.HTTP)
    return {p.get_param("name", header="content-disposition"): p for p in msg.iter_parts()}


def test_upload_streams_valid_multipart_and_reports_progress(server, tmp_path):
    payload = bytes(range(256)) * 12000  # ~3 MB: several 1 MB pieces
    z = tmp_path / "CertificateManagerUpdate-9.9.9.zip"
    z.write_bytes(payload)
    calls = []

    ok, msg, pending = su.upload(str(z), "admin", "pa:ssع", "2026-11-15T22:00",
                                 progress=lambda s, t: calls.append((s, t)))

    assert ok and pending["version"] == "9.9.9", msg
    got = server.got
    assert not got["chunked"] and int(got["headers"]["Content-Length"]) == len(got["body"])
    parts = _parse(got["headers"], got["body"])
    assert parts["file"].get_filename() == z.name
    assert parts["file"].get_payload(decode=True) == payload
    assert parts["username"].get_content().strip() == "admin"
    assert parts["run_at"].get_content().strip() == "2026-11-15T22:00"
    # progress: increasing, ends exactly at the total
    assert calls and calls[-1][0] == calls[-1][1] == len(got["body"])
    assert all(a[0] <= b[0] for a, b in zip(calls, calls[1:]))


def test_upload_progress_errors_do_not_break_upload(server, tmp_path):
    z = tmp_path / "u.zip"
    z.write_bytes(b"x" * 10)

    def boom(s, t):
        raise RuntimeError("ui gone")

    ok, msg, _ = su.upload(str(z), "a", "b", progress=boom)
    assert ok, msg


def test_upload_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(su, "is_online", lambda: True)
    ok, msg, _ = su.upload(str(tmp_path / "nope.zip"), "a", "b")
    assert not ok and msg


def test_upload_failure_is_logged(monkeypatch, tmp_path, caplog):
    """A failed upload must leave a line in the log (the 2.5.2 upload failed with no trace)."""
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()  # nothing listens
    monkeypatch.setattr(su, "is_online", lambda: True)
    monkeypatch.setattr(su, "get_api_url", lambda: f"http://127.0.0.1:{port}")
    z = tmp_path / "u.zip"
    z.write_bytes(b"x" * 10)
    with caplog.at_level("INFO", logger="server_update"):
        ok, msg, _ = su.upload(str(z), "a", "secret-pw")
    assert not ok and msg
    text = caplog.text
    assert "upload started" in text and "upload failed" in text
    assert "secret-pw" not in text
