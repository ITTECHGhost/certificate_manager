"""Template tags: one colour family per kind, a different shade per value, the same
classes on Settings → قوالب الوثائق and on «إصدار كتاب», readable in dark mode."""
import os
import re

from nicegui_ui.template_constants import (
    TAG_GENDERS, TAG_LANGS, TAG_MARKS, TAG_SYSTEMS, tag_chips, tag_class, tag_label_classes, template_tags,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = open(os.path.join(ROOT, "nicegui_ui", "theme.css"), encoding="utf-8").read()


def _all_classes():
    out = set()
    for k in TAG_SYSTEMS:
        out.add(tag_class("system", k))
    for k in TAG_LANGS:
        out.add(tag_class("lang", k))
    for k in TAG_MARKS:
        out.add(tag_class("marks", k))
    for k in TAG_GENDERS:
        out.add(tag_class("gender", k))
    return out


def test_each_value_has_its_own_class_within_a_kind():
    assert tag_class("lang", "Ar") != tag_class("lang", "En")
    assert tag_class("marks", True) != tag_class("marks", False)
    assert tag_class("system", "Annual") != tag_class("system", "Semester")
    assert len({tag_class("gender", g) for g in TAG_GENDERS}) == 3


def test_every_class_has_a_light_and_a_dark_colour():
    for cls in _all_classes():
        name = cls.split()[-1]
        assert re.search(r"^\." + re.escape(name) + r"\s*\{[^}]*--tag:", CSS, re.M), name
        assert re.search(r"^\.body--dark \." + re.escape(name) + r"\s*\{[^}]*--tag:", CSS, re.M), name


def _rgb(hex_colour):
    h = hex_colour.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def _luminance(rgb):
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a, b):
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _on(bg, rgba):
    """The tag background (rgba) laid over the card colour."""
    *rgb, alpha = rgba
    return [alpha * c / 255 + (1 - alpha) * b for c, b in zip(rgb, bg)]


def test_tag_text_is_readable_in_light_and_dark():
    light_card, dark_card = [1, 1, 1], _rgb("#1a1e23")
    rules = re.findall(r"^(\.body--dark )?\.app-tag--[\w-]+\s*\{\s*--tag:\s*(#[0-9a-f]{6});\s*"
                       r"--tag-bg:\s*rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", CSS, re.M)
    assert len(rules) == 22
    for dark, text, r, g, b, a in rules:
        card = dark_card if dark else light_card
        ratio = _contrast(_rgb(text), _on(card, (int(r), int(g), int(b), float(a))))
        assert ratio >= 4.5, (dark, text, round(ratio, 2))


def test_templates_page_and_issue_picker_use_the_same_classes():
    tags = template_tags("year - Temp - En - D - SBS.docx")
    chips = dict(tag_chips(tags))
    labels = tag_label_classes()
    for label in (tags["lang_ar"], tags["marks_ar"], tags["gender_ar"]):
        assert chips[label] == labels[label]
    src = open(os.path.join(ROOT, "nicegui_screens", "certificate_screen.py"), encoding="utf-8").read()
    assert "tag_label_classes()" in src and "app-tag-line" in src
    src = open(os.path.join(ROOT, "nicegui_screens", "settings", "templates.py"), encoding="utf-8").read()
    assert "tag_chips(tags)" in src
