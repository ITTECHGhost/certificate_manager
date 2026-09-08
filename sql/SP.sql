-- ========================================================
-- MySQL Stored Procedures Export: certificate_manager
-- ========================================================

-- --------------------------------------------------------
-- Stored Procedure `AuthenticateUser`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `AuthenticateUser` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `AuthenticateUser`(IN `p_username` VARCHAR(50), IN `p_password_hash` VARCHAR(255))
BEGIN

        SELECT 

        id, 

        name_ar, 

        name_en, 

        personnel_role

    FROM personnel

    WHERE username = p_username 

      AND password_hash = p_password_hash

      AND is_active = 1

    LIMIT 1;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `ClearAuditLogs`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `ClearAuditLogs` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `ClearAuditLogs`()
BEGIN

        TRUNCATE TABLE audit_log;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `CountStudentsFiltered`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `CountStudentsFiltered` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `CountStudentsFiltered`(
        IN p_search VARCHAR(150),
        IN p_dept_id INT,
        IN p_year VARCHAR(9)
    )
BEGIN
        SELECT COUNT(*) AS total_count
        FROM students s
        WHERE (p_search IS NULL OR p_search = '' OR s.full_name_ar LIKE CONCAT('%', p_search, '%') OR s.full_name_en LIKE CONCAT('%', p_search, '%'))
          AND (p_dept_id IS NULL OR s.department_id = p_dept_id)
          AND (p_year IS NULL OR p_year = '' OR YEAR(s.graduation_date) = p_year);
    END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `Create_Default_Settings`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `Create_Default_Settings` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `Create_Default_Settings`(

    IN p_EMP_ID INT

)
BEGIN

    INSERT INTO settings (EMP_ID, theme, accent_color, font_family, font_size_base, is_arabic_rtl)

    VALUES (

        p_EMP_ID, 

        'light',               'blue',               'Arial',              14,                   1                 );

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `DeleteDepartment`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `DeleteDepartment` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteDepartment`(IN p_id INT)
BEGIN

    DELETE FROM departments WHERE id = p_id;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `DeleteGraduationOrder`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `DeleteGraduationOrder` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteGraduationOrder`(IN p_id INT)
BEGIN

        UPDATE students SET order_id = NULL WHERE order_id = p_id;

        DELETE FROM graduation_orders WHERE id = p_id;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `DeleteIssuedCertificate`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `DeleteIssuedCertificate` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteIssuedCertificate`(
    IN p_id INT
)
BEGIN
    DELETE FROM issued_certificates WHERE id = p_id;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `DeletePersonnel`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `DeletePersonnel` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeletePersonnel`(

    IN p_id INT

)
BEGIN

    DELETE FROM personnel WHERE id = p_id;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `DeleteStudent`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `DeleteStudent` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteStudent`(IN p_id INT)
BEGIN

    DELETE FROM students WHERE id = p_id;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `DeleteStudentSupervisor`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `DeleteStudentSupervisor` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteStudentSupervisor`(IN p_id INT)
BEGIN
        DELETE FROM student_supervisors WHERE id = p_id;
    END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `DeleteStudyRoutine`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `DeleteStudyRoutine` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteStudyRoutine`(
    IN p_id INT
)
BEGIN
    DELETE src FROM study_routine_courses src
    JOIN study_routine_period srp ON src.period_id = srp.id
    WHERE srp.routine_id = p_id;

    DELETE FROM study_routine_period WHERE routine_id = p_id;

    DELETE FROM study_routines WHERE id = p_id;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `DeleteStudyRoutineCourse`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `DeleteStudyRoutineCourse` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteStudyRoutineCourse`(
    IN p_routine_id INT,
    IN p_course_id INT
)
BEGIN
    DELETE FROM study_routine_courses 
    WHERE routine_id = p_routine_id AND course_id = p_course_id;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `DeleteStudyRoutinePeriod`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `DeleteStudyRoutinePeriod` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteStudyRoutinePeriod`(
    IN p_period_id INT
)
BEGIN
    DELETE FROM study_routine_period WHERE id = p_period_id;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `DeleteStudyRoutinePeriodCourse`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `DeleteStudyRoutinePeriodCourse` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteStudyRoutinePeriodCourse`(
    IN p_period_id INT,
    IN p_course_id INT
)
BEGIN
    DELETE FROM study_routine_courses 
    WHERE period_id = p_period_id AND course_id = p_course_id;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `DeleteStudySystem`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `DeleteStudySystem` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteStudySystem`(IN p_id INT)
BEGIN

    DELETE FROM study_systems WHERE id = p_id;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `DeleteThesis`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `DeleteThesis` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `DeleteThesis`(IN p_id INT)
BEGIN
        DELETE FROM thesis_records WHERE id = p_id;
    END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetAcademicPeriodsByStudent`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetAcademicPeriodsByStudent` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAcademicPeriodsByStudent`(IN p_student_id INT)
BEGIN
        SELECT id, student_id, academic_year, stage_number, semester_num, study_system_id
        FROM academic_periods 
        WHERE student_id = p_student_id 
        ORDER BY academic_year ASC, semester_num ASC;
    END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetActivePersonnel`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetActivePersonnel` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetActivePersonnel`()
BEGIN

    SELECT id, name_ar, name_en, academic_title_ar, academic_title_en, 

           responsibility_ar, responsibility_en, display_order 

    FROM personnel 

    WHERE is_active = 1 ORDER BY display_order ASC;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetActiveStudySystems`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetActiveStudySystems` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetActiveStudySystems`()
BEGIN

    SELECT id, name_ar, name_en, study_day_type, calculation_rule, 

           calculation_weights, period_display

    FROM study_systems 

    WHERE is_active = 1 ORDER BY id ASC;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetAllCountries`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetAllCountries` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAllCountries`()
BEGIN

    SELECT id, name_ar, name_en, iso_code FROM countries ORDER BY name_en ASC;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetAllCourses`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetAllCourses` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAllCourses`()
BEGIN
    SELECT 
        c.id, 
        c.name_ar, 
        c.name_en, 
        c.credit_hours, 
        c.stage_number,
        c.study_system_id, 
        c.is_shared,
        c.department_id,
        COALESCE(
            d.name_ar, 
            (SELECT GROUP_CONCAT(d2.name_ar SEPARATOR '، ') 
             FROM course_departments cd 
             JOIN departments d2 ON cd.department_id = d2.id 
             WHERE cd.course_id = c.id)
        ) AS dept_name_ar,
        COALESCE(
            d.name_en, 
            (SELECT GROUP_CONCAT(d2.name_en SEPARATOR ', ') 
             FROM course_departments cd 
             JOIN departments d2 ON cd.department_id = d2.id 
             WHERE cd.course_id = c.id)
        ) AS dept_name_en,
        s.name_ar AS study_system_name_ar,
        s.name_en AS study_system_name_en
    FROM courses c
    LEFT JOIN departments d ON c.department_id = d.id
    LEFT JOIN study_systems s ON c.study_system_id = s.id
    ORDER BY c.name_ar ASC;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetAllDepartments`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetAllDepartments` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAllDepartments`()
BEGIN

    SELECT d.id, d.name_ar, d.name_en, u.college_name_ar, u.college_name_en

    FROM departments d

    LEFT JOIN university_settings u ON d.university_settings_id = u.id

    ORDER BY d.name_ar ASC;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetAllGovernorates`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetAllGovernorates` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAllGovernorates`()
BEGIN

    SELECT id, name_ar, name_en FROM governorates ORDER BY id ASC;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetAllGraduationOrders`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetAllGraduationOrders` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAllGraduationOrders`(

    IN p_limit INT,

    IN p_offset INT

)
BEGIN

    SELECT 

        o.id, 

        o.order_number, 

        o.order_date, 

        o.department_id, 

        d.name_ar AS dept_name_ar, 

        d.name_en AS dept_name_en, 

        o.study_type, 

        o.graduation_year,         o.graduation_semester, 

        o.num_students, 

        o.notes, 

        o.study_system_id,

        (SELECT COUNT(s.id) FROM students s WHERE s.order_id = o.id) AS linked_count

    FROM graduation_orders o

    JOIN departments d ON o.department_id = d.id

    ORDER BY o.id DESC     LIMIT p_limit OFFSET p_offset; END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetAllIssuedCertificates`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetAllIssuedCertificates` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAllIssuedCertificates`()
