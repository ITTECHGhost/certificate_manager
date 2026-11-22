"""Archive of issued documents (0013): drafts (Word) until archived; the first signed copy
archives the record (issue_date = today, drafts hidden) and locks it; replace = admin;
delete = admin or issued_certs:delete; temp -> rename after commit; soft delete only."""
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
DOCX = b"PK\x03\x04 word"
ADMIN = {"id": 1, "personnel_role": "admin", "is_active": 1}
USER = {"id": 7, "personnel_role": "user", "is_active": 1}
CERT = {"id": 3, "y": 2026, "certificate_number": "125/2026"}


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


def _add(conn, pid=1, data=PDF, name="scan.pdf", replace_id=None, kind="signed"):
    up = UploadFile(file=io.BytesIO(data), filename=name)
    return asyncio.run(idf.add_file(3, up, kind, pid, replace_id, conn))


def _sqls(conn):
    return [s for s, _ in _writes(conn)]


def _writes(conn):
    return [(s, p) for s, p in conn.sql if s.lstrip().startswith(("INSERT", "UPDATE", "DELETE"))]


def _files(d):
    return [p for p in d.rglob("*") if p.is_file()]


from datetime import date  # noqa: E402

YEAR = str(date.today().year)


# ── signed copy = archiving ───────────────────────────────────────────────
def test_first_signed_copy_archives_record(archive_dir):
    conn = _Conn(one=[ADMIN, CERT, None, None])
    out = _add(conn)
    assert out["archived"] is True and conn.commits == 1
    sqls = _sqls(conn)
    assert any("SET issue_date = CURDATE()" in s for s in sqls)
    assert any("kind = 'draft'" in s and "deleted_at = NOW()" in s for s in sqls)
    assert (archive_dir / YEAR / f"{out['sha256']}.pdf").read_bytes() == PDF
    assert not list(archive_dir.rglob("*.part"))


def test_png_kept_as_png(archive_dir):
    out = _add(_Conn(one=[ADMIN, CERT, None, None]), data=PNG, name="a.png")
    assert (archive_dir / YEAR / f"{out['sha256']}.png").exists()


def test_viewer_may_archive():
    conn = _Conn(one=[USER, CERT, None, None], all_=[[{"permission_key": "issued_certs:view"}]])
    assert _add(conn, pid=7)["archived"] is True


def test_no_grant_refused(archive_dir):
    conn = _Conn(one=[USER], all_=[[]])
    with pytest.raises(HTTPException) as e:
        _add(conn, pid=7)
    assert e.value.status_code == 403 and not _writes(conn) and not _files(archive_dir)


def test_no_user_refused():
    with pytest.raises(HTTPException) as e:
        _add(_Conn(), pid=None)
    assert e.value.status_code == 403


def test_signed_must_be_pdf_or_image():
    with pytest.raises(HTTPException) as e:
        _add(_Conn(one=[ADMIN]), data=DOCX, name="x.docx")
    assert e.value.status_code == 400


def test_bad_kind_refused():
    with pytest.raises(HTTPException) as e:
        _add(_Conn(one=[ADMIN]), kind="other")
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


def test_no_issued_number_refused(archive_dir):
    conn = _Conn(one=[ADMIN, {"id": 3, "y": 2026, "certificate_number": None}])
    with pytest.raises(HTTPException) as e:
        _add(conn)
    assert e.value.status_code == 409 and not _writes(conn) and not _files(archive_dir)


def test_second_signed_copy_needs_replace():
    conn = _Conn(one=[ADMIN, CERT, {"id": 9}])
    with pytest.raises(HTTPException) as e:
        _add(conn)
    assert e.value.status_code == 409 and not _writes(conn)


def test_duplicate_signed_not_added():
    conn = _Conn(one=[ADMIN, CERT, None, {"id": 9}])
    assert _add(conn)["duplicate"] is True and not _writes(conn)


def test_failed_insert_leaves_no_files(archive_dir):
    conn = _Conn(one=[ADMIN, CERT, None, None], fail_insert=True)
    with pytest.raises(HTTPException):
        _add(conn)
    assert conn.rollbacks == 1 and conn.commits == 0 and not _files(archive_dir)


# ── replace (admin only, history kept, date unchanged) ───────────────────
def test_replace_is_admin_only():
    conn = _Conn(one=[USER], all_=[[{"permission_key": "issued_certs:delete"}]])
    with pytest.raises(HTTPException) as e:
        _add(conn, pid=7, replace_id=9)
    assert e.value.status_code == 403 and not _writes(conn)


def test_replace_adds_row_with_supersedes_keeps_date():
    conn = _Conn(one=[ADMIN, CERT, {"id": 9}, None])
    out = _add(conn, replace_id=9)
    assert out["archived"] is False
    ((sql, params),) = _writes(conn)
    assert "supersedes_id" in sql and params[5] == 9


