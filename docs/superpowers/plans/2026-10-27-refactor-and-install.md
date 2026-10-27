# Refactor & Installers Implementation Plan

> **For agentic workers:** Phases 0, 1, 2, 6, 7 and 8 are executed from the exact runbooks in
> `runbooks/` (written for Claude Haiku; read `runbooks/00-README.md` first). Phases 3, 4 and 5
> (the file splits) need judgement and run on **Sonnet or Opus**, from this document, using
> superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Certificate Manager installable and split the four 2–4k-line files into focused modules,
with no change in behaviour:
- client laptops get a per-user `setup.exe`;
- the server gets a one-folder bundle with an idempotent `setup_server.bat`.

**Architecture:**
1. A safety net: a pytest suite with an ordered API-route snapshot, golden read-only API answers, and a public-names snapshot.
2. Repo hygiene.
3. One `app_paths` module, so the installed build writes only to `%LOCALAPPDATA%\CertificateManager` (from source, everything stays in the project folder).
4. The splits, guarded by the snapshots.
5. Packaging: PyInstaller → Inno Setup for the client, and a PowerShell-built bundle for the server.

**Tech Stack:** Python 3.14 (64-bit), NiceGUI 3.14.0, pywebview 6.2.1, FastAPI 0.137.2, uvicorn 0.49.0, MySQL 8 (AppServ), SQLite, PyInstaller 6.21.0, Inno Setup 6.7, pytest 9.1.1, PowerShell 5.1 / cmd.

**Spec:** No separate spec. The decisions below are the spec.

---

## Execution order and models

| Order | Phase | Model | Source of truth | Dry-run status (2026-10-27, scratch copy of `COLLAGE` @ 251ee0c) |
|---|---|---|---|---|
| 1 | 0 Safety net | Haiku | `runbooks/phase-0-safety-net.md` | passed: 41 tests, 1 commit |
| 2 | 1 Hygiene & secrets | Haiku | `runbooks/phase-1-hygiene.md` | passed: 44 tests, also in a clean venv from the pinned requirements |
| 3 | 2 Data folder, updater, version | Haiku | `runbooks/phase-2-paths.md` | passed: 62 tests, including an OTA patch into an Arabic + space path |
| 4 | 6 Client build & installer | Haiku | `runbooks/phase-6-client-installer.md` | passed: frozen exe starts and seeds its data folder; setup compiles; silent install/reinstall/uninstall test passes |
| 5 | 7 Server bundle & setup | Haiku | `runbooks/phase-7-server-bundle.md` | passed: 67 tests; bundle has no secrets; setup keeps server files and migrates an old `config.py`; offline wheels install |
| 6 | 3 API split | Sonnet/Opus | this document | not dry-run (judgement work) |
| 7 | 4 Repositories split | Sonnet/Opus | this document | not dry-run |
| 8 | 5 Screens split | Sonnet/Opus | this document | not dry-run |
| 9 | 8 Docs, final release, rollout | Haiku | `runbooks/phase-8-docs-rollout.md` | passed (docs edits apply; release + bundle + both install tests) |

One runbook or phase per session. Phases 6 and 7 come before the splits so that a safe installer exists early.
Phase 8 rebuilds the release after the splits.

## Decisions (all approved by the user on 2026-10-27)

| # | Decision |
|---|---|
| D1 | Client laptops get a real installer (Inno Setup). The server gets a bundle plus `setup_server.bat`, which wraps the existing service/HTTPS tools. |
| D2 | Make the program install-ready, then split `certificate_manager_api/main.py`, `data/repositories.py`, `nicegui_screens/settings_screen.py` and `nicegui_screens/certificate_screen.py`. Behaviour stays the same. |
| D3 | Stop tracking secrets, student data and runtime files. Rotate the MySQL password. Git history is not rewritten. |
| D4 | Per-user install: program in `%LOCALAPPDATA%\Programs\CertificateManager`, data in `%LOCALAPPDATA%\CertificateManager`. OTA patches need no admin rights; data survives updates and uninstall. |
| D5 | A random NiceGUI `storage_secret` per install (`.storage_secret` in the data folder). |
| D6 | A dedicated MySQL account `certman_api` with rights on `certificate_manager` only (`sql/fixes/2026-10-27_04_api_db_account.sql`, run by the user). |
| D7 | Haiku executes exact runbooks. The splits (Phases 3–5) run on Sonnet/Opus, because copying large code blocks by hand is where a weak executor fails silently. |

## Findings fixed by the runbooks (from the code survey and the dry runs)

