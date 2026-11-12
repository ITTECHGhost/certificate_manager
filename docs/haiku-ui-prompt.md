# Prompt for Haiku: UI/UX redesign of Certificate Manager

Copy everything below the line into the Haiku session.

---

You are working on the Certificate Manager desktop app. It is written in Python with NiceGUI and pywebview.
Work in the worktree `F:\CR_PY\certificate_manager\.claude\worktrees\certificate-design-fixes-dce558` on the branch `claude/certificate-design-fixes-dce558`.
The full design review is in `docs/design-review-2026-10-31.md`. Read it first; every item has an ID (G1, R1, …).

## Hard rules (never break these)

1. **Do not touch the Word templates.**
   - Nothing in `templets/` and no `.docx` files.
   - None of the template field or context code in `services/certificate_context.py`.
   - Skip every W item in the report.
2. Change only the Python UI and the CSS:
   - `nicegui_screens/`
   - `nicegui_screens/settings/`
   - `nicegui_ui/`, including `theme.css`
   - `assets/` (fonts only).

   Do not change how data is saved, the API, or the repositories.
3. Never write to MySQL. Never delete files: move anything obsolete to `old/`.
4. Do not commit `data/roles_config.json`. It changes at runtime.
5. Run the API only with `start_server.bat`. Never leave a hidden server on port 2030.
6. After each step below:
   - Run `py -3 -m pytest`. It must pass.
   - Make one separate commit for the step. End every commit message with `Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>`.
   - In the report, set the Status of each item you fixed to `fixed (<short sha>)`.
7. **Do not push.** Do all steps in ONE run without stopping to ask for approval between steps. Keep going until step 10 and the UX checklist are done.
8. Keep the existing code style: match the naming, the comment density and the `UI` helper components in `nicegui_ui/ui_components.py`. Reuse those helpers instead of adding new ad-hoc styling.
9. **Git problems: stop and report, never force.** If anything in git goes wrong (rebase/merge conflict, a failing commit hook, a changed file you did not touch, detached HEAD, a branch that moved), stop. Do not use `--force`, `reset --hard`, `checkout --`, `clean` or `--no-verify`. Tell the user exactly what happened and include the `git status` output. If pytest fails and you cannot fix it within a step, do not commit that step; report it and continue with the next independent step.

## Step 0: Prepare

- Already done: the docs are committed and the branch is rebased onto `refactor/install-ready` (`571f6aa`). Check with `git log --oneline -3`; if `571f6aa` is not in the history, stop and report.
- `data/roles_config.json` is modified by the running app. Leave it alone and never stage it: use `git add <files>`, never `git add -A` or `git add .`.
- Start the app in web mode with `py -3 main.py --web` on port 2323 so you can check each change in the browser. Ask the user to sign in; never type passwords yourself.

## Design direction (applies to every step)

The goal is a simple, calm, easy-to-read Arabic (RTL) admin app.

- **One language in the UI: Arabic.** Remove the small English sub-labels from labels, buttons, tabs, placeholders, notifications and tooltips. Page titles may keep a short English subtitle. This fixes G1 and G2, and most truncation disappears with it.
- **Labels never cut off with "…".** Use short labels, give fields the width they need, and let labels wrap if necessary.
- **Button hierarchy:**
  - One filled primary button per screen or dialog, in the app's green accent.
  - Secondary actions are outlined.
  - Back and cancel are flat or ghost buttons.
  - Delete and disable are icon-only flat buttons that turn red only on hover, or they go in a ⋮ menu. A list must never become a wall of red buttons.
- **One accent colour** (the existing green). There is no blue anywhere, including the login button. Icons are neutral or accent, never rainbow-coloured.
- **Typography:**
  - Bundle the Cairo font (woff2, regular, semibold and bold) in `assets/fonts/` and load it with `@font-face` in `theme.css`. Put it first in the font stack.
  - Use one font everywhere, with no monospace or letter-spaced chips.
  - Numbers use 2 decimals.
