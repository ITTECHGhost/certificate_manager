from utils.order_number import LRM, clean, ltr, normalize_order_number as n


def test_reversed_and_arabic_digits():
    for raw in ("3/12/20707", "٢٠٧٠٧/١٢/٣", "20707-12-3", "3 12 20707", "20707/12/3",
                "\u200f3/12/20707\u200e", r" 3\12\20707 ", "3.12.20707", "۲۰۷۰۷/۱۲/۳"):
        assert n(raw) == ("20707/12/3", False), raw


def test_reversed_whole_number():
    assert n("12/3/20707") == ("20707/3/12", False)
    assert n("20707/3") == ("20707/3", False)


def test_five_digits_in_middle_is_flagged():
    assert n("3/20707/12") == ("3/20707/12", True)


def test_needs_review():
    assert n("123/12/3") == ("123/12/3", True)            # no part of 4+ digits
    assert n("3/13/7580") == ("7580/13/3", False)         # older 4-digit orders
    assert n("20707/12345/3") == ("20707/12345/3", True)  # two of them
    assert n("abc") == ("abc", True)
    assert n("") == ("", False) and n(None) == ("", False)


def test_ltr():
    out = ltr("20707/12/3")
    assert out.startswith(LRM) and out.endswith(LRM) and clean(out) == "20707/12/3"
    assert ltr("") == ""


def test_server_copy_is_identical():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    assert (root / "utils/order_number.py").read_text(encoding="utf-8") == \
        (root / "certificate_manager_api/order_number.py").read_text(encoding="utf-8")
