"""Archive files of «سجل الوثائق الصادرة» (migration 0013).

Two kinds (user decisions 2026-11-22):
- draft  : the editable Word file, saved at every print while the record is NOT archived. A new
           draft hides the older ones and sets issued_certificates.printed_at = NOW().
- signed : the FINAL printed, signed, stamped copy (PDF/JPG/PNG); needs the issued number.
           The first signed copy ARCHIVES the record in one transaction: issue_date = today,
           drafts hidden. An archived record is final: no new draft, no edit (409).
           Replacing a signed copy (admin only) adds a row with supersedes_id; history is kept.
Files: issue_archive\\<year>\\<sha>.<ext>, written as .part, renamed after commit. Soft delete only.
Rights (until per-unit roles in 0008): draft / first signed copy = admin or issued_certs:view;
delete = admin or issued_certs:delete; replace = admin. Trusts the client personnel_id (known gap).
"""
import hashlib
import logging
import os
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from deps import get_db

logger = logging.getLogger("api.issued_doc_files")
router = APIRouter(prefix="/api/issued-doc-files", tags=["issued-doc-files"])

MAX_FILE_BYTES = 20 * 1024 * 1024
API_DIR = Path(__file__).resolve().parents[1]
ARCHIVE_DIR = Path("C:/AppServ/issue_archive") if os.path.isdir("C:/AppServ") else API_DIR / "issue_archive"
KINDS = ("signed", "draft")
VIEW, MANAGE, ADMIN = "issued_certs:view", "issued_certs:delete", None
_TYPES = {
    "signed": ((b"%PDF", "pdf"), (b"\xff\xd8\xff", "jpg"), (b"\x89PNG", "png")),
    "draft": ((b"PK\x03\x04", "docx"),),
}
_MEDIA = {"pdf": "application/pdf", "jpg": "image/jpeg", "png": "image/png",
          "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def _require(conn, personnel_id: Optional[int], key: Optional[str]) -> None:
    """key None = admin only."""
    if not personnel_id:
        raise HTTPException(403, "A signed-in user is required")
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT id, personnel_role, is_active FROM personnel WHERE id = %s", (personnel_id,))
        user = cur.fetchone()
        if not user or not user.get("is_active"):
            raise HTTPException(403, "Account not found or disabled")
        if str(user.get("personnel_role") or "").lower() == "admin":
            return
        if key is None:
            raise HTTPException(403, "Admins only")
        cur.execute("SELECT permission_key FROM personnel_permissions "
                    "WHERE personnel_id = %s AND is_granted = 1", (personnel_id,))
        granted = {r["permission_key"] for r in cur.fetchall()}
    finally:
        cur.close()
    if key not in granted:
        raise HTTPException(403, "No permission for the documents archive")


def _archived(cur, cert_id: int) -> bool:
    cur.execute("SELECT id FROM issued_document_files WHERE certificate_id = %s AND kind = 'signed' "
                "AND deleted_at IS NULL LIMIT 1", (cert_id,))
    return bool(cur.fetchone())


def is_archived(conn, cert_id: int) -> bool:
    """For other routers (edit lock). False before migration 0013 ran (table missing)."""
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        return _archived(cur, cert_id)
    except Exception as exc:
        if getattr(exc, "errno", None) == 1146:   # table doesn't exist yet
            return False
        raise
    finally:
        cur.close()


@router.get("/signed-ids")
def signed_ids(conn=Depends(get_db)):
    """Certificate ids that are archived (have a signed copy)."""
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT DISTINCT certificate_id FROM issued_document_files "
                    "WHERE kind = 'signed' AND deleted_at IS NULL")
        return [int(r["certificate_id"]) for r in cur.fetchall()]
    finally:
        cur.close()


@router.get("/status")
def status(conn=Depends(get_db)):
    """Print date and archived flag of every record (for the two lists)."""
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT c.id AS certificate_id, DATE_FORMAT(c.printed_at, '%Y-%m-%d %H:%i') AS printed_at, "
                    "EXISTS(SELECT 1 FROM issued_document_files f WHERE f.certificate_id = c.id "
                    "AND f.kind = 'signed' AND f.deleted_at IS NULL) AS archived "
                    "FROM issued_certificates c")
        return [{"certificate_id": int(r["certificate_id"]), "printed_at": r.get("printed_at"),
                 "archived": bool(r.get("archived"))} for r in cur.fetchall()]
    finally:
        cur.close()


@router.get("/{cert_id}")
def list_files(cert_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT f.id, f.kind, f.file_name, f.doc_year, f.supersedes_id, f.source_name, "
                    "DATE_FORMAT(f.created_at, '%Y-%m-%d %H:%i') AS created_at, "
                    "COALESCE(p.name_ar, '') AS created_by_name FROM issued_document_files f "
                    "LEFT JOIN personnel p ON p.id = f.created_by "
                    "WHERE f.certificate_id = %s AND f.deleted_at IS NULL ORDER BY f.id DESC", (cert_id,))
        return cur.fetchall()
    finally:
        cur.close()


