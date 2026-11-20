Read CLAUDE.md, docs/TODO.md and docs/PLAN_archive_and_next.md ("المسار ب" only). Rules: .ai/rules.md.
`git pull` first (with my OK). Work on `main`. Plan (≤10 lines) → my OK → tests first → build →
`pytest -q` (one line) → commit (detailed message) → push only after my OK.

Decisions (do not re-ask): registration_web/ = Django 5.2.19 + waitress, SQLite in REGWEB_DATA_DIR
(server: C:\registration_data), never touches MySQL, LAN only. Server = 172.50.1.100 (changeable via
settings.json), port 2040, service RegWebRegistration (pywin32 from system Python, like the API),
independent of Apache (AppServ now, maybe WAMP later). Never put real student data in git.

Done day 2 (2026-11-20, DEV): install_service.ps1, regweb_service.py, nightly backup_regweb (02:00,
30 days), create_trial_users (JSON in data folder), RESTORE.md, static served by Django. 13 tests.
Check first: did the SERVER follow registration_webINSTALL.md (port 2040)? Can staff log in from another PC? If not, fix that first.

Task: Track B, day 3 — registration form in the order of the real paper form + document upload
(several pages, phone photos, PDF).
1. First ask me for the filled sample forms (and permission to use them only in this session).
2. Media is NOT public: serve uploads only through a login-checked view (unit permissions).
3. Upload: temp file → rows in the transaction → rename after commit (rules.md). Size/type checks server-side.
4. Tests first: a student with 3 documents saves all-or-nothing; an anonymous user gets no file.
End with: changed / how to check / next step. Update TODO.md and rewrite this file for day 4.
