"""Accent themes: five token sets in theme.css, each readable in light and dark."""
import re
from pathlib import Path

from nicegui_ui.ui_theme import ACCENT_OPTIONS, ACCENT_LABELS, ACCENT_SWATCHES, normalize_accent

CSS = (Path(__file__).resolve().parents[1] / "nicegui_ui" / "theme.css").read_text(encoding="utf-8")
LIGHT = {"card": "#ffffff", "main": "#f4f5f7"}
DARK = {"card": "#1a1e23", "main": "#121519"}


def _lum(hex_):
    h = hex_.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _ratio(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _block(selector):
    m = re.search(re.escape(selector) + r"[^{]*\{([^}]*)\}", CSS)
    assert m, selector
    return dict(re.findall(r"--([\w-]+):\s*([^;]+);", m.group(1)))


def test_the_five_accents_of_571f6aa_are_back():
    assert set(ACCENT_OPTIONS) == {"green", "blue", "red", "orange", "purple"}
    for name in ACCENT_OPTIONS:
        assert ACCENT_LABELS[name]["ar"] and ACCENT_LABELS[name]["en"]
        assert ACCENT_SWATCHES[name].startswith("#")


def test_every_accent_has_light_and_dark_token_sets():
    for name in ACCENT_OPTIONS:
        for sel in (f"body.accent-{name} {{", f"body.accent-{name}.body--dark"):
            toks = _block(sel.rstrip(" {"))
            for key in ("accent", "accent-hover", "accent-text", "accent-soft", "accent-soft-strong", "accent-ring"):
                assert key in toks, (sel, key)


def test_accent_contrast_is_at_least_4_5_in_both_modes():
    for name in ACCENT_OPTIONS:
        light = _block(f"body.accent-{name}")
        dark = _block(f"body.accent-{name}.body--dark")
        for toks, surf in ((light, LIGHT), (dark, DARK)):
            assert _ratio("#ffffff", toks["accent"].strip()) >= 4.5, name
            for bg in surf.values():
                assert _ratio(toks["accent-text"].strip(), bg) >= 4.5, (name, bg)


def test_normalize_accent_maps_old_and_unknown_values():
    assert normalize_accent("Blue") == "blue"
    assert normalize_accent("dark_blue") == "blue"
    assert normalize_accent("dark-blue") == "blue"
    assert normalize_accent(None) == "green"
    assert normalize_accent("pink") == "green"


def test_success_does_not_follow_the_accent():
    assert "--success: var(--accent" not in CSS
