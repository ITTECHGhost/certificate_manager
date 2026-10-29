# =============================================================================
# data/repositories/certificates.py — Module 8: certificate data and issued certificates
# =============================================================================

from .base import *


class CertificateRepository(BaseRepository):

    def get_full_certificate_data(self, student_id: int, grouping_mode: str = "DEFAULT") -> dict | None:
        """Delegates 100% of certificate data fetching & context transformation to cert_repository.py."""
        try:
            from cert_repository import get_certificate_payload
            return get_certificate_payload(student_id, grouping_mode)
        except Exception as e:
            log_system(f"cert_repository.get_certificate_payload failed: {e}", "WARNING")
            return None

    def get_flat_yearly_courses(self, student_id: int) -> list[dict]:
        """Delegates flat-yearly course transcript fetching to cert_repository.py / data.query."""
        if is_online():
            try:
                resp = api_client.get(f"{self.api_url}/certificates/flat-yearly/{student_id}", timeout=5.0)
                if resp.status_code == 200:
                    rows = resp.json()
                    if isinstance(rows, list):
                        return rows
            except Exception as e:
                log_system(f"API flat-yearly courses fetch failed: {e}", "WARNING")

        try:
            from data.query import get_offline_flat_yearly_courses
            return get_offline_flat_yearly_courses(student_id)
        except Exception as e:
            log_system(f"Offline flat-yearly courses query failed: {e}", "WARNING")
            return []


