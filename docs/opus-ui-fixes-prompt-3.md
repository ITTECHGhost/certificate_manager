# Prompt for Opus: fixes after the user tested the redesign

Copy everything below the line into a new Opus session.

---

Act as a senior product designer and front-end engineer. The user tested the redesign of the Certificate Manager app (Python, NiceGUI, pywebview, Arabic RTL) and listed what is wrong or missing. Fix all of it in one run.

**Where to work:** `F:\CR_PY\certificate_manager\.claude\worktrees\certificate-design-fixes-dce558`, branch `claude/certificate-design-fixes-dce558`. The redesign commits are `219891c..4c556ff`. Run `git log --oneline 571f6aa..HEAD` and read `docs/opus-ui-redesign-prompt.md` first.

## Hard rules (unchanged)

1. **Do not touch the Word templates.** That means `templets/`, any `.docx` file, and the template context code in `services/certificate_context.py`. Certificates must print exactly as before. You may *read* the template config to filter and name templates.
2. **Never write to MySQL. Don't change the database schema.** Never delete files: move obsolete ones to `old/`. If a request needs a new stored field, check first whether a column or config key already holds it. If none does, compute the value in the UI. If it really must be stored, don't change anything: list it in the report instead.
3. **Start the API only with `start_server.bat`.** Never leave a hidden server on port 2030.
4. **Git:**
   - One commit per item group below. End each message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
   - Stage files by name with `git add <files>`.
   - Never stage these:
     - `data/roles_config.json` or `data/user_roles.json`.
     - The 7 files that differ only in line endings: `main.py`, `nicegui_screens/__init__.py`, `nicegui_screens/settings/__init__.py`, `nicegui_screens/settings_screen.py`, `nicegui_ui/__init__.py`, `nicegui_ui/state.py`, `nicegui_ui/upload_utils.py`. Stage one of them only if you made a real edit to it.
   - **Never push.** No force, `reset --hard`, `checkout --`, `clean` or `--no-verify`.
   - On any git problem, stop and report with the `git status` output.
5. **Tests:** `py -3 -m pytest` must pass before each commit. The only failures allowed are the 2 known ones in `tests/test_server_config.py` (missing `db_config.json`). Add tests for every helper you add: date parsing, academic-year formatting, template filtering and the graduation-count source.
6. **Checking in the app:**
   - Run `py -3 main.py --web` and open http://localhost:2323. The test admin account is username `1`, password `1`; use it for this run only and never store it.
   - Look and navigate only. Don't save, issue or delete real records.
   - Check each group at 800×600 and 1366×768, in dark and light themes, and in every accent theme.
   - Stop the app at the end.
7. **Parity:** the redesign must keep every capability the old design had. Before you start, compare the screens at `571f6aa` with HEAD (`git show 571f6aa:<file>`). List every control, option or setting that disappeared, and bring each one back unless the user asked to remove it.

## What to fix (one commit per group)

### 1. Accent themes
- The old design had at least 5 accent colours that the user chose as themes. The redesign reduced them to one green. Restore them all, using the names and colours from `571f6aa`.
- Each accent becomes a set of tokens in `nicegui_ui/theme.css` (accent, accent hover, accent soft background, focus ring). Every screen uses only the tokens, so switching the theme recolours the whole app.
- The theme picker is back in Settings → المظهر والسمات, with a colour swatch for each choice.
- Check contrast (4.5:1 for text) for every accent in both light and dark.

### 2. Controls
- **Switch (toggle):** the thumb sits slightly too high on the track (see the RTL switch in المظهر). Centre the thumb vertically in both states, in both directions and themes, everywhere.
- **Date fields**, on every date input:
  - picking a date in the calendar closes the popup;
  - typed dates are accepted with `-`, `/`, `.` or spaces as separators, or as digits only (`20251013`, `13102025`), and in either order (year first or day first);
  - the field normalises the value to the one app format, YYYY-MM-DD, when it loses focus or on Enter. An invalid date shows a clear Arabic error.
  - Put the parsing in one shared helper with tests.
