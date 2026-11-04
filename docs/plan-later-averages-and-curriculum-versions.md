# Later plan — averages, curriculum versions, data check (after the pilot)

Status: planned, not started. Averages are entered by hand today; nothing below
changes how the program behaves until it is built and approved.

Principle: **calculate from the student's own records, never from today's course
plan.** All reading stays in MySQL stored procedures (the program calls them via
the API, as now). Every SQL change ships as a `sql/fixes/*.sql` file that the
user reviews and runs; the program never alters the schema itself.

---

## Phase 1 — Data check report (read-only, first)

The old program inserted some data wrongly, so no automatic average can be
trusted until the data is clean.

- New SP `sp_CheckStudentAcademicData(student_id NULL = all)` returning one row
  per problem: student, stage/level, academic year, course, problem code, detail.
- Problem codes (first set):
  - `YEAR_STAGE_MISMATCH` — a stage studied in a year that doesn't follow the
    previous stage (e.g. stage 2 earlier than stage 1)
  - `COURSE_TWICE` — same course in two stages/levels (not a second-round retake)
  - `NO_UNITS` — a course with 0/NULL units
  - `EMPTY_PERIOD` — a stage/semester with no courses
  - `MARK_RANGE` — mark outside 0–100
  - `SEM_COLUMN` — semester-1 course stored as semester 2 (later-list item 8)
- Screen: Settings → «فحص البيانات»: filter by department/year, export to Excel,
  click a row to open the student. The user fixes the data; the report is re-run.

## Phase 2 — Versioned «سيرة دراسية» (curriculum versions)

- When a department changes its courses, the old سيرة is kept and a new one is
  made (no editing of a سيرة already applied to students).
- `sql/fixes`: add `admission_year_from`, `admission_year_to` (nullable) to
  `study_routines`; update `InsertStudyRoutine`/`UpdateStudyRoutine`/
  `GetAllStudyRoutines`.
- Student form: «تطبيق سيرة دراسية» offers the سيرة matching department +
  system + shift + admission year first.
- Applying a سيرة already copies its courses onto the student, so later edits to
  the سيرة never touch enrolled students — keep it that way (test).
- Per-student exception: a note field on the student's own enrollment row
  (course moved to another stage / equivalence) with who and why.

## Phase 3 — Automatic averages in stored procedures

One SP per rule, both reading only the student's own enrollments:

- **النظام الفصلي (rule = annual, by year/stage)** — `sp_CalcAverage_Annual`
  1. stage average = Σ(mark × units) / Σ(units) over that stage's courses, in the
     academic year the student actually took them (second-round marks per the
     college's rule, to confirm with the user);
  2. final = Σ(stage average × stage weight) using the system's weights
     (10:20:30:40 today; moved to «خيارات متقدمة»).
- **نظام المقررات (rule = semester, by level)** — `sp_CalcAverage_Credits`
  final = Σ(mark × units) / Σ(units) over all passed courses; year changes do not
  matter.
- **مسار بولونيا** — `sp_CalcAverage_Bologna` (ECTS, credit-weighted); rules
  confirmed with the user before next year's graduates; needs the shifts table /
  `credits` rule migration from plan C.
- Program: «احسب المعدل» button on the student → shows calculated vs stored
  average and the per-stage breakdown; the user accepts before it is saved.
  Manual entry remains possible.
- Tests: hand-worked transcripts from the user (one per system) as fixtures; the
  SP result must match to 2 decimals.

## Phase 4 — Certificate placement

- `sp_GetCertificate_AcademicCourses` groups by the student's own stage/year
  (الفصلي) or level (المقررات), so the Word certificate puts each course where
  the student actually took it. Golden-file tests for both template families.

## Order
1 → 2 → 3 → 4. Phase 1 can start right after the pilot; phase 3 waits for the
user's hand-worked examples.

---

## Also later — two-stage certificate numbers (reported 2026-11-05)

Letters signed by the university president are printed first with a **secret
(temporary) number**, sent for signature, and get the **public issued number**
only when they come back. Letters issued by the college itself get the public
number at once.

- `sql/fixes`: on `issued_certificates` add `number_stage` (`secret`/`public`),
  `secret_number`, `public_number_date`; a separate numbering sequence for
  secret numbers; extend the unique key (see the later list, item 1).
- «إصدار كتاب»: a switch «يُرسل لرئاسة الجامعة للتوقيع» → takes a secret number.
- «سجل الوثائق الصادرة»: filter «بانتظار الرقم العام» and an action
  «تثبيت الرقم العام» that assigns the next public number and re-prints/updates
  the Word file.
- Goes together with the offline-issuing fixes (numbers must not be computed
  from the stale local cache).
