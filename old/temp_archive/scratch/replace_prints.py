import re

path = 'f:/CR_PY/certificate_manager/data/repositories.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Simple exact string replacements
content = content.replace(
    'print(f"API request failed: {e}")',
    'log_system(f"API request failed: {e}", "WARNING")'
)

content = content.replace(
    'print(f"API request failed: {e}. Falling back to SQLite cache.")',
    'log_system(f"API request failed: {e}. Falling back to SQLite cache.", "WARNING")'
)

content = content.replace(
    'print(f"Supplemental fetch failed: {e}")',
    'log_system(f"Supplemental fetch failed: {e}", "WARNING")'
)

content = content.replace(
    'print(f"API supplemental fetch failed for {sid}: {e}")',
    'log_system(f"API supplemental fetch failed for {sid}: {e}", "WARNING")'
)

# 2. Regex for flush=True error/warning prints
# e.g. print(f"[ERROR]...", flush=True) -> log_system(f"[ERROR]...", "ERROR")
def repl_error(m):
    return f'log_system({m.group(1)}, "ERROR")'

def repl_warning(m):
    return f'log_system({m.group(1)}, "WARNING")'

content = re.sub(r'print\((f?"\[ERROR\].*?"), flush=True\)', repl_error, content)
content = re.sub(r'print\((f?"\[WARNING\].*?"), flush=True\)', repl_warning, content)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Replacement successful")
