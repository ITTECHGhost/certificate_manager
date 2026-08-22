import re

with open('sql/SP.sql', 'r', encoding='utf-8') as f:
    text = f.read()

m = re.search(r'CREATE\s+.*PROCEDURE\s+`GetStudentDossierByID`.*BEGIN(.*?)END', text, re.DOTALL)
if m:
    with open('scratch/dossier_sp.sql', 'w', encoding='utf-8') as out:
        out.write(m.group(0))
    print("Saved to scratch/dossier_sp.sql")
else:
    print("Not found")
