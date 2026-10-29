"""Issued certificates routes: /issued-certificates/* /api/issued-certificates/* /certificate-numbers/*."""
from datetime import datetime
from typing import Optional

import mysql.connector
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from deps import get_db, execute_sp_fetchall, execute_sp_fetchone

router = APIRouter()


# ===========================================================================
# 16. Issued Certificates Module
# ===========================================================================

class IssuedCertificatePayload(BaseModel):
    student_id: Optional[int] = None
    to_title: Optional[str] = "من يهمه الأمر"
    template_type: Optional[str] = "graduation"
    issue_date: Optional[str] = None
    certificate_number: Optional[str] = None


@router.get("/api/issued-certificates")
@router.get("/issued-certificates")
def get_all_issued_certificates(conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAllIssuedCertificates")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/issued-certificates/latest-number")
@router.get("/issued-certificates/latest-number")
def get_latest_certificate_number(conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute(
            "SELECT certificate_number FROM issued_certificates "
            "WHERE certificate_number IS NOT NULL AND certificate_number != '' "
            "ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
        latest = row["certificate_number"] if row else None
        # Numbers reserved by laptops for offline use must never be handed out online:
        # report the end of the highest reserved block if it is above the latest issued number
        parts = _cert_number_parts(latest)
        if parts:
            block_end = _max_reserved_block_end(conn, parts[1])
            if block_end and block_end >= parts[0]:
                latest = f"{block_end}/{parts[1]}"
        return {"latest_number": latest}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


def _cert_number_parts(number) -> Optional[tuple]:
    """'893/26' -> (893, '26'); anything else -> None."""
    import re as _re
    m = _re.match(r"^\s*(\d+)\s*/\s*(\S+)\s*$", str(number or ""))
    return (int(m.group(1)), m.group(2)) if m else None


def _max_reserved_block_end(conn, year_suffix: str) -> Optional[int]:
    cur = conn.cursor(buffered=True)
    try:
        cur.execute("SELECT MAX(end_no) FROM certificate_number_blocks WHERE year_suffix = %s", (year_suffix,))
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else None
    except Exception:
        return None  # table not created yet
    finally:
        cur.close()


class CertificateBlockRequest(BaseModel):
    device_id: str
    count: Optional[int] = 20
    year_suffix: Optional[str] = None


@router.post("/certificate-numbers/reserve")
def reserve_certificate_numbers(payload: CertificateBlockRequest, conn=Depends(get_db)):
    """
    Reserve a block of certificate numbers for one laptop to use while offline, so two
    offline laptops can never print the same number. The block starts above every number
    already issued or reserved for that year.
    """
    suffix = (payload.year_suffix or datetime.now().strftime("%y")).strip()
    count = max(1, min(int(payload.count or 20), 200))
    cur = conn.cursor(buffered=True)
    try:
        cur.execute("SELECT GET_LOCK('certificate_number_blocks', 10)")
        cur.fetchone()
        cur.execute(
            "SELECT certificate_number FROM issued_certificates WHERE certificate_number LIKE %s",
            (f"%/{suffix}",)
        )
        issued_max = max((p[0] for p in (_cert_number_parts(r[0]) for r in cur.fetchall()) if p and p[1] == suffix),
                         default=0)
        start = max(issued_max, _max_reserved_block_end(conn, suffix) or 0) + 1
        end = start + count - 1
        cur.execute(
            "INSERT INTO certificate_number_blocks (device_id, year_suffix, start_no, end_no) VALUES (%s, %s, %s, %s)",
            (payload.device_id[:64], suffix, start, end)
        )
        conn.commit()
        return {"year_suffix": suffix, "start_no": start, "end_no": end}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        try:
            cur.execute("SELECT RELEASE_LOCK('certificate_number_blocks')")
            cur.fetchone()
        except Exception:
            pass
        cur.close()


@router.get("/api/issued-certificates/report")
@router.get("/issued-certificates/report")
def get_issued_certificates_report(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    template_type: Optional[str] = Query(None),
    graduation_year: Optional[int] = Query(None),
    study_system_id: Optional[int] = Query(None),
    search_text: Optional[str] = Query(None),
    conn=Depends(get_db)
):
    try:
        return execute_sp_fetchall(
            conn,
            "GetIssuedCertificatesReport",
            (start_date, end_date, department_id, template_type, graduation_year, study_system_id, search_text)
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/issued-certificates/{cert_id}")
@router.get("/issued-certificates/{cert_id}")
def get_issued_certificate_by_id(cert_id: int, conn=Depends(get_db)):
    try:
        row = execute_sp_fetchone(conn, "GetIssuedCertificateById", (cert_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Issued certificate not found")
        return row
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/issued-certificates/by-student/{student_id}")
@router.get("/issued-certificates/by-student/{student_id}")
def get_issued_certificates_by_student(student_id: int, conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetIssuedCertificatesByStudent", (student_id,))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/issued-certificates")
@router.post("/issued-certificates")
def insert_issued_certificate(payload: IssuedCertificatePayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        issue_date = payload.issue_date or datetime.now().strftime("%Y-%m-%d")
        student_id = payload.student_id or 0
        cur.callproc(
            "InsertIssuedCertificate",
            (
                student_id,
                payload.to_title or "من يهمه الأمر",
                payload.template_type or "graduation",
                str(issue_date),
                payload.certificate_number,
            )
        )
        real_id = None
        if hasattr(cur, "stored_results"):
            for result in cur.stored_results():
                row = result.fetchone()
                if row:
                    if "inserted_id" in row:
                        real_id = row["inserted_id"]
                    elif "new_id" in row:
                        real_id = row["new_id"]
                    elif "id" in row:
                        real_id = row["id"]
                    break
        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        if real_id is None:
            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
            r = cur.fetchone()
            if r:
                real_id = r.get("new_id")

        conn.commit()
        return {"new_id": real_id, "inserted_id": real_id, "status": "success"}
    except mysql.connector.errors.IntegrityError as db_err:
        conn.rollback()
        if "Duplicate entry" in str(db_err) or "1062" in str(db_err):
            raise HTTPException(status_code=409, detail="Certificate record already exists for this student, date, and template.")
        raise HTTPException(status_code=400, detail=str(db_err))
    except mysql.connector.errors.DatabaseError as db_err:
        conn.rollback()
        # SIGNAL '45000' in InsertIssuedCertificate: the number belongs to another student
        if getattr(db_err, "sqlstate", None) == "45000":
            raise HTTPException(status_code=409, detail=getattr(db_err, "msg", None) or str(db_err))
        raise HTTPException(status_code=500, detail=str(db_err))
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.put("/api/issued-certificates/{cert_id}")
@router.put("/issued-certificates/{cert_id}")
def update_issued_certificate(cert_id: int, payload: IssuedCertificatePayload, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        issue_date = payload.issue_date or datetime.now().strftime("%Y-%m-%d")
        cur.callproc(
            "UpdateIssuedCertificate",
            (
                cert_id,
                payload.to_title or "",
                payload.template_type or "graduation",
                str(issue_date),
                payload.certificate_number,
            )
        )
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success", "message": "Issued certificate updated successfully"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.delete("/api/issued-certificates/{cert_id}")
@router.delete("/issued-certificates/{cert_id}")
def delete_issued_certificate(cert_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("DeleteIssuedCertificate", (cert_id,))
        try:
            while cur.nextset():
                pass
        except Exception:
            pass
        conn.commit()
        return {"status": "success", "message": "Issued certificate deleted successfully"}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()
