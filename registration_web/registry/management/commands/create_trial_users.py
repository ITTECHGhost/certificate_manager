"""Create staff users from a JSON file and put each in its unit group. Safe to run again.

File (keep it in the data folder, never in git):
  [{"username": "sa1", "full_name": "الاسم", "unit": "student_affairs"}, ...]
units: student_affairs | finance | legal
New users get a random password, written ONCE to --passwords-file (hand it over, then delete it).
Existing users keep their password; only name, staff flag and group are set.
"""
import json
import secrets
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

UNITS = ("student_affairs", "finance", "legal")


class Command(BaseCommand):
    help = "Create/update trial staff users from a JSON file (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("file")
        parser.add_argument("--passwords-file", default=None,
                            help="Default: <REGWEB_DATA_DIR>/trial_passwords.txt")

    def handle(self, *args, **opts):
        rows = json.loads(Path(opts["file"]).read_text(encoding="utf-8-sig"))
        for row in rows:
            if not row.get("username") or row.get("unit") not in UNITS:
                raise CommandError(f"Bad row (username and unit in {UNITS} required): {row}")
        out = Path(opts["passwords_file"] or Path(settings.DATA_DIR) / "trial_passwords.txt")
        new_lines = []
        with transaction.atomic():  # all or nothing
            groups = {u: Group.objects.get(name=u) for u in UNITS}
            for row in rows:
                user, created = User.objects.get_or_create(username=row["username"])
                if created:
                    password = secrets.token_urlsafe(9)
                    user.set_password(password)
                    new_lines.append(f"{user.username}\t{row['unit']}\t{password}")
                user.first_name = row.get("full_name", user.first_name)[:150]
                user.is_staff = True
                user.save()
                user.groups.remove(*[g for u, g in groups.items() if u != row["unit"]])
                user.groups.add(groups[row["unit"]])
        if new_lines:
            with out.open("a", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
        self.stdout.write(f"{len(rows)} users OK, {len(new_lines)} new (passwords in {out})")
