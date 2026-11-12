-- 0001: graduation order images (the scanned order, kept as the college archive)
--       + the expected graduation year/semester of each student (used by auto-link)

CREATE TABLE IF NOT EXISTS `graduation_order_images` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `order_id` int(11) NOT NULL,
  `page_no` int(11) NOT NULL DEFAULT 1,
  `image` mediumblob NOT NULL,
  `thumb` blob NOT NULL,
  `sha256` char(64) NOT NULL,
  `rotation` smallint(6) NOT NULL DEFAULT 0,
  `source_name` varchar(255) DEFAULT NULL,
  `uploaded_by` varchar(100) DEFAULT NULL,
  `uploaded_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `order_page` (`order_id`, `page_no`),
  CONSTRAINT `graduation_order_images_ibfk_1` FOREIGN KEY (`order_id`) REFERENCES `graduation_orders` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

SET @has := (SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'students' AND COLUMN_NAME = 'expected_graduation_year');
SET @sql := IF(@has = 0,
  'ALTER TABLE `students` ADD COLUMN `expected_graduation_year` int(11) DEFAULT NULL AFTER `graduation_semester`',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has := (SELECT COUNT(*) FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'students' AND COLUMN_NAME = 'expected_graduation_semester');
SET @sql := IF(@has = 0,
  'ALTER TABLE `students` ADD COLUMN `expected_graduation_semester` varchar(20) DEFAULT NULL AFTER `expected_graduation_year`',
  'SELECT 1');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Students already graduated: their expected year is the year they graduated
UPDATE `students`
SET `expected_graduation_year` = YEAR(`graduation_date`)
WHERE `expected_graduation_year` IS NULL AND `graduation_date` IS NOT NULL;
