-- Disable Foreign Key Checks temporarily to speed up bulk inserts
SET
    FOREIGN_KEY_CHECKS = 0;

START TRANSACTION;

-- =============================================================================
-- 1. MIGRATE DEPARTMENTS (Cleaned: Only 2 Departments)
-- =============================================================================
INSERT IGNORE INTO `certificate_manager`.`departments` (
    `id`,
    `name_ar`,
    `name_en`,
    `university_settings_id`
)
VALUES
    (
        1,
        'نظم المعلومات الحاسوبية',
        'Computer Information Systems',
        1
    ),
    (2, 'علوم الحاسوب', 'Computer Science', 1);

-- =============================================================================
-- 2. MIGRATE PERSONNEL
-- =============================================================================
-- Step 2A: Migrate Administrative Users (display_order = 0)
INSERT IGNORE INTO `certificate_manager`.`personnel` (
    `name_ar`,
    `name_en`,
    `academic_title_ar`,
    `academic_title_en`,
    `responsibility_ar`,
    `responsibility_en`,
    `display_order`,
    `username`,
    `password_hash`,
    `personnel_role`,
    `settings_id`,
    `university_settings_id`
)
SELECT
    `name`,
    'System User',
    'موظف',
    'Staff',
    'إدارة النظام',
    'System Administration',
    0,
    `username`,
    `password`,
    CASE
        WHEN `terms` LIKE '%مسؤول%' THEN 'admin'
        ELSE 'user'
    END,
    1,
    1
FROM
    `project2`.`admin`;

-- Step 2B: Migrate Signatories
INSERT IGNORE INTO `certificate_manager`.`personnel` (
    `name_ar`,
    `name_en`,
    `academic_title_ar`,
    `academic_title_en`,
    `responsibility_ar`,
    `responsibility_en`,
    `display_order`,
    `username`,
    `password_hash`,
    `personnel_role`,
    `settings_id`,
    `university_settings_id`
)
SELECT
    `associate_dean`,
    `associate_dean_en`,
    `sin_asst_dean`,
    `sin_asst_dean_en`,
    `pos_associate_dean`,
    `pos_associate_dean_en`,
    1,
    CONCAT ('signer_', id, '_1'),
    'disabled',
    'user',
    1,
    1
FROM
    `project2`.`signatures`
UNION ALL
SELECT
    `doc_unit`,
    `doc_unit_en`,
    `sin_doc_unit`,
    `sin_doc_unit_en`,
    `pos_doc_unit`,
    `pos_doc_unit_en`,
    2,
    CONCAT ('signer_', id, '_2'),
    'disabled',
    'user',
    1,
    1
FROM
    `project2`.`signatures`
UNION ALL
SELECT
    `doc_organize`,
    `doc_organize_en`,
    `sin_doc_organize`,
    `sin_doc_organize_en`,
    `pos_doc_organize`,
    `pos_doc_organize_en`,
    3,
    CONCAT ('signer_', id, '_3'),
    'disabled',
    'user',
    1,
    1
FROM
    `project2`.`signatures`
UNION ALL
SELECT
    `assist_university`,
    `assist_university_en`,
    `sin_assist_university`,
    `sin_assist_university_en`,
    `pos_assist_university`,
    `pos_assist_university_en`,
    4,
    CONCAT ('signer_', id, '_4'),
    'disabled',
    'user',
    1,
    1
FROM
    `project2`.`signatures`
UNION ALL
SELECT
    `dean`,
    `dean_en`,
    `sin_dean`,
    `sin_dean_en`,
    `pos_dean`,
    `pos_dean_en`,
    5,
    CONCAT ('signer_', id, '_5'),
    'disabled',
    'user',
    1,
    1
FROM
    `project2`.`signatures`
UNION ALL
SELECT
    `sign_m`,
    `sign_m_en`,
    `sin_sign_m`,
    `sin_sign_m_en`,
    `pos_sign_m`,
    `pos_sign_m_en`,
    6,
    CONCAT ('signer_', id, '_6'),
    'disabled',
    'user',
    1,
    1
