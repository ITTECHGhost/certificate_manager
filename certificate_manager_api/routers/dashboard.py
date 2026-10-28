"""Dashboard routes: /api/dashboard/*."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import logger, get_db

router = APIRouter()


# ===========================================================================
# 14. Dashboard Counts Module
# ===========================================================================

class DashboardCountsResponse(BaseModel):
    total_students: int
    total_departments: int
    total_courses: int
    total_personnel: int


@router.get("/api/dashboard/counts", response_model=DashboardCountsResponse)
def get_dashboard_counts(conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        result = None
        for sp_name in ("Get_dashboard_counts", "GetDashboardCounts"):
            try:
                cur.callproc(sp_name)
                if hasattr(cur, "stored_results"):
                    for r in cur.stored_results():
                        result = r.fetchone()
                        if result:
                            break
                try:
                    while cur.nextset():
                        pass
                except Exception:
                    pass
                if result:
                    break
            except Exception as sp_exc:
                logger.debug(f"{sp_name} SP call attempt failed: {sp_exc}")

        if not result:
            return DashboardCountsResponse(
                total_students=0,
                total_departments=0,
                total_courses=0,
                total_personnel=0
            )


        return DashboardCountsResponse(
            total_students=result.get("total_students", 0),
            total_departments=result.get("total_departments", 0),
            total_courses=result.get("total_courses", 0),
            total_personnel=result.get("total_personnel", 0)
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()
