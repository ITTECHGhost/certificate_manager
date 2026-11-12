"""Design tokens and the font stack live in theme.css, once, and work offline."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "nicegui_ui" / "theme.css").read_text(encoding="utf-8")


def _token(name: str) -> str:
    match = re.search(rf"--{name}:\s*([^;]+);", CSS)
    assert match, f"--{name} is not defined"
    return match.group(1).strip()


def test_no_remote_fonts_or_imports():
    assert "fonts.googleapis.com" not in CSS
    assert "@import" not in CSS


def test_one_font_stack_cairo_first_generic_last():
    assert len(re.findall(r"--font-primary\s*:", CSS)) == 1
    assert len(re.findall(r"--font-fallback\s*:", CSS)) == 1
    primary = _token("font-primary")
    fallback = _token("font-fallback")
    assert primary.startswith("'Cairo'")
    assert primary.endswith("var(--font-fallback)")
    assert fallback == "'Segoe UI', Tahoma, Arial, sans-serif"
    assert "local('Cairo')" in CSS


def test_font_stack_not_redefined_in_python():
    for path in (ROOT / "nicegui_ui").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "setProperty('--font-primary'" not in text, path.name
        assert "'Cairo', 'Roboto'" not in text, path.name


def test_spacing_radius_type_and_control_tokens():
    assert [_token(f"space-{i}") for i in range(1, 7)] == ["4px", "8px", "12px", "16px", "24px", "32px"]
    assert _token("radius") == "8px"
    assert [_token(n) for n in ("text-xs", "text-sm", "text-md", "text-lg", "text-xl")] == [
        "12px", "14px", "16px", "20px", "24px"
    ]
    assert _token("line") == "1.5"
    assert _token("control-h") == "40px"
    assert _token("control-h-dense") == "32px"
    assert _token("row-h") == "48px"


def test_buttons_centre_their_text():
    block = CSS[CSS.index(".q-btn .q-btn__content {"):]
    block = block[: block.index("}")]
    assert "inline-flex" in block
    assert "align-items: center" in block


def test_no_monospace_or_blue_accent():
    assert not re.search(r"font-family:[^;]*monospace", CSS)
    accent = _token("accent")
    assert accent.lower() == "#1f7a5a"
