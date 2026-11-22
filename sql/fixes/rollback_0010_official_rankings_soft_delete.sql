-- Rollback of 0010: removes the soft-delete columns (lists already archived become visible again).
-- Take a mysqldump first.
ALTER TABLE `official_rankings` DROP COLUMN `deleted_at`, DROP COLUMN `deleted_by`;
DELETE FROM `schema_migrations` WHERE `filename` = '0010_official_rankings_soft_delete.sql';
