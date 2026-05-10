-- Disable Foreign Key Checks temporarily to speed up bulk inserts
SET FOREIGN_KEY_CHECKS = 0;

START TRANSACTION;

-- =============================================================================
-- 1. MIGRATE DEPARTMENTS
-- =============================================================================
-- Assuming legacy table is project2.departments
INSERT IGNORE INTO `certificate_manager`.`departments` (
    `name_ar`, `name_en`, `university_settings_id`
)
SELECT 
    `name_ar`, 
    `name_en`, 
    1 -- Hardcoded to 1 to link to your singleton university_settings row
FROM `project2`.`department`;


-- =============================================================================
-- 2. MIGRATE PERSONNEL (Merging 'admin' and 'signatures')
-- =============================================================================
-- Step 2A: Migrate Administrative Users (display_order = NULL)
INSERT IGNORE INTO `certificate_manager`.`personnel` (
    `name_ar`, `name_en`, `academic_title_ar`, `academic_title_en`, 
    `responsibility_ar`, `responsibility_en`, `display_order`, 
    `username`, `password_hash`, `settings_id`, `university_settings_id`
)
SELECT 
    `name`, 
    'System User',         -- Default fallback for English name
    'موظف',                -- Default title
    'Staff', 
    'إدارة النظام', 
    'System Administration', 
    NULL,                  -- Null because they are not signatories
    `username`, 
    `password`, 
    1, 
    1
FROM `project2`.`admin`;

-- Step 2B: Migrate Signatories (Extracting horizontal columns to vertical rows)
-- Note: Replace 'admin_user' and 'hash' with generic placeholders for signers if they don't log in.
INSERT IGNORE INTO `certificate_manager`.`personnel` (
    `name_ar`, `name_en`, `academic_title_ar`, `academic_title_en`, 
    `responsibility_ar`, `responsibility_en`, `display_order`, 
    `username`, `password_hash`, `personnel_role`, `settings_id`, `university_settings_id`
)
SELECT `associate_dean`, `associate_dean_en`, `sin_asst_dean`, `sin_asst_dean_en`, `pos_associate_dean`, `pos_associate_dean_en`, 1, CONCAT('signer_', id, '_1'), 'disabled', 'user', 1, 1 FROM `project2`.`signatures` UNION ALL
SELECT `doc_unit`, `doc_unit_en`, `sin_doc_unit`, `sin_doc_unit_en`, `pos_doc_unit`, `pos_doc_unit_en`, 2, CONCAT('signer_', id, '_2'), 'disabled', 'user', 1, 1 FROM `project2`.`signatures` UNION ALL
SELECT `doc_organize`, `doc_organize_en`, `sin_doc_organize`, `sin_doc_organize_en`, `pos_doc_organize`, `pos_doc_organize_en`, 3, CONCAT('signer_', id, '_3'), 'disabled', 'user', 1, 1 FROM `project2`.`signatures` UNION ALL
SELECT `assist_university`, `assist_university_en`, `sin_assist_university`, `sin_assist_university_en`, `pos_assist_university`, `pos_assist_university_en`, 4, CONCAT('signer_', id, '_4'), 'disabled', 'user', 1, 1 FROM `project2`.`signatures` UNION ALL
SELECT `dean`, `dean_en`, `sin_dean`, `sin_dean_en`, `pos_dean`, `pos_dean_en`, 5, CONCAT('signer_', id, '_5'), 'disabled', 'user', 1, 1 FROM `project2`.`signatures` UNION ALL
SELECT `sign_m`, `sign_m_en`, `sin_sign_m`, `sin_sign_m_en`, `pos_sign_m`, `pos_sign_m_en`, 6, CONCAT('signer_', id, '_6'), 'disabled', 'user', 1, 1 FROM `project2`.`signatures`;


-- =============================================================================
-- 3. MIGRATE COURSES
-- =============================================================================

-- Part A: Migrate Semester System Courses (from subjects_140)
INSERT IGNORE INTO `certificate_manager`.`courses` (
    `name_ar`, `name_en`, `credit_hours`, `department_id`, `stage_number`, `study_system_id`, `is_shared`
)
SELECT 
    `name_ar`, `name_en`, `units`, 
    CASE 
        WHEN `dep` LIKE '%علوم الحاسوب%' THEN 2 
        WHEN `dep` LIKE '%نظم المعلومات الحاسوبية%' THEN 1 
        ELSE 1 -- Safety fallback
    END AS `department_id`,
    CAST(SUBSTRING(`code`, 3, 1) AS UNSIGNED), -- Extracts '1' from CS101
    2, -- 2 for Semester System
    1  -- is_shared defaults to 1
