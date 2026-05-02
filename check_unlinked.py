
from tools.migrate_mysql import SQLParser
parser = SQLParser('CSIT_SQL_DATABASE2.sql')
for table, rows in parser.parse():
    if table in ['students_140', 'students_q']:
        offset = 2000 if '140' in table else 0
        for r in rows:
            sid = int(r[0]) + offset
            if sid in [34, 36, 163, 257, 286]:
                print(f"Student {r[1]} ID {sid} Order: '{r[11]}'")
