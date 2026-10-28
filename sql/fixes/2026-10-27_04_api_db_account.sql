-- =============================================================================
-- 2026-10-27_04_api_db_account.sql
-- Run ONCE in phpMyAdmin (SQL tab) while logged in as root: on the developer laptop
-- and on the server laptop. FIRST replace the two CHANGE-ME passwords (keep the quotes).
--
-- 1. A dedicated MySQL account for the FastAPI server, with rights on the
--    certificate_manager database only (instead of root).
-- 2. A new root password. The old one was committed to GitHub: treat it as public.
--
-- Afterwards put the new account into certificate_manager_api\db_config.json:
--   {"host": "localhost", "user": "certman_api", "password": "<password from step 1>", "database": "certificate_manager"}
-- and restart the API (server: switch_server_mode.bat https|http; developer laptop: start_server.bat).
--
-- If Settings -> Backup later fails with "PROCESS privilege", also run:
--   GRANT PROCESS ON *.* TO 'certman_api'@'localhost';
-- A full restore of a dump whose procedures have DEFINER=`root` must still be done as root.
-- =============================================================================

CREATE USER IF NOT EXISTS 'certman_api'@'localhost' IDENTIFIED BY 'CHANGE-ME-api-password';
GRANT ALL PRIVILEGES ON certificate_manager.* TO 'certman_api'@'localhost';
FLUSH PRIVILEGES;

ALTER USER 'root'@'localhost' IDENTIFIED BY 'CHANGE-ME-new-root-password';
