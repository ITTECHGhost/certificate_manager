# Separate study system (فصلي / مقررات) from study type (صباحي / مسائي)

Status: PLAN ONLY — nothing changed in MySQL, local_cache.db, the service or the repo.
Base: origin/main 8b884b6 (after 2.5.3). Live server MySQL 5.7.15 read read-only on 2026-11-15.


## Done on 2026-11-15 (server laptop)
- Plan written; user answered the questions (section 8). Implementation postponed — nothing changed in MySQL,
  local_cache.db, the service or the code.
- Templates: the 8 English templates (year/semester × with/without marks × male/female) were uploaded to the
  server with the same tags as the user's Arabic ones. Server now has 17 templates; snapshot in
  `docs/template_snapshot_2026-11-15/`. Config backups before the upload:
  `Documents\CertificateManager	emplate_backups\config before English upload 20261115-140000` (server laptop).
- Next session: start from section 8 (items 1–8), on a new branch from origin/main.

## 1. What exists today

### Live MySQL (server laptop)
| table | column | data |
|---|---|---|
| study_systems | id 1–6, `study_day_type` enum(Morning,Evening,Other) | 1/3/5 = النظام الفصلي (annual, year) ×Morning/Evening/Other; 2/4/6 = نظام المقررات (semester, semester) ×M/E/O. All active, same weights 10:20:30:40 |
| students | `study_system_id` (FK students_ibfk_4) | 1 → 1693, 2 → 120. **No study_type column** |
| graduation_orders | `study_system_id` (no FK), `study_type` varchar(50) | (1,evening) 1, (1,morning) 26, (2,morning) 20, (3,evening) 6, (4,evening) 16 → 46 morning / 23 evening |
| study_routines | `study_system_id` (FK fk_study_routines_system) | 2 rows, both id 1 |
| academic_periods | `study_system_id` (no FK) | 761 rows, all id 1 |
| trigger trg_students_bi/bu | reads `study_systems.calculation_weights` by id | unaffected (same weights) |
| trigger trg_study_systems_sync_delete | logs deleted ids to sync_deletions | laptops will drop deleted rows |
| schema_migrations | 0001–0005 applied | next = 0006 |

Students joined to their order (`students.order_id`):
- study type from the order: evening 418 (2 + 66 + 348 + 2), morning 1388, no order 7.
- **Data issue (separate question):** 1,270 students have a system that differs from their order's
  (system 1 students in system-2/4 orders: 1,162 — علوم الحاسوب 621, نظم المعلومات 541;
  system 2 students in system-1 orders: 108). Not touched by this plan.

### Today's certificates print the wrong study type for evening students
`GetFullCertificateData` / `sp_GetCertificate_StudentInfo` / `GetStudentDossierByID` and
`data/query.py` return `ss.study_day_type AS study_type`. Every student is on id 1 or 2 (Morning),
so `{{ study_type }}` (services/certificate_context.py:447) prints «الصباحية» for all 418 evening students.

### Code that uses these columns (origin/main)
- `sql/schema.sql`, `sql/SP.sql` (~25 procedures: Get/Insert/Update/Delete/ToggleStudySystem, GetActiveStudySystems,
  Insert/UpdateStudent, SearchStudentByName, Insert/UpdateGraduationOrder, LinkStudentsToOrder, GetAllGraduationOrders,
  GetFullCertificateData, sp_GetCertificate_*, GetIssuedCertificatesReport, GetStudentDossierByID, study routines).
- API `certificate_manager_api/`: routers/study_systems.py, students.py (payload + order matching 396–409, 503),
  graduation.py, bulk_import.py, reports.py (filter + group-by "study_system"), sync.py (offline queue push 562/725),
  system.py, db.py schema warnings.
- Client: `sync_engine.py` (replica DDL 393–603, SP arg lists 158–232; new MySQL columns are auto-added to SQLite at
  pull time, lines 1063–1068), `data/query.py` (offline SQL, 6 joins), `data/repositories/{students,graduation,
  certificates,study_routines,departments,base}.py`, `cert_repository.py:370-373`, `services/certificate_context.py`,
  `services/excel_import_service.py` (already reads a study-type column, then drops it).
- UI: `nicegui_ui/study_system_choice.py` (StudySystemPicker: 2 selects mapped back to one id — used in
  student form, bulk import, routines), settings/study_systems.py (grouped view), reports_screen.py (single select,
  shows 6 rows — the screenshot), issued_certificates_screen.py (study-type filter on `study_day_type`),
  graduation_orders_screen.py (own study_type select — fine), courses_screen.py, study_routines_dialog.py,
  student_components.py (detail card shows «نوع الدراسة» from study_type; hard-coded fallback list 1273–1276).
- Templates: `templets/templates_config.json` `system` tag (Annual/Semester) — chosen from
  calculation_rule/name, not the id; not affected.

## 2. Design
- **study_systems = 2 rows** (1 فصلي, 2 مقررات). `study_day_type` stays one release, ignored (all 'Morning'),
  dropped in a later migration once no 2.5.x client is left.
- **Study type lives on the record:** new `students.study_type ENUM('morning','evening') NOT NULL DEFAULT 'morning'`.
  `graduation_orders.study_type` already exists — values normalised to morning/evening.
  Routines and academic periods stay per system only (no type).
- **Legacy id map** table `study_system_aliases(old_id, study_system_id, study_type)`:
  3→(1,evening), 4→(2,evening), 5→(1,morning), 6→(2,morning). The API translates any incoming 3–6
  (old clients, queued offline writes) so nothing fails on the FK.
- One shared helper `normalize_study_type()` (client + API) and one label map {morning: صباحي, evening: مسائي}.