BEGIN
    SELECT 
        ic.id,
        ic.student_id,
        COALESCE(ic.to_title, 'من يهمه الأمر') AS to_title,
        COALESCE(ic.template_type, 'ARABIC') AS template_type,
        ic.issue_date,
        ic.created_at,
        COALESCE(s.full_name_ar, '') AS student_name_ar,
        COALESCE(s.full_name_en, '') AS student_name_en
    FROM issued_certificates ic
    LEFT JOIN students s ON ic.student_id = s.id
    ORDER BY ic.issue_date DESC, ic.id DESC;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetAllPersonnel`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetAllPersonnel` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAllPersonnel`()
BEGIN

    SELECT 

        p.id,

        COALESCE(p.name_ar, '') AS name_ar,

        COALESCE(p.name_en, '') AS name_en,

        COALESCE(p.academic_title_ar, '') AS academic_title_ar,

        COALESCE(p.academic_title_en, '') AS academic_title_en,

        COALESCE(p.responsibility_ar, '') AS responsibility_ar,

        COALESCE(p.responsibility_en, '') AS responsibility_en,

        COALESCE(p.display_order, 0) AS display_order,

        CASE 

            WHEN COALESCE(p.display_order, 0) > 0 THEN TRUE 

            ELSE FALSE 

        END AS is_signature,

        COALESCE(p.display_order, 0) AS page_location,

        COALESCE(p.username, '') AS username,

        COALESCE(p.personnel_role, 'user') AS personnel_role,

        COALESCE(p.university_settings_id, 1) AS university_settings_id,

        COALESCE(p.is_active, 1) AS is_active,

        p.created_at

    FROM personnel p

    LEFT JOIN university_settings us ON p.university_settings_id = us.id

    ORDER BY p.display_order ASC, p.id ASC;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetAllStudyRoutines`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetAllStudyRoutines` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAllStudyRoutines`()
BEGIN
    SELECT 
        sr.id,
        COALESCE(sr.name_ar, '') AS name_ar,
        COALESCE(sr.name_en, '') AS name_en,
        COALESCE(sr.department_id, 1) AS department_id,
        COALESCE(sr.study_system_id, 1) AS study_system_id,
        sr.created_at,
        COALESCE(d.name_ar, '') AS department_name_ar,
        COALESCE(ss.name_ar, '') AS study_system_name_ar
    FROM study_routines sr
    LEFT JOIN departments d ON sr.department_id = d.id
    LEFT JOIN study_systems ss ON sr.study_system_id = ss.id
    ORDER BY d.name_ar ASC, sr.name_ar ASC;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetAllStudySystems`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetAllStudySystems` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetAllStudySystems`()
BEGIN

    SELECT id, name_ar, name_en, study_day_type, calculation_rule, 

           calculation_weights, period_display, is_active, created_at

    FROM study_systems ORDER BY id ASC;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetCoursesByDepartment`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetCoursesByDepartment` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetCoursesByDepartment`(IN p_dept_id INT)
BEGIN

    SELECT c.id, c.name_ar, c.name_en, c.credit_hours, c.study_system_id, c.is_shared

    FROM courses c

    WHERE c.department_id = p_dept_id 

       OR (c.is_shared = 1 AND c.id IN (SELECT course_id FROM course_departments WHERE department_id = p_dept_id))

    ORDER BY c.name_ar ASC;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetDepartmentByID`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetDepartmentByID` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetDepartmentByID`(IN p_dept_id INT)
BEGIN

    SELECT d.id, d.name_ar, d.name_en, u.college_name_ar, u.college_name_en

    FROM departments d

    LEFT JOIN university_settings u ON d.university_settings_id = u.id

    WHERE d.id = p_dept_id;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetEnrollmentsByPeriod`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetEnrollmentsByPeriod` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetEnrollmentsByPeriod`(IN p_period_id INT)
BEGIN

    SELECT e.id, e.period_id, e.course_id, e.score, e.passed_round,

           c.name_ar AS course_name_ar, c.name_en AS course_name_en, c.credit_hours

    FROM enrollments e 

    JOIN courses c ON e.course_id = c.id 

    WHERE e.period_id = p_period_id

    ORDER BY c.name_ar ASC;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetFullCertificateData`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetFullCertificateData` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetFullCertificateData`(IN p_student_id INT)
BEGIN 

    DECLARE v_grad_year INT;

    DECLARE v_dept_id INT;

    DECLARE v_avg FLOAT;



        SELECT 

        department_id, 

        average, 

        YEAR(graduation_date)

    INTO 

        v_dept_id, 

        v_avg, 

        v_grad_year

    FROM students

    WHERE id = p_student_id;



        SELECT 

        s.id,

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

    WHERE s.id = p_student_id; 



        SELECT 

        (SELECT COUNT(*) + 1 

         FROM students s2 

         WHERE s2.department_id = v_dept_id 

           AND YEAR(s2.graduation_date) = v_grad_year 

           AND s2.average > v_avg 

           AND s2.average IS NOT NULL) AS class_rank, 

        (SELECT COUNT(*) 

         FROM students s3 

         WHERE s3.department_id = v_dept_id 

           AND YEAR(s3.graduation_date) = v_grad_year) AS total_graduates, 

        (SELECT COALESCE(MAX(average), 0.0) 

         FROM students s4 

         WHERE s4.department_id = v_dept_id 

           AND YEAR(s4.graduation_date) = v_grad_year) AS top_average;



        SELECT 

        id, 

        student_id, 

        COALESCE(academic_year, '') AS academic_year, 

        COALESCE(stage_number, 1) AS stage_number, 

        COALESCE(semester_num, 1) AS semester_num, 

        COALESCE(study_system_id, 1) AS study_system_id 

    FROM academic_periods 

    WHERE student_id = p_student_id 

    ORDER BY academic_year ASC, semester_num ASC; 



        SELECT 

        e.id, 

        e.period_id, 

        e.course_id, 

        COALESCE(e.score, 0.0) AS score, 

        COALESCE(e.passed_round, 1) AS passed_round, 

        COALESCE(c.name_ar, '') AS course_name_ar, 

        COALESCE(c.name_en, '') AS course_name_en, 

        COALESCE(c.credit_hours, 0) AS credit_hours 

    FROM enrollments e 

    JOIN academic_periods ap ON e.period_id = ap.id 

    JOIN courses c ON e.course_id = c.id 

    WHERE ap.student_id = p_student_id 

    ORDER BY ap.academic_year ASC, ap.semester_num ASC, c.name_ar ASC; 



        SELECT 

        p.id,

        COALESCE(p.name_ar, '') AS name_ar,

        COALESCE(p.name_en, '') AS name_en,

        p.academic_title_ar,

        p.academic_title_en,

        COALESCE(p.responsibility_ar, '') AS responsibility_ar,

        COALESCE(p.responsibility_en, '') AS responsibility_en,

        COALESCE(p.display_order, 0) AS display_order,

        TRUE AS is_signature,

        COALESCE(p.display_order, 0) AS page_location,

        COALESCE(p.personnel_role, 'signer') AS personnel_role

    FROM personnel p

    WHERE p.is_active = 1 AND p.display_order > 0

    ORDER BY p.display_order ASC, p.id ASC; 



        SELECT * 

    FROM university_settings 

    ORDER BY id ASC 

    LIMIT 1; 

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetGraduationOrderByID`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetGraduationOrderByID` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetGraduationOrderByID`(IN p_order_id INT)
BEGIN

    SELECT o.*, d.name_ar AS dept_name_ar, d.name_en AS dept_name_en 

    FROM graduation_orders o

    JOIN departments d ON o.department_id = d.id

    WHERE o.id = p_order_id;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetIssuedCertificateById`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetIssuedCertificateById` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetIssuedCertificateById`(
    IN p_id INT
)
BEGIN
    SELECT 
        ic.id,
        ic.student_id,
        COALESCE(ic.to_title, 'من يهمه الأمر') AS to_title,
        COALESCE(ic.template_type, 'ARABIC') AS template_type,
        ic.issue_date,
        ic.created_at,
        COALESCE(s.full_name_ar, '') AS student_name_ar,
        COALESCE(s.full_name_en, '') AS student_name_en
    FROM issued_certificates ic
    LEFT JOIN students s ON ic.student_id = s.id
    WHERE ic.id = p_id
    LIMIT 1;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetIssuedCertificatesByStudent`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetIssuedCertificatesByStudent` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetIssuedCertificatesByStudent`(
    IN p_student_id INT
)
BEGIN
    SELECT 
        ic.id,
        ic.student_id,
        COALESCE(ic.to_title, 'من يهمه الأمر') AS to_title,
        COALESCE(ic.template_type, 'ARABIC') AS template_type,
        ic.issue_date,
        ic.created_at,
        COALESCE(s.full_name_ar, '') AS student_name_ar,
        COALESCE(s.full_name_en, '') AS student_name_en
    FROM issued_certificates ic
    LEFT JOIN students s ON ic.student_id = s.id
    WHERE ic.student_id = p_student_id
    ORDER BY ic.issue_date DESC;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetIssuedCertificatesReport`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetIssuedCertificatesReport` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetIssuedCertificatesReport`(
    IN p_start_date DATE,
    IN p_end_date DATE,
    IN p_department_id INT,
    IN p_template_type VARCHAR(100)
)
BEGIN
    SELECT 
        ic.id AS certificate_id,
        ic.student_id,
        COALESCE(ic.to_title, 'من يهمه الأمر') AS to_title,
        COALESCE(ic.template_type, 'ARABIC') AS template_type,
        COALESCE(ic.issue_date, '1970-01-01') AS issue_date,
        ic.created_at,
        COALESCE(s.full_name_ar, '') AS student_name_ar,
        COALESCE(s.full_name_en, '') AS student_name_en,
        COALESCE(s.average, 0.0) AS average,
        COALESCE(d.id, 0) AS department_id,
        COALESCE(d.name_ar, '') AS department_name_ar
    FROM issued_certificates ic
    LEFT JOIN students s ON ic.student_id = s.id
    LEFT JOIN departments d ON s.department_id = d.id
    WHERE 
        (ic.issue_date >= p_start_date OR p_start_date IS NULL)
        AND (ic.issue_date <= p_end_date OR p_end_date IS NULL)
        AND (d.id = p_department_id OR p_department_id = 0 OR p_department_id IS NULL)
        AND (ic.template_type = p_template_type OR p_template_type = '' OR p_template_type IS NULL)
    ORDER BY ic.issue_date DESC, d.name_ar ASC, s.full_name_ar ASC;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetPersonnelById`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetPersonnelById` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetPersonnelById`(

    IN p_id INT

)
BEGIN

    SELECT 

        p.id,

        COALESCE(p.name_ar, '') AS name_ar,

        COALESCE(p.name_en, '') AS name_en,

        p.academic_title_ar,

        p.academic_title_en,

        COALESCE(p.responsibility_ar, '') AS responsibility_ar,

        COALESCE(p.responsibility_en, '') AS responsibility_en,

        COALESCE(p.display_order, 0) AS display_order,

        CASE 

            WHEN COALESCE(p.display_order, 0) > 0 THEN TRUE 

            ELSE FALSE 

        END AS is_signature,

        COALESCE(p.display_order, 0) AS page_location,

        COALESCE(p.username, '') AS username,

        COALESCE(p.personnel_role, 'user') AS personnel_role,

        p.university_settings_id,

        COALESCE(p.is_active, 1) AS is_active,

        p.created_at

    FROM personnel p

    LEFT JOIN university_settings us ON p.university_settings_id = us.id

    WHERE p.id = p_id

    LIMIT 1;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetStudentDossierByID`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetStudentDossierByID` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetStudentDossierByID`(IN p_student_id INT)
BEGIN 
    SELECT s.*, YEAR(s.graduation_date) AS graduation_year, 
           d.name_ar AS dept_name_ar, d.name_en AS dept_name_en, 
           ss.name_ar AS study_system_name_ar, ss.name_en AS study_system_name_en, 
           ss.study_day_type AS study_type, 
           c.name_ar AS nationality_ar, c.name_en AS nationality_en, 
           g.name_ar AS birthplace_ar, g.name_en AS birthplace_en, 
           o.order_number, o.order_date, o.graduation_semester AS order_graduation_semester 
    FROM students s 
    LEFT JOIN departments d ON s.department_id = d.id 
    LEFT JOIN study_systems ss ON s.study_system_id = ss.id 
    LEFT JOIN countries c ON s.nationality_id = c.id 
    LEFT JOIN governorates g ON s.birthplace_id = g.id 
    LEFT JOIN graduation_orders o ON s.order_id = o.id 
    WHERE s.id = p_student_id; 
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetStudentTranscriptByID`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetStudentTranscriptByID` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetStudentTranscriptByID`(

    IN p_student_id INT

)
BEGIN

                SELECT 

        s.`id` AS `Student_ID`,

        s.`full_name_ar` AS `Arabic_Name`,

        s.`full_name_en` AS `English_Name`,

        s.`gender` AS `Gender`,

        s.`date_of_birth` AS `DOB`,

        gov.`name_ar` AS `Birthplace`,

        nat.`name_ar` AS `Nationality`,

        d.`name_ar` AS `Department`,

        s.`degree_level` AS `Degree_Level`,

        s.`admission_year` AS `Admission_Year`,

        s.`average` AS `Final_Average`,

        go.`order_number` AS `Graduation_Order_No`,

        go.`order_date` AS `Graduation_Order_Date`

    FROM `certificate_manager`.`students` AS s

    

        LEFT JOIN `certificate_manager`.`departments` AS d ON s.`department_id` = d.`id`

    LEFT JOIN `certificate_manager`.`governorates` AS gov ON s.`birthplace_id` = gov.`id`

    LEFT JOIN `certificate_manager`.`countries` AS nat ON s.`nationality_id` = nat.`id`

    LEFT JOIN `certificate_manager`.`graduation_orders` AS go ON s.`order_id` = go.`id`

    

    WHERE s.`id` = p_student_id;



                SELECT 

        ap.`academic_year` AS `Year`,

        ap.`semester_num` AS `Semester`,

        c.`name_ar` AS `Course_Name_AR`,

        c.`name_en` AS `Course_Name_EN`,

        c.`credit_hours` AS `Units`,

        e.`score` AS `Final_Score`,

        e.`passed_round` AS `Attempt_Round`

    FROM `certificate_manager`.`academic_periods` AS ap

    

    INNER JOIN `certificate_manager`.`enrollments` AS e 

        ON ap.`id` = e.`period_id`

        

    INNER JOIN `certificate_manager`.`courses` AS c 

        ON e.`course_id` = c.`id`

        

    WHERE ap.`student_id` = p_student_id

    

        ORDER BY 

        ap.`academic_year` ASC,

        ap.`semester_num` ASC;

        

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetStudentsByOrder`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetStudentsByOrder` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetStudentsByOrder`(IN p_order_id INT)
BEGIN

    SELECT s.id, s.full_name_ar, s.full_name_en, s.average, 

           s.graduation_date, s.graduation_semester, 

           d.name_ar AS dept_name_ar

    FROM students s

    JOIN departments d ON s.department_id = d.id

    WHERE s.order_id = p_order_id

    ORDER BY s.average DESC;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetStudentsPaginated`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetStudentsPaginated` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetStudentsPaginated`(
        IN p_limit INT,
        IN p_offset INT,
        IN p_search VARCHAR(150),
        IN p_dept_id INT,
        IN p_year VARCHAR(9)
    )
