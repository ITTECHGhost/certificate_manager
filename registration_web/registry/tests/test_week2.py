"""Week 2: per-unit inbox (no leaks), ID-card print, student search."""
import pytest
from django.contrib.auth.models import Group, User
from django.test import Client

from registry.models import Request, Student

pytestmark = pytest.mark.django_db


def _client(username, group=None, superuser=False):
    if superuser:
        u = User.objects.create_superuser(username, password="pw-test-123")
    else:
        u = User.objects.create_user(username, password="pw-test-123", is_staff=True)
        if group:
            u.groups.add(Group.objects.get(name=group))
    c = Client()
    c.force_login(u)
    return c


def _student(name, nid=""):
    return Student.objects.create(name_ar=name, national_id=nid, department="قسم",
                                  study_type="morning")


@pytest.fixture
def reqs():
    a = _student("علي حسن", "111")
    b = _student("علي كريم", "222")
    fin = Request.objects.create(student=a, title="طلب مالية", current_unit="finance")
    leg = Request.objects.create(student=b, title="طلب قانونية", current_unit="legal")
    done = Request.objects.create(student=a, title="منتهٍ", current_unit="finance",
                                  status="done")
    return fin, leg, done


def _ids(resp):
    return [r.pk for r in resp.context["page"].object_list]


def test_unit_sees_only_its_own_open_inbox(reqs):
    fin, leg, done = reqs
    resp = _client("f", "finance").get("/inbox/")
    assert resp.status_code == 200
    assert _ids(resp) == [fin.pk]


def test_inbox_newest_first(reqs):
    fin, _, _ = reqs
    newer = Request.objects.create(student=fin.student, title="أحدث", current_unit="finance")
    assert _ids(_client("f", "finance").get("/inbox/")) == [newer.pk, fin.pk]


@pytest.mark.parametrize("q", ["علي", "كريم", "222"])
def test_search_never_leaks_other_units(reqs, q):
    _, leg, _ = reqs
    ids = _ids(_client("f", "finance").get("/inbox/", {"q": q}))
    assert leg.pk not in ids


def test_search_by_national_id(reqs):
    fin, _, _ = reqs
    assert _ids(_client("f", "finance").get("/inbox/", {"q": "111"})) == [fin.pk]


def test_user_without_unit_gets_403(reqs):
    assert _client("nobody").get("/inbox/").status_code == 403


def test_superuser_sees_all_units(reqs):
    fin, leg, _ = reqs
    assert set(_ids(_client("root", superuser=True).get("/inbox/"))) == {fin.pk, leg.pk}


def test_inbox_paginated():
    s = _student("طالب")
    for i in range(30):
        Request.objects.create(student=s, title=f"ط{i}", current_unit="legal")
    c = _client("l", "legal")
    assert len(_ids(c.get("/inbox/"))) == 25
    assert len(_ids(c.get("/inbox/", {"page": 2}))) == 5


def test_id_card_student_affairs_only():
    s = _student("طالب البطاقة", "999")
    resp = _client("sa", "student_affairs").get(f"/students/{s.pk}/card/")
    assert resp.status_code == 200 and "طالب البطاقة" in resp.content.decode()
    assert _client("f", "finance").get(f"/students/{s.pk}/card/").status_code == 403


def test_admin_student_search_by_national_id():
    _student("أ", "123456")
    _student("ب", "777")
    resp = _client("root", superuser=True).get("/admin/registry/student/", {"q": "123456"})
    assert resp.context["cl"].result_count == 1
