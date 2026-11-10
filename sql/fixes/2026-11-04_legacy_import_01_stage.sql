-- =============================================================================
-- Legacy import 2026-11-04 — PART 1: stage and review (changes nothing live)
--
-- Before running this file, load the two legacy dumps into their own databases:
--   mysql -u root -p -e "CREATE DATABASE legacy_a CHARACTER SET utf8; CREATE DATABASE legacy_b CHARACTER SET utf8;"
--   mysql -u root -p --default-character-set=utf8 legacy_a < "old/sql_dumps/project 4112026.sql"
--   mysql -u root -p --default-character-set=utf8 legacy_b < "old/sql_dumps/project2 (4112026).sql"
--
-- legacy_a = "project 4112026.sql"      (PC A)
-- legacy_b = "project2 (4112026).sql"   (PC B)
-- Both copies started from the same June state and then grew apart, so the
-- same legacy id can be two different students. Nothing here keys on legacy id.
-- =============================================================================

DROP DATABASE IF EXISTS legacy_merge;
CREATE DATABASE legacy_merge CHARACTER SET utf8 COLLATE utf8_general_ci;
USE legacy_merge;

-- Name normaliser: drops spaces and stray Latin letters, unifies ة/ه, أ/إ/آ/ا, ى/ي,
-- and "عبدلله" / "عبدالله". Used only to MATCH names; the stored name is untouched.
DELIMITER $$
CREATE FUNCTION norm_name(s VARCHAR(200)) RETURNS VARCHAR(200) CHARSET utf8
DETERMINISTIC NO SQL
BEGIN
  DECLARE r VARCHAR(200) DEFAULT LOWER(TRIM(IFNULL(s, '')));
  DECLARE i INT DEFAULT 97;               -- 'a'
  WHILE i <= 122 DO                       -- 'z'
    SET r = REPLACE(r, CHAR(i), '');
    SET i = i + 1;
  END WHILE;
  SET r = REPLACE(r, ' ', '');
  SET r = REPLACE(r, 'ة', 'ه');
  SET r = REPLACE(r, 'أ', 'ا');
  SET r = REPLACE(r, 'إ', 'ا');
  SET r = REPLACE(r, 'آ', 'ا');
  SET r = REPLACE(r, 'ى', 'ي');
  SET r = REPLACE(r, 'عبدلله', 'عبدالله');
  RETURN r;
END$$
DELIMITER ;

-- -----------------------------------------------------------------------------
-- 1. Every legacy student row from both PCs
-- -----------------------------------------------------------------------------
CREATE TABLE stg_students (
  stg_id INT AUTO_INCREMENT PRIMARY KEY,
  src CHAR(1), src_table VARCHAR(20), legacy_id INT,
  name VARCHAR(150), name_en VARCHAR(150), gender VARCHAR(25), study VARCHAR(50),
  department VARCHAR(50), graduation_year VARCHAR(25), graduation_semester VARCHAR(25),
  average VARCHAR(25), sequence VARCHAR(25), num_students VARCHAR(100),
  order_university VARCHAR(60), order_date VARCHAR(25),
  nationality_en VARCHAR(50), birthplace_en VARCHAR(50),
  study_system_id INT, norm VARCHAR(200),
  status VARCHAR(20) DEFAULT 'new',       -- new | in_live | duplicate | review
  note VARCHAR(255)
) DEFAULT CHARSET=utf8;

INSERT INTO stg_students (src, src_table, legacy_id, name, name_en, gender, study, department,
  graduation_year, graduation_semester, average, sequence, num_students, order_university,
  order_date, nationality_en, birthplace_en, study_system_id)
SELECT 'A','students_q',  id, TRIM(name), TRIM(name_en), gender, study, department, graduation_year, `role`, average, sequence, num_students, TRIM(order_university), `date`, nationality_en, birthplace_en, 1 FROM legacy_a.students_q
UNION ALL
SELECT 'A','students_140',id, TRIM(name), TRIM(name_en), gender, study, department, graduation_year, graduation_semester, average, sequence, num_students, TRIM(order_university), `date`, nationality_en, birthplace_en, 2 FROM legacy_a.students_140
UNION ALL
SELECT 'B','students_q',  id, TRIM(name), TRIM(name_en), gender, study, department, graduation_year, `role`, average, sequence, num_students, TRIM(order_university), `date`, nationality_en, birthplace_en, 1 FROM legacy_b.students_q
UNION ALL
SELECT 'B','students_140',id, TRIM(name), TRIM(name_en), gender, study, department, graduation_year, graduation_semester, average, sequence, num_students, TRIM(order_university), `date`, nationality_en, birthplace_en, 2 FROM legacy_b.students_140;

