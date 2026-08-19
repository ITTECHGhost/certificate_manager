DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_AcademicCourses`//
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_AcademicCourses`(
    IN p_student_id INT,
    IN p_grouping_mode VARCHAR(50)
)
BEGIN
    DECLARE v_period_display VARCHAR(50);

            SELECT LOWER(COALESCE(ss.period_display, 'year'))
    INTO v_period_display
    FROM students s
    LEFT JOIN study_systems ss ON s.study_system_id = ss.id
    WHERE s.id = p_student_id
    LIMIT 1;

        IF v_period_display = 'semester' THEN
        
                                IF p_grouping_mode = 'BY_SEMESTER_stage' THEN
            CALL sp_GetCertificate_Courses_Semester_ByStage(p_student_id);
            
        ELSE
                        CALL sp_GetCertificate_Courses_Semester_ByYear(p_student_id);
        END IF;

    ELSE
        
                                IF p_grouping_mode = 'BY_PERIOD_STAGE' THEN
            CALL sp_GetCertificate_Courses_Yearly_ByPeriodStage(p_student_id);
            
        ELSEIF p_grouping_mode = 'BY_CURRICULUM_STAGE' THEN
            CALL sp_GetCertificate_Courses_Yearly_ByCurriculumStage(p_student_id);
            
        ELSE
                        CALL sp_GetCertificate_Courses_Yearly_ByAcademicYear(p_student_id);
        END IF;
        
    END IF;
END//
DELIMITER ;

DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_AcademicTimeline`//
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_AcademicTimeline`(
    IN p_student_id INT
)
BEGIN
    SELECT 
        MIN(ap.id) AS primary_period_id,
        CASE 
            WHEN ap.academic_year IS NULL OR ap.academic_year = '' THEN ''
            WHEN ap.academic_year LIKE '%-%' THEN ap.academic_year
            ELSE CONCAT(ap.academic_year, ' - ', CAST(ap.academic_year AS UNSIGNED) + 1)
        END AS academic_year,
        
                (
            SELECT ap_sub.stage_number
            FROM academic_periods ap_sub
            LEFT JOIN enrollments e_sub ON e_sub.period_id = ap_sub.id
            WHERE ap_sub.student_id = p_student_id
              AND ap_sub.academic_year = ap.academic_year
              AND COALESCE(ap_sub.semester_num, 1) = COALESCE(ap.semester_num, 1)
            GROUP BY ap_sub.stage_number
            ORDER BY COUNT(e_sub.id) DESC, ap_sub.stage_number DESC
            LIMIT 1
        ) AS stage_number,
        
        COALESCE(ap.semester_num, 1) AS semester_num,
        GROUP_CONCAT(DISTINCT COALESCE(ap.result_status, 'PASSED') ORDER BY ap.result_status ASC SEPARATOR ' / ') AS result_status
    FROM academic_periods ap
    WHERE ap.student_id = p_student_id
    GROUP BY 
        ap.academic_year, 
        ap.semester_num
    ORDER BY 
        ap.academic_year ASC, 
        ap.semester_num ASC;
END//
DELIMITER ;

DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_Courses_Semester_ByStage`//
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_Courses_Semester_ByStage`(
    IN p_student_id INT
)
BEGIN
    SELECT 
        CASE 
            WHEN ap.academic_year IS NULL OR ap.academic_year = '' THEN ''
            WHEN ap.academic_year LIKE '%-%' THEN ap.academic_year
            ELSE CONCAT(ap.academic_year, ' - ', CAST(ap.academic_year AS UNSIGNED) + 1)
        END AS academic_year_formatted,
        ap.academic_year,
        
                ap.stage_number,
        COALESCE(ap.semester_num, 1) AS semester_num,
        
        COALESCE(c.name_ar, '') AS subject_name,
        COALESCE(c.credit_hours, 0) AS unit,
        COALESCE(e.score, 0.0) AS mark,
        COALESCE(e.passed_round, 1) AS passed_round,
        
                CONCAT(ap.stage_number, '_', COALESCE(ap.semester_num, 1)) AS grouping_key

    FROM academic_periods ap
    JOIN enrollments e ON e.period_id = ap.id
    JOIN courses c ON e.course_id = c.id
    WHERE ap.student_id = p_student_id
    ORDER BY 
        ap.stage_number ASC,
        COALESCE(ap.semester_num, 1) ASC,
        c.name_ar ASC;
END//
DELIMITER ;

DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_Courses_Semester_ByYear`//
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_Courses_Semester_ByYear`(
    IN p_student_id INT
)
BEGIN
    SELECT 
        CASE 
            WHEN ap.academic_year IS NULL OR ap.academic_year = '' THEN ''
            WHEN ap.academic_year LIKE '%-%' THEN ap.academic_year
            ELSE CONCAT(ap.academic_year, ' - ', CAST(ap.academic_year AS UNSIGNED) + 1)
        END AS academic_year_formatted,
        ap.academic_year,
        
                ap.stage_number,
        COALESCE(ap.semester_num, 1) AS semester_num,
        
        COALESCE(c.name_ar, '') AS subject_name,
        COALESCE(c.credit_hours, 0) AS unit,
        COALESCE(e.score, 0.0) AS mark,
        COALESCE(e.passed_round, 1) AS passed_round,
        
                CONCAT(ap.academic_year, '_', COALESCE(ap.semester_num, 1)) AS grouping_key

    FROM academic_periods ap
    JOIN enrollments e ON e.period_id = ap.id
    JOIN courses c ON e.course_id = c.id
    WHERE ap.student_id = p_student_id
    ORDER BY 
        ap.academic_year ASC,
        COALESCE(ap.semester_num, 1) ASC,
        c.name_ar ASC;
END//
DELIMITER ;

DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_Ranking`//
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_Ranking`(
    IN p_student_id INT
)
BEGIN
    DECLARE v_dept_id INT;
    DECLARE v_grad_year INT;
    DECLARE v_avg DECIMAL(5,2);

        SELECT 
        department_id,
        COALESCE(average, 0.0),
        YEAR(graduation_date)
    INTO 
        v_dept_id,
        v_avg,
        v_grad_year
    FROM students
    WHERE id = p_student_id
    LIMIT 1;

        SELECT 
        (
            SELECT COUNT(*) + 1 
            FROM students s2 
            WHERE s2.department_id = v_dept_id 
              AND YEAR(s2.graduation_date) = v_grad_year 
              AND s2.average > v_avg 
              AND s2.average IS NOT NULL
        ) AS class_rank,
        (
            SELECT COUNT(*) 
            FROM students s3 
            WHERE s3.department_id = v_dept_id 
              AND YEAR(s3.graduation_date) = v_grad_year
        ) AS total_graduates,
        (
            SELECT COALESCE(MAX(average), 0.0) 
            FROM students s4 
            WHERE s4.department_id = v_dept_id 
              AND YEAR(s4.graduation_date) = v_grad_year
        ) AS top_average;
END//
DELIMITER ;

DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_Signers`//
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_Signers`()
BEGIN
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
    FROM personnel
    WHERE is_active = 1 AND display_order > 0
    ORDER BY display_order ASC, id ASC;
END//
DELIMITER ;

DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_StudentInfo`//
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_StudentInfo`(
    IN p_student_id INT
)
BEGIN
    SELECT 
        s.id AS student_id,
        COALESCE(s.full_name_ar, '') AS full_name_ar,
        COALESCE(s.full_name_en, '') AS full_name_en,
        COALESCE(s.average, 0.0) AS average,
        COALESCE(YEAR(s.graduation_date), 0) AS graduation_year,
        s.graduation_date,
        s.admission_year,
        s.study_system_id,
        s.department_id,
        s.nationality_id,
        s.birthplace_id,
        s.order_id,
        COALESCE(d.name_ar, '') AS dept_name_ar, 
        COALESCE(d.name_en, '') AS dept_name_en, 
        COALESCE(ss.name_ar, '') AS study_system_name_ar, 
        COALESCE(ss.name_en, '') AS study_system_name_en, 
        COALESCE(ss.calculation_rule, '') AS calculation_rule, 
        COALESCE(ss.calculation_weights, '') AS calculation_weights, 
        COALESCE(ss.period_display, '') AS period_display, 
        COALESCE(ss.study_day_type, '') AS study_type, 
        COALESCE(c.name_ar, '') AS nationality_ar, 
        COALESCE(c.name_en, '') AS nationality_en, 
        COALESCE(g.name_ar, '') AS birthplace_ar, 
        COALESCE(g.name_en, '') AS birthplace_en, 
        COALESCE(o.order_number, '') AS order_number, 
        o.order_date 
    FROM students s 
    LEFT JOIN departments d ON s.department_id = d.id 
    LEFT JOIN study_systems ss ON s.study_system_id = ss.id 
    LEFT JOIN countries c ON s.nationality_id = c.id 
    LEFT JOIN governorates g ON s.birthplace_id = g.id 
    LEFT JOIN graduation_orders o ON s.order_id = o.id 
    WHERE s.id = p_student_id
    LIMIT 1;
END//
DELIMITER ;

DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_UniversitySettings`//
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_UniversitySettings`()
BEGIN
    SELECT * 
    FROM university_settings 
    ORDER BY id ASC 
    LIMIT 1;
END//
DELIMITER ;

DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetFullCertificateData`//
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetFullCertificateData`(
    IN p_student_id INT,
    IN p_grouping_mode VARCHAR(50)
)
BEGIN
                    
        CALL sp_GetCertificate_UniversitySettings();

        CALL sp_GetCertificate_StudentInfo(p_student_id);

        CALL sp_GetCertificate_Ranking(p_student_id);

        CALL sp_GetCertificate_Signers();

        CALL sp_GetCertificate_AcademicTimeline(p_student_id);

        CALL sp_GetCertificate_AcademicCourses(p_student_id, p_grouping_mode);
    
END//
DELIMITER ;

