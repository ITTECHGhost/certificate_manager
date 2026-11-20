Read CLAUDE.md, docs/TODO.md and docs/PLAN_archive_and_next.md ("المسار ب" only). Rules: .ai/rules.md.
`git pull` first (with my OK). Work on `main`. Plan (≤10 lines) → my OK → tests first → build →
`pytest -q` (one line) → commit (detailed message) → push only after my OK.

Decisions (do not re-ask): registration_web/ = SEPARATE Django 5.2 web program; the Windows app is
unchanged. SQLite in REGWEB_DATA_DIR, never MySQL, LAN only, no offline mode. Server
172.50.1.100:2040, service RegWebRegistration. Work on DEV (launch config "registration-web",
port 8000) unless I say the real server is available.

Done 2026-11-20 (DEV): /inbox/, ID card, admin search, «رفض الطلب» (services.reject_request).
Then orphan .part sweep: uploads.sweep_orphan_parts + `manage.py sweep_parts [--hours 24]
[--dry-run]`; only media/student_docs/**/*.part older than N hours, never final files or
backup .partial folders. 61 tests. No migration, no new dependency. Not yet scheduled.

Open: ID-card fields + layout are a GUESS (needs the real card sample); EXPORT_COLUMNS still a
guess (real columns in-session only, never in git); /register/ field order still a guess;
real server not checked (git pull + pip install -r requirements.txt + migrate + restart, then
one request through 3 units, one reject, one export, one inbox, one card print, one
`sweep_parts --dry-run`); add sweep_parts to the nightly task in install_service.ps1;
rejected requests are not yet listed anywhere except the student's page.

Task: real-server check if I say the server is available; otherwise a «مرفوضة» list
(rejected requests per unit, paginated). Tests first. End with: changed / how to check /
next step. Update TODO.md and rewrite this file.
