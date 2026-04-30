import re

with open("localhost_new.sql", "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

tables = re.findall(r"CREATE TABLE IF NOT EXISTS `([^`]+)`", content)
print("Tables found with backticks:")
print(tables)

tables2 = re.findall(r"CREATE TABLE ([^\s(]+)", content)
print("Tables found without backticks:")
print(tables2)

inserts = re.findall(r"INSERT\s+INTO\s+([^\s(]+)", content, re.IGNORECASE)
unique_inserts = sorted(list(set(inserts)))
print("Tables with INSERTs:")
print(unique_inserts)
