-- =============================================================================
-- 2026-10-24_03_change_tracking_and_cert_blocks.sql
-- 1) Change tracking: laptops download only rows changed since their last sync
--    (updated_at column + a record of deleted rows), instead of whole tables.
-- 2) Certificate number blocks reserved by each laptop for offline printing.
--
-- Run ONCE in phpMyAdmin / MySQL Workbench on the certificate_manager database,
-- after 2026-10-24_01 and _02. The program works before this is run (full downloads,
-- no conflict check, no reserved numbers) and uses the new features right after.
-- Large tables (enrollments, students) may take a few seconds each.
-- If you run it twice, the ALTER / CREATE TRIGGER lines fail with "Duplicate" errors -
-- that is fine, the rest is unaffected.
-- =============================================================================

-- 1. Record of deleted rows (filled by the triggers below)
CREATE TABLE IF NOT EXISTS sync_deletions (
    id          BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
    table_name  VARCHAR(64)  NOT NULL,
    row_id      INT          NOT NULL,
    deleted_at  TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    KEY idx_sync_deletions_table_time (table_name, deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Certificate number blocks (one row per block a laptop reserved)
CREATE TABLE IF NOT EXISTS certificate_number_blocks (
    id           INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    device_id    VARCHAR(64)  NOT NULL,
    year_suffix  VARCHAR(10)  NOT NULL,
    start_no     INT          NOT NULL,
    end_no       INT          NOT NULL,
    reserved_at  TIMESTAMP    NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_cert_blocks_year (year_suffix, end_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. updated_at on every replicated table: set by MySQL itself on INSERT and on every UPDATE
ALTER TABLE university_settings ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_university_settings_updated_at (updated_at);
ALTER TABLE countries ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_countries_updated_at (updated_at);
ALTER TABLE governorates ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_governorates_updated_at (updated_at);
ALTER TABLE settings ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_settings_updated_at (updated_at);
ALTER TABLE departments ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_departments_updated_at (updated_at);
ALTER TABLE study_systems ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_study_systems_updated_at (updated_at);
ALTER TABLE personnel ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_personnel_updated_at (updated_at);
ALTER TABLE courses ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_courses_updated_at (updated_at);
ALTER TABLE graduation_orders ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_graduation_orders_updated_at (updated_at);
ALTER TABLE students ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_students_updated_at (updated_at);
ALTER TABLE academic_periods ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_academic_periods_updated_at (updated_at);
ALTER TABLE enrollments ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_enrollments_updated_at (updated_at);
ALTER TABLE student_supervisors ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_student_supervisors_updated_at (updated_at);
ALTER TABLE thesis_records ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_thesis_records_updated_at (updated_at);
ALTER TABLE issued_certificates ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_issued_certificates_updated_at (updated_at);
ALTER TABLE study_routines ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_study_routines_updated_at (updated_at);
ALTER TABLE study_routine_period ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_study_routine_period_updated_at (updated_at);
ALTER TABLE study_routine_courses ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_study_routine_courses_updated_at (updated_at);
ALTER TABLE personnel_permissions ADD COLUMN updated_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3), ADD INDEX idx_personnel_permissions_updated_at (updated_at);

-- 4. Remember deleted rows (MySQL does not run these for rows removed by ON DELETE CASCADE;
--    the program cleans those up itself and also does a full download once a day)
CREATE TRIGGER trg_university_settings_sync_delete AFTER DELETE ON university_settings FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('university_settings', OLD.id);
CREATE TRIGGER trg_countries_sync_delete AFTER DELETE ON countries FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('countries', OLD.id);
CREATE TRIGGER trg_governorates_sync_delete AFTER DELETE ON governorates FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('governorates', OLD.id);
CREATE TRIGGER trg_settings_sync_delete AFTER DELETE ON settings FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('settings', OLD.id);
CREATE TRIGGER trg_departments_sync_delete AFTER DELETE ON departments FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('departments', OLD.id);
CREATE TRIGGER trg_study_systems_sync_delete AFTER DELETE ON study_systems FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('study_systems', OLD.id);
CREATE TRIGGER trg_personnel_sync_delete AFTER DELETE ON personnel FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('personnel', OLD.id);
CREATE TRIGGER trg_courses_sync_delete AFTER DELETE ON courses FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('courses', OLD.id);
CREATE TRIGGER trg_graduation_orders_sync_delete AFTER DELETE ON graduation_orders FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('graduation_orders', OLD.id);
CREATE TRIGGER trg_students_sync_delete AFTER DELETE ON students FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('students', OLD.id);
CREATE TRIGGER trg_academic_periods_sync_delete AFTER DELETE ON academic_periods FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('academic_periods', OLD.id);
CREATE TRIGGER trg_enrollments_sync_delete AFTER DELETE ON enrollments FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('enrollments', OLD.id);
CREATE TRIGGER trg_student_supervisors_sync_delete AFTER DELETE ON student_supervisors FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('student_supervisors', OLD.id);
CREATE TRIGGER trg_thesis_records_sync_delete AFTER DELETE ON thesis_records FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('thesis_records', OLD.id);
CREATE TRIGGER trg_issued_certificates_sync_delete AFTER DELETE ON issued_certificates FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('issued_certificates', OLD.id);
CREATE TRIGGER trg_study_routines_sync_delete AFTER DELETE ON study_routines FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('study_routines', OLD.id);
CREATE TRIGGER trg_study_routine_period_sync_delete AFTER DELETE ON study_routine_period FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('study_routine_period', OLD.id);
CREATE TRIGGER trg_study_routine_courses_sync_delete AFTER DELETE ON study_routine_courses FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('study_routine_courses', OLD.id);
CREATE TRIGGER trg_personnel_permissions_sync_delete AFTER DELETE ON personnel_permissions FOR EACH ROW INSERT INTO sync_deletions (table_name, row_id) VALUES ('personnel_permissions', OLD.id);

-- 5. Optional housekeeping (run now and then): forget deletions older than 90 days
-- DELETE FROM sync_deletions WHERE deleted_at < NOW() - INTERVAL 90 DAY;
