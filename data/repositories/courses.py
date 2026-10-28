# =============================================================================
# data/repositories/courses.py — Module 5: Course Catalog
# =============================================================================

from .base import *
from .base import _local_ready, _refreshes_local_copy


class CourseRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        # Local-first: the local copy matches the API row for row (refreshed after every change)
        if not is_online() or _local_ready("courses"):
            return get_offline_courses()
        try:
            resp = api_client.get(f"{self.api_url}/courses", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            raise RuntimeError(f"API returned status code {resp.status_code}")
        except Exception as e:
            log_system(f"API request failed: {e}. Falling back to SQLite cache.", "WARNING")
            return get_offline_courses()

    def get_by_department(self, dept_id: int) -> list[dict]:
        if not is_online():
            return get_offline_courses_by_department(dept_id)
        try:
            resp = api_client.get(f"{self.api_url}/courses/by-dept/{dept_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            raise RuntimeError(f"API returned status code {resp.status_code}")
        except Exception as e:
            log_system(f"API request failed: {e}. Falling back to SQLite cache.", "WARNING")
            return get_offline_courses_by_department(dept_id)

    def get_by_dept_stage_system(self, dept_id: int, stage: int, system_id: int) -> list[dict]:
        if not is_online():
            return get_offline_courses_by_dept_stage_system(dept_id, stage, system_id)
        try:
            resp = api_client.get(
                f"{self.api_url}/courses/by-dept-stage-system",
                params={"dept_id": dept_id, "stage": stage, "system_id": system_id},
                timeout=5.0
            )
            if resp.status_code == 200:
                return resp.json()
            raise RuntimeError(f"API returned status code {resp.status_code}")
        except Exception as e:
            log_system(f"API request failed: {e}. Falling back to SQLite cache.", "WARNING")
            return get_offline_courses_by_dept_stage_system(dept_id, stage, system_id)

    def get_shared_dept_ids(self, course_id: int) -> list[int]:
        return []

    @_refreshes_local_copy("courses")
    def insert(self, data: dict) -> int:
        if not is_online():
            raise OfflineModeError()
        try:
            payload = dict(data)
            payload["credit_hours"] = int(payload["credit_hours"])
            payload["stage_number"] = int(payload["stage_number"])
            if "department_id" in payload and payload["department_id"] is not None:
                payload["department_id"] = int(payload["department_id"])

            resp = api_client.post(f"{self.api_url}/courses", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة مادة دراسية جديدة: {data.get('name_ar')}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    @_refreshes_local_copy("courses")
    def update(self, course_id: int, data: dict) -> None:
        payload = dict(data)
        payload["credit_hours"] = int(payload.get("credit_hours", 3))
        payload["stage_number"] = int(payload.get("stage_number", 1))
        if "department_id" in payload and payload["department_id"] is not None:
            payload["department_id"] = int(payload["department_id"])

        if not is_online():
            update_offline_course(
                course_id,
                payload.get("name_ar"),
                payload.get("name_en"),
                payload["credit_hours"],
                payload.get("department_id"),
                payload["stage_number"]
            )
            return

        try:
            resp = api_client.put(f"{self.api_url}/courses/{course_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل بيانات المادة الدراسية ID: {course_id}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")

            # Sync local SQLite cache
            update_offline_course(
                course_id,
                payload.get("name_ar"),
                payload.get("name_en"),
                payload["credit_hours"],
                payload.get("department_id"),
                payload["stage_number"]
            )
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    @_refreshes_local_copy("courses")
    def delete(self, course_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = api_client.delete(f"{self.api_url}/courses/{course_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف المادة الدراسية ID: {course_id}")
            else:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise
