-- 0005: order images become files on the server (C:\AppServ\order_images\<order_id>\);
--       the table keeps only the file name. The API moves the images stored by 2.4.0 out of
--       the database at its next start; the blob columns stay (empty) until a later version.

SET @has := (SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'graduation_order_images' AND COLUMN_NAME = 'file_name');
SET @sql := IF(@has = 0,
  'ALTER TABLE `graduation_order_images` ADD COLUMN `file_name` varchar(100) DEFAULT NULL AFTER `sha256`',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE `graduation_order_images` MODIFY `image` mediumblob NULL, MODIFY `thumb` blob NULL;
