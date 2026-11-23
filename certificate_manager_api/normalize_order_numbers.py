r"""Lists graduation orders whose number is not in the form 20707/12/3, and can fix them.

    py normalize_order_numbers.py           -> report only, writes nothing
    py normalize_order_numbers.py --apply   -> fixes the ones it can, in ONE transaction

--apply first dumps the whole database into backups\order_numbers_<time>.sql
(mysqldump) and stops if that fails, so nothing is changed without a backup.
Numbers with no part of 4+ digits, more than one, or one in the middle are never changed:
they are listed for someone to fix by hand in the program.
order_number.py here is a copy of utils/order_number.py (a test keeps them the same).
"""
import sys
from datetime import datetime
from pathlib import Path

import mysql.connector

from config import DBConfig
from order_number import normalize_order_number


def plan(rows: list) -> tuple[list, list, list]:
    """rows: id, order_number, department_id, study_system_id, graduation_semester.
    Returns (fix, review, clash): clash = the fixed number would be the SAME order as another row
    (same number, department, study system, semester: the unique key) - both are kept and listed
    to merge by hand; changing it would fail the whole run."""
    def key(r, number):
        return (number, r.get("department_id"), r.get("study_system_id"), r.get("graduation_semester"))
    taken = {key(r, r["order_number"] or ""): r["id"] for r in rows}
    fix, review, clash = [], [], []
    for r in rows:
        raw = r["order_number"] or ""
        norm = normalize_order_number(raw)
        if norm.needs_review:
            review.append((r["id"], raw))
        elif norm.value != raw:
            other = taken.get(key(r, norm.value))
            if other and other != r["id"]:
                clash.append((r["id"], raw, norm.value, other))
            else:
                fix.append((r["id"], raw, norm.value))
                taken[key(r, norm.value)] = r["id"]
    return fix, review, clash


def main(apply: bool) -> int:
    conn = mysql.connector.connect(host=DBConfig.DB_HOST, user=DBConfig.DB_USER,
                                   password=DBConfig.DB_PASSWORD, database=DBConfig.DB_NAME)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, order_number, department_id, study_system_id, graduation_semester "
                    "FROM graduation_orders ORDER BY id")
        fix, review, clash = plan(cur.fetchall())
        for oid, raw, new in fix:
            print(f"order {oid}: {raw!r} -> {new}")
        for oid, raw in review:
            print(f"order {oid}: {raw!r} NEEDS REVIEW (fix by hand)")
        for oid, raw, new, other in clash:
            print(f"order {oid}: {raw!r} is the SAME order as order {other} ({new}) - not changed; "
                  f"move its students to order {other} in the program, then delete order {oid}")
        print(f"{len(fix)} to fix, {len(review)} to review by hand, {len(clash)} duplicates to merge by hand")
        if apply and fix:
            from db import backup_db
            dump = Path(__file__).resolve().parent / "backups" / f"order_numbers_{datetime.now():%Y%m%d_%H%M%S}.sql"
            backup_db(dump)  # raises (and nothing is changed) if the dump fails
            if not dump.is_file() or dump.stat().st_size < 1000:
                raise SystemExit(f"backup looks empty, nothing changed: {dump}")
            print(f"backup: {dump}")
            try:
                for oid, _raw, new in fix:
                    cur.execute("UPDATE graduation_orders SET order_number = %s WHERE id = %s", (new, oid))
                conn.commit()
                print(f"fixed {len(fix)}")
            except Exception:
                conn.rollback()
                raise
        elif fix:
            print("report only; run with --apply to fix")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main("--apply" in sys.argv[1:]))
