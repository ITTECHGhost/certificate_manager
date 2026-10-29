"""Characterization tests for the certificate text helpers.

Expected values are what the functions returned before they moved to
services/certificate_context.py (checked by eye). Each case runs against the
new module and against the old import path in nicegui_screens.certificate_screen.
"""
import importlib

import pytest

LRM = chr(0x200E)


def ar(s: str) -> str:
    """ASCII digits -> Eastern Arabic digits (U+0660..U+0669)."""
    return "".join(chr(0x0660 + int(c)) if c.isdigit() else c for c in s)


@pytest.fixture(params=["services.certificate_context", "nicegui_screens.certificate_screen"])
def mod(request):
    return importlib.import_module(request.param)


@pytest.mark.parametrize("args, expected", [
    ((None,), ""),
    (("",), ""),
    ((2021,), ar("2021")),
    ((3.0,), ar("3.0")),
    (("2021-09-15",), ar("2021-09-15")),
    (("12", True), "12"),
])
def test_to_arabic_num(mod, args, expected):
    assert mod.to_arabic_num(*args) == expected


@pytest.mark.parametrize("args, expected", [
    ((None,), ""),
    (("",), ""),
    ((20210915,), LRM + ar("20210915") + LRM),
    (("2021-09-15",), LRM + ar("2021/09/15") + LRM),
    (("2021-20-2",), LRM + ar("2021/02/20") + LRM),
    (("2021/9/5", True), LRM + "2021/09/05" + LRM),
    (("15/09/2021",), LRM + ar("15/09/2021") + LRM),
])
def test_format_date_rtl(mod, args, expected):
    assert mod.format_date_rtl(*args) == expected


@pytest.mark.parametrize("args, expected", [
    ((None,), ""),
    (("",), ""),
    ((2016,), ar("2016")),
    (("2017-2016",), LRM + ar("2016-2017") + LRM),
    (("2016 - 2017", True), LRM + "2016-2017" + LRM),
    (("2016",), ar("2016")),
])
def test_format_academic_year_ltr(mod, args, expected):
    assert mod.format_academic_year_ltr(*args) == expected


@pytest.mark.parametrize("args, expected", [
    ((None,), 1),
    (("",), 1),
    ((3,), 3),
    ((2.7,), 2),
    (("Stage 2",), 2),
    (("المرحلة 4",), 4),
    (("abc",), 1),
    (("abc", 5), 5),
    ((None, 7), 7),
])
def test_parse_stage_num(mod, args, expected):
    assert mod.parse_stage_num(*args) == expected


MOVED = {
    "services.certificate_context": [
        "parse_stage_num", "safe_int_val", "consolidate_courses_for_certificate", "consolidate_course_history",
        "to_arabic_num", "format_date_rtl", "format_academic_year_ltr", "get_subj_display", "build_certificate_context",
    ],
    "services.office_automation": [
        "generate_pdf_from_docx", "convert_docx_to_html", "get_installed_printers", "get_default_printer",
        "print_file_to_printer",
    ],
}


@pytest.mark.parametrize("module, name", [(m, n) for m, names in MOVED.items() for n in names])
def test_certificate_screen_reexports_the_moved_function(module, name):
    screen = importlib.import_module("nicegui_screens.certificate_screen")
    assert getattr(screen, name) is getattr(importlib.import_module(module), name)
