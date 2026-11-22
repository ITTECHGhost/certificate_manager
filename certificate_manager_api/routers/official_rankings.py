# =============================================================================
# certificate_manager_api/routers/official_rankings.py — قوائم الترتيب الرسمية
# A ranking list comes with a college order; the certificate takes the student's rank
# from it. Saving a list is one transaction (header + every entry, or nothing).
# =============================================================================

import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import get_db

router = APIRouter(prefix="/api/official-rankings", tags=["official-rankings"])

LIST_TYPES = ("jobs", "masters")
STUDY_TYPES = ("morning", "evening", "parallel")
ROUNDS = ("1", "2")

_AR_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})
_AR_MARKS = re.compile(r"[ً-ْـ‌-‏\s\.\-_/]")


def normalize_name(name: str) -> str:
    """Folds the spellings that differ between an order's list and the database:
    hamza forms, ta marbuta, alif maqsura, diacritics, tatweel and every space
    ('عبد الحسين' == 'عبدالحسين')."""
    return _AR_MARKS.sub("", str(name or "").translate(_AR_FOLD))


def match_names(names: List[str], students: List[dict]) -> List[Optional[int]]:
    """Student id for each written name: an exact match after normalize_name, and only when
    exactly one student has it. Otherwise None (the user picks the student by hand)."""
    index: dict = {}
    for s in students:
        index.setdefault(normalize_name(s.get("full_name_ar")), []).append(s["id"])
    out = []
    for n in names:
        ids = index.get(normalize_name(n)) or []
        out.append(ids[0] if len(ids) == 1 else None)
    return out


class EntryPayload(BaseModel):
    position: int
    name_written: Optional[str] = ""
    average: Optional[float] = None
    student_id: Optional[int] = None


class RankingPayload(BaseModel):
    list_type: str
    title: Optional[str] = ""
    order_number: Optional[str] = ""
    order_date: Optional[str] = None
    department_id: Optional[int] = None
    study_type: Optional[str] = None
    exam_round: Optional[str] = None
    academic_year: Optional[str] = ""
    created_by: Optional[int] = None
    entries: List[EntryPayload]


class MatchPayload(BaseModel):
    department_id: Optional[int] = None
    names: List[str]


def _check(p: RankingPayload) -> None:
    if p.list_type not in LIST_TYPES:
        raise HTTPException(422, "list_type must be jobs or masters")
    if p.study_type and p.study_type not in STUDY_TYPES:
        raise HTTPException(422, "bad study_type")
    if p.exam_round and p.exam_round not in ROUNDS:
        raise HTTPException(422, "exam_round must be 1 or 2")
    if not p.department_id:
        raise HTTPException(422, "department_id is required")
    if p.list_type == "jobs" and not (p.study_type and p.exam_round):
        raise HTTPException(422, "a jobs list needs study_type and exam_round")
    if not p.entries:
        raise HTTPException(422, "the list is empty")
    positions = [e.position for e in p.entries]
    if len(set(positions)) != len(positions) or min(positions) < 1:
        raise HTTPException(422, "positions must be unique and start from 1")


PAGE_PERMISSIONS = ("page:rankings",)   # same key the sidebar uses for the page


def _require_user(conn, personnel_id: Optional[int]) -> None:
    """Refuse a write unless personnel_id is an active account that is an admin or was granted the
    rankings page (page:rankings). NOTE: the server has no per-user token yet (known gap,
    docs/PLAN_archive_and_next.md), so this trusts the id the client sends."""
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
    if not granted.intersection(PAGE_PERMISSIONS):
        raise HTTPException(403, "No permission for official ranking lists")


def _has_soft_delete(conn) -> bool:
    """True once migration 0010 ran (official_rankings.deleted_at exists)."""
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        cur.execute("SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = 'official_rankings' AND COLUMN_NAME = 'deleted_at'")
        row = cur.fetchone()
        return bool(row and row.get("n"))
    finally:
        cur.close()


def _paging(page: int, page_size: int) -> tuple:
    page = max(1, int(page or 1))
    page_size = min(100, max(1, int(page_size or 25)))
    return page, page_size, (page - 1) * page_size


def _like(search: str) -> str:
    q = str(search or "").strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return "%" + q + "%"


