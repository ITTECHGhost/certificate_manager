# Overnight plan — item 13 (first half): in-app feedback page (2026-11-20)
1. Migration `sql/migrations/0009_feedback.sql` (+ `sql/fixes/rollback_0009_feedback.sql`): table `feedback` (utf8mb4, message, screen, app_version, created_at/created_by, soft delete). Number 0009 follows docs/PLAN_archive_and_next.md (0008 = identity, 0009 = feedback + student_holds). NOT run by the AI.
   Merge note: if the holds session also writes a `0009_*` file, one of them must become 0010 (migrate.py refuses two files with the same number).
2. API `certificate_manager_api/routers/feedback.py`: `POST /api/feedback` (one insert, one commit), `GET /api/feedback` (newest first, not deleted), `DELETE /api/feedback/{id}` (soft). Registered in `main.py`. Not `/sp/*`.
3. Client `data/repositories/feedback.py`: `send()` raises `OfflineModeError` offline; `list_all()` returns [] offline.
4. Screen `nicegui_screens/feedback_view.py`: dialog (Arabic only) with a text box; saves text + current screen + app version + user id. Opened from a button in the sidebar footer. List of received notes shown in the same dialog.
5. Tests first: `tests/test_feedback.py` (validation, rollback on error, one commit, offline error, repository payload). Existing all-or-nothing and Arabic-only tests must stay green.
Known gap: `/api/login` gives no token, so the server trusts `created_by` sent by the client (same as official_rankings) until the identity work (0008) lands.
