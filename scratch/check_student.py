import os
import sys
import sqlite3

sys.path.insert(0, os.path.abspath("."))
conn = sqlite3.connect("local_cache.db")
cur = conn.cursor()
try:
    cur.execute("SELECT id, full_name_ar FROM local_students LIMIT 1")
    print("First local student:", cur.fetchone())
except Exception as e:
    print(f"Error local_students: {e}")

try:
    cur.execute("SELECT id, full_name_ar FROM students WHERE id = 2138")
    print("Student 2138:", cur.fetchone())
except Exception as e:
    print(f"Error students: {e}")
