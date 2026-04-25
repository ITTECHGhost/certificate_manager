import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "..", "certificate_manager.db")
conn = sqlite3.connect(db_path)
conn.execute('PRAGMA foreign_keys = OFF')

tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
for t in tables:
    conn.execute(f'DELETE FROM {t[0]}')

conn.execute('DELETE FROM sqlite_sequence')
conn.commit()
print("Database cleared.")
