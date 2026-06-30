"""
Verification script for sync_engine.py - Tests all 4 tasks.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date
from sync_engine import (
    init_local_db, generate_temp_id, log_offline_insert,
    get_queue_status, _json_dumps, _json_loads, _get_local_conn,
    _resolve_temp_id, _TABLE_REGISTRY, _LOCAL_DB_PATH,
)

# Clean slate
if _LOCAL_DB_PATH.exists():
    os.remove(str(_LOCAL_DB_PATH))
    print(f"Removed old {_LOCAL_DB_PATH}")

# -- Task 1: init_local_db --
print("\n=== Task 1: init_local_db ===")
init_local_db()
assert _LOCAL_DB_PATH.exists(), "local_cache.db was not created"
print("PASS - local_cache.db created with all tables.")

# -- Task 2: generate_temp_id --
print("\n=== Task 2: generate_temp_id ===")
ids = [generate_temp_id() for _ in range(5)]
print(f"  Generated IDs: {ids}")
assert all(i < 0 for i in ids), "All IDs must be negative"
assert len(set(ids)) == 5, "All IDs must be unique"
assert ids == sorted(ids, reverse=True), "IDs should decrease monotonically"
print("PASS - all IDs negative, unique, and monotonically decreasing.")

# -- Task 3: log_offline_insert --
print("\n=== Task 3: log_offline_insert ===")

# 3a. Insert a student
student_payload = {
    "full_name_ar": "test_student",
    "full_name_en": "Hussein Ali",
    "gender": "M",
    "department_id": 1,
    "admission_year": 2022,
    "date_of_birth": "2000-01-15",
    "study_system_id": 1,
    "degree_level": "Bachelor",
}
tid_student = log_offline_insert("students", student_payload)
print(f"  Student temp_id = {tid_student}")
assert tid_student < 0

# 3b. Insert an academic period referencing the student's temp_id
period_payload = {
    "student_id": tid_student,
    "academic_year": "2022-2023",
    "study_system_id": 1,
    "stage_number": 1,
    "semester_num": 1,
}
tid_period = log_offline_insert("academic_periods", period_payload)
print(f"  Period temp_id = {tid_period}  (FK student_id = {tid_student})")
assert tid_period < 0

# 3c. Insert an enrollment referencing the period's temp_id
enr_payload = {
    "period_id": tid_period,
    "course_id": 5,
    "score": 85.0,
    "passed_round": "1",
}
tid_enrollment = log_offline_insert("enrollments", enr_payload)
print(f"  Enrollment temp_id = {tid_enrollment}  (FK period_id = {tid_period})")
assert tid_enrollment < 0

# Verify queue status
status = get_queue_status()
print(f"\n  Queue status: {status['pending']} pending entries")
for e in status["entries"]:
    print(f"    #{e['id']}  {e['table_name']}  temp_id={e['temp_id']}")
assert status["pending"] == 3
print("PASS - 3 records queued (student -> period -> enrollment).")

# Verify local mirror tables have the data
conn = _get_local_conn()
row = conn.execute("SELECT * FROM local_students WHERE id = ?", (tid_student,)).fetchone()
assert row is not None, "Student not in local_students"
assert row["full_name_en"] == "Hussein Ali"

row = conn.execute("SELECT * FROM local_academic_periods WHERE id = ?", (tid_period,)).fetchone()
assert row is not None, "Period not in local_academic_periods"
assert row["student_id"] == tid_student, "FK student_id mismatch"

row = conn.execute("SELECT * FROM local_enrollments WHERE id = ?", (tid_enrollment,)).fetchone()
assert row is not None, "Enrollment not in local_enrollments"
assert row["period_id"] == tid_period, "FK period_id mismatch"
conn.close()
print("PASS - all 3 local mirror tables contain correct data with FK chains.")

# -- Task 4: ID Resolution (simulated) --
print("\n=== Task 4: ID Resolution (simulated) ===")
FAKE_REAL_STUDENT_ID = 542
FAKE_REAL_PERIOD_ID  = 87
FAKE_REAL_ENROLLMENT_ID = 1001

conn = _get_local_conn()

# Resolve student: temp_id -> 542
_resolve_temp_id(conn, "students", tid_student, FAKE_REAL_STUDENT_ID)
conn.commit()

row = conn.execute("SELECT id FROM local_students WHERE id = ?", (FAKE_REAL_STUDENT_ID,)).fetchone()
assert row is not None, "Student PK not resolved"
print(f"  Student: {tid_student} -> {FAKE_REAL_STUDENT_ID}  [OK]")

# Verify: period FK cascaded
row = conn.execute("SELECT student_id FROM local_academic_periods WHERE id = ?", (tid_period,)).fetchone()
assert row["student_id"] == FAKE_REAL_STUDENT_ID, (
    f"Period FK not cascaded: expected {FAKE_REAL_STUDENT_ID}, got {row['student_id']}"
)
print(f"  Period FK student_id: {tid_student} -> {FAKE_REAL_STUDENT_ID}  [OK]  (cascade)")

# Verify: sync_queue payload also updated
queue_row = conn.execute(
    "SELECT payload FROM sync_queue WHERE table_name='academic_periods' AND temp_id=?",
    (tid_period,)
).fetchone()
payload = _json_loads(queue_row["payload"])
assert payload["student_id"] == FAKE_REAL_STUDENT_ID, (
    f"Queue payload FK not cascaded: expected {FAKE_REAL_STUDENT_ID}, got {payload['student_id']}"
)
print(f"  Queue payload student_id: {tid_student} -> {FAKE_REAL_STUDENT_ID}  [OK]  (payload cascade)")

# Resolve period: temp_id -> 87
_resolve_temp_id(conn, "academic_periods", tid_period, FAKE_REAL_PERIOD_ID)
conn.commit()

row = conn.execute("SELECT id FROM local_academic_periods WHERE id = ?", (FAKE_REAL_PERIOD_ID,)).fetchone()
assert row is not None, "Period PK not resolved"
print(f"  Period: {tid_period} -> {FAKE_REAL_PERIOD_ID}  [OK]")

# Verify: enrollment FK cascaded
row = conn.execute("SELECT period_id FROM local_enrollments WHERE id = ?", (tid_enrollment,)).fetchone()
assert row["period_id"] == FAKE_REAL_PERIOD_ID, (
    f"Enrollment FK not cascaded: expected {FAKE_REAL_PERIOD_ID}, got {row['period_id']}"
)
print(f"  Enrollment FK period_id: {tid_period} -> {FAKE_REAL_PERIOD_ID}  [OK]  (cascade)")

# Verify enrollment queue payload also updated
queue_row = conn.execute(
    "SELECT payload FROM sync_queue WHERE table_name='enrollments' AND temp_id=?",
    (tid_enrollment,)
).fetchone()
payload = _json_loads(queue_row["payload"])
assert payload["period_id"] == FAKE_REAL_PERIOD_ID, (
    f"Enrollment queue payload FK not cascaded: expected {FAKE_REAL_PERIOD_ID}, got {payload['period_id']}"
)
print(f"  Queue payload period_id: {tid_period} -> {FAKE_REAL_PERIOD_ID}  [OK]  (payload cascade)")

conn.close()

# -- JSON Safety --
print("\n=== JSON Safety ===")
j = _json_dumps({"d": date(2026, 6, 15), "n": None, "v": 100.0})
parsed = _json_loads(j)
assert parsed["d"] == "2026-06-15"
assert parsed["n"] is None
assert parsed["v"] == 100.0
print(f"  Serialized: {j}")
print("PASS - dates, nulls, and floats serialize/deserialize correctly.")

# -- Cleanup --
os.remove(str(_LOCAL_DB_PATH))
print(f"\nCleaned up {_LOCAL_DB_PATH}")

print("\n" + "=" * 60)
print("  ALL TESTS PASSED - Sync Engine verified successfully.")
print("=" * 60)
