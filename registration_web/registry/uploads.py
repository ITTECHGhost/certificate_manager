"""Register a student with documents, all or nothing (rules.md):
temp file -> rows in one transaction -> rename only after commit; any failure deletes the temps."""
import hashlib
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .forms import StudentForm
from .models import Student, StudentDocument

MAX_FILE_BYTES = 10 * 1024 * 1024
# extension -> accepted leading bytes (checked on the server, not trusted from the browser)
ALLOWED = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".pdf": (b"%PDF-",),
}
KIND_CODES = {k for k, _ in StudentDocument.KINDS}


def check_file(f):
    """Raise ValidationError unless f is a JPG/PNG/PDF of at most MAX_FILE_BYTES."""
    ext = Path(f.name).suffix.lower()
    if ext not in ALLOWED:
        raise ValidationError(f"نوع الملف غير مسموح: {f.name} (المسموح JPG أو PNG أو PDF).")
    if f.size > MAX_FILE_BYTES:
        raise ValidationError(f"الملف أكبر من 10 ميغابايت: {f.name}")
    f.seek(0)
    head = f.read(8)
    f.seek(0)
    if not any(head.startswith(sig) for sig in ALLOWED[ext]):
        raise ValidationError(f"محتوى الملف لا يطابق نوعه: {f.name}")


def _write_temp(f):
    """Write the upload to a .part file; return (temp path, final relative name, sha256)."""
    now = timezone.now()
    rel_dir = Path("student_docs") / f"{now:%Y}" / f"{now:%m}"
    abs_dir = Path(settings.MEDIA_ROOT) / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{Path(f.name).suffix.lower()}"
    tmp = abs_dir / (name + ".part")
    h = hashlib.sha256()
    with open(tmp, "wb") as out:
        for chunk in f.chunks():
            h.update(chunk)
            out.write(chunk)
    return tmp, (rel_dir / name).as_posix(), h.hexdigest()


def _finish(temps):
    for tmp, rel in temps:
        tmp.replace(Path(settings.MEDIA_ROOT) / rel)


def _discard(temps):
    for tmp, _ in temps:
        tmp.unlink(missing_ok=True)


def register_student(data, files, user):
    """data: form fields; files: [(kind, UploadedFile)]. Returns the saved Student."""
    form = StudentForm(data)
    if not form.is_valid():
        raise ValidationError(form.errors)
    for kind, f in files:
        if kind not in KIND_CODES:
            raise ValidationError(f"نوع وثيقة غير معروف: {kind}")
        check_file(f)

    temps = []
    try:
        with transaction.atomic():
            student = form.save(commit=False)
            student.created_by = user
            student.save()
            for kind, f in files:
                tmp, rel, digest = _write_temp(f)
                temps.append((tmp, rel))
                doc = StudentDocument(student=student, kind=kind, sha256=digest,
                                      created_by=user)
                doc.file.name = rel
                doc.save()
            # outer request transaction (ATOMIC_REQUESTS): rename only when it commits
            # If the outer transaction later rolls back, the .part files stay orphaned
            # (never linked to a row); they are harmless and can be swept by age.
            transaction.on_commit(lambda: _finish(temps))
    except BaseException:
        _discard(temps)
        raise
    return student
