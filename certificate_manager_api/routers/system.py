"""System routes: /ping, /health/db, the stored-procedure gateway, replica download, table counts, backup/restore."""
import os
from datetime import datetime
from typing import List, Any, Optional

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from pydantic import BaseModel

from deps import logger, get_db, decode_db_value, table_has_updated_at, _require_admin

router = APIRouter()


@router.get("/ping")
def ping():
    """Health check endpoint to verify database server connectivity/status."""
    return {"status": "online"}


@router.get("/health/db")
def health_db(conn=Depends(get_db)):
    """Database health check: confirms MySQL is reachable and lists the stored procedures it holds."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT ROUTINE_NAME FROM information_schema.ROUTINES "
            "WHERE ROUTINE_SCHEMA = DATABASE() AND ROUTINE_TYPE = 'PROCEDURE'"
        )
        procedures = [decode_db_value(r[0]) for r in cur.fetchall()]
        return {"database": "ok", "procedures": procedures}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


# ---------------------------------------------------------------------------
# Stored-Procedure Gateway (used by the client's BaseRepository helpers)
# Only the procedures listed here can be called; anything else is refused.
# ---------------------------------------------------------------------------

SP_READ_WHITELIST = {
    "GetThesisByStudent", "GetSupervisorsByStudent",
    "GetAllStudyRoutines", "GetStudyRoutineCourses",
    "GetStudyRoutinePeriods", "GetStudyRoutinePeriodCourses",
}

SP_WRITE_WHITELIST = {
    "ClearAuditLogs",
    "InsertDepartment", "UpdateDepartment", "DeleteDepartment",
    "InsertStudySystem", "UpdateStudySystem", "DeleteStudySystem",
    "DeleteStudent", "InsertAcademicPeriod", "InsertEnrollment",
    "InsertGraduationOrder", "UpdateGraduationOrder", "DeleteGraduationOrder",
    "LinkStudentsToOrder", "UnlinkStudentFromOrder",
    "InsertThesis", "UpdateThesis", "DeleteThesis",
    "InsertStudentSupervisor", "UpdateStudentSupervisor", "DeleteStudentSupervisor",
    "InsertStudyRoutine", "UpdateStudyRoutine", "DeleteStudyRoutine", "InsertStudyRoutineCourse",
    "InsertStudyRoutinePeriod", "DeleteStudyRoutinePeriod",
    "InsertStudyRoutinePeriodCourse", "DeleteStudyRoutinePeriodCourse",
}


class SPCallPayload(BaseModel):
    proc: str
    args: List[Any] = []


@router.post("/sp/read")
def sp_read(payload: SPCallPayload, conn=Depends(get_db)):
    """Run a whitelisted read-only stored procedure and return every result set."""
    if payload.proc not in SP_READ_WHITELIST:
        raise HTTPException(status_code=403, detail=f"Procedure not allowed: {payload.proc}")
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc(payload.proc, tuple(payload.args))
        datasets = [decode_db_value(res.fetchall()) for res in cur.stored_results()]
        return {"datasets": datasets}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.post("/sp/write")
def sp_write(payload: SPCallPayload, conn=Depends(get_db)):
    """Run a whitelisted write stored procedure inside a transaction and return any new row ID."""
    if payload.proc not in SP_WRITE_WHITELIST:
        raise HTTPException(status_code=403, detail=f"Procedure not allowed: {payload.proc}")
    cur = conn.cursor(dictionary=True)
    try:
        cur.callproc(payload.proc, tuple(payload.args))
        new_id = None
        first_row = None
        for res in cur.stored_results():
            row = res.fetchone()
            if first_row is None and isinstance(row, dict):
                first_row = row
        conn.commit()
        # Same LAST_INSERT_ID() extraction the client used to do locally
        if first_row:
            if first_row.get("new_id") is not None:
                new_id = int(first_row["new_id"])
            elif first_row.get("inserted_id") is not None:
                new_id = int(first_row["inserted_id"])
            else:
                vals = [v for v in first_row.values() if isinstance(v, int)]
                new_id = vals[0] if vals else None
        return {"new_id": new_id, "row": decode_db_value(first_row) if first_row else None}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


# ---------------------------------------------------------------------------
# Replica Download (client SQLite offline cache is filled from here)
# ---------------------------------------------------------------------------

REPLICA_TABLES = [
    "university_settings", "countries", "governorates", "settings",
    "departments", "study_systems", "personnel", "courses",
    "graduation_orders", "students", "academic_periods", "enrollments",
    "student_supervisors", "thesis_records", "issued_certificates",
    "study_routines", "study_routine_period", "study_routine_courses",
    "permissions", "personnel_permissions",
    "roles", "user_roles",
]


def _replica_cast(val: Any) -> Any:
    """Cast a MySQL value exactly as the client's replica loader always stored it in SQLite."""
    if val is None or isinstance(val, (int, float)):
        return val
    if isinstance(val, (bytes, bytearray)):
        try:
            return val.decode("utf-8")
        except UnicodeDecodeError:
            return str(val)
    return str(val)


