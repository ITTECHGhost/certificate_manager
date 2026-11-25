"""Pictures on a feedback note (0014): JPEG only, size limit, author or admin, file kept only
after the row is committed, one commit per upload."""
import asyncio
import io
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "certificate_manager_api"))

import routers.feedback_images as fi  # noqa: E402

JPG = b"\xff\xd8\xff" + b"pic" * 20
ADMIN = {"id": 1, "personnel_role": "admin", "is_active": 1}
AUTHOR = {"id": 7, "personnel_role": "user", "is_active": 1}
OTHER = {"id": 8, "personnel_role": "user", "is_active": 1}
NOTE = {"created_by": 7, "status": "new"}


class _Cur:
    def __init__(self, conn):
        self.conn, self.lastrowid, self.rowcount = conn, 42, 1

    def execute(self, sql, params=None):
        self.conn.sql.append(sql)
        if self.conn.fail_insert and sql.lstrip().startswith("INSERT"):
            raise RuntimeError("boom")

    def fetchone(self):
        return self.conn.one.pop(0) if self.conn.one else None

    def fetchall(self):
        return []

    def close(self):
        pass


class _Conn:
    def __init__(self, one=(), fail_insert=False):
        self.one, self.fail_insert = list(one), fail_insert
        self.sql, self.commits, self.rollbacks = [], 0, 0

    def cursor(self, **k):
        return _Cur(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture(autouse=True)
def images_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(fi, "IMAGES_DIR", tmp_path)
    return tmp_path


def _add(conn, pid=7, data=JPG):
    return asyncio.run(fi.add_image(3, UploadFile(file=io.BytesIO(data), filename="s.jpg"), "shot.png", pid, conn))


def _files(d):
    return [p for p in d.rglob("*") if p.is_file()]


def test_author_upload_saves_row_then_file(images_dir):
    conn = _Conn(one=[AUTHOR, NOTE, None, {"n": 0}])
    assert _add(conn)["duplicate"] is False and conn.commits == 1
    assert [p.suffix for p in _files(images_dir)] == [".jpg"]


def test_admin_may_upload_to_any_note():
    assert _add(_Conn(one=[ADMIN, NOTE, None, {"n": 0}]), pid=1)["duplicate"] is False


def test_other_user_refused(images_dir):
    conn = _Conn(one=[OTHER, NOTE])
    with pytest.raises(HTTPException) as e:
        _add(conn, pid=8)
    assert e.value.status_code == 403 and conn.commits == 0 and not _files(images_dir)


def test_not_jpeg_refused():
    with pytest.raises(HTTPException) as e:
        _add(_Conn(one=[AUTHOR, NOTE]), data=b"\x89PNG....")
    assert e.value.status_code == 400


def test_too_large_refused(monkeypatch):
    monkeypatch.setattr(fi, "MAX_IMAGE_BYTES", 10)
    with pytest.raises(HTTPException) as e:
        _add(_Conn(one=[AUTHOR, NOTE]))
    assert e.value.status_code == 413


def test_too_many_images_refused():
    with pytest.raises(HTTPException) as e:
        _add(_Conn(one=[AUTHOR, NOTE, None, {"n": fi.MAX_IMAGES_PER_NOTE}]))
    assert e.value.status_code == 409


def test_failed_insert_leaves_no_file(images_dir):
    conn = _Conn(one=[AUTHOR, NOTE, None, {"n": 0}], fail_insert=True)
    with pytest.raises(HTTPException):
        _add(conn)
    assert conn.rollbacks == 1 and conn.commits == 0 and not _files(images_dir)


def test_screenshot_png_becomes_jpeg():
    from PIL import Image
    from services.order_images import to_feedback_jpeg
    buf = io.BytesIO()
    Image.new("RGBA", (50, 30), (255, 0, 0, 128)).save(buf, "PNG")
    assert to_feedback_jpeg(buf.getvalue()).startswith(b"\xff\xd8\xff")


def test_migration_0014_and_rollback_exist():
    mig = (ROOT / "sql" / "migrations" / "0014_feedback_images.sql").read_text(encoding="utf-8")
    rb = (ROOT / "sql" / "fixes" / "rollback_0014_feedback_images.sql").read_text(encoding="utf-8")
    assert "feedback_images" in mig and "deleted_at" in mig
    assert "DROP TABLE IF EXISTS `feedback_images`" in rb


def test_feedback_button_in_top_bar_not_sidebar():
    src = (ROOT / "nicegui_screens" / "dashboard_screen.py").read_text(encoding="utf-8")
    assert '"الملاحظات", icon="feedback"' in src and 'ui.label("ملاحظات وشكاوى")' not in src


def test_gzipped_log_is_accepted_and_served_as_gzip(images_dir):
    """The user's program log (gzipped) rides on the same route, saved as .gz (2026-11-24)."""
    import gzip
    data = gzip.compress(b"2026-11-24 09:51:57 [WARNING] API refused ...")
    conn = _Conn(one=[AUTHOR, NOTE, None, {"n": 0}])
    assert _add(conn, data=data)["duplicate"] is False
    saved = _files(images_dir)
    assert [p.suffix for p in saved] == [".gz"]
    resp = fi.get_image(3, 42, 7, _Conn(one=[AUTHOR, NOTE, {"sha256": saved[0].stem, "file_name": saved[0].name}]))
    assert resp.media_type == "application/gzip" and gzip.decompress(resp.body).startswith(b"2026")
