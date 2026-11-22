-- 0012: scanned pages of an official ranking list (الورقة الممسوحة لقائمة الترتيب).
--   Like graduation-order pages: JPEG files on the server (ranking_images\<ranking_id>\<sha>.jpg
--   + <sha>_t.jpg); the table keeps the name. Soft delete only; the file is never erased.
-- Rollback: sql/fixes/rollback_0012_official_ranking_images.sql

CREATE TABLE IF NOT EXISTS `official_ranking_images` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `ranking_id` int(11) NOT NULL,
  `page_no` int(11) NOT NULL DEFAULT 1,
  `sha256` char(64) NOT NULL,
  `file_name` varchar(100) NOT NULL,
  `source_name` varchar(255) DEFAULT NULL,
  `created_by` int(11) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `deleted_at` timestamp NULL DEFAULT NULL,
  `deleted_by` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_official_ranking_images_list` (`ranking_id`, `page_no`),
  CONSTRAINT `fk_official_ranking_images_list` FOREIGN KEY (`ranking_id`)
    REFERENCES `official_rankings` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
