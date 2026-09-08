import re, glob, os

sps = set()
for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                for m in re.finditer(r'callproc\s*\(\s*["\']([^"\']+)["\']', content):
                    sps.add(m.group(1))
                for m in re.finditer(r'_call_(?:write|read_all|read_one|read_multi)\s*\(\s*["\']([^"\']+)["\']', content):
                    sps.add(m.group(1))

print(f"Total unique Stored Procedures called in python code: {len(sps)}\n")
for sp in sorted(sps):
    print(f"- {sp}")
