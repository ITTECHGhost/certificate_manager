"""Dashboard stat cards: Students first, then issued certificates, courses and personnel."""
from nicegui_ui.ui_theme import STAT_CARDS


def test_stat_card_order():
    assert [card["count_key"] for card in STAT_CARDS] == [
        "total_students", "total_issued", "total_courses", "total_personnel",
    ]


def test_stat_cards_are_arabic_only():
    assert all("label_en" not in card for card in STAT_CARDS)
