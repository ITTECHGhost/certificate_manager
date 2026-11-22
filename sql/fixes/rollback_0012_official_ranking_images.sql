-- Rollback of 0012_official_ranking_images: removes the table (the JPEG files stay on disk
-- in ranking_images\ and can be deleted by hand). Take a mysqldump first.
DROP TABLE IF EXISTS `official_ranking_images`;
DELETE FROM `schema_migrations` WHERE `filename` = '0012_official_ranking_images.sql';
