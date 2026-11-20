# 12 — Second laptop receives templates check (bullet line 71)
- Goal: confirm `template_sync` delivers `templets/` to a second client PC and printing works there.
- Files: none expected; fix in `services/template_sync.py` only if it fails; dated note in `.ai/bug-ledger.md`.
- DB / migration: none.
- Tests first: existing template_sync tests (`pytest -q -k template`); then manual print test.
- Risks: Word templates are user-edited only — never modify them; path differences per PC.
- Model: Haiku/Sonnet (checklist run).
- Question: Which second PC can we use for the test?
