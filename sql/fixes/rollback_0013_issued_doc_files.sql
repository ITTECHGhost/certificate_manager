-- Rollback of 0013_issued_doc_files: removes the table (files stay on disk in issue_archive\).
-- Take a mysqldump first.
DROP TABLE IF EXISTS `issued_document_files`;
ALTER TABLE `issued_certificates` DROP COLUMN `printed_at`;
DELETE FROM `schema_migrations` WHERE `filename` = '0013_issued_doc_files.sql';
