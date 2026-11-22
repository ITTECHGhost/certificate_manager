# =============================================================================
# services/extraction_review.py — logic behind the «مراجعة الاستخراج» dialog
# Pure functions (no UI, no network): flag suspicious grade rows, edit one
# score/meta field and recompute the average the same way parse_grades_file does.
# Rows are the dicts returned by services.excel_import_service.parse_grades_file.
# =============================================================================
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Sequence

from utils.order_number import normalize_order_number

REASON_AVG = "المعدل خارج 50–100"
REASON_SCORE = "درجة خارج 0–100"
REASON_MISSING = "مواد ناقصة"
REASON_DUP = "رقم وطني مكرر"
REASON_NAME = "الاسم لا يطابق طالبًا مرفوعًا"

AVG_MIN, AVG_MAX = 50.0, 100.0


def _norm(name: Any) -> str:
    return " ".join(str(name or "").split())


def flag_rows(rows: Sequence[Dict[str, Any]], courses: Sequence[Dict[str, Any]],
              known_names: Optional[Sequence[str]] = None) -> List[List[str]]:
    """One list of reasons per row; an empty list = the row looks fine."""
    needed = len(courses)
    known = {_norm(n) for n in known_names} if known_names else None
    counts: Dict[str, int] = {}
    for r in rows:
        nid = str(r.get("national_id") or "").strip()
        if nid and not nid.startswith("GEN_"):
            counts[nid] = counts.get(nid, 0) + 1

    out: List[List[str]] = []
    for r in rows:
        why: List[str] = []
        scores = r.get("scores") or []
        avg = r.get("average")
        if scores and avg is not None and not (AVG_MIN <= float(avg) <= AVG_MAX):
            why.append(REASON_AVG)
        if any(not (0.0 <= float(s.get("score", 0)) <= 100.0) for s in scores):
            why.append(REASON_SCORE)
        if needed and len(scores) < needed:
            why.append(REASON_MISSING)
        nid = str(r.get("national_id") or "").strip()
        if nid and counts.get(nid, 0) > 1:
            why.append(REASON_DUP)
        if known is not None and _norm(r.get("student_name")) not in known:
            why.append(REASON_NAME)
        out.append(why)
    return out


def _recompute(row: Dict[str, Any]) -> None:
    scores = row.get("scores") or []
    total_units = sum(float(s.get("credit_hours") or 3) for s in scores)
    if total_units > 0:
        weighted = sum(float(s["score"]) * float(s.get("credit_hours") or 3) for s in scores)
        row["average"] = round(weighted / total_units, 3)
    else:
        row["average"] = 0.0
    row["scores_count"] = len(scores)


def set_score(row: Dict[str, Any], course_id: int, value: Optional[float],
              courses: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Copy of `row` with one course score set (None removes it). Out-of-range values are
    kept on purpose so the row stays flagged until a person fixes them."""
    new = copy.deepcopy(row)
    scores = new.setdefault("scores", [])
    scores[:] = [s for s in scores if int(s["course_id"]) != int(course_id)] if value is None else scores
    if value is not None:
        existing = next((s for s in scores if int(s["course_id"]) == int(course_id)), None)
        if existing:
            existing["score"] = float(value)
        else:
            crs = next((c for c in courses if int(c["id"]) == int(course_id)), {})
            scores.append({
                "course_id": int(course_id),
                "course_name_ar": crs.get("name_ar", ""),
                "course_name_en": crs.get("name_en", ""),
                "credit_hours": float(crs.get("credit_hours") or 3),
                "score": float(value),
                "passed_round": new.get("passed_round", 1),
                "stage_number": int(crs.get("stage_number") or 1),
            })
    _recompute(new)
    return new


def set_meta(row: Dict[str, Any], student_name: Optional[str] = None,
             passed_round: Optional[int] = None, result_status: Optional[str] = None) -> Dict[str, Any]:
    new = copy.deepcopy(row)
    if student_name is not None:
        new["student_name"] = _norm(student_name)
        new["student_name_norm"] = new["student_name"]
    if passed_round is not None:
        new["passed_round"] = int(passed_round)
        for s in new.get("scores") or []:
            s["passed_round"] = int(passed_round)
    if result_status is not None:
        new["result_status"] = result_status
    return new


def order_number_problem(raw: Any) -> Optional[str]:
    """Arabic message when the order number can't be normalised safely, else None."""
    res = normalize_order_number(raw)
    if res.needs_review:
        return "رقم الأمر غير واضح؛ راجعه يدويًا (مثل 20707/12/3)"
    return None
