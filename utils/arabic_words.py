# =============================================================================
# utils/arabic_words.py — numbers in Arabic words for certificates
#   number_words("85.26")  -> "خمسة وثمانون فاصلة ستة وعشرون"
#   ordinal_words(3)       -> "الثالث"
# =============================================================================

ONES = ["صفر", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة", "سبعة", "ثمانية", "تسعة"]
TEENS = {10: "عشرة", 11: "أحد عشر", 12: "اثنا عشر", 13: "ثلاثة عشر", 14: "أربعة عشر", 15: "خمسة عشر",
         16: "ستة عشر", 17: "سبعة عشر", 18: "ثمانية عشر", 19: "تسعة عشر"}
TENS = {2: "عشرون", 3: "ثلاثون", 4: "أربعون", 5: "خمسون", 6: "ستون", 7: "سبعون", 8: "ثمانون", 9: "تسعون"}
HUNDREDS = {1: "مئة", 2: "مئتان", 3: "ثلاثمئة", 4: "أربعمئة", 5: "خمسمئة", 6: "ستمئة", 7: "سبعمئة",
            8: "ثمانمئة", 9: "تسعمئة"}

ORD_ONES = {1: "الأول", 2: "الثاني", 3: "الثالث", 4: "الرابع", 5: "الخامس", 6: "السادس", 7: "السابع",
            8: "الثامن", 9: "التاسع", 10: "العاشر"}
ORD_UNITS_COMPOUND = {1: "الحادي", 2: "الثاني", 3: "الثالث", 4: "الرابع", 5: "الخامس", 6: "السادس",
                      7: "السابع", 8: "الثامن", 9: "التاسع"}
ORD_HUNDREDS = {1: "المئة", 2: "المئتين", 3: "الثلاثمئة", 4: "الأربعمئة", 5: "الخمسمئة", 6: "الستمئة",
                7: "السبعمئة", 8: "الثمانمئة", 9: "التسعمئة"}


def _below_100(n: int) -> str:
    if n < 10:
        return ONES[n]
    if n < 20:
        return TEENS[n]
    t, u = divmod(n, 10)
    return TENS[t] if u == 0 else f"{ONES[u]} و{TENS[t]}"


def int_words(n: int) -> str:
    if n < 0:
        return "سالب " + int_words(-n)
    if n < 100:
        return _below_100(n)
    if n < 1000:
        h, r = divmod(n, 100)
        return HUNDREDS[h] if r == 0 else f"{HUNDREDS[h]} و{_below_100(r)}"
    if n < 1_000_000:
        th, r = divmod(n, 1000)
        head = {1: "ألف", 2: "ألفان"}.get(th) or (f"{int_words(th)} آلاف" if th <= 10 else f"{int_words(th)} ألف")
        return head if r == 0 else f"{head} و{int_words(r)}"
    return str(n)


def _to_ascii_digits(text: str) -> str:
    return str(text).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789."))


def number_words(value) -> str:
    """'85.26' -> 'خمسة وثمانون فاصلة ستة وعشرون'. Empty text for empty or invalid input."""
    text = _to_ascii_digits(str(value if value is not None else "")).strip().replace(",", ".")
    if not text:
        return ""
    try:
        float(text)
    except ValueError:
        return ""
    whole, _, frac = text.partition(".")
    words = int_words(int(whole or "0"))
    frac = frac.rstrip("0")
    if frac:
        lead = "صفر " * (len(frac) - len(frac.lstrip("0")))
        words += f" فاصلة {lead}{int_words(int(frac))}"
    return words


def ordinal_words(value) -> str:
    """1 -> 'الأول', 21 -> 'الحادي والعشرون', 105 -> 'الخامس بعد المئة'."""
    try:
        n = int(float(_to_ascii_digits(str(value)).strip()))
    except (TypeError, ValueError):
        return ""
    if n <= 0:
        return ""
    if n > 999:
        return int_words(n)
    h, r = divmod(n, 100)
    if r == 0:
        return ORD_HUNDREDS[h]
    if r <= 10:
        part = ORD_ONES[r]
    elif r < 20:
        part = f"{ORD_UNITS_COMPOUND[r - 10]} عشر"
    else:
        t, u = divmod(r, 10)
        tens = "ال" + TENS[t]
        part = tens if u == 0 else f"{ORD_UNITS_COMPOUND[u]} و{tens}"
    return part if h == 0 else f"{part} بعد {ORD_HUNDREDS[h]}"


YEARS_WORDS = {1: "سنة واحدة", 2: "سنتان", 3: "ثلاث سنوات", 4: "أربع سنوات", 5: "خمس سنوات",
               6: "ست سنوات", 7: "سبع سنوات"}


def study_duration_words(calculation_weights: str = "", degree_level=None) -> str:
    """Normal study length. The study system's weights have one part per year (10:20:30:40 = 4 years);
    without them, the usual length for the degree."""
    parts = [p for p in str(calculation_weights or "").replace(",", ":").split(":") if p.strip()]
    years = len(parts) if 1 <= len(parts) <= 7 else {1: 4, 2: 1, 3: 2, 4: 3}.get(_int(degree_level), 0)
    return YEARS_WORDS.get(years, "")


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0
