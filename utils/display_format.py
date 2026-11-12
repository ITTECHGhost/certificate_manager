"""Small display helpers for numbers shown in lists and detail views."""


MAX_AVERAGE = 100.0


def average_is_valid(value) -> bool:
    """An average is a mark out of 100. Empty counts as valid (not entered yet)."""
    if value is None or str(value).strip() == "":
        return True
    try:
        return 0.0 <= float(value) <= MAX_AVERAGE
    except (TypeError, ValueError):
        return False


def format_average(value) -> str:
    """A student's average with exactly two decimals ("78.50"); a dash when missing.

    Display only: the stored value and what the templates receive are unchanged.
    """
    if value is None or str(value).strip() == "":
        return "—"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)
