DELIMITER //

-- MODULE 10: THESIS RECORDS
CREATE PROCEDURE GetThesisByStudent(IN p_student_id INT)
BEGIN
    SELECT id, student_id, title_ar, title_en, defense_date, committee_decision, final_grade
    FROM thesis_records WHERE student_id = p_student_id ORDER BY id DESC;
END //

CREATE PROCEDURE InsertThesis(
    IN p_student_id INT, IN p_title_ar VARCHAR(500), IN p_title_en VARCHAR(500),
    IN p_defense_date DATE, IN p_committee_decision VARCHAR(100), IN p_final_grade FLOAT
)
BEGIN
    INSERT INTO thesis_records (student_id, title_ar, title_en, defense_date, committee_decision, final_grade) 
    VALUES (p_student_id, p_title_ar, p_title_en, p_defense_date, p_committee_decision, p_final_grade);
    SELECT LAST_INSERT_ID() AS new_id;
END //

CREATE PROCEDURE UpdateThesis(
    IN p_id INT, IN p_title_ar VARCHAR(500), IN p_title_en VARCHAR(500),
    IN p_defense_date DATE, IN p_committee_decision VARCHAR(100), IN p_final_grade FLOAT
)
BEGIN
    UPDATE thesis_records SET title_ar = p_title_ar, title_en = p_title_en, defense_date = p_defense_date, 
        committee_decision = p_committee_decision, final_grade = p_final_grade WHERE id = p_id;
END //

CREATE PROCEDURE DeleteThesis(IN p_id INT)
BEGIN
    DELETE FROM thesis_records WHERE id = p_id;
END //

-- MODULE 11: STUDENT SUPERVISORS
CREATE PROCEDURE GetSupervisorsByStudent(IN p_student_id INT)
BEGIN
    SELECT ss.id, ss.student_id, ss.personnel_id, ss.supervision_role,
           p.name_ar AS supervisor_name_ar, p.name_en AS supervisor_name_en, p.academic_title_ar, p.academic_title_en
    FROM student_supervisors ss JOIN personnel p ON ss.personnel_id = p.id
    WHERE ss.student_id = p_student_id ORDER BY ss.supervision_role ASC, p.display_order ASC;
END //

CREATE PROCEDURE InsertStudentSupervisor(IN p_student_id INT, IN p_personnel_id INT, IN p_supervision_role VARCHAR(50))
BEGIN
    INSERT INTO student_supervisors (student_id, personnel_id, supervision_role) VALUES (p_student_id, p_personnel_id, p_supervision_role);
    SELECT LAST_INSERT_ID() AS new_id;
END //

CREATE PROCEDURE UpdateStudentSupervisor(IN p_id INT, IN p_personnel_id INT, IN p_supervision_role VARCHAR(50))
BEGIN
    UPDATE student_supervisors SET personnel_id = p_personnel_id, supervision_role = p_supervision_role WHERE id = p_id;
END //

CREATE PROCEDURE DeleteStudentSupervisor(IN p_id INT)
BEGIN
    DELETE FROM student_supervisors WHERE id = p_id;
END //

DELIMITER ;
