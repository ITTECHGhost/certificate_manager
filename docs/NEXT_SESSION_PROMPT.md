Read CLAUDE.md, docs/TODO.md and docs/PLAN_archive_and_next.md ("المسار ب" only). Rules: .ai/rules.md.
`git pull` first (with my OK). Work on `main`. Plan (≤10 lines) → my OK → tests first → build →
`pytest -q` (one line) → commit (detailed message) → push only after my OK.

Decisions (do not re-ask): registration_web/ = SEPARATE Django 5.2 web program; the Windows app is
unchanged. SQLite in REGWEB_DATA_DIR, never MySQL, LAN only, no offline mode. Server
172.50.1.100:2040, service RegWebRegistration. Work on DEV (launch config "registration-web",
port 8000) unless I say the real server is available.

Done day 5 (2026-11-20, DEV): /students/<pk>/holds/ — Student Affairs sees every hold in full
(kind, unit, note, open/cleared, by whom, when), read only; only the owning unit gets the clear
button and the server re-checks (403 otherwise). Admin student list: «القيود» link + action
«تصدير المحددين للبريد الجامعي» (Excel, RTL); /students/export/?ids= (SA only, only those ids).
New dependency openpyxl 3.1.5 (requirements.txt; install it on the server venv). 37 tests.
Open: EXPORT_COLUMNS in registry/views.py is a GUESS — replace with the real e-mail sample
columns (in-session only, never in git); /register/ field order still a guess; real server not
checked (git pull + pip install -r requirements.txt + migrate + restart, then one request through
3 units and one export); orphan .part sweep; no "reject" button.

Task: Track B, week 2 — one inbox per unit (requests it holds now, newest first, search by
name/national id, paginated), ID-card print, search + filter on students. Tests first: a unit sees
only its own inbox; search never leaks other units' held requests. End with: changed / how to
check / next step. Update TODO.md and rewrite this file.
