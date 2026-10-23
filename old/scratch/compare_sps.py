import re
import difflib

def parse_sql_procedures(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    procs = {}
    pattern = r'CREATE\s+(?:DEFINER=`[^`]+`@`[^`]+`[\s\n]+)?PROCEDURE\s+`?(\w+)`?\s*\((.*?)\)[\s\n]*BEGIN(.*?\n)END'
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    
    for name, params, body in matches:
        p_clean = ' '.join(params.split())
        body_lines = [line.strip() for line in body.splitlines() if line.strip()]
        procs[name] = {
            'params': p_clean,
            'body_lines': body_lines,
            'full_text': p_clean + '\n' + '\n'.join(body_lines)
        }
    return procs

test_sp = parse_sql_procedures('sql/test_SPs.sql')
db_sp = parse_sql_procedures('sql/SP.sql')

report = []
report.append(f"Total procedures in test_SPs.sql: {len(test_sp)}")
report.append(f"Total procedures in SP.sql: {len(db_sp)}\n")

for name in sorted(test_sp.keys()):
    report.append('=' * 75)
    report.append(f"PROCEDURE: {name}")
    report.append('=' * 75)
    if name not in db_sp:
        report.append("Status: NOT FOUND IN DATABASE (sql/SP.sql)\n")
    else:
        t = test_sp[name]
        d = db_sp[name]
        
        if t['params'] != d['params']:
            report.append(f"Parameters diff:\n  Backup:   ({t['params']})\n  Database: ({d['params']})")
            
        # Ignore comments and whitespace differences in SQL body comparison
        t_clean_lines = [l for l in t['body_lines'] if not l.startswith('--')]
        d_clean_lines = [l for l in d['body_lines'] if not l.startswith('--')]
        
        if t_clean_lines == d_clean_lines:
            report.append("Status: EXACT LOGICAL MATCH (Ignoring formatting/comments)\n")
        else:
            report.append("Status: DIFFERENCES DETECTED")
            diff = difflib.unified_diff(
                t_clean_lines, d_clean_lines,
                fromfile='sql/test_SPs.sql (Backup)',
                tofile='sql/SP.sql (Live Database)',
                lineterm=''
            )
            report.append('\n'.join(diff))
            report.append('\n')

report_text = '\n'.join(report)
with open('scratch/sp_diff_report.txt', 'w', encoding='utf-8') as f:
    f.write(report_text)

print("Comparison complete. Report saved to scratch/sp_diff_report.txt")
