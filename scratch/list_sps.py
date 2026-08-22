import re

with open('sql/SP.sql', 'r', encoding='utf-8') as f:
    text = f.read()

matches = re.findall(r'DROP PROCEDURE IF EXISTS `([^`]+)`', text)
print(f"Total procedures in SP.sql: {len(matches)}")
print(sorted(set(matches)))
