
from tools.migrate_mysql import SQLParser
import sqlite3

parser = SQLParser('CSIT_SQL_DATABASE2.sql')
counts = {}
for table, rows in parser.parse():
    counts[table] = counts.get(table, 0) + len(rows)

conn = sqlite3.connect('certificate_manager.db')
db_s = conn.execute('SELECT COUNT(*) FROM students').fetchone()[0]
db_o = conn.execute('SELECT COUNT(*) FROM graduation_orders').fetchone()[0]

sql_s = counts.get('students_140', 0) + counts.get('students_q', 0)
sql_o = counts.get('order_university', 0)

print(f"SQL Students: {sql_s}")
print(f"DB Students: {db_s}")
print(f"SQL Orders: {sql_o}")
print(f"DB Orders: {db_o}")

# Check for linked orders
linked = conn.execute('SELECT COUNT(*) FROM students WHERE order_id IS NOT NULL').fetchone()[0]
unlinked = conn.execute('SELECT COUNT(*) FROM students WHERE order_id IS NULL').fetchone()[0]
print(f"Linked Students: {linked}")
print(f"Unlinked Students: {unlinked}")
