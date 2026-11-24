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
        __import__("PIL.Image").Image.new("RGB", (4, 4)).save(path, "BMP")


class _Item:
    def __init__(self, pages):
        self.left = pages

    def Transfer(self, fmt=None):
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
        def Transfer(self, fmt=None):
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
    assert not any(p.exists() for p in pages)  # only the PDF stays
    assert data.startswith(b"%PDF") and data.count(b"/Type /Page\n") + data.count(b"/Type /Page ") >= 1


def test_scan_defaults_match_the_office_scanner():
    import inspect
    sig = inspect.signature(scanner.scan_pages)
    assert sig.parameters["file_type"].default == "pdf" and sig.parameters["page_size"].default == "A4"
    assert sig.parameters["color"].default is True and sig.parameters["dpi"].default == 300


class _Invalid(Exception):
    def __init__(self):
        super().__init__(-2147352567, "Exception occurred.",
                         (0, None, "The parameter is incorrect.\r\n", None, 0, -2147024809), None)


class _Refuses(_Item):
    """Refuses (E_INVALIDARG) at the levels listed, then gives pages."""
    def __init__(self, pages, refuse):
        super().__init__(pages)
        self.refuse = refuse

    def Transfer(self, fmt=None):
        if self.refuse:
            raise _Invalid()
        return super().Transfer(fmt)


def _fake_levels(monkeypatch, tmp_path, refused_levels, pages=2):
    tried = []
    monkeypatch.setattr(scanner, "scans_root", lambda: tmp_path)

    def prep(device_id, source, dpi, color, page_size, level):
        tried.append(level)
        return _Refuses(pages, level in refused_levels)
    monkeypatch.setattr(scanner, "_prepare", prep)
    return tried


def test_refused_setting_retries_with_fewer(monkeypatch, tmp_path):
    tried = _fake_levels(monkeypatch, tmp_path, {"all"})
    folder, files = scanner.scan_pages("dev", "flatbed", file_type="jpg")
    assert tried == ["all", "no_page_size"] and len(files) == 1   # flatbed: one page


def test_refused_everything_is_clear_message(monkeypatch, tmp_path):
    tried = _fake_levels(monkeypatch, tmp_path, set(scanner.SETTING_LEVELS))
    with pytest.raises(RuntimeError, match="رفض الماسح"):
        scanner.scan_pages("dev", "flatbed")
    assert tried == list(scanner.SETTING_LEVELS) and not list(tmp_path.iterdir())


def test_invalid_setting_detected():
    assert scanner.is_invalid_setting(_Invalid()) and not scanner.is_invalid_setting(_Empty())


def _fake_winrt(monkeypatch, tmp_path, output, rc=0):
    monkeypatch.setattr(scanner, "new_batch_folder", lambda: (tmp_path / "b").mkdir() or tmp_path / "b")
    monkeypatch.setattr(scanner, "_scanner_name", lambda d: "Canon MF270 Series")
    calls = []

    def run(script, args):
        calls.append(args)
        folder = Path(args[args.index("-Out") + 1])
        lines = []
        for n in range(output if isinstance(output, int) else 0):
            f = folder / (f"SCN_x_{n}.jpg" if n else "SCN_x.jpg")
            from PIL import Image
            Image.new("RGB", (10, 10)).save(f)
            lines.append(f"FILE {f}")
        return rc, "\n".join(lines) if isinstance(output, int) else output
    monkeypatch.setattr(scanner, "_run_powershell", run)
    return calls


def test_feeder_uses_windows_scan_api_and_names_pages(monkeypatch, tmp_path):
    """Seen on the Canon MF270 (2026-11-24): WIA Transfer gives None; the WinRT API gives one file per sheet."""
    calls = _fake_winrt(monkeypatch, tmp_path, 3)
    folder, files = scanner.scan_pages("dev", "feeder", file_type="jpg")
    assert [f.name for f in files] == ["page_001.jpg", "page_002.jpg", "page_003.jpg"]
    assert calls[0][calls[0].index("-Name") + 1] == "Canon MF270 Series"


def test_feeder_pages_become_one_pdf(monkeypatch, tmp_path):
    _fake_winrt(monkeypatch, tmp_path, 2)
    folder, files = scanner.scan_pages("dev", "feeder")
    assert len(files) == 1 and files[0].suffix == ".pdf" and [p.name for p in folder.iterdir()] == [files[0].name]


def test_feeder_empty_is_clear_message(monkeypatch, tmp_path):
    _fake_winrt(monkeypatch, tmp_path, "ERR -2145844748 Internal server error (500).", rc=1)
    with pytest.raises(RuntimeError, match="المغذّي فارغ"):
        scanner.scan_pages("dev", "feeder")
    assert not (tmp_path / "b").exists()


def test_feeder_busy_is_clear_message(monkeypatch, tmp_path):
    _fake_winrt(monkeypatch, tmp_path, "ERR -2145320954 busy", rc=1)
    with pytest.raises(RuntimeError, match="مشغول"):
        scanner.scan_pages("dev", "feeder")