FROM
    `project2`.`signatures`;

-- =============================================================================
-- 3. MIGRATE COURSES (department_id = NULL for shared courses)
-- =============================================================================
-- Part A: Semester System Courses
INSERT IGNORE INTO `certificate_manager`.`courses` (
    `name_ar`,
    `name_en`,
    `credit_hours`,
    `department_id`,
    `stage_number`
)
SELECT
    `name_ar`,
    `name_en`,
    CAST(`units` AS UNSIGNED),
    CASE
        WHEN `dep` LIKE '%علوم الحاسوب%' THEN 2
        WHEN `dep` LIKE '%نظم المعلومات%' THEN 1
        ELSE NULL -- NULL represents a shared college requirement
    END,
    CAST(SUBSTRING(`code`, 3, 1) AS UNSIGNED)
FROM
    `project2`.`subjects_140`;

-- Part B: Annual System Courses
INSERT IGNORE INTO `certificate_manager`.`courses` (
    `name_ar`,
    `name_en`,
    `credit_hours`,
    `department_id`,
    `stage_number`
)
SELECT
    `name_ar`,
    `name_en`,
    CAST(`units` AS UNSIGNED),
    CASE
        WHEN `dep` LIKE '%علوم الحاسوب%' THEN 2
        WHEN `dep` LIKE '%نظم المعلومات%' THEN 1
        ELSE NULL
    END,
    CASE
        WHEN `requirment` LIKE '%اولى%' THEN 1
        WHEN `requirment` LIKE '%ثانية%' THEN 2
        WHEN `requirment` LIKE '%ثالثة%' THEN 3
        WHEN `requirment` LIKE '%رابعة%' THEN 4
        ELSE 1
    END
FROM
    `project2`.`subjects_q`;

COMMIT;

SET
    FOREIGN_KEY_CHECKS = 1;

-------------------------------------------------------------------------------------------------
SET
    FOREIGN_KEY_CHECKS = 0;

START TRANSACTION;

-- =============================================================================
-- 4. MIGRATE GRADUATION ORDERS (FIXED: Using Structural Column Matching)
-- =============================================================================
INSERT IGNORE INTO `certificate_manager`.`graduation_orders` (
    `order_number`,
    `order_date`,
    `department_id`,
    `graduation_semester`,
    `num_students`,
    `study_system_id`
)
SELECT
    `order_university`,
    `date` AS order_date,
    CASE
        WHEN `dep` LIKE '%علوم الحاسوب%' THEN 2
        WHEN `dep` LIKE '%نظم المعلومات%' THEN 1
        ELSE 1
    END AS department_id,
    -- Unifies 'graduation_semester' and 'role' into our clean enum values
    CASE
        WHEN `graduation_semester` LIKE '%الاول%'
        OR `role` LIKE '%الاول%' THEN 'first'
        WHEN `graduation_semester` LIKE '%الثاني%'
        OR `role` LIKE '%الثاني%' THEN 'second'
        WHEN `graduation_semester` LIKE '%الصيفي%' THEN 'summer'
        ELSE 'first'
    END AS graduation_semester,
    CAST(`num_students` AS UNSIGNED),
    -- Your Direct Structural Rule mapping logic:
    CASE
        WHEN `study` LIKE '%صباح%'
        AND (
            `graduation_semester` IS NULL
            OR `graduation_semester` = ''
        ) THEN 1 -- Annual Morning
        WHEN `study` LIKE '%مساء%'
        AND (
            `graduation_semester` IS NULL
            OR `graduation_semester` = ''
        ) THEN 3 -- Annual Evening
        WHEN `study` LIKE '%صباح%'
        AND (
            `graduation_semester` IS NOT NULL
            AND `graduation_semester` != ''
        ) THEN 2 -- Semester Morning
        WHEN `study` LIKE '%مساء%'
        AND (
            `graduation_semester` IS NOT NULL
            AND `graduation_semester` != ''
        ) THEN 4 -- Semester Evening
        ELSE 1
    END AS study_system_id
