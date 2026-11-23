# Next session (written 2026-11-23, DEV laptop)

Read CLAUDE.md, docs/TODO.md, then this. Do not re-scan the codebase.

State: release 2.6.0 is on the server. All commits up to b331948 are pushed.

1. Canon MF270 FEEDER still gives no image (glass works; Windows Scan works).
   - services/scanner.py `_feeder_transfer` / `_transfer_pages`. Tried: Transfer(JPEG) -> None;
     Transfer() twice -> "remote procedure call failed" (-2147023170); CommonDialog.ShowTransfer(BMP) -> still fails.
   - Driver formats: JPEG {..CAE}, BMP {..CAB}, {9980BD5B-...} (raw?). No PDF.
   - Ask the user to run `py -3 scans\feeder_test.py` (3 sheets in feeder) and paste output;
     use the way that works. PDF choice must leave ONLY the PDF (done in pages_to_pdf).
2. DONE 2026-11-23: order numbers normalized on the server; order 138 merged by hand.
3. Then build 2.6.1 (changes-only zip from dist\manifest_v2.6.0.json) - ask first; stash templets/ changes.
4. DONE 2026-11-23: migration 0014 run on the dev DB.
5. Waiting on user: rankings table photos (CSV columns + Gemini prompt).
6. Later: per-user login token (migration 0008).

Never commit the user's templets/ changes. Tests: `py -3 -m pytest -q` (test_api_golden known failing).
