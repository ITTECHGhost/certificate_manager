"""Page switching: skeleton first, slow data and hidden tabs off the build path."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASH = (ROOT / "nicegui_screens" / "dashboard_screen.py").read_text(encoding="utf-8")


def _method(src: str, name: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            return ast.get_source_segment(src, node)
    raise AssertionError(name)


def test_switch_shows_skeleton_then_builds_on_next_tick():
    render = _method(DASH, "_render_active_screen")
    assert "UI.skeleton(" in render and "ui.timer(" in render
    # a newer switch wins over a pending one
    assert "if token != self._render_token" in _method(DASH, "_build_active_screen")


def test_dashboard_does_not_load_whole_report_while_building():
    assert "get_issued_certificates_report" not in _method(DASH, "refresh_data")
    assert "run.io_bound" in _method(DASH, "_load_issued_count")


def test_hidden_tabs_build_on_first_open():
    settings = (ROOT / "nicegui_screens" / "settings" / "screen.py").read_text(encoding="utf-8")
    build = _method(settings, "_build_ui")
    assert "on_value_change" in build and "_build_panel(" in build
    courses = (ROOT / "nicegui_screens" / "courses_screen.py").read_text(encoding="utf-8")
    listing = _method(courses, "show_list_view")
    assert "on_value_change(_open_routines)" in listing