@router.get("/replica/tables")
def replica_tables():
    """List the tables the client replicates, in dependency order."""
    return REPLICA_TABLES


@router.get("/replica/{table_name}")
def replica_table(table_name: str, since: Optional[str] = Query(None), conn=Depends(get_db)):
    """
    Rows of one replicated table for the client's offline SQLite copy.

    Without `since` (or if the table has no updated_at column yet): every row ("mode": "full").
    With `since`: only rows changed at or after that time, plus the ids deleted since then
    ("mode": "delta"). `next_since` is what the client sends next time; it lies 60 s in the
    past so rows committed by transactions that were still running are not missed.
    """
    if table_name not in REPLICA_TABLES:
        raise HTTPException(status_code=403, detail=f"Table not allowed: {table_name}")
    # buffered: several queries run one after another on this connection
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        has_updated_at = table_has_updated_at(conn, table_name)
        cur.execute("SELECT NOW(3) - INTERVAL 60 SECOND AS next_since")
        next_since = str(cur.fetchone()["next_since"]) if has_updated_at else None

        if since and has_updated_at:
            cur.execute(f"SELECT * FROM `{table_name}` WHERE updated_at >= %s", (since,))
            rows = cur.fetchall()
            columns = list(cur.column_names) if cur.column_names else []
            deleted_ids: List[int] = []
            try:
                cur.execute(
                    "SELECT row_id FROM sync_deletions WHERE table_name = %s AND deleted_at >= %s",
                    (table_name, since)
                )
                deleted_ids = [int(r["row_id"]) for r in cur.fetchall()]
            except Exception:
                pass  # sync_deletions not created yet
            mode = "delta"
        else:
            cur.execute(f"SELECT * FROM `{table_name}`")
            rows = cur.fetchall()
            columns = list(cur.column_names) if cur.column_names else []
            deleted_ids = []
            mode = "full"
        return {
            "table": table_name,
            "mode": mode,
            "columns": columns,
            "rows": [[_replica_cast(r.get(c)) for c in columns] for r in rows],
            "deleted_ids": deleted_ids,
            "next_since": next_since,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


@router.get("/table-count/{table_name}")
def table_count(table_name: str, conn=Depends(get_db)):
    """Count rows in one of the dashboard tables."""
    if table_name not in ("students", "departments", "courses", "personnel", "graduation_orders", "study_systems"):
        raise HTTPException(status_code=403, detail=f"Table not allowed: {table_name}")
    cur = conn.cursor(buffered=True)
    try:
        cur.execute(f"SELECT COUNT(*) FROM `{table_name}`")
        row = cur.fetchone()
        return {"count": int(row[0]) if row else 0}
    finally:
        cur.close()


# ---------------------------------------------------------------------------
# Database Backup & Restore (runs mysqldump / mysql on the server)
# ---------------------------------------------------------------------------

@router.get("/admin/backup")
def admin_backup(personnel_id: Optional[int] = Query(None), conn=Depends(get_db)):
    """Create a mysqldump of the database and stream it back as a .sql file."""
    import tempfile
    from pathlib import Path
    from fastapi.responses import FileResponse
    from starlette.background import BackgroundTask
    from db import backup_db

    _require_admin(conn, personnel_id)
    fd, tmp_name = tempfile.mkstemp(suffix=".sql", prefix="cm_backup_")
    os.close(fd)
    try:
        backup_db(Path(tmp_name))
    except Exception as exc:
        os.remove(tmp_name)
        raise HTTPException(status_code=500, detail=str(exc))
    return FileResponse(
        tmp_name,
        media_type="application/sql",
        filename=f"certificate_manager_backup_{datetime.now():%Y%m%d_%H%M%S}.sql",
        background=BackgroundTask(os.remove, tmp_name),
    )


@router.post("/admin/restore")
async def admin_restore(personnel_id: Optional[int] = Query(None), file: UploadFile = File(...), conn=Depends(get_db)):
    """Restore the database from an uploaded .sql dump (admin only, replaces all data)."""
    import tempfile
    from pathlib import Path
    from db import restore_db

    _require_admin(conn, personnel_id)
    fd, tmp_name = tempfile.mkstemp(suffix=".sql", prefix="cm_restore_")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(await file.read())
        restore_db(Path(tmp_name))
        logger.warning(f"Database restored from upload by personnel {personnel_id}")
        return {"status": "restored"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        try:
            os.remove(tmp_name)
        except OSError:
            pass