def test_replace_unknown_old_file_404():
    conn = _Conn(one=[ADMIN, CERT, None])
    with pytest.raises(HTTPException) as e:
        _add(conn, replace_id=99)
    assert e.value.status_code == 404 and not _writes(conn)


# ── drafts ───────────────────────────────────────────────────────────────
def test_draft_saved_without_number_sets_print_date(archive_dir):
    conn = _Conn(one=[USER, {"id": 3, "y": 2026, "certificate_number": None}, None, None],
                 all_=[[{"permission_key": "issued_certs:view"}]])
    out = _add(conn, pid=7, data=DOCX, name="d.docx", kind="draft")
    sqls = _sqls(conn)
    assert sqls[0].startswith("UPDATE issued_document_files SET deleted_at")   # older drafts hidden
    assert any("SET printed_at = NOW()" in s for s in sqls)
    assert not any("issue_date" in s for s in sqls)
    assert (archive_dir / "2026" / f"{out['sha256']}.docx").exists()


def test_draft_must_be_word():
    with pytest.raises(HTTPException) as e:
        _add(_Conn(one=[ADMIN]), kind="draft")
    assert e.value.status_code == 400


def test_same_draft_again_only_moves_print_date():
    conn = _Conn(one=[ADMIN, CERT, None, {"id": 4}])
    out = _add(conn, data=DOCX, kind="draft")
    assert out["duplicate"] is True
    assert _sqls(conn) == ["UPDATE issued_certificates SET printed_at = NOW() WHERE id = %s"]


def test_no_draft_after_archive():
    conn = _Conn(one=[ADMIN, CERT, {"id": 9}])
    with pytest.raises(HTTPException) as e:
        _add(conn, data=DOCX, kind="draft")
    assert e.value.status_code == 409 and not _writes(conn)


def test_draft_cannot_be_replace():
    with pytest.raises(HTTPException) as e:
        _add(_Conn(), data=DOCX, kind="draft", replace_id=4)
    assert e.value.status_code == 422


# ── delete / read ────────────────────────────────────────────────────────
def test_soft_delete_keeps_file():
    conn = _Conn(one=[ADMIN])
    idf.delete_file(3, 9, personnel_id=1, conn=conn)
    (sql,) = _sqls(conn)
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


def test_status_gives_print_date_and_archived():
    conn = _Conn(all_=[[{"certificate_id": 3, "printed_at": "2026-11-01 10:00", "archived": 1},
                        {"certificate_id": 4, "printed_at": None, "archived": 0}]])
    assert idf.status(conn) == [{"certificate_id": 3, "printed_at": "2026-11-01 10:00", "archived": True},
                                {"certificate_id": 4, "printed_at": None, "archived": False}]


def test_is_archived_false_before_migration():
    class _E(Exception):
        errno = 1146

    class _C(_Conn):
        def cursor(self, **k):
            c = _Cur(self)
            c.execute = lambda *a: (_ for _ in ()).throw(_E())
            return c
    assert idf.is_archived(_C(), 3) is False
    assert idf.is_archived(_Conn(one=[{"id": 1}]), 3) is True


def test_get_file_reads_with_type(archive_dir):
    sha = "c" * 64
    (archive_dir / "2026").mkdir()
    (archive_dir / "2026" / f"{sha}.pdf").write_bytes(PDF)
    resp = idf.get_file(3, 9, conn=_Conn(one=[{"file_name": f"{sha}.pdf", "doc_year": 2026}]))
    assert resp.body == PDF and resp.media_type == "application/pdf"
    with pytest.raises(HTTPException) as e:
        idf.get_file(3, 10, conn=_Conn(one=[None]))
    assert e.value.status_code == 404


# ── edit lock on the record itself ───────────────────────────────────────
def test_archived_record_cannot_be_edited():
    import routers.issued_certificates as ic
    conn = _Conn(one=[{"id": 9}])
    with pytest.raises(HTTPException) as e:
        ic.update_issued_certificate(3, ic.IssuedCertificatePayload(student_id=1), conn)
    assert e.value.status_code == 409 and not _writes(conn)


def test_migration_0013_and_rollback_exist():
    mig = (ROOT / "sql" / "migrations" / "0013_issued_doc_files.sql").read_text(encoding="utf-8")
    rb = (ROOT / "sql" / "fixes" / "rollback_0013_issued_doc_files.sql").read_text(encoding="utf-8")
    assert "issued_document_files" in mig and "supersedes_id" in mig and "printed_at" in mig
    assert "DROP TABLE IF EXISTS `issued_document_files`" in rb and "DROP COLUMN `printed_at`" in rb
