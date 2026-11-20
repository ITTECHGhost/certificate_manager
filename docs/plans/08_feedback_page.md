# 08 — In-app feedback/complaints page (TODO C13 + bullet line 87)
- Goal: user writes a note; saved with screen name, app version, time, user; admins list them.
- Files: new `nicegui_screens/feedback.py`, `data/repositories/feedback_repo.py`, new router `certificate_manager_api/routers/feedback.py`, register in `main.py`; offline → `sync_engine` queue.
- DB / migration: `feedback` table in `0009_feedback_holds.sql` + rollback (plan 07).
- Tests first: `tests/test_feedback_router.py` (validation: empty/too long rejected; one transaction), add to all_or_nothing guard.
- Risks: needs migration before release; without plan 06 the "user" field is trust-the-client. NOTE: sibling session build-feedback-page is working on this — merge, don't redo.
- Model: Sonnet.
- Question: Should staff see their own past notes, or only admins see the list?
