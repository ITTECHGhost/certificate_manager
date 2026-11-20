"""Signed-copy archive on accepted requests: same file checks, temp -> rename on commit,
soft delete only, holding unit or Student Affairs only (server-checked)."""
import os
import time

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

from registry import uploads
from registry.models import Request, SignedCopy
from registry.tests.test_week2 import _client, _student

pytestmark = pytest.mark.django_db

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


def _png(name="s.png", data=PNG):
    return SimpleUploadedFile(name, data, content_type="image/png")


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def done():
    return Request.objects.create(student=_student("علي", "111"), title="مقبول",
                                  current_unit="finance", status="done")


@pytest.fixture
def commit(django_capture_on_commit_callbacks):
    """Run on_commit callbacks (the rename) as a real commit would."""
    return lambda: django_capture_on_commit_callbacks(execute=True)


def test_holding_unit_uploads_and_file_renamed(done, media, commit):
    c = _client("f", "finance")
    with commit():
        resp = c.post(f"/requests/{done.pk}/signed/", {"file": _png(), "note": "موقعة"})
    assert resp.status_code == 302
    sc = SignedCopy.objects.get()
    assert sc.request == done and sc.note == "موقعة" and len(sc.sha256) == 64
    assert (media / sc.file.name).is_file()
    assert not list(media.rglob("*.part"))


def test_student_affairs_may_upload(done):
    c = _client("sa", "student_affairs")
    assert c.post(f"/requests/{done.pk}/signed/", {"file": _png()}).status_code == 302
    assert SignedCopy.objects.count() == 1


def test_other_unit_forbidden(done):
    c = _client("l", "legal")
    assert c.post(f"/requests/{done.pk}/signed/", {"file": _png()}).status_code == 403
    assert SignedCopy.objects.count() == 0


def test_only_accepted_requests(done):
    from django.contrib.auth.models import User
    u = User.objects.create_superuser("root", password="pw-test-123")
    done.status = "open"
    done.save()
    with pytest.raises(ValidationError):
        uploads.add_signed_copy(done, _png(), u)


@pytest.mark.parametrize("f", [_png("x.exe"), _png("x.png", b"not a png at all")])
def test_bad_file_refused(done, f, media):
    c = _client("f", "finance")
    c.post(f"/requests/{done.pk}/signed/", {"file": f})
    assert SignedCopy.objects.count() == 0
    assert not [p for p in media.rglob("*") if p.is_file()]


def test_too_big_refused(done, monkeypatch):
    monkeypatch.setattr(uploads, "MAX_FILE_BYTES", 10)
    from django.contrib.auth.models import User
    u = User.objects.create_superuser("root", password="pw-test-123")
    with pytest.raises(ValidationError):
        uploads.add_signed_copy(done, _png(), u)


def test_rollback_leaves_no_final_file(done, media):
    from django.contrib.auth.models import User
    u = User.objects.create_superuser("root", password="pw-test-123")
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            uploads.add_signed_copy(done, _png(), u)
            raise RuntimeError("boom")
    assert SignedCopy.all_objects.count() == 0
    assert not [p for p in media.rglob("*") if p.is_file() and not p.name.endswith(".part")]


def test_soft_delete_keeps_row_and_file(done, media, commit):
    c = _client("f", "finance")
    with commit():
        c.post(f"/requests/{done.pk}/signed/", {"file": _png()})
    sc = SignedCopy.objects.get()
    assert _client("l", "legal").post(f"/signed/{sc.pk}/delete/").status_code == 403
    assert c.post(f"/signed/{sc.pk}/delete/").status_code == 302
    assert SignedCopy.objects.count() == 0
    assert SignedCopy.all_objects.get().deleted_at is not None
    assert (media / sc.file.name).is_file()
    with pytest.raises(PermissionDenied):
        sc.delete()


def test_file_view_checked(done, commit):
    c = _client("f", "finance")
    with commit():
        c.post(f"/requests/{done.pk}/signed/", {"file": _png()})
    sc = SignedCopy.objects.get()
    assert c.get(f"/signed/{sc.pk}/").status_code == 200
    assert _client("l", "legal").get(f"/signed/{sc.pk}/").status_code == 403


def test_request_page_lists_live_copies(done):
    c = _client("f", "finance")
    c.post(f"/requests/{done.pk}/signed/", {"file": _png(), "note": "نسخة-أولى"})
    page = c.get(f"/requests/{done.pk}/").content.decode()
    assert "النسخ الموقعة" in page and "نسخة-أولى" in page
    SignedCopy.objects.get().soft_delete(None)
    assert "نسخة-أولى" not in c.get(f"/requests/{done.pk}/").content.decode()


def test_sweep_covers_signed_copies(media):
    p = media / "signed_copies" / "2026" / "11" / "a.pdf.part"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"x")
    t = time.time() - 30 * 3600
    os.utime(p, (t, t))
    assert uploads.sweep_orphan_parts(max_age_hours=24) == (1, 1)
    assert not p.exists()