@router.get("/page")
def rankings_page(search: str = "", page: int = 1, page_size: int = 25,
                  department_id: Optional[int] = None, conn=Depends(get_db)):
    """One page of lists, newest first. Search: order number, title, year or department name."""
    page, page_size, offset = _paging(page, page_size)
    where, params = ["1 = 1"], []
    if _has_soft_delete(conn):
        where.append("r.deleted_at IS NULL")
    if department_id:
        where.append("r.department_id = %s")
        params.append(department_id)
    if str(search or "").strip():
        like = _like(search)
        where.append("(r.order_number LIKE %s OR r.title LIKE %s OR r.academic_year LIKE %s OR d.name_ar LIKE %s)")
        params += [like, like, like, like]
    w = " AND ".join(where)
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT COUNT(*) AS n FROM official_rankings r LEFT JOIN departments d ON d.id = r.department_id "
                    "WHERE " + w, tuple(params))
        total = int((cur.fetchone() or {}).get("n") or 0)
        cur.execute(
            "SELECT r.id, r.list_type, r.title, r.order_number, DATE_FORMAT(r.order_date, '%Y-%m-%d') AS order_date, "
            "r.department_id, COALESCE(d.name_ar, '') AS department_name, r.study_type, r.exam_round, r.academic_year, "
            "COUNT(e.position) AS total, SUM(e.student_id IS NOT NULL) AS matched "
            "FROM official_rankings r LEFT JOIN departments d ON d.id = r.department_id "
            "LEFT JOIN official_ranking_entries e ON e.ranking_id = r.id "
            "WHERE " + w + " GROUP BY r.id ORDER BY r.id DESC LIMIT %s OFFSET %s",
            tuple(params) + (page_size, offset))
        items = [{**r, "matched": int(r.get("matched") or 0)} for r in cur.fetchall()]
        return {"items": items, "total": total, "page": page, "page_size": page_size}
    finally:
        cur.close()


@router.get("/{ranking_id}/entries-page")
def ranking_entries_page(ranking_id: int, search: str = "", only_unlinked: bool = False,
                         page: int = 1, page_size: int = 50, conn=Depends(get_db)):
    """One page of a list's names. Search: written name, linked student name or position."""
    page, page_size, offset = _paging(page, page_size)
    where, params = ["e.ranking_id = %s"], [ranking_id]
    if only_unlinked:
        where.append("e.student_id IS NULL")
    q = str(search or "").strip()
    if q:
        like = _like(q)
        where.append("(e.name_written LIKE %s OR s.full_name_ar LIKE %s OR e.position = %s)")
        params += [like, like, int(q) if q.isdigit() else -1]
    w = " AND ".join(where)
    cur = conn.cursor(dictionary=True)
    try:
        base = "FROM official_ranking_entries e LEFT JOIN students s ON s.id = e.student_id WHERE " + w
        cur.execute("SELECT COUNT(*) AS n " + base, tuple(params))
        total = int((cur.fetchone() or {}).get("n") or 0)
        cur.execute("SELECT e.position, e.name_written, e.average, e.student_id, COALESCE(s.full_name_ar, '') AS student_name "
                    + base + " ORDER BY e.position LIMIT %s OFFSET %s", tuple(params) + (page_size, offset))
        items = [{**r, "average": float(r["average"]) if r.get("average") is not None else None} for r in cur.fetchall()]
        return {"items": items, "total": total, "page": page, "page_size": page_size}
    finally:
        cur.close()


@router.get("")
def list_rankings(conn=Depends(get_db)):
    soft = "WHERE r.deleted_at IS NULL " if _has_soft_delete(conn) else ""
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT r.id, r.list_type, r.title, r.order_number, DATE_FORMAT(r.order_date, '%Y-%m-%d') AS order_date, "
            "r.department_id, COALESCE(d.name_ar, '') AS department_name, r.study_type, r.exam_round, r.academic_year, "
            "COUNT(e.position) AS total, SUM(e.student_id IS NOT NULL) AS matched "
            "FROM official_rankings r LEFT JOIN departments d ON d.id = r.department_id "
            "LEFT JOIN official_ranking_entries e ON e.ranking_id = r.id "
            + soft + "GROUP BY r.id ORDER BY r.id DESC")
        return [{**r, "matched": int(r.get("matched") or 0)} for r in cur.fetchall()]
    finally:
        cur.close()


