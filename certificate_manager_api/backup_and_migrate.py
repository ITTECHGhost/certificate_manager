r"""One click: mysqldump backup -> copy the server file folders -> show pending migrations ->
run them (after a yes). Stops if the backup fails. Login comes from db_config.json; nothing is printed.

    py -3 certificate_manager_api/backup_and_migrate.py --backup-dir F:\CR_PY\db_backups_dev [--server]
"""
import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "certificate_manager_api"
sys.path.insert(0, str(API))
FILE_FOLDERS = ("order_images", "ranking_images", "issue_archive")   # under C:\AppServ on the server


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup-dir", required=True, type=Path)
    ap.add_argument("--server", action="store_true", help="also make/copy the C:/AppServ file folders")
    ap.add_argument("--yes", action="store_true", help="do not ask before migrating")
    a = ap.parse_args(argv)

    import db
    import migrate

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    dump = a.backup_dir / f"before_migrate_{stamp}.sql"
    print(f"[1] Backup -> {dump}")
    try:
        db.backup_db(dump)
    except Exception as exc:
        print(f"    BACKUP FAILED, nothing changed: {exc}")
        return 1
    if dump.stat().st_size < 1000:
        print("    BACKUP looks empty, nothing changed.")
        return 1
    print(f"    OK ({dump.stat().st_size // 1024} KB)")

    if a.server:
        print("[2] File folders")
        for name in FILE_FOLDERS:
            src = Path("C:/AppServ") / name
            src.mkdir(parents=True, exist_ok=True)
            dst = a.backup_dir / f"files_{stamp}" / name
            shutil.copytree(src, dst, dirs_exist_ok=True)
            print(f"    {src} (copied to {dst})")

    sql_dir = ROOT / "sql"
    print("[3] Pending migrations:")
    if migrate.main(["--sql-dir", str(sql_dir), "--dry-run"]) != 0:
        return 1
    if not a.yes and input("Run them now? (y/n) ").strip().lower() != "y":
        print("Stopped. Nothing changed (backup kept).")
        return 0
    rc = migrate.main(["--sql-dir", str(sql_dir)])
    print("DONE." if rc == 0 else f"MIGRATION FAILED. Restore with: mysql <db> < \"{dump}\"")
    return rc


if __name__ == "__main__":
    sys.exit(main())
