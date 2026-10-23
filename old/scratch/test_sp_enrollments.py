import sys
sys.path.append(r"f:\CR_PY\certificate_manager")
sys.stdout.reconfigure(encoding='utf-8')

from db import get_connection

conn = get_connection()
cur = conn.cursor(dictionary=True)
cur.execute("SELECT * FROM enrollments LIMIT 10")
rows = cur.fetchall()
print("Direct MySQL enrollments sample:")
for r in rows:
    print(r)

if rows:
    p_id = rows[0]["period_id"]
    cur.callproc("GetEnrollmentsByPeriod", (p_id,))
    for result_set in cur.stored_results():
        sp_rows = result_set.fetchall()
        print(f"\nSP GetEnrollmentsByPeriod({p_id}) output:")
        for sr in sp_rows:
            print(sr)

cur.close()
conn.close()