@router.get("/{ranking_id}/entries")
def ranking_entries(ranking_id: int, conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT e.position, e.name_written, e.average, e.student_id, COALESCE(s.full_name_ar, '') AS student_name "
                    "FROM official_ranking_entries e LEFT JOIN students s ON s.id = e.student_id "
                    "WHERE e.ranking_id = %s ORDER BY e.position", (ranking_id,))
        return [{**r, "average": float(r["average"]) if r.get("average") is not None else None} for r in cur.fetchall()]
    finally:
        cur.close()


@router.post("")
def save_ranking(p: RankingPayload, conn=Depends(get_db)):
    _check(p)
    _require_user(conn, p.created_by)
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO official_rankings (list_type, title, order_number, order_date, department_id, study_type, "
            "exam_round, academic_year, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (p.list_type, p.title or "", p.order_number or "", p.order_date or None, p.department_id,
             p.study_type or None, p.exam_round or None, p.academic_year or "", p.created_by))
        rid = cur.lastrowid
        cur.executemany(
            "INSERT INTO official_ranking_entries (ranking_id, position, student_id, name_written, average) "
            "VALUES (%s, %s, %s, %s, %s)",
            [(rid, e.position, e.student_id, (e.name_written or "")[:255], e.average) for e in p.entries])
        conn.commit()
        return {"id": rid, "saved": len(p.entries)}
    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(500, f"Nothing was saved: {exc}")
    finally:
        cur.close()


@router.put("/{ranking_id}/entries/{position}")
def set_entry_student(ranking_id: int, position: int, student_id: Optional[int] = None,
                      personnel_id: Optional[int] = None, conn=Depends(get_db)):
    """Links (or unlinks) one row of the list to a student after the import."""
    _require_user(conn, personnel_id)
    cur = conn.cursor()
    try:
        cur.execute("UPDATE official_ranking_entries SET student_id = %s WHERE ranking_id = %s AND position = %s",
                    (student_id, ranking_id, position))
        conn.commit()
        return {"updated": cur.rowcount}
    finally:
        cur.close()


@router.delete("/{ranking_id}")
def delete_ranking(ranking_id: int, personnel_id: Optional[int] = None, conn=Depends(get_db)):
    """Archives the list (soft delete, migration 0010); before the migration it is deleted for real."""
    _require_user(conn, personnel_id)
    soft = _has_soft_delete(conn)
    cur = conn.cursor()
    try:
        if soft:
            cur.execute("UPDATE official_rankings SET deleted_at = NOW(), deleted_by = %s "
                        "WHERE id = %s AND deleted_at IS NULL", (personnel_id, ranking_id))
        else:
            cur.execute("DELETE FROM official_rankings WHERE id = %s", (ranking_id,))   # entries cascade
        conn.commit()
        return {"deleted": cur.rowcount}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(500, f"Nothing was deleted: {exc}")
    finally:
        cur.close()


@router.post("/match")
def match(p: MatchPayload, conn=Depends(get_db)):
    """Student ids for the written names (same department when given)."""
    cur = conn.cursor(dictionary=True)
    try:
        if p.department_id:
            cur.execute("SELECT id, full_name_ar FROM students WHERE department_id = %s", (p.department_id,))
        else:
            cur.execute("SELECT id, full_name_ar FROM students")
        return {"student_ids": match_names(p.names, cur.fetchall())}
    finally:
        cur.close()


@router.get("/for-student/{student_id}")
def for_student(student_id: int, conn=Depends(get_db)):
    """Every official list the student appears in: [{list_type, position, total, order_number, ...}]."""
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT r.id, r.list_type, r.title, r.order_number, DATE_FORMAT(r.order_date, '%Y-%m-%d') AS order_date, "
            "r.study_type, r.exam_round, r.academic_year, e.position, "
            "(SELECT COUNT(*) FROM official_ranking_entries x WHERE x.ranking_id = r.id) AS total, "
            "(SELECT x.average FROM official_ranking_entries x WHERE x.ranking_id = r.id AND x.position = 1) AS first_average "
            "FROM official_ranking_entries e JOIN official_rankings r ON r.id = e.ranking_id "
            "WHERE e.student_id = %s ORDER BY r.id DESC", (student_id,))
        return [{**r, "first_average": float(r["first_average"]) if r.get("first_average") is not None else None}
                for r in cur.fetchall()]
    finally:
        cur.close()
