# Plan — study systems (now), template tags, Bologna (later)

Scope agreed with the user: do the minor changes now, pilot, then upgrade.
No MySQL schema change in parts A and B. Part C needs one and waits for approval.

Hard rules (same as before): don't edit `.docx` files or the template context in
`services/certificate_context.py`; never write to MySQL from scripts; move, don't delete;
one commit per part, files staged by name; `py -3 -m pytest` passes (only the 2
`tests/test_server_config.py` failures allowed); check in the app at 800×600 and 1366×768.

---

## A. Study systems — work with what we have (no schema change)

The table already holds one row per (system × shift): `calculation_rule`
(annual/semester), `period_display` (year/semester), `study_day_type`
(Morning/Evening/Other), weights, active.

A1. **Settings → أنظمة الدراسة, grouped view.** One block per system (grouped by
    `calculation_rule` + `period_display` + weights), its shifts shown as chips
    (صباحي / مسائي / أخرى) each with its own active switch. Show the shift column
    that is hidden today, so the 4 rows stop looking like duplicates.
A2. **Add/edit dialog** gets every field the row has: Arabic/English name,
    calculation rule, period display, shift, weights, active. "Add shift to this
    system" copies the system's rules into a new row with the chosen shift.
A3. **Name check.** Warn (don't block) when the name contradicts the rule — e.g.
    «نظام فصلي» saved with `annual`. Offer the suggested name. The user fixes the
    current ids 1/3 from this dialog (the app saves; no script writes MySQL).
A4. **Logic follows the rule, not the name.** Template filter, stage calculation,
    and transcript grouping read `calculation_rule`/`period_display` only (audit
    `student_system()` in `nicegui_ui/issue_helpers.py`, `calculate_stage`, routines).
A5. **«موازي» (parallel) for now:** the enum only allows Morning/Evening/Other.
    Use "Other" labelled «موازي» in the UI (a label map, one place), noted in the
    report as temporary until part C.
A6. Tests: grouping helper, name-vs-rule check, shift label map.

## B. Templates — the user's name plus editable tags

The user now names templates freely (e.g. «تأييد انجليزي مقررات») in
`templets/templates_config.json` (`display_name`). Tags live in the same entry:
`lang`, `system`, `sbs`. They are shown but cannot be edited after adding.

B1. **Edit dialog = full form.** The pencil opens one dialog with: name, language
    (عربي/إنكليزي), study system (annual / semester / master — and later bologna),
    marks (بالدرجات / بدون درجات), all prefilled. Saving calls
    `register_template(file, name, lang=…, system=…, sbs=…)` (it already accepts
    them). The `.docx` itself is not touched.
B2. **Add form:** same three tag inputs (already there) + the name is free text;
    the suggested name is only a placeholder, never overwrites what the user typed.
    Replace the checkbox «مقترن جنباً إلى جنب (SBS)» with a select
    «بالدرجات / بدون درجات» so it reads like the tags.
B3. **Card layout:** name on the first line, the tags as chips right beside it
    (system • language • marks), file name/size/date on a muted line under it.
    Fix the current card where the tags sit far from the name.
B4. **Issue screen («إصدار كتاب»):** line 1 = the user's `display_name`
    (fallback: the generated name), line 2 = the tags (عربي • بالدرجات). The
    template filter uses the `system` tag, not the file name.
B5. **Tag consistency check:** if a name contains a word that contradicts a tag
    (e.g. «انجليزي» with lang=Ar, «مقررات» with system=Annual), show a warning chip
    on the card — the screenshot has two such cases («…فصلي» tagged النظام السنوي).
B6. Tests: tag save round-trip on a temp config file, label line builder,
    contradiction check, filter by tag.

## C. Bologna — before next year's graduates (needs approval)

C1. Schema (one migration, approved first): `calculation_rule` gets `credits`;
    new `study_shifts` table (+ «موازي»); `shift_id` on students, orders,
    routines; copy script fills them from today's (system × shift) rows.
C2. Credit-weighted average and ECTS display in the calculation code, with tests
    against a hand-worked transcript the user provides.
C3. Template system tag `Bologna`; new Word templates come from the user.
C4. Settings UI from A1 becomes two real lists (systems, shifts).

---

## Order and commits
1. B (templates tags + issue labels) — most visible, no risk.
2. A (study systems grouped view, dialog, rule-based logic).
3. Report: what to check, the A5 workaround, the C items waiting for approval.
C is planned separately once the pilot is done and the Bologna rules are known.
