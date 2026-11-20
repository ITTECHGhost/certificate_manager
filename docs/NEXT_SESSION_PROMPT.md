# Prompt for the next session (paste into a new Claude Code session in F:\CR_PY\certificate_manager)

Read CLAUDE.md, docs/TODO.md and docs/PLAN_archive_and_next.md (only the track you work on).
Work on `main`, one step at a time: plan (≤10 lines) → my OK → tests first → build → `pytest -q` (one line)
→ commit (detailed message) → push only after my OK. Rules: `.ai/rules.md`.

Decisions already made 2026-11-20 (do not re-ask):
- ONE certificate_manager program for now; screens by the employee's units. Exe split postponed.
- Two tracks: A = graduation (extract paper orders/grade sheets → existing grades-matrix Excel
  template → existing bulk import; then a review screen), B = registration in `registration_web/`
  (Django 5.2 LTS admin, own SQLite DB, LAN only; NOT on MySQL 5.7, which Django 4.2+ does not support).
- Security token / units / archive in certificate_manager come after the registration season (track C).
- Never put real student data in git; sample images live outside the repo.

Next step: Track A step 2 (review screen) OR Track B day 1 — the user says which.
Track B day 1 = create `registration_web/` (own requirements file, pinned Django 5.2.x), models
Student, StudentDocument, Hold, Request, RequestStep; Arabic RTL admin (LANGUAGE_CODE='ar');
groups student_affairs/finance/legal with per-model permissions; ATOMIC_REQUESTS=True;
tests for permissions (finance cannot clear a legal hold; only the owning unit edits a hold).
Ask before adding any dependency to the client's requirements.txt (Django stays in its own file).
