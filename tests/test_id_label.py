from services.certificate_context import id_label


def test_iraqi_by_id():
    assert id_label({"nationality_id": 274}) == "الرقم الوطني"


def test_foreign_by_id():
    assert id_label({"nationality_id": 101}) == "رقم الجواز"


def test_by_name_when_no_id():
    assert id_label({"nationality_ar": "العراق"}) == "الرقم الوطني"
    assert id_label({"nationality_ar": "سوريا"}) == "رقم الجواز"


def test_english():
    assert id_label({"nationality_id": 274}, True) == "National ID No."
