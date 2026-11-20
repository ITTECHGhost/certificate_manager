# 05 — registration_web Day 2 remainder: real server install (TODO 6 [~])
- Goal: run `install_service.ps1` on 172.50.1.100 as admin, create trial users, log in from another PC, do the first restore test per `RESTORE.md`.
- Files: none expected; fixes only in `registration_web/install_service.ps1` / `RESTORE.md` if steps fail; dated entry in `.ai/releases.md`.
- DB / migration: SQLite only (`manage.py migrate`, incl. 0005_signedcopy). Never MySQL.
- Tests first: none; checklist run on SERVER laptop, `pytest -q` in `registration_web` before install.
- Risks: firewall/port 2040 blocked; service account cannot reach `REGWEB_DATA_DIR`; restore overwrites live DB (restore to a copy).
- Model: Sonnet (on the SERVER laptop session).
- Question: What are the trial staff names for each unit?
