"""Graduation orders: the count label, and the student form's order-date default and derived year."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORDERS = (ROOT / "nicegui_screens" / "graduation_orders_screen.py").read_text(encoding="utf-8")
FORM = (ROOT / "nicegui_ui" / "student_components.py").read_text(encoding="utf-8")


def test_count_label_renamed():
    assert "عدد الطلاب في أمر التخرج" in ORDERS
    assert "عدد الطلاب (حسب الوثيقة)" not in ORDERS


def test_order_date_becomes_the_default_graduation_date():
    assert "self.order_id.on_value_change(_on_order_picked)" in FORM
    assert "self.grad_date.value = odate" in FORM


def test_graduation_year_is_derived_not_saved():
    assert 'UI.text_input("سنة التخرج")' in FORM
    assert "backward=academic_year_from_date" in FORM
    payload = FORM[FORM.index("payload = {"):FORM.index("try:", FORM.index("payload = {"))]
    assert "graduation_year" not in payload
