import sqlite3

conn = sqlite3.connect(r"f:\CR_PY\certificate_manager\certificate_manager.db")
cur = conn.cursor()
cur.execute("SELECT id, period_id, course_id, score, passed_round FROM enrollments LIMIT 10")
rows = cur.fetchall()
print("Local SQLite enrollments:", rows)
if rows:
    p_id = rows[0][1]
    cur.execute("SELECT student_id FROM academic_periods WHERE id = ?", (p_id,))
    st = cur.fetchone()
    print("Period", p_id, "student:", st)
conn.close()
