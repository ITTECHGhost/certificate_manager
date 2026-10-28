# =============================================================================
# data/repositories/students.py — Students and Module 7: Timelines & Enrollments
# =============================================================================

from .base import *
from .personnel import _RESULT_STATUS_CODES
from .certificates import IssuedCertificateRepository


class StudentRepository(BaseRepository):
    def __init__(self, api_url: str | None = None, local_db_path: str = DB_PATH):
        super().__init__(api_url)
        self._api_base_url = api_url
        self.local_db_path = local_db_path

    @property
    def api_base_url(self) -> str:
        return self._api_base_url or get_api_url()

    @api_base_url.setter
    def api_base_url(self, value: str) -> None:
        self._api_base_url = value

    def search_students_paginated(self, query: str = "", limit: int = 25, offset: int = 0, dept_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Paginated student search route supporting online API endpoint with offline SQLite fallback."""
        if is_online():
            try:
                params = {"query": query, "limit": limit, "offset": offset}
                if dept_id is not None:
                    params["dept_id"] = dept_id
                response = api_client.get(
                    f"{self.api_base_url}/students/search",
                    params=params,
                    timeout=3
                )
                if response.status_code == 200:
                    payload = response.json()
                    return [
                        {
                            "student_id": safe_cast(item.get("student_id"), int, 0),
                            "name_ar": safe_cast(item.get("name_ar"), str, "Unknown"),
                            "name_en": safe_cast(item.get("name_en"), str, "Unknown"),
                            "department_name_ar": safe_cast(item.get("department_name_ar"), str, "Unknown"),
                            "graduation_year": safe_cast(item.get("graduation_year"), str, "N/A"),
                            "average": safe_cast(item.get("average"), float, 0.0)
                        } for item in payload
                    ]
            except Exception as err:
                log_system(f"[WARNING][StudentRepository] API request failed, falling back to SQLite: {err}", "WARNING")

        return search_offline_students_paginated(self.local_db_path, query, limit, offset, dept_id=dept_id)

    def get_last_added_students(self, limit: int = 5) -> list[dict]:
        """Fetch the most recently added students (ordered by id DESC)."""
        return get_offline_last_added_students(limit)

    def get_recent_issued_certificates(self, limit: int = 5) -> list[dict]:
        """Fetch recently issued certificates strictly from issued_certificates table (no graduation_orders fallback)."""
        certs = IssuedCertificateRepository().get_all()
        return certs[:limit] if certs else []

    def get_issued_certificates_report(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        department_id: int | None = None,
        template_type: str | None = None
    ) -> list[dict]:
        """Calls GetIssuedCertificatesReport SP via API or SQLite offline fallback."""
        if is_online():
            try:
                params = {}
                if start_date: params["start_date"] = start_date
                if end_date: params["end_date"] = end_date
                if department_id: params["department_id"] = department_id
                if template_type: params["template_type"] = template_type
                resp = api_client.get(f"{self.api_url}/issued-certificates/report", params=params, timeout=5.0)
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                log_system(f"Failed to fetch issued certificates report via SP API: {e}", "WARNING")

        return get_offline_issued_certificates_report(start_date, end_date, department_id, template_type)

    def get_issued_certificates_by_student(self, student_id: int) -> list[dict]:
        """Calls GetIssuedCertificatesByStudent SP via API or SQLite offline fallback."""
        if is_online():
            try:
                resp = api_client.get(f"{self.api_url}/issued-certificates/by-student/{student_id}", timeout=5.0)
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                log_system(f"API request failed for student issued certs: {e}", "WARNING")

        return get_offline_issued_certificates_by_student(student_id)

    def get_issued_certificate_by_id(self, cert_id: int) -> dict | None:
        """Calls GetIssuedCertificateById SP via API or SQLite offline fallback."""
        if is_online():
            try:
                resp = api_client.get(f"{self.api_url}/issued-certificates/{cert_id}", timeout=5.0)
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                log_system(f"API request failed for issued cert by id: {e}", "WARNING")

        return get_offline_issued_certificate_by_id(cert_id)

    def get_recent_printed_certificates(self, limit: int = 5) -> list[dict]:
        """Fetch recently printed certificates strictly from issued_certificates table."""
        return self.get_recent_issued_certificates(limit=limit)

    def get_recent_graduates(self, limit: int = 5) -> list[dict]:
        """Fetch recently graduated students (students linked to a graduation order)."""
        return self.get_recent_issued_certificates(limit=limit)

    def _inject_missing_graduation_numbers(self, students_list: list[dict]) -> list[dict]:
        """Supplemental fetch for columns omitted by legacy Stored Procedures."""
        if not students_list:
            return students_list

        # Check if the key is missing from the first record
        if students_list and "postgraduation_number" not in students_list[0]:
            try:
                # Extract all IDs currently being processed
                student_ids = [s["id"] for s in students_list if "id" in s]
                if not student_ids: return students_list

                # Use the appropriate connection (MySQL if online, SQLite if offline)
                if is_online():
                    # For supplemental columns when online, fetch via the API endpoint
                    supp_data = {}
                    for sid in student_ids:
                        try:
                            resp = api_client.get(f"{self.api_url}/students/{sid}", timeout=5.0)
                            if resp.status_code == 200:
                                sdata = resp.json()
                                supp_data[sid] = {
                                    "id": sid,
                                    "sequence_number": sdata.get("sequence_number"),
                                    "postgraduation_number": sdata.get("postgraduation_number")
                                }
                        except Exception as e:
                            log_system(f"API supplemental fetch failed for {sid}: {e}", "WARNING")
                else:
                    supp_data = get_offline_student_supplemental_graduation(student_ids)

                # Inject back into the original list (set both keys for robust compatibility)
                for s in students_list:
                    sid = s.get("id")
                    if sid in supp_data:
                        s["sequence_number"] = supp_data[sid].get("sequence_number")
                        s["postgraduation_number"] = supp_data[sid].get("postgraduation_number")

            except Exception as e:
                log_system(f"Supplemental fetch failed: {e}", "WARNING")

        return students_list

    def get_all_paginated(self, limit: int = 25, offset: int = 0, name_query: str = "", dept_id: int = None, year: str | int | None = None) -> list[dict]:
        if not is_online():
            res = get_offline_students_paginated(limit=limit, offset=offset, name_query=name_query, dept_id=dept_id, year=year)
        else:
            try:
                resp = api_client.get(
                    f"{self.api_url}/students/paginated",
                    params={
                        "limit": limit,
                        "offset": offset,
                        "name_query": name_query,
                        "dept_id": dept_id,
                        "year": str(year) if year is not None else None
                    },
                    timeout=5.0
                )
                if resp.status_code == 200:
                    res = resp.json()
                    # Sort online results by ID descending as requested by user
                    if not name_query:
                        res.sort(key=lambda x: x.get("id", 0), reverse=True)
                else:
                    res = []
            except Exception as e:
                log_system(f"API request failed: {e}", "WARNING")
                res = []
        return self._inject_missing_graduation_numbers(res)

    def get_by_id(self, student_id: int) -> dict | None:
        if not is_online():
            res = get_offline_student_by_id(student_id)
        else:
            try:
                resp = api_client.get(f"{self.api_url}/students/{student_id}", timeout=5.0)
                if resp.status_code == 200:
                    res = resp.json()
                else:
                    res = None
            except Exception as e:
                log_system(f"API request failed: {e}", "WARNING")
                res = None
        if res:
            res = self._inject_missing_graduation_numbers([res])[0]
        return res

    def search(self, query: str, limit: int = 8) -> list[dict]:
        clean_query = query.strip()

        # 1. Performance Guard: Mirroring the SP logic, abort if less than 2 chars
        if len(clean_query) < 2:
            return []

        if not is_online():
            res = search_offline_students(clean_query, limit=limit)
        else:
            # 3. Online Mode: FastAPI Call
            try:
                resp = api_client.get(
                    f"{self.api_url}/students/search/all",
                    params={"query": clean_query, "limit": limit},
                    timeout=5.0
                )
                if resp.status_code == 200:
                    res = resp.json()
                else:
                    res = []
            except Exception as e:
                log_system(f"API request failed: {e}", "WARNING")
                res = []

        # 4. Map back to standard dict format and inject missing numbers
        formatted_res = []
        for row in res:
            formatted_res.append({
                "id": row.get("student_id") if "student_id" in row else row.get("id"),
                "full_name_ar": row.get("name_ar") if "name_ar" in row else row.get("full_name_ar"),
                "full_name_en": row.get("name_en") if "name_en" in row else row.get("full_name_en"),
                "dept_name_ar": row.get("dept_name_ar"),
                "admission_year": row.get("admission_year"),
                "graduation_year": row.get("graduation_year"),
                "average": row.get("average")
            })

        return self._inject_missing_graduation_numbers(formatted_res)

    def count(self, name_query: str = "", dept_id: int = None, year: str | int | None = None) -> int:
        if not is_online():
            return count_offline_students(name_query=name_query, dept_id=dept_id, year=year)
        try:
            resp = api_client.get(
                f"{self.api_url}/students/count/all",
                params={
                    "name_query": name_query,
                    "dept_id": dept_id,
                    "year": str(year) if year is not None else None
                },
                timeout=5.0
            )
            if resp.status_code == 200:
                row = resp.json()
            else:
                row = {"total_count": 0}
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            row = {"total_count": 0}
        return row['total_count'] if row else 0

    def get_by_order(self, order_id: int) -> list[dict]:
        if not is_online():
            return get_offline_students_by_order_id(order_id)
        try:
            resp = api_client.get(f"{self.api_url}/students/by-order/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def link_to_order(self, student_id: int, order_id: int) -> None:
        if not is_online():
            link_offline_students_to_order([student_id], order_id)
            log_activity(f"تم ربط الطالب ID {student_id} بالأمر الجامعي ID {order_id}")
            return
        try:
            resp = api_client.put(f"{self.api_url}/students/{student_id}/link-order/{order_id}", timeout=5.0)
            if resp.status_code != 200:
                st = self.get_by_id(student_id)
                if st:
                    st["order_id"] = order_id
                    self.update(student_id, st)
            log_activity(f"تم ربط الطالب ID {student_id} بالأمر الجامعي ID {order_id}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")

    def unlink_from_order(self, student_id: int) -> None:
        if not is_online():
            unlink_offline_students_from_order([student_id])
            log_activity(f"تم إلغاء ربط الطالب ID {student_id} من الأمر الجامعي")
            return
        try:
            resp = api_client.put(f"{self.api_url}/students/{student_id}/unlink-order", timeout=5.0)
            if resp.status_code != 200:
                st = self.get_by_id(student_id)
                if st:
                    st["order_id"] = None
                    self.update(student_id, st)
            log_activity(f"تم إلغاء ربط الطالب ID {student_id} من الأمر الجامعي")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")

    def search_unlinked(self, name_query: str = "", dept_id: int | None = None, year: int | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if is_online():
            try:
                resp = api_client.get(
                    f"{self.api_url}/students/search/unlinked",
                    params={
                        "name_query": name_query,
                        "dept_id": dept_id,
                        "year": str(year) if year is not None else None,
                        "limit": limit
                    },
                    timeout=3.0
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                log_system(f"API request failed: {e}", "WARNING")

        return search_offline_unlinked_students(name_query=name_query, dept_id=dept_id, year=year, limit=limit)

    def auto_link_matching(self, order_id: int, order_data: dict) -> int:
        dept_id = order_data.get("department_id")
        grad_year = order_data.get("graduation_year")
        matching = get_offline_unlinked_students_matching(dept_id, grad_year)

        count = 0
        for m in matching:
            sid = m["id"]
            self.link_to_order(sid, order_id)
            count += 1
        return count

    def unlink_from_order(self, student_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = api_client.post(f"{self.api_url}/students/{student_id}/unlink-order", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم فك ارتباط الطالب ID: {student_id} بالأمر الجامعي")
            else:
                raise RuntimeError(f"API unlink failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def link_students_to_order(self, order_id: int, order_data: dict) -> int:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = api_client.post(f"{self.api_url}/students/link-order/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                row = resp.json()
                count = row.get('affected_rows', 0)
                if count > 0:
                    log_activity(f"تم ربط {count} طالب بالأمر الجامعي ID: {order_id}")
                return count
            else:
                raise RuntimeError(f"API link failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def link_to_order(self, student_id: int, order_id: int) -> None:
        if not is_online():
            raise OfflineModeError()
        try:
            resp = api_client.post(f"{self.api_url}/students/{student_id}/link-order/{order_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم ربط الطالب ID: {student_id} بالأمر الجامعي ID: {order_id}")
            else:
                raise RuntimeError(f"API single link failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def search_for_order(self, name_query: str = "", admission_year: str | int | None = None, department_id: int = None, limit: int = 50, offset: int = 0) -> list[dict]:
        """Legacy wrapper for OrderStudentsScreen mapping to the new paginated SP."""
        return self.get_all_paginated(limit=limit, offset=offset, name_query=name_query, dept_id=department_id, year=admission_year)

    def get_distinct_admission_years(self) -> list[str]:
        if not is_online():
            return get_offline_distinct_admission_years()
        try:
            resp = api_client.get(f"{self.api_url}/students/distinct/years", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def insert(self, data: dict) -> int:
        if not is_online():
            # Route to offline sync engine
            return log_offline_insert("students", dict(data))
        try:
            payload = {
                "full_name_ar": data.get('full_name_ar'),
                "full_name_en": data.get('full_name_en'),
                "gender": data.get('gender', 1),
                "sequence_number": data.get('sequence_number'),
                "postgraduation_number": data.get('postgraduation_number'),
                "date_of_birth": str(data.get('date_of_birth')) if data.get('date_of_birth') else None,
                "birthplace_id": data.get('birthplace_id', 2),
                "birthplace_other": data.get('birthplace_other'),
                "nationality_id": data.get('nationality_id', 274),
                "national_id": data.get('national_id'),
                "department_id": data.get('department_id'),
                "study_system_id": data.get('study_system_id'),
                "degree_level": data.get('degree_level', 1),
                "order_id": data.get('order_id'),
                "admission_year": str(data.get('admission_year')) if data.get('admission_year') else None,
                "summer_training_data": data.get('summer_training_data'),
                "average": float(data['average']) if data.get('average') is not None else None,
                "graduation_date": str(data.get('graduation_date')) if data.get('graduation_date') else None,
                "graduation_semester": data.get('graduation_semester')
            }
            resp = api_client.post(f"{self.api_url}/students", json=payload, timeout=5.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                log_activity(f"تم إضافة طالب جديد: {data.get('full_name_ar')}")
                return new_id
            else:
                raise RuntimeError(f"API insert failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def update(self, student_id: int, data: dict) -> None:
        payload = {
            "full_name_ar": data.get('full_name_ar'),
            "full_name_en": data.get('full_name_en'),
            "gender": data.get('gender', 1),
            "sequence_number": data.get('sequence_number'),
            "postgraduation_number": data.get('postgraduation_number'),
            "date_of_birth": str(data.get('date_of_birth')) if data.get('date_of_birth') else None,
            "birthplace_id": data.get('birthplace_id'),
            "birthplace_other": data.get('birthplace_other'),
            "nationality_id": data.get('nationality_id', 1),
            "national_id": data.get('national_id'),
            "department_id": data.get('department_id'),
            "study_system_id": data.get('study_system_id'),
            "degree_level": data.get('degree_level', 1),
            "order_id": data.get('order_id'),
            "admission_year": str(data.get('admission_year')) if data.get('admission_year') else None,
            "summer_training_data": data.get('summer_training_data'),
            "average": float(data['average']) if data.get('average') is not None else None,
            "graduation_date": str(data.get('graduation_date')) if data.get('graduation_date') else None,
            "graduation_semester": data.get('graduation_semester')
        }

        if not is_online():
            log_offline_update("students", student_id, payload)
            log_activity(f"تم تعديل بيانات الطالب ID: {student_id} (أوفلاين)")
            return

        try:
            resp = api_client.put(f"{self.api_url}/students/{student_id}", json=payload, timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم تعديل بيانات الطالب ID: {student_id}")
            else:
                raise RuntimeError(f"API update failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise

    def bulk_import(self, students_payload: list[dict]) -> dict:
        """Atomically imports a cohort of students, periods, and enrollments."""
        if not is_online():
            raise OfflineModeError("Bulk import requires active online connection to central server.")
        try:
            resp = api_client.post(
                f"{self.api_url}/api/students/bulk-import",
                json={"students": students_payload},
                timeout=60.0
            )
            if resp.status_code == 200:
                result = resp.json()
                log_activity(f"اكتمل الاستيراد المجمع للطلاب: تم إنشاء {result.get('created_students')}, وتحديث {result.get('updated_students')}")
                pull_mysql_to_sqlite_background()
                return result
            else:
                raise RuntimeError(f"Bulk import failed ({resp.status_code}): {resp.text}")
        except Exception as e:
            log_system(f"Bulk import API error: {e}", "ERROR")
            raise

    def delete(self, student_id: int) -> None:
        if not is_online():
            delete_offline_student(student_id)
            log_activity(f"تم حذف الطالب ID: {student_id}")
            return

        try:
            resp = api_client.delete(f"{self.api_url}/students/{student_id}", timeout=5.0)
            if resp.status_code == 200:
                log_activity(f"تم حذف الطالب ID: {student_id}")
            else:
                self._call_write("DeleteStudent", (student_id,))
                log_activity(f"تم حذف الطالب ID: {student_id}")
        except Exception as e:
            log_system(f"API delete failed, using direct write: {e}", "WARNING")
            self._call_write("DeleteStudent", (student_id,))
            log_activity(f"تم حذف الطالب ID: {student_id}")

# ---------------------------------------------------------------------------
# Module 7: Timelines & Enrollments
# ---------------------------------------------------------------------------

class AcademicPeriodRepository(BaseRepository):
    def get_by_student(self, student_id: int) -> list[dict]:
        periods = []
        if is_online():
            try:
                resp = api_client.get(f"{self.api_url}/academic-periods/by-student/{student_id}", timeout=3.0)
                if resp.status_code == 200:
                    periods = resp.json()
            except Exception as e:
                log_system(f"API request failed for get_by_student academic_periods: {e}", "WARNING")

        if not periods:
            periods = get_offline_academic_periods_by_student(student_id)

        status_code_map = {
            1: "PASSED", "1": "PASSED", "PASSED": "PASSED",
            2: "FAILED_REPEAT", "2": "FAILED_REPEAT", "FAILED": "FAILED_REPEAT", "FAILED_REPEAT": "FAILED_REPEAT",
            3: "EXCEPTIONAL_PASS", "3": "EXCEPTIONAL_PASS", "EXCEPTIONAL_PASS": "EXCEPTIONAL_PASS",
            4: "CARRIED_OVER", "4": "CARRIED_OVER", "CARRIED_OVER": "CARRIED_OVER",
            5: "DEFERRED", "5": "DEFERRED", "DEFERRED": "DEFERRED",
            6: "DISMISSED", "6": "DISMISSED", "DISMISSED": "DISMISSED",
        }

        norm_periods = []
        for r in periods:
            if isinstance(r, dict):
                raw_st = r.get("result_status")
                r["result_status"] = status_code_map.get(raw_st, status_code_map.get(str(raw_st).strip(), "PASSED"))
                norm_periods.append(r)
            elif isinstance(r, (tuple, list)) and len(r) >= 7:
                raw_st = r[6]
                st_str = status_code_map.get(raw_st, status_code_map.get(str(raw_st).strip(), "PASSED"))
                norm_periods.append({
                    "id": r[0], "student_id": r[1], "academic_year": r[2],
                    "study_system_id": r[3], "stage_number": r[4], "semester_num": r[5],
                    "result_status": st_str
                })

        return norm_periods

    def insert(self, student_id: int, year: str, sys_id: int, stage: int, semester_num: int = 1, result_status: str = "PASSED") -> int:
        # MySQL academic_periods.result_status is a number (1=PASSED ... 6=DISMISSED);
        # sending the key text 'PASSED' made MySQL store 0, so always send the code
        result_status = _RESULT_STATUS_CODES.get(result_status, _RESULT_STATUS_CODES.get(str(result_status).strip().upper(), 1))
        if not is_online():
            return log_offline_insert("academic_periods", {
                "student_id": student_id,
                "academic_year": year,
                "study_system_id": sys_id,
                "stage_number": stage,
                "semester_num": semester_num,
                "result_status": result_status,
            })
        try:
            payload = {
                "student_id": student_id,
                "academic_year": str(year),
                "study_system_id": sys_id,
                "stage_number": stage,
                "semester_num": semester_num,
                "result_status": str(result_status),
            }
            resp = api_client.post(f"{self.api_url}/academic-periods", json=payload, timeout=3.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                try:
                    from sync_engine import _get_local_conn
                    with _get_local_conn() as conn_loc:
                        conn_loc.execute(
                            "INSERT OR REPLACE INTO academic_periods (id, student_id, academic_year, study_system_id, stage_number, semester_num, result_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (new_id, student_id, str(year), sys_id, stage, semester_num, result_status)
                        )
                        conn_loc.commit()
                except Exception:
                    pass
                return new_id
        except Exception as e:
            log_system(f"API request failed for academic-periods insert: {e}", "WARNING")

        try:
            new_id = self._call_write("InsertAcademicPeriod", (student_id, str(year), stage, semester_num, result_status))
            if new_id:
                return new_id
        except Exception as sp_err:
            log_system(f"SP InsertAcademicPeriod error: {sp_err}", "WARNING")

        return log_offline_insert("academic_periods", {
            "student_id": student_id, "academic_year": year,
            "study_system_id": sys_id, "stage_number": stage,
            "semester_num": semester_num, "result_status": result_status,
        })

    def update_status(self, period_id: int, result_status: str | int) -> None:
        st_code = _RESULT_STATUS_CODES.get(result_status, _RESULT_STATUS_CODES.get(str(result_status).strip().upper(), 1))
        st_key = {1: "PASSED", 2: "FAILED_REPEAT", 3: "EXCEPTIONAL_PASS", 4: "CARRIED_OVER", 5: "DEFERRED", 6: "DISMISSED"}.get(st_code, "PASSED")

        update_offline_academic_period_status(period_id, st_key)

        if not is_online():
            return

        try:
            resp = api_client.patch(
                f"{self.api_url}/academic-periods/{period_id}/status",
                json={"result_status": str(st_code)},
                timeout=3.0
            )
        except Exception as e:
            log_system(f"API update_status failed: {e}", "WARNING")

    def update_stage(self, period_id: int, stage_number: int) -> None:
        update_offline_academic_period_stage(period_id, stage_number)

        if not is_online():
            return

        try:
            resp = api_client.patch(
                f"{self.api_url}/academic-periods/{period_id}/stage",
                json={"stage_number": stage_number},
                timeout=3.0
            )
        except Exception as e:
            log_system(f"API update_stage failed: {e}", "WARNING")

    def delete(self, period_id: int) -> None:
        delete_offline_academic_period(period_id)
        if not is_online():
            log_activity(f"تم حذف المرحلة الدراسية (أوفلاين) ID: {period_id}")
            return
        try:
            resp = api_client.delete(f"{self.api_url}/academic-periods/{period_id}", timeout=5.0)
            if resp.status_code != 200:
                log_system(f"API delete warning for academic-period {period_id}: {resp.text}", "WARNING")
        except Exception as e:
            log_system(f"API request failed for academic-period delete: {e}", "WARNING")
            raise


class EnrollmentRepository(BaseRepository):
    def get_by_period(self, period_id: int) -> list[dict]:
        if not is_online():
            return get_offline_enrollments_by_period(period_id)
        try:
            resp = api_client.get(f"{self.api_url}/enrollments/by-period/{period_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            return []

    def insert(self, period_id: int, course_id: int, score: float, is_second: int) -> int:
        val = is_second
        passed_round = '2' if val == 2 else ('3' if val == 3 else '1')
        if not is_online():
            return log_offline_insert("enrollments", {
                "period_id": period_id,
                "course_id": course_id,
                "score": score,
                "passed_round": passed_round,
            })
        try:
            payload = {
                "period_id": period_id,
                "course_id": course_id,
                "score": float(score),
                "is_second": int(is_second)
            }
            resp = api_client.post(f"{self.api_url}/enrollments", json=payload, timeout=3.0)
            if resp.status_code == 200:
                new_id = resp.json()["new_id"]
                try:
                    from sync_engine import _get_local_conn
                    with _get_local_conn() as conn_loc:
                        conn_loc.execute(
                            "INSERT OR REPLACE INTO enrollments (id, period_id, course_id, score, passed_round) VALUES (?, ?, ?, ?, ?)",
                            (new_id, period_id, course_id, float(score), passed_round)
                        )
                        conn_loc.commit()
                except Exception:
                    pass
                return new_id
        except Exception as e:
            log_system(f"API request failed for enrollment insert: {e}", "WARNING")

        try:
            new_id = self._call_write("InsertEnrollment", (period_id, course_id, float(score), passed_round))
            if new_id:
                return new_id
        except Exception as sp_err:
            log_system(f"SP InsertEnrollment error: {sp_err}", "WARNING")

        return log_offline_insert("enrollments", {
            "period_id": period_id, "course_id": course_id,
            "score": score, "passed_round": passed_round
        })

    def update(self, enrollment_id: int, score: float, is_second: int) -> None:
        val = int(is_second)
        if val == 2:
            passed_round = '2'
        elif val == 3:
            passed_round = '3'
        elif val == 0:
            passed_round = '0'
        else:
            passed_round = '1'

        update_offline_enrollment(enrollment_id, score, passed_round)

        if not is_online():
            return

        try:
            resp = api_client.put(
                f"{self.api_url}/enrollments/{enrollment_id}",
                params={"score": float(score), "is_second": int(is_second)},
                timeout=3.0
            )
        except Exception as e:
            log_system(f"API request failed for enrollment update: {e}", "WARNING")

    def delete(self, enrollment_id: int) -> None:
        delete_offline_enrollment(enrollment_id)
        if not is_online():
            log_activity(f"تم حذف تسجيل المادة (أوفلاين) ID: {enrollment_id}")
            return
        try:
            resp = api_client.delete(f"{self.api_url}/enrollments/{enrollment_id}", timeout=5.0)
            if resp.status_code != 200:
                raise RuntimeError(f"API delete failed: {resp.text}")
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            raise
