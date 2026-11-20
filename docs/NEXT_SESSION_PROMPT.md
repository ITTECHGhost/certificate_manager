Read CLAUDE.md, docs/TODO.md and docs/PLAN_archive_and_next.md ("المسار ب" only). Rules: .ai/rules.md.
`git pull` first (with my OK). Work on `main`. Plan (≤10 lines) → my OK → tests first → build →
`pytest -q` (one line) → commit (detailed message) → push only after my OK.

Decisions (do not re-ask): registration_web/ = SEPARATE Django 5.2 web program (confirmed again
2026-11-20); the Windows app with offline cache is unchanged. SQLite in REGWEB_DATA_DIR, never MySQL,
LAN only, no offline mode. Server 172.50.1.100:2040, service RegWebRegistration.
Work on the DEV laptop against localhost (launch config "registration-web", port 8000) unless I say
the real server is available.

Done day 3 (2026-11-20, DEV): /register/ form (Student Affairs only) in sections, 11 new Student fields
(migration 0003), several files per document kind (JPG/PNG/PDF, ≤10 MB, signature checked on server),
temp .part → rows in one transaction → rename on commit. /documents/<pk>/ serves files after login +
unit check; /media/ is never served. Admin cannot add documents directly. 25 tests.
Open from day 3: field order is a GUESS — match it to the real paper form when I send a sample
(use it in-session only, never in git). Real server not yet checked (git pull + migrate + restart).
Orphan .part files can remain if the outer request rolls back; sweep by age later.

Task: Track B, day 4 — status («عند المالية / عند القانونية / مقبول») + «إرسال إلى وحدة» with
annotation, each step logged (user, IP, time) using services.send_request. A request passes 3 units.
Tests first: a step cannot be edited; a unit cannot send a request it does not hold.
End with: changed / how to check / next step. Update TODO.md and rewrite this file for day 5.
