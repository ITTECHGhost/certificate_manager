Read CLAUDE.md, docs/TODO.md and docs/PLAN_archive_and_next.md ("المسار ب" only). Rules: .ai/rules.md.
`git pull` first (with my OK). Work on `main`. Plan (≤10 lines) → my OK → tests first → build →
`pytest -q` (one line) → commit (detailed message) → push only after my OK.

Decisions (do not re-ask): registration_web/ = SEPARATE Django 5.2 web program (confirmed again
2026-11-20); the Windows app with offline cache is unchanged. SQLite in REGWEB_DATA_DIR, never MySQL,
LAN only, no offline mode. Server 172.50.1.100:2040, service RegWebRegistration.
Work on the DEV laptop against localhost (launch config "registration-web", port 8000) unless I say
the real server is available.

Done day 4 (2026-11-20, DEV): Request.stage_label («عند شؤون الطلبة/المالية/القانونية»، «مقبول»،
«مرفوض»); services.send_request now refuses (before any row) a unit that does not hold the request,
a closed request, an unknown unit; new services.accept_request (approve step + status done).
/requests/<pk>/: any unit member views status + step log (user, IP from REMOTE_ADDR, time); only
the holder sends (unit + annotation) or accepts; others get 403 on POST. Admin list links to it.
Migration 0004 = label change only. 31 tests.
Open: field order of /register/ still a GUESS (match the real paper sample, in-session only);
real server not yet checked (git pull + migrate + restart, then one request through 3 units);
orphan .part sweep by age; no "reject" button yet (status rejected exists, unused).

Task: Track B, day 5 — Student Affairs sees all financial/legal holds of a student in full
(read only; only the owning unit clears); Excel export for the university e-mail (ask me for the
sample columns — use in-session only, never in git). Tests first: SA cannot clear a hold; export
contains only the requested students. End with: changed / how to check / next step.
Update TODO.md and rewrite this file for week 2.
