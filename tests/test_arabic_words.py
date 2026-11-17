from utils.arabic_words import number_words, ordinal_words, study_duration_words


def test_number_words():
    assert number_words("85.26") == "خمسة وثمانون فاصلة ستة وعشرون"
    assert number_words(90) == "تسعون"
    assert number_words("٧٥.٥") == "خمسة وسبعون فاصلة خمسة"
    assert number_words("70.05") == "سبعون فاصلة صفر خمسة"
    assert number_words("") == "" and number_words("abc") == ""


def test_ordinals():
    assert ordinal_words(1) == "الأول"
    assert ordinal_words(11) == "الحادي عشر"
    assert ordinal_words(21) == "الحادي والعشرون"
    assert ordinal_words(40) == "الأربعون"
    assert ordinal_words(105) == "الخامس بعد المئة"
    assert ordinal_words("") == ""


def test_duration():
    assert study_duration_words("10:20:30:40") == "أربع سنوات"
    assert study_duration_words("", 1) == "أربع سنوات"
    assert study_duration_words("10:20:30:40:50") == "خمس سنوات"


def test_permille_words():
    from utils.arabic_words import permille_words
    assert permille_words("75.385") == "خمسة وسبعون وثلاثمئة وخمسة وثمانون بالألف"
    assert permille_words("٧٥.٣٨٠") == "خمسة وسبعون وثلاثمئة وثمانون بالألف"
    assert permille_words("80.5") == "ثمانون وخمسمئة بالألف"
    assert permille_words("70.005") == "سبعون وخمسة بالألف"
    assert permille_words("90.000") == "تسعون"
    assert permille_words("") == "" and permille_words("—") == ""
