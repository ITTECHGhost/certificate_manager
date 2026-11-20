from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from registry.backup import run_backup


class Command(BaseCommand):
    help = "Back up the SQLite DB (online backup API) and media to <data>/backups/<date>, keep 30 days."

    def add_arguments(self, parser):
        parser.add_argument("--dest", default=None, help="Backup root (default: <REGWEB_DATA_DIR>/backups)")
        parser.add_argument("--keep-days", type=int, default=30)

    def handle(self, *args, **opts):
        root = Path(opts["dest"]) if opts["dest"] else Path(settings.DATA_DIR) / "backups"
        dest = run_backup(settings.DATA_DIR, root, keep_days=opts["keep_days"])
        self.stdout.write(f"Backup OK: {dest}")
