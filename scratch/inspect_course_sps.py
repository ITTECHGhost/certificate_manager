with open('sql/SP.sql', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

import re
matches = re.findall(r'CREATE DEFINER=`root`@`localhost` PROCEDURE `(sp_GetCertificate_Courses_[^`]+)`\([^)]*\)\s*BEGIN(.*?)END //', text, re.DOTALL)
for name, body in matches:
    print(f"=== PROCEDURE {name} ===")
    print(body[:800])
