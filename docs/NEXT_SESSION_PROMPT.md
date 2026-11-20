Read CLAUDE.md, docs/TODO.md and docs/PLAN_archive_and_next.md ("المسار ب" only). Rules: .ai/rules.md.
`git pull` first (with my OK). Work on `main`. Plan (≤10 lines) → my OK → tests first → build →
`pytest -q` (one line) → commit (detailed message) → push only after my OK.

Decisions (do not re-ask): registration_web/ = SEPARATE Django 5.2 web program; the Windows app is
unchanged. SQLite in REGWEB_DATA_DIR, never MySQL, LAN only, no offline mode. Server
172.50.1.100:2040, service RegWebRegistration. Work on DEV (launch config "registration-web",
port 8000) unless I say the real server is available.

Done 2026-11-20 (DEV): week 2 = /inbox/, /students/<pk>/card/ ID card, student admin search/filters.
Then «رفض الطلب» on /requests/<pk>/: holding unit only (403 otherwise), annotation required
(server-side; JS check too), reject step + status «مرفوض» in ONE transaction
(services.reject_request). Rejected/accepted requests cannot move. 57 tests. No migration,
no new dependency.

Open: ID-card fields + layout are a GUESS (needs the real card sample); EXPORT_COLUMNS still a
guess (real columns in-session only, never in git); /register/ field order still a guess;
real server not checked (git pull + pip install -r requirements.txt + migrate + restart, then
one request through 3 units, one reject, one export, one inbox, one card print);
orphan .part sweep; rejected requests are not yet listed anywhere except the student's page.

Task: real-server check if I say the server is available; otherwise the orphan .part sweep.
Tests first. End with: changed / how to check / next step. Update TODO.md and rewrite this file.
