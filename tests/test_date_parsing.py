import pytest

from utils.date_parsing import parse_date, format_academic_year, academic_year_start, academic_year_from_date


@pytest.mark.parametrize("raw", [
    "2025-10-13", "2025/10/13", "2025.10.13", "2025 10 13", "2025 - 10 - 13",
    "13-10-2025", "13/10/2025", "13.10.2025", "13 10 2025",
    "20251013", "13102025", "٢٠٢٥-١٠-١٣",
])
def test_parse_date_accepts_every_separator_and_order(raw):
    assert parse_date(raw) == "2025-10-13"


def test_parse_date_pads_single_digits():
    assert parse_date("3/1/2024") == "2024-01-03"
    assert parse_date("2024.1.3") == "2024-01-03"


@pytest.mark.parametrize("raw", ["2025-13-01", "31/02/2025", "abc", "2025-10", "1234567", "99999999", "10-13-25"])
def test_parse_date_rejects_invalid(raw):
    assert parse_date(raw) is None


def test_parse_date_empty():
    assert parse_date("") == "" and parse_date(None) == "" and parse_date("  ") == ""


@pytest.mark.parametrize("raw", ["2025", "2025-2026", "2025/2026", "2025 2026", "25/26", "2025-26", " 2025 / 2026 "])
def test_academic_year_forms(raw):
    assert format_academic_year(raw) == "2025/2026"


@pytest.mark.parametrize("raw", ["2025/2027", "abc", "202", "2025/2026/2027", "26/25"])
def test_academic_year_rejects(raw):
    assert format_academic_year(raw) is None


def test_academic_year_helpers():
    assert format_academic_year("") == ""
    assert academic_year_start("2025/2026") == 2025
    assert academic_year_start("x") is None
    assert academic_year_from_date("2025-07-01") == "2025/2026"
    assert academic_year_from_date("") == ""
