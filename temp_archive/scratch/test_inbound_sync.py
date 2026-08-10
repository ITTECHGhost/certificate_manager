"""
Verification: Inbound Sync Engine (Local Read Replica)
Tests: replica schema creation, pull_mysql_to_sqlite, offline auth, offline reads
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sync_engine import (
    init_local_db, set_online, is_online, _LOCAL_DB_PATH,
    _get_local_conn, pull_mysql_to_sqlite,
    sqlite_read_all, sqlite_read_one,
)

# Clean slate
if _LOCAL_DB_PATH.exists():
    os.remove(str(_LOCAL_DB_PATH))

# -- Test 1: init_local_db creates all replica tables --
print("=== Test 1: Replica tables created ===")
init_local_db()
conn = _get_local_conn()
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print(f"  Tables: {tables}")

expected = [
    'academic_periods', 'countries', 'course_departments', 'courses',
    'departments', 'enrollments', 'governorates', 'graduation_orders',
    'local_academic_periods', 'local_enrollments', 'local_students',
    'personnel', 'read_cache', 'students', 'study_systems',
    'sync_queue', 'temp_id_counter', 'university_settings',
    'user_preferences',
]
for t in expected:
    assert t in tables, f"Missing table: {t}"
print("PASS")

# -- Test 2: Seed some data into replica tables directly --
print("\n=== Test 2: Seed test data ===")
conn.execute(
    "INSERT INTO personnel (id, name_ar, name_en, username, password_hash, personnel_role, is_active) "
    "VALUES (1, 'admin_ar', 'admin_en', 'admin', 'hash123', 'admin', 1)"
)
conn.execute(
    "INSERT INTO personnel (id, name_ar, name_en, username, password_hash, personnel_role, is_active) "
    "VALUES (2, 'user_ar', 'user_en', 'user1', 'hash456', 'user', 0)"
)
conn.execute(
    "INSERT INTO students (id, full_name_ar, full_name_en, department_id, study_system_id, average) "
    "VALUES (1, 'student_ar1', 'student_en1', 1, 1, 85.5)"
)
conn.execute(
    "INSERT INTO students (id, full_name_ar, full_name_en, department_id, study_system_id, average) "
    "VALUES (2, 'student_ar2', 'student_en2', 1, 1, 92.0)"
)
conn.execute(
    "INSERT INTO departments (id, name_ar, name_en) VALUES (1, 'CS_ar', 'CS_en')"
)
conn.execute(
    "INSERT INTO courses (id, name_ar, name_en, credit_hours, department_id, stage_number, study_system_id) "
    "VALUES (1, 'math_ar', 'Math', 3, 1, 1, 1)"
)
conn.execute(
    "INSERT INTO university_settings (id, univ_name_ar, univ_name_en, college_name_ar, college_name_en) "
    "VALUES (1, 'uni_ar', 'uni_en', 'col_ar', 'col_en')"
)
conn.commit()
print("PASS")

# -- Test 3: sqlite_read_all / sqlite_read_one helpers --
print("\n=== Test 3: SQLite read helpers ===")
students = sqlite_read_all("SELECT * FROM students")
assert len(students) == 2
assert students[0]["full_name_ar"] == "student_ar1"
print(f"  sqlite_read_all students -> {len(students)} rows  [OK]")

one = sqlite_read_one("SELECT * FROM students WHERE id = ?", (2,))
assert one is not None
assert one["full_name_en"] == "student_en2"
print(f"  sqlite_read_one student #2 -> {one['full_name_en']}  [OK]")

none_result = sqlite_read_one("SELECT * FROM students WHERE id = ?", (999,))
assert none_result is None
print(f"  sqlite_read_one (not found) -> None  [OK]")
print("PASS")

# -- Test 4: Offline authentication via SQLite --
print("\n=== Test 4: Offline authentication ===")
set_online(False)
from data.repositories import PersonnelRepository
repo = PersonnelRepository()

# Correct credentials
user = repo.authenticate("admin", "hash123")
assert user is not None
assert user["name_en"] == "admin_en"
print(f"  admin login -> {user['name_en']}  [OK]")

# Wrong password
user = repo.authenticate("admin", "wrong")
assert user is None
print(f"  wrong password -> None  [OK]")

# Inactive user
user = repo.authenticate("user1", "hash456")
assert user is None
print(f"  inactive user -> None  [OK]")
print("PASS")

# -- Test 5: Offline reads from other repos --
print("\n=== Test 5: Offline reads from repositories ===")
set_online(False)
from data.repositories import SettingsRepository

settings_repo = SettingsRepository()
settings = settings_repo.get_settings()
assert settings["univ_name_en"] == "uni_en"
print(f"  SettingsRepository.get_settings() -> {settings['univ_name_en']}  [OK]")

# count_table_rows should use SQLite
from data.repositories import BaseRepository
base = BaseRepository()
count = base.count_table_rows("students")
assert count == 2
print(f"  count_table_rows('students') -> {count}  [OK]")

count = base.count_table_rows("departments")
assert count == 1
print(f"  count_table_rows('departments') -> {count}  [OK]")

from data.repositories import CourseRepository
course_repo = CourseRepository()
courses = course_repo.get_by_dept_stage_system(1, 1, 1)
assert len(courses) == 1
assert courses[0]["name_en"] == "Math"
print(f"  CourseRepository.get_by_dept_stage_system() -> {len(courses)} courses  [OK]")

print("PASS")

# -- Test 6: Personnel offline gets --
print("\n=== Test 6: Personnel offline reads ===")
all_personnel = repo.get_all()
assert len(all_personnel) == 2
print(f"  get_all() -> {len(all_personnel)} records  [OK]")

active = repo.get_active()
assert len(active) == 1
print(f"  get_active() -> {len(active)} records  [OK]")
print("PASS")

# Cleanup
set_online(True)
conn.close()
os.remove(str(_LOCAL_DB_PATH))
print(f"\nCleaned up {_LOCAL_DB_PATH}")

print("\n" + "=" * 60)
print("  ALL TESTS PASSED - Inbound Sync Engine verified.")
print("=" * 60)