## 3. Migration `sql/migrations/0006_study_type_split.sql` (runs once, via migrate.py)
1. `CREATE TABLE _bak_0006_study_systems AS SELECT * FROM study_systems;` and
   `_bak_0006_orders (id, study_system_id, study_type)` — exact rollback data inside the DB.
2. Create + fill `study_system_aliases`.
3. `ALTER TABLE students ADD study_type ENUM('morning','evening') NOT NULL DEFAULT 'morning' AFTER study_system_id`.
4. Fill students.study_type: from the order's study_type when linked; else evening if old id in (3,4); else morning.
   Expected: 418 evening / 1395 morning.
5. graduation_orders: normalise study_type; evening where old id in (3,4); move 3→1, 4→2, 5→1, 6→2 (22 orders).
   Checked: no unique-key collision on (order_number, department_id, study_system_id, graduation_semester).
6. students / study_routines / academic_periods: same remap (0 rows today, done anyway).
7. `DELETE FROM study_systems WHERE id IN (3,4,5,6)` (trigger tells laptops), set rows 1–2 study_day_type='Morning'.
8. Verification SELECTs at the end (counts must match step 4/5).
Note: `students.updated_at` changes for all rows → next sync re-downloads students once (normal).

## 4. Code changes
- SP.sql: Insert/UpdateStudent get `p_study_type` (last arg; Update keeps old value on NULL); certificate,
  dossier, search, issued-certificates SPs return `s.study_type`; LinkStudentsToOrder unchanged unless you say
  it should also match study type; study-system SPs stop using study_day_type.
- API: students/bulk_import/sync payloads accept optional `study_type`; alias translation helper;
  reports get `study_type` filter + group-by option; study-systems payload no longer needs study_day_type.
- Client: StudySystemPicker becomes two independent values (system id + study type); student form, bulk import
  (Excel's study-type column is finally saved per student), reports (new «نوع الدراسة» filter + group-by),
  issued certificates filter (reads student study_type), settings study-systems (plain list of 2 systems),
  sync_engine DDL for fresh installs, data/query.py offline SQL, cert_repository.
- Tests: helper, migration-mapping logic, report where-builder, picker values, offline query; run full pytest.

## 5. Release, compatibility, offline laptops
- Order: **server first** (migration 0006 + SP.sql + API via the normal server update; migrate.py stops and the
  updater restores on error), then client 2.5.4 (or next number).
- 2.5.2/2.5.3 clients against the new server keep working: they see each system once, a type select with only
  صباحي, and their saves don't overwrite study_type (NULL → keep). Ids 3–6 from them are translated.
- Offline laptops with old replicas: next pull adds `students.study_type` automatically, deletes rows 3–6
  (sync_deletions + daily full download). Queued writes go through the API → translated. local_cache.db is
  never edited by hand.
- Optional: raise `minimum_supported_version` after all laptops are on the new client.

## 6. Backup and rollback
- Before: `mysqldump --no-defaults --single-transaction --routines --triggers` (password via MYSQL_PWD) into
  `C:\AppServ\www\certificate_manager_api\backups\pre_0006_study_type_<date>.sql`; copy the API folder files
  that change; test restore of the dump into a scratch DB first.
- Rollback A (exact, keeps later data): `sql/fixes/rollback_0006_study_type.sql` — re-insert study_systems
  3–6 from `_bak_0006_study_systems`, restore orders from `_bak_0006_orders`, drop students.study_type and the
  aliases table, delete the 0006 row from schema_migrations; then reinstall the previous server build.
- Rollback B (full): restore the mysqldump (loses writes made after the update).

## 7. Questions for the user
1. OK to drop «موازي/Other» (only صباحي/مسائي)? Ids 5/6 have no data.
2. LinkStudentsToOrder: also require the student's study type to match the order's?
3. The 1,270 students whose system differs from their order's: leave for now (separate task)?
4. Approve: backup + migration 0006 on the server laptop MySQL, then code on branch
   `claude/study-system-type-split` from origin/main, pytest, commit (no push).

## 8. User decisions (2026-11-15) — work postponed to next day (estimated > 15 min)
1. KEEP «موازي/Other» as a study type: study_type ENUM('morning','evening','parallel'); ids 5/6 → (1,parallel)/(2,parallel) in the alias map.
2. LinkStudentsToOrder: match the student's study type to the order's by default, but the user can still choose
   other students (pre-filter/suggest, never block).
3. The 1,270 system mismatches: separate task later.
4. Approved: backup → migration 0006 → code on a new branch from origin/main → pytest → commit. No push without OK.
New requests (same work package):
5. Search filters on the Students page and the Graduation Orders page.
6. Inputs keep old values after search / upload / export of a document; the user must clear them by hand.
   Proposed: reset the form after a successful upload/export; a clear (×) on each field + «مسح الكل» for search.
   Confirm with the user which screens exactly.
7. (2026-11-15) Settings → قوالب الوثائق: give each tag chip its own colour so the differences stand out —
   one colour per tag kind (system, language, marks, gender), and different shades per value
   (e.g. فصلي vs مقررات, عربي vs إنكليزي, بالدرجات vs بدون درجات, ذكور vs إناث). Same colours on the
   issue screen («إصدار كتاب») template labels. Must stay readable in dark mode.
8. (2026-11-15) BUG: a user account cannot be deactivated (إلغاء تنشيط المستخدم لا يعمل). Investigate in
   Settings → الكوادر / الأدوار والصلاحيات: UI switch, API route, stored procedure, and whether sync
   or a later save puts is_active back to 1. Reproduce first, then fix with a test.