FROM
    `project2`.`order_university` AS `ou`;

COMMIT;

SET
    FOREIGN_KEY_CHECKS = 1;

-------------------------------------------------------------------------------------------------
SET
    FOREIGN_KEY_CHECKS = 0;

START TRANSACTION;

-- =============================================================================
-- 5. MIGRATE STUDENTS
-- =============================================================================
-- Part A: Semester System Students (students_140)
INSERT IGNORE INTO `certificate_manager`.`students` (
    `full_name_ar`,
    `full_name_en`,
    `gender`,
    `sequence_number`,
    `postgraduation_number`,
    `date_of_birth`,
    `birthplace_id`,
    `birthplace_other`,
    `nationality_id`,
    `department_id`,
    `study_system_id`,
    `order_id`,
    `admission_year`,
    `summer_training_data`,
    `average`
)
SELECT
    `name`,
    `name_en`,
    CASE
        WHEN `gender` LIKE '%ذكر%' THEN 'M'
        ELSE 'F'
    END,
    CAST(`sequence` AS UNSIGNED),
    CAST(`num_students` AS UNSIGNED),
    STR_TO_DATE (
        CONCAT (
            CAST(`graduation_year` AS UNSIGNED) - 22,
            '-01-01'
        ),
        '%Y-%m-%d'
    ),
    COALESCE(
        (
            SELECT
                `id`
            FROM
                `certificate_manager`.`governorates`
            WHERE
                `name_en` = `s140`.`birthplace_en`
            LIMIT
                1
        ),
        2
    ),
    NULL,
    COALESCE(
        (
            SELECT
                `id`
            FROM
                `certificate_manager`.`countries`
            WHERE
                `name_en` = `s140`.`nationality_en`
            LIMIT
                1
        ),
        274
    ),
    CASE
        WHEN `department` LIKE '%علوم الحاسوب%' THEN 2
        WHEN `department` LIKE '%نظم المعلومات%' THEN 1
        ELSE 1
    END AS `department_id`,
    CASE
        WHEN `study` LIKE '%مساء%' THEN 4
        ELSE 2
    END AS `study_system_id`,
    (
        SELECT
            `id`
        FROM
            `certificate_manager`.`graduation_orders`
        WHERE
            `order_number` = `s140`.`order_university`
            AND `department_id` = CASE
                WHEN `s140`.`department` LIKE '%علوم الحاسوب%' THEN 2
                ELSE 1
            END
            AND `study_system_id` = CASE
                WHEN `s140`.`study` LIKE '%مساء%' THEN 4
                ELSE 2
            END
        LIMIT
            1
    ) AS order_id,
    CAST(`graduation_year` AS UNSIGNED) - 4,
    CAST(`graduation_year` AS UNSIGNED) - 1,
    CAST(`average` AS DECIMAL(5, 2))
FROM
    `project2`.`students_140` AS `s140`
