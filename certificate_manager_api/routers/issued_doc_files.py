"""Archive files of «سجل الوثائق الصادرة» (migration 0013).

Only the FINAL document is archived: printed, signed, stamped, with its issued number and
date (issue_date is NOT NULL; an upload without certificate_number is refused, 409).

Files on disk: issue_archive\\<year>\\<sha256>.<pdf|jpg|png>, written as .part and renamed only
after the row is committed. Replace = a new row with supersedes_id (old versions stay).
Delete = soft delete (the file stays).
Rights (until per-unit roles in 0008): upload new = admin or issued_certs:view;
replace/delete = admin or issued_certs:delete. NOTE: trusts the personnel_id the client sends
(known gap, docs/PLAN_archive_and_next.md).
"""
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from deps import get_db

logger = logging.getLogger("api.issued_doc_files")
router = APIRouter(prefix="/api/issued-doc-files", tags=["issued-doc-files"])

MAX_FILE_BYTES = 20 * 1024 * 1024
API_DIR = Path(__file__).resolve().parents[1]
ARCHIVE_DIR = Path("C:/AppServ/issue_archive") if os.path.isdir("C:/AppServ") else API_DIR / "issue_archive"
KINDS = ("signed",)   # only the final signed+stamped document is archived
VIEW, MANAGE = "issued_certs:view", "issued_certs:delete"
_TYPES = ((b"%PDF", "pdf", "application/pdf"), (b"\xff\xd8\xff", "jpg", "image/jpeg"),
          (b"\x89PNG", "png", "image/png"))
_MEDIA = {ext: media for _, ext, media in _TYPES}


def _require(conn, personnel_id: Optional[int], key: str) -> None:
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
        cur.execute("SELECT permission_key FROM personnel_permissions "
                    "WHERE personnel_id = %s AND is_granted = 1", (personnel_id,))
        granted = {r["permission_key"] for r in cur.fetchall()}
    finally:
        cur.close()
    if key not in granted:
        raise HTTPException(403, "No permission for the documents archive")


@router.get("/signed-ids")
def signed_ids(conn=Depends(get_db)):
    """Certificate ids that have at least one signed scan (for the list filter)."""
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT DISTINCT certificate_id FROM issued_document_files "
                    "WHERE kind = 'signed' AND deleted_at IS NULL")
        return [int(r["certificate_id"]) for r in cur.fetchall()]
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
    _require(conn, personnel_id, MANAGE if replace_id else VIEW)
    if kind not in KINDS:
        raise HTTPException(422, "Unknown file kind")
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File too large")
    ext = next((e for magic, e, _ in _TYPES if data.startswith(magic)), None)
    if not ext:
        raise HTTPException(400, "Only PDF, JPG or PNG files are accepted")
    sha = hashlib.sha256(data).hexdigest()
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT id, YEAR(issue_date) AS y, certificate_number FROM issued_certificates WHERE id = %s", (cert_id,))
        cert = cur.fetchone()
        if not cert:
            raise HTTPException(404, "Issued document not found")
        if not str(cert.get("certificate_number") or "").strip():
            raise HTTPException(409, "The document has no issued number yet")
        cur.execute("SELECT id FROM issued_document_files WHERE certificate_id = %s AND sha256 = %s "
                    "AND deleted_at IS NULL", (cert_id, sha))
        dup = cur.fetchone()
        if dup:
            return {"id": dup["id"], "duplicate": True, "sha256": sha}
        if replace_id:
            cur.execute("SELECT id FROM issued_document_files WHERE id = %s AND certificate_id = %s "
                        "AND deleted_at IS NULL", (replace_id, cert_id))
            if not cur.fetchone():
                raise HTTPException(404, "The file to replace was not found")
        year = int(cert.get("y") or 0) or 0
        final = ARCHIVE_DIR / str(year) / f"{sha}.{ext}"
        final.parent.mkdir(parents=True, exist_ok=True)
        tmp = final.with_name(final.name + ".part")
        try:
            tmp.write_bytes(data)
            cur.execute("INSERT INTO issued_document_files (certificate_id, kind, sha256, file_name, "
                        "doc_year, supersedes_id, source_name, created_by) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (cert_id, kind, sha, final.name, year, replace_id,
                         (file.filename or "")[:255] or None, personnel_id))
            new_id = cur.lastrowid
            conn.commit()
        except Exception as exc:
            conn.rollback()
            tmp.unlink(missing_ok=True)
            logger.error("archive file insert failed: %s", exc)
            raise HTTPException(500, "Could not save the file")
        os.replace(tmp, final)
        return {"id": new_id, "duplicate": False, "sha256": sha}
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
