DELIMITER / /
DROP PROCEDURE IF EXISTS sp_GetCertificate_AcademicCourses / / CREATE PROCEDURE sp_GetCertificate_AcademicCourses (
    IN p_student_id INT,
    IN p_grouping_mode VARCHAR(50)
) BEGIN DECLARE v_period_display VARCHAR(50);

-- 1. Identify the Study System Type for this specific student
-- We strictly use period_display ('year' or 'semester') from the study_systems table
SELECT
    LOWER(COALESCE(ss.period_display, 'year')) INTO v_period_display
FROM
    students s
    LEFT JOIN study_systems ss ON s.study_system_id = ss.id
WHERE
    s.id = p_student_id
LIMIT
    1;

-- 2. Route based on Study System
IF v_period_display = 'semester' THEN
-- ==========================================
-- SEMESTER SYSTEM ROUTING
-- ==========================================
IF p_grouping_mode = 'BY_SEMESTER_stage' THEN CALL sp_GetCertificate_Courses_Semester_ByStage (p_student_id);

ELSE
-- DEFAULT: Semester system grouped by Academic Year
CALL sp_GetCertificate_Courses_Semester_ByYear (p_student_id);

END IF;

ELSE
-- ==========================================
-- YEARLY (ANNUAL) SYSTEM ROUTING
-- ==========================================
IF p_grouping_mode = 'BY_PERIOD_STAGE' THEN CALL sp_GetCertificate_Courses_Yearly_ByPeriodStage (p_student_id);

ELSEIF p_grouping_mode = 'BY_CURRICULUM_STAGE' THEN CALL sp_GetCertificate_Courses_Yearly_ByCurriculumStage (p_student_id);

ELSE
-- DEFAULT: Yearly system grouped by Academic Year
CALL sp_GetCertificate_Courses_Yearly_ByAcademicYear (p_student_id);

END IF;

END IF;

END / / DELIMITER;

DELIMITER / /
DROP PROCEDURE IF EXISTS sp_GetCertificate_Courses_Yearly_ByCurriculumStage / / CREATE PROCEDURE sp_GetCertificate_Courses_Yearly_ByCurriculumStage (IN p_student_id INT) BEGIN
SELECT
    CASE
        WHEN ap.academic_year IS NULL
        OR ap.academic_year = '' THEN ''
        WHEN ap.academic_year LIKE '%-%' THEN ap.academic_year
        ELSE CONCAT (
            ap.academic_year,
            ' - ',
            CAST(ap.academic_year AS UNSIGNED) + 1
        )
    END AS academic_year_formatted,
    ap.academic_year,
    ap.stage_number AS period_stage,
    COALESCE(c.stage_number, ap.stage_number) AS course_curriculum_stage,
    COALESCE(ap.semester_num, 1) AS semester_num,
    COALESCE(c.name_ar, '') AS subject_name,
    COALESCE(c.credit_hours, 0) AS unit,
    COALESCE(e.score, 0.0) AS mark,
    COALESCE(e.passed_round, 1) AS passed_round,
    CASE
        WHEN COALESCE(c.stage_number, ap.stage_number) < ap.stage_number THEN 'عبور'
        ELSE 'أساسي'
    END AS course_type,
    -- Grouping Key: The Course's Official Syllabus Stage
    CAST(COALESCE(c.stage_number, ap.stage_number) AS CHAR) AS grouping_key
FROM
    academic_periods ap
    JOIN enrollments e ON e.period_id = ap.id
    JOIN courses c ON e.course_id = c.id
WHERE
    ap.student_id = p_student_id
ORDER BY
    COALESCE(c.stage_number, ap.stage_number) ASC,
    COALESCE(ap.semester_num, 1) ASC,
    c.name_ar ASC;

END / / DELIMITER;

DELIMITER / /
DROP PROCEDURE IF EXISTS sp_GetCertificate_Courses_Yearly_ByPeriodStage / / CREATE PROCEDURE sp_GetCertificate_Courses_Yearly_ByPeriodStage (IN p_student_id INT) BEGIN
SELECT
    CASE
        WHEN ap.academic_year IS NULL
        OR ap.academic_year = '' THEN ''
        WHEN ap.academic_year LIKE '%-%' THEN ap.academic_year
        ELSE CONCAT (
            ap.academic_year,
            ' - ',
            CAST(ap.academic_year AS UNSIGNED) + 1
        )
    END AS academic_year_formatted,
    ap.academic_year,
    ap.stage_number AS period_stage,
    COALESCE(c.stage_number, ap.stage_number) AS course_curriculum_stage,
    COALESCE(ap.semester_num, 1) AS semester_num,
    COALESCE(c.name_ar, '') AS subject_name,
    COALESCE(c.credit_hours, 0) AS unit,
    COALESCE(e.score, 0.0) AS mark,
    COALESCE(e.passed_round, 1) AS passed_round,
    CASE
        WHEN COALESCE(c.stage_number, ap.stage_number) < ap.stage_number THEN 'عبور'
        ELSE 'أساسي'
    END AS course_type,
    -- Grouping Key: Strictly the Period Stage
    CAST(ap.stage_number AS CHAR) AS grouping_key