BEGIN
        SELECT s.id, s.full_name_ar, s.full_name_en, YEAR(s.graduation_date) AS graduation_year, s.admission_year, s.average, s.order_id, 
               d.name_ar AS dept_name_ar
        FROM students s
        LEFT JOIN departments d ON s.department_id = d.id
        WHERE (p_search IS NULL OR p_search = '' OR s.full_name_ar LIKE CONCAT('%', p_search, '%') OR s.full_name_en LIKE CONCAT('%', p_search, '%'))
          AND (p_dept_id IS NULL OR s.department_id = p_dept_id)
          AND (p_year IS NULL OR p_year = '' OR YEAR(s.graduation_date) = p_year)
        ORDER BY s.full_name_ar ASC
        LIMIT p_limit OFFSET p_offset;
    END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetStudyRoutineById`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetStudyRoutineById` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetStudyRoutineById`(
    IN p_id INT
)
BEGIN
    SELECT 
        sr.id,
        COALESCE(sr.name_ar, '') AS name_ar,
        COALESCE(sr.name_en, '') AS name_en,
        COALESCE(sr.department_id, 1) AS department_id,
        COALESCE(sr.study_system_id, 1) AS study_system_id,
        COALESCE(sr.stage_number, 1) AS stage_number,
        COALESCE(sr.semester_num, 1) AS semester_num,
        sr.created_at,
        COALESCE(d.name_ar, '') AS department_name_ar,
        COALESCE(ss.name_ar, '') AS study_system_name_ar
    FROM study_routines sr
    LEFT JOIN departments d ON sr.department_id = d.id
    LEFT JOIN study_systems ss ON sr.study_system_id = ss.id
    WHERE sr.id = p_id
    LIMIT 1;
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetStudyRoutineById`(
    IN p_id INT
)
BEGIN
    SELECT 
        sr.id,
        COALESCE(sr.name_ar, '') AS name_ar,
        COALESCE(sr.name_en, '') AS name_en,
        COALESCE(sr.department_id, 1) AS department_id,
        COALESCE(sr.study_system_id, 1) AS study_system_id,
        COALESCE(sr.stage_number, 1) AS stage_number,
        COALESCE(sr.semester_num, 1) AS semester_num,
        sr.created_at,
        COALESCE(d.name_ar, '') AS department_name_ar,
        COALESCE(ss.name_ar, '') AS study_system_name_ar
    FROM study_routines sr
    LEFT JOIN departments d ON sr.department_id = d.id
    LEFT JOIN study_systems ss ON sr.study_system_id = ss.id
    WHERE sr.id = p_id
    LIMIT 1;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetStudyRoutineCourses`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetStudyRoutineCourses` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetStudyRoutineCourses`(
    IN p_routine_id INT
)
BEGIN
    SELECT 
        src.id AS mapping_id,
        srp.routine_id,
        src.period_id,
        src.course_id,
        COALESCE(c.name_ar, '') AS course_name_ar,
        COALESCE(c.name_en, '') AS course_name_en,
        COALESCE(c.credit_hours, 0) AS credit_hours,
        COALESCE(srp.stage_number, c.stage_number, 1) AS stage_number,
        COALESCE(srp.semester_num, c.semester_num, 1) AS semester_num
    FROM study_routine_courses src
    JOIN courses c ON src.course_id = c.id
    JOIN study_routine_period srp ON src.period_id = srp.id
    WHERE srp.routine_id = p_routine_id
    ORDER BY srp.stage_number ASC, srp.semester_num ASC, c.name_ar ASC;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetStudyRoutinePeriodCourses`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetStudyRoutinePeriodCourses` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetStudyRoutinePeriodCourses`(
    IN p_period_id INT
)
BEGIN
    SELECT 
        src.id AS mapping_id,
        src.period_id,
        src.course_id,
        COALESCE(c.name_ar, '') AS course_name_ar,
        COALESCE(c.name_en, '') AS course_name_en,
        COALESCE(c.credit_hours, 0) AS credit_hours
    FROM study_routine_courses src
    JOIN courses c ON src.course_id = c.id
    WHERE src.period_id = p_period_id
    ORDER BY c.name_ar ASC;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetStudyRoutinePeriods`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetStudyRoutinePeriods` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetStudyRoutinePeriods`(
    IN p_routine_id INT
)
BEGIN
    SELECT 
        srp.id AS period_id,
        srp.routine_id,
        COALESCE(srp.stage_number, 1) AS stage_number,
        COALESCE(srp.semester_num, 1) AS semester_num
    FROM study_routine_period srp
    WHERE srp.routine_id = p_routine_id
    ORDER BY srp.stage_number ASC, srp.semester_num ASC;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetStudySystemByID`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetStudySystemByID` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetStudySystemByID`(IN p_system_id INT)
