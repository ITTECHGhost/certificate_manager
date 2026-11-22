-- Rollback of 0009_feedback: removes the feedback table.
-- Take a mysqldump first; the notes entered after 0009 are lost.
DROP TABLE IF EXISTS `feedback`;
DELETE FROM `schema_migrations` WHERE `filename` = '0009_feedback.sql';
