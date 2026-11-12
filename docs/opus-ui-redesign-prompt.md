# Prompt for Opus: professional UI/UX redesign

Copy everything below the line into a new Opus session. This replaces `docs/haiku-ui-prompt-2.md`; don't run both.

---

Act as a senior product designer and front-end engineer. Redesign the UI and UX of the Certificate Manager desktop app (Python, NiceGUI, pywebview, Arabic RTL). It is used by university staff to manage students and issue graduation certificates.

**The goal:** a professional, calm, consistent app that a new admin can use without training. Target a UX score of 85+/100; today it is about 52.

**Where to work:** `F:\CR_PY\certificate_manager\.claude\worktrees\certificate-design-fixes-dce558`, branch `claude/certificate-design-fixes-dce558`.

## Read first

- `docs/design-review-2026-10-31.md`: 52 findings with IDs and status. Pass 1 (by Haiku) partly fixed some of them.
- `docs/haiku-ui-prompt.md` and `docs/haiku-ui-prompt-2.md`: the earlier briefs. Their findings stand: newest-first lists, design tokens, font fallback.
- `git log --oneline 571f6aa..HEAD`: what pass 1 changed. The roughly 600 label edits were never checked in the app; treat them as unverified.

## Hard rules

1. **Do not touch the Word templates.** That means `templets/`, any `.docx` file, and the template field/context code in `services/certificate_context.py`. Certificates must print exactly as before.
2. **UI and CSS only**, plus the ORDER BY of list queries. Don't change what is saved, the API contracts or the database schema.
3. **Never write to MySQL.** Never delete files: move obsolete ones to `old/`.
4. **Run the API only through `start_server.bat`.** Never leave a hidden server on port 2030.
5. **Git:**
   - One commit per step, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
   - `git add <files>` by name only. Never stage `data/roles_config.json` (the app rewrites it). Never stage the 7 files that differ only in line endings (`main.py`, `nicegui_screens/__init__.py`, `nicegui_screens/settings/__init__.py`, `nicegui_screens/settings_screen.py`, `nicegui_ui/__init__.py`, `nicegui_ui/state.py`, `nicegui_ui/upload_utils.py`) unless you made a real edit to one of them.
   - **Never push.** Never use force, `reset --hard`, `checkout --`, `clean` or `--no-verify`.
   - On any git problem, stop and report with the `git status` output.
6. **Tests:**
   - `py -3 -m pytest` must pass before every commit.
   - The 2 failures in `tests/test_server_config.py` are known; they need a `db_config.json` that is missing from this worktree. Don't copy credentials.
   - Add tests for logic you change: sort orders, the font CSS, the settings tabs, helpers.
7. **Checking in the app:**
   - Run `py -3 main.py --web` and open http://localhost:2323 in the browser pane.
   - The user allows the test admin account (username `1`, password `1`) for this work only. Don't store it anywhere.
   - Look and navigate only. Don't save, issue or delete real records.
   - Stop the app when you finish.
8. **Work in one run.** Don't stop for approval between steps; stop only for a git problem. Check every step in the app (screenshots at 800×600 and 1366×768, dark and light themes) before committing it.

## Design principles

- **Arabic only in the UI.** Remove all English sublabels, placeholders and notification text. Labels are short and never truncated with "…".
- **One obvious next action per screen:** one filled primary button. Secondary actions are outlined, back/cancel are text buttons.
- **Destructive actions are quiet.** Use a grey icon that turns red on hover, or a ⋮ menu. Always confirm, and show the item's name in the confirmation.
- **Lists show newest first** and are read-only. Editing happens in a side panel or dialog. Every list has search, an empty state and one standard paginator.
- **Clear feedback:**
  - every action shows a short Arabic toast;
  - loading shows a skeleton;
  - errors say what to do next.
- **Keyboard:** Enter submits, Esc closes dialogs, the Tab order follows RTL reading order, and focus rings are visible.
- **Contrast** of at least 4.5:1 for text in both themes.

## Steps (one commit each)

