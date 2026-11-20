from django.core.management.base import BaseCommand

from registry.uploads import sweep_orphan_parts


class Command(BaseCommand):
    help = "Delete orphan upload temps (media/student_docs/**/*.part) older than --hours (default 24)."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        found, deleted = sweep_orphan_parts(opts["hours"], dry_run=opts["dry_run"])
        self.stdout.write(f"Orphan .part files: found {found}, deleted {deleted}")