BEGIN

    SELECT * FROM study_systems WHERE id = p_system_id;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetSupervisorsByStudent`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetSupervisorsByStudent` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetSupervisorsByStudent`(IN p_student_id INT)
BEGIN
        SELECT ss.id, ss.student_id, ss.personnel_id, ss.supervision_role,
               p.name_ar AS supervisor_name_ar, p.name_en AS supervisor_name_en, p.academic_title_ar, p.academic_title_en
        FROM student_supervisors ss JOIN personnel p ON ss.personnel_id = p.id
        WHERE ss.student_id = p_student_id ORDER BY ss.supervision_role ASC, p.display_order ASC;
    END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetSystemSettings`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetSystemSettings` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetSystemSettings`()
BEGIN

    SELECT * FROM settings ORDER BY id ASC LIMIT 1;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetThesisByStudent`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetThesisByStudent` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetThesisByStudent`(IN p_student_id INT)
BEGIN
        SELECT id, student_id, title_ar, title_en, defense_date, committee_decision, final_grade
        FROM thesis_records WHERE student_id = p_student_id ORDER BY id DESC;
    END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `GetUserPreferences`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `GetUserPreferences` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `GetUserPreferences`(IN p_emp_id INT)
BEGIN CALL Get_User_Settings(p_emp_id); END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `Get_User_Settings`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `Get_User_Settings` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `Get_User_Settings`(

    IN p_emp_id INT

)
BEGIN

    SELECT 

        s.id,

        COALESCE(s.theme, 'Dark') AS theme,

        COALESCE(s.accent_color, 'blue') AS accent_color,

        COALESCE(s.font_family, 'Arial') AS font_family,

        COALESCE(s.font_size_base, 14) AS font_size_base,

        COALESCE(s.is_arabic_rtl, 1) AS is_arabic_rtl

    FROM settings s

    WHERE s.id = p_emp_id

    LIMIT 1;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `Get_dashboard_counts`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `Get_dashboard_counts` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `Get_dashboard_counts`()
BEGIN

        SELECT 

        COALESCE((SELECT COUNT(id) FROM students), 0) AS total_students,

        COALESCE((SELECT COUNT(id) FROM departments), 0) AS total_departments,

        COALESCE((SELECT COUNT(id) FROM courses), 0) AS total_courses,

        COALESCE((SELECT COUNT(id) FROM personnel), 0) AS total_personnel;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `InsertDepartment`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `InsertDepartment` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertDepartment`(

    IN p_name_ar VARCHAR(100),

    IN p_name_en VARCHAR(100),

    IN p_university_settings_id INT

)
BEGIN

    INSERT INTO departments (name_ar, name_en, university_settings_id)

    VALUES (p_name_ar, p_name_en, p_university_settings_id);

    SELECT LAST_INSERT_ID() AS new_id;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `InsertGraduationOrder`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `InsertGraduationOrder` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertGraduationOrder`(
    IN p_order_number VARCHAR(60),
    IN p_order_date DATE,
    IN p_department_id INT,
    IN p_study_type VARCHAR(50),
    IN p_graduation_year INT,
    IN p_graduation_semester VARCHAR(50),
    IN p_num_students INT,
    IN p_notes VARCHAR(255),
    IN p_study_system_id INT
)
BEGIN
    INSERT INTO graduation_orders (
        order_number, order_date, department_id, study_type, 
        graduation_year, graduation_semester, num_students, notes, study_system_id
    ) VALUES (
        p_order_number, p_order_date, p_department_id, p_study_type, 
        p_graduation_year, p_graduation_semester, p_num_students, p_notes, p_study_system_id
    );
    SELECT LAST_INSERT_ID() AS new_id;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `InsertIssuedCertificate`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `InsertIssuedCertificate` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertIssuedCertificate`(
    IN p_student_id INT,
    IN p_to_title VARCHAR(255),
    IN p_template_type VARCHAR(100),
    IN p_issue_date DATE
)
BEGIN
    INSERT INTO issued_certificates (
        student_id, 
        to_title, 
        template_type, 
        issue_date
    ) VALUES (
        p_student_id,
        COALESCE(p_to_title, 'من يهمه الأمر'),
        COALESCE(p_template_type, 'ARABIC'),
        COALESCE(p_issue_date, CURDATE())
    );
    
    SELECT LAST_INSERT_ID() AS inserted_id;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `InsertPersonnel`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `InsertPersonnel` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertPersonnel`(

    IN p_name_ar VARCHAR(80),

    IN p_name_en VARCHAR(80),

    IN p_academic_title_ar VARCHAR(50),

    IN p_academic_title_en VARCHAR(50),

    IN p_responsibility_ar VARCHAR(120),

    IN p_responsibility_en VARCHAR(120),

    IN p_display_order INT,

    IN p_username VARCHAR(50),

    IN p_password_hash VARCHAR(255),

    IN p_personnel_role VARCHAR(20),

    IN p_university_settings_id INT,

    IN p_is_active TINYINT(1)

)
BEGIN

    INSERT INTO personnel (

        name_ar,

        name_en,

        academic_title_ar,

        academic_title_en,

        responsibility_ar,

        responsibility_en,

        display_order,

        username,

        password_hash,

        personnel_role,

        university_settings_id,

        is_active

    ) VALUES (

        TRIM(p_name_ar),

        TRIM(p_name_en),

        IF(TRIM(p_academic_title_ar) = '', NULL, TRIM(p_academic_title_ar)),

        IF(TRIM(p_academic_title_en) = '', NULL, TRIM(p_academic_title_en)),

        TRIM(p_responsibility_ar),

        TRIM(p_responsibility_en),

        COALESCE(p_display_order, 0),

        TRIM(p_username),

        p_password_hash,

        COALESCE(p_personnel_role, 'user'),

        p_university_settings_id,

        COALESCE(p_is_active, 1)

    );



    SELECT LAST_INSERT_ID() AS inserted_id;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `InsertStudent`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `InsertStudent` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertStudent`(
        IN p_full_name_ar VARCHAR(150),
        IN p_full_name_en VARCHAR(150),
        IN p_gender VARCHAR(1),
        IN p_sequence_number INT,
        IN p_postgraduation_number INT,
        IN p_date_of_birth DATE,
        IN p_birthplace_id INT,
        IN p_birthplace_other VARCHAR(100),
        IN p_nationality_id INT,
        IN p_department_id INT,
        IN p_study_system_id INT,
        IN p_degree_level VARCHAR(50),
        IN p_order_id INT,
        IN p_admission_year VARCHAR(9),
        IN p_summer_training_data VARCHAR(20),
        IN p_average FLOAT,
        IN p_graduation_date DATE,
        IN p_graduation_semester VARCHAR(50)
    )
