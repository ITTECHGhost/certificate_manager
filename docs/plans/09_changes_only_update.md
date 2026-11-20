# 09 — Changes-only update package (TODO C13 + bullet line 86)
- Goal: builder compares with previous release, packs only changed files + delete list (manifest with hashes); libs skipped if unchanged; full package stays as fallback.
- Files: `scripts/build_release.bat`, `make_client_patch.ps1`, new `scripts/make_manifest.py`, `services/updater.py` (apply after app exit, `.pending` marker for rollback), `certificate_manager_api/routers/updates.py`.
- DB / migration: none (or `program_versions` from 0008 if min-version check is wanted).
- Tests first: `tests/test_manifest_diff.py` (added/changed/removed detection), `tests/test_updater_apply.py` (rollback when `.pending` remains).
- Risks: half-applied update bricks the exe; antivirus locks files; test on DEV first, server last.
- Model: Opus.
- Question: Keep the last N full packages on the server for rollback — how many (suggest 2)?
