"""Rule: every client request that writes is ONE transaction: all of it is saved or none.

These checks keep the three things that make that true:
- the API connection pool does not autocommit, and a request that ends without commit
  is rolled back (deps.get_db);
- no endpoint commits more than once on one path (a commit halfway would leave half);
- no stored procedure commits or starts its own transaction.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "certificate_manager_api"


def test_request_without_commit_is_rolled_back():
    src = (API / "deps.py").read_text(encoding="utf-8")
    assert "conn.rollback()" in src and "in_transaction" in src
    assert "autocommit=True" not in src


def _commits_on_one_path(node) -> int:
    """Most commit() calls that can run in one pass through the function (if/else, try/except = alternatives)."""
    def walk(stmts):
        total = 0
        for s in stmts:
            if isinstance(s, ast.If):
                total += max(walk(s.body), walk(s.orelse))
            elif isinstance(s, ast.Try):
                total += max([walk(s.body + s.orelse + s.finalbody)] +
                             [walk(h.body) for h in s.handlers])
            elif isinstance(s, (ast.For, ast.While, ast.With)):
                inner = walk(s.body)
                total += inner * (2 if isinstance(s, (ast.For, ast.While)) else 1)
            else:
                total += sum(1 for x in ast.walk(s) if isinstance(x, ast.Call)
                             and getattr(x.func, "attr", "") == "commit")
        return total
    return walk(node.body)


# Not client requests: start-up maintenance that commits one finished item at a time on purpose
NOT_REQUESTS = {"order_images.py:move_blobs_to_files"}  # each page: file written, then its row; repeatable


def test_no_endpoint_commits_halfway():
    bad = []
    for f in sorted((API / "routers").glob("*.py")):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and _commits_on_one_path(n) > 1
                    and f"{f.name}:{n.name}" not in NOT_REQUESTS):
                bad.append(f"{f.name}:{n.lineno} {n.name}")
    assert not bad, "commit more than once in one request: " + ", ".join(bad)


def test_procedures_never_commit():
    sql = (ROOT / "sql" / "SP.sql").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(COMMIT|START\s+TRANSACTION|ROLLBACK)\b", sql, re.I | re.M)
