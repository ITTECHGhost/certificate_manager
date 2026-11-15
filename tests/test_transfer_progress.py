"""Text of the shared progress bar, and page progress from order image uploads."""
import services.order_images as oi
from nicegui_ui.transfer_progress import format_bytes_line, format_pages_line


def test_bytes_line():
    mb = 1048576
    assert format_bytes_line(0, 100 * mb, 0.5) == "0.0 / 100.0 MB (0%)"
    line = format_bytes_line(25 * mb, 100 * mb, 10.0)  # 2.5 MB/s → 30 s left
    assert line.startswith("25.0 / 100.0 MB (25%)") and "2.5 MB/ث" in line and "0:30" in line
    assert format_bytes_line(100 * mb, 100 * mb, 40.0).endswith("اكتمل النقل")


def test_pages_line():
    assert format_pages_line(3, 12) == "الصفحة 3 من 12"
    assert format_pages_line(1, 0) == "الصفحة 1"


class _Resp:
    status_code = 200

    def json(self):
        return {"duplicate": False, "sha256": "x"}


def test_upload_file_reports_pages(monkeypatch):
    monkeypatch.setattr(oi, "is_online", lambda: True)
    monkeypatch.setattr(oi, "file_to_pages", lambda name, data: [(b"p1", b"t1"), (b"p2", b"t2"), (b"p3", b"t3")])
    monkeypatch.setattr(oi.api_client, "post", lambda *a, **k: _Resp())
    monkeypatch.setattr(oi, "_cache_put", lambda *a: None)
    calls = []
    assert oi.upload_file(1, "order.pdf", b"", progress=lambda d, t: calls.append((d, t))) == 3
    assert calls == [(0, 3), (1, 3), (2, 3), (3, 3)]
