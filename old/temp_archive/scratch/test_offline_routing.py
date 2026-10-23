"""
Verification: offline routing in repositories.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sync_engine import init_local_db, set_online, is_online, _LOCAL_DB_PATH
from data.repositories import OfflineModeError, BaseRepository

# Clean slate
if _LOCAL_DB_PATH.exists():
    os.remove(str(_LOCAL_DB_PATH))
init_local_db()

repo = BaseRepository()

# -- Test 1: Online mode (reads should go to MySQL) --
print("=== Test 1: Online mode ===")
set_online(True)
assert is_online() == True
# count_table_rows goes to MySQL - should not crash
count = repo.count_table_rows("students")
print(f"  Student count (online): {count}")
print("PASS")

# -- Test 2: Offline mode (reads should return safe defaults) --
print("\n=== Test 2: Offline reads ===")
set_online(False)
assert is_online() == False

# _call_read_all should return [] when offline and no cache
result = repo._call_read_all("NonExistentProc", ())
assert result == [], f"Expected [], got {result}"
print("  _call_read_all (no cache) -> []  [OK]")

# _call_read_one should return None when offline and no cache
result = repo._call_read_one("NonExistentProc", ())
assert result is None, f"Expected None, got {result}"
print("  _call_read_one (no cache) -> None  [OK]")

# count_table_rows should return 0 when offline
count = repo.count_table_rows("students")
assert count == 0
print("  count_table_rows -> 0  [OK]")

print("PASS")

# -- Test 3: Offline writes should raise OfflineModeError --
print("\n=== Test 3: Offline write block ===")
try:
    repo._call_write("SomeUpdateProc", (1,))
    assert False, "Should have raised OfflineModeError"
except OfflineModeError as e:
    msg = str(e)
    assert "Offline Mode" in msg or "Cannot" in msg
    print(f"  _call_write raised OfflineModeError  [OK]")
print("PASS")

# -- Test 4: Read cache serves offline reads --
print("\n=== Test 4: Read cache fallback ===")
from sync_engine import cache_read_result, get_cached_read

# Simulate caching a result while online
cache_read_result("GetStudentsPaginated", (25, 0, "", None, None), [
    {"id": 1, "full_name_ar": "test1"},
    {"id": 2, "full_name_ar": "test2"},
])

# Now read it back while offline
set_online(False)
result = repo._call_read_all("GetStudentsPaginated", (25, 0, "", None, None))
assert len(result) == 2
assert result[0]["full_name_ar"] == "test1"
print(f"  _call_read_all (cached) -> {len(result)} rows  [OK]")

# _call_read_one with cached data
cache_read_result("GetStudentDossierByID", (1,), [{"id": 1, "full_name_ar": "test1"}])
result = repo._call_read_one("GetStudentDossierByID", (1,))
assert result is not None
assert result["id"] == 1
print(f"  _call_read_one (cached) -> {result['id']}  [OK]")

print("PASS")

# -- Test 5: Offline INSERT routing --
print("\n=== Test 5: Offline INSERT routing ===")
set_online(False)
from data.repositories import StudentRepository, EnrollmentRepository, AcademicPeriodRepository

student_repo = StudentRepository()
tid = student_repo.insert({
    "full_name_ar": "offline_student",
    "full_name_en": "Offline Student",
    "gender": "M",
    "department_id": 1,
    "study_system_id": 1,
    "degree_level": "Bachelor",
    "admission_year": 2024,
})
assert tid < 0, f"Expected negative temp_id, got {tid}"
print(f"  StudentRepository.insert() -> temp_id={tid}  [OK]")

period_repo = AcademicPeriodRepository()
tid_p = period_repo.insert(tid, "2024-2025", 1, 1)
assert tid_p < 0
print(f"  AcademicPeriodRepository.insert() -> temp_id={tid_p}  [OK]")

enr_repo = EnrollmentRepository()
tid_e = enr_repo.insert(tid_p, 5, 85.0, 0)
assert tid_e < 0
print(f"  EnrollmentRepository.insert() -> temp_id={tid_e}  [OK]")

# Verify UPDATE/DELETE blocked
try:
    enr_repo.update(tid_e, 90.0, 0)
    assert False, "Should have raised"
except OfflineModeError:
    print("  EnrollmentRepository.update() -> OfflineModeError  [OK]")

try:
    enr_repo.delete(tid_e)
    assert False, "Should have raised"
except OfflineModeError:
    print("  EnrollmentRepository.delete() -> OfflineModeError  [OK]")

try:
    period_repo.delete(tid_p)
    assert False, "Should have raised"
except OfflineModeError:
    print("  AcademicPeriodRepository.delete() -> OfflineModeError  [OK]")

print("PASS")

# Cleanup
set_online(True)
os.remove(str(_LOCAL_DB_PATH))
print(f"\nCleaned up {_LOCAL_DB_PATH}")

print("\n" + "=" * 60)
print("  ALL TESTS PASSED - Repository routing verified.")
print("=" * 60)
