"""Offline synchronization: POST /sync (router) and the batch endpoint POST /sync + /api/sync (batch_router).

batch_router is included last in main.py, where its routes were registered before the split.
Its /sync registration is shadowed by router's; /api/sync is served by it.
"""
from datetime import datetime
from typing import List, Dict, Any

import mysql.connector
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import (logger, get_db, decode_db_value, table_has_updated_at,
                  _set_must_change_password, result_status_code)
from password_hashing import is_hashed

router = APIRouter()
batch_router = APIRouter()


# ===========================================================================
# 1. System & Health & Offline Sync
# ===========================================================================

TABLE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "students": {
        "sp_name": "InsertStudent",
        "update_sp_name": "UpdateStudent",
        "delete_sp_name": "DeleteStudent",
        "sp_args": [
            "full_name_ar", "full_name_en", "gender",
            "sequence_number", "postgraduation_number", "date_of_birth",
            "birthplace_id", "birthplace_other", "nationality_id", "national_id",
            "department_id", "study_system_id", "degree_level",
            "order_id", "admission_year", "summer_training_data",
            "average", "graduation_date", "graduation_semester",
        ],
    },
    "academic_periods": {
        "sp_name": "InsertAcademicPeriod",
        "delete_sp_name": "DeleteAcademicPeriod",
        "sp_args": ["student_id", "academic_year", "stage_number", "semester_num", "result_status"],
    },
    "enrollments": {
        "sp_name": "InsertEnrollment",
        "delete_sp_name": "DeleteEnrollment",
        "sp_args": ["period_id", "course_id", "score", "passed_round"],
    },
    "issued_certificates": {
        "sp_name": "InsertIssuedCertificate",
        "sp_args": ["student_id", "to_title", "template_type", "issue_date", "certificate_number"],
    },
    "study_routines": {
        "sp_name": "InsertStudyRoutine",
        "sp_args": ["name_ar", "name_en", "department_id", "study_system_id"],
    },
    "study_routine_courses": {
        "sp_name": "InsertStudyRoutineCourse",
        "sp_args": ["routine_id", "course_id"],
    },
    "study_routine_period": {
        "sp_name": "InsertStudyRoutinePeriod",
        "sp_args": ["routine_id", "stage_number", "semester_num"],
    },
    "study_routine_period_courses": {
        "sp_name": "InsertStudyRoutinePeriodCourse",
        "sp_args": ["period_id", "course_id"],
    },
}


class SyncAction(BaseModel):
    id: int
    table_name: str
    operation: str
    temp_id: int
    payload: Dict[str, Any]


class SyncPayload(BaseModel):
    actions: List[SyncAction]


def resolve_payload_fks(payload: dict, id_map: dict) -> dict:
    """Resolve temporary IDs (negative integers) to real database auto-increment IDs."""
    resolved = {}
    for k, v in payload.items():
        if v in id_map:
            resolved[k] = id_map[v]
        elif isinstance(v, str) and v.lstrip('-').isdigit():
            int_val = int(v)
            if int_val in id_map:
                resolved[k] = id_map[int_val]
            else:
                resolved[k] = v
        else:
            resolved[k] = v
    return resolved


def _has_unresolved_temp_ref(payload: dict, id_map: dict) -> bool:
    """True when the payload still points at a temporary (negative) parent ID that was not synced."""
    for key, val in payload.items():
        if key == "id":
            continue
        num = None
        if isinstance(val, int) and not isinstance(val, bool):
            num = val
        elif isinstance(val, str) and val.startswith("-") and val[1:].isdigit():
            num = int(val)
        if num is not None and num < 0 and num not in id_map:
            return True
    return False


