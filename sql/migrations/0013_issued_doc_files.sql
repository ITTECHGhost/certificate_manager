-- 0013: archive files of «سجل الوثائق الصادرة».
--   kind 'draft'  = the editable Word file, saved at each print until the record is archived.
--   kind 'signed' = the FINAL printed, signed, stamped copy. Archiving it sets issue_date to that
--   day, drops the drafts and locks the record (no edit / reprint).
--   Files on the server: issue_archive\<year>\<sha256>.<pdf|jpg|png>; the table keeps the row.
--   Replace = a NEW row with supersedes_id (old versions are kept). Soft delete only.
-- Rollback: sql/fixes/rollback_0013_issued_doc_files.sql
--   No foreign key on purpose: deleting an issued_certificates row keeps its archive rows.
-- NOTE: student_holds moves to the next free number (0014).

CREATE TABLE IF NOT EXISTS `issued_document_files` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `certificate_id` int(11) NOT NULL,
  `kind` varchar(16) NOT NULL DEFAULT 'signed',
  `sha256` char(64) NOT NULL,
  `file_name` varchar(100) NOT NULL,
  `doc_year` int(11) NOT NULL,
  `supersedes_id` int(11) DEFAULT NULL,
  `source_name` varchar(255) DEFAULT NULL,
  `created_by` int(11) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `deleted_at` timestamp NULL DEFAULT NULL,
  `deleted_by` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_issued_document_files_cert` (`certificate_id`, `kind`),
  KEY `ix_issued_document_files_sha` (`sha256`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Print date, kept apart from the issue date (user decision 2026-11-22):
--   printed_at = last time the draft was printed/saved; issue_date = the day the signed copy
--   was archived (set by the API). Old records start with printed_at = issue_date.
ALTER TABLE `issued_certificates` ADD COLUMN `printed_at` datetime NULL DEFAULT NULL;
UPDATE `issued_certificates` SET `printed_at` = `issue_date` WHERE `printed_at` IS NULL;
