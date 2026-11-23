# Next session (written 2026-11-23, DEV laptop)

Release 2.6.0 is built (dist\release\2.6.0) and main is pushed. Not yet installed anywhere.
- SERVER laptop: copy CertificateManagerUpdate-2.6.0 by USB, run Update.bat as Administrator
  (backs up DB + files, migrations 0011-0014, restarts API, publishes the client patch).
- DEV DB: run scripts\dev_backup_and_migrate.bat once more for 0014 (feedback_images).
- dist\manifest_v2.6.0.json exists: the next release can be changes-only
  (make_client_patch.ps1 -Changes dist\manifest_v2.6.0.json).

New in 2.6.0 (not clicked through by the AI): issued-documents archive + drafts, ranking-list
scans, feedback replies + pictures (top-bar «الملاحظات», screenshot), scanned-order import that
creates the missing order first, links students, keeps the scan with the order; orders page
tabs (أوامر التخرج | قوائم الترتيب الرسمية); rankings import from CSV + scanner card.

Waiting on the user: photos of the official ranking table (to match CSV columns + Gemini prompt),
real scanner test, real Gemini CSV import, Track B item 5.
Next build (recommended): per-user login token (docs/PLAN_archive_and_next.md).
Migrations: 0008 reserved (identity), student_holds -> 0015. Uncommitted templets/ changes
belong to the user — never commit them (stash during a release build, then pop).
