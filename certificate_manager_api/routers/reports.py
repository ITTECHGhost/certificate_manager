# =============================================================================
# certificate_manager_api/routers/reports.py — «تقارير الطلاب»: counts and lists of students
# Filters and group-by columns are whitelisted here; nothing from the request reaches SQL text.
# =============================================================================

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from deps import get_db

router = APIRouter(prefix="/api/reports", tags=["reports"])

IRAQ = 274
STATUS_SQL = "IF(s.order_id IS NULL OR s.order_id = 0, 'not_graduated', 'graduated')"
NATIONALITY_SQL = f"IF(s.nationality_id = {IRAQ}, 'iraqi', 'other')"

# group key -> (SQL expression, label SQL)
GROUPS = {
    "department": ("s.department_id", "COALESCE(d.name_ar, '-')"),
    "study_system": ("s.study_system_id", "COALESCE(ss.name_ar, '-')"),
    "gender": ("s.gender", "CASE s.gender WHEN 1 THEN 'ذكر' WHEN 2 THEN 'أنثى' ELSE '-' END"),
    "nationality": (NATIONALITY_SQL, f"IF(s.nationality_id = {IRAQ}, 'عراقي', 'غير عراقي')"),
    "status": (STATUS_SQL, "IF(s.order_id IS NULL OR s.order_id = 0, 'غير متخرج', 'متخرج')"),
    "graduation_year": ("COALESCE(o.graduation_year, s.expected_graduation_year)",
                        "COALESCE(CONCAT(COALESCE(o.graduation_year, s.expected_graduation_year), '/', "
                        "COALESCE(o.graduation_year, s.expected_graduation_year) + 1), '-')"),
    "semester": ("COALESCE(o.graduation_semester, s.expected_graduation_semester, '')",
                 "CASE COALESCE(o.graduation_semester, s.expected_graduation_semester, '') "
                 "WHEN 'first' THEN 'الأول' WHEN 'second' THEN 'الثاني' WHEN 'summer' THEN 'الصيفي' ELSE '-' END"),
    "admission_year": ("LEFT(COALESCE(s.admission_year, ''), 4)", "COALESCE(NULLIF(s.admission_year, ''), '-')"),
    "order": ("s.order_id", "COALESCE(o.order_number, '-')"),
}

FROM = ("FROM students s "
        "LEFT JOIN departments d ON d.id = s.department_id "
        "LEFT JOIN study_systems ss ON ss.id = s.study_system_id "
        "LEFT JOIN graduation_orders o ON o.id = s.order_id ")


def build_where(department_id=None, study_system_id=None, gender=None, nationality=None, status=None,
                graduation_year=None, semester=None, admission_year=None, name=None) -> tuple[str, list]:
    where, params = [], []
    if department_id:
        where.append("s.department_id = %s"); params.append(int(department_id))
    if study_system_id:
        where.append("s.study_system_id = %s"); params.append(int(study_system_id))
    if gender in (1, 2, "1", "2"):
        where.append("s.gender = %s"); params.append(int(gender))
    if nationality in ("iraqi", "other"):
        where.append(f"{NATIONALITY_SQL} = %s"); params.append(nationality)
    if status in ("graduated", "not_graduated"):
        where.append(f"{STATUS_SQL} = %s"); params.append(status)
    if graduation_year:
        where.append("COALESCE(o.graduation_year, s.expected_graduation_year) = %s"); params.append(int(graduation_year))
    if semester in ("first", "second", "summer"):
        where.append("COALESCE(o.graduation_semester, s.expected_graduation_semester) = %s"); params.append(semester)
    if admission_year:
        where.append("LEFT(s.admission_year, 4) = %s"); params.append(str(int(admission_year)))
    if name and name.strip():
        where.append("(s.full_name_ar LIKE %s OR s.full_name_en LIKE %s)"); params += [f"%{name.strip()}%"] * 2
    return ("WHERE " + " AND ".join(where)) if where else "", params


@router.get("/students")
def students_report(department_id: Optional[int] = None, study_system_id: Optional[int] = None,
                    gender: Optional[int] = None, nationality: Optional[str] = None,
                    status: Optional[str] = None, graduation_year: Optional[int] = None,
                    semester: Optional[str] = None, admission_year: Optional[int] = None,
                    name: Optional[str] = None, group_by: str = "department", then_by: str = "",
                    list_limit: int = 2000, conn=Depends(get_db)):
    keys = [k for k in (group_by, then_by) if k]
    bad = [k for k in keys if k not in GROUPS]
    if bad:
        raise HTTPException(status_code=400, detail=f"Unknown group: {bad[0]}")
    where, params = build_where(department_id, study_system_id, gender, nationality, status,
                                graduation_year, semester, admission_year, name)
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT COUNT(*) AS total, "
            f"SUM({STATUS_SQL} = 'graduated') AS graduated, "
            "SUM(s.gender = 1) AS male, SUM(s.gender = 2) AS female, "
            "ROUND(AVG(IF(s.average BETWEEN 0 AND 100, s.average, NULL)), 2) AS avg_average "
            f"{FROM} {where}", params)
        summary = {k: (float(v) if k == "avg_average" and v is not None else int(v or 0))
                   for k, v in cur.fetchone().items()}

        groups = []
        if keys:
            select = ", ".join(f"{GROUPS[k][1]} AS `{k}`" for k in keys)
            group = ", ".join(GROUPS[k][0] for k in keys)
            cur.execute(
                f"SELECT {select}, COUNT(*) AS count, SUM(s.gender = 1) AS male, SUM(s.gender = 2) AS female, "
                f"SUM({STATUS_SQL} = 'graduated') AS graduated, "
                "ROUND(AVG(IF(s.average BETWEEN 0 AND 100, s.average, NULL)), 2) AS avg_average "
                f"{FROM} {where} GROUP BY {group}, {', '.join(GROUPS[k][1] for k in keys)} "
                f"ORDER BY {', '.join(f'`{k}`' for k in keys)}", params)
            for row in cur.fetchall():
                row = {k: (float(v) if k == "avg_average" and v is not None else
                           int(v) if k in ("count", "male", "female", "graduated") else v) for k, v in row.items()}
                groups.append(row)

        cur.execute(
            "SELECT s.id, s.full_name_ar, COALESCE(d.name_ar, '') AS department, COALESCE(ss.name_ar, '') AS study_system, "
            "CASE s.gender WHEN 1 THEN 'ذكر' WHEN 2 THEN 'أنثى' ELSE '-' END AS gender, "
            f"IF(s.nationality_id = {IRAQ}, 'عراقي', 'غير عراقي') AS nationality, "
            "COALESCE(s.admission_year, '') AS admission_year, "
            "COALESCE(o.graduation_year, s.expected_graduation_year) AS graduation_year, "
            "COALESCE(o.order_number, '') AS order_number, s.average "
            f"{FROM} {where} ORDER BY d.name_ar, s.full_name_ar LIMIT %s",
            (*params, max(1, min(int(list_limit), 20000))))
        students = cur.fetchall()
        for st in students:
            if st.get("average") is not None:
                st["average"] = float(st["average"])
        return {"summary": summary, "groups": groups, "group_keys": keys, "students": students}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()