UPDATE stg_students SET norm = norm_name(name);
CREATE INDEX ix_norm ON stg_students (norm, order_university);

-- -----------------------------------------------------------------------------
-- 2. Already in the live database? (normalised name, any order)
-- -----------------------------------------------------------------------------
CREATE TABLE live_norm (norm VARCHAR(200), student_id INT, KEY (norm)) DEFAULT CHARSET=utf8;
INSERT INTO live_norm SELECT norm_name(full_name_ar), id FROM certificate_manager.students;

UPDATE stg_students s JOIN live_norm l ON l.norm = s.norm
SET s.status = 'in_live', s.note = CONCAT('live student id ', l.student_id);

-- -----------------------------------------------------------------------------
-- 3. Same student on both PCs (or twice on one): keep one row per
--    (normalised name, order). Prefer the row that has an English name, then PC A.
-- -----------------------------------------------------------------------------
UPDATE stg_students s
JOIN (
  SELECT norm, order_university,
         SUBSTRING_INDEX(GROUP_CONCAT(stg_id ORDER BY (name_en = ''), src, stg_id), ',', 1) + 0 AS keep_id
  FROM stg_students WHERE status = 'new'
  GROUP BY norm, order_university
) k ON k.norm = s.norm AND k.order_university = s.order_university
SET s.status = 'duplicate', s.note = CONCAT('same as stg_id ', k.keep_id)
WHERE s.status = 'new' AND s.stg_id <> k.keep_id;

-- -----------------------------------------------------------------------------
-- 4. Rows held back for your decision (see the explanation). Edit freely:
--    UPDATE stg_students SET status='new' WHERE stg_id = ...;   -- to import one
-- -----------------------------------------------------------------------------
UPDATE stg_students SET status = 'review', note = 'name variant of live "محمد علي طه عبدالامير حسين" (missing طه) - test entry?'
WHERE status = 'new' AND norm = norm_name('محمدعلي عبدالامير حسين');

UPDATE stg_students SET status = 'review', note = 'two near-identical names in the same order - one may be a typo'
WHERE status = 'new' AND norm IN (norm_name('زينب مصطفى سلمان'), norm_name('زينب مصطفى سلمان خنفر'),
                                  norm_name('ميثاق شمخي عبد العباس داغر'), norm_name('ميثاق شمخي عبد العباس محمد'));

-- -----------------------------------------------------------------------------
-- 5. Graduation orders found in either PC
-- -----------------------------------------------------------------------------
CREATE TABLE stg_orders (
  order_number VARCHAR(60), dep VARCHAR(50), study VARCHAR(50), department_id INT, study_type VARCHAR(10),
  year_study VARCHAR(10), semester VARCHAR(10), order_date VARCHAR(25), num_students VARCHAR(20),
  in_live TINYINT DEFAULT 0, PRIMARY KEY (order_number, department_id, study_type)
) DEFAULT CHARSET=utf8;

INSERT IGNORE INTO stg_orders (order_number, dep, study, department_id, study_type, year_study, semester, order_date, num_students)
SELECT TRIM(order_university), dep, study,
       IF(dep LIKE '%نظم المعلومات%', 1, 2),
       IF(study LIKE '%المسائي%', 'evening', 'morning'),
       year_study,
       CASE WHEN CONCAT(graduation_semester, role) LIKE '%الصيفي%' THEN 'summer'
            WHEN CONCAT(graduation_semester, role) LIKE '%الثاني%' THEN 'second'
            ELSE 'first' END,
       `date`, num_students
FROM (SELECT * FROM legacy_a.order_university UNION ALL SELECT * FROM legacy_b.order_university) o;

UPDATE stg_orders s JOIN certificate_manager.graduation_orders g
  ON g.order_number = s.order_number AND g.department_id = s.department_id
 AND (g.study_type = s.study_type OR g.study_type IS NULL)
SET s.in_live = 1;

-- =============================================================================
-- REVIEW — read these results before running PART 2
-- =============================================================================
SELECT status, src, COUNT(*) AS n FROM stg_students GROUP BY status, src ORDER BY status, src;

-- Orders that PART 2 will create
SELECT * FROM stg_orders WHERE in_live = 0;

-- Students that PART 2 will create
SELECT stg_id, src, src_table, legacy_id, name, name_en, department, study, order_university, average
FROM stg_students WHERE status = 'new' ORDER BY order_university, name;

-- Students held back for your decision
SELECT stg_id, src, name, order_university, note FROM stg_students WHERE status = 'review';

-- New students whose order is in neither the live DB nor the dumps (would get order_id NULL)
SELECT s.stg_id, s.name, s.order_university FROM stg_students s
LEFT JOIN stg_orders o ON o.order_number = s.order_university
WHERE s.status = 'new' AND o.order_number IS NULL;
