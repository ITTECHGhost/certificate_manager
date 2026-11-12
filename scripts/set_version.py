r"""Write a new APP_VERSION into app_version.py. Usage: py -3 scripts\set_version.py 2.3.0"""
import re
import sys
from pathlib import Path

if len(sys.argv) != 2 or not re.fullmatch(r"\d+\.\d+\.\d+", sys.argv[1]):
    sys.exit("Usage: set_version.py X.Y.Z  (numbers only, e.g. 2.3.0)")
path = Path(__file__).resolve().parents[1] / "app_version.py"
data = path.read_bytes()  # bytes: keeps the file's own line endings
new, count = re.subn(rb'^APP_VERSION = "[^"]+"', b'APP_VERSION = "' + sys.argv[1].encode() + b'"', data, flags=re.M)
if count != 1:
    sys.exit("APP_VERSION line not found in app_version.py")
path.write_bytes(new)
print(f"APP_VERSION = {sys.argv[1]}")