BEGIN
        INSERT INTO students (
            full_name_ar, full_name_en, gender, sequence_number, postgraduation_number, 
            date_of_birth, birthplace_id, birthplace_other, nationality_id, department_id, 
            study_system_id, degree_level, order_id, admission_year, summer_training_data, 
            average, graduation_date, graduation_semester
        ) VALUES (
            p_full_name_ar, p_full_name_en, p_gender, p_sequence_number, p_postgraduation_number, 
            p_date_of_birth, p_birthplace_id, p_birthplace_other, p_nationality_id, p_department_id, 
            p_study_system_id, p_degree_level, p_order_id, p_admission_year, p_summer_training_data, 
            p_average, p_graduation_date, p_graduation_semester
        );
        SELECT LAST_INSERT_ID() AS new_id;
    END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `InsertStudentSupervisor`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `InsertStudentSupervisor` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertStudentSupervisor`(IN p_student_id INT, IN p_personnel_id INT, IN p_supervision_role VARCHAR(50))
BEGIN
        INSERT INTO student_supervisors (student_id, personnel_id, supervision_role) VALUES (p_student_id, p_personnel_id, p_supervision_role);
        SELECT LAST_INSERT_ID() AS new_id;
    END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `InsertStudyRoutine`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `InsertStudyRoutine` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertStudyRoutine`(
    IN p_name_ar VARCHAR(150),
    IN p_name_en VARCHAR(150),
    IN p_department_id INT,
    IN p_study_system_id INT
)
BEGIN
    INSERT INTO study_routines (
        name_ar, name_en, department_id, study_system_id
    ) VALUES (
        TRIM(p_name_ar), TRIM(p_name_en), p_department_id, COALESCE(p_study_system_id, 1)
    );
    SELECT LAST_INSERT_ID() AS inserted_id;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `InsertStudyRoutineCourse`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `InsertStudyRoutineCourse` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertStudyRoutineCourse`(
    IN p_routine_id INT,
    IN p_course_id INT
)
BEGIN
    INSERT IGNORE INTO study_routine_courses (routine_id, course_id) 
    VALUES (p_routine_id, p_course_id);
    
    SELECT LAST_INSERT_ID() AS inserted_id;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `InsertStudyRoutinePeriod`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `InsertStudyRoutinePeriod` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertStudyRoutinePeriod`(
    IN p_routine_id INT,
    IN p_stage_number INT,
    IN p_semester_num INT
)
BEGIN
    INSERT INTO study_routine_period (
        routine_id, stage_number, semester_num
    ) VALUES (
        p_routine_id, COALESCE(p_stage_number, 1), COALESCE(p_semester_num, 1)
    );
    SELECT LAST_INSERT_ID() AS inserted_id;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `InsertStudyRoutinePeriodCourse`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `InsertStudyRoutinePeriodCourse` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertStudyRoutinePeriodCourse`(
    IN p_period_id INT,
    IN p_course_id INT
)
BEGIN
    INSERT IGNORE INTO study_routine_courses (period_id, course_id) 
    VALUES (p_period_id, p_course_id);
    
    SELECT LAST_INSERT_ID() AS inserted_id;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `InsertStudySystem`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `InsertStudySystem` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertStudySystem`(

    IN p_name_ar VARCHAR(60),

    IN p_name_en VARCHAR(60),

    IN p_study_day_type VARCHAR(50),

    IN p_calculation_rule VARCHAR(50),

    IN p_calculation_weights VARCHAR(100),

    IN p_period_display VARCHAR(50),

    IN p_is_active TINYINT(1)

)
BEGIN

    INSERT INTO study_systems (name_ar, name_en, study_day_type, calculation_rule, calculation_weights, period_display, is_active)

    VALUES (p_name_ar, p_name_en, p_study_day_type, p_calculation_rule, p_calculation_weights, p_period_display, p_is_active);

    SELECT LAST_INSERT_ID() AS new_id;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `InsertThesis`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `InsertThesis` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `InsertThesis`(
        IN p_student_id INT, IN p_title_ar VARCHAR(500), IN p_title_en VARCHAR(500),
        IN p_defense_date DATE, IN p_committee_decision VARCHAR(100), IN p_final_grade FLOAT
    )
BEGIN
        INSERT INTO thesis_records (student_id, title_ar, title_en, defense_date, committee_decision, final_grade) 
        VALUES (p_student_id, p_title_ar, p_title_en, p_defense_date, p_committee_decision, p_final_grade);
        SELECT LAST_INSERT_ID() AS new_id;
    END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `LinkStudentsToOrder`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `LinkStudentsToOrder` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `LinkStudentsToOrder`(IN p_order_id INT)
BEGIN
    DECLARE v_dept_id INT;
    DECLARE v_year INT;
    DECLARE v_study_system_id INT;
    DECLARE v_date DATE;
    DECLARE v_sem VARCHAR(50);

    SELECT department_id, graduation_year, study_system_id, order_date, graduation_semester
    INTO v_dept_id, v_year, v_study_system_id, v_date, v_sem
    FROM graduation_orders WHERE id = p_order_id;

    UPDATE students 
    SET order_id = p_order_id, 
        graduation_date = v_date, 
        graduation_semester = v_sem
    WHERE department_id = v_dept_id 
      AND study_system_id = v_study_system_id
      AND YEAR(graduation_date) = v_year
      AND order_id IS NULL;
      
    SELECT ROW_COUNT() AS affected_rows;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `SearchStudentByName`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `SearchStudentByName` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `SearchStudentByName`(

    IN p_search_name VARCHAR(150)

)
BEGIN

    SELECT 

        s.`id` AS `Student_ID`,

        s.`full_name_ar` AS `Arabic_Name`,

        s.`full_name_en` AS `English_Name`,

        d.`name_ar` AS `Department`,

        s.`admission_year` AS `Admission_Year`,

        s.`study_system_id` AS `System_ID`

    FROM `certificate_manager`.`students` AS s

    LEFT JOIN `certificate_manager`.`departments` AS d 

        ON s.`department_id` = d.`id`

    WHERE s.`full_name_ar` LIKE CONCAT('%', TRIM(p_search_name), '%')

       OR s.`full_name_en` LIKE CONCAT('%', TRIM(p_search_name), '%')

    ORDER BY s.`full_name_ar` ASC;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `SearchStudentsBasic`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `SearchStudentsBasic` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `SearchStudentsBasic`(
        IN p_search_term VARCHAR(255),
        IN p_limit INT
    )
BEGIN
        SET p_search_term = TRIM(p_search_term);

        IF CHAR_LENGTH(p_search_term) < 2 THEN
            SELECT 
                s.id AS student_id,
                s.full_name_ar AS name_ar,
                s.full_name_en AS name_en,
                d.name_ar AS dept_name_ar,
                YEAR(s.graduation_date) AS graduation_year,
                s.admission_year,
                s.average
            FROM students s
            LEFT JOIN departments d ON s.department_id = d.id
            WHERE 1 = 0;
        ELSE
            SELECT 
                s.id AS student_id,
                s.full_name_ar AS name_ar,
                s.full_name_en AS name_en,
                d.name_ar AS dept_name_ar,
                YEAR(s.graduation_date) AS graduation_year,
                s.admission_year,
                s.average
            FROM 
                students s
            LEFT JOIN departments d ON s.department_id = d.id
            WHERE 
                s.full_name_ar LIKE CONCAT('%', p_search_term, '%') 
                OR s.full_name_en LIKE CONCAT('%', p_search_term, '%')
            ORDER BY
                CASE 
                    WHEN s.full_name_ar = p_search_term OR s.full_name_en = p_search_term THEN 1
                    WHEN s.full_name_ar LIKE CONCAT(p_search_term, '%') OR s.full_name_en LIKE CONCAT(p_search_term, '%') THEN 2
                    ELSE 3 
                END,
                s.full_name_ar ASC
            LIMIT p_limit;
        END IF;
    END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `SearchStudentsPaginated`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `SearchStudentsPaginated` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `SearchStudentsPaginated`(

    IN p_search_term VARCHAR(255),

    IN p_limit INT,

    IN p_offset INT

)
BEGIN

    SET p_search_term = TRIM(COALESCE(p_search_term, ''));



        IF CHAR_LENGTH(p_search_term) < 2 THEN

        SELECT 

            s.id AS student_id,

            COALESCE(s.full_name_ar, 'Unknown') AS name_ar,

            COALESCE(s.full_name_en, 'Unknown') AS name_en,

            COALESCE(d.name_ar, 'Unknown') AS department_name_ar,

            COALESCE(YEAR(s.graduation_date), 'N/A') AS graduation_year,

            COALESCE(s.average, 0.0) AS average

        FROM students s

        LEFT JOIN departments d ON s.department_id = d.id

        ORDER BY s.id DESC

        LIMIT p_limit OFFSET p_offset;

    ELSE

                SELECT 

            s.id AS student_id,

            COALESCE(s.full_name_ar, 'Unknown') AS name_ar,

            COALESCE(s.full_name_en, 'Unknown') AS name_en,

            COALESCE(d.name_ar, 'Unknown') AS department_name_ar,

            COALESCE(YEAR(s.graduation_date), 'N/A') AS graduation_year,

            COALESCE(s.average, 0.0) AS average

        FROM students s

        LEFT JOIN departments d ON s.department_id = d.id

        WHERE 

            s.full_name_ar LIKE CONCAT('%', p_search_term, '%')

            OR s.full_name_en LIKE CONCAT('%', p_search_term, '%')

        ORDER BY 

            CASE 

                WHEN s.full_name_ar = p_search_term OR s.full_name_en = p_search_term THEN 1 

                WHEN s.full_name_ar LIKE CONCAT(p_search_term, '%') OR s.full_name_en LIKE CONCAT(p_search_term, '%') THEN 2 

                ELSE 3 

            END, 

            s.full_name_ar ASC

        LIMIT p_limit OFFSET p_offset;

    END IF;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `UnlinkStudentFromOrder`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `UnlinkStudentFromOrder` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `UnlinkStudentFromOrder`(IN p_student_id INT)
