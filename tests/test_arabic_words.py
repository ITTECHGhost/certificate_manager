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
