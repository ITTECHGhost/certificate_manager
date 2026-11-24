# Next session (written 2026-11-23, DEV laptop)

Read CLAUDE.md, docs/TODO.md, then this. Do not re-scan the codebase.

State: release 2.6.0 is on the server. All commits up to b331948 are pushed.

1. DONE 2026-11-24: Canon MF270 feeder now scans through WinRT (Windows Scan app API via PowerShell);
   real test 3 sheets -> 3-page PDF from scanner.py. User to confirm once in the app (py -3 main.py).
2. DONE 2026-11-23: order numbers normalized on the server; order 138 merged by hand.
3. Then build 2.6.1 (changes-only zip from dist\manifest_v2.6.0.json) - ask first; stash templets/ changes.
4. DONE 2026-11-23: migration 0014 run on the dev DB.
5. Waiting on user: rankings table photos (CSV columns + Gemini prompt).
6. Later: per-user login token (migration 0008).
7. Student ID tool (tools/student_ids/make_ids.py, not committed yet): checks + problems.xlsx done,
   real run 76 passed / 28 failed. Current xlsx export has NO "Email address"/phone columns ->
   dedup falls back to Arabic name; re-export the form sheet and run again. Needs pillow-heif.

Never commit the user's templets/ changes. Tests: `py -3 -m pytest -q` (test_api_golden known failing).