@router.post("/sync")
def sync_offline_queue(payload: SyncPayload, conn=Depends(get_db)):
    """
    Synchronize offline actions to MySQL one at a time.

    Each action is its own transaction: good actions are committed, a failing
    action is rolled back and reported in "failed" without blocking the rest.
    An action whose parent record (temporary negative ID) did not sync is
    skipped and reported, so it is never written with a broken link.
    """
    id_map: Dict[int, int] = {}
    failed: List[Dict[str, Any]] = []
    for action in payload.actions:
        if action.table_name == "personnel_password":
            try:
                _apply_offline_password_change(conn, action)
                id_map[action.temp_id] = action.temp_id
            except HTTPException as exc:
                failed.append({
                    "queue_id": action.id, "table_name": action.table_name, "temp_id": action.temp_id,
                    "error": str(exc.detail),
                })
            continue
        if _has_unresolved_temp_ref(action.payload, id_map):
            failed.append({
                "queue_id": action.id, "table_name": action.table_name, "temp_id": action.temp_id,
                "error": "Parent record was not synced / السجل الأب لم تتم مزامنته",
            })
            continue
        try:
            _apply_sync_actions(SyncPayload(actions=[action]), conn, id_map)
        except HTTPException as exc:
            failed.append({
                "queue_id": action.id, "table_name": action.table_name, "temp_id": action.temp_id,
                "error": str(exc.detail),
            })
    if failed:
        logger.warning(f"Sync finished with {len(failed)} failed action(s) of {len(payload.actions)}")
    return {"id_map": id_map, "failed": failed}


def _normalize_ts(value) -> str:
    """Compare timestamps written as '2026-10-24 10:00:00.123000' or '2026-10-24T10:00:00.123'."""
    text = str(value or "").replace("T", " ").strip()
    if "." in text:
        head, frac = text.split(".", 1)
        text = f"{head}.{frac[:3].ljust(3, '0')}"
    else:
        text = f"{text}.000" if text else ""
    return text


def _check_offline_edit_conflict(conn, table_name: str, record_id: int, payload: dict) -> None:
    """
    An offline edit carries "_base_updated_at": the version of the record the laptop had.
    If the server's record changed since then (someone else edited it), refuse the edit
    (409) instead of silently overwriting the newer data. "_override": true skips the check.
    """
    base = payload.get("_base_updated_at")
    if not base or payload.get("_override") or not table_has_updated_at(conn, table_name):
        return
    cur = conn.cursor(buffered=True)
    try:
        cur.execute(f"SELECT updated_at FROM `{table_name}` WHERE id = %s", (record_id,))
        row = cur.fetchone()
    finally:
        cur.close()
    if row and _normalize_ts(row[0]) != _normalize_ts(base):
        raise HTTPException(
            status_code=409,
            detail=f"Conflict: this {table_name} record was changed on the server after this laptop's copy "
                   f"(server {row[0]}, laptop {base}); the offline edit was not applied",
        )


def _check_duplicate_student(conn, payload: dict) -> None:
    """
    A student created offline may already exist (added on another laptop or on the server).
    Same national ID, or same Arabic name in the same department -> refuse (409) unless
    "_allow_duplicate" is set (the user chose "keep as new student").
    """
    if payload.get("_allow_duplicate") or payload.get("_override"):
        return
    national_id = str(payload.get("national_id") or "").strip()
    name_ar = " ".join(str(payload.get("full_name_ar") or "").split())
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        row = None
        if national_id:
            cur.execute("SELECT id, full_name_ar FROM students WHERE national_id = %s LIMIT 1", (national_id,))
            row = cur.fetchone()
        if not row and name_ar and payload.get("department_id"):
            cur.execute(
                "SELECT id, full_name_ar FROM students WHERE TRIM(full_name_ar) = %s AND department_id = %s LIMIT 1",
                (name_ar, payload.get("department_id"))
            )
            row = cur.fetchone()
    finally:
        cur.close()
    if row:
        raise HTTPException(
            status_code=409,
            detail=f"Possible duplicate: student #{row['id']} ({decode_db_value(row['full_name_ar'])}) already exists",
        )


def _apply_offline_password_change(conn, action: "SyncAction") -> None:
    """
    Password set on a laptop while offline (admin temporary reset, or the user's own change).
    payload: {"password_hash": <hash made on the laptop>, "base_hash": <hash the laptop had>, "must_change": bool}
    temp_id is the personnel id. If the server's password changed in the meantime, the newer
    server password wins and this change is reported as failed (409).
    """
    data = action.payload or {}
    new_hash = str(data.get("password_hash") or "")
    if not is_hashed(new_hash):
        raise HTTPException(status_code=400, detail="Offline password change must carry a hashed password")
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT password_hash FROM personnel WHERE id = %s", (action.temp_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Personnel {action.temp_id} not found")
        if "base_hash" in data and (row.get("password_hash") or "") != (data.get("base_hash") or ""):
            raise HTTPException(status_code=409, detail="Password was changed on the server meanwhile; the offline change was not applied")
        cur.execute("UPDATE personnel SET password_hash = %s WHERE id = %s", (new_hash, action.temp_id))
        _set_must_change_password(conn, action.temp_id, bool(data.get("must_change")))
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database synchronization failed: {exc}")
    finally:
        cur.close()