UNION ALL
-- Part B: Annual System Students (students_q)
SELECT
    `name`,
    `name_en`,
    CASE
        WHEN `gender` LIKE '%ذكر%' THEN 'M'
        ELSE 'F'
    END,
    CAST(`sequence` AS UNSIGNED),
    CAST(`num_students` AS UNSIGNED),
    STR_TO_DATE (
        CONCAT (
            CAST(`graduation_year` AS UNSIGNED) - 22,
            '-01-01'
        ),
        '%Y-%m-%d'
    ),
    COALESCE(
        (
            SELECT
                `id`
            FROM
                `certificate_manager`.`governorates`
            WHERE
                `name_en` = `sq`.`birthplace_en`
            LIMIT
                1
        ),
        2
    ),
    NULL,
    COALESCE(
        (
            SELECT
                `id`
            FROM
                `certificate_manager`.`countries`
            WHERE
                `name_en` = `sq`.`nationality_en`
            LIMIT
                1
        ),
        274
    ),
    CASE
        WHEN `department` LIKE '%علوم الحاسوب%' THEN 2
        WHEN `department` LIKE '%نظم المعلومات%' THEN 1
        ELSE 1
    END AS `department_id`,
    CASE
        WHEN `study` LIKE '%مساء%' THEN 3
        ELSE 1
    END AS `study_system_id`,
    (
        SELECT
            `id`
        FROM
            `certificate_manager`.`graduation_orders`
        WHERE
            `order_number` = `sq`.`order_university`
            AND `department_id` = CASE
                WHEN `sq`.`department` LIKE '%علوم الحاسوب%' THEN 2
                ELSE 1
            END
            AND `study_system_id` = CASE
                WHEN `sq`.`study` LIKE '%مساء%' THEN 3
                ELSE 1
            END
        LIMIT
            1
    ) AS order_id,
    CAST(`graduation_year` AS UNSIGNED) - 4,
    CAST(`graduation_year` AS UNSIGNED) - 1,
    CAST(`average` AS DECIMAL(5, 2))
FROM
    `project2`.`students_q` AS `sq`;

COMMIT;

SET
    FOREIGN_KEY_CHECKS = 1;

----------------------------------------------------------
SET
    FOREIGN_KEY_CHECKS = 0;

START TRANSACTION;

-- =============================================================================
-- STEP 1: WIPE THE SLATE CLEAN
-- Safely clears partial data from previous runs while respecting constraints
-- =============================================================================
DELETE FROM `certificate_manager`.`enrollments`;

ALTER TABLE `certificate_manager`.`enrollments` AUTO_INCREMENT = 1;

DELETE FROM `certificate_manager`.`academic_periods`;

ALTER TABLE `certificate_manager`.`academic_periods` AUTO_INCREMENT = 1;

-- =============================================================================
-- STEP 2: MIGRATE ACADEMIC PERIODS 
-- Flattened: Using the newly minted CM_STD_ID directly
-- =============================================================================
INSERT IGNORE INTO `certificate_manager`.`academic_periods` (
    `student_id`,
    `academic_year`,
    `stage_number`,
    `semester_num`
)
SELECT DISTINCT
    `CM_STD_ID`, -- The verified new system ID
    `year`,
    `Stage`,
    `semester`
FROM
    `project2`.`big_table_enrrolment`
WHERE
    `CM_STD_ID` IS NOT NULL;

-- =============================================================================
-- STEP 3: MIGRATE ENROLLMENTS
-- Flattened: Anchored entirely by CM_STD_ID
-- =============================================================================
INSERT IGNORE INTO `certificate_manager`.`enrollments` (`period_id`, `course_id`, `score`, `passed_round`)
SELECT
    ap.`id` AS `period_id`,
    c.`id` AS `course_id`,
    CAST(bte.`degree` AS DECIMAL(5, 1)) AS `score`,
    bte.`Failed` AS `passed_round`
FROM
    `project2`.`big_table_enrrolment` AS bte
    -- 1. Grab the new student profile to access their Department ID
    INNER JOIN `certificate_manager`.`students` AS cms ON cms.`id` = bte.`CM_STD_ID`
    -- 2. Bind to the precise Academic Period we just generated
    INNER JOIN `certificate_manager`.`academic_periods` AS ap ON ap.`student_id` = bte.`CM_STD_ID`
    AND ap.`academic_year` = bte.`year`
    AND ap.`stage_number` = bte.`Stage`
    AND ap.`semester_num` = bte.`semester`
    -- 3. Lock onto the precise Course (Filtered by Name and the Student's Department)
    INNER JOIN `certificate_manager`.`courses` AS c ON TRIM(c.`name_ar`) = TRIM(bte.`Name_ar`);

COMMIT;

SET
    FOREIGN_KEY_CHECKS = 1;