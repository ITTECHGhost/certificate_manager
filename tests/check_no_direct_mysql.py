# =============================================================================
# tests/check_no_direct_mysql.py — Architecture guard: the client never talks to MySQL
#
# Every database request must go through FastAPI. This check fails if any
# client module imports mysql.connector, the MySQL helper module `db`, or the
# credentials class `DBConfig`, or calls requests.get/post/... directly
# instead of the shared api_client.
#
# Run:  python tests/check_no_direct_mysql.py      (exit code 1 = violation)
# =============================================================================

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Server code, archived code and developer-only DB tools are allowed to reach MySQL.
EXCLUDED_DIRS = {"old", "certificate_manager_api", "tests", "tools", "installer", "build", "dist", ".venv",
                 ".git", ".claude", ".agent", ".gemini", ".nicegui", "__pycache__"}
EXCLUDED_FILES: set[str] = set()
HTTP_CALLS = {"get", "post", "put", "patch", "delete", "request", "Session"}


def find_violations() -> list[str]:
    violations = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if rel.parts[0] in EXCLUDED_DIRS or (len(rel.parts) == 1 and rel.name in EXCLUDED_FILES):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError as exc:
            violations.append(f"{rel}: cannot parse ({exc})")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "db" or alias.name.startswith("mysql"):
                        violations.append(f"{rel}:{node.lineno}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                if node.module == "db" or node.module.startswith("mysql"):
                    violations.append(f"{rel}:{node.lineno}: from {node.module} import ...")
                elif node.module == "config" and any(a.name == "DBConfig" for a in node.names):
                    violations.append(f"{rel}:{node.lineno}: from config import DBConfig")
            # Every API call must use api_client (shared session, HTTPS verification, app key)
            elif (rel.name != "api_client.py" and isinstance(node, ast.Attribute)
                  and isinstance(node.value, ast.Name) and node.value.id == "requests"
                  and node.attr in HTTP_CALLS):
                violations.append(f"{rel}:{node.lineno}: requests.{node.attr} (use api_client.{node.attr.lower()})")
    return violations


if __name__ == "__main__":
    found = find_violations()
    if found:
        print("Direct MySQL access found in client code (must go through FastAPI):")
        for v in found:
            print("  " + v)
        sys.exit(1)
    print("OK: no client module accesses MySQL directly.")
