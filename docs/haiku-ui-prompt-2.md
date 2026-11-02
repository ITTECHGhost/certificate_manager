# Prompt for Haiku: UI/UX pass 2

Copy everything below the line into the Haiku session.

---

You are continuing the UI/UX redesign of the Certificate Manager app (Python, NiceGUI, pywebview).
Work in `F:\CR_PY\certificate_manager\.claude\worktrees\certificate-design-fixes-dce558` on branch `claude/certificate-design-fixes-dce558`.

Read these first:
- `docs/design-review-2026-10-31.md`: every item has an ID and a Status.
- `docs/haiku-ui-prompt.md`: the design direction and hard rules from pass 1. **All its hard rules still apply.**

Short version of those rules:
- Don't touch the Word templates.
- Change UI and CSS only.
- Never write to MySQL.
- Never delete files; move them to `old/`.
- Don't push.
- Use one commit per step, with `py -3 -m pytest` passing.
- On a git problem, stop and report; never force anything.

Pass 1 left commits `e9d307f`…`4efa1a4`. 45 items are still `open`.

## Do everything in ONE run

Don't stop between steps for approval. Stop only for:
- (nothing else)
- a git problem.

## Step 0: Setup (no questions needed)

1. **Font: do not download anything.** The installer installs Cairo on the PC. The app must use Cairo when it is installed and fall back to the default font when it isn't.
   - In `nicegui_ui/theme.css`, keep `@font-face { src: local('Cairo'), local('Cairo-Regular') … }` with a font stack of `'Cairo', 'Segoe UI', 'Tahoma', Arial, sans-serif`.
   - Remove the `@import url('https://fonts.googleapis.com/…')` line. The app must work offline, and an `@import` placed after other rules is ignored anyway.
   - Make sure the font stack is defined in one place only (theme.css lines ~19 and ~297 currently disagree).
   - Add a test that theme.css has no `fonts.googleapis.com` and that `--font-primary` starts with Cairo and ends with a generic fallback.
2. **Sign-in for checks.** Start the app with `py -3 main.py --web`; it runs at http://localhost:2323. Open it in the browser pane.
   - The user has allowed you to sign in with the test admin account: username `1`, password `1`. This is only for testing in this run.
   - Do not save these credentials anywhere and do not change the account.
   - Don't save, issue or delete real records while checking. Look and navigate only.

## Known git state (not problems)

- `main.py`, `nicegui_screens/__init__.py`, `nicegui_screens/settings/__init__.py`, `nicegui_screens/settings_screen.py`, `nicegui_ui/__init__.py`, `nicegui_ui/state.py` and `nicegui_ui/upload_utils.py` show as modified. The changes are only line endings (`git diff` shows no content).
  - Leave them unstaged.
  - If you really need to edit one of them, stage only your own edit.
- `data/roles_config.json` is rewritten by the running app. Never stage it.
- Always `git add <file>` by name; never use `git add .` or `-A`.
- Two tests in `tests/test_server_config.py` fail because `certificate_manager_api/db_config.json` is missing in this worktree. They are expected; don't copy credentials. Every other test must pass.

## Step 1: Visual check of pass 1 (first, before new work)

The 600 label edits from pass 1 were never seen in the app. Go through every page at 800×600 and 1366×768, in dark and light themes:
- dashboard
- students and the student view
- orders
- courses
- personnel
- issue certificate: search, student, options
- issued log and its row-detail dialog
- every Settings tab, including the new Departments tab
- profile

Fix anything that is broken: wrong or missing text, leftover English, "…" truncation, layout breaks. Commit as `fix(ui): issues found checking pass 1`.

## Step 1b: Design system (before any screen work)

The app looks unprofessional mainly because nothing lines up. The user reported:
- lines that are not at the same level;
- button text that sits below the middle of the button;
- the "بحث / Search" button text is low and cut off;
- the header pieces (user chip, Online pill, refresh card, title) have different heights.

Fix this at the root, in `nicegui_ui/theme.css` and `nicegui_ui/ui_components.py`, not screen by screen:
- **Fixed control heights.** Inputs, selects and buttons are 40 px (32 px for dense table actions). Use `display:inline-flex; align-items:center; justify-content:center; line-height:1` on buttons, and remove the two-line label stacks that push the text down.
- **One spacing scale:** 4/8/12/16/24/32 px. No other margins or paddings.
- **One radius** (8 px) and one border colour. No nested bordered boxes.
- **Type scale:** 12/14/16/20/24 px. Body text 14 px, page titles 20 px, line-height 1.5.
- **Tables:** row height 48 px, cells vertically centred, numbers aligned to the start, header in the same font size as the body (semibold).
- **Toolbar rows** (search + buttons) share one baseline and one height.

