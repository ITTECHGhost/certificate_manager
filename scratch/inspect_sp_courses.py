with open('sql/SP.sql', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

import re
matches = re.findall(r'CREATE DEFINER=`root`@`localhost` PROCEDURE `(sp_GetCertificate_Courses_[^`]+)`\([^)]*\)\s*BEGIN(.*?)END //', text, re.DOTALL)
for name, body in matches:
    print(f"=== PROCEDURE {name} ===")
    lines = [l.strip() for l in body.splitlines() if 'AS' in l or 'SELECT' in l or 'c.name' in l or 'subject_name' in l]
    for l in lines[:15]:
        print("  ", l)
