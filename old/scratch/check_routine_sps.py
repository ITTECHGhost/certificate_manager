import os
import re
import sys

sys.path.insert(0, os.path.abspath('.'))

try:
    import db
except Exception as e:
    db = None

# 1. Fetch Routine SPs in Live Database or sql/SP.sql
db_routine_sps = {}

if db:
    try:
        conn = db.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT ROUTINE_NAME, ROUTINE_DEFINITION, DTD_IDENTIFIER 
            FROM INFORMATION_SCHEMA.ROUTINES 
            WHERE ROUTINE_SCHEMA = DATABASE() 
              AND ROUTINE_TYPE = 'PROCEDURE' 
              AND ROUTINE_NAME LIKE '%Routine%'
        """)
        rows = cursor.fetchall()
        for r in rows:
            # get parameters
            proc_name = r['ROUTINE_NAME']
            cursor.execute("""
                SELECT PARAMETER_MODE, PARAMETER_NAME, DTD_IDENTIFIER
                FROM INFORMATION_SCHEMA.PARAMETERS
                WHERE SPECIFIC_SCHEMA = DATABASE() AND SPECIFIC_NAME = %s
                ORDER BY ORDINAL_POSITION
            """, (proc_name,))
            params = cursor.fetchall()
            db_routine_sps[proc_name] = params
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error querying live DB: {e}")

# Also check sql/SP.sql for routine SPs
sp_file_sps = set()
sql_sp_file = os.path.join('sql', 'SP.sql')
if os.path.exists(sql_sp_file):
    with open(sql_sp_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        for m in re.finditer(r'CREATE\s+(?:DEFINER=`[^`]+`@`[^`]+`[\s\n]+)?PROCEDURE\s+`?(\w*Routine\w*)`?', content, re.IGNORECASE):
            sp_file_sps.add(m.group(1))

# 2. Check SP calls in repositories.py
repo_sp_calls = {}
repo_file = os.path.join('data', 'repositories.py')
if os.path.exists(repo_file):
    with open(repo_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        for idx, line in enumerate(lines, 1):
            for m in re.finditer(r'(?:callproc|_call_write|_call_read_all|_call_read_one)\s*\(\s*["\'](\w*Routine\w*)["\']', line, re.IGNORECASE):
                proc = m.group(1)
                repo_sp_calls.setdefault(proc, []).append(f"repositories.py:{idx}")

# 3. Check Routine FastAPI endpoints in api/main.py
api_file = os.path.join('api', 'main.py')
api_routes = []
api_sp_calls = {}
if os.path.exists(api_file):
    with open(api_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        for idx, line in enumerate(lines, 1):
            if '@app.' in line and 'routine' in line.lower():
                api_routes.append(f"Line {idx}: {line.strip()}")
            for m in re.finditer(r'callproc\s*\(\s*["\'](\w*Routine\w*)["\']', line, re.IGNORECASE):
                proc = m.group(1)
                api_sp_calls.setdefault(proc, []).append(f"api/main.py:{idx}")

print("================================================================================")
print("STUDY ROUTINE STORED PROCEDURES & FASTAPI API AUDIT")
print("================================================================================")
print(f"1. Routine SPs defined in Live MySQL DB: {len(db_routine_sps)}")
for proc_name, params in sorted(db_routine_sps.items()):
    p_str = ", ".join([f"{p['PARAMETER_MODE'] or 'IN'} {p['PARAMETER_NAME']} {p['DTD_IDENTIFIER']}" for p in params if p['PARAMETER_NAME']])
    print(f"   - {proc_name}({p_str})")

print(f"\n2. Routine SPs called in repositories.py ({len(repo_sp_calls)}):")
for proc_name, locs in sorted(repo_sp_calls.items()):
    print(f"   - {proc_name} -> {locs[0]}")

print(f"\n3. Routine SPs called directly in api/main.py ({len(api_sp_calls)}):")
for proc_name, locs in sorted(api_sp_calls.items()):
    print(f"   - {proc_name} -> {locs[0]}")

print(f"\n4. Registered FastAPI Study Routine Endpoints in api/main.py ({len(api_routes)}):")
for r in api_routes:
    print(f"   - {r}")

# Write to file
with open(os.path.join('scratch', 'routine_audit.txt'), 'w', encoding='utf-8') as out_f:
    out_f.write("STUDY ROUTINE AUDIT REPORT\n")
    out_f.write(f"Live DB Routine SPs: {list(db_routine_sps.keys())}\n")
    out_f.write(f"Repo Routine SP Calls: {list(repo_sp_calls.keys())}\n")
    out_f.write(f"API Routine SP Calls: {list(api_sp_calls.keys())}\n")
    out_f.write(f"API Endpoints:\n" + "\n".join(api_routes) + "\n")
