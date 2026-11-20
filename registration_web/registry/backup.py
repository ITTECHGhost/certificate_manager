"""Nightly backup: SQLite online backup (safe while the service runs) + media folder.

Each run writes <backup_root>/<YYYY-MM-DD>/ with registration.sqlite3 and media/,
then removes dated folders older than keep_days. Restore steps: RESTORE.md.
"""
import datetime
import shutil
import sqlite3
from pathlib import Path

DB_NAME = "registration.sqlite3"


def backup_database(src: Path, dest: Path) -> None:
    """Copy a live SQLite DB with the sqlite3 backup API (never a raw file copy)."""
    source = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    target = sqlite3.connect(dest)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    check = sqlite3.connect(dest)
    try:
        result = check.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        check.close()
    if result != "ok":
        raise RuntimeError(f"Backup copy failed integrity_check: {result}")


def prune(backup_root: Path, today: datetime.date, keep_days: int) -> None:
    cutoff = today - datetime.timedelta(days=keep_days)
    for folder in backup_root.iterdir():
        try:
            day = datetime.date.fromisoformat(folder.name)
        except ValueError:
            continue  # only touch folders this job created
        if folder.is_dir() and day < cutoff:
            shutil.rmtree(folder)


def run_backup(data_dir, backup_root, today=None, keep_days=30) -> Path:
    data_dir, backup_root = Path(data_dir), Path(backup_root)
    today = today or datetime.date.today()
    dest = backup_root / today.isoformat()
    tmp = backup_root / (today.isoformat() + ".partial")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    backup_database(data_dir / DB_NAME, tmp / DB_NAME)
    media = data_dir / "media"
    if media.exists():
        shutil.copytree(media, tmp / "media")
    if dest.exists():  # second run on the same day replaces the first
        shutil.rmtree(dest)
    tmp.rename(dest)
    prune(backup_root, today, keep_days)
    return dest
