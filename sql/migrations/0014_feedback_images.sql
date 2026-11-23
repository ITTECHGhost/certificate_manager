-- 0014: pictures attached to a feedback note (screenshots, photos of the problem).
--   Like the other images: JPEG files on the server (feedback_images\<feedback_id>\<sha>.jpg);
--   the table keeps the row. Soft delete only; the file is never erased.
--   (student_holds, if it ever comes to MySQL, takes 0015.)
-- Rollback: sql/fixes/rollback_0014_feedback_images.sql

CREATE TABLE IF NOT EXISTS `feedback_images` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `feedback_id` int(11) NOT NULL,
  `sha256` char(64) NOT NULL,
  `file_name` varchar(100) NOT NULL,
  `source_name` varchar(255) DEFAULT NULL,
  `created_by` int(11) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `deleted_at` timestamp NULL DEFAULT NULL,
  `deleted_by` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_feedback_images_note` (`feedback_id`),
  CONSTRAINT `fk_feedback_images_note` FOREIGN KEY (`feedback_id`) REFERENCES `feedback` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
