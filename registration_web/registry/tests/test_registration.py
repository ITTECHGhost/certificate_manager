"""Day 3: registration form + document upload (all or nothing, files never public)."""
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from registry import uploads
from registry.models import Student, StudentDocument

pytestmark = pytest.mark.django_db

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100
JPG = b"\xff\xd8\xff\xe0" + b"0" * 100
PDF = b"%PDF-1.4\n" + b"0" * 100

STUDENT = {
    "name_ar": "طالب تجريبي", "name_en": "Test Student", "mother_name": "أم تجريبية",
    "birth_date": "2005-01-02", "birth_place": "مدينة", "gender": "male",
    "national_id": "000000000000", "phone": "07700000000", "address": "عنوان تجريبي",
    "school_name": "إعدادية تجريبية", "graduation_year": "2024", "average": "88.50",
    "department": "قسم تجريبي", "study_type": "morning",
}


def _user(username, group=None):
    u = User.objects.create_user(username, password="pw-test-123", is_staff=True)
    if group:
        u.groups.add(Group.objects.get(name=group))
    return u


def _client(user):
    c = Client()
    c.login(username=user.username, password="pw-test-123")
    return c


def _files():
    return [
        ("id_card", SimpleUploadedFile("id.jpg", JPG, "image/jpeg")),
        ("certificate", SimpleUploadedFile("cert.pdf", PDF, "application/pdf")),
        ("photo", SimpleUploadedFile("photo.png", PNG, "image/png")),
    ]


def _media_files():
    root = Path(settings.MEDIA_ROOT)
    return {p for p in root.rglob("*") if p.is_file()} if root.exists() else set()


# --- all or nothing ------------------------------------------------------------

def test_student_with_three_documents_saved_together(django_capture_on_commit_callbacks):
    sa = _user("sa", "student_affairs")
    before = _media_files()
    with django_capture_on_commit_callbacks(execute=True):
        student = uploads.register_student(STUDENT, _files(), sa)
    docs = list(StudentDocument.objects.filter(student=student))
    assert len(docs) == 3 and all(d.created_by == sa for d in docs)
    for d in docs:
        assert Path(d.file.path).is_file()
        assert len(d.sha256) == 64
    new = _media_files() - before
    assert len(new) == 3 and not any(p.suffix == ".part" for p in new)


def test_bad_third_file_saves_nothing(django_capture_on_commit_callbacks):
    sa = _user("sa", "student_affairs")
    files = _files()
    files[2] = ("photo", SimpleUploadedFile("virus.exe", b"MZ" + b"0" * 50,
                                            "application/octet-stream"))
    before = _media_files()
    with pytest.raises(ValidationError):
        with django_capture_on_commit_callbacks(execute=True):
            uploads.register_student(STUDENT, files, sa)
    assert Student.objects.count() == 0 and StudentDocument.objects.count() == 0
    assert _media_files() == before


def test_db_failure_after_temp_files_leaves_no_files(monkeypatch,
                                                      django_capture_on_commit_callbacks):
    sa = _user("sa", "student_affairs")
    before = _media_files()

    def boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(StudentDocument, "save", boom)
    with pytest.raises(RuntimeError):
        with django_capture_on_commit_callbacks(execute=True):
            uploads.register_student(STUDENT, _files(), sa)
    assert Student.objects.count() == 0
    assert _media_files() == before


# --- server-side checks ----------------------------------------------------------

def test_wrong_type_rejected():
    with pytest.raises(ValidationError):
        uploads.check_file(SimpleUploadedFile("a.pdf", b"not a pdf", "application/pdf"))


def test_too_big_rejected():
    big = SimpleUploadedFile("a.png", PNG + b"0" * uploads.MAX_FILE_BYTES, "image/png")
    with pytest.raises(ValidationError):
        uploads.check_file(big)


def test_bad_form_data_rejected():
    sa = _user("sa", "student_affairs")
    with pytest.raises(ValidationError):
        uploads.register_student({**STUDENT, "name_ar": ""}, _files(), sa)
    assert Student.objects.count() == 0


# --- the page and who may open files ----------------------------------------------

def test_register_page_saves_student(django_capture_on_commit_callbacks):
    sa = _user("sa", "student_affairs")
    data = {**STUDENT, "doc_id_card": SimpleUploadedFile("id.jpg", JPG, "image/jpeg")}
    with django_capture_on_commit_callbacks(execute=True):
        r = _client(sa).post("/register/", data)
    assert r.status_code == 302
    assert StudentDocument.objects.count() == 1


def test_register_page_closed_to_other_units():
    fin = _user("fin", "finance")
    assert _client(fin).get("/register/").status_code == 403
    assert Client().get("/register/").status_code == 302  # to login


@pytest.fixture
def saved_doc(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        student = uploads.register_student(STUDENT, _files(), _user("owner", "student_affairs"))
    return student.documents.first()


def test_anonymous_gets_no_file(saved_doc):
    r = Client().get(f"/documents/{saved_doc.pk}/")
    assert r.status_code == 302 and "/login/" in r["Location"]


def test_other_unit_gets_no_file(saved_doc):
    assert _client(_user("leg", "legal")).get(f"/documents/{saved_doc.pk}/").status_code == 403


def test_student_affairs_gets_file(saved_doc):
    r = _client(_user("sa2", "student_affairs")).get(f"/documents/{saved_doc.pk}/")
    assert r.status_code == 200
    r.close()


def test_media_folder_not_served_directly(saved_doc):
    r = _client(_user("sa3", "student_affairs")).get("/media/" + saved_doc.file.name)
    assert r.status_code == 404
