# Project Anatomy

- `main.py`: The NiceGUI application entry point. Native desktop mode on port 2323.
- `nicegui_screens/`: NiceGUI UI screens — `login_screen`, `dashboard_screen`, `students_screen`, `courses_screen`, `departments_screen`, `personnel_screen`, `graduation_orders_screen`, `certificate_screen`, `issued_certificates_screen`, `profile_screen`, `settings_screen`, `student_bulk_import_view`, `study_routines_screen`, `study_routines_dialog`.
- `nicegui_ui/`: NiceGUI UI components and tokens — `ui_components.py`, `ui_theme.py`, `state.py`, `student_components.py`, `template_constants.py`, `theme.css`.
- `db.py`: MySQL connection factory (`get_connection`), read-only schema check (`init_db`), grade helper, and backup/restore via `mysqldump`/`mysql` CLI. (Client use of this is an architecture violation being phased out — see Bug Ledger #226.)
- `sync_engine.py`: Offline sync engine. Local SQLite cache (`local_cache.db`), network status flag (`is_online`/`set_online`/`check_network_status`), outbound sync queue (temp negative IDs → API `/sync`), inbound replica pull, SP result cache, and SQLite helpers (`sqlite_read_all`/`sqlite_read_one`).
- `config.py`: Holds `DBConfig` (still used by `db.py`); the rest is dead CustomTkinter-era theme code.
- `api_config.py` / `server_config.json`: API URL (http/https), CA file and app key for the client. `server_config.example.json` is the git template (the real file holds the app key and is not committed).
- `api_client.py`: the ONLY way the client talks to FastAPI — per-thread keep-alive session, HTTPS verification with `certs/college_ca.crt`, `X-App-Key` header, safe retries.
- `certs/college_ca.crt`: public certificate of the college CA, shipped with the client (bundled by `client.spec`).
- `data/repositories.py`: Data Access Layer with online/offline routing (API via `requests`, SQLite fallback). `data/query.py`: offline SQLite query helpers. `data/roles_config.json`, `data/user_roles.json`: role persistence.
- `repositories/auth_repository.py`: thin wrapper over `PersonnelRepository`/`SettingsRepository`.
- `cert_repository.py`: certificate payload building.
- `services/`: `excel_import_service`, `template_sync`, `updater`. `utils/`: `logger`, `file_delivery`, `health_check`, `error_formatter`.
- `certificate_manager_api/`: FastAPI server (GitHub copy). Deployed copy runs from `C:\AppServ\www\certificate_manager_api\` on port 2030. Production runs it as the `FastAPICertificateManager` Windows service (`fastapi_service.py`, settings in `server_settings.json`, log `logs\api_service.log`). Server tools: `install_service.bat`, `switch_server_mode.bat https|http`, `update_server.bat <folder>`, `setup_server_https.bat` (+ `make_https_cert.bat`), `publish_client_update.bat`; console runs for testing: `start_server.bat` / `start_server_https.bat`. `app_keys.json` (program keys, audit/enforce), `.htaccess` (blocks Apache). Full guide: `certificate_manager_api/SERVER_SETUP_GUIDE.md`. Client patches: `scripts/build_client.bat` → `scripts/make_client_patch.bat`; `scripts/apply_patch.bat` keeps each laptop's `server_config.json` + `certs\`.
- `templets/`, `certificates/`: Word templates and generated certificates.
- `sql/fixes/`: numbered MySQL change files the user runs in order (`2026-10-24_01` result_status repair, `_02` accounts/roles, `_03` change tracking + certificate blocks).
- `utils/password_hashing.py` (+ identical `certificate_manager_api/password_hashing.py`): PBKDF2 password hashing. `nicegui_ui/upload_utils.py`: `read_upload()` for NiceGUI 2/3 upload events.
- `tools/`: empty package (the old `migrate_mysql.py` is in `old/tools/`). `export_db.py`, `get_db_schema.py`: DB inspection tools. `sql/`: exported schema/SP files.
- `old/`: **Everything legacy** — CustomTkinter UI (`temp_archive/old design/`), scratch scripts, backups, copies, old themes, stray DBs. Not imported by anything; safe to delete when confirmed.
- `logs/system_log.txt`, `logs/activity_log.txt`: runtime logs.

> **AGENT RULE:** When investigating system behavior, errors, or tracing recent actions (e.g., failed logins, API/SP failures, offline fallback triggers), ALWAYS search `logs/system_log.txt` and `logs/activity_log.txt` to gather context on what actually happened during runtime.

## Strict Rules & Execution Directives
1. **Do not make assumptions about database and MySQL is off-limits**: You are NOT to make any changes directly to the MySQL database. You can only ask the user to make the changes or provide SQL code for the user to execute.
2. **Database inspection protocol**: In case you need to inspect or check the MySQL database, run `export_db.py` then check `sql/schema.sql`, `sql/SP.sql`, and `sql/SQLite.sql`.
3. **FastAPI code checking order**: For checking FastAPI code, check `C:\AppServ\www\certificate_manager_api\main.py` first, then check `certificate_manager_api\main.py` (which is the copy of the main file saved for GitHub).
4. **Strict Instruction Following**: Follow user instructions strictly without making assumptions, breaking existing work, or performing unauthorized actions.
5. **Legacy files go to `old/`**, never deleted, never left in the project root.
