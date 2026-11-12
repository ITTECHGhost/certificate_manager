"""Issued-certificates log: newest first, five columns, details with reprint and PDF."""
import os
import time
from pathlib import Path

import nicegui_screens.issued_certificates_screen as screen
from nicegui_screens.issued_certificates_screen import find_issued_files, sort_newest_first

SRC = Path(screen.__file__).read_text(encoding="utf-8")


def test_newest_issue_date_first_then_higher_id():
    rows = [
        {"issue_date": "2025-03-01", "certificate_id": 9},
        {"issue_date": "2026-01-10", "certificate_id": 4},
        {"issue_date": "2026-01-10", "certificate_id": 7},
        {"issue_date": None, "certificate_id": 12},
    ]
    assert [r["certificate_id"] for r in sort_newest_first(rows)] == [7, 4, 9, 12]


def test_find_issued_files_by_leading_number(tmp_path, monkeypatch):
    monkeypatch.setattr(screen.app_paths, "data_path", lambda *_: str(tmp_path))
    old = tmp_path / "964-26 - year - Temp - Ar - Ali - DEFAULT.docx"
    old.write_bytes(b"x")
    time.sleep(0.01)
    new = tmp_path / "964-26 - year - Temp - Ar - Ali - BY_PERIOD_STAGE.docx"
    new.write_bytes(b"x")
    os.utime(old, (1, 1))
    (tmp_path / "9640-26 - other.docx").write_bytes(b"x")  # a longer number must not match
    (tmp_path / (new.stem + ".pdf")).write_bytes(b"%PDF")

    docx, pdf = find_issued_files("964/26")
    assert docx == str(new)
    assert pdf == str(tmp_path / (new.stem + ".pdf"))
    assert find_issued_files("111/26") == (None, None)
    assert find_issued_files("—") == (None, None)


def test_table_has_five_columns_and_one_paginator():
    build = SRC[SRC.index("def _build_table"):SRC.index("def _go_to_page")]
    assert build.count('{"name": ') == 5
    assert "UI.paginator(" in build and "rowClick" in build
    assert "السابق" not in SRC


def test_details_offer_reprint_and_pdf_with_quiet_delete():
    detail = SRC[SRC.index("def _show_cert_detail"):SRC.index("async def _ensure_pdf")]
    assert '"إعادة الطباعة"' in detail and '"ملف PDF"' in detail
    assert detail.count("UI.primary_button(") == 1
    assert "UI.danger_icon_button(" in detail
    assert "UI.confirm_dialog(" in SRC


def test_list_shows_skeleton_while_loading():
    assert "UI.skeleton(" in SRC and "run.io_bound" in SRC
