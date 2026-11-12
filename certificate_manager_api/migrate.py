# =============================================================================
# migrate.py — bring the server database up to date (run by setup_server.bat)
#
#   python migrate.py --sql-dir <folder with migrations\ and SP.sql> [--dry-run]
#   python migrate.py --sql-dir <folder> --baseline     (first time on an existing server)
#
# 1. sql\migrations\NNNN_name.sql — each runs ONCE. The table schema_migrations
#    records what ran (file name + SHA-256). A file that already ran and was
#    changed afterwards is refused: write a new migration instead.
# 2. sql\SP.sql — every stored procedure, re-applied on every update (the file is
#    all DROP IF EXISTS + CREATE), so a procedure can never stay out of date.
#    DEFINER clauses are removed, so the API's own account can create them.
#
# The MySQL login comes from db_config.json (config.py). Stops at the first error
# and exits 1; the caller (setup_server.ps1) then restores the old version.
# =============================================================================

import argparse
import hashlib
import re
import sys
from pathlib import Path

MIGRATION_NAME = re.compile(r"^(\d{4})_[\w\-]+\.sql$")
LEDGER_DDL = (
    "CREATE TABLE IF NOT EXISTS schema_migrations ("
    " filename VARCHAR(255) NOT NULL PRIMARY KEY,"
    " sha256 CHAR(64) NOT NULL,"
    " applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
    " baseline TINYINT(1) NOT NULL DEFAULT 0)"
)
_DEFINER = re.compile(r"DEFINER\s*=\s*(`[^`]*`|'[^']*'|\w+)\s*@\s*(`[^`]*`|'[^']*'|[\w.%]+)\s*", re.IGNORECASE)


def strip_definer(sql: str) -> str:
    """CREATE DEFINER=`root`@`localhost` PROCEDURE … -> CREATE PROCEDURE …"""
    return _DEFINER.sub("", sql)


def split_sql(text: str) -> list[str]:
    """Statements of a .sql file, honouring DELIMITER lines, quotes and comments."""
    statements: list[str] = []
    delim = ";"
    buf: list[str] = []
    i, n = 0, len(text)
    quote = ""
    at_line_start = True
    while i < n:
        ch = text[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and quote != "`" and i + 1 < n:
                buf.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = ""
            i += 1
            continue
        if at_line_start:
            line_end = text.find("\n", i)
            line = text[i:] if line_end == -1 else text[i:line_end]
            m = re.match(r"\s*DELIMITER\s+(\S+)\s*$", line, re.IGNORECASE)
            if m:
                _flush(buf, statements)
                delim = m.group(1)
                i = n if line_end == -1 else line_end + 1
                continue
        if ch in "'\"`":
            quote = ch
            buf.append(ch)
            i += 1
            at_line_start = False
            continue
        if text.startswith("--", i) and (i + 2 >= n or text[i + 2] in " \t\r\n"):
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if ch == "#":
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if text.startswith(delim, i):
            _flush(buf, statements)
            i += len(delim)
            at_line_start = False
            continue
        buf.append(ch)
        at_line_start = ch == "\n"
        i += 1
    _flush(buf, statements)
    return statements


def _flush(buf: list[str], out: list[str]) -> None:
    stmt = "".join(buf).strip()
    buf.clear()
    if stmt:
        out.append(stmt)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def migration_files(sql_dir: Path) -> list[Path]:
    folder = sql_dir / "migrations"
    if not folder.is_dir():
        return []
    files = sorted(p for p in folder.iterdir() if MIGRATION_NAME.match(p.name))
    numbers = [p.name[:4] for p in files]
    dupes = {x for x in numbers if numbers.count(x) > 1}
    if dupes:
        raise SystemExit(f"[ERROR] Two migrations share a number: {sorted(dupes)}")
    return files


def plan(files: list[Path], applied: dict[str, str]) -> tuple[list[Path], list[str]]:
    """(files still to run, errors for files changed after they ran)."""
    todo, errors = [], []
    for p in files:
        done = applied.get(p.name)
        if done is None:
            todo.append(p)
        elif done != sha256_of(p):
            errors.append(f"{p.name} changed after it ran on this server — add a new migration instead")
    return todo, errors


def _connect():
    import mysql.connector
    from config import DBConfig as c
    return mysql.connector.connect(host=c.DB_HOST, user=c.DB_USER, password=c.DB_PASSWORD,
                                   database=c.DB_NAME, autocommit=True)


def _run_file(cur, path: Path, strip: bool) -> int:
    text = path.read_text(encoding="utf-8-sig")
    if strip:
        text = strip_definer(text)
    count = 0
    for stmt in split_sql(text):
        cur.execute(stmt)
        if cur.with_rows:
            cur.fetchall()
        count += 1
    return count


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sql-dir", required=True, type=Path)
    ap.add_argument("--dry-run", action="store_true", help="show what would run; change nothing")
    ap.add_argument("--baseline", action="store_true",
                    help="mark every migration as already applied (existing server, first time)")
    ap.add_argument("--skip-procedures", action="store_true")
    ap.add_argument("--procedures-only", action="store_true",
                    help="re-apply SP.sql only (used to put the previous procedures back on a roll-back)")
    args = ap.parse_args(argv)

    files = [] if args.procedures_only else migration_files(args.sql_dir)
    sp_file = args.sql_dir / "SP.sql"

    if args.dry_run:
        for p in files:
            print(f"[MIGRATION] {p.name}: {len(split_sql(p.read_text(encoding='utf-8-sig')))} statements")
        if sp_file.exists() and not args.skip_procedures:
            stmts = split_sql(strip_definer(sp_file.read_text(encoding="utf-8-sig")))
            creates = sum(1 for s in stmts if re.match(r"CREATE\s+PROCEDURE", s, re.IGNORECASE))
            print(f"[PROCEDURES] SP.sql: {len(stmts)} statements, {creates} procedures")
        print("[DRY RUN] nothing was changed")
        return 0

    conn = _connect()
    cur = conn.cursor()
    cur.execute(LEDGER_DDL)
    cur.execute("SELECT filename, sha256 FROM schema_migrations")
    applied = {name: sha for name, sha in cur.fetchall()}

    if args.baseline:
        for p in files:
            if p.name not in applied:
                cur.execute("INSERT INTO schema_migrations (filename, sha256, baseline) VALUES (%s, %s, 1)",
                            (p.name, sha256_of(p)))
                print(f"[BASELINE] {p.name} marked as applied")
        print("[OK] Baseline done")
        return 0

    todo, errors = plan(files, applied)
    if errors:
        for e in errors:
            print(f"[ERROR] {e}")
        return 1

    for p in todo:
        try:
            n = _run_file(cur, p, strip=True)
        except Exception as exc:
            print(f"[ERROR] Migration {p.name} failed: {exc}")
            return 1
        cur.execute("INSERT INTO schema_migrations (filename, sha256) VALUES (%s, %s)", (p.name, sha256_of(p)))
        print(f"[OK] Migration {p.name} ({n} statements)")
    if not todo:
        print("[OK] No new migrations")

    if sp_file.exists() and not args.skip_procedures:
        try:
            n = _run_file(cur, sp_file, strip=True)
        except Exception as exc:
            print(f"[ERROR] Stored procedures (SP.sql) failed: {exc}")
            return 1
        print(f"[OK] Stored procedures re-applied ({n} statements)")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
