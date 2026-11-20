-- 0009: in-app feedback / complaints (صفحة الملاحظات).
--   Users type a note inside the program; the client adds the screen they were on and the
--   program version, so a report like "can't type Arabic" arrives with details.
--   Soft delete only (deleted_at / deleted_by).
-- Rollback: sql/fixes/rollback_0009_feedback.sql

CREATE TABLE IF NOT EXISTS `feedback` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `message` text NOT NULL,
  `screen` varchar(64) DEFAULT NULL,
  `app_version` varchar(32) DEFAULT NULL,
  `created_by` int(11) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `deleted_at` timestamp NULL DEFAULT NULL,
  `deleted_by` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_feedback_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
