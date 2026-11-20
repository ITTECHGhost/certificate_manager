# Prompt for the next session (paste into a new Claude Code session in F:\CR_PY\certificate_manager)

Read CLAUDE.md, docs/TODO.md and docs/PLAN_archive_and_next.md ("المسار ب" only). Rules: .ai/rules.md.
`git pull` first (with my OK). Work on `main`. Plan (≤10 lines) → my OK → tests first → build →
`pytest -q` (one line) → commit (detailed message) → push only after my OK.

Decisions already made 2026-11-20 (do not re-ask):
- Registration runs in a small Django app in `registration_web/` (APPROVED). Django 5.2.x LTS, its own
  SQLite DB; it never touches certificate_manager's MySQL (Django 4.2+ does not support MySQL 5.7).
  LAN only, served by waitress as a Windows service later (day 2).
- certificate_manager stays ONE program; its token/units/archive work waits until after the season.
- Never put real student data in git.

Task: Track B, day 1 — the skeleton that staff can log into.
1. `registration_web/` with its own `requirements.txt` (pinned Django 5.2.x, waitress; ask before anything else).
   Do not touch the client's requirements.txt.
2. Settings: LANGUAGE_CODE='ar', TIME_ZONE='Asia/Baghdad', ATOMIC_REQUESTS=True, SECRET_KEY and
   ALLOWED_HOSTS from environment variables, DEBUG off by default, MEDIA_ROOT outside the repo.
3. Models (utf8, created_at/created_by, no hard delete): Student (Arabic name, English name,
   department, study type, status), StudentDocument (file, kind, pages, sha256), Hold (student, unit,
   kind financial/legal, note, open/cleared, who/when), Request + RequestStep (from/to unit,
   action, annotation, user, IP, time; steps append-only).
4. Admin in Arabic RTL: search, filters, pagination; groups student_affairs / finance / legal.
   Server rule: only the owning unit edits or clears a Hold; student_affairs sees all holds read-only.
5. Tests first: permissions (finance cannot clear a legal hold), RequestStep cannot be edited,
   a failed save writes nothing.
End with: changed / how to check (`py -3 manage.py runserver` + login path) / next step. Update
TODO.md, Project Map in CLAUDE.md (new folder), and rewrite this file for day 2.
