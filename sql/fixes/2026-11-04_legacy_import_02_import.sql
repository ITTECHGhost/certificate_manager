-- =============================================================================
-- Legacy import 2026-11-04 — PART 2: write to certificate_manager
-- Run only after PART 1 and after reviewing its result sets.
-- Back up first:
--   mysqldump -u root -p --routines --triggers certificate_manager > "old/sql_dumps/backup_before_legacy_import_2026_11_04.sql"
-- =============================================================================
USE certificate_manager;
START TRANSACTION;

-- 1. Missing graduation orders
--    study_system_id: 1 = annual/morning, 3 = annual/evening (the new legacy
--    students in these orders are annual-system students).
INSERT INTO graduation_orders
  (order_number, order_date, department_id, graduation_semester, num_students,
   graduation_year, study_system_id, study_type, notes)
SELECT o.order_number,
       STR_TO_DATE(o.order_date, '%Y-%m-%d'),
       o.department_id,
       o.semester,
       CAST(o.num_students AS UNSIGNED),
       CAST(o.year_study AS UNSIGNED),
       IF(o.study_type = 'evening', 3, 1),
       o.study_type,
       'legacy import 2026-11-04'
FROM legacy_merge.stg_orders o
WHERE o.in_live = 0;

-- 2. New students
INSERT INTO students
  (full_name_ar, full_name_en, gender, nationality_id, date_of_birth, birthplace_id,
   study_system_id, degree_level, department_id, admission_year, graduation_date,
   graduation_semester, average, order_id, sequence_number, postgraduation_number,
   summer_training_data)
SELECT s.name,
       IFNULL(s.name_en, ''),
       IF(s.gender LIKE '%ذكر%', 1, 2),                       -- 1 male, 2 female (app convention)
       COALESCE((SELECT c.id FROM countries c
                 WHERE c.name_en IN (s.nationality_en, IF(s.nationality_en = 'Iraqi', 'Iraq', s.nationality_en))
                 LIMIT 1), 274),
       NULL,                                                  -- legacy has no birth date
       COALESCE((SELECT gv.id FROM governorates gv WHERE gv.name_en = s.birthplace_en LIMIT 1), 2),
       s.study_system_id,
       1,                                                     -- bachelor
       IF(s.department LIKE '%نظم المعلومات%', 1, 2),
       CAST(CAST(s.graduation_year AS UNSIGNED) - 4 AS CHAR), -- same rule as the earlier migration
       STR_TO_DATE(s.order_date, '%Y-%m-%d'),
       CASE WHEN s.graduation_semester LIKE '%الصيفي%' THEN 'summer'
            WHEN s.graduation_semester LIKE '%الثاني%' THEN 'second'
            ELSE 'first' END,
       CAST(s.average AS DECIMAL(6,3)),
       (SELECT g.id FROM graduation_orders g
         WHERE g.order_number = s.order_university
           AND g.department_id = IF(s.department LIKE '%نظم المعلومات%', 1, 2)
         ORDER BY (g.study_type = IF(s.study LIKE '%المسائي%', 'evening', 'morning')) DESC,
                  (g.study_system_id IN (s.study_system_id, s.study_system_id + 2)) DESC, g.id
         LIMIT 1),
       NULLIF(CAST(s.sequence AS UNSIGNED), 0),
       NULLIF(CAST(s.num_students AS UNSIGNED), 0),
       CAST(CAST(s.graduation_year AS UNSIGNED) - 1 AS CHAR)  -- same rule as the earlier migration
FROM legacy_merge.stg_students s
WHERE s.status = 'new';

-- 3. Check, then COMMIT (or ROLLBACK if anything looks wrong)
SELECT COUNT(*) AS orders_added   FROM graduation_orders WHERE notes = 'legacy import 2026-11-04';
SELECT COUNT(*) AS students_added FROM students s
  JOIN legacy_merge.stg_students t ON t.name = s.full_name_ar AND t.status = 'new';
SELECT COUNT(*) AS students_without_order FROM students s
  JOIN legacy_merge.stg_students t ON t.name = s.full_name_ar AND t.status = 'new'
 WHERE s.order_id IS NULL;

COMMIT;

-- Afterwards, when you are happy:
-- DROP DATABASE legacy_merge; DROP DATABASE legacy_a; DROP DATABASE legacy_b;
