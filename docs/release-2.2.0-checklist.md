# Release 2.2.0 — checklist for installing on the server laptop

Branch: `claude/certificate-design-fixes-dce558` (40 commits on top of
`refactor/install-ready`). Full procedure: `docs/installation_guide.md`.

## Tonight — after the user's test passes
1. Merge the branch into `refactor/install-ready` (user approves first).
2. Raise `APP_VERSION` in `app_version.py` from 2.1.0 to **2.2.0**
   (clients compare it to decide whether to update; 2.1.0 also contained an
   uncommitted roles_config edit, so a fresh build is needed anyway).
3. `py -3 -m pytest` — only the 2 `tests/test_server_config.py` failures allowed.
4. Clean working tree (the build refuses otherwise). Leave
   `data/roles_config.json` / `data/user_roles.json` uncommitted? Decide: they are
   the user's live role edits — commit them only if they should ship.
5. Client: `scripts\build_release.bat` → `dist\release\2.2.0\`
   (Setup exe, `patch_v2.2.0.zip`, `SHA256SUMS.txt`).
6. Server: `powershell -ExecutionPolicy Bypass -File scripts\build_server_bundle.ps1`
   → `CertificateManagerServer-2.2.0.zip`.
7. Copy both to a USB stick with `docs/installation_guide.md`.

## Moving this database to the new server laptop

Rule: finish all data work **on this laptop**, check it in the app, then move
**one complete dump**. Never run the legacy import files on the new laptop.

### A. On this laptop (tonight)
1. **Legacy import — only if not done yet.** Check in phpMyAdmin: if the
   databases `legacy_a`, `legacy_b`, `legacy_merge` don't exist and the old
   students are in the app, it's done → skip to step 2. Otherwise, in order:
   - back up: `mysqldump -u root -p --routines --triggers certificate_manager > "old/sql_dumps/backup_before_legacy_import_2026_11_04.sql"`
   - load the two old dumps into `legacy_a` / `legacy_b` (commands at the top of
     `sql/fixes/2026-11-04_legacy_import_01_stage.sql`)
   - run `..._01_stage.sql`, **read its result lists** (matches, conflicts)
   - run `..._02_import.sql`, then `..._03_fix_and_cleanup.sql`
     (03 lists anyone left with gender 0 — fix those by hand; it also drops the
     three legacy databases)
   - open the app and check a few imported students and their marks.
2. **Close every copy of the program** (and stop issuing) so nothing changes
   during the export. Check the program has no unsent offline items
   (Settings → السيرفر والصيانة والسجلات → the failed/queued list).
3. **Export the whole database** (data + stored procedures + triggers), in a
   Command Prompt:
   ```
   cd C:\AppServ\MySQL\bin
   mysqldump -u root -p --routines --triggers --events --single-transaction --default-character-set=utf8 --databases certificate_manager > D:\certificate_manager_2026-11-05.sql
   ```
   `--databases` puts `CREATE DATABASE`/`USE` in the file, so it restores under
   the same name.
4. Check the file: it should be several MB, start with `-- MySQL dump`, and
   contain `CREATE PROCEDURE` (open it in Notepad++ and search). Copy it to the
   USB stick with the release folder.
5. Also copy `C:\AppServ\www\certificate_manager_api\templets\templates_config.json`
   (the bundle has the same file, this is a spare).

### B. On the new server laptop (tomorrow)
Follow `docs/installation_guide.md` §2 "First installation", with this change
at **step 2** (database):
1. Install AppServ (MySQL 8), keep `bind-address = 127.0.0.1`.
2. Restore the dump instead of creating an empty database:
   ```
   cd C:\AppServ\MySQL\bin
   mysql -u root -p --default-character-set=utf8 < D:\certificate_manager_2026-11-05.sql
   ```
   (Large file: use this command line, not phpMyAdmin's upload, which has a size limit.)
3. Check in phpMyAdmin: database `certificate_manager` exists; tables have rows
   (students, enrollments, issued_certificates); **Routines** tab lists the
   stored procedures (e.g. `GetFullCertificateData`).
4. Step 3 of the guide (`sql\fixes\*.sql`): run **only**
   `2026-10-27_04_api_db_account.sql` (it creates the `certman_api` account —
   accounts are not inside the dump). The other fixes are already in this
   database. **Do not run the `legacy_import` files.**
5. Continue with steps 4–6 of the guide (Python, `setup_server.bat` with the
   `certman_api` login, HTTPS/program key).
6. Clients: point them to the new server's IP (installer asks; installed
   laptops: Settings → السيرفر). On first start each client downloads a fresh
   copy into its local cache.

### If something goes wrong
The old laptop still has the original database untouched — nothing above
deletes it. Fix and export again.

## Tomorrow — server laptop
- Database: **no schema change in this release**. The study-system names, the
  موازي shifts and the template names were already written through the API on
  the current server; if the server laptop uses a different database, redo them
  from Settings (or restore a backup of this one).
- Server code changes are small (personnel + study routines routers). Update
  with the new bundle's `setup_server.bat` (keeps db_config, keys, certs, logs).
- `templets\`: the bundle only adds missing templates. Make sure the server's
  `templets\templates_config.json` holds the corrected names (8 تأييد / وثيقة
  بالدرجات names); clients fetch it at start-up.
- Clients: install `CertificateManager-Setup-2.2.0.exe`, or let installed
  laptops update from the patch.

## Smoke test after install (each laptop)
- Log in; dashboard shows «إصدار كتاب».
- Settings → المظهر: accent colours, language switch.
- Settings → معلومات الجامعة: departments; study systems show النظام الفصلي and
  نظام المقررات with صباحي / مسائي / موازي.
- Settings → قوالب الوثائق: 8 templates with your names and tags.
- Students: open one; النظام / نوع الدراسة show correctly; graduation order sets the date.
- «إصدار كتاب»: pick a student → only that system's templates, two lines each;
  step 3 shows the grouped transcript. Issue one test letter and check the Word/PDF.

## Known, not in this release
See the later list (offline issuing, semester column, exe speed) and
`docs/plan-later-averages-and-curriculum-versions.md`.
