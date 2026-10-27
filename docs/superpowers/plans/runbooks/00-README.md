# Runbooks: how to execute this plan with a low-cost model

These runbooks turn the plan in `../2026-10-27-refactor-and-install.md` into exact,
copy-only steps. They are written for **Claude Haiku**. Every file content, every
edit and every command is given in full, and was dry-run on a scratch copy of the
repository before it was written down. The executor never designs anything.

## Which model runs which phase

| Order | Runbook | Model | What it does |
|---|---|---|---|
| 1 | `phase-0-safety-net.md` | Haiku | pytest + snapshot tests of today's behaviour |
| 2 | `phase-1-hygiene.md` | Haiku | untrack secrets/data, move duplicates, pin requirements, DB login out of code |
| 3 | `phase-2-paths.md` | Haiku | per-user data folder, OTA updater fix, version file |
| 4 | `phase-6-client-installer.md` | Haiku | fixed PyInstaller build + Inno Setup installer + release script |
| 5 | `phase-7-server-bundle.md` | Haiku | server bundle + idempotent `setup_server.bat` |
| 6 | Phases 3, 4, 5 in `../2026-10-27-refactor-and-install.md` | **Sonnet or Opus** | splitting the 2–4k-line files (needs judgement) |
| 7 | `phase-8-docs-rollout.md` | Haiku | docs, final release build, PR; then the user-driven rollout |

Run **one runbook per session**. Start a new session for the next one.

## Rules for the executor

1. **Start-up.** `CLAUDE.md` asks you to run the task-observer start-up first. Do that,
   then open the runbook and run its "Before you start" block.
2. **Order.** Do the steps in order. Do not skip, merge, reorder or "improve" steps.
   Do not change code that a step does not mention.
3. **Write steps** ("Write `path`"): use the **Write** tool. The file content is
   everything between the opening fence line (` ````python file=… `) and the closing
   fence line (` ```` `), **without** those two fence lines. If the file already
   exists, Read it first (the Write tool requires it), then Write the full new content.
4. **Edit steps** ("Edit `path`"): Read the file first. Then call the **Edit** tool with
   `old_string` = the text in the **Find** block and `new_string` = the text in the
   **Replace with** block, exactly, including indentation. When the step says
   **all occurrences**, set `replace_all` to true. If Edit says the text was not found
   or is not unique: STOP (rule 6).
5. **Run steps** (` ````powershell run `): run the whole block with the **PowerShell**
   tool as one call, from the repository root `F:\CR_PY\certificate_manager`.
6. **Expected / STOP.** After each run step, compare the output with the line
   `Expected:`. If it does not match, or any tool reports an error, **STOP**:
   do not try to fix it, do not try another command. Tell the user the step number,
   what you ran, and the full output. The only exception is when the step itself
   says what to do on a specific output.
7. **Git.** Run only the git commands written in the runbook. Never `push`, `reset`,
   `stash`, `rebase`, or switch branches unless a step says so. Commit only the paths
   the step lists. If your environment requires a `Co-Authored-By` line, add it as one
   extra `-m "…"` argument to the commit command; change nothing else.
8. **Database and server.** Never change MySQL. Never start or stop the API server or
   the Windows service unless a step says so. Steps marked ` ````powershell manual `
   are for the **user**: show them to the user and wait for "done".
9. **End.** Run the final step of the runbook (it prints the new commits) and report
   that output to the user.

## Harmless messages (do not STOP for these)

- `warning: in the working copy of '…', LF will be replaced by CRLF the next time Git touches it`
- pip notices such as `[notice] A new release of pip is available`
- pytest warnings such as `PytestUnknownMarkWarning` or `DeprecationWarning`, as long as the `passed` count matches
- PyInstaller lines such as `WARNING: Hidden import "tzdata" not found!`, `Hidden import "pycparser.lextab" not found!`, or `Failed to collect submodules for 'webview.platforms.android'`

## What "Expected" means

`Expected: `12 passed`` means the output must contain that text. Extra lines around it
(timings, warnings) are fine. A different number is **not** fine: STOP.
