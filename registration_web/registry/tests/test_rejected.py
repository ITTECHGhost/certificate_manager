"""«مرفوضة» list: rejected requests of the user's own unit (unit filter before search)."""
import pytest
from django.contrib.auth.models import User
from django.test import Client

from registry.models import Request, RequestStep
from registry.tests.test_week2 import _client, _ids, _student

pytestmark = pytest.mark.django_db


def _reject(req, reason="ناقص"):
    u = User.objects.create_user(f"rej{req.pk}", password="pw-test-123")
    RequestStep.objects.create(request=req, from_unit=req.current_unit,
                               to_unit=req.current_unit, action="reject",
                               annotation=reason, user=u)
    req.status = "rejected"
    req.save(update_fields=["status"])
    return req


@pytest.fixture
def rej():
    a = _student("علي حسن", "111")
    b = _student("علي كريم", "222")
    fin = _reject(Request.objects.create(student=a, title="مالية", current_unit="finance"))
    leg = _reject(Request.objects.create(student=b, title="قانونية", current_unit="legal"))
    Request.objects.create(student=a, title="مفتوح", current_unit="finance")
    return fin, leg


def test_unit_sees_only_its_own_rejected(rej):
    fin, _ = rej
    resp = _client("f", "finance").get("/rejected/")
    assert resp.status_code == 200
    assert _ids(resp) == [fin.pk]
    assert "ناقص" in resp.content.decode()


@pytest.mark.parametrize("q", ["علي", "كريم", "222"])
def test_search_never_leaks_other_units(rej, q):
    _, leg = rej
    assert leg.pk not in _ids(_client("f", "finance").get("/rejected/", {"q": q}))


def test_search_by_name_and_id(rej):
    fin, _ = rej
    c = _client("f", "finance")
    assert _ids(c.get("/rejected/", {"q": "111"})) == [fin.pk]
    assert _ids(c.get("/rejected/", {"q": "حسن"})) == [fin.pk]


def test_student_affairs_sees_all(rej):
    fin, leg = rej
    assert set(_ids(_client("sa", "student_affairs").get("/rejected/"))) == {fin.pk, leg.pk}


def test_newest_first_and_paginated():
    s = _student("طالب")
    reqs = [_reject(Request.objects.create(student=s, title=f"ط{i}", current_unit="legal"))
            for i in range(30)]
    c = _client("l", "legal")
    first = _ids(c.get("/rejected/"))
    assert len(first) == 25 and first[0] == reqs[-1].pk
    assert len(_ids(c.get("/rejected/", {"page": 2}))) == 5


def test_no_unit_403_and_anonymous_redirect(rej):
    assert _client("nobody").get("/rejected/").status_code == 403
    assert Client().get("/rejected/").status_code == 302


def test_inbox_links_to_rejected(rej):
    assert "/rejected/" in _client("f", "finance").get("/inbox/").content.decode()
