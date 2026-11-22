"""Archive files of issued documents (0013): PDF/JPG/PNG, temp -> rename after commit,
replace = new row with supersedes_id, soft delete. Upload: admin or issued_certs:view;
replace/delete: admin or issued_certs:delete (server-checked)."""
import asyncio
import io
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "certificate_manager_api"))

import routers.issued_doc_files as idf  # noqa: E402

PDF = b"%PDF-1.4 signed scan"
PNG = b"\x89PNG\r\n\x1a\n data"
ADMIN = {"id": 1, "personnel_role": "admin", "is_active": 1}
USER = {"id": 7, "personnel_role": "user", "is_active": 1}
CERT = {"id": 3, "y": 2026}


class _Cur:
    def __init__(self, conn):
        self.conn, self.lastrowid, self.rowcount = conn, 42, conn.rowcount

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
    def __init__(self, one=(), all_=(), fail_insert=False, rowcount=1):
        self.one, self.all, self.fail_insert, self.rowcount = list(one), list(all_), fail_insert, rowcount
        self.sql, self.commits, self.rollbacks = [], 0, 0

    def cursor(self, **k):
        return _Cur(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture(autouse=True)
def archive_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(idf, "ARCHIVE_DIR", tmp_path)
    return tmp_path


def _add(conn, pid=1, data=PDF, name="scan.pdf", replace_id=None):
    up = UploadFile(file=io.BytesIO(data), filename=name)
    return asyncio.run(idf.add_file(3, up, "signed", pid, replace_id, conn))


def _writes(conn):
    return [(s, p) for s, p in conn.sql if s.lstrip().startswith(("INSERT", "UPDATE", "DELETE"))]


def _files(d):
    return [p for p in d.rglob("*") if p.is_file()]


def test_admin_upload_pdf_goes_to_year_folder(archive_dir):
    conn = _Conn(one=[ADMIN, CERT, None])
    out = _add(conn)
    assert out["duplicate"] is False and conn.commits == 1
    assert (archive_dir / "2026" / f"{out['sha256']}.pdf").read_bytes() == PDF
    assert not list(archive_dir.rglob("*.part"))


def test_png_kept_as_png(archive_dir):
    out = _add(_Conn(one=[ADMIN, CERT, None]), data=PNG, name="a.png")
    assert (archive_dir / "2026" / f"{out['sha256']}.png").exists()


def test_viewer_may_upload_new():
    conn = _Conn(one=[USER, CERT, None], all_=[[{"permission_key": "issued_certs:view"}]])
    assert _add(conn, pid=7)["duplicate"] is False


def test_no_grant_refused(archive_dir):
    conn = _Conn(one=[USER], all_=[[]])
    with pytest.raises(HTTPException) as e:
        _add(conn, pid=7)
    assert e.value.status_code == 403 and not _writes(conn) and not _files(archive_dir)


def test_no_user_refused():
    with pytest.raises(HTTPException) as e:
        _add(_Conn(), pid=None)
    assert e.value.status_code == 403


def test_bad_type_refused():
    with pytest.raises(HTTPException) as e:
        _add(_Conn(one=[ADMIN]), data=b"MZ exe", name="x.exe")
    assert e.value.status_code == 400


def test_bad_kind_refused():
    up = UploadFile(file=io.BytesIO(PDF), filename="a.pdf")
    with pytest.raises(HTTPException) as e:
        asyncio.run(idf.add_file(3, up, "other", 1, None, _Conn(one=[ADMIN])))
    assert e.value.status_code == 422


def test_too_large_refused(monkeypatch):
    monkeypatch.setattr(idf, "MAX_FILE_BYTES", 5)
    with pytest.raises(HTTPException) as e:
        _add(_Conn(one=[ADMIN]))
    assert e.value.status_code == 413


def test_unknown_certificate_404():
    conn = _Conn(one=[ADMIN, None])
    with pytest.raises(HTTPException) as e:
        _add(conn)
    assert e.value.status_code == 404 and not _writes(conn)


def test_duplicate_not_added():
    conn = _Conn(one=[ADMIN, CERT, {"id": 9}])
    assert _add(conn)["duplicate"] is True and not _writes(conn)


def test_failed_insert_leaves_no_files(archive_dir):
    conn = _Conn(one=[ADMIN, CERT, None], fail_insert=True)
    with pytest.raises(HTTPException):
        _add(conn)
    assert conn.rollbacks == 1 and not _files(archive_dir)


def test_replace_needs_delete_grant():
    conn = _Conn(one=[USER], all_=[[{"permission_key": "issued_certs:view"}]])
    with pytest.raises(HTTPException) as e:
        _add(conn, pid=7, replace_id=9)
    assert e.value.status_code == 403 and not _writes(conn)


def test_replace_adds_row_with_supersedes():
    conn = _Conn(one=[ADMIN, CERT, None, {"id": 9}])
    _add(conn, replace_id=9)
    ((sql, params),) = _writes(conn)
    assert "supersedes_id" in sql and params[5] == 9


def test_replace_unknown_old_file_404():
    conn = _Conn(one=[ADMIN, CERT, None, None])
    with pytest.raises(HTTPException) as e:
        _add(conn, replace_id=99)
    assert e.value.status_code == 404 and not _writes(conn)


def test_soft_delete_keeps_file(archive_dir):
    conn = _Conn(one=[ADMIN])
    idf.delete_file(3, 9, personnel_id=1, conn=conn)
    ((sql, _),) = _writes(conn)
    assert sql.startswith("UPDATE issued_document_files SET deleted_at") and conn.commits == 1


def test_delete_needs_delete_grant():
    conn = _Conn(one=[USER], all_=[[{"permission_key": "issued_certs:view"}]])
    with pytest.raises(HTTPException) as e:
        idf.delete_file(3, 9, personnel_id=7, conn=conn)
    assert e.value.status_code == 403 and not _writes(conn)


def test_delete_missing_404():
    with pytest.raises(HTTPException) as e:
        idf.delete_file(3, 9, personnel_id=1, conn=_Conn(one=[ADMIN], rowcount=0))
    assert e.value.status_code == 404


def test_list_and_signed_ids_skip_deleted():
    conn = _Conn(all_=[[{"id": 1}], [{"certificate_id": 3}, {"certificate_id": 5}]])
    assert idf.list_files(3, conn) == [{"id": 1}]
    assert idf.signed_ids(conn) == [3, 5]
    assert all("deleted_at IS NULL" in s for s, _ in conn.sql)


def test_get_file_reads_with_type(archive_dir):
    sha = "c" * 64
    (archive_dir / "2026").mkdir()
    (archive_dir / "2026" / f"{sha}.pdf").write_bytes(PDF)
    resp = idf.get_file(3, 9, conn=_Conn(one=[{"file_name": f"{sha}.pdf", "doc_year": 2026}]))
    assert resp.body == PDF and resp.media_type == "application/pdf"
    with pytest.raises(HTTPException) as e:
        idf.get_file(3, 10, conn=_Conn(one=[None]))
    assert e.value.status_code == 404


def test_migration_0013_and_rollback_exist():
    mig = (ROOT / "sql" / "migrations" / "0013_issued_doc_files.sql").read_text(encoding="utf-8")
    rb = (ROOT / "sql" / "fixes" / "rollback_0013_issued_doc_files.sql").read_text(encoding="utf-8")
    assert "issued_document_files" in mig and "supersedes_id" in mig and "deleted_at" in mig
    assert "DROP TABLE IF EXISTS `issued_document_files`" in rb