FROM
    academic_periods ap
    JOIN enrollments e ON e.period_id = ap.id
    JOIN courses c ON e.course_id = c.id
WHERE
    ap.student_id = p_student_id
ORDER BY
    ap.stage_number ASC,
    COALESCE(ap.semester_num, 1) ASC,
    c.name_ar ASC;

END / / DELIMITER;

DELIMITER / /
DROP PROCEDURE IF EXISTS sp_GetCertificate_Courses_Yearly_ByAcademicYear / / CREATE PROCEDURE sp_GetCertificate_Courses_Yearly_ByAcademicYear (IN p_student_id INT) BEGIN
SELECT
    CASE
        WHEN ap.academic_year IS NULL
        OR ap.academic_year = '' THEN ''
        WHEN ap.academic_year LIKE '%-%' THEN ap.academic_year
        ELSE CONCAT (
            ap.academic_year,
            ' - ',
            CAST(ap.academic_year AS UNSIGNED) + 1
        )
    END AS academic_year_formatted,
    ap.academic_year,
    ap.stage_number AS period_stage,
    COALESCE(c.stage_number, ap.stage_number) AS course_curriculum_stage,
    COALESCE(ap.semester_num, 1) AS semester_num,
    COALESCE(c.name_ar, '') AS subject_name,
    COALESCE(c.credit_hours, 0) AS unit,
    COALESCE(e.score, 0.0) AS mark,
    COALESCE(e.passed_round, 1) AS passed_round,
    CASE
        WHEN COALESCE(c.stage_number, ap.stage_number) < ap.stage_number THEN 'عبور'
        ELSE 'أساسي'
    END AS course_type,
    -- Grouping Key: Strictly the Calendar Year
    ap.academic_year AS grouping_key
FROM
    academic_periods ap
    JOIN enrollments e ON e.period_id = ap.id
    JOIN courses c ON e.course_id = c.id
WHERE
    ap.student_id = p_student_id
ORDER BY
    ap.academic_year ASC,
    COALESCE(ap.semester_num, 1) ASC,
    c.name_ar ASC;

END / / DELIMITER;

DELIMITER / /
DROP PROCEDURE IF EXISTS sp_GetCertificate_Courses_Semester_ByYear / / CREATE PROCEDURE sp_GetCertificate_Courses_Semester_ByYear (IN p_student_id INT) BEGIN
SELECT
    CASE
        WHEN ap.academic_year IS NULL
        OR ap.academic_year = '' THEN ''
        WHEN ap.academic_year LIKE '%-%' THEN ap.academic_year
        ELSE CONCAT (
            ap.academic_year,
            ' - ',
            CAST(ap.academic_year AS UNSIGNED) + 1
        )
    END AS academic_year_formatted,
    ap.academic_year,
    -- Strictly relies on the period the student was actually in
    ap.stage_number,
    COALESCE(ap.semester_num, 1) AS semester_num,
    COALESCE(c.name_ar, '') AS subject_name,
    COALESCE(c.credit_hours, 0) AS unit,
    COALESCE(e.score, 0.0) AS mark,
    COALESCE(e.passed_round, 1) AS passed_round,
    -- Grouping Key: Year + Semester
    CONCAT (
        ap.academic_year,
        '_',
        COALESCE(ap.semester_num, 1)
    ) AS grouping_key
FROM
    academic_periods ap
    JOIN enrollments e ON e.period_id = ap.id
    JOIN courses c ON e.course_id = c.id
WHERE
    ap.student_id = p_student_id
ORDER BY
    ap.academic_year ASC,
    COALESCE(ap.semester_num, 1) ASC,
    c.name_ar ASC;

END / / DELIMITER;

