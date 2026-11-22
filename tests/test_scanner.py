"""Scanning order papers (services/scanner.py): feeder loop, empty tray, folders. No real scanner."""
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import scanner  # noqa: E402


class _Empty(Exception):
    def __init__(self):
        super().__init__(-2147352567, "Exception occurred.", (0, None, None, None, 0, -2145320957), None)


class _Image:
    def SaveFile(self, path):
        Path(path).write_bytes(b"\xff\xd8\xff")


class _Item:
    def __init__(self, pages):
        self.left = pages

    def Transfer(self, fmt):
        if self.left <= 0:
            raise _Empty()
        self.left -= 1
        return _Image()


def test_feeder_takes_every_sheet_until_empty(tmp_path):
    seen = []
    pages = scanner._transfer_pages(_Item(3), "feeder", tmp_path, 200, progress=seen.append)
    assert [p.name for p in pages] == ["page_001.jpg", "page_002.jpg", "page_003.jpg"] and seen == [1, 2, 3]


def test_empty_feeder_at_start_is_clear_message(tmp_path):
    with pytest.raises(RuntimeError, match="المغذّي فارغ"):
        scanner._transfer_pages(_Item(0), "feeder", tmp_path, 200)


def test_flatbed_takes_one_page(tmp_path):
    assert len(scanner._transfer_pages(_Item(5), "flatbed", tmp_path, 200)) == 1


def test_other_errors_are_not_swallowed(tmp_path):
    class _Jam(_Item):
        def Transfer(self, fmt):
            raise RuntimeError("paper jam")
    with pytest.raises(RuntimeError, match="paper jam"):
        scanner._transfer_pages(_Jam(1), "feeder", tmp_path, 200)


def test_batch_folders_never_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "scans_root", lambda: tmp_path)
    now = datetime(2026, 11, 22, 10, 30, 0)
    a, b = scanner.new_batch_folder(now), scanner.new_batch_folder(now)
    assert a.name == "2026-11-22 10-30-00" and b.name == "2026-11-22 10-30-00 (2)"


def test_paper_empty_detection():
    assert scanner.is_paper_empty(_Empty()) and not scanner.is_paper_empty(RuntimeError("x"))


def test_unknown_source_refused():
    with pytest.raises(ValueError):
        scanner.scan_pages("dev", source="cloud")


def test_pages_join_into_one_pdf(tmp_path):
    from PIL import Image
    pages = []
    for i in range(3):
        p = tmp_path / f"page_{i}.jpg"
        Image.new("RGB", (40, 60), "white").save(p, "JPEG")
        pages.append(p)
    pdf = scanner.pages_to_pdf(pages, tmp_path / "order.pdf")
    data = pdf.read_bytes()
    assert data.startswith(b"%PDF") and data.count(b"/Type /Page\n") + data.count(b"/Type /Page ") >= 1


def test_scan_defaults_match_the_office_scanner():
    import inspect
    sig = inspect.signature(scanner.scan_pages)
    assert sig.parameters["file_type"].default == "pdf" and sig.parameters["page_size"].default == "A4"
    assert sig.parameters["color"].default is True and sig.parameters["dpi"].default == 300
