from utils.error_formatter import format_error_message, remember_error, recent_errors


def test_fk_1452_is_missing_parent():
    t, _ = format_error_message('400: {"detail":"1452 (23000): Cannot add or update a child row: a foreign key constraint fails"}')
    assert t == "السجل المرتبط غير موجود على الخادم"


def test_fk_1451_is_linked_records():
    t, _ = format_error_message("1451 (23000): Cannot delete or update a parent row: a foreign key constraint fails")
    assert t == "تعارض في البيانات المرتبطة"


def test_number_containing_code_is_not_fk():
    t, d = format_error_message("تعذر فتح الملف C:\\docs\\14512-26.docx")
    assert t == "تنبيه" and "14512" in d


def test_recent_errors_keep_raw_text():
    remember_error("1452 (23000): raw detail")
    assert "raw detail" in recent_errors[-1]
