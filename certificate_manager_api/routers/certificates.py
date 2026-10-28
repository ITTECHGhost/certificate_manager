"""Certificate data and lookups routes: /certificates/* /api/certificates/* /lookups/*."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from deps import get_db, decode_db_value, execute_sp_fetchall

router = APIRouter()


# ===========================================================================
# 11. Certificates & Transcripts Module
# ===========================================================================

@router.get("/certificates/{student_id}")
@router.get("/api/certificates/{student_id}")
def get_certificate_raw_data(student_id: int, grouping_mode: str = Query("DEFAULT"), conn=Depends(get_db)):
    try:
        cur = conn.cursor(dictionary=True)
        try:
            cur.callproc("sp_GetFullCertificateData", (student_id, grouping_mode))
            result_sets = []
            if hasattr(cur, "stored_results"):
                for result in cur.stored_results():
                    rows = decode_db_value(result.fetchall())
                    result_sets.append(rows)
            try:
                while cur.nextset():
                    pass
            except Exception:
                pass

            student_info_list = result_sets[0] if len(result_sets) > 0 and result_sets[0] else []
            ranking_list = result_sets[1] if len(result_sets) > 1 and result_sets[1] else []
            signers_list = result_sets[2] if len(result_sets) > 2 else []
            timeline_list = result_sets[3] if len(result_sets) > 3 else []
            courses_list = result_sets[4] if len(result_sets) > 4 else []

            settings_list = []
            if student_info_list and isinstance(student_info_list[0], dict):
                s = student_info_list[0]
                settings_list = [{
                    "id": s.get("university_settings_id") or s.get("id"),
                    "univ_name_ar": s.get("univ_name_ar", ""),
                    "univ_name_en": s.get("univ_name_en", ""),
                    "college_name_ar": s.get("college_name_ar", ""),
                    "college_name_en": s.get("college_name_en", ""),
                }]

            return {
                "student_id": student_id,
                "grouping_mode": grouping_mode,
                "settings": settings_list,
                "student_info": student_info_list,
                "ranking": ranking_list,
                "signers": signers_list,
                "academic_timeline": timeline_list,
                "courses_grouped": courses_list
            }
        finally:
            cur.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class AcademicFlatRecord(BaseModel):
    student_id: int
    student_name_ar: str
    study_system_ar: Optional[str] = ""
    academic_year: Optional[str] = ""
    stage_number: Optional[int] = 1
    stage_name_ar: Optional[str] = ""
    course_id: Optional[int] = 0
    course_code: Optional[str] = ""
    course_name_ar: Optional[str] = ""
    course_name_en: Optional[str] = ""
    units: Optional[float] = 0.0
    mark: Optional[float] = 0.0
    result_status_code: Optional[int] = 1
    result_status_label: Optional[str] = "PASSED"


@router.get("/certificates/flat-yearly/{student_id}")
def get_flat_yearly_certificate_courses(student_id: int, grouping_mode: str = Query("DEFAULT"), conn=Depends(get_db)):
    cur = conn.cursor(dictionary=True)
    try:
        try:
            cur.callproc("sp_GetCertificate_Yearly_ByAcademicDefualte", (student_id,))
        except Exception:
            try:
                cur.callproc("sp_GetCertificate_Courses_Yearly_ByAcademicDefualte", (student_id,))
            except Exception:
                cur.callproc("sp_GetCertificate_AcademicCourses", (student_id, grouping_mode))

        rows = []
        if hasattr(cur, "stored_results"):
            for result in cur.stored_results():
                rows = result.fetchall()
                break
        try:
            while cur.nextset():
                pass
        except Exception:
            pass

        return decode_db_value(rows)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        cur.close()


# ===========================================================================
# 12. Lookups Module
# ===========================================================================

@router.get("/lookups/countries")
def get_countries(conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAllCountries")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/lookups/governorates")
def get_governorates(conn=Depends(get_db)):
    try:
        return execute_sp_fetchall(conn, "GetAllGovernorates")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
