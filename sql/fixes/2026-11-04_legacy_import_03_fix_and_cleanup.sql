-- =============================================================================
-- Legacy import 2026-11-04 — PART 3: standardise old students, then clean up
-- Needs legacy_merge from PART 1 (still present). Back up certificate_manager first.
--
-- 1. gender 0 -> 1 (male) / 2 (female), taken from the legacy record of the same
--    student (matched on the normalised name). A name whose legacy rows disagree
--    on gender is left at 0 and listed.
-- 2. degree_level 0 -> 1 (bachelor), the value the app writes for every student.
-- 3. date_of_birth is not touched.
-- 4. Drops legacy_a, legacy_b, legacy_merge.
-- =============================================================================
USE certificate_manager;
START TRANSACTION;

-- One gender per normalised legacy name (only names whose rows all agree)
CREATE TEMPORARY TABLE tmp_legacy_gender (norm VARCHAR(200) PRIMARY KEY, g TINYINT) DEFAULT CHARSET=utf8;
INSERT INTO tmp_legacy_gender
SELECT norm, MAX(IF(gender LIKE '%ذكر%', 1, 2))
FROM legacy_merge.stg_students
WHERE TRIM(gender) <> ''
GROUP BY norm
HAVING COUNT(DISTINCT IF(gender LIKE '%ذكر%', 1, 2)) = 1;

UPDATE students s
JOIN tmp_legacy_gender t ON t.norm = legacy_merge.norm_name(s.full_name_ar)
SET s.gender = t.g
WHERE s.gender = 0;

UPDATE students SET degree_level = 1 WHERE degree_level = 0;

-- Results
SELECT gender, COUNT(*) AS students FROM students GROUP BY gender;
SELECT degree_level, COUNT(*) AS students FROM students GROUP BY degree_level;

-- Anyone still at gender 0 (fix by hand: UPDATE students SET gender = 1 or 2 WHERE id = ...)
SELECT id, full_name_ar FROM students WHERE gender = 0 ORDER BY full_name_ar;

COMMIT;
DROP TEMPORARY TABLE tmp_legacy_gender;

-- Clean up: the staging databases are no longer needed (the .sql dumps stay on disk)
DROP DATABASE legacy_merge;
DROP DATABASE legacy_a;
DROP DATABASE legacy_b;