class CertificateRejected(Exception):
    """The server refused to record the certificate (4xx, e.g. 409 duplicate); it is not queued offline."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(f"{status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class IssuedCertificateRepository(BaseRepository):
    def get_all(self) -> list[dict]:
        if not is_online():
            from data.query import get_offline_issued_certificates_report
            return get_offline_issued_certificates_report()
        try:
            resp = api_client.get(f"{self.api_url}/issued-certificates/report", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            from data.query import get_offline_issued_certificates_report
            return get_offline_issued_certificates_report()

    def get_by_student(self, student_id: int) -> list[dict]:
        if not is_online():
            from data.query import get_offline_issued_certificates_by_student
            return get_offline_issued_certificates_by_student(student_id)
        try:
            resp = api_client.get(f"{self.api_url}/issued-certificates/by-student/{student_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            from data.query import get_offline_issued_certificates_by_student
            return get_offline_issued_certificates_by_student(student_id)

    def get_by_id(self, cert_id: int) -> dict | None:
        if not is_online():
            from data.query import get_offline_issued_certificate_by_id
            return get_offline_issued_certificate_by_id(cert_id)
        try:
            resp = api_client.get(f"{self.api_url}/issued-certificates/{cert_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            from data.query import get_offline_issued_certificate_by_id
            return get_offline_issued_certificate_by_id(cert_id)

    def get_report(
        self,
        start_date=None,
        end_date=None,
        dept_id=None,
        template_type=None,
        graduation_year=None,
        study_system_id=None,
        search_text=None
    ) -> list[dict]:
        if not is_online():
            from data.query import get_offline_issued_certificates_report
            return get_offline_issued_certificates_report(
                start_date=start_date,
                end_date=end_date,
                dept_id=dept_id,
                template_type=template_type,
                graduation_year=graduation_year,
                study_system_id=study_system_id,
                search_text=search_text
            )
        try:
            params = {}
            if start_date: params["start_date"] = start_date
            if end_date: params["end_date"] = end_date
            if dept_id is not None and dept_id != 0: params["department_id"] = dept_id
            if template_type: params["template_type"] = template_type
            if graduation_year is not None and graduation_year != 0: params["graduation_year"] = graduation_year
            if study_system_id is not None and study_system_id != 0: params["study_system_id"] = study_system_id
            if search_text: params["search_text"] = search_text
            resp = api_client.get(f"{self.api_url}/issued-certificates/report", params=params, timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            from data.query import get_offline_issued_certificates_report
            return get_offline_issued_certificates_report(
                start_date=start_date,
                end_date=end_date,
                dept_id=dept_id,
                template_type=template_type,
                graduation_year=graduation_year,
                study_system_id=study_system_id,
                search_text=search_text
            )

    def get_latest_number(self) -> str | None:
        if is_online():
            try:
                resp = api_client.get(f"{self.api_url}/issued-certificates/latest-number", timeout=3.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("latest_number"):
                        return data["latest_number"]
            except Exception as e:
                log_system(f"API request latest certificate number failed: {e}", "WARNING")

        from data.query import get_offline_latest_certificate_number
        return get_offline_latest_certificate_number()

    CERT_BLOCK_SIZE = 20

    def ensure_number_block(self) -> None:
        """
        While online, make sure this laptop holds a block of reserved certificate numbers for
        the current year, so certificates printed offline can never repeat a number printed
        on another laptop. Renewed when fewer than 5 numbers are left.
        """
        if not is_online():
            return
        from datetime import datetime as _dt
        from sync_engine import get_cert_number_block, save_cert_number_block, get_device_id
        suffix = _dt.now().strftime("%y")
        block = get_cert_number_block()
        if block and block["year_suffix"] == suffix and block["end_no"] - block["next_no"] + 1 >= 5:
            return
        try:
            resp = api_client.post(
                f"{self.api_url}/certificate-numbers/reserve",
                json={"device_id": get_device_id(), "count": self.CERT_BLOCK_SIZE, "year_suffix": suffix},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                save_cert_number_block(data["year_suffix"], int(data["start_no"]), int(data["end_no"]))
                log_system(f"Reserved certificate numbers {data['start_no']}-{data['end_no']}/{data['year_suffix']} for offline use", "INFO")
            else:
                log_system(f"Certificate number block not reserved ({resp.status_code}): {resp.text[:120]}", "DEBUG")
        except Exception as exc:
            log_system(f"Certificate number block reservation failed: {exc}", "DEBUG")

    def _offline_next_number(self) -> str:
        """Next number when the server cannot be asked: this laptop's reserved block first,
        otherwise one above the highest number this laptop knows for the current year."""
        import re
        from datetime import datetime as _dt
        from sync_engine import get_cert_number_block
        suffix = _dt.now().strftime("%y")
        block = get_cert_number_block()
        if block and block["year_suffix"] == suffix and block["next_no"] <= block["end_no"]:
            return f"{block['next_no']}/{suffix}"
        rows = sqlite_read_all(
            "SELECT certificate_number FROM issued_certificates WHERE certificate_number LIKE ? "
            "UNION ALL SELECT certificate_number FROM local_issued_certificates WHERE certificate_number LIKE ?",
            (f"%/{suffix}", f"%/{suffix}"),
        )
        numbers = [int(m.group(1)) for m in (re.match(r"^\s*(\d+)\s*/", str(r.get("certificate_number") or "")) for r in rows) if m]
        return f"{max(numbers, default=0) + 1}/{suffix}"

    def get_next_number(self) -> str:
        """
        Auto-increments the latest certificate number.
        Handles patterns like '420/44' -> '421/44', '105' -> '106'.
        Defaults to '1' if no previous certificate number exists.
        Offline (or server unreachable): uses this laptop's reserved block (_offline_next_number).
        """
        import re
        latest = None
        if is_online():
            try:
                resp = api_client.get(f"{self.api_url}/issued-certificates/latest-number", timeout=3.0)
                if resp.status_code == 200:
                    latest = resp.json().get("latest_number")
                    if not latest:
                        from datetime import datetime
                        return f"1/{datetime.now().strftime('%y')}"
            except Exception as e:
                log_system(f"API request latest certificate number failed: {e}", "WARNING")
        if latest is None:
            return self._offline_next_number()
        if not latest:
            from datetime import datetime
            curr_year_short = datetime.now().strftime("%y")
            return f"1/{curr_year_short}"

        cleaned = str(latest).strip()
        match = re.match(r"^(\d+)(/.*)?$", cleaned)
        if match:
            num = int(match.group(1)) + 1
            suffix = match.group(2) or ""
            return f"{num}{suffix}"

        # If it ends with digits, e.g. "DOC-420"
        sub_match = re.search(r"(\d+)$", cleaned)
        if sub_match:
            val = int(sub_match.group(1)) + 1
            prefix = cleaned[:sub_match.start(1)]
            return f"{prefix}{val}"

        return f"{cleaned}-1"

    def check_duplicate(self, certificate_number: str, current_student_id: int) -> dict:
        """
        Verifies if a certificate number is already used in the database.
        Returns:
            {"exists": bool, "same_student": bool, "owner_id": int | None, "owner_name": str, "certificate_id": int | None}
        """
        if not certificate_number or not certificate_number.strip():
            return {"exists": False, "same_student": False, "owner_id": None, "owner_name": "", "certificate_id": None}

        num_target = certificate_number.strip().lower()
        records = self.get_report(search_text=certificate_number.strip())
        for r in records:
            cert_num = str(r.get("certificate_number") or "").strip().lower()
            if cert_num == num_target:
                sid = r.get("student_id")
                same = (int(sid) == int(current_student_id)) if sid is not None and current_student_id else False
                name = r.get("student_name_ar") or r.get("full_name_ar") or ""
                cert_id = r.get("certificate_id") or r.get("id")
                return {"exists": True, "same_student": same, "owner_id": sid, "owner_name": name, "certificate_id": cert_id}

        return {"exists": False, "same_student": False, "owner_id": None, "owner_name": "", "certificate_id": None}

    def insert(
        self,
        student_id: int,
        to_title: Optional[str] = "من يهمه الأمر",
        template_type: Optional[str] = "graduation",
        issue_date: Optional[str] = None,
        certificate_number: Optional[str] = None,
        user_id: Optional[int] = None,
        user_name: Optional[str] = None
    ) -> int:
        if not issue_date:
            from datetime import datetime
            issue_date = datetime.now().strftime("%Y-%m-%d")

        payload = {
            "student_id": int(student_id),
            "to_title": str(to_title or "من يهمه الأمر"),
            "template_type": str(template_type or "graduation"),
            "issue_date": str(issue_date),
            "certificate_number": str(certificate_number or "").strip() or None
        }

        new_id = None
        if not is_online():
            from data.query import insert_offline_issued_certificate
            new_id = insert_offline_issued_certificate(
                student_id=payload["student_id"],
                to_title=payload["to_title"],
                template_type=payload["template_type"],
                issue_date=payload["issue_date"],
                certificate_number=payload["certificate_number"]
            )
        else:
            try:
                resp = api_client.post(f"{self.api_url}/issued-certificates", json=payload, timeout=5.0)
                if resp.status_code == 200:
                    res_data = resp.json()
                    new_id = res_data.get("new_id") or res_data.get("inserted_id")
                elif 400 <= resp.status_code < 500:
                    # The server answered and refused (e.g. 409 duplicate): queueing it offline would only fail again
                    log_system(f"API refused issued certificate ({resp.status_code}): {resp.text}", "WARNING")
                    raise CertificateRejected(resp.status_code, resp.text)
                else:
                    log_system(f"API insert issued certificate warning: {resp.text}", "WARNING")
            except CertificateRejected:
                raise
            except Exception as e:
                log_system(f"API request failed for insert issued certificate: {e}", "WARNING")

            if not new_id:
                from data.query import insert_offline_issued_certificate
                new_id = insert_offline_issued_certificate(
                    student_id=payload["student_id"],
                    to_title=payload["to_title"],
                    template_type=payload["template_type"],
                    issue_date=payload["issue_date"],
                    certificate_number=payload["certificate_number"]
                )

        # A number taken from this laptop's reserved block is now used
        if payload["certificate_number"]:
            from sync_engine import mark_cert_number_used
            mark_cert_number_used(payload["certificate_number"])

        # Log user activity with user_id, user_name, certificate_id, certificate_number
        u_id = user_id if user_id is not None else "—"
        u_name = user_name or "المستخدم"
        c_num = payload["certificate_number"] or "—"
        log_activity(f"المستخدم ID: {u_id} ({u_name}) قام بإصدار وثيقة برقم ID: {new_id}، رقم الوثيقة: {c_num} للطالب ID: {student_id}")

        return new_id or 1

    def update(
        self,
        cert_id: int,
        to_title: Optional[str] = None,
        template_type: Optional[str] = None,
        issue_date: Optional[str] = None,
        certificate_number: Optional[str] = None
    ) -> None:
        payload = {}
        if to_title is not None: payload["to_title"] = to_title
        if template_type is not None: payload["template_type"] = template_type
        if issue_date is not None: payload["issue_date"] = issue_date
        if certificate_number is not None: payload["certificate_number"] = certificate_number

        if not is_online():
            from data.query import update_offline_issued_certificate
            update_offline_issued_certificate(
                cert_id=cert_id,
                to_title=payload.get("to_title"),
                template_type=payload.get("template_type"),
                issue_date=payload.get("issue_date"),
                certificate_number=payload.get("certificate_number")
            )
            return

        try:
            resp = api_client.put(f"{self.api_url}/issued-certificates/{cert_id}", json=payload, timeout=5.0)
            if resp.status_code != 200:
                log_system(f"API update issued certificate warning: {resp.text}", "WARNING")
                from data.query import update_offline_issued_certificate
                update_offline_issued_certificate(
                    cert_id=cert_id,
                    to_title=payload.get("to_title"),
                    template_type=payload.get("template_type"),
                    issue_date=payload.get("issue_date"),
                    certificate_number=payload.get("certificate_number")
                )
        except Exception as e:
            log_system(f"API request failed for update issued certificate: {e}", "WARNING")
            from data.query import update_offline_issued_certificate
            update_offline_issued_certificate(
                cert_id=cert_id,
                to_title=payload.get("to_title"),
                template_type=payload.get("template_type"),
                issue_date=payload.get("issue_date"),
                certificate_number=payload.get("certificate_number")
            )

    def delete(self, cert_id: int) -> None:
        if not is_online():
            from data.query import delete_offline_issued_certificate
            delete_offline_issued_certificate(cert_id)
            return
        try:
            resp = api_client.delete(f"{self.api_url}/issued-certificates/{cert_id}", timeout=5.0)
            if resp.status_code != 200:
                log_system(f"API delete failed: {resp.text}", "WARNING")
                from data.query import delete_offline_issued_certificate
                delete_offline_issued_certificate(cert_id)
        except Exception as e:
            log_system(f"API request failed: {e}", "WARNING")
            from data.query import delete_offline_issued_certificate
            delete_offline_issued_certificate(cert_id)
