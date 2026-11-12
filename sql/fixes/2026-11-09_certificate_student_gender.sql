-- 2026-11-09: sp_GetCertificate_StudentInfo now returns the student's gender,
-- so the issue screen offers only templates tagged for that gender.
-- Safe to run more than once. Run on the server database:
--   mysql -u root -p certificate_manager < sql/fixes/2026-11-09_certificate_student_gender.sql

DELIMITER //
DROP PROCEDURE IF EXISTS `sp_GetCertificate_StudentInfo` //
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_GetCertificate_StudentInfo`(IN `p_student_id` INT)
BEGIN
    SELECT 
        s.id AS student_id,
        COALESCE(s.full_name_ar, '') AS full_name_ar,
        COALESCE(s.full_name_en, '') AS full_name_en,
        COALESCE(s.gender, '') AS gender,
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
        COALESCE(s.national_id, '') AS national_id,
        
        CASE 
            WHEN s.nationality_id != 274 THEN COALESCE(s.birthplace_other, '') 
            ELSE COALESCE(g.name_ar, '')  
        END AS birthplace_ar,
    
        CASE 
            WHEN s.nationality_id != 274 THEN COALESCE(s.birthplace_other, '')  
            ELSE COALESCE(g.name_en, '')  
        END AS birthplace_en,

        COALESCE(o.order_number, '') AS order_number, 
        COALESCE(o.order_date, '1970-01-01') AS order_date,

        COALESCE(us.id, 1) AS university_settings_id,
        COALESCE(us.univ_name_ar, '') AS univ_name_ar,
        COALESCE(us.univ_name_en, '') AS univ_name_en,
        COALESCE(us.college_name_ar, '') AS college_name_ar,
        COALESCE(us.college_name_en, '') AS college_name_en

    FROM students s 
    LEFT JOIN departments d ON s.department_id = d.id 
    LEFT JOIN study_systems ss ON s.study_system_id = ss.id 
    LEFT JOIN countries c ON s.nationality_id = c.id 
    LEFT JOIN governorates g ON s.birthplace_id = g.id 
    LEFT JOIN graduation_orders o ON s.order_id = o.id 
    LEFT JOIN university_settings us ON us.id = COALESCE(
        (SELECT id FROM university_settings WHERE id = d.university_settings_id LIMIT 1),
        (SELECT id FROM university_settings ORDER BY id ASC LIMIT 1)
    )
    WHERE s.id = p_student_id
    LIMIT 1;
END //
DELIMITER ;
