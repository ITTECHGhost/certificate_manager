"""Derived colour names must follow dark mode, not stay at their light :root values."""
import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "nicegui_ui" / "theme.css").read_text(encoding="utf-8")


def _blocks():
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", CSS):
        yield m.group(1).strip(), m.group(2)


def test_every_var_alias_is_also_declared_for_dark():
    """A custom property set to var(...) only on :root is resolved there, against the light
    tokens, and every element then inherits the light colour even under .body--dark."""
    for selector, body in _blocks():
        if "var(" not in body:
            continue
        sels = {s.strip() for s in selector.split(",")}
        if ":root" in sels:
            aliased = [ln for ln in body.splitlines()
                       if re.match(r"\s*--[\w-]+:\s*var\(", ln) and "--font" not in ln]
            if aliased:
                assert "body.body--dark" in sels, f"{selector}: {aliased[:3]}"


def test_bg_main_follows_dark_surface():
    for selector, body in _blocks():
        if "--bg-main:" in body:
            assert "body.body--dark" in selector
