"""Day 4: request status + send to unit with annotation; every step logged."""
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


def test_saved_step_cannot_be_edited_or_deleted(req):
    sa = _user("sa", "student_affairs")
    step = services.send_request(req, "finance", sa, ip="10.0.0.1", annotation="للتدقيق")
    step.annotation = "تغيير"
    with pytest.raises(PermissionDenied):
        step.save()
    with pytest.raises(PermissionDenied):
        step.delete()
    assert RequestStep.objects.get(pk=step.pk).annotation == "للتدقيق"


def test_unit_cannot_send_request_it_does_not_hold(req):
    fin = _user("fin", "finance")
    with pytest.raises(PermissionDenied):
        services.send_request(req, "legal", fin, ip="10.0.0.2")
    req.refresh_from_db()
    assert req.current_unit == "student_affairs"
    assert not RequestStep.objects.exists()


def test_unknown_unit_logs_nothing(req):
    sa = _user("sa", "student_affairs")
    with pytest.raises(ValidationError):
        services.send_request(req, "nowhere", sa)
    assert not RequestStep.objects.exists()


def test_request_passes_three_units_and_is_accepted(req):
    sa, fin, leg = (_user("sa", "student_affairs"), _user("fin", "finance"),
                    _user("leg", "legal"))
    assert req.stage_label == "عند شؤون الطلبة"
    services.send_request(req, "finance", sa, ip="10.0.0.1", annotation="أ")
    req.refresh_from_db()
    assert req.stage_label == "عند المالية"
    services.send_request(req, "legal", fin, ip="10.0.0.2", annotation="ب")
    req.refresh_from_db()
    assert req.stage_label == "عند القانونية"
    services.accept_request(req, leg, ip="10.0.0.3", annotation="ج")
    req.refresh_from_db()
    assert req.status == "done" and req.stage_label == "مقبول"
    steps = list(req.steps.all())
    assert [s.user for s in steps] == [sa, fin, leg]
    assert [s.ip for s in steps] == ["10.0.0.1", "10.0.0.2", "10.0.0.3"]
    assert all(s.created_at for s in steps)
    with pytest.raises(ValidationError):  # closed: no more moves
        services.send_request(req, "finance", leg)


def test_unit_cannot_accept_request_it_does_not_hold(req):
    with pytest.raises(PermissionDenied):
        services.accept_request(req, _user("leg", "legal"))
    req.refresh_from_db()
    assert req.status == "open"


def test_view_send_logs_ip_and_blocks_non_holder(req):
    url = reverse("request_detail", args=[req.pk])
    c = Client()
    c.force_login(_user("fin", "finance"))
    assert c.get(url).status_code == 200  # can view
    assert c.post(url, {"action": "send", "to_unit": "legal"}).status_code == 403
    c.force_login(_user("sa", "student_affairs"))
    r = c.post(url, {"action": "send", "to_unit": "finance", "annotation": "للمالية"},
               REMOTE_ADDR="10.9.9.9")
    assert r.status_code == 302
    step = req.steps.get()
    assert step.ip == "10.9.9.9" and step.annotation == "للمالية"
