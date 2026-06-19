import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parent.parent / "local_cache.db"
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

print("Columns in 'academic_periods' table:")
cur.execute("PRAGMA table_info(academic_periods)")
for col in cur.fetchall():
    print(dict(zip(['cid', 'name', 'type', 'notnull', 'dflt_value', 'pk'], col)))

print("\nColumns in 'local_academic_periods' table:")
cur.execute("PRAGMA table_info(local_academic_periods)")
for col in cur.fetchall():
    print(dict(zip(['cid', 'name', 'type', 'notnull', 'dflt_value', 'pk'], col)))

conn.close()
