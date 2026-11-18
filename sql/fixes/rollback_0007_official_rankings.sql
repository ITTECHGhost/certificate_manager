-- Rollback of 0007_official_rankings: removes the official ranking lists.
-- Take a mysqldump first; the lists entered after 0007 are lost.
DROP TABLE IF EXISTS `official_ranking_entries`;
DROP TABLE IF EXISTS `official_rankings`;
DELETE FROM `schema_migrations` WHERE `filename` = '0007_official_rankings.sql';
