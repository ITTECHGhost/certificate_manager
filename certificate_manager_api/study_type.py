"""Study type (صباحي / مسائي / موازي) — one spelling everywhere: morning | evening | parallel.

Kept identical to the program's utils/study_type.py (tests/test_study_type.py checks it):
the API is installed on its own, without the program's code.
"""

STUDY_TYPES = ("morning", "evening", "parallel")
STUDY_TYPE_LABELS_AR = {"morning": "صباحي", "evening": "مسائي", "parallel": "موازي"}

_ALIASES = {
    "morning": "morning", "day": "morning", "صباحي": "morning", "الصباحي": "morning",
    "صباحية": "morning", "الصباحية": "morning",
    "evening": "evening", "night": "evening", "مسائي": "evening", "المسائي": "evening",
    "مسائية": "evening", "المسائية": "evening",
    "parallel": "parallel", "other": "parallel", "موازي": "parallel", "الموازي": "parallel",
    "موازية": "parallel", "الموازية": "parallel",
}


def normalize_study_type(value) -> str | None:
    """'Evening', 'مسائي', ' evening ' -> 'evening'. Empty or unknown -> None (the caller
    keeps the saved value or uses its default)."""
    text = str(value or "").strip().lower()
    if not text:
        return None
    return _ALIASES.get(text)