BEGIN

    UPDATE students 

    SET order_id = NULL, 

        graduation_date = NULL, 

        graduation_semester = NULL 

    WHERE id = p_student_id;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `UpdateDepartment`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `UpdateDepartment` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateDepartment`(

    IN p_id INT,

    IN p_name_ar VARCHAR(100),

    IN p_name_en VARCHAR(100),

    IN p_university_settings_id INT

)
BEGIN

    UPDATE departments

    SET name_ar = p_name_ar,

        name_en = p_name_en,

        university_settings_id = p_university_settings_id

    WHERE id = p_id;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `UpdateGraduationOrder`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `UpdateGraduationOrder` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateGraduationOrder`(
    IN p_id INT,
    IN p_order_number VARCHAR(60),
    IN p_order_date DATE,
    IN p_department_id INT,
    IN p_study_type VARCHAR(50),
    IN p_graduation_year INT,
    IN p_graduation_semester VARCHAR(50),
    IN p_num_students INT,
    IN p_notes VARCHAR(255),
    IN p_study_system_id INT
)
BEGIN
    UPDATE graduation_orders
    SET order_number = p_order_number,
        order_date = p_order_date,
        department_id = p_department_id,
        study_type = p_study_type,
        graduation_year = p_graduation_year,
        graduation_semester = p_graduation_semester,
        num_students = p_num_students,
        notes = p_notes,
        study_system_id = p_study_system_id
    WHERE id = p_id;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `UpdateIssuedCertificate`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `UpdateIssuedCertificate` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateIssuedCertificate`(
    IN p_id INT,
    IN p_student_id INT,
    IN p_to_title VARCHAR(255),
    IN p_template_type VARCHAR(100),
    IN p_issue_date DATE
)
BEGIN
    UPDATE issued_certificates SET 
        student_id = COALESCE(p_student_id, student_id),
        to_title = COALESCE(p_to_title, to_title),
        template_type = COALESCE(p_template_type, template_type),
        issue_date = COALESCE(p_issue_date, issue_date)
    WHERE id = p_id;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `UpdatePersonnel`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `UpdatePersonnel` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdatePersonnel`(

    IN p_id INT,

    IN p_name_ar VARCHAR(80),

    IN p_name_en VARCHAR(80),

    IN p_academic_title_ar VARCHAR(50),

    IN p_academic_title_en VARCHAR(50),

    IN p_responsibility_ar VARCHAR(120),

    IN p_responsibility_en VARCHAR(120),

    IN p_display_order INT,

    IN p_username VARCHAR(50),

    IN p_personnel_role VARCHAR(20),

    IN p_university_settings_id INT,

    IN p_is_active TINYINT(1)

)
BEGIN

    UPDATE personnel

    SET 

        name_ar = TRIM(p_name_ar),

        name_en = TRIM(p_name_en),

        academic_title_ar = IF(TRIM(p_academic_title_ar) = '', NULL, TRIM(p_academic_title_ar)),

        academic_title_en = IF(TRIM(p_academic_title_en) = '', NULL, TRIM(p_academic_title_en)),

        responsibility_ar = TRIM(p_responsibility_ar),

        responsibility_en = TRIM(p_responsibility_en),

        display_order = COALESCE(p_display_order, 0),

        username = TRIM(p_username),

        personnel_role = COALESCE(p_personnel_role, 'user'),

        university_settings_id = p_university_settings_id,

        is_active = COALESCE(p_is_active, 1)

    WHERE id = p_id;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `UpdateStudent`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `UpdateStudent` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateStudent`(
        IN p_id INT,
        IN p_full_name_ar VARCHAR(150),
        IN p_full_name_en VARCHAR(150),
        IN p_gender VARCHAR(1),
        IN p_sequence_number INT,
        IN p_postgraduation_number INT,
        IN p_date_of_birth DATE,
        IN p_birthplace_id INT,
        IN p_birthplace_other VARCHAR(100),
        IN p_nationality_id INT,
        IN p_department_id INT,
        IN p_study_system_id INT,
        IN p_degree_level VARCHAR(50),
        IN p_order_id INT,
        IN p_admission_year VARCHAR(9),
        IN p_summer_training_data VARCHAR(20),
        IN p_average FLOAT,
        IN p_graduation_date DATE,
        IN p_graduation_semester VARCHAR(50)
    )
BEGIN
        UPDATE students
        SET full_name_ar = p_full_name_ar,
            full_name_en = p_full_name_en,
            gender = p_gender,
            sequence_number = p_sequence_number,
            postgraduation_number = p_postgraduation_number,
            date_of_birth = p_date_of_birth,
            birthplace_id = p_birthplace_id,
            birthplace_other = p_birthplace_other,
            nationality_id = p_nationality_id,
            department_id = p_department_id,
            study_system_id = p_study_system_id,
            degree_level = p_degree_level,
            order_id = p_order_id,
            admission_year = p_admission_year,
            summer_training_data = p_summer_training_data,
            average = p_average,
            graduation_date = p_graduation_date,
            graduation_semester = p_graduation_semester
        WHERE id = p_id;
    END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `UpdateStudentSupervisor`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `UpdateStudentSupervisor` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateStudentSupervisor`(IN p_id INT, IN p_personnel_id INT, IN p_supervision_role VARCHAR(50))
