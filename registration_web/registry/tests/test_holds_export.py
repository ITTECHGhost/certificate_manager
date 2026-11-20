"""Day 5: Student Affairs sees all holds (read only); export for the university e-mail."""
import io

import pytest
from django.contrib.auth.models import Group, User
from django.test import Client
from django.urls import reverse
from openpyxl import load_workbook

from registry.models import Hold, Student

pytestmark = pytest.mark.django_db


def _client(username, group):
    u = User.objects.create_user(username, password="pw-test-123", is_staff=True)
    u.groups.add(Group.objects.get(name=group))
    c = Client()
    c.force_login(u)
    return u, c


@pytest.fixture
def student():
    s = Student.objects.create(name_ar="طالب أول", name_en="First", department="قسم",
                               study_type="morning")
    Hold.objects.create(student=s, unit="finance", note="قسط غير مدفوع")
    Hold.objects.create(student=s, unit="legal", note="تعهد ناقص")
    return s


def test_student_affairs_sees_all_holds_in_full(student):
    _, c = _client("sa", "student_affairs")
    r = c.get(reverse("student_holds", args=[student.pk]))
    assert r.status_code == 200
    body = r.content.decode()
    assert "قسط غير مدفوع" in body and "تعهد ناقص" in body
    assert 'name="hold"' not in body  # no clear button for SA


def test_student_affairs_cannot_clear_hold(student):
    _, c = _client("sa", "student_affairs")
    hold = student.holds.get(unit="finance")
    r = c.post(reverse("student_holds", args=[student.pk]), {"hold": hold.pk})
    assert r.status_code == 403
    hold.refresh_from_db()
    assert hold.is_open


def test_owning_unit_clears_only_its_hold(student):
    _, c = _client("fin", "finance")
    fin_hold = student.holds.get(unit="finance")
    legal_hold = student.holds.get(unit="legal")
    assert c.post(reverse("student_holds", args=[student.pk]),
                  {"hold": legal_hold.pk}).status_code == 403
    c.post(reverse("student_holds", args=[student.pk]), {"hold": fin_hold.pk})
    fin_hold.refresh_from_db()
    legal_hold.refresh_from_db()
    assert not fin_hold.is_open and legal_hold.is_open


def test_finance_cannot_view_other_units_holds_page(student):
    _, c = _client("fin", "finance")
    body = c.get(reverse("student_holds", args=[student.pk])).content.decode()
    assert "قسط غير مدفوع" in body and "تعهد ناقص" not in body


def test_export_contains_only_requested_students(student):
    other = Student.objects.create(name_ar="طالب آخر", department="قسم", study_type="morning")
    third = Student.objects.create(name_ar="طالب ثالث", department="قسم", study_type="morning")
    _, c = _client("sa", "student_affairs")
    r = c.get(reverse("student_export") + f"?ids={student.pk},{third.pk}")
    assert r.status_code == 200
    ws = load_workbook(io.BytesIO(r.content)).active
    names = [row[0] for row in ws.iter_rows(min_row=2, values_only=True)]
    assert sorted(names) == sorted(["طالب أول", "طالب ثالث"])
    assert "طالب آخر" not in names and other.pk


def test_export_only_for_student_affairs(student):
    _, c = _client("fin", "finance")
    assert c.get(reverse("student_export") + f"?ids={student.pk}").status_code == 403
