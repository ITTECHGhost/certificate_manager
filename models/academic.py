# =============================================================================
# models/academic.py — Pydantic Schemas & Academic Result Status Enum
# =============================================================================

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class AcademicResultStatus(str, Enum):
    """Allowed result status values for an academic period."""
    PASSED = "PASSED"
    CARRIED_OVER = "CARRIED_OVER"
    EXCEPTIONAL_PASS = "EXCEPTIONAL_PASS"
    FAILED_REPEAT = "FAILED_REPEAT"
    DEFERRED = "DEFERRED"
    DISMISSED = "DISMISSED"


class AcademicPeriodBase(BaseModel):
    student_id: int
    academic_year: str
    study_system_id: int = 1
    stage_number: int = 1
    semester_num: int = 1
    result_status: AcademicResultStatus = AcademicResultStatus.PASSED


class AcademicPeriodCreate(AcademicPeriodBase):
    pass


class AcademicPeriodUpdate(BaseModel):
    academic_year: Optional[str] = None
    study_system_id: Optional[int] = None
    stage_number: Optional[int] = None
    semester_num: Optional[int] = None
    result_status: Optional[AcademicResultStatus] = None


class AcademicPeriodStatusUpdate(BaseModel):
    result_status: AcademicResultStatus


class CourseEnrollmentItem(BaseModel):
    id: int
    period_id: int
    course_id: int
    score: Optional[float] = None
    passed_round: str = "1"
    course_name_ar: Optional[str] = None
    course_name_en: Optional[str] = None
    credit_hours: Optional[int] = 1


class AcademicPeriodResponse(AcademicPeriodBase):
    id: int
    enrollments: List[CourseEnrollmentItem] = []


class CertificateStageGroup(BaseModel):
    stage_number: int
    academic_year: str
    stage_name_ar: str
    stage_name_en: str
    courses: List[CourseEnrollmentItem] = []


class CertificatePreviewResponse(BaseModel):
    student_id: int
    full_name_ar: str
    full_name_en: str
    study_system_id: int
    is_annual: bool
    stages: List[CertificateStageGroup] = []
