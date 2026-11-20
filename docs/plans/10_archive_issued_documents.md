# 10 — Archive from «سجل الوثائق الصادرة» (TODO C14 + bullets lines 81, 83)
- Goal: every issued + signed/stamped document stored by hash, searchable by its unit; only unit admin edits/replaces/deletes (soft); replace = new row with `supersedes_id`.
- Files: `certificate_manager_api/routers/issued_certificates.py`, new `services/archive_store.py` (hash-named files in a virtual folder), `nicegui_screens/issued_certificates.py`, nightly backup script.
- DB / migration: `0010_document_archive.sql` + `sql/fixes/rollback_0010_document_archive.sql` (archive_files: hash, unit_id, year, supersedes_id, deleted_at). Needs 0008 units first.
- Tests first: `tests/test_archive_store.py` (same file → same hash, replace keeps old row, non-admin 403, soft delete only).
- Risks: depends on plans 06+07; disk growth; monthly restore test must actually happen.
- Model: Opus (design), Sonnet (UI).
- Question: Storage location for the archive folder on the server (which drive)?
