# 04 — Official rankings page + real-Excel test (TODO A4 + bullet line 59)
- Goal: dedicated page for official ranking lists (like graduation orders) and a verified import of a real Student Affairs Excel.
- Files: `nicegui_screens/official_rankings_view.py`, `services/official_ranking_import.py`, router `official_rankings` (exist — extend only).
- DB / migration: none expected (0007 already added tables); if a column is missing → `0008_*` is reserved, use next free number + rollback.
- Tests first: `tests/test_official_ranking_import.py` with an anonymised copy of the real header row.
- Risks: real file layout differs from guessed columns. NOTE: sibling session build-rankings-page is working on this — merge, don't redo.
- Model: Sonnet.
- Question: Can you send one real rankings Excel (names may be blanked)?
