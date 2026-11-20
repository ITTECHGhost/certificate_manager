"""Day-1 rules: unit ownership of holds, append-only steps, all-or-nothing saves."""
import pytest
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client

from registry import services
from registry.models import Hold, Request, RequestStep, Student

pytestmark = pytest.mark.django_db


def _user(username, group=None, staff=True):
    u = User.objects.create_user(username, password="pw-test-123", is_staff=staff)
    if group:
        u.groups.add(Group.objects.get(name=group))
    return u


@pytest.fixture
def student():
    return Student.objects.create(
        name_ar="طالب تجريبي", name_en="Test Student", department="قسم تجريبي",
        study_type="morning",
    )


@pytest.fixture
def legal_hold(student):
    return Hold.objects.create(student=student, unit="legal", note="قيد تجريبي",
                               created_by=_user("legal_owner", "legal"))


# --- groups -------------------------------------------------------------------

def test_three_unit_groups_exist():
    names = set(Group.objects.values_list("name", flat=True))
    assert {"student_affairs", "finance", "legal"} <= names


# --- hold ownership -----------------------------------------------------------

def test_finance_cannot_clear_legal_hold(legal_hold):
    finance = _user("fin", "finance")
    with pytest.raises(PermissionDenied):
        services.clear_hold(legal_hold, finance)
    legal_hold.refresh_from_db()
    assert legal_hold.is_open


def test_legal_can_clear_legal_hold(legal_hold):
    legal = _user("leg", "legal")
    services.clear_hold(legal_hold, legal)
    legal_hold.refresh_from_db()
    assert not legal_hold.is_open
    assert legal_hold.cleared_by == legal and legal_hold.cleared_at is not None


def test_student_affairs_sees_hold_but_cannot_change_it(legal_hold):
    sa = _user("sa", "student_affairs")
    assert services.can_view_hold(sa, legal_hold)
    assert not services.can_edit_hold(sa, legal_hold)
    with pytest.raises(PermissionDenied):
        services.clear_hold(legal_hold, sa)


def test_finance_cannot_change_legal_hold_through_admin(legal_hold):
    _user("fin2", "finance")
    c = Client()
    c.login(username="fin2", password="pw-test-123")
    r = c.post(f"/admin/registry/hold/{legal_hold.pk}/change/",
               {"student": legal_hold.student_id, "unit": "legal", "note": "تغيير"})
    assert r.status_code in (302, 403)  # redirected away or forbidden, never saved
    legal_hold.refresh_from_db()
    assert legal_hold.note == "قيد تجريبي"


def test_hold_cannot_be_hard_deleted(legal_hold):
    with pytest.raises(PermissionDenied):
        legal_hold.delete()
    assert Hold.all_objects.filter(pk=legal_hold.pk).exists()


# --- request steps are append-only --------------------------------------------

def test_request_step_cannot_be_edited_or_deleted(student):
    sa = _user("sa2", "student_affairs")
    req = Request.objects.create(student=student, title="طلب تجريبي",
                                 current_unit="student_affairs", created_by=sa)
    step = services.send_request(req, "finance", sa, ip="10.0.0.5", annotation="للتدقيق")
    step.annotation = "تعديل"
    with pytest.raises(PermissionDenied):
        step.save()
    with pytest.raises(PermissionDenied):
        step.delete()
    assert RequestStep.objects.get(pk=step.pk).annotation == "للتدقيق"
    assert step.from_unit == "student_affairs" and step.to_unit == "finance"
    assert step.ip == "10.0.0.5" and step.user == sa


# --- all or nothing -----------------------------------------------------------

def test_failed_send_writes_nothing(student):
    sa = _user("sa3", "student_affairs")
    req = Request.objects.create(student=student, title="طلب", current_unit="student_affairs",
                                 created_by=sa)
    with pytest.raises(ValidationError):
        services.send_request(req, "no_such_unit", sa, ip="10.0.0.5", annotation="x")
    assert RequestStep.objects.count() == 0
    req.refresh_from_db()
    assert req.current_unit == "student_affairs"


def test_settings_wrap_every_request_in_a_transaction(settings):
    assert settings.DATABASES["default"]["ATOMIC_REQUESTS"] is True
