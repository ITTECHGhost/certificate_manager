# Next session (written 2026-11-23, DEV laptop)

Read CLAUDE.md, docs/TODO.md, then this. Do not re-scan the codebase.

State: release 2.6.0 is on the server. Local commits NOT pushed yet (aee13cc..c563aa9):
order-number duplicates fix + 4 scanner feeder commits. Ask the user before pushing.

1. Canon MF270 FEEDER still gives no image (glass works; Windows Scan works).
   - services/scanner.py `_feeder_transfer` / `_transfer_pages`. Tried: Transfer(JPEG) -> None;
     Transfer() twice -> "remote procedure call failed" (-2147023170); CommonDialog.ShowTransfer(BMP) -> still fails.
   - Driver formats: JPEG {..CAE}, BMP {..CAB}, {9980BD5B-...} (raw?). No PDF.
   - Ask the user to run `py -3 scans\feeder_test.py` (3 sheets in feeder) and paste output;
     use the way that works. PDF choice must leave ONLY the PDF (done in pages_to_pdf).
2. Server: after push, on the server pull/copy `certificate_manager_api/normalize_order_numbers.py`,
   run it without --apply (report), then with --apply. Order 138 (3/13/15710) duplicates an
   existing order: user merges students by hand, then deletes 138.
3. Then build 2.6.1 (changes-only zip from dist\manifest_v2.6.0.json) - ask first; stash templets/ changes.
4. Dev DB: run migration 0014 (`scripts\dev_backup_and_migrate.bat`).
5. Waiting on user: rankings table photos (CSV columns + Gemini prompt).
6. Later: per-user login token (migration 0008).

Never commit the user's templets/ changes. Tests: `py -3 -m pytest -q` (test_api_golden known failing).
