-- 0013: archive files of «سجل الوثائق الصادرة»: the FINAL document only (printed, signed, stamped,
--   with its issued number and date). kind stays for future use; the API accepts 'signed' only.
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
