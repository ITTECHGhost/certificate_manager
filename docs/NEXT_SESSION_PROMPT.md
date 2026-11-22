# Next session (written 2026-11-22, DEV laptop)

Branch `overnight-builds` (NOT pushed, NOT merged into main) has:
- review dialog `3c4a59d`, rankings soft delete `46700c1`, feedback page `1d2e22a`
- A: feedback reply/status/edit/delete `2ac3bc8` (migration 0011)
- B: scanned pages for official ranking lists (migration 0012, router `ranking_images.py`,
  `services/ranking_images.py`, «الورقة الممسوحة» button in the lists table)
- Archive in «سجل الوثائق الصادرة» (migration 0013, router `issued_doc_files.py`, button «الأرشيف»
  in a record's dialog). Two lists: printed drafts (Word draft saved on the server at each print,
  printed_at) / issued (first signed copy = final: issue_date = that day, drafts hidden, edit locked).
main has `00b238a` (scripts/orders_csv_to_roster.py) — NOT pushed.

User steps still open:
1. mysqldump the dev DB to F:\CR_PY\db_backups_dev, then from certificate_manager_api:
   `py -3 migrate.py --sql-dir ..\sql` (runs 0011, 0012, 0013).
2. Restart start_server.bat, test feedback reply, ranking scans and the archive in the app; review dialog (later).
3. Try «استيراد الأوامر الممسوحة» (admins, sidebar) on a real Gemini CSV: create the orders in
   «أوامر التخرج» first, then import (link_only: no academic period). Script still works too.
4. Then: merge overnight-builds into main (ask), push with OK.

Known: tests/test_api_golden fails since ff05a22 (unrelated). Migration numbers: 0008 reserved
(identity), student_holds → 0014. Uncommitted templets/ changes belong to the user — don't commit.
Track B item 5 (real-server check) only when the server is available.

Update (2026-11-22, DEV): changes-only client update is built (commit on main, NOT pushed): scripts/release_manifest.py,
`make_client_patch.ps1 -Changes <manifest_vOLD.json>`, changes_* in version.json, updater falls back to the full zip.
Open: try it on the next real build (keep dist\manifest_v2.5.9... from THAT build: 2.5.9 has none, so the first
small zip can only be made from the release after it). tests/test_architecture fails on scripts/backup_and_migrate.py:25 (import db) — not from this change.