@router.get("/{cert_id}/{file_id}")
def get_file(cert_id: int, file_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT file_name, doc_year FROM issued_document_files WHERE id = %s "
                    "AND certificate_id = %s AND deleted_at IS NULL", (file_id, cert_id))
        row = cur.fetchone()
    finally:
        cur.close()
    if not row:
        raise HTTPException(404, "File not found")
    path = ARCHIVE_DIR / str(int(row["doc_year"])) / row["file_name"]
    if not path.exists():
        raise HTTPException(404, "File missing on the server")
    ext = path.suffix.lstrip(".").lower()
    return Response(content=path.read_bytes(), media_type=_MEDIA.get(ext, "application/octet-stream"))


@router.post("/{cert_id}")
async def add_file(cert_id: int, file: UploadFile = File(...), kind: str = Form("signed"),
                   personnel_id: Optional[int] = Form(None), replace_id: Optional[int] = Form(None),
                   conn=Depends(get_db)):
    if kind not in KINDS:
        raise HTTPException(422, "Unknown file kind")
    if replace_id and kind != "signed":
        raise HTTPException(422, "Only a signed copy can be replaced")
    _require(conn, personnel_id, ADMIN if replace_id else VIEW)
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File too large")
    ext = next((e for magic, e in _TYPES[kind] if data.startswith(magic)), None)
    if not ext:
        raise HTTPException(400, "Wrong file type for this kind")
    sha = hashlib.sha256(data).hexdigest()
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT id, YEAR(issue_date) AS y, certificate_number FROM issued_certificates "
                    "WHERE id = %s", (cert_id,))
        cert = cur.fetchone()
        if not cert:
            raise HTTPException(404, "Issued document not found")
        if kind == "signed" and not str(cert.get("certificate_number") or "").strip():
            raise HTTPException(409, "The document has no issued number yet")
        archiving = False
        if replace_id:
            cur.execute("SELECT id FROM issued_document_files WHERE id = %s AND certificate_id = %s "
                        "AND kind = 'signed' AND deleted_at IS NULL", (replace_id, cert_id))
            if not cur.fetchone():
                raise HTTPException(404, "The file to replace was not found")
        elif _archived(cur, cert_id):
            raise HTTPException(409, "The document is archived (final)")
        else:
            archiving = kind == "signed"
        cur.execute("SELECT id FROM issued_document_files WHERE certificate_id = %s AND kind = %s "
                    "AND sha256 = %s AND deleted_at IS NULL", (cert_id, kind, sha))
        dup = cur.fetchone()
        if dup and kind == "signed":
            return {"id": dup["id"], "duplicate": True, "sha256": sha}
        reprint = bool(dup)   # same draft printed again: only the print date moves
        year = date.today().year if archiving else (int(cert.get("y") or 0) or date.today().year)
        final = ARCHIVE_DIR / str(year) / f"{sha}.{ext}"
        tmp = final.with_name(final.name + ".part")
        new_id = dup["id"] if dup else None
        try:
            if not reprint:
                final.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_bytes(data)
                if kind == "draft":
                    cur.execute("UPDATE issued_document_files SET deleted_at = NOW(), deleted_by = %s "
                                "WHERE certificate_id = %s AND kind = 'draft' AND deleted_at IS NULL",
                                (personnel_id, cert_id))
                cur.execute("INSERT INTO issued_document_files (certificate_id, kind, sha256, file_name, "
                            "doc_year, supersedes_id, source_name, created_by) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (cert_id, kind, sha, final.name, year, replace_id,
                             (file.filename or "")[:255] or None, personnel_id))
                new_id = cur.lastrowid
            if kind == "draft":
                cur.execute("UPDATE issued_certificates SET printed_at = NOW() WHERE id = %s", (cert_id,))
            if archiving:
                cur.execute("UPDATE issued_certificates SET issue_date = CURDATE() WHERE id = %s", (cert_id,))
                cur.execute("UPDATE issued_document_files SET deleted_at = NOW(), deleted_by = %s "
                            "WHERE certificate_id = %s AND kind = 'draft' AND deleted_at IS NULL",
                            (personnel_id, cert_id))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            tmp.unlink(missing_ok=True)
            logger.error("archive file save failed: %s", exc)
            raise HTTPException(500, "Could not save the file")
        if reprint:
            return {"id": new_id, "duplicate": True, "sha256": sha, "archived": False}
        os.replace(tmp, final)
        return {"id": new_id, "duplicate": False, "sha256": sha, "archived": archiving}
    finally:
        cur.close()


@router.delete("/{cert_id}/{file_id}")
def delete_file(cert_id: int, file_id: int, personnel_id: Optional[int] = None, conn=Depends(get_db)):
    """Soft delete: the row is hidden, the file stays on disk."""
    _require(conn, personnel_id, MANAGE)
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("UPDATE issued_document_files SET deleted_at = NOW(), deleted_by = %s "
                    "WHERE id = %s AND certificate_id = %s AND deleted_at IS NULL",
                    (personnel_id, file_id, cert_id))
        changed = cur.rowcount
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("archive file delete failed: %s", exc)
        raise HTTPException(500, "Could not delete the file")
    finally:
        cur.close()
    if not changed:
        raise HTTPException(404, "File not found")
    return {"ok": True}