1. **Check pass 1 in the app.** Fix leftover English, broken text and truncation on every page.
2. **Design system.** Define it once in `nicegui_ui/theme.css` as CSS variables and in `nicegui_ui/ui_components.py` as helpers. Screens use only these.
   - Spacing: 4/8/12/16/24/32. Radius: 8. One border colour.
   - Type scale 12/14/16/20/24, body 14, line-height 1.5.
   - Font:
     - Use `local('Cairo')` from the installed fonts, falling back to `'Segoe UI', Tahoma, Arial, sans-serif`.
     - Remove the Google Fonts `@import`; the app works offline.
     - Keep one font-stack definition only.
     - No monospace or letter-spaced text.
   - Controls are 40 px tall, 32 px in dense tables. Button text is centred with `inline-flex` and `align-items:center` (today it sits low).
   - Every toolbar row shares one height and baseline.
   - Colour: one green accent, neutral greys, red only for danger, amber for warnings. No blue, no rainbow icons.
   - Components: Button (primary/secondary/ghost/danger-icon), Input, Select, DateField (YYYY-MM-DD, as in `571f6aa`), Switch (clear on/off), Card (no nested borders), DataTable (48 px rows, centred cells, sticky header), Paginator, EmptyState, ConfirmDialog, SidePanel, Toast, PageHeader, Skeleton.
3. **App shell.**
   - The sidebar is a flat list: icon plus Arabic label; the active item has a filled background and an accent bar; it can collapse to icons.
   - The header is one row of one height:
     - the page title once;
     - on the other side, a sync-status dot, a refresh icon and a user chip whose menu holds Profile and Logout.
   - Only the content area scrolls, and the scrollbar sits on the correct side.
   - Consistent page padding.
4. **Newest first everywhere.**
   - Departments, the Courses management screen, Personnel and Roles change to `id DESC`. Check study routines and any other list.
   - Keep stage/name order where courses feed transcripts, certificates or dropdowns.
   - Remove any client-side re-sorting.
   - Add a test per changed query.
5. **Login and dashboard.**
   - Login: centred card, accent button, Enter submits, a clear error message, theme toggle in a corner.
   - Dashboard:
     - stats in the order Students, Issued certificates, Courses, Personnel;
     - one large primary tile "إصدار وثيقة";
     - recent students and recent issued certificates, visible at 800×600.
6. **Students.**
   - The list has search, the add buttons in one toolbar row and 2-decimal averages.
   - The student view is its own page with a "رجوع" back button and a two-column details list, with a direct "إصدار وثيقة لهذا الطالب" button.
   - Add Student works from anywhere.
   - Bulk import keeps working.
7. **Graduation orders, courses, personnel.**
   - Order cards show the number and date prominently.
   - Course rows are read-only, edited in a dialog.
   - The personnel signature chip appears only when a signature exists.
   - One paginator everywhere.
8. **Settings.**
   - Vertical tab list. The Departments tab comes right after "معلومات الجامعة"; it already exists and needs polish.
   - Long college names get full-width fields.
   - The logo upload shows a preview of the current logo. It has no "0.0B / 0.00%" and no empty box until an upload actually runs.
   - The RTL switch goes under "متقدم".
   - Role cards are simpler.
   - Printer labels are not truncated.
9. **Redesign the issue-certificate flow.** This is the main task.
   - Make it a clear 3-step wizard with a stepper at the top:
     1. **Student:** search and pick a student; a recent-students list shows by default.
     2. **Document:**
        - document type and template, shown by display name, never by file name;
        - the options with clear switches;
        - a sensible default for every option, so most users just press Next;
        - advanced options collapsed.
     3. **Review and issue:**
        - a summary of the student, document, number and recipient;
        - a duplicate-number warning shown inline;
        - one primary "إصدار وطباعة" button; PDF preview and Save are secondary.
   - The transcript shows as flat table rows. The printer dialog has no truncation.
   - Target: from the dashboard to an issued certificate in 4 clicks or fewer for the common case.
   - **Do not change the context data passed to the templates.** Only the screens that collect it change.
10. **Issued certificates log.**
    - Five columns; a row click opens the details, with Reprint and PDF actions.
    - The filters are wide enough and sit in one row.
    - Newest first.
11. **Profile and speed.**
    - Fix the tooltip overlap.
    - Show a skeleton immediately on page switch.
    - Measure the page-build times, fix the slowest pages, and put the before/after numbers in the commit message.
12. **Final audit.**
    - Go through every page in both themes at both sizes.
    - In `docs/design-review-2026-10-31.md`, set each item's Status to `fixed (<sha>)`, `won't fix: why` or `open: why`.
    - Write a "UX check" section from what you saw, with a new score out of 100 for each area: learnability, task speed, visual quality, readability, consistency, feedback and safety, performance, data presentation.

## Final report

When you finish, reply with:
- one line per step: commit sha and what changed, or why it was skipped;
- what you checked in the app;
- any git problems;
- the final pytest result;
- the new UX score;
- the item IDs still open.
