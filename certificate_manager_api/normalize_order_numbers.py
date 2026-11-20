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


def main(apply: bool) -> int:
    conn = mysql.connector.connect(host=DBConfig.DB_HOST, user=DBConfig.DB_USER,
                                   password=DBConfig.DB_PASSWORD, database=DBConfig.DB_NAME)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, order_number FROM graduation_orders ORDER BY id")
        fix, review = [], []
        for row in cur.fetchall():
            raw = row["order_number"] or ""
            norm = normalize_order_number(raw)
            if norm.needs_review:
                review.append((row["id"], raw))
            elif norm.value != raw:
                fix.append((row["id"], raw, norm.value))
        for oid, raw, new in fix:
            print(f"order {oid}: {raw!r} -> {new}")
        for oid, raw in review:
            print(f"order {oid}: {raw!r} NEEDS REVIEW (fix by hand)")
        print(f"{len(fix)} to fix, {len(review)} to review by hand")
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
