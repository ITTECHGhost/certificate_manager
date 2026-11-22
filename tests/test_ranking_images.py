"""Scanned pages of an official ranking list (0012): JPEG only, temp -> rename after commit,
soft delete, admin or page:rankings only (server-checked)."""
import asyncio
import io
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "certificate_manager_api"))

import routers.ranking_images as ri  # noqa: E402

JPG = b"\xff\xd8\xff" + b"page-bytes" * 10
THUMB = b"\xff\xd8\xff" + b"thumb"
ADMIN = {"id": 1, "personnel_role": "admin", "is_active": 1}
USER = {"id": 7, "personnel_role": "user", "is_active": 1}


class _Cur:
    def __init__(self, conn):
        self.conn, self.lastrowid, self.rowcount = conn, 42, 1

    def execute(self, sql, params=None):
        self.conn.sql.append((sql, params))
        if self.conn.fail_insert and sql.lstrip().startswith("INSERT"):
            raise RuntimeError("boom")

    def fetchone(self):
        return self.conn.one.pop(0) if self.conn.one else None

    def fetchall(self):
        return self.conn.all.pop(0) if self.conn.all else []

    def close(self):
        pass


class _Conn:
    def __init__(self, one=(), all_=(), fail_insert=False):
        self.one, self.all, self.fail_insert = list(one), list(all_), fail_insert
        self.sql, self.commits, self.rollbacks = [], 0, 0

    def cursor(self, **k):
        return _Cur(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture(autouse=True)
def images_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ri, "IMAGES_DIR", tmp_path)
    return tmp_path


def _up(data, name="p.jpg"):
    return UploadFile(file=io.BytesIO(data), filename=name)


def _add(conn, personnel_id=1, data=JPG, thumb=THUMB):
    return asyncio.run(ri.add_image(5, _up(data), _up(thumb), "scan.pdf", personnel_id, conn))


def _writes(conn):
    return [s for s, _ in conn.sql if s.lstrip().startswith(("INSERT", "UPDATE", "DELETE"))]


def test_admin_upload_saves_row_then_final_files(images_dir):
    # admin check, list exists, duplicate check (none), next page_no
    conn = _Conn(one=[ADMIN, {"id": 5}, None, {"n": 1}])
    out = _add(conn)
    assert out["duplicate"] is False and conn.commits == 1
    sha = out["sha256"]
    assert (images_dir / "5" / f"{sha}.jpg").read_bytes() == JPG
    assert (images_dir / "5" / f"{sha}_t.jpg").read_bytes() == THUMB
    assert not list(images_dir.rglob("*.part"))


def test_granted_user_may_upload():
    conn = _Conn(one=[USER, {"id": 5}, None, {"n": 1}],
                 all_=[[{"permission_key": "page:rankings"}]])
    assert _add(conn, personnel_id=7)["duplicate"] is False


def test_user_without_grant_refused(images_dir):
    conn = _Conn(one=[USER], all_=[[]])
    with pytest.raises(HTTPException) as e:
        _add(conn, personnel_id=7)
    assert e.value.status_code == 403 and not _writes(conn)
    assert not [p for p in images_dir.rglob("*") if p.is_file()]


def test_no_user_refused():
    with pytest.raises(HTTPException) as e:
        _add(_Conn(), personnel_id=None)
    assert e.value.status_code == 403


def test_not_jpeg_refused(images_dir):
    conn = _Conn(one=[ADMIN])
    with pytest.raises(HTTPException) as e:
        _add(conn, data=b"%PDF-1.4 nope")
    assert e.value.status_code == 400 and not _writes(conn)


def test_too_large_refused(monkeypatch):
    monkeypatch.setattr(ri, "MAX_PAGE_BYTES", 10)
    with pytest.raises(HTTPException) as e:
        _add(_Conn(one=[ADMIN]))
    assert e.value.status_code == 413


def test_unknown_list_404():
    conn = _Conn(one=[ADMIN, None])
    with pytest.raises(HTTPException) as e:
        _add(conn)
    assert e.value.status_code == 404 and not _writes(conn)


def test_failed_insert_leaves_no_files(images_dir):
    conn = _Conn(one=[ADMIN, {"id": 5}, None, {"n": 1}], fail_insert=True)
    with pytest.raises(HTTPException):
        _add(conn)
    assert conn.rollbacks == 1 and conn.commits == 0
    assert not [p for p in images_dir.rglob("*") if p.is_file()]


def test_duplicate_page_not_added_again():
    conn = _Conn(one=[ADMIN, {"id": 5}, {"id": 9}])
    out = _add(conn)
    assert out == {"id": 9, "duplicate": True, "sha256": out["sha256"]}
    assert not _writes(conn)


def test_soft_delete_keeps_file(images_dir):
    sha = "a" * 64
    (images_dir / "5").mkdir()
    (images_dir / "5" / f"{sha}.jpg").write_bytes(JPG)
    conn = _Conn(one=[ADMIN])
    ri.delete_image(5, 9, personnel_id=1, conn=conn)
    (sql,) = _writes(conn)
    assert sql.startswith("UPDATE official_ranking_images SET deleted_at") and conn.commits == 1
    assert (images_dir / "5" / f"{sha}.jpg").exists()


def test_delete_without_grant_refused():
    conn = _Conn(one=[USER], all_=[[]])
    with pytest.raises(HTTPException) as e:
        ri.delete_image(5, 9, personnel_id=7, conn=conn)
    assert e.value.status_code == 403 and not _writes(conn)


def test_list_skips_deleted():
    conn = _Conn(all_=[[{"id": 1}]])
    assert ri.list_images(5, conn) == [{"id": 1}]
    assert "deleted_at IS NULL" in conn.sql[0][0]


def test_get_image_reads_file(images_dir):
    sha = "b" * 64
    (images_dir / "5").mkdir()
    (images_dir / "5" / f"{sha}.jpg").write_bytes(JPG)
    (images_dir / "5" / f"{sha}_t.jpg").write_bytes(THUMB)
    resp = ri.get_image(5, 9, thumb=True, conn=_Conn(one=[{"sha256": sha}]))
    assert resp.body == THUMB
    with pytest.raises(HTTPException) as e:
        ri.get_image(5, 10, conn=_Conn(one=[None]))
    assert e.value.status_code == 404


def test_migration_0012_and_rollback_exist():
    mig = (ROOT / "sql" / "migrations" / "0012_official_ranking_images.sql").read_text(encoding="utf-8")
    rb = (ROOT / "sql" / "fixes" / "rollback_0012_official_ranking_images.sql").read_text(encoding="utf-8")
    assert "official_ranking_images" in mig and "deleted_at" in mig
    assert "DROP TABLE IF EXISTS `official_ranking_images`" in rb
