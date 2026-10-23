import sys
import os

with open("data/query.py", "r", encoding="utf-8") as f:
    content = f.read()

target = '    "ap.academic_year AS grouping_key "\n    "FROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap "'
replacement = '    "ap.academic_year AS grouping_key, "\n    "1 AS result_status_code, "\n    "\'PASSED\' AS result_status_label "\n    "FROM (SELECT * FROM academic_periods UNION ALL SELECT * FROM local_academic_periods) ap "'

content = content.replace(target, replacement)

with open("data/query.py", "w", encoding="utf-8") as f:
    f.write(content)
