Read CLAUDE.md, docs/TODO.md and docs/PLAN_archive_and_next.md ("المسار ب" only). Rules: .ai/rules.md.
`git fetch`; pull only with my OK. Work on `main`. For each item: plan (≤10 lines) → my OK →
tests first → build → `pytest -q` (registration_web: `.venv\Scripts\python -m pytest -o addopts="" -q`
shows the count) → commit (detailed message) → tick TODO.md → ask before the next item. Push only after my OK.

Decisions (do not re-ask): registration_web/ = SEPARATE Django 5.2 program; Windows app unchanged.
SQLite in REGWEB_DATA_DIR, never MySQL, LAN only, no offline mode. Server 172.50.1.100:2040,
service RegWebRegistration. DEV = launch config "registration-web", port 8000.
No real samples yet: do NOT touch the ID card layout, EXPORT_COLUMNS or /register/ field order.

Done 2026-11-20 (DEV): item 4 accepted-students roster export /students/roster/ (registry/roster_export.py, admission year picked on the page; 92 tests + 1 strict xfail). Item 3 signed-copy archive (SignedCopy model, SQLite migration 0005, uploads.add_signed_copy, /requests/<pk>/signed/, /signed/<pk>/[delete/]; 83 tests). Item 2 nightly sweep_parts line in regweb_backup.bat (git pull on server is enough; 71 tests). Item 1 «مرفوضة» list `/rejected/` (views.rejected, rejected.html, link
on /inbox/; unit filter before search; Student Affairs sees all; reject reason column). 70 tests.

Next items, in order:
Known Windows-app bug (bug-ledger 2026-11-20): bulk import reads gender from the nationality column; one-line fix pending (separate session, Windows app).
5. Real-server check only if I say the server is available (see TODO).
Still open (needs real samples): ID-card fields/layout, EXPORT_COLUMNS, /register/ field order.
