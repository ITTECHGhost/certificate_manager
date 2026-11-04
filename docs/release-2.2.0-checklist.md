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
