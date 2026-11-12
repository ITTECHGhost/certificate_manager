You are on my DEV laptop (Windows). Project: F:\CR_PY\certificate_manager
(GitHub ITTECHGhost/certificate_manager). Work step by step and report before anything
I have to approve.

Goal: release client 2.5.1 so the laptops get the fixes that are on main but not in 2.5.0.

Context (from a session on the server laptop, 2026-11-12):
- Installed client everywhere is 2.5.0 (built from release commit 607237c).
- Branch claude/jolly-pascal-kra5ju = origin/main (d4257b0) + one commit e888836:
  sql/SP.sql fixes UpdateUserPreferences/Get_User_Settings (save/read settings by EMP_ID),
  and installer/update/finish_update.bat health check uses curl.exe -k.
  The server's MySQL already has these procedures; it already runs them.
- Client fixes already on main but not in 2.5.0:
  68f3ce3: "فحص الاتصال بالسيرفر" tested with http:// even on an https server.
  cb7e1b3: rows that fail to sync are marked 'failed' so "View failed records" shows them.

Tasks, in order:
1. git fetch; check the working tree is clean. Fast-forward main to
   origin/claude/jolly-pascal-kra5ju (it must be a fast-forward). Show me the log, wait for
   my OK before pushing main.
2. Run the tests (tests/, including tests/test_sync_queue_failures.py). Report results.
3. Find how releases are made in this repo (look at the "release: 2.5.0" commit 607237c,
   app_version.py, the build/installer scripts and docs/). Bump to 2.5.1 the same way, with
   a short changelog (Arabic and English) for the fixes above.
4. Build the client and the client patch exactly as for 2.5.0 (patch_v2.5.1.zip). Check
   the patch contains the fixes: nicegui_screens/settings/server.py uses preview_api_url,
   sync_engine.py has _mark_failed.
5. Tell me where patch_v2.5.1.zip is. I will copy it to the server and drag it onto
   C:\AppServ\www\certificate_manager_api\publish_client_update.bat.

Rules: do not push or tag without my OK. Never print secrets (db_config.json password,
app key).
