"""Issue screen: a 3-step wizard whose widgets still feed the unchanged generation code."""
import ast
import re
from pathlib import Path

from nicegui_ui.template_constants import get_template_label_ar

SRC = (Path(__file__).resolve().parents[1] / "nicegui_screens" / "certificate_screen.py").read_text(encoding="utf-8")
TREE = ast.parse(SRC)
CLS = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == "CertificateScreen")
METHODS = {f.name: f for f in CLS.body if isinstance(f, ast.FunctionDef | ast.AsyncFunctionDef)}


def _src(name: str) -> str:
    return ast.get_source_segment(SRC, METHODS[name])


def _self_attrs_assigned(func) -> set[str]:
    out = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                for sub in ast.walk(t):
                    if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == "self":
                        out.add(sub.attr)
    return out


def test_three_steps_in_order():
    assert '["الطالب", "الوثيقة", "المراجعة والإصدار"]' in SRC
    assert "UI.stepper(self.STEPS" in _src("build_ui")
    go = _src("_go_step")
    for view in ("view_student_info", "view_print_options", "view_review"):
        assert view in go


def test_step_one_lists_recent_students_by_default():
    recent = _src("_show_recent_students")
    assert "search_students_paginated" in recent and 'query=""' in recent
    assert "self._show_recent_students()" in _src("build_ui")
    # a short or empty search goes back to the recent list
    assert "self._show_recent_students()" in _src("perform_search")


def test_selecting_a_student_opens_the_document_step():
    assert "self._go_step(2)" in _src("select_student")


def test_every_widget_generation_reads_is_built():
    """generate_certificate is unchanged; every self.<widget> it reads must still exist."""
    gen = _src("generate_certificate")
    read = set(re.findall(r"self\.((?:sw|inp|to|cert|issue|template|grouping|rank)_?\w*)\.value", gen))
    assert read, "expected generate_certificate to read widget values"
    built = _self_attrs_assigned(METHODS["build_ui"])
    assert read <= built, f"missing widgets: {read - built}"


def test_review_has_one_primary_and_inline_duplicate_check():
    build = _src("build_ui")
    review_part = build[build.index("STEP 3"):]
    assert review_part.count("UI.primary_button(") == 1
    assert '"إصدار وطباعة"' in review_part
    assert "check_duplicate" in _src("_render_review")
    assert "self.btn_generate.disable()" in _src("_render_review")


def test_transcript_is_flat_table_rows():
    t = _src("_transcript_table")
    assert "UI.data_table(" in t
    assert "ui.grid(" not in _src("update_student_ui")


def test_template_picker_shows_arabic_names_not_files():
    # The picker shows the template name and a second line for the variant (no old part labels)
    assert "template_option_label" in _src("_format_template_options")
    from nicegui_ui.issue_helpers import template_option_label
    two = template_option_label("year - Temp - Ar - D - SBS.docx")
    assert two == "وثيقة تخرج — النظام السنوي\nعربي • بالدرجات"
    assert ".docx" not in two and "جدولان" not in two
    assert get_template_label_ar("year - Temp - Ar - D - SBS.docx") == "عربية • سنوي • جدولان متجاوران"
    label = get_template_label_ar("semester - Temp - En.docx")
    assert label == "إنكليزية • فصلي"
    assert ".docx" not in label


def test_print_dialog_has_no_emoji_or_truncation():
    dlg = _src("show_in_app_print_dialog")
    assert "truncate" not in dlg
    assert not re.search(r"[\U0001F300-\U0001FAFF]", dlg)
    assert dlg.count("UI.primary_button(") == 1
