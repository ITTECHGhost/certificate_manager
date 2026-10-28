# =============================================================================
# data/repositories/study_routines.py — Module 14: Predefined Study Routines
# =============================================================================

from .base import *
from .courses import CourseRepository
from .students import StudentRepository, AcademicPeriodRepository, EnrollmentRepository


class StudyRoutineRepository(BaseRepository):
    def get_all(self, dept_id: int | None = None) -> list[dict]:
        """Fetch all predefined study routines with their linked courses and department info (3-Tier Failover)."""
        routines = []
        if is_online():
            try:
                resp = api_client.get(f"{self.api_url}/study-routines", timeout=3.0)
                if resp.status_code == 200:
                    routines = resp.json()
            except Exception as e:
                log_system(f"API request failed for get_all study routines: {e}", "WARNING")

            if not routines:
                try:
                    routines = self._call_read_all("GetAllStudyRoutines")
                except Exception as sp_err:
                    log_system(f"SP GetAllStudyRoutines fallback error: {sp_err}", "WARNING")

        if not routines:
            routines = get_offline_study_routines(dept_id)

        if dept_id:
            routines = [r for r in routines if r.get("department_id") == dept_id]

        for r in routines:
            rid = r.get("id")
            if rid:
                courses = []
                if is_online():
                    try:
                        c_resp = api_client.get(f"{self.api_url}/study-routine-courses/{rid}", timeout=3.0)
                        if c_resp.status_code == 200:
                            courses = c_resp.json()
                    except Exception:
                        pass
                    if not courses:
                        try:
                            courses = self._call_read_all("GetStudyRoutineCourses", (rid,))
                        except Exception:
                            pass
                if not courses:
                    courses = get_offline_study_routine_period_courses(rid)
                r["courses"] = courses
                r["course_ids"] = [c["id"] for c in courses if isinstance(c, dict) and "id" in c]

        return routines

    def get_by_id(self, routine_id: int) -> dict | None:
        """Fetch a single study routine with full course details."""
        routines = self.get_all()
        for r in routines:
            if r.get("id") == routine_id:
                return r
        return None

    def insert(self, data: dict) -> int:
        """Create a new study routine and link default periods/courses (3-Tier Failover)."""
        name_ar = data.get("name_ar", "")
        name_en = data.get("name_en", "")
        dept_id = int(data.get("department_id") or 1)
        sys_id = int(data.get("study_system_id") or 1)
        course_ids = data.get("course_ids") or []

        if not is_online():
            local_id = insert_offline_study_routine(name_ar, name_en, dept_id, sys_id)
            if local_id:
                for stg in range(1, 5):
                    for sem in (1, 2):
                        self.insert_period({"routine_id": local_id, "stage_number": stg, "semester_num": sem})
            log_activity(f"تم إنشاء روتين دراسي جديد (أوفلاين): {name_ar}")
            return local_id or 1

        new_id = None
        try:
            new_id = self._call_write("InsertStudyRoutine", (name_ar, name_en, dept_id, sys_id))
        except Exception as sp_err:
            log_system(f"SP InsertStudyRoutine error: {sp_err}", "WARNING")
            new_id = insert_offline_study_routine(name_ar, name_en, dept_id, sys_id)

        target_id = new_id or 1

        try:
            for stg in range(1, 5):
                for sem in (1, 2):
                    self.insert_period({"routine_id": target_id, "stage_number": stg, "semester_num": sem})
        except Exception as p_err:
            log_system(f"Error auto-creating routine periods: {p_err}", "WARNING")

        log_activity(f"تم إنشاء روتين دراسي جديد: {name_ar}")
        return target_id

    def update(self, routine_id: int, data: dict) -> None:
        """Update an existing study routine header and sync its metadata."""
        name_ar = data.get("name_ar", "")
        name_en = data.get("name_en", "")
        dept_id = int(data.get("department_id") or 1)
        sys_id = int(data.get("study_system_id") or 1)
        course_ids = data.get("course_ids") or []

        update_offline_study_routine(routine_id, name_ar, name_en, dept_id, sys_id)

        if not is_online():
            log_activity(f"تم تعديل الروتين الدراسي (أوفلاين) ID: {routine_id}")
            return

        try:
            payload = {
                "name_ar": name_ar,
                "name_en": name_en,
                "department_id": dept_id,
                "study_system_id": sys_id,
            }
            resp = api_client.put(f"{self.api_url}/study-routines/{routine_id}", json=payload, timeout=3.0)
            if resp.status_code != 200:
                self._call_write("UpdateStudyRoutine", (routine_id, name_ar, name_en, dept_id, sys_id))
        except Exception as e:
            try:
                self._call_write("UpdateStudyRoutine", (routine_id, name_ar, name_en, dept_id, sys_id))
            except Exception as sp_err:
                log_system(f"SP UpdateStudyRoutine error: {sp_err}", "WARNING")

        for cid in course_ids:
            try:
                api_client.post(
                    f"{self.api_url}/study-routine-courses",
                    json={"routine_id": routine_id, "course_id": cid},
                    timeout=3.0
                )
            except Exception:
                try:
                    self._call_write("InsertStudyRoutineCourse", (routine_id, cid))
                except Exception:
                    pass

        log_activity(f"تم تعديل بيانات الروتين الدراسي ID: {routine_id}")

    def delete(self, routine_id: int) -> None:
        """Delete a study routine and its linked period & course entries (3-Tier Failover)."""
        delete_offline_study_routine(routine_id)

        if not is_online():
            log_activity(f"تم حذف الروتين الدراسي (أوفلاين) ID: {routine_id}")
            return

        api_success = False
        try:
            resp = api_client.delete(f"{self.api_url}/study-routines/{routine_id}", timeout=5.0)
            if resp.status_code == 200:
                api_success = True
                log_activity(f"تم حذف الروتين الدراسي ID: {routine_id} عبر API")
        except Exception as e:
            log_system(f"API request failed for delete study routine: {e}", "WARNING")

        if not api_success:
            try:
                self._call_write("DeleteStudyRoutine", (routine_id,))
                log_activity(f"تم حذف الروتين الدراسي ID: {routine_id} عبر SP")
            except Exception as sp_err:
                log_system(f"SP DeleteStudyRoutine error: {sp_err}", "WARNING")

    def get_periods(self, routine_id: int) -> list[dict]:
        """Fetch periods associated with a study routine (3-Tier Failover)."""
        periods = []
        if is_online():
            try:
                periods = self._call_read_all("GetStudyRoutinePeriods", (routine_id,))
            except Exception as e:
                log_system(f"SP GetStudyRoutinePeriods error: {e}", "WARNING")

        if not periods:
            periods = get_offline_study_routine_periods(routine_id)
        return periods

    def get_period_courses(self, period_id: int) -> list[dict]:
        """Fetch courses associated with a routine period (3-Tier Failover)."""
        courses = []
        if is_online():
            try:
                courses = self._call_read_all("GetStudyRoutinePeriodCourses", (period_id,))
            except Exception as e:
                log_system(f"SP GetStudyRoutinePeriodCourses error: {e}", "WARNING")

        if not courses:
            courses = get_offline_study_routine_period_courses(period_id)
        return courses

    def insert_period(self, data: dict) -> int:
        """Add a stage/semester period to a study routine."""
        routine_id = int(data.get("routine_id") or 0)
        stage = int(data.get("stage_number") or 1)
        sem_num = int(data.get("semester_num") or 1)

        local_id = insert_offline_study_routine_period(routine_id, stage, sem_num)

        if not is_online():
            return local_id or 1

        new_id = None
        try:
            new_id = self._call_write("InsertStudyRoutinePeriod", (routine_id, stage, sem_num))
        except Exception as sp_err:
            log_system(f"SP InsertStudyRoutinePeriod error: {sp_err}", "WARNING")

        return new_id or local_id or 1

    def insert_period_course(self, period_id: int, course_id: int) -> None:
        """Assign a course to a routine period."""
        insert_offline_study_routine_period_course(period_id, course_id)

        if is_online():
            try:
                self._call_write("InsertStudyRoutinePeriodCourse", (period_id, course_id))
            except Exception as sp_err:
                log_system(f"SP InsertStudyRoutinePeriodCourse error: {sp_err}", "WARNING")

    def delete_period(self, period_id: int) -> None:
        """Delete a routine period and unassign its courses."""
        delete_offline_study_routine_period(period_id)

        if is_online():
            try:
                self._call_write("DeleteStudyRoutinePeriod", (period_id,))
            except Exception as sp_err:
                log_system(f"SP DeleteStudyRoutinePeriod error: {sp_err}", "WARNING")

    def delete_period_course(self, period_id: int, course_id: int) -> None:
        """Unassign a course from a routine period."""
        delete_offline_study_routine_period_course(period_id, course_id)

        if is_online():
            try:
                self._call_write("DeleteStudyRoutinePeriodCourse", (period_id, course_id))
            except Exception as sp_err:
                log_system(f"SP DeleteStudyRoutinePeriodCourse error: {sp_err}", "WARNING")

    def apply_routine_to_student(self, student_id: int, routine_id: int, academic_year: str = "") -> dict:
        """
        Applies a comprehensive 4-Year Routine to a student:
        1. Reads routine periods and courses across all stages/semesters.
        2. Groups courses by (stage_number, semester_num).
        3. For each stage/semester group:
           - Calculates academic year relative to student's admission year.
           - Creates/finds matching academic_period for the student.
           - Inserts all routine courses into enrollments (score=0.0, passed_round='1').
        """
        routine = self.get_by_id(routine_id) or {}

        sys_id = routine.get("study_system_id", 1)

        # Build comprehensive course map grouped by (stage_number, semester_num)
        courses_by_stage_sem = {}

        # 1. Read period-based courses
        routine_periods = self.get_periods(routine_id) or []
        for p in routine_periods:
            pid = p.get("id") or p.get("period_id")
            stg = int(p.get("stage_number") or 1)
            sem = int(p.get("semester_num") or 1)
            key = (stg, sem)
            if key not in courses_by_stage_sem:
                courses_by_stage_sem[key] = []

            if pid:
                p_courses = self.get_period_courses(pid) or []
                for pc in p_courses:
                    cid = pc.get("course_id") if (isinstance(pc, dict) and pc.get("course_id") is not None) else (pc.get("id") if isinstance(pc, dict) else None)
                    if cid and not any((c.get("id") == cid or c.get("course_id") == cid) for c in courses_by_stage_sem[key]):
                        courses_by_stage_sem[key].append({
                            "id": cid,
                            "course_id": cid,
                            "stage_number": stg,
                            "semester_num": sem
                        })

        # 2. Also check direct header courses if any
        header_courses = routine.get("courses", []) or []
        for c in header_courses:
            cid = c.get("course_id") if (isinstance(c, dict) and c.get("course_id") is not None) else (c.get("id") if isinstance(c, dict) else None)
            stg = int(c.get("stage_number") or 1)
            sem = int(c.get("semester_num") or 1)
            key = (stg, sem)
            if key not in courses_by_stage_sem:
                courses_by_stage_sem[key] = []
            if cid and not any((existing.get("id") == cid or existing.get("course_id") == cid) for existing in courses_by_stage_sem[key]):
                courses_by_stage_sem[key].append({
                    "id": cid,
                    "course_id": cid,
                    "stage_number": stg,
                    "semester_num": sem
                })

        student_repo = StudentRepository()
        st = student_repo.get_by_id(student_id) if hasattr(student_repo, 'get_by_id') else None
        if not st:
            st_list = student_repo.search_students_paginated("", limit=100)
            st = next((s for s in st_list if s.get("student_id") == student_id or s.get("id") == student_id), {})

        target_dept = routine.get("department_id") or st.get("department_id") or 1

        # If no periods/courses found at all, build default 4 stages x 2 semesters
        if not courses_by_stage_sem:
            for stg in range(1, 5):
                for sem in (1, 2):
                    courses_by_stage_sem[(stg, sem)] = []

        # 3. Fallback: If any stage/semester has no assigned courses in routine,
        # fetch catalog courses for student's department and stage
        course_repo = CourseRepository()
        for (stg, sem), c_list in courses_by_stage_sem.items():
            if not c_list:
                dept_courses = course_repo.get_by_dept_stage_system(target_dept, stg, sys_id) or []
                if not dept_courses:
                    all_dept = course_repo.get_by_department(target_dept) or []
                    dept_courses = [c for c in all_dept if safe_cast(c.get("stage_number"), int, 1) == stg]

                for dc in dept_courses:
                    cid = dc.get("id") or dc.get("course_id")
                    if cid and not any((c.get("id") == cid or c.get("course_id") == cid) for c in c_list):
                        c_list.append({
                            "id": cid,
                            "course_id": cid,
                            "stage_number": stg,
                            "semester_num": sem
                        })

        adm_yr_raw = str(st.get("admission_year") or "2024").strip()
        adm_yr = int(adm_yr_raw) if adm_yr_raw.isdigit() else 2024

        period_repo = AcademicPeriodRepository()
        enroll_repo = EnrollmentRepository()
        existing_periods = period_repo.get_by_student(student_id) or []

        # Map existing periods by (stage_number, semester_num)
        period_map = {}
        for p in existing_periods:
            stg_num = p.get("stage_number")
            sem_n = p.get("semester_num")
            if stg_num and sem_n:
                period_map[(int(stg_num), int(sem_n))] = p

        total_added_courses = 0
        periods_affected = 0

        for (stg, sem), c_list in courses_by_stage_sem.items():
            start_yr = adm_yr + (stg - 1)
            calc_year = f"{start_yr}-{start_yr+1}"

            target_period = period_map.get((stg, sem))
            period_created = False
            if not target_period:
                try:
                    period_id = period_repo.insert(
                        student_id=student_id,
                        year=calc_year,
                        sys_id=sys_id,
                        stage=stg,
                        semester_num=sem
                    )
                    target_period = {"id": period_id, "stage_number": stg, "semester_num": sem}
                    period_map[(stg, sem)] = target_period
                    period_created = True
                except Exception as p_err:
                    log_system(f"Failed to create academic period for Stage {stg} Sem {sem}: {p_err}", "WARNING")
                    continue

            pid = target_period["id"]
            existing_enrs = enroll_repo.get_by_period(pid) or []
            existing_cids = {e.get("course_id") for e in existing_enrs if "course_id" in e}

            added_in_period = 0
            for c in c_list:
                cid = c.get("id") or c.get("course_id")
                if cid and cid not in existing_cids:
                    try:
                        enroll_repo.insert(period_id=pid, course_id=cid, score=0.0, is_second=1)
                        total_added_courses += 1
                        added_in_period += 1
                        existing_cids.add(cid)
                    except Exception as err:
                        log_system(f"Failed to add routine course {cid} to period {pid}: {err}", "WARNING")

            if period_created or added_in_period > 0:
                periods_affected += 1

        log_activity(f"تم تطبيق الروتين الشامل ({routine.get('name_ar')}) على الطالب ID: {student_id} — تم إضافة {total_added_courses} مادة عبر {periods_affected} فترة دراسية")
        return {"periods_affected": periods_affected, "added_courses": total_added_courses}
