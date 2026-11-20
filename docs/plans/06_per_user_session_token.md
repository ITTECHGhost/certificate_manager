# 06 — Per-user session token + password-change guard (TODO C11)
- Goal: `/api/login` issues a token; `current_user` dependency on every router; `PUT /personnel/{id}/password` needs old password or admin; X-App-Key `enforce=true`.
- Files: `certificate_manager_api/routers/personnel.py` (login), `deps.py` (`current_user`), `main.py`, `api_client.py` (send token, re-login on 401), `sync_engine.py` (offline queue keeps user).
- DB / migration: `user_sessions` table in `0008_identity.sql` + `sql/fixes/rollback_0008_identity.sql` (plan 07).
- Tests first: `tests/test_auth_token.py` (no token → 401, expired → 401, change other user's password → 403), all_or_nothing still green.
- Risks: old clients break the day enforce goes on → needs minimum-version gate (plan 07) and a staged rollout; offline mode replays with stale token.
- Model: Opus (security, cross-cutting).
- Question: Token lifetime — one working day (re-login each morning) OK?
