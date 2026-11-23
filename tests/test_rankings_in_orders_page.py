"""Official ranking lists and the scanned-papers import live inside the graduation orders page
(not the side menu); the ranking import also reads the CSV the AI makes from the scanned paper."""
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nicegui_ui.ui_theme import NAV_ITEMS  # noqa: E402
from services.official_ranking_import import read_csv, read_excel, read_list_file  # noqa: E402

ROWS = [("ت", "الاسم", "المعدل"), (1, "علي حسن", "85.5"), (2, "زيد علي", "80")]


def _xlsx() -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    for r in ROWS:
        wb.active.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _csv() -> bytes:
    return ("﻿" + "\n".join(",".join(str(c) for c in r) for r in ROWS)).encode("utf-8")


def test_csv_reads_like_excel():
    assert read_csv(_csv()) == read_excel(_xlsx())
    assert [r["position"] for r in read_csv(_csv())] == [1, 2]


def test_file_type_by_name():
    assert read_list_file("list.CSV", _csv()) == read_list_file("list.xlsx", _xlsx())


def test_side_menu_has_no_separate_pages():
    keys = {i["key"] for i in NAV_ITEMS}
    assert "rankings" not in keys and "scan_import" not in keys and "orders" in keys


def test_orders_page_holds_both_tabs():
    src = (ROOT / "nicegui_screens" / "graduation_orders_screen.py").read_text(encoding="utf-8")
    assert "OfficialRankingsScreen()" in src and "ScannedOrdersImportScreen(" in src
    rank = (ROOT / "nicegui_screens" / "official_rankings_screen.py").read_text(encoding="utf-8")
    assert "scan_card(" in rank and ".csv" in rank
