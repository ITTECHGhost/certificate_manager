# Prompt for the next session (paste into a new Claude Code session in F:\CR_PY\certificate_manager)

Read CLAUDE.md, docs/TODO.md and docs/PLAN_archive_and_next.md first. Work on `main`, one
part at a time: build → test → commit (detailed message) → push only after my OK. Ask me
before any migration on the server DB (dev DB: mysqldump first into F:\CR_PY\db_backups_dev).
Never open local_cache.db for writing, never print keys or passwords, ask before any release
build, bump the version only when I say. Every write request is ONE transaction (rule in
.ai/cerebrum.md, guarded by tests/test_all_or_nothing.py).

## Decisions already made (do not re-ask)
- Programs: ONE codebase, SEPARATE executables (certificate manager, archive, student
  affairs; legal and financial later), sharing one client library (login, sync, API client,
  UI kit, updater) and one FastAPI server + MySQL.
- Units now: شؤون الطلبة، وحدة التخرج، الوحدة المالية، الوحدة القانونية، الأقسام العلمية،
  مكتب العميد، مكتب المعاون العلمي، مكتب المعاون الإداري. An employee can belong to SEVERAL
  units, with admin rights per unit. The server (not the program) enforces unit access.
- Archive: documents issued by the program + any signed, stamped, numbered document. Each
  unit searches/opens its own documents; only that unit's admin deletes/edits/replaces
  (logged, old file kept hidden). Storage: a "virtual folder" on the server behind one API.
- Student holds (legal/financial notes): one shared table (student, unit, note, open/cleared,
  who/when). Student affairs sees the FULL details; only the owning unit edits or clears.
- OCR: part of the archive, engine switchable (local default; cloud option off by default,
  key on the server only, every import logged). Test local models on real photos AFTER the
  archive program exists: PaddleOCR (Arabic), Qwen2.5-VL 3B/7B via Ollama, Qari-OCR, Surya.
- The server must refuse program versions too old for it (minimum version per program).

## Order of work (quick ones first)
1. Update files with changes only (plan section 2): manifest per release, delta package,
   version check, backup + verify + automatic undo; wheels only when requirements change.
   Try 2.5.9 → next on the dev laptop.
2. Feedback page (plan section 3): button on every screen, admin page, offline queue.
3. Units and permissions foundation: migration 0008 (+ rollback) for units, personnel_units
   (many-to-many, is_admin), student_holds, feedback; server-side checks; minimum version
   per program.
4. Split the client into shared library + per-program entry points; build script makes
   one exe per program; updater handles each.
5. Archive program (plan section 1), starting from «سجل الوثائق الصادرة».
6. Official rankings page (like the graduation orders page) and a test with a real Excel
   file from student affairs.
7. OCR model comparison on my sample photos, then the import wizard.
8. Student affairs program: admission archive and documents, registering students (name,
   department, study type), holds shown with full details before admission is completed.

Start with step 1. Before coding, show me the design in a few lines and wait for my OK.