1. **Writable files resolved three different ways.** In a PyInstaller build they landed in `_internal\`, which
   an update overwrites, so offline edits in `local_cache.db` could be lost. Fixed in Phase 2. A legacy cache is
   also migrated, both by the app and by the installer.
2. **The OTA patch extracted into `_internal\`, and `apply_patch.bat` ran from the folder it overwrote.** Phase 2
   fixes both: it targets `INSTALL_DIR`, runs a temp copy of the `.bat`, and quotes the command with `cmd /s`.
3. **`client.spec` shipped the build PC's `server_config.json` (with its app key) and did not ship `assets/`.**
   Fixed in Phase 6. The build also lacked `multiprocessing.freeze_support()`, which the native window needs; added in Phase 2.
4. **Secrets and personal data were in git:**
   - the MySQL root password in 3 `.py` files;
   - `certificates/` (student names);
   - SQL dumps, including `sql/SQLite.sql`, a full data dump;
   - `logs/`, `.nicegui/`.

   Untracked in Phase 1. Git history is unchanged, so the password must be rotated (D6).
5. **Duplicates and dead files:** root `db.py`/`config.py`, `theme copy.css`. `docxtpl`, `pywebview`, `openpyxl`, `psutil`,
   `python-multipart` were missing from `requirements.txt`, and nothing was pinned. Fixed in Phase 1.
6. **`POST /sync` and `/api/sync` are registered twice** (`main.py` lines ~625 and ~3757); Starlette serves the first.
   This is handled in Phase 3, Task 3.1.

## Global Constraints

- The assistant never writes to MySQL. Schema and account changes ship as numbered files in `sql/fixes/` for the user.
- Legacy files move to `old/`, never deleted. Files that hold passwords or student data go to the ignored
  `old/root_duplicates/` or `old/sql_dumps/`.
- Code is changed with Write/Edit only, never with scripts that rewrite source files (`.ai/cerebrum.md`).
- Every API method+path stays registered **in the same order** (`tests/snapshots/api_routes.json`, 153 entries).
- Every name in `tests/snapshots/public_names.json` stays importable from the same module path.
- `tests/check_no_direct_mysql.py` stays green: the client never talks to MySQL.
- From source, all data stays in the project root. The installed build writes only to the data folder (`app_paths`).
- FastAPI runs only through `certificate_manager_api\start_server.bat` in a visible console. Never run a hidden server on 2030.
- The deployed server copy changes only when the user runs `setup_server.bat`.
- Never committed: `server_config.json`, `app_keys.json`, `db_config.json`, `*.key`, `local_cache.db`, `.storage_secret`,
  `certificates/`, `logs/`, `.nicegui/`, `sql/SQLite.sql`, `tests/.golden/`, `dist/`, `build/`.
- Work happens on branch `refactor/install-ready` (created in Phase 0 from `COLLAGE`), with one commit per task.
  It is merged to `main` by PR (the user pushes).

## Review Focus (each pinned by a test in the runbooks)

1. Upgrading a laptop with unsynced offline edits loses nothing. Covered by `test_prepare_migrates_legacy_db_without_overwriting` and the `-OldDir` case in `installer/client/test_install.ps1`.
2. Paths with spaces and Arabic letters work. Covered by `test_prepare_handles_space_and_arabic_path`, `test_apply_patch_handles_space_and_arabic_paths`, and the Arabic data folder in `test_install.ps1`.
3. An OTA patch on an installed build lands next to the exe and keeps `server_config.json`. Covered by `test_patch_targets_install_dir_and_runs_temp_copy` and `test_apply_patch_handles_space_and_arabic_paths`.
4. No Word / no print spooler gives a clear message, not a crash. Covered by `tests/test_office_fallbacks.py` and the installer prerequisite warnings.
5. Re-running `setup_server.bat` keeps the server's own files. Covered by case A in `installer/server/test_setup_server.ps1`.

## Smoke checklist (manual, for Phases 3–5)

Start the API with `certificate_manager_api\start_server.bat` in a visible console. Close it afterwards and confirm port 2030 is free.

- **S1** `py -3 main.py` → the window opens; login works online.
- **S2** Students: search, open a profile, open course enrollments.
- **S3** Generate one year-based and one semester-based certificate (Word + PDF). Print preview opens.
- **S4** Close the server console → offline badge. Search and certificate generation still work.
- **S5** Settings: server tab, "Sync templates from server", logs tab, printers tab.
- **S6** Restart the server console → the offline queue syncs (pending 0).
- **S7** `git status --short` shows nothing outside ignored paths.

---

## Phase 3 — Split `certificate_manager_api/main.py` (≈4,000 lines) — Sonnet/Opus

Prerequisite: the Phase 0–2 runbooks are done (Phases 6–7 may be done too).

The guards, run before and after every task:
- Before the task: `py -3 -m pytest -m mysql --record-golden`. This re-records today's answers immediately before the change, because the dev DB changes over time.
- After the task:
  - `py -3 -m pytest`, which includes the ordered route snapshot;
  - `py -3 -m pytest -m mysql`, the golden comparison;
  - S1+S2 against `start_server.bat`.

`tests/helpers.py::run_probe` imports the API in a subprocess with cwd = `certificate_manager_api/`.

Target layout. It stays flat, because uvicorn runs `main:app` with the folder as cwd, and `fastapi_service.py` and `setup_server` depend on that:

```
certificate_manager_api/
  main.py            # app, lifespan, app-key middleware, include_router calls in original order (≤250 lines)
  deps.py            # logger, get_db + pool, decode_db_value, execute_sp_fetchall/one, _require_admin
  routers/system.py          # /ping /health/db /sp/* /replica/* /table-count/* /admin/*
  routers/sync.py            # /sync and helpers (resolve_payload_fks, _apply_sync_actions, conflict checks, …)
  routers/students.py        # /students/*
  routers/departments.py     # /departments/*
  routers/study_systems.py   # /study-systems/*
  routers/courses.py         # /courses/* /api/courses/*
  routers/personnel.py       # /personnel/* /login /api/login /logout /permissions /roles /user-roles
  routers/academic.py        # /academic-periods /periods /enrollments
  routers/graduation.py      # /graduation-orders /orders
  routers/settings.py        # /settings /user
  routers/certificates.py    # /certificates /lookups
  routers/thesis.py          # /thesis /supervisors
  routers/dashboard.py       # /api/dashboard/*
  routers/study_routines.py  # /study-routine*
  routers/issued_certificates.py  # /issued-certificates /certificate-numbers
