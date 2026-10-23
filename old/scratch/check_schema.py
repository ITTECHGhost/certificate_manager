import sqlite3
import json

conn = sqlite3.connect('local_cache.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def get_columns(table):
    cur.execute(f"PRAGMA table_info('{table}')")
    return [dict(row) for row in cur.fetchall()]

print("enrollments:", [c['name'] for c in get_columns('enrollments')])
print("academic_periods:", [c['name'] for c in get_columns('academic_periods')])
print("students:", [c['name'] for c in get_columns('students')])
