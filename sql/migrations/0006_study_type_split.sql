-- 0006: study system (فصلي / مقررات) and study type (صباحي / مسائي / موازي) become two separate values.
--   Before: study_systems had 6 rows, one per system × day type (1/3/5 فصلي, 2/4/6 مقررات ×
--           Morning/Evening/Other), and every student sat on 1 or 2, so certificates printed
--           «الصباحية» for evening students.
--   After:  study_systems keeps rows 1 and 2; the type lives on students.study_type and
--           graduation_orders.study_type ('morning' | 'evening' | 'parallel').
--   Old clients (2.5.2 / 2.5.3) may still send ids 3-6: the API maps them through
--   study_system_aliases. study_day_type stays (unused, 'Morning') until a later migration.
-- Rollback: sql/fixes/rollback_0006_study_type.sql (uses the _bak_0006_* tables made here).
-- Plan: docs/plan-study-type-split-and-followups.md (sections 3 and 8).

-- 1. Exact rollback data, kept inside the database (made only on the first run)
SET @has := (SELECT COUNT(*) FROM information_schema.TABLES
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '_bak_0006_study_systems');
SET @sql := IF(@has = 0, 'CREATE TABLE `_bak_0006_study_systems` AS SELECT * FROM `study_systems`', 'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has := (SELECT COUNT(*) FROM information_schema.TABLES
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '_bak_0006_orders');
SET @sql := IF(@has = 0,
  'CREATE TABLE `_bak_0006_orders` AS SELECT `id`, `study_system_id`, `study_type` FROM `graduation_orders`',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has := (SELECT COUNT(*) FROM information_schema.TABLES
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '_bak_0006_students');
SET @sql := IF(@has = 0,
  'CREATE TABLE `_bak_0006_students` AS SELECT `id`, `study_system_id` FROM `students`',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 2. Old id -> (system, type), used by the API for old clients and queued offline writes
CREATE TABLE IF NOT EXISTS `study_system_aliases` (
  `old_id` int(11) NOT NULL,
  `study_system_id` int(11) NOT NULL,
  `study_type` enum('morning','evening','parallel') NOT NULL,
  PRIMARY KEY (`old_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

INSERT INTO `study_system_aliases` (`old_id`, `study_system_id`, `study_type`) VALUES
  (1, 1, 'morning'), (2, 2, 'morning'),
  (3, 1, 'evening'), (4, 2, 'evening'),
  (5, 1, 'parallel'), (6, 2, 'parallel')
ON DUPLICATE KEY UPDATE `study_system_id` = VALUES(`study_system_id`), `study_type` = VALUES(`study_type`);

-- 3. students.study_type (added and filled only on the first run, so later edits are never overwritten)
SET @had_student_type := (SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'students' AND COLUMN_NAME = 'study_type');
SET @sql := IF(@had_student_type = 0,
  'ALTER TABLE `students` ADD COLUMN `study_type` enum(''morning'',''evening'',''parallel'') NOT NULL DEFAULT ''morning'' AFTER `study_system_id`',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 4. graduation_orders: one spelling for the type; the old evening/other system ids decide first
UPDATE `graduation_orders` o
  LEFT JOIN `study_system_aliases` a ON a.`old_id` = o.`study_system_id` AND a.`old_id` > 2
SET o.`study_type` = CASE
      WHEN a.`old_id` IS NOT NULL THEN a.`study_type`
      WHEN LOWER(TRIM(o.`study_type`)) IN ('evening', 'مسائي', 'المسائي', 'مسائية', 'المسائية') THEN 'evening'
      WHEN LOWER(TRIM(o.`study_type`)) IN ('parallel', 'other', 'موازي', 'الموازي', 'موازية', 'الموازية') THEN 'parallel'
      ELSE 'morning'
    END;

-- 5. Fill students.study_type: from the student's order, else from the old system id (first run only)
SET @sql := IF(@had_student_type = 0,
  'UPDATE `students` s
     LEFT JOIN `graduation_orders` o ON o.`id` = s.`order_id`
     LEFT JOIN `study_system_aliases` a ON a.`old_id` = s.`study_system_id`
   SET s.`study_type` = COALESCE(o.`study_type`, a.`study_type`, ''morning'')',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 6. Move every reference from ids 3-6 to 1 / 2
UPDATE `graduation_orders` o JOIN `study_system_aliases` a ON a.`old_id` = o.`study_system_id`
   SET o.`study_system_id` = a.`study_system_id` WHERE o.`study_system_id` > 2;
UPDATE `students` s JOIN `study_system_aliases` a ON a.`old_id` = s.`study_system_id`
   SET s.`study_system_id` = a.`study_system_id` WHERE s.`study_system_id` > 2;
UPDATE `study_routines` r JOIN `study_system_aliases` a ON a.`old_id` = r.`study_system_id`
   SET r.`study_system_id` = a.`study_system_id` WHERE r.`study_system_id` > 2;
UPDATE `academic_periods` p JOIN `study_system_aliases` a ON a.`old_id` = p.`study_system_id`
   SET p.`study_system_id` = a.`study_system_id` WHERE p.`study_system_id` > 2;

-- 7. Two systems left (the delete trigger tells the laptops to drop 3-6)
DELETE FROM `study_systems` WHERE `id` IN (3, 4, 5, 6);
UPDATE `study_systems` SET `study_day_type` = 'Morning' WHERE `id` IN (1, 2);

-- 8. Counts to compare with the plan (418 evening students expected); run these by hand after the update
SELECT `study_type`, COUNT(*) AS students FROM `students` GROUP BY `study_type`;
SELECT `study_system_id`, `study_type`, COUNT(*) AS orders FROM `graduation_orders` GROUP BY `study_system_id`, `study_type`;
