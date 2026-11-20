# Architecture rules (always apply; ≤40 lines)

Updated 2026-11-20. Replaces the "Architectural Rules" of the old cerebrum.md (its customtkinter, config.py-theme and SidePanel/RecordList rules were stale: the client is NiceGUI).

## Data and server
- ALL OR NOTHING: every client request that writes is ONE transaction. One commit at the end of the request (`deps.get_db` rolls back anything uncommitted). Multi-step saves go to the server as one request (`/sp/write-batch` or one endpoint), never several requests from the UI. No COMMIT inside stored procedures. File uploads: write a temp file, insert rows in the transaction, rename the file only after commit; any failure deletes the temp. Guarded by `tests/test_all_or_nothing.py`.
- The AI never writes to MySQL (no INSERT/UPDATE/DELETE/ALTER/DROP/CREATE, no procedure replacement). It writes migration + rollback files; the user runs them, dev DB first after mysqldump.
- All DB access goes through the FastAPI server. No client-side DB config or raw connections.
- New features: an explicit endpoint per action that checks the calling user and their unit on the server. Do not add new procedures to the generic `/sp/*` whitelist.
- New tables: utf8mb4, `created_at`/`created_by`, soft delete (`deleted_at`, `deleted_by`) for important records.
- mysql-connector: after `fetchone()` use a buffered cursor (or read the rest), or the next query on that connection fails with "Unread result found".

## Client
- NiceGUI screens in `nicegui_screens/`, shared widgets/tokens in `nicegui_ui/` (`ui_components.py`, `ui_theme.py`, `theme.css`). Arabic-first RTL; user-visible text in Arabic (`tests/test_arabic_only_ui.py`).
- Client data access only through `data/repositories/` and `api_client.py`; no raw SQL in UI files.
- Offline: all offline infrastructure is in `sync_engine.py` (SQLite replica + outbound queue, temp negative IDs resolved on sync). Writes that must not happen offline raise `OfflineModeError`. New modules (holds, requests, archive) are read-only offline.
- App start is fault tolerant: if the server is down the app starts offline from the replica.

## Process
- Code changes are made with the editor's edit tools so each change is a reviewable diff; no scratch scripts that rewrite project files.
- Word templates in `templets/` are edited by the user only.
- Backend deploy on the server: copy changed API files to the service folder and restart the service as Administrator (see `.ai/releases.md`).
- Never commit real student data, keys, `db_config.json`, `app_keys.json`, `server_config.json`.
