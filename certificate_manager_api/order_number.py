# =============================================================================
# utils/order_number.py — One form for university order numbers: 20707/12/3
#
# People type the number inside Arabic text, so it arrives as "3/12/20707",
# "٢٠٧٠٧/١٢/٣", "20707-12-3" or with invisible direction marks. The main part
# (the only one with 4 or more digits, normally 5)
# goes first, joined by "/". When it was typed last the number was read
# right-to-left, so all parts are reversed (3/12/20707 -> 20707/12/3).
# With no such part, more than one, or one in the middle, nothing is
# guessed: the cleaned value is returned and flagged for review.
# =============================================================================

from __future__ import annotations

import re
from typing import NamedTuple

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_BIDI_MARKS = re.compile("[\u200e\u200f\u202a-\u202e\u2066-\u2069\u061c]")
_SEPARATORS = re.compile(r"[\s/\\.-]+")

LRM = "\u200e"  # left-to-right mark


class OrderNumber(NamedTuple):
    value: str          # what to save
    needs_review: bool  # True: not normalised, a person should check it


def clean(raw: object) -> str:
    """Western digits, no direction marks, trimmed."""
    return _BIDI_MARKS.sub("", str(raw or "")).translate(_DIGITS).strip()


def normalize_order_number(raw: object) -> OrderNumber:
    text = clean(raw)
    if not text:
        return OrderNumber("", False)
    parts = [p for p in _SEPARATORS.split(text) if p]
    # The main part: the one with 4+ digits (usually 5, older orders have 4: 7580/13/3)
    five = [i for i, p in enumerate(parts) if len(p) >= 4 and p.isdigit()]
    if len(five) != 1:
        return OrderNumber(text, True)
    if five[0] == len(parts) - 1:
        # 5-digit part last: the whole number was read right-to-left (3/12/20707)
        parts.reverse()
    elif five[0] != 0:
        return OrderNumber(text, True)  # in the middle: don't guess
    return OrderNumber("/".join(parts), False)


def ltr(text: object) -> str:
    """The number kept left-to-right inside Arabic text (Word, PDF, plain text).

    A left-to-right mark on each side of every "/" holds the parts in order. Checked in
    Word: the isolate marks (U+2066..U+2069) print as boxes and embeddings (U+202A)
    still reverse the number; only these marks print 20707/12/3.
    """
    s = str(text or "")
    if not s:
        return ""
    return LRM + s.replace("/", f"{LRM}/{LRM}") + LRM
