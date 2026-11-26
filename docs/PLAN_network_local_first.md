# Plan: work well on a bad network (local-first) — 2026-11-25

Why: one user laptop loses the server often (ping test: mostly unreachable). Login, search and
ping are slow; the app flips online/offline and makes temporary ids (the −3 print bug, fixed in e7bc732).
Goal: the user never waits on the network for reading; writes keep going through the queue.

## What exists already (reuse, do not rebuild)
- SQLite replica `local_cache.db` + `pull_mysql_to_sqlite` (incremental `since`), offline queue with id_map.
- `LOCAL_FIRST_TABLES` (departments, study_systems, courses, countries, governorates, graduation_orders),
  refreshed every 5 min — but repositories still call the API first for most reads.
- Online check every 5 s (`check_network_status` in dashboard loop); on offline→online it runs a full
  queue sync + replica pull.
- "Slow API call" lines in the client log (e7bc732) and log upload in feedback.

## Steps (one session each, in order)
1. **Measure (no code).** Get the user's log through feedback; list the slow calls and how often the
   online flag flips. Decides the order of 3–5.
2. **Stop the flapping.** Online = 2 failed checks in a row to go offline, 2 good ones to come back
   (hysteresis); short check timeout (2 s). After coming back, pull only changed rows, never a full pull
   more than once per N minutes. Files: `sync_engine.py`, `dashboard_screen.py`. Tests: state machine.
3. **Local-first reads.** Student search, students list, student by id, issued list, reports read from
   SQLite always; a background pull keeps it fresh (every 1–2 min when online, changed rows only).
   API only for: issuing/number reservation, login check, permissions refresh, file downloads.
   Files: `data/repositories/students.py`, `certificates.py` (+ the matching `data/query.py` readers).
   Risk: data up to ~2 min old on screen → show "آخر تحديث: …" and a refresh button.
4. **Short cache for rarely-changing data.** Settings, templates list, permissions/access profile:
   memory cache 5–10 min, cleared when the user saves one. File: `data/repositories/base.py` helper.
5. **Fast login.** Try the server with a 3 s limit; if no answer, log in with the local password hash
   (already stored) and mark the session "offline login"; re-check in the background.
   Files: `data/repositories/auth.py`. Test: server down → login < 4 s.
6. **Sync status visible.** Header badge: "N بانتظار الرفع" (from `get_queue_status`), red if any failed;
   click → list. Users know offline prints are queued, not lost.
7. **Ship.** Server laptop update + release build (user's OK), then compare the user's slow-call log
   before/after.

## Not doing (and why)
- WebSocket: does not help a dropping link; adds reconnect complexity.
- Offline login for a user never logged in on that laptop: no local hash → still needs the server.
- Changing the network: outside our control (report it to whoever runs it).

## Tests to keep green
`tests/test_all_or_nothing.py`, the sync/queue tests, plus one new test per step.
