import re

text = open('certificate_manager.sql', 'r', encoding='utf-8').read()

# Find all CREATE TABLE statements
creates = re.findall(r'CREATE TABLE `(\w+)`', text)
print(f"Tables found: {creates}")
print()

targets = ['personnel', 'students', 'university_settings', 'courses',
           'departments', 'study_systems', 'graduation_orders', 'enrollments',
           'countries', 'governorates', 'user_preferences']

for t in targets:
    m = re.search(rf'CREATE TABLE `{t}`[^;]+;', text, re.DOTALL)
    if m:
        schema = m.group()[:1200].encode('ascii', 'replace').decode('ascii')
        print(f"--- {t} ---")
        print(schema)
        print()
    else:
        print(f"--- {t}: NOT FOUND ---")
        print()
