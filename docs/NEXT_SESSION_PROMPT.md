Read CLAUDE.md, docs/TODO.md and docs/PLAN_archive_and_next.md ("المسار ب" only). Rules: .ai/rules.md.
`git pull` first (with my OK). Work on `main`. Plan (≤10 lines) → my OK → tests first → build →
`pytest -q` (one line) → commit (detailed message) → push only after my OK.

Decisions (do not re-ask): registration_web/ = SEPARATE Django 5.2 web program; the Windows app is
unchanged. SQLite in REGWEB_DATA_DIR, never MySQL, LAN only, no offline mode. Server
172.50.1.100:2040, service RegWebRegistration. Work on DEV (launch config "registration-web",
port 8000) unless I say the real server is available.

Done week 2 (2026-11-20, DEV): /inbox/ — open requests held NOW by the user's units, newest
first, search by name/national id (unit filter applied before search → no leak), 25 per page;
superuser sees all; no unit → 403. Admin header «عرض الموقع» → /inbox/.
/students/<pk>/card/ printable A6 ID card (Student Affairs only, 403 otherwise); admin student
list «طباعة الهوية» link. Student admin: search national_id + mother_name, filter gender +
graduation_year. 48 tests. No migration, no new dependency.

Open: ID-card fields + layout are a GUESS (no photo yet; needs the real card sample);
EXPORT_COLUMNS still a guess (real columns in-session only, never in git); /register/ field
order still a guess; real server not checked (git pull + pip install -r requirements.txt +
migrate + restart, then one request through 3 units, one export, one inbox, one card print);
orphan .part sweep; no "reject" button.

Task: pick one — real-server check, or the "reject" button (holding unit only, annotation
required, one transaction). Tests first. End with: changed / how to check / next step.
Update TODO.md and rewrite this file.