Commit as `style(ui): design tokens; aligned control heights and centred button text`.

Check this in the app with screenshots at 800×600 and 1366×768: every button's text must be centred, and every row of controls must line up.

## Step 1c: Newest first in every list

**Rule: every list shows the most recently added item at the top and the oldest at the bottom.** Already correct:
- students: `s.id DESC`;
- graduation orders: `o.id DESC`;
- issued certificates: `issue_date DESC, id DESC`.

Not following the rule (fix these):
- **Departments:** `data/query.py` ~732 and ~1032 order by `d.name_ar`. Change to `d.id DESC`.
- **Courses list screen:** `data/query.py` ~776/784/792 and `certificate_manager_api/routers/courses.py` 48/73/94 order by stage and name. Use `id DESC` for the Courses management list only. Keep stage/name order where courses feed a transcript, certificate or dropdown: that order is required for certificates.
- **Personnel:** `SELECT * FROM personnel` (`data/query.py` ~759/762) has no ORDER BY. Add `ORDER BY id DESC` for the Personnel screen. Keep `display_order` for the signature list (~362).
- **Roles:** `routers/personnel.py` 440 uses `id ASC`. Use `is_system DESC, id DESC`.
- **Study routines:** `data/query.py` ~1280/1295. Check and use newest first.

Also check the screens for client-side `sorted()`/`.sort()` that re-orders a list after loading, and any list not named here. Only change the ORDER BY of list queries; don't change what is saved. Add a test per changed query that asserts its ORDER BY.

Commit as `fix(lists): newest first in every management list`.

## Steps 2–10 (one commit each)

2. **Finish the global shell:**
   - G3/G4: one scroll container (content only, no double scrollbar).
   - G9: flat sidebar; the active item has a filled background and an accent bar.
   - G8: header with a refresh icon and a user chip; the chip opens a menu with Profile and Logout.
   - G10, G11: consistent top margin; the page title appears once.
3. **Buttons (G6, G7):**
   - Add `primary` / `secondary` / `ghost` / `danger-icon` variants in `nicegui_ui/ui_components.py`.
   - Apply them on every screen: one filled primary per screen.
   - Delete and disable become grey icons that turn red on hover, in every list.
4. **Login and dashboard leftovers:**
   - L1–L4: accent button; theme toggle in a corner with a tooltip; plain background.
   - D2–D4: one icon colour; RTL-correct arrows; recent-students table visible at 800×600.
5. **Students and orders:**
   - S1, S3, S4, S5: short placeholder; 2 decimals; Back button and working Add Student in the student view; two-column personal details.
   - O1, O2: order number and date prominent; dates YYYY-MM-DD with no letter-spacing.

   S2 is test data; leave it.
6. **Departments, courses, personnel:**
   - P1, P2: search icon and placeholder; college name not truncated.
   - P3: read-only course rows, edit in a dialog.
   - P4: one paginator.
   - P5: signature chip only when a signature exists.
7. **Issue certificate (C1–C8):**
   - C1: normal search height.
   - C2: template display name, not the file name (read existing config only).
   - C3: clear on/off switches.
   - C4: rank dropdown width.
   - C5: flat transcript rows.
   - C6: no monospace chips.
   - C7: one primary "إصدار" button.
   - C8: printer dialog has no truncation.
8. **Settings leftovers:**
   - T2: textarea or full width for long college names.
   - T3: show a logo preview; no "0.0B / 0.00%" or empty box until an upload runs.
   - T6: simpler role cards.
   - R2: issued-log filters wide enough.
9. **Profile and speed:**
   - U1: tooltip doesn't cover buttons.
   - U2.
   - G12: show a skeleton immediately on page switch. Log page-build timings, fix the slowest page, and put the before/after times in the commit message.
10. **Docs:**
    - Update every Status in the review file to `fixed (<sha>)`, `partly (<sha>): what is left`, `not checked in app`, or `won't fix: why`.
    - Rewrite the "UX check" section from what you actually saw in the app.

Check each step in the browser before committing it, where sign-in worked.

## Final report

Reply with:
- One line per step: commit sha and what changed, or "skipped: why".
- Whether the font was added.
- What was checked in the app and what wasn't.
- Any git problems, with the `git status` output.
- The final pytest result. Only the two known `test_server_config.py` failures are allowed.
- The IDs still `open`.
- Stop the app on port 2323 before you finish.