FROM `project2`.`subjects_140`;


-- Part B: Migrate Annual System Courses (from subjects_q)
INSERT INTO `certificate_manager`.`courses` (
    `name_ar`, `name_en`, `credit_hours`, `department_id`, `stage_number`, `study_system_id`, `is_shared`
)
SELECT 
    `name_ar`, `name_en`, `units`, 
    CASE 
        WHEN `dep` LIKE '%علوم الحاسوب%' THEN 2 
        WHEN `dep` LIKE '%نظم المعلومات الحاسوبية%' THEN 1 
        ELSE 1 -- Safety fallback
    END AS `department_id`,
    -- Fix: Pattern match the Arabic words to extract the stage integer
    CASE 
        WHEN `requirment` LIKE '%اولى%' THEN 1
        WHEN `requirment` LIKE '%ثانية%' THEN 2
        WHEN `requirment` LIKE '%ثالثة%' THEN 3
        WHEN `requirment` LIKE '%رابعة%' THEN 4
        ELSE 1 -- Safety fallback
    END AS `stage_number`,
    1, -- 1 for Annual System
    1  -- is_shared defaults to 1
FROM `project2`.`subjects_q`;

-- =============================================================================
-- 4. MIGRATE GRADUATION ORDERS
-- =============================================================================
INSERT INTO `certificate_manager`.`graduation_orders` (
    `order_number`, 
    `order_date`, 
    `department_id`, 
    `study_system_id`, 
    `admission_year`, 
    `graduation_semester`, 
    `num_students`
)
SELECT 
    `order_university`, 
    `date`, 
    CASE 
        WHEN `dep` LIKE '%علوم الحاسوب%' THEN 2 
        WHEN `dep` LIKE '%نظم المعلومات%' THEN 1 
        ELSE 1 
    END,
    CASE 
        WHEN `study` LIKE '%صباحي%' THEN 'Morning'
        WHEN `study` LIKE '%مسائي%' THEN 'Evening'
        ELSE 'Morning' 
    END as `study_type`
    CASE 
        WHEN `year_study` > 2020 THEN 2 -- semester system
        ELSE 1 -- annual system
    END as `study_system_name`
    CASE 
        WHEN `study_type` = 'Morning' AND `study_system_name` = 2 THEN 2
        WHEN `study_type` = 'Evening' AND `study_system_name` = 2 THEN 4
        WHEN `study_type` = 'Morning' AND `study_system_name` = 1 THEN 1
        WHEN `study_type` = 'Evening' AND `study_system_name` = 1 THEN 3
    END as `study_type_id`
    (SELECT `certificate_manager`.`study_system_id`.`id` FROM `certificate_manager`.`study_system_id` WHERE
     `certificate_manager`.`study_system_id`.`id` = `study_type_id`), -- where id = 2 mean semester system and study type is morning or evening based on order_university.study
    `year_study`, 
    -- Mapping legacy Arabic semesters to ENUM ('first', 'second')
    CASE 
        WHEN `graduation_semester` LIKE '%الاول%' THEN 'first' 
        WHEN `graduation_semester` LIKE '%الثاني%' THEN 'second'
        WHEN `graduation_semester` LIKE '%الصيفي%' THEN 'summer' 
        ELSE 'first' 
    END,
    `num_students`
FROM `project2`.`order_university`;

-- =============================================================================
-- 5. MIGRATE STUDENTS
-- =============================================================================
-- Disable foreign keys temporarily to prevent birthplace/nationality lookup errors
SET FOREIGN_KEY_CHECKS = 0;

