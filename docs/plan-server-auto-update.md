# Plan — updating the installed server automatically

Status, 2026-11-09: **Stage 1 is built** and is waiting for its first real run on the server. Stage 2 is still a proposal.

### What Stage 1 became (it differs from the proposal below)
- `setup_server.bat` stays the single update action; there is no separate `update_server.bat`. Its new step 7b runs while the service is stopped:
  1. A `mysqldump` backup into `backups\`, using the API's login through a temporary options file.
  2. `certificate_manager_api\migrate.py`: migrations from `sql\migrations\`, then all of `SP.sql`.
  3. It saves that `SP.sql` next to the code and writes `server_version.txt`.
- **Roll-back:** the old code and the previous `SP.sql` are restored, and the old service starts again. The database dump is **not** restored automatically, because a full restore would undo any work saved between the backup and the failure. The dump's path is shown on screen for a manual restore.
- Every procedure is created without a `DEFINER`. The `certman_api` account (ALL on the database) can create them, so root is never needed.
- `sql\migrations\` starts empty. The scripts in `sql\fixes\` stay history, because some of them hold passwords or one-off imports. `--baseline` exists for a server whose schema already has a migration applied by hand.
- Not built from the proposal: the build-time check that refuses an `SP.sql` change without a version bump, and a test against a throwaway database. Instead, `tests	est_migrate.py` checks that every procedure in `SP.sql` parses.

## Today

| Part | How it reaches the server now |
|---|---|
| FastAPI code | `scripts\build_server_bundle.ps1` → zip → USB → run `setup_server.bat` again (it backs up the code, stops the service, copies the code and restarts the service) |
| Stored procedures (`sql\SP.sql`) | by hand in phpMyAdmin |
| Schema/data fixes (`sql\fixes\*.sql`) | by hand, "run only the new ones", and nobody records which ones already ran |
| Templates | the bundle only adds templates that are missing; names, tags, uploads and deletes sync through the API |
| Client program | already automatic: OTA from `/api/update/version.json` |

The weak point is the database. Nothing records which scripts already ran on a server, so a step can be skipped or run twice. This is how `sp_GetCertificate_StudentInfo` (gender) could have shipped without reaching the server.

## Target

One action on the developer laptop, then the server updates itself, keeps a backup, and rolls back on failure.

## Stage 1 — one double-click update on the server (recommended first)

1. **Numbered migrations with a ledger.**
   - Each change becomes a numbered file, `sql\migrations\NNNN_short_name.sql`. The existing `sql\fixes` files are copied in as 0001..00NN, and every migration from now on goes there.
   - A table, `schema_migrations(id, filename, sha256, applied_at)`, records what ran.
   - A runner (`scripts\migrate.py`) applies only the missing files, in order, each inside a transaction where MySQL allows it. It stops at the first error.
   - If a file that already ran has changed (its hash differs), the runner refuses and asks for a new migration instead.
   - On an existing server, a first `--baseline` run marks the scripts that were already applied by hand as done.
2. **Procedures are re-applied on every update.**
   - `SP.sql` is all `DROP … IF EXISTS` + `CREATE`, so the runner applies the whole file after the migrations. A procedure can never be out of date.
   - The runner removes the `DEFINER=root@localhost` clauses before applying. Then it can run as the API's own MySQL account if that account is granted `CREATE ROUTINE, ALTER ROUTINE`. Otherwise it asks once for the root password and never stores it.
3. **`update_server.bat` inside the bundle.** It runs these steps in order, and each one logs to `logs\update-<date>.log`:
   1. Check the bundle's version is newer than the one installed (`server_version.txt`).
   2. Back up the database with `mysqldump --routines --triggers` into `backups\`.
   3. Back up the code, which `setup_server.ps1` already does.
   4. Stop the service, copy the code, and `pip install` from the bundled wheels.
   5. Run `migrate.py`: migrations first, then `SP.sql`.
   6. Start the service and check `/ping` plus one stored-procedure call.
   7. If any step fails, restore the code backup and the database dump, restart the old version, and show the error.
4. **Release check on the developer laptop.** `build_server_bundle.ps1` refuses to build if `SP.sql` changed but its migration-number or version file wasn't bumped. A test also confirms every procedure in `SP.sql` exists after a fresh run of the migrations on an empty test database.

Result: copy the zip to the server, double-click `update_server.bat`, and you're done. No phpMyAdmin steps.

## Stage 2 — no USB: the server pulls the update

1. **Publish from the developer laptop.** A new script, `scripts\publish_server_update.ps1`, builds the bundle and uploads it to the server through a new admin-only endpoint, `POST /api/admin/server-update`. The endpoint:
   - is protected by an admin key in `app_keys.json`, which is never in the bundle;
   - checks the zip's SHA-256 against a signed manifest;
   - stores the zip in `C:\AppServ\www\server_updates\incoming\`.
2. **A separate updater task on the server.** The API service can't replace itself while it is running, so a Windows Scheduled Task, `CertificateManagerServerUpdater`, runs as SYSTEM every 5 minutes (and at startup). When it finds a new verified zip, it runs the same `update_server.bat` steps from Stage 1, including the rollback. It then writes the result to `server_updates\status.json`.
3. **Visibility.**
   - Settings → سجلات shows "Server version 2.3.0 — updated 2026-11-10 21:04 ✓" or the failure reason, read from `status.json` through `/api/admin/server-update/status`.
   - The update waits for a quiet window, either a set hour or no requests for 10 minutes, so it never restarts the API while someone is issuing.
4. **Clients follow.** The publish script can also place the client OTA patch, so one publish updates the server first and then each client at its next start. `minimum_supported_version` then forces old clients to update.

## Order of work

1. Stage 1, steps 1–2: migrations, ledger and runner, with tests on a throwaway database. Baseline the server once.
2. Stage 1, steps 3–4: `update_server.bat` with backup and rollback, and the build check. Try it on the developer laptop's AppServ first.
3. Stage 2, after Stage 1 has done at least one real update.

## For this release (until Stage 1 exists)

On the server, in phpMyAdmin, run `sql\fixes\2026-11-09_certificate_student_gender.sql`. Then rerun `setup_server.bat` from the new bundle. That delivers the new `DELETE /api/templates/{name}` route and keeps the API in step with the clients.
