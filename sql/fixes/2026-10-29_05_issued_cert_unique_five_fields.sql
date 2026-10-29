-- =============================================================================
-- 2026-10-29_05_issued_cert_unique_five_fields.sql
-- Run ONCE in phpMyAdmin (SQL tab), on the developer laptop and on the server laptop.
--
-- An issued certificate is now unique by FIVE fields:
--   certificate number, student, issue date, certificate type, "to" title.
-- Before, it was the last four only, so the same student could not get two
-- certificates of the same type, to the same party, on the same day, even with
-- different numbers.
-- Changes no rows: the new rule is looser than the old one.
-- =============================================================================

ALTER TABLE `issued_certificates`
  DROP INDEX `uq_student_cert_record`,
  ADD UNIQUE KEY `uq_student_cert_record` (`certificate_number`,`student_id`,`issue_date`,`template_type`,`to_title`);