- **Academic-year fields** (سنة القبول, سنة التخرج, التدريب الصيفي): accept `2025`, `2025-2026`, `2025/2026`, `2025 2026` or `25/26`, and always show and save the value as `2025/2026`. A single year `Y` becomes `Y/Y+1`. Use one shared helper with tests. Check how these fields are saved today and keep that column; only the formatting of the value changes.

### 3. Interface language
- The redesign removed all English. Add an interface-language option in Settings: العربية or English. The default is Arabic.
- With English chosen, labels, buttons, menus and toasts switch to English and the layout becomes LTR. Use the old English strings from `571f6aa` as the source.
- Use one string table (for example `nicegui_ui/i18n.py` with `t(key)`) rather than duplicating screens. Never show the two languages side by side again.

### 4. Settings: college, departments, personnel
- **College and departments in one view:**
  - Remove the separate الأقسام tab. Departments become a section inside معلومات الجامعة / الكلية.
  - The college information (Arabic and English name, logos) is entered once at the top.
  - Below it is the department list. Add departments one at a time with only two fields: the Arabic name and the English name. Each department belongs to that college automatically, so don't ask for the college per department.
  - The list is newest first and supports edit and delete with confirmation.
- **Personnel moves into Settings:**
  - Remove الكوادر from the sidebar and add it as a Settings tab. Keep the same permission check.
  - In the list, the column that now shows الصلاحية shows the **position** (المنصب) instead.
  - The role (الصلاحية) appears as a small second line under the person's name, together with the username.

### 5. Study system
- The old design had two separate choices: the study system (سنوي or فصلي) and the study type (صباحي or مسائي). The redesign merged them into one list, for example "نظام فصلي [الدراسة الصباحية]".
- Bring back two separate selects wherever the old design had them: the student form, graduation orders, the filters and the issue wizard.

### 6. Graduation orders and the student form
- Rename "عدد الطلاب (حسب الوثيقة)" to **"عدد الطلاب في أمر التخرج"**.
- When a student is linked to a graduation order:
  - تاريخ التخرج defaults to the order's date. The user can change it, but the order's date is the default.
  - Add a **سنة التخرج** field. By default it is derived from the graduation date in the `Y/Y+1` form. First check where this is stored today; if nothing stores it, derive it and show it read-only (rule 2).

### 7. Issue flow (UI names and choices only; don't change the template context)
- **Rename** "إصدار وثيقة" to **"إصدار كتاب"** everywhere: the sidebar, page title, dashboard tile and buttons.
- **Templates match the student:**
  - The template list shows only the templates for the student's study system: annual students see annual templates, semester students see semester templates, and the same applies to any other type.
  - Read this from the existing template config or metadata. Don't rename or edit the template files.
- **Template names:**
  - The نوع الوثيقة field shows only the template's name as the admin entered it, for example "تأييد" or "وثيقة بالدرجات".
  - Under the name, as a small second line, show the variant: عربي or إنكليزي, and بالدرجات or بدون درجات (or the other type).
  - In the dropdown, each option uses the same two lines.
  - Drop the "عربية • سنوي • جدولان متجاوران" style of label.
- **عدد الخريجين** has exactly three sources:
  1. from the graduation order;
  2. from the student's information;
  3. entered manually.

  Remove any other options.
- **Transcript display:**
  - Group the courses by year (annual students) or by semester (semester students).
  - Each group has a header such as "المرحلة 1 • 2020-2021" or "الفصل الأول • 2020-2021", plus a clearly different background or a coloured side marker using the accent tones, so the groups are easy to tell apart.
  - Show a per-group course count, and keep the total in the section title.

## Final report
- One line per group: commit sha and what changed, or why it was skipped.
- The parity list: what was missing compared with `571f6aa` and what you brought back.
- Any request you could not do without a schema change (rule 2).
- What you checked in the app.
- Any git problems, and the final pytest result.
