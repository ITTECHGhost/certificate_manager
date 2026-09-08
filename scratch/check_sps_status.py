import os
import re
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath('.'))

try:
    import db
except Exception as e:
    print(f"Error importing db: {e}")
    db = None

# 1. Find all SPs called in Python codebase
sps_in_code = {}

# Target core data files or sweep python files carefully
target_files = []
for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['.git', 'brain', 'venv', '.gemini', 'scratch']):
        continue
    for file in files:
        if file.endswith('.py'):
            target_files.append(os.path.join(root, file))

for path in target_files:
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        for line_idx, line in enumerate(lines, 1):
            # match callproc("Name", ...) or _call_xxx("Name", ...)
            for m in re.finditer(r'callproc\s*\(\s*["\']([A-Za-z0-9_]+)["\']', line):
                proc = m.group(1)
                sps_in_code.setdefault(proc, []).append(f"{path}:{line_idx}")
            for m in re.finditer(r'_call_(?:write|read_all|read_one|read_multi)\s*\(\s*["\']([A-Za-z0-9_]+)["\']', line):
                proc = m.group(1)
                sps_in_code.setdefault(proc, []).append(f"{path}:{line_idx}")

# 2. Check Live MySQL Database SPs if connected
live_sps = {}
if db:
    try:
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT ROUTINE_NAME, ROUTINE_DEFINITION, DTD_IDENTIFIER FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_SCHEMA = DATABASE() AND ROUTINE_TYPE = 'PROCEDURE'")
        rows = cursor.fetchall()
        for r in rows:
            live_sps[r['ROUTINE_NAME']] = r
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"\nCould not query MySQL Live DB: {e}")

# 3. Check SPs defined in sql/SP.sql
sql_sp_file = os.path.join('sql', 'SP.sql')
file_sps = set()
if os.path.exists(sql_sp_file):
    with open(sql_sp_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        for m in re.finditer(r'CREATE\s+(?:DEFINER=`[^`]+`@`[^`]+`[\s\n]+)?PROCEDURE\s+`?(\w+)`?', content, re.IGNORECASE):
            file_sps.add(m.group(1))

# 4. Save audit to report text file
report = []
report.append("================================================================================")
report.append("STORED PROCEDURE AUDIT REPORT")
report.append("================================================================================")
report.append(f"Total unique SPs referenced in Python code: {len(sps_in_code)}")
report.append(f"Total SPs existing in Live MySQL DB: {len(live_sps)}")
report.append(f"Total SPs defined in sql/SP.sql: {len(file_sps)}\n")

missing_in_live = [sp for sp in sorted(sps_in_code.keys()) if sp not in live_sps]
missing_in_sql = [sp for sp in sorted(sps_in_code.keys()) if sp not in file_sps]
in_db_not_code = [sp for sp in sorted(live_sps.keys()) if sp not in sps_in_code]

report.append(f"--- 1. SPs USED IN CODE BUT MISSING IN LIVE DB ({len(missing_in_live)}) ---")
if missing_in_live:
    for sp in missing_in_live:
        report.append(f"  [MISSING IN DB] {sp}")
        for loc in sps_in_code[sp]:
            report.append(f"     at {loc}")
else:
    report.append("  [OK] All SPs used in code exist in the live MySQL Database!")

report.append(f"\n--- 2. SPs USED IN CODE BUT MISSING IN sql/SP.sql ({len(missing_in_sql)}) ---")
if missing_in_sql:
    for sp in missing_in_sql:
        report.append(f"  [MISSING IN FILE] {sp}")
else:
    report.append("  [OK] All SPs used in code exist in sql/SP.sql!")

report.append(f"\n--- 3. ALL SPs USED IN CODE ({len(sps_in_code)}) ---")
for sp in sorted(sps_in_code.keys()):
    in_live_str = "EXISTS in Live DB" if sp in live_sps else "MISSING in Live DB"
    in_file_str = "EXISTS in sql/SP.sql" if sp in file_sps else "MISSING in sql/SP.sql"
    report.append(f"  - {sp}: {in_live_str} | {in_file_str}")

report.append(f"\n--- 4. LIVE DB SPs NOT REFERENCED IN CODE ({len(in_db_not_code)}) ---")
for sp in in_db_not_code:
    report.append(f"  - {sp}")

report_content = "\n".join(report)
print(report_content)

with open(os.path.join('scratch', 'sp_audit_results.txt'), 'w', encoding='utf-8') as out_f:
    out_f.write(report_content)

