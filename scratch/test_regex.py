import re

sql = """
INSERT INTO
	`admin` (`id`, `name`, `username`, `password`, `terms`)
VALUES
	(
		11,
		'صادق ابراهيم',
		'sadiq',
		'sadiq1997',
		'مستخدم'
	);
"""

insert_pattern = re.compile(
    r"INSERT\s+INTO\s+`?([\w.]+)`?\s*\(([^)]+)\)\s*VALUES\s*(.*?);",
    re.DOTALL | re.IGNORECASE,
)

for match in insert_pattern.finditer(sql):
    print(f"Table: {match.group(1)}")
    print(f"Cols: {match.group(2)}")
    print(f"Values: {match.group(3)}")
