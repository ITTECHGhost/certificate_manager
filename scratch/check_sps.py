import re

with open('sql/SP.sql', encoding='utf-8') as f:
    text = f.read()

for m in re.finditer(r'PROCEDURE `([^`]+)`', text):
    name = m.group(1)
    if 'student' in name.lower():
        line = text[:m.start()].count('\n') + 1
        print(f'{line}: {name}')