def _apply_sync_actions(payload: SyncPayload, conn, id_map: dict) -> dict:
    """Apply offline actions to MySQL in a single transaction (all or nothing), filling id_map."""
    try:
        for action in payload.actions:
            tbl = action.table_name
            temp_id = action.temp_id
            if tbl not in TABLE_REGISTRY:
                logger.error(f"Table '{tbl}' is not in TABLE_REGISTRY.")
                raise HTTPException(status_code=400, detail=f"Unsupported table: {tbl}")

            resolved_payload = resolve_payload_fks(action.payload, id_map)
            resolved_payload.pop("id", None)
            if tbl == "academic_periods" and "result_status" in resolved_payload:
                resolved_payload["result_status"] = result_status_code(resolved_payload["result_status"])
            meta = TABLE_REGISTRY[tbl]
            cur = conn.cursor(dictionary=True)
            try:
                if action.operation == "UPDATE" and "update_sp_name" in meta:
                    _check_offline_edit_conflict(conn, tbl, temp_id, resolved_payload)
                    sp_name = meta["update_sp_name"]
                    # For UpdateStudent, student_id is the first arg, then the rest
                    sp_args = [temp_id] + [resolved_payload.get(k) for k in meta["sp_args"]]
                    logger.info(f"Calling SP {sp_name} (UPDATE) with args {sp_args}")
                    try:
                        cur.callproc(sp_name, sp_args)
                        try:
                            while cur.nextset(): pass
                        except Exception: pass
                        id_map[temp_id] = temp_id
                        logger.info(f"Successfully updated {tbl}: id={temp_id}")
                        continue
                    except Exception as err:
                        logger.error(f"Error updating {tbl} with ID {temp_id}: {err}")
                        raise

                if action.operation == "DELETE" and "delete_sp_name" in meta:
                    sp_name = meta["delete_sp_name"]
                    target_id = temp_id if temp_id > 0 else resolved_payload.get("id")
                    if target_id and target_id in id_map:
                        target_id = id_map[target_id]
                    if target_id and target_id > 0:
                        logger.info(f"Calling SP {sp_name} (DELETE) for {tbl} with ID {target_id}")
                        try:
                            cur.callproc(sp_name, (target_id,))
                            try:
                                while cur.nextset(): pass
                            except Exception: pass
                            logger.info(f"Successfully deleted {tbl}: id={target_id}")
                        except Exception as err:
                            logger.error(f"Error deleting {tbl} with ID {target_id}: {err}")
                            raise
                    continue

                if tbl == "students":
                    _check_duplicate_student(conn, resolved_payload)
                if meta["sp_name"]:
                    sp_args = tuple(resolved_payload.get(k) for k in meta["sp_args"])
                    logger.info(f"Calling SP {meta['sp_name']} with args {sp_args}")
                    try:
                        cur.callproc(meta["sp_name"], sp_args)
                    except (mysql.connector.errors.IntegrityError, mysql.connector.errors.DatabaseError) as err:
                        if tbl == "issued_certificates":
                            err_msg = str(err)
                            is_dup = (isinstance(err, mysql.connector.errors.IntegrityError) and getattr(err, "errno", None) == 1062)
                            is_collision = (
                                getattr(err, "errno", None) == 1644
                                or getattr(err, "sqlstate", None) == "45000"
                                or "Certificate number already assigned to another student" in err_msg
                                or "رقم الوثيقة مستخدم بالفعل" in err_msg
                            )
                            if is_collision:
                                base_num = str(resolved_payload.get("certificate_number") or "").strip()
                                logger.warning(f"Certificate number collision for {tbl} (student {resolved_payload.get('student_id')}, num '{base_num}'). Reallocating next available number...")
                                cur.execute("SELECT certificate_number FROM issued_certificates WHERE certificate_number IS NOT NULL AND certificate_number != ''")
                                existing_nums = {str(r["certificate_number"]).strip().lower() for r in cur.fetchall() if r.get("certificate_number")}

                                import re
                                match = re.match(r"^(\d+)(/.*)?$", base_num)
                                if match:
                                    n = int(match.group(1))
                                    sfx = match.group(2) or ""
                                    next_candidate = f"{n}{sfx}"
                                    while next_candidate.strip().lower() in existing_nums:
                                        n += 1
                                        next_candidate = f"{n}{sfx}"
                                else:
                                    counter = 1
                                    next_candidate = f"{base_num or '1/26'}-{counter}"
                                    while next_candidate.strip().lower() in existing_nums:
                                        counter += 1
                                        next_candidate = f"{base_num or '1/26'}-{counter}"

                                new_args = list(sp_args)
                                if len(new_args) >= 5:
                                    new_args[4] = next_candidate
                                logger.info(f"Retrying SP {meta['sp_name']} with reallocated number: {next_candidate}")
                                cur.callproc(meta["sp_name"], tuple(new_args))
                                resolved_payload["certificate_number"] = next_candidate

                                real_id = None
                                if hasattr(cur, "stored_results"):
                                    for result in cur.stored_results():
                                        row = result.fetchone()
                                        if row:
                                            if "new_id" in row:
                                                real_id = row["new_id"]
                                            elif "inserted_id" in row:
                                                real_id = row["inserted_id"]
                                            break
                                try:
                                    while cur.nextset():
                                        pass
                                except Exception:
                                    pass

                                if real_id is None:
                                    cur.execute("SELECT LAST_INSERT_ID() AS new_id")
                                    real_id = cur.fetchone()["new_id"]

                                id_map[temp_id] = real_id
                                logger.info(f"Successfully inserted {tbl} after collision recovery: temp_id={temp_id} -> real_id={real_id} (cert_num={next_candidate})")
                                continue
                            elif is_dup:
                                logger.warning(f"Duplicate entry ignored for SP {meta['sp_name']}: {err}")
                                c_num = resolved_payload.get("certificate_number")
                                if c_num:
                                    cur.execute("SELECT id FROM issued_certificates WHERE certificate_number=%s", (c_num,))
                                else:
                                    cur.execute(
                                        "SELECT id FROM issued_certificates WHERE student_id=%s AND issue_date=%s AND to_title=%s AND template_type=%s",
                                        (resolved_payload.get("student_id"), resolved_payload.get("issue_date"), resolved_payload.get("to_title"), resolved_payload.get("template_type"))
                                    )
                                existing_row = cur.fetchone()
                                if existing_row:
                                    real_id = existing_row["id"]
                                    id_map[temp_id] = real_id
                                    logger.info(f"Recovered existing ID {real_id} for {tbl}")
                                    continue
                            else:
                                raise
                        elif err.errno == 1062 and tbl == "academic_periods":
                            st_id = resolved_payload.get("student_id")
                            stg = resolved_payload.get("stage_number")
                            sem = resolved_payload.get("semester_num")
                            logger.warning(f"Duplicate academic period ignored for SP {meta['sp_name']}: {err}")
                            cur.execute(
                                "SELECT id FROM academic_periods WHERE student_id=%s AND stage_number=%s AND semester_num=%s",
                                (st_id, stg, sem)
                            )
                            row = cur.fetchone()
                            if row:
                                real_id = row["id"]
                                id_map[temp_id] = real_id
                                logger.info(f"Recovered existing ID {real_id} for {tbl}")
                                continue
                        elif err.errno == 1062 and tbl == "enrollments":
                            pid = resolved_payload.get("period_id")
                            cid = resolved_payload.get("course_id")
                            logger.warning(f"Duplicate enrollment ignored for SP {meta['sp_name']}: {err}")
                            cur.execute(
                                "SELECT id FROM enrollments WHERE period_id=%s AND course_id=%s",
                                (pid, cid)
                            )
                            row = cur.fetchone()
                            if row:
                                real_id = row["id"]
                                id_map[temp_id] = real_id
                                score = float(resolved_payload.get("score") or 0.0)
                                pr = int(resolved_payload.get("passed_round") or 1)
                                cur.callproc("UpdateEnrollment", (real_id, score, pr))
                                try:
                                    while cur.nextset(): pass
                                except Exception: pass
                                logger.info(f"Recovered existing ID {real_id} for {tbl} and updated enrollment")
                                continue
                        raise

                    real_id = None
                    if hasattr(cur, "stored_results"):
                        for result in cur.stored_results():
                            row = result.fetchone()
                            if row:
                                if "new_id" in row:
                                    real_id = row["new_id"]
                                elif "inserted_id" in row:
                                    real_id = row["inserted_id"]
                                break
                    try:
                        while cur.nextset():
                            pass
                    except Exception:
                        pass

                    if real_id is None:
                        cur.execute("SELECT LAST_INSERT_ID() AS new_id")
                        real_id = cur.fetchone()["new_id"]
                else:
                    insert_sql = meta["insert_sql"]
                    insert_keys = meta["insert_keys"]
                    values = tuple(resolved_payload.get(k) for k in insert_keys)
                    logger.info(f"Executing raw SQL: {insert_sql} with values {values}")
                    try:
                        cur.execute(insert_sql, values)
                        real_id = cur.lastrowid
                    except mysql.connector.errors.IntegrityError as err:
                        if err.errno == 1062 and tbl == "academic_periods":
                            st_id = resolved_payload.get("student_id")
                            stg = resolved_payload.get("stage_number")
                            sem = resolved_payload.get("semester_num")
                            logger.warning(f"Duplicate academic period ignored: {err}")
                            cur.execute(
                                "SELECT id FROM academic_periods WHERE student_id=%s AND stage_number=%s AND semester_num=%s",
                                (st_id, stg, sem)
                            )
                            row = cur.fetchone()
                            if row:
                                real_id = row["id"]
                            else:
                                raise
                        elif err.errno == 1062 and tbl == "enrollments":
                            pid = resolved_payload.get("period_id")
                            cid = resolved_payload.get("course_id")
                            logger.warning(f"Duplicate enrollment ignored: {err}")
                            cur.execute(
                                "SELECT id FROM enrollments WHERE period_id=%s AND course_id=%s",
                                (pid, cid)
                            )
                            row = cur.fetchone()
                            if row:
                                real_id = row["id"]
                                cur.execute(
                                    "UPDATE enrollments SET score=%s, passed_round=%s WHERE id=%s",
                                    (resolved_payload.get("score", 0.0), str(resolved_payload.get("passed_round", "1")), real_id)
                                )
                            else:
                                raise
                        else:
                            raise

                id_map[temp_id] = real_id
                logger.info(f"Successfully inserted {tbl}: temp_id={temp_id} -> real_id={real_id}")
            finally:
                cur.close()

        conn.commit()
        return {"id_map": id_map}
    except Exception as exc:
        conn.rollback()
        # One short line per failed action (the caller reports it back to the client); no traceback
        first = payload.actions[0] if payload.actions else None
        where = f"{first.table_name} queue_id={first.id} temp_id={first.temp_id}" if first else "empty batch"
        logger.warning(f"Sync action rolled back ({where}): {exc}")
        raise HTTPException(status_code=500, detail=f"Database synchronization failed: {str(exc)}")