- **Spacing:** use a 4/8/16/24/32 px scale and the same top margin on every page. The title appears once per page (in the top bar); cards get section titles only.
- **Scrolling:** only the content area scrolls, so there is never a double scrollbar.
- **Lists:** rows are read-only, and editing happens in a side panel or dialog. Empty states and search boxes have an icon and placeholder text.
- **Feedback:** every save, delete or issue action shows a short Arabic notification. Destructive actions ask for confirmation.
- **Test at 800×600 and at 1366×768, in dark and light themes.**

## Steps (one commit each, all in one run)

1. **Global shell:** G1, G2, G3, G4, G5, G8, G9, G11.
   - Fonts.
   - One-language labels in the sidebar and header.
   - Flat sidebar: the active item has a filled background and an accent bar.
   - A clean header with a refresh icon and a user chip; the chip opens a menu with Profile and Logout.
   - A single scroll container.
2. **Buttons and destructive actions:** G6, G7. Build the shared button variants in `ui_components.py` and apply them on every screen.
3. **Move Departments into Settings.**
   - Remove "إدارة الأقسام" from the sidebar.
   - Add a "الأقسام" tab in Settings directly after the institution ("معلومات الجامعة") tab. It reuses `DepartmentsScreen` from `nicegui_screens/departments_screen.py`, embedded inside the tab panel, not as a full page.
   - Keep the same permission check: a user who could open Departments before can see this tab.
   - Delete the `departments` branch in `dashboard_screen.py` `_switch_screen` and the header map entry only if nothing else uses them. Otherwise point them to settings with that tab selected.
   - Fix P1 and P2 while you are there.
   - Add a test that the settings screen exposes the departments tab.
4. **Settings layout:** T1–T6.
   - A vertical tab list on the right side (RTL) instead of the scrolling top tab row.
   - Full-width or textarea for the long college names.
   - Logo upload shows a preview of the current logo and no "0.0B / 0.00%" until an upload is actually running.
   - Move "Enable RTL" into an advanced section.
   - Simpler role cards.
5. **Login and dashboard:** L1–L4, D1–D4.
   - Login: accent button, theme toggle in a corner with a tooltip, a plain brand background.
   - Dashboard stats in this order: Students, Issued certificates (add this count), Courses, Personnel.
   - Quick-action arrows point correctly for RTL.
   - The recent-students table is visible at 800×600.
6. **Students and orders:** S1, S3, S4, S5, O1, O2.
   - Opening a student keeps a clear "رجوع" button, and Add Student works from that view.
   - Personal details use a two-column label/value list.
   - Order cards show the number and date prominently.
   - Dates use one format, YYYY-MM-DD, matching the new date picker from commit `571f6aa`.
7. **Courses and personnel:** P3, P4, P5.
   - Course cards are read-only and editing happens in a dialog.
   - Use one standard paginator.
   - Show the signature chip only when a signature exists.
8. **Issue certificate:** C1–C8.
   - Normal search input height.
   - Show the template display name, not the file name. Read it from the existing config; do not edit the templates.
   - Clear on/off switch colours.
   - Flat transcript rows.
   - One primary "إصدار" button.
   - The printer dialog has no truncation.
9. **Issued certificates log:** R1, R2.
   - Fewer columns: number, student, document type, date, recipient.
   - The rest goes in a row-click detail.
   - Filters are wide enough to show their values.
10. **Profile and polish:** U1, U2, G10, G12.
    - Fix the tooltip placement.
    - Show a skeleton immediately on page switch, and profile slow page builds (log timings, then fix the slowest).

## UX checklist to run at the end

- Can a new admin issue a certificate in ≤ 4 clicks from the dashboard without reading English?
- Is there any "…" truncation left at 800×600? Search screenshots of every page.
- Does every screen have exactly one primary button?
- Do keyboard Tab order and Enter-to-submit work in the login, search and dialogs?
- Is the contrast at least 4.5:1 for text in both themes?

Write the answers in a short "UX check" section at the end of `docs/design-review-2026-10-31.md`, and commit it.

## Final report to the user

When finished, reply with:
- one line per step: commit sha and what changed, or "skipped: why";
- every git problem met, with the `git status` output;
- the final `py -3 -m pytest` result;
- the report items still `open`.
