"""Interface language: one Arabic→English table, Arabic by default, LTR in English."""
import pytest

from nicegui_ui import i18n
from nicegui_ui.i18n_table import EN


@pytest.fixture(autouse=True)
def _lang_file(tmp_path, monkeypatch):
    monkeypatch.setattr(i18n, "_config_path", lambda: tmp_path / "config" / "ui_language.json")
    i18n._state["lang"] = None
    i18n.translate.cache_clear()
    yield
    i18n._state["lang"] = None


def test_default_is_arabic_and_rtl():
    assert i18n.get_language() == "ar"
    assert i18n.is_rtl()
    assert i18n.t("الإعدادات") == "الإعدادات"


def test_english_is_stored_and_translates():
    i18n.set_language("en")
    i18n._state["lang"] = None           # read back from the file
    assert i18n.get_language() == "en" and not i18n.is_rtl()
    assert i18n.t("الإعدادات") == "Settings"


def test_templates_fill_values():
    assert i18n.translate("تعذر حفظ الطالب: timeout") == "Could not save the student: timeout"
    assert i18n.translate("الوثيقة رقم 965/26") == "Document number 965/26"


def test_unknown_and_non_arabic_text_is_unchanged():
    assert i18n.translate("abc 123") == "abc 123"
    assert i18n.translate("نص غير معروف إطلاقا") == "نص غير معروف إطلاقا"


def test_table_values_have_no_arabic_and_keep_placeholders():
    import re
    ar = re.compile(r"[\u0600-\u06FF]")
    for k, v in EN.items():
        assert not ar.search(v), k
        assert k.count("{}") == v.count("{}"), k


def test_props_translation_covers_options_and_columns():
    props = {"label": "الإعدادات", "options": [{"label": "الإعدادات", "value": 1}], "columns": [{"label": "الإعدادات", "name": "x"}]}
    out = i18n._translate_props(props)
    assert out["label"] == "Settings"
    assert out["options"][0]["label"] == "Settings"
    assert out["columns"][0]["label"] == "Settings"
    assert props["label"] == "الإعدادات"          # the element's own props are untouched