BEGIN
        UPDATE student_supervisors SET personnel_id = p_personnel_id, supervision_role = p_supervision_role WHERE id = p_id;
    END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `UpdateStudyRoutine`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `UpdateStudyRoutine` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateStudyRoutine`(
    IN p_id INT,
    IN p_name_ar VARCHAR(150),
    IN p_name_en VARCHAR(150),
    IN p_department_id INT,
    IN p_study_system_id INT
)
BEGIN
    UPDATE study_routines SET 
        name_ar = TRIM(COALESCE(p_name_ar, name_ar)),
        name_en = TRIM(COALESCE(p_name_en, name_en)),
        department_id = COALESCE(p_department_id, department_id),
        study_system_id = COALESCE(p_study_system_id, study_system_id)
    WHERE id = p_id;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `UpdateStudyRoutinePeriod`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `UpdateStudyRoutinePeriod` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateStudyRoutinePeriod`(
    IN p_period_id INT,
    IN p_stage_number INT,
    IN p_semester_num INT
)
BEGIN
    UPDATE study_routine_period SET 
        stage_number = COALESCE(p_stage_number, stage_number),
        semester_num = COALESCE(p_semester_num, semester_num)
    WHERE id = p_period_id;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `UpdateStudySystem`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `UpdateStudySystem` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateStudySystem`(

    IN p_id INT,

    IN p_name_ar VARCHAR(60),

    IN p_name_en VARCHAR(60),

    IN p_study_day_type VARCHAR(50),

    IN p_calculation_rule VARCHAR(50),

    IN p_calculation_weights VARCHAR(100),

    IN p_period_display VARCHAR(50),

    IN p_is_active TINYINT(1)

)
BEGIN

    UPDATE study_systems

    SET name_ar = p_name_ar,

        name_en = p_name_en,

        study_day_type = p_study_day_type,

        calculation_rule = p_calculation_rule,

        calculation_weights = p_calculation_weights,

        period_display = p_period_display,

        is_active = p_is_active

    WHERE id = p_id;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `UpdateSystemSettings`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `UpdateSystemSettings` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateSystemSettings`(

    IN p_id INT,

    IN p_theme VARCHAR(20),

    IN p_accent_color VARCHAR(20),

    IN p_font_family VARCHAR(100),

    IN p_font_size_base INT,

    IN p_is_arabic_rtl TINYINT(1)

)
BEGIN

    UPDATE settings 

    SET theme = p_theme,

        accent_color = p_accent_color,

        font_family = p_font_family,

        font_size_base = p_font_size_base,

        is_arabic_rtl = p_is_arabic_rtl

    WHERE id = p_id;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `UpdateThesis`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `UpdateThesis` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateThesis`(
        IN p_id INT, IN p_title_ar VARCHAR(500), IN p_title_en VARCHAR(500),
        IN p_defense_date DATE, IN p_committee_decision VARCHAR(100), IN p_final_grade FLOAT
    )
BEGIN
        UPDATE thesis_records SET title_ar = p_title_ar, title_en = p_title_en, defense_date = p_defense_date, 
            committee_decision = p_committee_decision, final_grade = p_final_grade WHERE id = p_id;
    END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `UpdateUserPreferences`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `UpdateUserPreferences` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateUserPreferences`(

    IN p_id INT,

    IN p_theme VARCHAR(20),

    IN p_accent_color VARCHAR(20),

    IN p_font_family VARCHAR(100),

    IN p_font_size_base INT,

    IN p_is_arabic_rtl TINYINT(1)

)
BEGIN

    INSERT INTO settings (id, theme, accent_color, font_family, font_size_base, is_arabic_rtl)

    VALUES (p_id, p_theme, p_accent_color, p_font_family, p_font_size_base, p_is_arabic_rtl)

    ON DUPLICATE KEY UPDATE

        theme = VALUES(theme),

        accent_color = VALUES(accent_color),

        font_family = VALUES(font_family),

        font_size_base = VALUES(font_size_base),

        is_arabic_rtl = VALUES(is_arabic_rtl);

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `Update_User_Settings`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `Update_User_Settings` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `Update_User_Settings`(

    IN p_EMP_ID INT,

    IN p_theme VARCHAR(20),

    IN p_accent_color VARCHAR(20),

    IN p_font_family VARCHAR(100),

    IN p_font_size_base INT,

    IN p_is_arabic_rtl TINYINT

)
BEGIN

    IF EXISTS (SELECT 1 FROM settings WHERE EMP_ID = p_EMP_ID) THEN

        UPDATE settings

        SET 

            theme = p_theme,

            accent_color = p_accent_color,

            font_family = p_font_family,

            font_size_base = p_font_size_base,

            is_arabic_rtl = p_is_arabic_rtl

        WHERE EMP_ID = p_EMP_ID;

    ELSE

        INSERT INTO settings (EMP_ID, theme, accent_color, font_family, font_size_base, is_arabic_rtl)

        VALUES (p_EMP_ID, p_theme, p_accent_color, p_font_family, p_font_size_base, p_is_arabic_rtl);

    END IF;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `sp_GetCertificate_AcademicCourses`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_AcademicCourses` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_AcademicCourses`(
    IN `p_student_id` INT, 
    IN `p_grouping_mode` VARCHAR(50)
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
        ELSEIF p_grouping_mode = 'BY_ByAcademicYear' THEN
                        CALL sp_GetCertificate_Courses_Yearly_ByAcademicYear(p_student_id);
        ELSE
            CALL sp_GetCertificate_Yearly_ByAcademicDefualte(p_student_id);
        END IF;
    END IF;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `sp_GetCertificate_AcademicTimeline`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_AcademicTimeline` //
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

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `sp_GetCertificate_Courses_Semester_ByStage`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_Courses_Semester_ByStage` //
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
   COALESCE(c.name_en, c.name_ar, '') AS subject_name_en,
   COALESCE(c.name_ar, '') AS subject_name_ar,
   COALESCE(c.name_en, c.name_ar, '') AS course_name_en,
   COALESCE(c.name_ar, '') AS course_name_ar,

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

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `sp_GetCertificate_Courses_Semester_ByYear`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_Courses_Semester_ByYear` //
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
   COALESCE(c.name_en, c.name_ar, '') AS subject_name_en,
   COALESCE(c.name_ar, '') AS subject_name_ar,
   COALESCE(c.name_en, c.name_ar, '') AS course_name_en,
   COALESCE(c.name_ar, '') AS course_name_ar,

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

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `sp_GetCertificate_Courses_Yearly_ByAcademicYear`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_Courses_Yearly_ByAcademicYear` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_Courses_Yearly_ByAcademicYear`(IN `p_student_id` INT)
BEGIN

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

   COALESCE(c.name_en, '') AS course_name_en,
   COALESCE(c.name_ar, '') AS course_name_ar,

    COALESCE(c.credit_hours, 0) AS unit,

    COALESCE(e.score, 0.0) AS mark,

    COALESCE(e.passed_round, 1) AS passed_round,

    CASE

        WHEN COALESCE(c.stage_number, ap.stage_number) < ap.stage_number THEN 'عبور'

        ELSE 'أساسي'

    END AS course_type,

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

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `sp_GetCertificate_Courses_Yearly_ByCurriculumStage`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_Courses_Yearly_ByCurriculumStage` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_Courses_Yearly_ByCurriculumStage`(IN `p_student_id` INT)
BEGIN

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

   COALESCE(c.name_en, c.name_ar, '') AS course_name_en,
   COALESCE(c.name_ar, '') AS course_name_ar,

    COALESCE(c.credit_hours, 0) AS unit,

    COALESCE(e.score, 0.0) AS mark,

    COALESCE(e.passed_round, 1) AS passed_round,

    CASE

        WHEN COALESCE(c.stage_number, ap.stage_number) < ap.stage_number THEN 'عبور'

        ELSE 'أساسي'

    END AS course_type,

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



END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `sp_GetCertificate_Courses_Yearly_ByPeriodStage`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_Courses_Yearly_ByPeriodStage` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_Courses_Yearly_ByPeriodStage`(IN `p_student_id` INT)
BEGIN

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

   COALESCE(c.name_en, '') AS course_name_en,
   COALESCE(c.name_ar, '') AS course_name_ar,

    COALESCE(c.credit_hours, 0) AS unit,

    COALESCE(e.score, 0.0) AS mark,

    COALESCE(e.passed_round, 1) AS passed_round,

    CASE

        WHEN COALESCE(c.stage_number, ap.stage_number) < ap.stage_number THEN 'عبور'

        ELSE 'أساسي'

    END AS course_type,

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

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `sp_GetCertificate_Ranking`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_Ranking` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_Ranking`(IN `p_student_id` INT)
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

            SELECT 
            CAST(COALESCE(MAX(average), 0.0) AS DECIMAL(5, 3)) AS top_average

            FROM students s4 

            WHERE s4.department_id = v_dept_id 

              AND YEAR(s4.graduation_date) = v_grad_year

        ) AS top_average;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `sp_GetCertificate_Signers`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_Signers` //
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

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `sp_GetCertificate_StudentInfo`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_StudentInfo` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_StudentInfo`(IN `p_student_id` INT)
BEGIN

    SELECT 
        s.id AS student_id,
        COALESCE(s.full_name_ar, '') AS full_name_ar,
        COALESCE(s.full_name_en, '') AS full_name_en,
        CAST(COALESCE(s.average, 0.0) AS DECIMAL(5, 3)) AS average,
        COALESCE(YEAR(s.graduation_date), 0) AS graduation_year,
        COALESCE(s.graduation_date, '1970-01-01') AS graduation_date,
        COALESCE(s.graduation_semester, 1) AS graduation_semester,
        COALESCE(s.date_of_birth, '1970-01-01') AS date_of_birth,
        COALESCE(s.sequence_number, 0) AS sequence_number,
        
        CASE 
            WHEN s.postgraduation_number = 0 OR s.postgraduation_number IS NULL 
            THEN COALESCE(o.num_students, '')  
            ELSE COALESCE(s.postgraduation_number, '')  
        END AS postgraduation_number,
        
        COALESCE(s.admission_year, 0) AS admission_year,
        COALESCE(s.summer_training_data, '') AS summer_training_data,
        COALESCE(s.order_id, 0) AS order_id,

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
        
        CASE 
            WHEN s.nationality_id != 274 THEN COALESCE(s.birthplace_other, '') 
            ELSE COALESCE(g.name_ar, '')  
        END AS birthplace_ar,
    
        CASE 
            WHEN s.nationality_id != 274 THEN COALESCE(s.birthplace_other, '')  
            ELSE COALESCE(g.name_en, '')  
        END AS birthplace_en,

        COALESCE(o.order_number, '') AS order_number, 
        COALESCE(o.order_date, '1970-01-01') AS order_date

    FROM students s 
    LEFT JOIN departments d ON s.department_id = d.id 
    LEFT JOIN study_systems ss ON s.study_system_id = ss.id 
    LEFT JOIN countries c ON s.nationality_id = c.id 
    LEFT JOIN governorates g ON s.birthplace_id = g.id 
    LEFT JOIN graduation_orders o ON s.order_id = o.id 
    WHERE s.id = p_student_id
    LIMIT 1;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `sp_GetCertificate_UniversitySettings`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_UniversitySettings` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_UniversitySettings`()
BEGIN

    SELECT * 

    FROM university_settings 

    ORDER BY id ASC 

    LIMIT 1;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `sp_GetCertificate_Yearly_ByAcademicDefualte`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_Yearly_ByAcademicDefualte` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_Yearly_ByAcademicDefualte`(
    IN p_student_id INT
)
BEGIN
    SELECT 
        s.id AS student_id,
        COALESCE(s.full_name_ar, '') AS student_name_ar,
        COALESCE(ss.name_ar, '') AS study_system_ar,
        COALESCE(ap_target.academic_year, '') AS academic_year,
        GROUP_CONCAT(DISTINCT ap_target.stage_number ORDER BY ap_target.stage_number ASC SEPARATOR ', ') AS stages,
        COUNT(cd.course_id) AS total_courses,
        GROUP_CONCAT(
            CONCAT(
                cd.name_ar, 
                ' (مرحلة ', cd.default_stage, ' - دور ', COALESCE(cd.max_round, 1), ')',
                ': ', COALESCE(cd.max_score, 0.0)
            ) 
            ORDER BY cd.default_stage ASC, cd.name_ar ASC 
            SEPARATOR ' | '
        ) AS courses_and_degrees
    FROM students s
    LEFT JOIN study_systems ss ON s.study_system_id = ss.id
        LEFT JOIN (
        SELECT 
            cp.course_id,
            cp.name_ar,
            cp.default_stage,
            cp.max_score,
            cp.max_round,
            CASE 
                WHEN cp.first_status = 'FAILED_REPEAT' THEN 
                    COALESCE(
                        (SELECT ap_next.id 
                         FROM academic_periods ap_next 
                         WHERE ap_next.student_id = p_student_id 
                           AND ap_next.stage_number = cp.first_stage 
                           AND ap_next.academic_year > cp.first_year 
                         ORDER BY ap_next.academic_year ASC LIMIT 1),
                        cp.first_period_id
                    )
                ELSE cp.first_period_id 
            END AS target_period_id
        FROM (
            SELECT 
                c.id AS course_id,
                c.name_ar,
                COALESCE(c.stage_number, MIN(ap.stage_number)) AS default_stage,
                MAX(e.score) AS max_score,
                MAX(e.passed_round) AS max_round,
                MIN(ap.academic_year) AS first_year,
                                (SELECT ap_sub.id 
                 FROM enrollments e_sub 
                 JOIN academic_periods ap_sub ON e_sub.period_id = ap_sub.id 
                 WHERE e_sub.course_id = c.id AND ap_sub.student_id = p_student_id 
                 ORDER BY ap_sub.academic_year ASC, ap_sub.stage_number ASC LIMIT 1) AS first_period_id,
                (SELECT COALESCE(ap_sub2.result_status, '') 
                 FROM enrollments e_sub2 
                 JOIN academic_periods ap_sub2 ON e_sub2.period_id = ap_sub2.id 
                 WHERE e_sub2.course_id = c.id AND ap_sub2.student_id = p_student_id 
                 ORDER BY ap_sub2.academic_year ASC, ap_sub2.stage_number ASC LIMIT 1) AS first_status,
                (SELECT ap_sub3.stage_number 
                 FROM enrollments e_sub3 
                 JOIN academic_periods ap_sub3 ON e_sub3.period_id = ap_sub3.id 
                 WHERE e_sub3.course_id = c.id AND ap_sub3.student_id = p_student_id 
                 ORDER BY ap_sub3.academic_year ASC, ap_sub3.stage_number ASC LIMIT 1) AS first_stage
            FROM enrollments e
            JOIN academic_periods ap ON e.period_id = ap.id
            JOIN courses c ON e.course_id = c.id
            WHERE ap.student_id = p_student_id
            GROUP BY c.id, c.name_ar, c.stage_number
        ) cp
    ) cd ON 1=1
        LEFT JOIN academic_periods ap_target ON cd.target_period_id = ap_target.id
    WHERE s.id = p_student_id
    GROUP BY 
        s.id, 
        s.full_name_ar, 
        ss.name_ar, 
        ap_target.academic_year
    ORDER BY 
        ap_target.academic_year ASC;
END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `sp_GetCertificate_Yearly_ByAcademicYear`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_Yearly_ByAcademicYear` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_Yearly_ByAcademicYear`(

    IN p_student_id INT

)
BEGIN

    SELECT 

        s.id AS student_id,

        COALESCE(s.full_name_ar, '') AS student_name_ar,

        COALESCE(ss.name_ar, '') AS study_system_ar,

        COALESCE(ap.academic_year, '') AS academic_year,

        GROUP_CONCAT(DISTINCT ap.stage_number ORDER BY ap.stage_number ASC SEPARATOR ', ') AS stages,

        COUNT(c.id) AS total_courses,

        GROUP_CONCAT(

            CONCAT(

                c.name_ar, 

                ' (مرحلة ', COALESCE(c.stage_number, ap.stage_number), ' - دور ', e.passed_round, ')',

                ': ', COALESCE(e.score, 0.0)

            ) 

            ORDER BY ap.stage_number ASC, c.name_ar ASC 

            SEPARATOR ' | '

        ) AS courses_and_degrees

    FROM students s

    LEFT JOIN study_systems ss ON s.study_system_id = ss.id

    JOIN academic_periods ap ON ap.student_id = s.id

    JOIN enrollments e ON e.period_id = ap.id

    JOIN courses c ON e.course_id = c.id

    WHERE s.id = p_student_id

    GROUP BY 

        s.id, 

        s.full_name_ar, 

        ss.name_ar, 

        ap.academic_year

    ORDER BY 

        ap.academic_year ASC;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `sp_GetCertificate_Yearly_ByCurriculumStage`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_Yearly_ByCurriculumStage` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_Yearly_ByCurriculumStage`(

    IN p_student_id INT

)
BEGIN

    SELECT 

        s.id AS student_id,

        COALESCE(s.full_name_ar, '') AS student_name_ar,

        COALESCE(ss.name_ar, '') AS study_system_ar,

        COALESCE(c.stage_number, ap.stage_number) AS curriculum_stage,

        GROUP_CONCAT(DISTINCT ap.academic_year ORDER BY ap.academic_year ASC SEPARATOR ', ') AS academic_years,

        COUNT(c.id) AS total_courses,

        GROUP_CONCAT(

            CONCAT(

                c.name_ar, 

                ' (سنة الإنجاز: ', ap.academic_year, ' - دور ', e.passed_round, ')',

                ': ', COALESCE(e.score, 0.0)

            ) 

            ORDER BY ap.academic_year ASC, c.name_ar ASC 

            SEPARATOR ' | '

        ) AS courses_and_degrees

    FROM students s

    LEFT JOIN study_systems ss ON s.study_system_id = ss.id

    JOIN academic_periods ap ON ap.student_id = s.id

    JOIN enrollments e ON e.period_id = ap.id

    JOIN courses c ON e.course_id = c.id

    WHERE s.id = p_student_id

    GROUP BY 

        s.id, 

        s.full_name_ar, 

        ss.name_ar, 

        COALESCE(c.stage_number, ap.stage_number)

    ORDER BY 

        curriculum_stage ASC;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `sp_GetCertificate_Yearly_ByPeriodStage`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_Yearly_ByPeriodStage` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_Yearly_ByPeriodStage`(

    IN p_student_id INT

)
BEGIN

    SELECT 

        s.id AS student_id,

        COALESCE(s.full_name_ar, '') AS student_name_ar,

        COALESCE(ss.name_ar, '') AS study_system_ar,

        COALESCE(ap.stage_number, 1) AS period_stage,

        GROUP_CONCAT(DISTINCT ap.academic_year ORDER BY ap.academic_year ASC SEPARATOR ', ') AS academic_years,

        COUNT(c.id) AS total_courses,

        GROUP_CONCAT(

            CONCAT(

                c.name_ar, 

                ' (سنة ', ap.academic_year, ' - دور ', e.passed_round, ')',

                ': ', COALESCE(e.score, 0.0)

            ) 

            ORDER BY ap.academic_year ASC, c.name_ar ASC 

            SEPARATOR ' | '

        ) AS courses_and_degrees

    FROM students s

    LEFT JOIN study_systems ss ON s.study_system_id = ss.id

    JOIN academic_periods ap ON ap.student_id = s.id

    JOIN enrollments e ON e.period_id = ap.id

    JOIN courses c ON e.course_id = c.id

    WHERE s.id = p_student_id

    GROUP BY 

        s.id, 

        s.full_name_ar, 

        ss.name_ar, 

        ap.stage_number

    ORDER BY 

        period_stage ASC;

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `sp_GetFullCertificateData`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetFullCertificateData` //
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

    

END //
DELIMITER ;

-- --------------------------------------------------------
-- Stored Procedure `UpdateStudyRoutine`
-- --------------------------------------------------------
DELIMITER //
DROP PROCEDURE IF EXISTS `UpdateStudyRoutine` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `UpdateStudyRoutine`(
    IN p_id INT,
    IN p_name_ar VARCHAR(150),
    IN p_name_en VARCHAR(150),
    IN p_department_id INT,
    IN p_study_system_id INT
)
BEGIN
    DECLARE v_duplicate_count INT DEFAULT 0;
    
    -- Clean inputs to prevent whitespace duplication bypassing the check
    SET p_name_ar = TRIM(p_name_ar);
    SET p_name_en = TRIM(p_name_en);

    -- Check if another routine has the exact same constraints
    SELECT COUNT(*) INTO v_duplicate_count
    FROM study_routines
    WHERE name_ar = p_name_ar 
      AND department_id = p_department_id 
      AND study_system_id = p_study_system_id
      AND id != p_id; -- Ignore the current routine being edited

    IF v_duplicate_count > 0 THEN
        -- Throw a clear database exception if a duplicate is found
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Duplicate entry: A routine with this name already exists in this department and study system.';
    ELSE
        -- Safe to update
        UPDATE study_routines SET 
            name_ar = COALESCE(p_name_ar, name_ar),
            name_en = COALESCE(p_name_en, name_en),
            department_id = COALESCE(p_department_id, department_id),
            study_system_id = COALESCE(p_study_system_id, study_system_id)
        WHERE id = p_id;
    END IF;
END //
DELIMITER ;

