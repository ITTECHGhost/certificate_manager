# 02 — «مراجعة الاستخراج» review screen (TODO A2)
- Goal: image beside an editable grid; suspect rows coloured (avg outside 50–100, broken sequence, unknown name, bad order no.); confirm saves in one transaction.
- Files: new `nicegui_screens/extraction_review.py`, `services/extraction_checks.py` (pure checks), menu entry in `main.py`; reuse `/bulk-import` router (no new API).
- DB / migration: none.
- Tests first: `tests/test_extraction_checks.py` (each flag rule), add path to `tests/test_all_or_nothing.py` if a new write path appears.
- Risks: duplicates bulk-import logic; large images slow in pywebview. NOTE: sibling session build-review-screen is working on this now — merge, don't redo.
- Model: Sonnet (UI + clear rules).
- Question: Should a flagged row block saving, or only warn?
