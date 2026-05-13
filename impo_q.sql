SELECT ap.student_id AS id_student, st.full_name_en, ap.academic_year AS yearr, CONCAT('مرحلة ', ap.stage_number) AS stage, ap.semester_num AS course_term, e.id AS courses FROM academic_periods ap JOIN students st ON ap.student_id = st.id JOIN enrollments e ON ap.id = e.period_id WHERE ap.student_id = 139 ORDER BY stage ASC, course_term ASC, yearr ASC;

SELECT ap.student_id AS id_student, ap.academic_year AS yearr, CONCAT('مرحلة ', ap.stage_number) AS stage, ap.`semester_num` AS course_term, COUNT(e.id) AS total_courses_in_term FROM academic_periods ap JOIN enrollments e ON ap.id = e.period_id WHERE ap.student_id = 12 GROUP BY ap.student_id, ap.academic_year, ap.stage_number ORDER BY ap.stage_number ASC;

SELECT id_student, name_ar, name_en, yearr, SUBSTRING_INDEX(requirment, '-', 1) AS stage, SUBSTRING_INDEX(requirment, '-', -1) AS course_term, degree, units FROM `subjects_students_q` WHERE id_student = 12 ORDER BY stage ASC, `course_term` ASC , yearr ASC;

SELECT DISTINCT
    (SELECT `id` FROM `certificate_manager`.`students` WHERE `full_name_ar` = 
        (SELECT `name` FROM `project2`.`students_q` WHERE `id` = `ssq`.`id_student` LIMIT 1) LIMIT 1) AS s_id,
    (SELECT `full_name_ar` FROM `certificate_manager`.`students` WHERE `full_name_ar` = 
        (SELECT `name` FROM `project2`.`students_q` WHERE `id` = `ssq`.`id_student` LIMIT 1) LIMIT 1) AS s_name,
    `yearr` AS yearr, -- Calendar Year
    1 AS Annual, -- 1 = Annual System
    CASE 
        WHEN `requirment` LIKE '%اولى%' THEN 1
        WHEN `requirment` LIKE '%ثانية%' THEN 2
        WHEN `requirment` LIKE '%ثالثة%' THEN 3
        WHEN `requirment` LIKE '%رابعة%' THEN 4
        ELSE 1 
    END AS stage_number, -- stage_number
    CASE WHEN `requirment` LIKE '%كورس اول%' THEN 1 ELSE 2 END AS semester_num -- semester_num
FROM `project2`.`subjects_students_q` AS `ssq`
WHERE (SELECT `name` FROM `project2`.`students_q` WHERE `id` = `ssq`.`id_student` LIMIT 1) IS NOT NULL;

SELECT ap.student_id AS id_student, ap.academic_year AS yearr, CONCAT('مرحلة ', ap.stage_number) AS stage, ap.`semester_num` AS semester_num, e.id AS courses_in_term FROM academic_periods ap JOIN enrollments e ON ap.id = e.period_id WHERE ap.student_id = 10 ORDER BY ap.academic_year ASC, ap.stage_number ASC, semester_num ASC;

SELECT * FROM `subjects_students_140` WHERE id_student = 10 ORDER BY `yearr` ASC, `semester` ASC;