```

Rules for every Phase 3 task:
- Move code verbatim. Change only `@app.` → `@router.` and the imports. Payload models move with their routes.
- `main.py` includes the routers in the order of the table. The existing `bulk_import`/`updates`/`templates`
  routers keep their place (they are included before the inline routes today).
- The moved code is a cut from `main.py` (Edit) plus a new module (Write). No scripts.

### Task 3.1: `deps.py` + `routers/system.py` + `routers/sync.py`, and the unreachable `/sync`
- [ ] Check that both method+path pairs of `process_offline_sync_batch` (`@app.post("/sync")` and `@app.post("/api/sync")` near the end of `main.py`) also appear earlier in `api_routes.json`. If so, move the function to `old/api_unreachable_routes.py`. Delete exactly its two entries from `tests/snapshots/api_routes.json` by hand (never re-record the route snapshot), and say so in the commit message.
- [ ] Create `deps.py`. The signatures are copied exactly. `main.py` re-imports the names, so `from main import get_db` keeps working (check `routers/*.py` first).
- [ ] Create `routers/system.py` and `routers/sync.py`; remove the moved blocks from `main.py`.
- [ ] Run the guards. Commit `refactor(api): extract deps, system and sync routers`.

### Task 3.2: students, departments, study_systems, courses routers
- [ ] Same steps. Commit `refactor(api): extract students/departments/study-systems/courses routers`.

### Task 3.3: personnel/auth, academic, graduation, settings routers
- [ ] Same steps, plus S1 with a correct password, a wrong password, and a "must change password" account.
  Commit `refactor(api): extract personnel, academic, graduation, settings routers`.

### Task 3.4: certificates, thesis, dashboard, study_routines, issued_certificates routers; trim `main.py`
- [ ] Same steps, plus:
  - `main.py` ≤ 250 lines;
  - `py -3 -c "import ast; ast.parse(open('certificate_manager_api/fastapi_service.py').read())"`;
  - S3 (certificate numbers are reserved and issued).

  Commit `refactor(api): extract remaining routers; main.py is wiring only`.

---

## Phase 4 — Split `data/repositories.py` (≈3,840 lines) into a package — Sonnet/Opus

`data/repositories.py` becomes `data/repositories/`. Its `__init__.py` re-exports **every** name in
`tests/snapshots/public_names.json["data.repositories"]`. That list includes imported names such as `API_URL`,
`DB_PATH` and helper functions, not only classes. `import data.repositories as _repos` in `sync_engine.py` must keep working.
Since Phase 2 the module imports `app_paths`; keep that import in every new module that uses it
(`RoleRepository`, `AuditRepository`).

```
data/repositories/
  __init__.py          # re-exports only (+ `from .auth import AuthRepository`)
  base.py              # imports, safe_cast, _local_ready, _refreshes_local_copy, OfflineModeError, BaseRepository
  settings.py          # SettingsRepository, CountryRepository, GovernorateRepository
  departments.py       # DepartmentRepository, StudySystemRepository
  personnel.py         # PersonnelRepository, ALL_SYSTEM_PERMISSIONS, ALL_PERMISSION_KEYS, PermissionRepository,
                       #   DEFAULT_SYSTEM_ROLES, _RESULT_STATUS_CODES, RoleRepository
  courses.py           # CourseRepository
  students.py          # StudentRepository, AcademicPeriodRepository, EnrollmentRepository
  certificates.py      # CertificateRepository, IssuedCertificateRepository
  graduation.py        # GraduationOrderRepository, ThesisRepository, StudentSupervisorRepository, SupervisorRepository
  audit.py             # AuditRepository, DashboardRepository
  study_routines.py    # StudyRoutineRepository
  auth.py              # contents of repositories/auth_repository.py (the root package `repositories/` → old/)
```

### Task 4.1: Package skeleton
- [ ] `git mv data/repositories.py data/repositories/_legacy.py`. Write `__init__.py` with `from ._legacy import *`
  plus explicit imports of every underscore name in the snapshot. Move the header and base block into `base.py`;
  `_legacy.py` imports from `.base`.
- [ ] Read `sync_engine.py` around `import data.repositories as _repos`, and confirm every attribute it uses is exported.
- [ ] `py -3 -m pytest` (public names + import smoke), S1, S2, S4. Commit `refactor(data): repositories becomes a package (base extracted)`.

### Task 4.2: Move the repositories out of `_legacy.py`, one module at a time
- [ ] For each module in the table, in order: move the classes (Write/Edit), re-export them in `__init__`, and run `py -3 -m pytest`.
  When `_legacy.py` is empty, move it to `old/`. The old file's last line,
  `from repositories.auth_repository import AuthRepository`, becomes `from .auth import AuthRepository` in `__init__.py`.
  Then move the root `repositories/` to `old/`.
- [ ] S1–S7. Commit after every 2–3 modules.

---

## Phase 5 — Split the two biggest screens — Sonnet/Opus

### Task 5.1: `certificate_screen.py` → pure helpers + Office automation + screen
- [ ] Before moving anything: generate four certificates (year/semester × Ar/En) for one student. Dump each one's
  paragraph and table text with python-docx into `tests/.golden/cert_<n>.txt` (ignored).
- [ ] Add characterization tests for `to_arabic_num`, `format_date_rtl`, `format_academic_year_ltr` and `parse_stage_num`.
  The expected values are what the current functions return, checked by eye; at least `None`, `""`, an int and a typical string per function.
- [ ] Move `parse_stage_num`, `safe_int_val`, `consolidate_courses_for_certificate`, `consolidate_course_history`, `to_arabic_num`,
  `format_date_rtl`, `format_academic_year_ltr`, `get_subj_display` and `build_certificate_context` to `services/certificate_context.py`.
  Move `generate_pdf_from_docx`, `convert_docx_to_html`, `get_installed_printers`, `get_default_printer` and `print_file_to_printer` to
  `services/office_automation.py`. `certificate_screen.py` re-imports all of them (public-names snapshot).

  `tests/test_office_fallbacks.py` monkeypatches `win32com.client.Dispatch` / `win32print.*`, which still works after the move
  (module attributes). The `_cert_dir` static-files registration (it uses `app_paths`) stays in `certificate_screen.py`.
- [ ] Regenerate the four certificates and compare the text dumps (identical, except dates printed as "today").
  Run `py -3 -m pytest`. Commit `refactor(ui): certificate helpers and Office automation move to services/`.

### Task 5.2: `settings_screen.py` → package of section mixins
- [ ] Create `nicegui_screens/settings/` with one mixin per section:

  | Module | Section |
  |---|---|
  | `institution.py` | institution info, logos |
  | `study_systems.py` | study systems |
  | `appearance.py` | appearance |
  | `printers.py` | printers (uses `app_paths`) |
  | `roles.py` | roles and permissions (≈800 lines) |
  | `logs_analytics.py` | logs and analytics (uses `app_paths`) |
  | `server.py` | server config, sync queue |
  | `maintenance.py` | backup, restore, diagnostics |
  | `templates.py` | templates (uses `app_paths`) |
  | `screen.py` | `SettingsScreen(…mixins)`: `__init__`, `_load_data`, `_build_ui`, `_section_about`, `_get_event_value` |

  `nicegui_screens/settings_screen.py` becomes a shim that re-exports `SettingsScreen` and every name in the snapshot
  (`_SYNC_KIND_LABELS`, `_friendly_sync_reason`, `_summarize_sync_payload`, …).
- [ ] Move one mixin at a time and run `py -3 -m pytest` after each. Then S5, plus: edit a role, save printer settings, back up to a temp folder.
  Commit after every 3 mixins.

> Not split in this plan: `sync_engine.py` (≈1,900 lines) and `nicegui_ui/student_components.py` (≈1,560 lines).
> Revisit later, with characterization tests for the offline queue first.

After Phase 5, run the Phase 8 runbook (Haiku): docs, final release, rollout checklist.
