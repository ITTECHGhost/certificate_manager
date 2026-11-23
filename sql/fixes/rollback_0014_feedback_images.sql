-- Rollback of 0014_feedback_images: removes the table (the JPEG files stay on disk in
-- feedback_images\ and can be deleted by hand). Take a mysqldump first.
DROP TABLE IF EXISTS `feedback_images`;
DELETE FROM `schema_migrations` WHERE `filename` = '0014_feedback_images.sql';
