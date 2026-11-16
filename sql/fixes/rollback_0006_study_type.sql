-- rollback_0006_study_type.sql — undo migration 0006 (study type split). Run BY HAND on the server,
-- only after a mysqldump, then reinstall the previous server build (2.5.3) so SP.sql matches.
-- Keeps data written after the update (except students.study_type, which the old schema has no place for).
--   mysql --no-defaults -u <user> -p certificate_manager < rollback_0006_study_type.sql
-- Needs the _bak_0006_* tables that 0006 made.

-- 1. Put study systems 3-6 back exactly as they were
INSERT INTO `study_systems`
SELECT b.* FROM `_bak_0006_study_systems` b
LEFT JOIN `study_systems` s ON s.`id` = b.`id`
WHERE s.`id` IS NULL;
UPDATE `study_systems` s JOIN `_bak_0006_study_systems` b ON b.`id` = s.`id`
   SET s.`study_day_type` = b.`study_day_type`;

-- 2. Orders: old system id and old type text (orders created after the update keep their values)
UPDATE `graduation_orders` o JOIN `_bak_0006_orders` b ON b.`id` = o.`id`
   SET o.`study_system_id` = b.`study_system_id`, o.`study_type` = b.`study_type`;

-- 3. Students: old system id
UPDATE `students` s JOIN `_bak_0006_students` b ON b.`id` = s.`id`
   SET s.`study_system_id` = b.`study_system_id`;

-- 4. Remove what 0006 added
ALTER TABLE `students` DROP COLUMN `study_type`;
DROP TABLE IF EXISTS `study_system_aliases`;
DELETE FROM `schema_migrations` WHERE `filename` = '0006_study_type_split.sql';

-- 5. Keep the _bak_0006_* tables until the rollback is confirmed, then:
--    DROP TABLE `_bak_0006_study_systems`, `_bak_0006_orders`, `_bak_0006_students`;
