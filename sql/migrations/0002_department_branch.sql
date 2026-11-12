-- 0002: the branch (الفرع) of a department, printed on certificates as {{branch}}

SET @has := (SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'departments' AND COLUMN_NAME = 'branch_ar');
SET @sql := IF(@has = 0,
  'ALTER TABLE `departments` ADD COLUMN `branch_ar` varchar(150) DEFAULT NULL AFTER `name_en`',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
