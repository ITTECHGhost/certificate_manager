# =============================================================================
# ranking.py — graduation sequences calculated from averages
#
# Who counts: students linked to a graduation order, with an average. The order gives the
# year, semester and study system. Sequence = 1 + graduates in the group with a higher
# average, so equal averages share a sequence (1, 2, 2, 4).
# Groups (the year is always the same):
#   term_system  same semester + same study system (= the graduation order)
#   term         same semester, all study systems
#   system       same study system, all semesters
#   year         the whole year
# each for the department (dept_*) and for the whole college (college_*).
# =============================================================================

GROUPS = {
    "term_system": ("semester", "system_id"),
    "term": ("semester",),
    "system": ("system_id",),
    "year": (),
}

LABELS_AR = {
    "term_system": "نفس الفصل ونفس نظام الدراسة",
    "term": "نفس الفصل، كل أنظمة الدراسة",
    "system": "نفس نظام الدراسة، كل الفصول",
    "year": "السنة كاملة",
}


def _avg(row):
    try:
        return round(float(row.get("average")), 4)
    except (TypeError, ValueError):
        return None


def compute_ranks(me: dict, graduates: list) -> dict:
    """me / graduates: dicts with id, department_id, semester, system_id, average (same year).
    Returns {'dept_term_system': {'seq': 3, 'of': 40}, ..., 'first_student_college_seq': {...}}."""
    my_avg = _avg(me)
    rows = [g for g in graduates if _avg(g) is not None]
    out = {}
    for scope in ("dept", "college"):
        for key, fields in GROUPS.items():
            group = [g for g in rows
                     if all(g.get(f) == me.get(f) for f in fields)
                     and (scope == "college" or g.get("department_id") == me.get("department_id"))]
            seq = None
            if my_avg is not None:
                seq = 1 + sum(1 for g in group if _avg(g) > my_avg)
            out[f"{scope}_{key}"] = {"seq": seq, "of": len(group)}

    # The department's top student (this year) and their place in the college list
    dept_rows = [g for g in rows if g.get("department_id") == me.get("department_id")]
    if dept_rows:
        top = max(_avg(g) for g in dept_rows)
        out["first_student_college_seq"] = {"seq": 1 + sum(1 for g in rows if _avg(g) > top),
                                            "of": len(rows), "average": top}
    else:
        out["first_student_college_seq"] = {"seq": None, "of": len(rows), "average": None}
    return out
