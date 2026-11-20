# Prompt for the next session (paste into a new Claude Code session in F:\CR_PY\certificate_manager)

Read CLAUDE.md, docs/TODO.md and docs/PLAN_archive_and_next.md ("المسار ب" only). Rules: .ai/rules.md.
`git pull` first (with my OK). Work on `main`. Plan (≤10 lines) → my OK → tests first → build →
`pytest -q` (one line) → commit (detailed message) → push only after my OK.

Decisions already made (do not re-ask):
- Registration runs in `registration_web/` (Django 5.2.19 LTS, waitress), its own SQLite DB in
  REGWEB_DATA_DIR outside the repo; it never touches certificate_manager's MySQL. LAN only.
- certificate_manager stays ONE program; its token/units/archive work waits until after the season.
- Never put real student data in git.

Done on day 1 (2026-11-20, DEV laptop): project `regweb/`, app `registry/` (Student, StudentDocument,
Hold, Request, RequestStep), Arabic RTL admin, groups student_affairs / finance / legal (migration
0002), hold ownership in `registry/services.py`, steps append-only, ATOMIC_REQUESTS. 9 tests in
`registration_web/registry/tests/`. Dev deps in `requirements-dev.txt` (pytest, pytest-django).

Task: Track B, day 2 — install on the SERVER laptop so staff log in from their browsers.
1. First ask me: Python version on the server (3.11+?), free LAN port, server's LAN IP/name,
   names of two trial staff per unit.
2. A `registration_web\install_service.ps1` (run as Administrator by me): venv, pip install -r
   requirements.txt, migrate, collectstatic, create the data folder, set the env vars
   (REGWEB_SECRET_KEY generated once and kept in the data folder, not in git; REGWEB_ALLOWED_HOSTS),
   register waitress as a Windows service (ask before adding NSSM or pywin32 — no new dependency
   without asking). Static files served by the app (ask before adding WhiteNoise).
3. Firewall rule for the port, LAN profile only.
4. Nightly backup: SQLite online backup (`sqlite3` .backup API, not a file copy) + media folder to
   a dated folder; keep 30 days; a restore test documented step by step.
5. A management command to create the trial users and put them in their unit group.
6. Tests first: backup produces a readable DB copy; the user command is idempotent.
End with: changed / how to check (browser on another PC → http://<server>:<port>/admin/) / next
step. Add a `.ai/releases.md` entry for the server steps done by hand. Update TODO.md and rewrite
this file for day 3.
