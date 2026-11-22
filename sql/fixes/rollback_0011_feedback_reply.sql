-- Rollback of 0011_feedback_reply: removes the reply/status columns (the notes stay).
-- Take a mysqldump first; replies written after 0011 are lost.
ALTER TABLE `feedback`
  DROP COLUMN `edited_at`,
  DROP COLUMN `replied_at`,
  DROP COLUMN `replied_by`,
  DROP COLUMN `reply`,
  DROP COLUMN `status`;
DELETE FROM `schema_migrations` WHERE `filename` = '0011_feedback_reply.sql';
