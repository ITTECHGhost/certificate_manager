"""
Verification: StudentRepository search_for_order, get_by_order, and distinct admission years
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sqlite3
from sync_engine import init_local_db, set_online, is_online, _LOCAL_DB_PATH, get_local_connection
from data.repositories import StudentRepository, OfflineModeError

# Clean slate
if _LOCAL_DB_PATH.exists():
    os.remove(str(_LOCAL_DB_PATH))
init_local_db()

# Seed SQLite replica with departments and students
conn = get_local_connection()
cur = conn.cursor()

# Insert dummy departments
cur.execute("INSERT OR IGNORE INTO departments (id, name_ar, name_en) VALUES (1, 'قسم هندسة الحاسوب', 'Computer Engineering Department')")
cur.execute("INSERT OR IGNORE INTO departments (id, name_ar, name_en) VALUES (2, 'قسم هندسة الكهرباء', 'Electrical Engineering Department')")

# Insert dummy students
cur.execute("""
    INSERT INTO students (id, full_name_ar, full_name_en, admission_year, average, department_id, order_id)
    VALUES (101, 'أحمد علي', 'Ahmed Ali', 2019, 85.5, 1, 10)
""")
cur.execute("""
    INSERT INTO students (id, full_name_ar, full_name_en, admission_year, average, department_id, order_id)
    VALUES (102, 'محمد حسن', 'Mohamed Hassan', 2020, 78.2, 1, NULL)
""")

# Insert dummy local_students (offline-created student)
cur.execute("""
    INSERT INTO local_students (id, full_name_ar, full_name_en, admission_year, average, department_id, order_id)
    VALUES (-1, 'زينب جعفر', 'Zainab Jafar', 2019, 92.4, 2, 10)
""")
conn.commit()
conn.close()

# Start verification
print("=== Student Order Routing Tests ===")

# Force offline
set_online(False)
assert not is_online(), "Should be offline"

repo = StudentRepository()

# 1. Test get_distinct_admission_years()
print("\nTest 1: get_distinct_admission_years()")
years = repo.get_distinct_admission_years()
print(f"  Result: {years}")
assert years == ['2020', '2019'], f"Expected ['2020', '2019'], got {years}"
print("  get_distinct_admission_years -> OK")

# 2. Test get_by_order()
print("\nTest 2: get_by_order()")
students_in_order = repo.get_by_order(10)
print(f"  Result (order 10): {[{'id': s['id'], 'name': s['full_name_ar'], 'avg': s['average']} for s in students_in_order]}")
# Should have ID 101 and ID -1, ordered by average DESC (-1 has avg 92.4, 101 has avg 85.5)
assert len(students_in_order) == 2, f"Expected 2 students, got {len(students_in_order)}"
assert students_in_order[0]['id'] == -1, f"Expected first student to be ID -1, got {students_in_order[0]['id']}"
assert students_in_order[1]['id'] == 101, f"Expected second student to be ID 101, got {students_in_order[1]['id']}"
print("  get_by_order -> OK")

# 3. Test get_all_paginated() and search_for_order()
print("\nTest 3: search_for_order() wrapper & get_all_paginated()")
all_students = repo.get_all_paginated(limit=50, offset=0)
print(f"  get_all_paginated (all) -> count: {len(all_students)}")
assert len(all_students) == 3, f"Expected 3, got {len(all_students)}"

# Filter by year
students_2019 = repo.search_for_order(admission_year=2019, limit=50)
print(f"  search_for_order (year 2019) -> count: {len(students_2019)}")
assert len(students_2019) == 2, f"Expected 2, got {len(students_2019)}"

# Filter by dept
students_dept2 = repo.search_for_order(department_id=2, limit=50)
print(f"  search_for_order (dept 2) -> count: {len(students_dept2)}")
assert len(students_dept2) == 1, f"Expected 1, got {len(students_dept2)}"

# Filter by name
students_name = repo.search_for_order(name_query="محمد", limit=50)
print(f"  search_for_order (name filter) -> count: {len(students_name)}")
assert len(students_name) == 1, f"Expected 1, got {len(students_name)}"
assert students_name[0]['id'] == 102, f"Expected ID 102, got {students_name[0]['id']}"
print("  search_for_order -> OK")

# 4. Test count() offline
print("\nTest 4: count() offline")
cnt_2019 = repo.count(year=2019)
print(f"  count (year 2019) -> {cnt_2019}")
assert cnt_2019 == 2, f"Expected 2, got {cnt_2019}"
print("  count -> OK")

# 5. Test get_by_id() offline
print("\nTest 5: get_by_id() offline")
st = repo.get_by_id(101)
print(f"  get_by_id(101) -> name: {st['full_name_ar'] if st else None}, dept_name: {st['dept_name_ar'] if st else None}")
assert st is not None
assert st['id'] == 101
assert st['dept_name_ar'] == 'قسم هندسة الحاسوب'

st_neg = repo.get_by_id(-1)
print(f"  get_by_id(-1) -> name: {st_neg['full_name_ar'] if st_neg else None}, dept_name: {st_neg['dept_name_ar'] if st_neg else None}")
assert st_neg is not None
assert st_neg['id'] == -1
assert st_neg['dept_name_ar'] == 'قسم هندسة الكهرباء'
print("  get_by_id -> OK")

# 6. Test write blockers
print("\nTest 6: Offline write block checks")
try:
    repo.unlink_from_order(101)
    assert False, "Should have raised OfflineModeError"
except OfflineModeError:
    print("  unlink_from_order raised OfflineModeError -> OK")

try:
    repo.link_students_to_order(10, {})
    assert False, "Should have raised OfflineModeError"
except OfflineModeError:
    print("  link_students_to_order raised OfflineModeError -> OK")

print("\n" + "=" * 60)
print("  ALL TESTS PASSED - Student Repository offline routing verified.")
print("=" * 60)

# Cleanup
if _LOCAL_DB_PATH.exists():
    os.remove(str(_LOCAL_DB_PATH))
