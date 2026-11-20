# CLAUDE.md — certificate_manager

Existing management / archiving app, partly built and in use. Keep answers short; act more than explain.

## 1. Session start
- Read this file, then `docs/TODO.md` and `docs/NEXT_SESSION_PROMPT.md`. Read other files only when the task needs them.
- `git fetch`; say if origin/main has commits this checkout lacks (pull only with the user's OK).
- Do NOT re-scan the codebase. The Project Map below is the source of truth; `.ai/anatomy.md` has more detail.
- Live architecture rules: `.ai/rules.md` (short, always applies).
- Lessons/bugs: `.ai/bug-ledger.md` — never read whole. `grep` it for the area you touch; before a release or a server/laptop update read `.ai/releases.md`.

## 2. Working style
- One feature or fix per session; at the end tell the user to `/clear`.
- Bigger than a small fix: short plan (files, tables, tests, ≤10 lines) and wait for OK. Small clear fixes: just do them.
- Minimum change. No refactor/rename/reformat of untouched code. Follow existing patterns. No new dependency without asking.
- Never delete data, migrations or files without asking. Unclear → ask ONE short question.
- Work on `main`. Commit with a detailed message (what was seen, on which laptop, what was and was not checked). Push only after the user's OK.

## 3. Token discipline
- Don't print whole files; show changed parts. Grep before reading large files.
- Never read lock files, build output, venv, `old/`, media/uploads, DB dumps, `local_cache.db`.
- Quiet test output (`pytest -q`); summarise long logs. Suggest `/compact` with a focus note when long.

## 4. Skills (only when the task matches; this file wins over any skill's "always")
- writing-plans: features touching 3+ files; small tasks. executing-plans: INLINE only, no subagents unless asked.
- test-driven-development: business logic (grades, fees, records, permissions, archive rules). Not for pure UI tweaks.
- systematic-debugging: any bug whose cause isn't obvious after one look.
- verification-before-completion: before saying done, run the test/command, show one line.
- brainstorming: only for a NEW module with unclear scope. ui-ux-pro-max: only for a new/redesigned screen.

## 5. Quality rules
- Server-side validation for every form. Server enforces roles/units for anything that edits or deletes.
- Paginate and search lists. Soft delete / archive over hard delete for important records.
- DB changes only via `sql/migrations/NNNN_*.sql` + `sql/fixes/rollback_NNNN_*.sql`; the AI writes the files, the user runs them (dev DB first, after mysqldump to `F:\CR_PY\db_backups_dev`). The AI never writes to MySQL.
- Every write request is ONE transaction (all or nothing) — guarded by `tests/test_all_or_nothing.py`.
- Secrets in env/config files outside git; never print keys or passwords. Never put real student data in git.
- Word templates (`templets/`) are edited by the user only, then print-tested.
- Ask before any release build; bump the version only when told (`scripts/set_version.py`).

## 6. End of each task, give exactly
1. What changed (1–3 lines) 2. How to check it (one command or click path) 3. Next suggested step (one line)
Then rewrite `docs/NEXT_SESSION_PROMPT.md` (≤25 lines) and tick `docs/TODO.md`.

## Project Map (≤30 lines; update when structure changes)
- Stack: Python 3, NiceGUI 3 desktop client (pywebview, Arabic RTL) → FastAPI server → MySQL 5.7 (Windows server, service). Client is a PyInstaller exe with in-app updater.
- `main.py` client entry (port 2323). `nicegui_screens/` screens (students, courses, departments, personnel, graduation_orders, certificate, issued_certificates, official_rankings_view, reports, settings, study_routines, bulk import). `nicegui_ui/` shared UI kit (ui_components, ui_theme, theme.css, i18n, state).
- `data/repositories/` client data access (via API only); `api_client.py`, `api_config.py`, `server_config.json` (not in git).
- `sync_engine.py` offline mode: SQLite `local_cache.db` replica + outbound queue (never open it for writing by hand).
- `services/` excel_import (students + grades matrix), office_automation (Word → PDF), order_images, official_ranking_import, template_sync, updater, server_update, first_connection.
- `utils/` order_number, study_type, date_parsing, arabic_words, health_check, logger.
- `certificate_manager_api/` FastAPI: `main.py` (app, X-App-Key audit/enforce), `deps.py` (`get_db`, rollback on failure), `routers/` (students, courses, departments, graduation, certificates, issued_certificates, official_rankings, bulk_import, order_images, personnel+login, reports, settings, study_routines, study_systems, thesis, sync, system, templates, updates, server_update), `migrate.py`.
- DB: `sql/schema.sql` (20 tables: students, enrollments, courses, departments, graduation_orders, issued_certificates, personnel, permissions, study_systems, study_routines…), `sql/SP.sql` stored procedures (called via `/sp/read|write|write-batch`), `sql/migrations/0001–0007`, `sql/fixes/` one-off fixes + rollbacks.
- Templates: `templets/` Word templates (docxtpl). Installer/build: `scripts/build_release.bat`, `make_client_patch.ps1`, `installer/`.
- Known gap (2026-11-20): `/api/login` issues no per-user token; the server cannot tell who calls it. Fix planned (docs/PLAN_archive_and_next.md).
- Run client: `py -3 main.py`. Run server (dev): `certificate_manager_api\start_server.bat`.
- Tests: `py -3 -m pytest -q` (72 files; `-m mysql` for read-only tests against local MySQL).
- Version: `app_version.py` (2.5.9).

## Shared notes between the DEV laptop and the SERVER laptop
Sessions run on two laptops (DEV: repo + build tools; SERVER: MySQL + API). Only this GitHub repo is shared.
- When a session learns something the other laptop needs, add one short dated entry to `.ai/bug-ledger.md` (or `.ai/releases.md`) saying which laptop saw it; commit it with the related change; push with the user's OK.
- Detailed commit messages are the other half of the hand-over.
