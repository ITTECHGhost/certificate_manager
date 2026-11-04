"""Small display helpers for numbers shown in lists and detail views."""


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