# ===========================================================================
# 17. Batch Offline Synchronization Engine Endpoint
# ===========================================================================

@batch_router.post("/sync")
@batch_router.post("/api/sync")
def process_offline_sync_batch(payload: dict, conn=Depends(get_db)):
    """
    Batch sync endpoint for pushing queued offline writes to MySQL.
    Processes queued actions in FIFO order, resolving parent temporary IDs
    (e.g., negative student_id or period_id) to real MySQL auto-increment IDs
    before executing child inserts (academic_periods, enrollments, etc.).
    """
    actions = payload.get("actions", [])
    if not actions:
        return {"status": "success", "id_map": {}}

    id_map = {}
    cur = conn.cursor(dictionary=True)
    try:
        for action in actions:
            tbl = action.get("table_name")
            op = action.get("operation")
            temp_id = action.get("temp_id")
            data = dict(action.get("payload") or {})

            # 1. Remap parent temporary IDs in payload to real MySQL IDs
            for k, v in list(data.items()):
                if isinstance(v, int) and v in id_map:
                    data[k] = id_map[v]
                elif isinstance(v, str) and (v.startswith("-") and v[1:].isdigit()):
                    v_int = int(v)
                    if v_int in id_map:
                        data[k] = id_map[v_int]

            # 2. Process Operations
            if op == "INSERT":
                if tbl == "students":
                    args = (
                        data.get("full_name_ar"),
                        data.get("full_name_en"),
                        int(data.get("gender") or 1),
                        data.get("sequence_number"),
                        data.get("postgraduation_number"),
                        data.get("date_of_birth"),
                        data.get("birthplace_id"),
                        data.get("birthplace_other"),
                        int(data.get("nationality_id") or 1),
                        data.get("national_id"),
                        data.get("department_id"),
                        int(data.get("study_system_id") or 1),
                        int(data.get("degree_level") or 1),
                        data.get("order_id"),
                        data.get("admission_year"),
                        data.get("summer_training_data"),
                        data.get("average"),
                        data.get("graduation_date"),
                        data.get("graduation_semester") or "first"
                    )
                    cur.callproc("InsertStudent", args)
                    real_id = None
                    if hasattr(cur, "stored_results"):
                        for res in cur.stored_results():
                            row = res.fetchone()
                            if row and ("new_id" in row or "inserted_id" in row):
                                real_id = row.get("new_id") or row.get("inserted_id")
                                break
                    try:
                        while cur.nextset():
                            pass
                    except Exception:
                        pass
                    if real_id is None:
                        cur.execute("SELECT LAST_INSERT_ID() AS new_id")
                        r = cur.fetchone()
                        if r: real_id = r.get("new_id")
                    if temp_id and real_id:
                        id_map[int(temp_id)] = int(real_id)

                elif tbl == "academic_periods":
                    st_id = data.get("student_id")
                    if st_id is not None:
                        try:
                            st_id_int = int(st_id)
                            st_id = id_map.get(st_id_int, st_id_int)
                        except (ValueError, TypeError):
                            pass
                    yr = data.get("academic_year", "")
                    stg = int(data.get("stage_number") or 1)
                    sem = int(data.get("semester_num") or 1)
                    raw_st = result_status_code(data.get("result_status", "PASSED"))

                    try:
                        cur.callproc("InsertAcademicPeriod", (st_id, yr, stg, sem, str(raw_st)))
                        real_id = None
                        if hasattr(cur, "stored_results"):
                            for res in cur.stored_results():
                                row = res.fetchone()
                                if row and ("new_period_id" in row or "new_id" in row):
                                    real_id = row.get("new_period_id") or row.get("new_id")
                                    break
                        try:
                            while cur.nextset(): pass
                        except Exception: pass
                        if real_id is None:
                            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
                            r = cur.fetchone()
                            if r: real_id = r.get("new_id")
                    except Exception as ins_err:
                        cur.execute(
                            "SELECT id FROM academic_periods WHERE student_id=%s AND stage_number=%s AND semester_num=%s",
                            (st_id, stg, sem)
                        )
                        r = cur.fetchone()
                        if r:
                            real_id = r["id"]
                        else:
                            raise ins_err

                    if temp_id and real_id:
                        id_map[int(temp_id)] = int(real_id)

                elif tbl == "enrollments":
                    pid = data.get("period_id")
                    if pid is not None:
                        try:
                            pid_int = int(pid)
                            pid = id_map.get(pid_int, pid_int)
                        except (ValueError, TypeError):
                            pass
                    cid = data.get("course_id")
                    score = float(data.get("score") or 0.0)
                    pr = int(data.get("passed_round") or 1)

                    try:
                        cur.callproc("InsertEnrollment", (pid, cid, score, pr))
                        real_id = None
                        if hasattr(cur, "stored_results"):
                            for res in cur.stored_results():
                                row = res.fetchone()
                                if row and ("new_enrollment_id" in row or "new_id" in row):
                                    real_id = row.get("new_enrollment_id") or row.get("new_id")
                                    break
                        try:
                            while cur.nextset(): pass
                        except Exception: pass
                        if real_id is None:
                            cur.execute("SELECT LAST_INSERT_ID() AS new_id")
                            r = cur.fetchone()
                            if r: real_id = r.get("new_id")
                    except Exception as ins_err:
                        cur.execute(
                            "SELECT id FROM enrollments WHERE period_id=%s AND course_id=%s",
                            (pid, cid)
                        )
                        r = cur.fetchone()
                        if r:
                            real_id = r["id"]
                            cur.callproc("UpdateEnrollment", (real_id, score, pr))
                            try:
                                while cur.nextset(): pass
                            except Exception: pass
                        else:
                            raise ins_err

                    if temp_id and real_id:
                        id_map[int(temp_id)] = int(real_id)

                elif tbl == "issued_certificates":
                    st_id = data.get("student_id")
                    to_title = data.get("to_title", "من يهمه الأمر")
                    tmpl = data.get("template_type", "graduation")
                    idate = data.get("issue_date") or datetime.now().strftime("%Y-%m-%d")
                    cert_num = data.get("certificate_number")
                    cur.callproc("InsertIssuedCertificate", (st_id, to_title, tmpl, str(idate), cert_num))
                    real_id = None
                    if hasattr(cur, "stored_results"):
                        for res in cur.stored_results():
                            row = res.fetchone()
                            if row and ("new_id" in row or "inserted_id" in row):
                                real_id = row.get("new_id") or row.get("inserted_id")
                                break
                    try:
                        while cur.nextset():
                            pass
                    except Exception:
                        pass
                    if real_id is None:
                        cur.execute("SELECT LAST_INSERT_ID() AS new_id")
                        r = cur.fetchone()
                        if r: real_id = r.get("new_id")
                    if temp_id and real_id:
                        id_map[int(temp_id)] = int(real_id)

            elif op == "UPDATE":
                if tbl == "students":
                    target_id = temp_id if temp_id > 0 else data.get("id")
                    if target_id and target_id in id_map:
                        target_id = id_map[target_id]
                    if target_id and target_id > 0:
                        sp_args = (
                            target_id,
                            data.get("full_name_ar"),
                            data.get("full_name_en"),
                            int(data.get("gender") or 1),
                            data.get("sequence_number"),
                            data.get("postgraduation_number"),
                            data.get("date_of_birth"),
                            data.get("birthplace_id"),
                            data.get("birthplace_other"),
                            int(data.get("nationality_id") or 1),
                            data.get("national_id"),
                            data.get("department_id"),
                            int(data.get("study_system_id") or 1),
                            int(data.get("degree_level") or 1),
                            data.get("order_id"),
                            data.get("admission_year"),
                            data.get("summer_training_data"),
                            data.get("average"),
                            data.get("graduation_date"),
                            data.get("graduation_semester") or "first"
                        )
                        cur.callproc("UpdateStudent", sp_args)
                        try:
                            while cur.nextset(): pass
                        except Exception: pass

                elif tbl == "enrollments":
                    target_id = temp_id if temp_id > 0 else data.get("id")
                    if target_id and target_id in id_map:
                        target_id = id_map[target_id]
                    if target_id and target_id > 0:
                        score = float(data.get("score") or 0.0)
                        pr = int(data.get("passed_round") or 1)
                        cur.callproc("UpdateEnrollment", (target_id, score, pr))
                        try:
                            while cur.nextset(): pass
                        except Exception: pass

                elif tbl == "academic_periods":
                    target_id = temp_id if temp_id > 0 else data.get("id")
                    if target_id and target_id in id_map:
                        target_id = id_map[target_id]
                    if target_id and target_id > 0:
                        if "result_status" in data:
                            raw_st = str(result_status_code(data.get("result_status")))
                            cur.callproc("UpdateAcademicPeriodStatus", (target_id, raw_st))
                            try:
                                while cur.nextset(): pass
                            except Exception: pass

            elif op == "DELETE":
                target_id = temp_id if temp_id > 0 else data.get("id")
                if target_id and target_id in id_map:
                    target_id = id_map[target_id]
                if target_id and target_id > 0:
                    if tbl == "students":
                        cur.callproc("DeleteStudent", (target_id,))
                        try:
                            while cur.nextset(): pass
                        except Exception: pass
                    elif tbl == "academic_periods":
                        cur.callproc("DeleteAcademicPeriod", (target_id,))
                        try:
                            while cur.nextset(): pass
                        except Exception: pass
                    elif tbl == "enrollments":
                        cur.callproc("DeleteEnrollment", (target_id,))
                        try:
                            while cur.nextset(): pass
                        except Exception: pass

        conn.commit()
        return {"status": "success", "id_map": id_map}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()
