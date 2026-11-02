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
- the two questions in Step 0;
- a git problem.

## Step 0: Two questions to ask the user at the start, then continue

1. **Font download.** Ask: "May I download the Cairo font (woff2: regular, semibold, bold) from Google Fonts into `assets/fonts/`?" Only if the user says yes:
   - download it;
   - add `@font-face` in `nicegui_ui/theme.css`;
   - make sure the PyInstaller spec bundles `assets/fonts`.

   If the answer is no, skip G5 and say so in the final report.
2. **Sign-in for checks.** Start the app with `py -3 main.py --web`; it runs at http://localhost:2323. Open it in the browser pane and ask the user to sign in there. **Never type a password yourself.** If the user can't sign in, do the code-only work and mark every item "not checked in app".

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
