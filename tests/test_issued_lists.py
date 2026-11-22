"""Two lists in «سجل الوثائق الصادرة» (printed drafts / archived issued) and the quiet draft save."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nicegui_screens.issued_certificates_screen import split_lists  # noqa: E402
from services import issued_doc_files as idf  # noqa: E402

RECS = [{"certificate_id": 1, "issue_date": "2026-01-05"},
        {"certificate_id": 2, "issue_date": "2026-03-01"},
        {"certificate_id": 3, "issue_date": "2026-02-01"}]
STATUS = {1: {"printed_at": "2026-01-01 09:00", "archived": True},
          2: {"printed_at": "2026-02-10 09:00", "archived": False},
          3: {"printed_at": "2026-02-20 09:00", "archived": False}}


def test_issued_list_has_archived_only():
    out = split_lists(RECS, STATUS, "issued")
    assert [r["certificate_id"] for r in out] == [1] and out[0]["printed_at"] == "2026-01-01 09:00"


def test_drafts_sorted_by_print_date():
    assert [r["certificate_id"] for r in split_lists(RECS, STATUS, "drafts")] == [3, 2]


def test_no_status_shows_everything_unsplit():
    assert [r["certificate_id"] for r in split_lists(RECS, None, "drafts")] == [2, 3, 1]


def test_latest_draft_and_current_versions():
    items = [{"id": 4, "kind": "draft"}, {"id": 7, "kind": "draft"}, {"id": 5, "kind": "signed"},
             {"id": 8, "kind": "signed", "supersedes_id": 5}]
    assert idf.latest_draft(items)["id"] == 7
    cur, old = idf.current_and_old(items)
    assert 5 not in [i["id"] for i in cur] and [i["id"] for i in old] == [5]


def test_save_draft_quietly_skips_without_file_or_id(tmp_path):
    assert idf.save_draft_quietly(None, str(tmp_path / "x.docx"), 1) is False
    assert idf.save_draft_quietly(3, str(tmp_path / "missing.docx"), 1) is False


def test_save_draft_quietly_never_raises(tmp_path, monkeypatch):
    f = tmp_path / "d.docx"
    f.write_bytes(b"PK\x03\x04")
    monkeypatch.setattr(idf, "is_online", lambda: True)
    monkeypatch.setattr(idf, "upload", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    assert idf.save_draft_quietly(3, str(f), 1) is False
