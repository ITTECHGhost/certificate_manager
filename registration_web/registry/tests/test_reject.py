"""Reject: holding unit only, annotation required, one transaction."""
from unittest import mock

import pytest
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client
from django.urls import reverse

from registry import services
from registry.models import Request, RequestStep, Student

pytestmark = pytest.mark.django_db


def _user(username, group):
    u = User.objects.create_user(username, password="pw-test-123", is_staff=True)
    u.groups.add(Group.objects.get(name=group))
    return u


@pytest.fixture
def req():
    s = Student.objects.create(name_ar="طالب تجريبي", name_en="Test", department="قسم",
                               study_type="morning")
    return Request.objects.create(student=s, title="تسجيل", current_unit="student_affairs")


def test_holding_unit_rejects_with_note(req):
    sa = _user("sa", "student_affairs")
    step = services.reject_request(req, sa, ip="10.0.0.1", annotation="وثيقة ناقصة")
    req.refresh_from_db()
    assert req.status == "rejected" and req.stage_label == "مرفوض"
    assert step.action == "reject" and step.annotation == "وثيقة ناقصة"
    assert step.from_unit == step.to_unit == "student_affairs"


def test_other_unit_cannot_reject(req):
    fin = _user("fin", "finance")
    with pytest.raises(PermissionDenied):
        services.reject_request(req, fin, annotation="لا")
    req.refresh_from_db()
    assert req.status == "open" and not RequestStep.objects.exists()


@pytest.mark.parametrize("note", ["", "   "])
def test_reject_needs_annotation(req, note):
    sa = _user("sa", "student_affairs")
    with pytest.raises(ValidationError):
        services.reject_request(req, sa, annotation=note)
    req.refresh_from_db()
    assert req.status == "open" and not RequestStep.objects.exists()


def test_closed_request_cannot_be_rejected(req):
    sa = _user("sa", "student_affairs")
    services.accept_request(req, sa)
    with pytest.raises(ValidationError):
        services.reject_request(req, sa, annotation="متأخر")
    req.refresh_from_db()
    assert req.status == "done"


def test_rejected_request_cannot_move(req):
    sa = _user("sa", "student_affairs")
    services.reject_request(req, sa, annotation="مرفوض")
    with pytest.raises(ValidationError):
        services.send_request(req, "finance", sa)
    with pytest.raises(ValidationError):
        services.accept_request(req, sa)


def test_reject_all_or_nothing(req):
    sa = _user("sa", "student_affairs")
    with mock.patch.object(Request, "save", side_effect=RuntimeError("disk")):
        with pytest.raises(RuntimeError):
            services.reject_request(req, sa, annotation="سبب")
    req.refresh_from_db()
    assert req.status == "open" and not RequestStep.objects.exists()


def test_reject_via_page(req):
    sa = _user("sa", "student_affairs")
    c = Client()
    c.force_login(sa)
    url = reverse("request_detail", args=[req.pk])
    assert "رفض الطلب" in c.get(url).content.decode()
    c.post(url, {"action": "reject", "annotation": ""})
    req.refresh_from_db()
    assert req.status == "open"
    c.post(url, {"action": "reject", "annotation": "نقص"})
    req.refresh_from_db()
    assert req.status == "rejected"


def test_reject_via_page_other_unit_403(req):
    fin = _user("fin", "finance")
    c = Client()
    c.force_login(fin)
    r = c.post(reverse("request_detail", args=[req.pk]),
               {"action": "reject", "annotation": "x"})
    assert r.status_code == 403
    req.refresh_from_db()
    assert req.status == "open"