INSERT INTO `certificate_manager`.`students` (
    `full_name_ar`, 
    `full_name_en`, 
    `gender`, 
    `study_system_id`, 
    `sequence_number`,
    `postgraduation_number`,
    `date_of_birth`, -- get from birth_date column
    `birthplace_id`,
    `birthplace_other`,
    `nationality_id`,
    `department_id`, 
    `order_id`, 
    `admission_year`, 
    `summer_training_data`,
    `average`
)
-- Part A: Semester System Students (students_140)
SELECT 
    `name` AS `full_name_ar`, 
    `name_en` AS `full_name_en`, 
    CASE 
        WHEN `gender` LIKE '%ذكر%' THEN 'male' 
        ELSE 'female' 
    END AS `gender`,
    (SELECT `certificate_manager`.`study_system_id`.`id` FROM `certificate_manager`.`study_system_id` WHERE
     `certificate_manager`.`study_system_id`.`study_type_day` = `s140`.`study` AND 
     `certificate_manager`.`study_system_id`.`id` = 2) AS `study_system_id`, -- where id = 2 mean semester system and study type is morning or evening based on s140.study
    `sequence` as `sequence_number`, -- Student_Sequence
    `num_student` as `postgraduation_number`, -- postgraduation_number
    CASE 
        WHEN `graduation_semester` LIKE '%الاول%' THEN 'first' 
        WHEN `graduation_semester` LIKE '%الثاني%' THEN 'second'
        WHEN `graduation_semester` LIKE '%الصيفي%' THEN 'summer' 
        ELSE 'first' 
    END AS `graduation_semester`,
    -- get order id from graduation_orders
    (SELECT `certificate_manager`.`graduation_orders`.`id` FROM `certificate_manager`.`graduation_orders` WHERE
     `certificate_manager`.`graduation_orders`.`order_number` = `s140`.`order_university` AND
     `certificate_manager`.`graduation_orders`.`order_date` = `s140`.`date` AND
     `certificate_manager`.`graduation_orders`.`department_id` = `department_id` AND 
     `certificate_manager`.`graduation_orders`.`study_type` = `study_type` AND
     `certificate_manager`.`graduation_orders`.`graduation_semester` = `graduation_semester`
      LIMIT 1) as `order_id`,
    (SELECT `id` FROM `certificate_manager`.`governorates` WHERE `name_en` = `s140`.`birthplace_en` LIMIT 1),
    (SELECT `id` FROM `certificate_manager`.`countries` WHERE `name_en` = `s140`.`nationality_en` LIMIT 1),
    CASE  
        WHEN (SELECT `id` FROM `certificate_manager`.`countries` WHERE 
            `name_en` = `s140`.`nationality_en` LIMIT 1) = 1 THEN `birthplace_other` 
        ELSE NULL 
    END AS `birthplace_other`,
    CASE 
        WHEN `department` LIKE '%علوم الحاسوب%' THEN 2 
        WHEN `department` LIKE '%نظم المعلومات%' THEN 1 
        ELSE 1 
    END AS `department_id`,
    (SELECT `id` FROM `certificate_manager`.`countries` WHERE `name_en` = `s140`.`nationality_en` LIMIT 1) as `nationality_id`,
    `graduation_year` - 4 AS `admission_year`,
    `graduation_year` - 1 AS `summer_training_data`,
    `average`
FROM `project2`.`students_140` AS `s140`

UNION ALL

-- Part B: Annual System Students (students_q)
SELECT 
    `name` AS `full_name_ar`, 
    `name_en` AS `full_name_en`, 
    CASE WHEN `gender` LIKE '%ذكر%' THEN 'male' ELSE 'female' END,
    CASE 
        WHEN `department` LIKE '%علوم الحاسوب%' THEN 2 
        WHEN `department` LIKE '%نظم المعلومات%' THEN 1 
        ELSE 1 
    END AS `department_id`,
    1 AS `study_system_id`, -- 1 for Annual System
    (SELECT `id` FROM `certificate_manager`.`graduation_orders` WHERE `order_number` = `sq`.`order_university` LIMIT 1),
    `graduation_year` - 4,
    CASE WHEN `study` LIKE '%الصباحية%' THEN 'morning' ELSE 'evening' END,
    `average`,
    (SELECT `id` FROM `certificate_manager`.`governorates` WHERE `name_en` = `sq`.`birthplace_en` LIMIT 1),
    (SELECT `id` FROM `certificate_manager`.`countries` WHERE `name_en` = `sq`.`nationality_en` LIMIT 1)
FROM `project2`.`students_q` AS `sq`;

SET FOREIGN_KEY_CHECKS = 1;


-- =============================================================================
-- 6. MIGRATE ACADEMIC PERIODS & ENROLLMENTS
-- =============================================================================
INSERT INTO `certificate_manager`.`academic_periods` (
    `id`, `student_id`, `academic_year`, `study_system_id`, `stage_number`, `passed_round`
)
SELECT `id`, `student_id`, `year`, `system_id`, `stage`, `round`
FROM `project2`.`academic_periods`;

INSERT INTO `certificate_manager`.`enrollments` (
    `id`, `period_id`, `course_id`, `score`, `is_second_round`
)
SELECT `id`, `period_id`, `course_id`, `score`, `second_round`
FROM `project2`.`enrollments`;


-- Commit the transaction if all inserts succeed
COMMIT;

-- Re-enable Foreign Key Checks to secure the database
SET FOREIGN_KEY_CHECKS = 1;