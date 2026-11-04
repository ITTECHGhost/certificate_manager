"""Settings: tab order, logo upload without an empty progress box, RTL under advanced, printers."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = ROOT / "nicegui_screens" / "settings"


def _src(name: str) -> str:
    return (SETTINGS / name).read_text(encoding="utf-8")


def test_tabs_are_vertical_and_start_with_university_info():
    src = _src("screen.py")
    assert src.index('ui.tab(name="institution", label="معلومات الجامعة"') < src.index('ui.tab(name="appearance"')
    assert '"vertical' in src


def test_logo_uploader_is_hidden_until_a_file_is_picked():
    src = _src("institution.py")
    assert src.count('.classes("hidden")') >= 2
    assert src.count('run_method("pickFiles")') == 2
    assert 'ui.grid(columns=2).classes("w-full gap-4"):\n                self.univ_ar_input' not in src


def test_rtl_switch_is_under_advanced():
    src = _src("appearance.py")
    adv = src.index('ui.expansion("متقدم"')
    assert src.index("self.rtl_switch =") > adv


def test_printer_pickers_full_width_and_arabic_orientation():
    src = _src("printers.py")
    assert '{"Portrait": "عمودي", "Landscape": "أفقي"}' in src
    assert "Printer names are long" in src


def test_role_cards_have_one_summary_line():
    src = _src("roles.py")
    body = src[src.index("def _render_roles_overview"):src.index("def _render_full_page_role_editor")]
    assert "summary = f" in body
    assert "font-mono" not in body and "+{len(allowed_pages)-5}" not in body
