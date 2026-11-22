-- 0010: soft delete for official ranking lists (rule: important records are archived, not erased).
--   Adds deleted_at / deleted_by to official_rankings. Lists with deleted_at set are hidden by the API.
-- Rollback: sql/fixes/rollback_0010_official_rankings_soft_delete.sql
-- Safe to run twice (checks information_schema).

SET @has := (SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'official_rankings' AND COLUMN_NAME = 'deleted_at');
SET @sql := IF(@has = 0,
  'ALTER TABLE `official_rankings` ADD COLUMN `deleted_at` TIMESTAMP NULL DEFAULT NULL, ADD COLUMN `deleted_by` INT(11) NULL DEFAULT NULL',
  'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
