-- 0007: official ranking lists (قوائم الترتيب الرسمية).
--   The college issues an order with each ranking list; the documents unit wants the
--   certificate rank taken from that paper, not computed:
--     list_type 'jobs'    (للتعيين)          : department + study type + exam round
--     list_type 'masters' (للدراسات العليا) : the whole department
--   One header row per order, one entry per student in the order's own sequence.
-- Rollback: sql/fixes/rollback_0007_official_rankings.sql (drops both tables).

CREATE TABLE IF NOT EXISTS `official_rankings` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `list_type` varchar(16) NOT NULL,
  `title` varchar(255) DEFAULT NULL,
  `order_number` varchar(64) DEFAULT NULL,
  `order_date` date DEFAULT NULL,
  `department_id` int(11) DEFAULT NULL,
  `study_type` varchar(16) DEFAULT NULL,
  `exam_round` varchar(8) DEFAULT NULL,
  `academic_year` varchar(16) DEFAULT NULL,
  `created_by` int(11) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_official_rankings_dept` (`department_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS `official_ranking_entries` (
  `ranking_id` int(11) NOT NULL,
  `position` int(11) NOT NULL,
  `student_id` int(11) DEFAULT NULL,
  `name_written` varchar(255) DEFAULT NULL,
  `average` decimal(12,8) DEFAULT NULL,
  PRIMARY KEY (`ranking_id`, `position`),
  KEY `ix_official_ranking_entries_student` (`student_id`),
  CONSTRAINT `fk_official_ranking_entries_list` FOREIGN KEY (`ranking_id`)
    REFERENCES `official_rankings` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