DELIMITER / /
DROP PROCEDURE IF EXISTS sp_GetCertificate_Courses_Semester_ByStage / / CREATE PROCEDURE sp_GetCertificate_Courses_Semester_ByStage (IN p_student_id INT) BEGIN
SELECT
    CASE
        WHEN ap.academic_year IS NULL
        OR ap.academic_year = '' THEN ''
        WHEN ap.academic_year LIKE '%-%' THEN ap.academic_year
        ELSE CONCAT (
            ap.academic_year,
            ' - ',
            CAST(ap.academic_year AS UNSIGNED) + 1
        )
    END AS academic_year_formatted,
    ap.academic_year,
    -- Strictly relies on the period the student was actually in
    ap.stage_number,
    COALESCE(ap.semester_num, 1) AS semester_num,
    COALESCE(c.name_ar, '') AS subject_name,
    COALESCE(c.credit_hours, 0) AS unit,
    COALESCE(e.score, 0.0) AS mark,
    COALESCE(e.passed_round, 1) AS passed_round,
    -- Grouping Key: Period Stage + Semester
    CONCAT (
        ap.stage_number,
        '_',
        COALESCE(ap.semester_num, 1)
    ) AS grouping_key
FROM
    academic_periods ap
    JOIN enrollments e ON e.period_id = ap.id
    JOIN courses c ON e.course_id = c.id
WHERE
    ap.student_id = p_student_id
ORDER BY
    ap.stage_number ASC,
    COALESCE(ap.semester_num, 1) ASC,
    c.name_ar ASC;

END / / DELIMITER;

DELIMITER / /
DROP PROCEDURE IF EXISTS sp_GetCertificate_UniversitySettings / / CREATE PROCEDURE sp_GetCertificate_UniversitySettings () BEGIN
SELECT
    *
FROM
    university_settings
ORDER BY
    id ASC
LIMIT
    1;

END / / DELIMITER;

DELIMITER / /
DROP PROCEDURE IF EXISTS sp_GetCertificate_Signers / / CREATE PROCEDURE sp_GetCertificate_Signers () BEGIN
SELECT
    id,
    COALESCE(name_ar, '') AS name_ar,
    COALESCE(name_en, '') AS name_en,
    COALESCE(academic_title_ar, '') AS academic_title_ar,
    COALESCE(academic_title_en, '') AS academic_title_en,
    COALESCE(responsibility_ar, '') AS responsibility_ar,
    COALESCE(responsibility_en, '') AS responsibility_en,
    COALESCE(display_order, 0) AS display_order,
    TRUE AS is_signature,
    COALESCE(display_order, 0) AS page_location,
    COALESCE(personnel_role, 'signer') AS personnel_role
FROM
    personnel
WHERE
    is_active = 1
    AND display_order > 0
ORDER BY
    display_order ASC,
    id ASC;

END / / DELIMITER;

DELIMITER / /
DROP PROCEDURE IF EXISTS sp_GetCertificate_AcademicTimeline / / CREATE PROCEDURE sp_GetCertificate_AcademicTimeline (IN p_student_id INT) BEGIN
SELECT
    MIN(ap.id) AS primary_period_id,
    CASE
        WHEN ap.academic_year IS NULL
        OR ap.academic_year = '' THEN ''
        WHEN ap.academic_year LIKE '%-%' THEN ap.academic_year
        ELSE CONCAT (
            ap.academic_year,
            ' - ',
            CAST(ap.academic_year AS UNSIGNED) + 1
        )
    END AS academic_year,
    -- The Magic Fix: Picks the stage_number that holds the highest count of courses for this semester
    (
        SELECT
            ap_sub.stage_number
        FROM
            academic_periods ap_sub
            LEFT JOIN enrollments e_sub ON e_sub.period_id = ap_sub.id
        WHERE
            ap_sub.student_id = p_student_id
            AND ap_sub.academic_year = ap.academic_year
            AND COALESCE(ap_sub.semester_num, 1) = COALESCE(ap.semester_num, 1)
        GROUP BY
            ap_sub.stage_number
        ORDER BY
            COUNT(e_sub.id) DESC,
            ap_sub.stage_number DESC
        LIMIT
            1
    ) AS stage_number,
    COALESCE(ap.semester_num, 1) AS semester_num,
    GROUP_CONCAT (
        DISTINCT COALESCE(ap.result_status, 'PASSED')
        ORDER BY
            ap.result_status ASC SEPARATOR ' / '
    ) AS result_status
FROM
    academic_periods ap
WHERE
    ap.student_id = p_student_id
GROUP BY
    ap.academic_year,
    ap.semester_num
ORDER BY
    ap.academic_year ASC,
    ap.semester_num ASC;

END / / DELIMITER;